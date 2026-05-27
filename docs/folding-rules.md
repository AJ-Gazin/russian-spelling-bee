# Folding rules

A *fold* answers the question "are two morphologically related lemmas one word or two for puzzle purposes?" This doc explains which folds the build pipeline applies (and why), which it doesn't (and why), and how to reason about adding a new one without needing to be a Russian linguist.

The pipeline is in [`backend/src/rsb/folds.py`](../backend/src/rsb/folds.py). The build script's per-build summary lives at [`backend/data/fold-report.md`](../backend/data/fold-report.md) — open it after every `python scripts/build_dictionary.py` to see exactly what fired this run.

---

## Background: Russian morphology in one screen

You don't need to be fluent to maintain this code, but you do need to know the categories pymorphy3 distinguishes. The folds are defined in terms of these tags:

| Tag | What it is | Example |
|---|---|---|
| `NOUN` | Noun | дом, кот, ребёнок |
| `VERB` | Finite verb form (past/present/future tense) | читаю, читал, прочитают |
| `INFN` | Infinitive (the citation form of a verb) | читать, прочитать |
| `ADJF` | Long-form adjective (the dictionary form) | красивый, высокий |
| `ADJS` | Short-form adjective | красив, высок (predicative usage) |
| `COMP` | Synthetic comparative | быстрее, выше, лучше |
| `PRTF` | Full participle (a verb form that acts as an adjective) | пишущий "writing", написанный "written" |
| `PRTS` | Short participle | написан |
| `GRND` | Gerund (verbal adverb) | читая, прочитав |
| `ADVB` | Adverb | быстро, абсолютно |
| `PRED` | Predicative ("it is …") | нужно, ясно, видно |
| `PRCL` | Particle | же, ли, бы |
| `Refl` | Reflexive grammeme (added to verb tags for `-ся` verbs) | мыться is tagged `INFN,impf,intr,Refl` |

Russian verbs come in **aspect pairs**: imperfective (ongoing action: писать) vs perfective (completed action: написать). The two are often morphologically related but lexically distinct enough that L–S lists them as separate lemmas.

The four phenomena the folding rules consider:

1. **Reflexives** — `-ся` / `-сь` verbs (мыться, учиться). Always a distinct lemma in pymorphy3; sometimes only one member of the pair (transitive vs reflexive) is in L–S.
2. **Participles** — verb forms ending in -щий / -вший / -нный / -мый that grammatically pattern as adjectives. Some lexicalize into standalone adjectives (бывший "former"); most don't.
3. **Short adjectives** — masculine, feminine, neuter, plural short forms used in predicative position (он красив "he is handsome"). Almost always derivable from the long form.
4. **Synthetic comparatives** — single-word comparatives (быстрее) versus periphrastic (более быстрый). Often have a base adjective.

---

## What ships in `rsb.folds.compute_folds`

### Rule 1: reflexive alias (`X ↔ X+ся`)

**What:** When L–S has one member of a reflexive pair but pymorphy3 knows the other exists as a real word, add a lemma→lemma alias so a player typing a form of the missing partner credits the present one.

**Why:** The motivating bug: L–S has `наедаться` (0.7 ipm) and `наесться` (4.3 ipm) but not the transitive imperfective `наедать`. A player typing `наедал` had it pymorphy3-lemmatized to `наедать`, which wasn't in the dict, and rejected. With the alias `наедать → наедаться` in the table, the lemmatizer falls back to the alias target.

**Guards:**
- Pymorphy3's `dictionary.word_is_known(partner)` must return True. This is critical: pymorphy3 will morphologically *predict* a `-ся` partner for almost any verb (`*быться` for `быть`, `*любиться` for `любить`), but those forms aren't in actual corpora. The `word_is_known` filter weeds them out.
- The partner must round-trip as a verb (pymorphy3 lemmatizes the partner to itself with a VERB/INFN tag).

**Both directions are produced:**
- `base → reflexive` (424 entries today): the dict has the reflexive, the base is missing. Sample: `случить → случиться`, `согласить → согласиться`, `стремить → стремиться`, **`наедать → наедаться`**. These are mostly *reflexiva tantum* — verbs that exist primarily or only in reflexive form.
- `reflexive → base` (2,469 entries today): the dict has the transitive base, the reflexive is missing. Sample: `позвониться → позвонить`, `проходиться → проходить`. These are reflexive forms pymorphy3 recognizes that L–S didn't list separately.

**Risk:** Low. Aliases are purely additive (they only add acceptances, never remove them). The worst failure mode is "player types a typo that happens to parse to an aliased lemma and gets credit they didn't deserve" — but for that to happen, the typo had to be a *valid Russian form* in the first place.

### Rule 2: participle merger (`PRTF lemma → parent verb`)

**What:** Remove from the dict an ADJF-tagged lemma when (a) pymorphy3's top parse of the lemma is PRTF pointing to a verb Y, (b) Y is in the dict as VERB, (c) the candidate's L–S frequency is below 20 ipm. The candidate's frequency is absorbed into Y so puzzle weighting reflects combined usage.

**Why:** L–S lists many productive participles as their own adjective entries (`сверкающий`, `доминирующий`, `гарантированный`). Players don't think of these as distinct from the verb. After the merger, a player typing `сверкающий` parses to `сверкать` (pymorphy3's PRTF reading) and credits the verb directly.

**Three independent guards:**

1. **Top-parse rule.** Pymorphy3 ranks parses by score. If the *top* parse is ADJF (not PRTF), pymorphy3 itself has judged this lemma to be lexicalized as an adjective — we don't merge. This automatically protects all the classical lexicalized participles:
   - `бывший` "former" — top parse ADJF (PRTF→быть is parse #3)
   - `следующий` "next, following" — top parse ADJF
   - `текущий` "current" — top parse ADJF
   - `будущий` "future" — top parse ADJF
   - `грядущий` "coming" — top parse ADJF
   - `настоящий` "real, present" — top parse ADJF

2. **Candidate-POS gate.** L–S must have tagged the candidate `a` (mapped to ADJF). If L–S says it's PRED or ADVB, we respect that judgment. This is what stops the short-adj rule from devouring -о adverbs (see Rule 3).

3. **Frequency cutoff (20 ipm).** Even if pymorphy3 ranks PRTF first, a candidate with its own freq ≥ 20 ipm has enough independent corpus presence that we leave it alone. Today this protects 7 lemmas: `соответствующий`, `обязанный`, `действующий`, `положенный`, `напряжённый`, `специализированный`, `принятый`.

**Today's impact:** 81 lemmas merged out of the dict. Sample (highest source-freq merged): `образованный` (19.4) → `образовать`, `цивилизованный` (18.4) → `цивилизовать`, `организованный` (16.4) → `организовать`, `отдалённый` (16.0) → `отдалить`, `сверкающий` (8.0) → `сверкать`.

**Risk:** Low after all three guards. The dominant failure mode would be merging a participle that *did* lexicalize but L–S didn't reach 20 ipm to flag it. Diff review (`backend/data/fold-report.md`) catches these case-by-case.

### Rule 3: short adjective merger (`ADJS lemma → parent ADJF`)

**What:** Same shape as Rule 2 but with `ADJS` as the folding tag and `ADJF→ADJF` as the parent relationship. Conditions: top parse is ADJS, candidate POS is ADJF in our dict, target ADJF in dict, candidate freq < 20 ipm.

**Why:** Short adjective forms (красив, мил, высок) are nearly always derivable from the long form (красивый, милый, высокий). If L–S ever ships a short form as its own ADJF-tagged lemma, this rule will merge it.

**Today's impact:** zero mergers. L–S 2011 doesn't seem to ship pure short-form lemmas. One protected entry: `намерен` (35.7 ipm, would have merged into `намеренный`) — borderline case where the short form is genuinely common and L–S treated it specially.

**Why the candidate-POS gate matters specifically here:** ~1,400 *adverbs* in the dict (forms like `абсолютно`, `аккуратно`, `вежливо`) have a *secondary* ADJS reading pointing to their long adjective (`абсолютный`). Without the POS=ADJF gate, all 1,400 would be erroneously merged and the player typing the adverb would get credited with the adjective. The gate trusts L–S's editorial judgment that these are adverbs, not short adjectives.

### Rule 4: comparative merger (`COMP lemma → parent ADJF`)

**What:** Same shape. Conditions: top parse is COMP, candidate POS is COMP in dict, target ADJF in dict, candidate freq < 20 ipm.

**Why:** Synthetic comparatives like *красивее* lemmatize to their base adjective *красивый*. If L–S lists a comparative as its own COMP lemma, this rule merges it.

**Today's impact:** zero mergers. L–S 2011 contains zero COMP-tagged lemmas (the `comp` POS in `POS_KEEP` is a watchdog mapping). The high-frequency synthetic comparatives that *do* exist as separate lemmas (`больше` 634 ipm, `лучше`, `выше`) are all tagged ADVB in L–S, so the candidate-POS gate excludes them — correctly, because in modern usage these have lexicalized far enough that crediting `больше` as `большой` would feel wrong to a player.

---

## What does NOT ship (and why)

### Aspect-pair folding (`читать ↔ прочитать`)

**Not shipped.** Russian verbs come in aspect pairs (imperfective / perfective) that differ by prefix (по-, про-, на-, с-), suffix (-ыв-, -ва-), or stem alternation. Examples:
- читать (impf) / прочитать (perf) — semantically very close
- делать / сделать — close
- писать / написать — close
- говорить / сказать — suppletive, no morphological link
- брать / взять — suppletive

**Why deferred:** No mechanical rule distinguishes "purely aspectual prefix" from "prefix carrying semantic load." `на-` in `наесть` adds "eat fully" semantics; in `прочитать` `про-` is essentially vacuous. Auto-folding either over- or under-merges depending on the case. Suppletive pairs (`говорить/сказать`) can't be handled by any morphological rule at all and would need an explicit pair table (which OpenCorpora has some of, but coverage is incomplete).

**Signal to reconsider:** if play data shows players consistently expecting that finding the imperfective should credit the perfective (or vice versa), revisit by either (a) curating a pair table for the most common cases or (b) folding only specific high-confidence prefixes.

### Productive prefix folding (general `pre + verb → verb`)

**Not shipped.** Russian verbal prefixes are productive but semantically loaded. `наедать` (eat onto a surface, eat in excess) ≠ `есть` (eat). `припомнить` (recall with effort) is its own concept apart from `помнить` (remember). Folding any prefixed verb to its base would silently collapse distinctions the player cares about.

**Signal to reconsider:** never, probably. If the goal is "more lemmas pass dictionary lookup," union with a richer frequency-weighted source (see `docs/` — the OpenCorpora-corpus union experiment is the right tool, not prefix collapsing).

### Verbal noun folding (`-ние` / `-тие` → parent verb)

**Not shipped.** Verbal nouns are highly productive (понимание, чтение, написание, выполнение) but very often lexicalize into independent concepts (понимание "understanding" — the abstract noun, not just "[the act of] understanding"). Folding wholesale would lose nuance players notice.

**Signal to reconsider:** worth a fresh audit if a future play-data report shows many "I found понимать but the puzzle also wants понимание" complaints.

### Diminutives and augmentatives (`-ик`, `-чик`, `-очк-`, `-ищ-`)

**Not shipped as a rule.** Russian diminutives are extremely productive but almost always semantically distinct (`дом` "house" vs `домик` "little house"). The existing `backend/data/overrides.yaml` curates ~27 case-by-case excludes (`садик`, `котик`, `домик`) on the principle that the diminutive is *too transparently a small-X* to deserve its own dict slot in a puzzle context. The line is editorial; per-word judgment is correct here.

**How to extend:** add to `overrides.yaml` `exclude:` list. Re-run the build (or just restart the API — overrides are re-applied at startup).

### Gerunds (`-я`, `-в`, `-вши`)

**Not relevant.** Pymorphy3 emits gerunds (GRND tag) as forms of the parent verb, not as standalone lemmas — they never enter the dict as separate entries. The form-fitness rule already credits gerund forms to the verb.

---

## How to judge a new fold proposal

You don't need linguistic intuition for individual lemmas. You need to apply the same three-part filter the existing rules use:

1. **Does pymorphy3 already make the distinction we want?** If yes, the fold is mostly a question of "which side of the pair is in our dict and which is missing." If no, the fold needs a hand-curated source.
2. **Does L–S's POS tag make the distinction?** L–S did a lot of editorial work. If you find yourself overriding their POS choices, you're probably wrong.
3. **Is there a frequency floor that protects lexicalized cases?** 20 ipm has worked here; tune per-rule if needed.

When in doubt, **defer the rule and add specific cases to `overrides.yaml`** instead. Overrides are case-by-case; rules are categorical. Overrides can't accidentally take down 1,000 lemmas at 3am; rules can.

### The diff-review workflow

Every dictionary build writes `backend/data/fold-report.md`. After running the build:

1. Open the report.
2. Scan the "Mergers applied" list. For each rule, do the top-20 by frequency look like things you'd be happy to silently fold? If yes, ship. If no, raise the freq cutoff for that rule or tighten the candidate-POS gate.
3. Scan the "Protected by frequency cutoff" list. These are candidates the rule *would* have folded but the freq protected. Do any of them look like things you'd actually want folded? If many, lower the cutoff. If few/none, the cutoff is right.
4. Spot-check the "Aliases added" list — pick 10 random entries per direction, eyeball them.

This is the maintenance loop. **You're reviewing categories, not words.** Each review is a one-time check per rule edit, not an ongoing per-lemma task.

---

## Implementation pointers

- **Rule definitions:** [`backend/src/rsb/folds.py`](../backend/src/rsb/folds.py) — `_compute_reflexive_aliases`, `_compute_mergers`.
- **DB tables:** `lemmas` (existing) and `aliases` (new in schema v3) in [`backend/src/rsb/store.py`](../backend/src/rsb/store.py).
- **Lemmatizer integration:** [`backend/src/rsb/lemmatizer.py`](../backend/src/rsb/lemmatizer.py) — `Lemmatizer(aliases=...)` consults the alias map only after all direct parses fail.
- **Build wiring:** [`backend/scripts/build_dictionary.py`](../backend/scripts/build_dictionary.py) calls `compute_folds` after overrides, writes both tables, and emits `data/fold-report.md`.
- **API wiring:** [`backend/src/rsb/api.py`](../backend/src/rsb/api.py) loads aliases at startup and passes them to the `Lemmatizer`.
- **Tests:** [`backend/tests/test_folds.py`](../backend/tests/test_folds.py) — one test per guard, one per rule.

To **add** a new rule, extend `_compute_mergers` (for a merger) or write a new `_compute_*_aliases` function (for an alias rule). Always include a corresponding test that demonstrates the rule *fires* on a positive case AND *doesn't fire* on at least one tricky negative case (a `следующий` analogue for your new rule).

To **tune** a rule, change `DEFAULT_FREQ_CUTOFF` or pass a custom value via the build script. Adjusting one number rebuilds the dict and writes a new report; compare side-by-side via `git diff backend/data/fold-report.md`.
