"""Per-POS folding rules for the dictionary build pipeline.

Folding answers the question *"are two morphologically related lemmas one
word or two for puzzle purposes?"* The pipeline supports two kinds of fold:

* **Alias fold** (rule 1, reflexive ↔ base verb). The dictionary keeps the
  lemma it already has; we add a side-table mapping the *missing* partner to
  the present one. The lemmatizer consults the map when a parse points at a
  lemma not in the puzzle's valid set, so e.g. a player who types *наедал*
  (parses to `наедать`, not in L–S) is credited with `наедаться` (in L–S).
  No lemmas are added or removed.

* **Merger fold** (rules 2/3/4 — participle / short adjective / synthetic
  comparative). The dictionary's secondary lemma is *removed* and its
  frequency is added to the surviving "parent" lemma. The lemmatizer needs
  no changes here because pymorphy3 already returns a parse pointing to the
  parent (PRTF→VERB, ADJS→ADJF, COMP→ADJF) alongside the parse pointing to
  the lemma being removed; once removed, the parent parse wins by default.

Each merger rule uses three guards in combination to stay conservative:

1. **Top-parse rule**: pymorphy3 must read the candidate's TOP parse with the
   folding tag (PRTF/ADJS/COMP). This protects lemmas that are *primarily*
   something else even though pymorphy3 also offers a secondary reading —
   e.g. the adverb *абсолютно* has a secondary ADJS reading, but its top
   parse is ADVB, so the short-adjective fold leaves it alone.

2. **Candidate-POS gate**: L–S must already have tagged the candidate with
   the right POS (ADJF for PRTF/ADJS folds, COMP for the comparative fold).
   This trusts L–S's editorial judgment about whether a lemma is, say, an
   adverb (PRED) or a short adjective (ADJF). The L–S 2011 list contains
   zero COMP-tagged lemmas, so rule 4 is mostly a watchdog today.

3. **Frequency cutoff** (`DEFAULT_FREQ_CUTOFF`, 20 ipm). Above this floor a
   lemma is "lexicalized enough that players think of it as its own word."
   This is the imperfect-but-defensible proxy for the linguistic judgment
   we'd otherwise have to make per-word: *бывший*, *следующий*, *текущий*
   etc. all sit above the floor and stay; productive participles like
   *сверкающий*, *доминирующий* sit below it and merge into the verb.

See `docs/folding-rules.md` for the why/what/how-to-judge writeup intended
for non-linguist maintainers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

# Lemmas at or above this frequency are treated as lexicalized — they retain
# their own dictionary entry even when the merger conditions match. See
# docs/folding-rules.md for why 20 ipm and how to tune.
DEFAULT_FREQ_CUTOFF: float = 20.0

# Rule identifiers — recorded in the aliases table and the human-readable
# report so a future bug bisect can ask "which rule produced this alias?"
RULE_REFLEXIVE_BASE_TO_REFL = "reflexive:base->refl"
RULE_REFLEXIVE_REFL_TO_BASE = "reflexive:refl->base"
RULE_PARTICIPLE_MERGE = "participle->verb"
RULE_SHORT_ADJ_MERGE = "short-adj->long-adj"
RULE_COMPARATIVE_MERGE = "comparative->adj"


@dataclass(slots=True)
class FoldReport:
    """Per-rule counts and samples for the build script's report output."""

    # alias entries: (source_lemma, target_lemma, rule_id)
    aliases_added: list[tuple[str, str, str]] = field(default_factory=list)
    # mergers actually applied: (source_lemma, target_lemma, rule_id, source_freq)
    mergers_applied: list[tuple[str, str, str, float]] = field(default_factory=list)
    # mergers blocked by the freq cutoff: same shape — useful to see what
    # would have merged if you lowered the cutoff
    mergers_protected_by_freq: list[tuple[str, str, str, float]] = field(default_factory=list)

    def alias_count_by_rule(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for _, _, rule in self.aliases_added:
            out[rule] = out.get(rule, 0) + 1
        return out

    def merger_count_by_rule(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for _, _, rule, _ in self.mergers_applied:
            out[rule] = out.get(rule, 0) + 1
        return out


def _tag_set(parse) -> set[str]:
    return set(str(parse.tag).replace(",", " ").split())


def _has_self_parse_with_tag(morph, lemma: str, required_tag: str) -> bool:
    """True iff `lemma` has any parse whose normal_form is itself AND whose
    tag set contains `required_tag` (e.g. 'VERB' or 'INFN')."""
    for p in morph.parse(lemma):
        if p.normal_form != lemma:
            continue
        if required_tag in _tag_set(p):
            return True
    return False


def _is_verb_self_parse(morph, lemma: str) -> bool:
    """True iff `lemma` round-trips through pymorphy3 with a verb-like tag.
    pymorphy3 distinguishes INFN (infinitive) from VERB (finite forms); both
    count for verb identification."""
    for p in morph.parse(lemma):
        if p.normal_form != lemma:
            continue
        tags = _tag_set(p)
        if "VERB" in tags or "INFN" in tags:
            return True
    return False


# ---------- Rule 1: reflexive alias ----------------------------------------


def _compute_reflexive_aliases(
    morph,
    in_dict: dict[str, tuple[str, float]],
) -> list[tuple[str, str, str]]:
    """Return alias entries (source, target, rule) for the reflexive fold.

    Two directions:

    * **base → reflexive** — for each `-ся` verb in dict, if the corresponding
      non-reflexive base is not in dict but pymorphy3 *knows* it as a verb
      (`word_is_known` AND round-trips with a VERB/INFN tag), add an alias so
      that a player typing the base credits the reflexive partner. This is
      the *наедать → наедаться* class.

    * **reflexive → base** — symmetric: for each non-`-ся` verb in dict, if
      the `+ся` partner is missing from dict but pymorphy3 knows it, alias
      reflexive→base. Covers cases where L–S has the transitive verb but
      not its reflexive partner.

    The `word_is_known` filter is critical: pymorphy3's morphological
    generator will *predict* a `-ся` partner for almost any verb (`быться`
    for `быть`, `любиться` for `любить`), but those are hallucinated forms
    not seen in actual corpora. Filtering on `word_is_known` keeps only the
    aliases where pymorphy3's bundled OpenCorpora dictionary recognizes the
    word as a real form.
    """
    out: list[tuple[str, str, str]] = []
    d = morph.dictionary
    for lemma, (pos, _freq) in in_dict.items():
        if pos != "VERB":
            continue
        # Direction 1: this lemma is reflexive, base is missing
        if lemma.endswith("ся"):
            base = lemma[:-2]
            if base and base not in in_dict and d.word_is_known(base) and _is_verb_self_parse(morph, base):
                out.append((base, lemma, RULE_REFLEXIVE_BASE_TO_REFL))
        # Direction 2: this lemma is the base, reflexive partner is missing
        elif not lemma.endswith("сь"):  # exclude past-tense reflexive-like artifacts
            refl = lemma + "ся"
            if refl not in in_dict and d.word_is_known(refl) and _is_verb_self_parse(morph, refl):
                out.append((refl, lemma, RULE_REFLEXIVE_REFL_TO_BASE))
    return out


# ---------- Rules 2/3/4: merger folds --------------------------------------


def _compute_mergers(
    morph,
    in_dict: dict[str, tuple[str, float]],
    freq_cutoff: float,
) -> tuple[list[tuple[str, str, str, float]], list[tuple[str, str, str, float]]]:
    """Return (mergers_applied, mergers_protected_by_freq).

    For each lemma X in `in_dict`, look at pymorphy3's TOP parse (the
    highest-`.score` reading). Three independent merger conditions:

    * PRTF → VERB: X is read as a participle of a verb Y; if X's POS in
      our dict is ADJF and Y is in our dict as VERB, X is a participle
      merger candidate.
    * ADJS → ADJF: X is read as a short form of an adjective Y; if X's POS
      is ADJF and Y is in our dict as ADJF, X is a short-adj candidate.
    * COMP → ADJF: X is read as a comparative of an adjective Y; if X's POS
      is COMP and Y is in our dict as ADJF, X is a comparative candidate.

    Candidates with `freq >= freq_cutoff` are reported separately as
    "protected by freq" but not merged — these are the lexicalized forms
    the player thinks of as standalone words (см. `бывший`, `следующий`,
    `текущий`).
    """
    applied: list[tuple[str, str, str, float]] = []
    protected: list[tuple[str, str, str, float]] = []

    for lemma, (pos, freq) in in_dict.items():
        parses = morph.parse(lemma)
        if not parses:
            continue
        top = parses[0]
        tags = _tag_set(top)
        target = top.normal_form
        if target == lemma or target not in in_dict:
            continue
        target_pos = in_dict[target][0]

        rule: str | None = None
        if "PRTF" in tags and pos == "ADJF" and target_pos == "VERB":
            rule = RULE_PARTICIPLE_MERGE
        elif "ADJS" in tags and pos == "ADJF" and target_pos == "ADJF":
            rule = RULE_SHORT_ADJ_MERGE
        elif "COMP" in tags and pos == "COMP" and target_pos == "ADJF":
            rule = RULE_COMPARATIVE_MERGE

        if rule is None:
            continue
        if freq >= freq_cutoff:
            protected.append((lemma, target, rule, freq))
        else:
            applied.append((lemma, target, rule, freq))

    return applied, protected


# ---------- Public entry point ---------------------------------------------


def compute_folds(
    rows: Iterable[tuple],
    morph,
    *,
    freq_cutoff: float = DEFAULT_FREQ_CUTOFF,
) -> tuple[list[tuple], list[tuple[str, str, str]], FoldReport]:
    """Apply all four folding rules to a list of compiled dictionary rows.

    Input `rows` is the 5-tuple shape used by the build pipeline:
        (lemma, pos, freq_ipm, mask, form_masks)

    Returns `(new_rows, aliases, report)` where:
        - `new_rows` is `rows` with merged lemmas removed and their freq
          absorbed into the surviving parent lemma (freq sums; mask and
          form_masks of the parent are left untouched on the assumption
          that pymorphy3's parent-lexeme enumeration already covers the
          merged forms — which is the case for participles, short forms
          and comparatives, all of which are members of the parent's
          lexeme).
        - `aliases` is a list of `(source_lemma, target_lemma, rule)`
          tuples to persist in the aliases table and feed to the Lemmatizer.
        - `report` is a `FoldReport` summarizing what happened and what
          was protected by the freq cutoff.
    """
    rows_list = list(rows)
    if rows_list and len(rows_list[0]) != 5:
        raise ValueError(
            f"compute_folds expects 5-tuple rows (lemma, pos, freq, mask, form_masks); "
            f"got arity {len(rows_list[0])}"
        )

    in_dict: dict[str, tuple[str, float]] = {r[0]: (r[1], r[2]) for r in rows_list}

    # Rule 1: aliases (no row changes)
    aliases = _compute_reflexive_aliases(morph, in_dict)

    # Rules 2/3/4: mergers (row changes)
    mergers, protected = _compute_mergers(morph, in_dict, freq_cutoff)

    # Apply mergers: drop merged rows, add their freq to the parent row.
    merge_targets: dict[str, float] = {}
    drops: set[str] = set()
    for src, tgt, _rule, src_freq in mergers:
        drops.add(src)
        merge_targets[tgt] = merge_targets.get(tgt, 0.0) + src_freq

    new_rows: list[tuple] = []
    for row in rows_list:
        lemma = row[0]
        if lemma in drops:
            continue
        if lemma in merge_targets:
            # freq is index 2 in the 5-tuple
            new_rows.append((row[0], row[1], row[2] + merge_targets[lemma], row[3], row[4]))
        else:
            new_rows.append(row)

    report = FoldReport(
        aliases_added=aliases,
        mergers_applied=mergers,
        mergers_protected_by_freq=protected,
    )
    return new_rows, aliases, report


def report_markdown(report: FoldReport, *, sample_size: int = 25) -> str:
    """Render a `FoldReport` as a human-readable markdown document.

    Sorts samples by frequency descending so the highest-impact entries are
    visible first. Truncates to `sample_size` per rule.
    """
    lines: list[str] = []
    lines.append("# Folding rules — build report")
    lines.append("")
    lines.append("Generated by `scripts/build_dictionary.py` via `rsb.folds.compute_folds`.")
    lines.append("See `docs/folding-rules.md` for the rule definitions and rationale.")
    lines.append("")

    # --- aliases summary
    by_alias = report.alias_count_by_rule()
    lines.append("## Aliases added")
    lines.append("")
    lines.append(f"Total: **{len(report.aliases_added)}** aliases across {len(by_alias)} rule(s).")
    lines.append("")
    for rule, n in sorted(by_alias.items()):
        lines.append(f"- `{rule}`: {n}")
    lines.append("")
    if report.aliases_added:
        lines.append("### Samples (alphabetical, first per rule)")
        lines.append("")
        seen_rules: set[str] = set()
        by_rule: dict[str, list[tuple[str, str]]] = {}
        for src, tgt, rule in report.aliases_added:
            by_rule.setdefault(rule, []).append((src, tgt))
        for rule, pairs in sorted(by_rule.items()):
            lines.append(f"**{rule}**")
            for src, tgt in sorted(pairs)[:sample_size]:
                lines.append(f"  - `{src}` → `{tgt}`")
            lines.append("")

    # --- mergers summary
    by_merger = report.merger_count_by_rule()
    lines.append("## Mergers applied")
    lines.append("")
    lines.append(f"Total: **{len(report.mergers_applied)}** lemmas removed (frequency absorbed into parent).")
    lines.append("")
    for rule, n in sorted(by_merger.items()):
        lines.append(f"- `{rule}`: {n}")
    lines.append("")
    if report.mergers_applied:
        lines.append("### Samples (highest source-freq per rule)")
        lines.append("")
        by_rule_m: dict[str, list[tuple[str, str, float]]] = {}
        for src, tgt, rule, freq in report.mergers_applied:
            by_rule_m.setdefault(rule, []).append((src, tgt, freq))
        for rule, items in sorted(by_rule_m.items()):
            lines.append(f"**{rule}**")
            for src, tgt, freq in sorted(items, key=lambda x: -x[2])[:sample_size]:
                lines.append(f"  - `{src}` ({freq:.1f} ipm) → `{tgt}`")
            lines.append("")

    # --- protected
    lines.append("## Protected by frequency cutoff")
    lines.append("")
    lines.append(f"Total: **{len(report.mergers_protected_by_freq)}** candidates kept (lemma's own freq ≥ cutoff).")
    lines.append("")
    if report.mergers_protected_by_freq:
        lines.append("These would have merged under a lower freq cutoff. They stayed because the")
        lines.append("lemma is lexicalized — players treat it as a standalone word.")
        lines.append("")
        by_rule_p: dict[str, list[tuple[str, str, float]]] = {}
        for src, tgt, rule, freq in report.mergers_protected_by_freq:
            by_rule_p.setdefault(rule, []).append((src, tgt, freq))
        for rule, items in sorted(by_rule_p.items()):
            lines.append(f"**{rule}**")
            for src, tgt, freq in sorted(items, key=lambda x: -x[2])[:sample_size]:
                lines.append(f"  - `{src}` ({freq:.1f} ipm) — would have merged into `{tgt}`")
            lines.append("")

    return "\n".join(lines)
