> **Frozen reference, not canonical.**
> This is the original planning document, preserved unchanged for context. It is **not** the live specification. The canonical, up-to-date description of what is actually implemented on this branch lives in [`../STATUS.md`](../STATUS.md). The canonical to-do list lives in [`../todo.md`](../todo.md). Where the live implementation diverges from this document, `STATUS.md` wins.

# Russian Spelling Bee — design document

## Context

A daily word puzzle in the spirit of the NYT Spelling Bee, played within a small family group of fluent Russian speakers living in the United States. Adult academic and professional life in English produces a slow attrition of active Russian vocabulary that isn't matched by any equivalent decay in passive vocabulary. A puzzle that systematically rewards finding the breadth of what you actively know — and occasionally surfaces a word you'd forgotten you knew — is the inverse pressure.

This is not a study tool. The audience does not need to be taught Russian grammar, and the puzzle should not feel pedagogical. It should feel like a game, with the same texture and pacing as the English Spelling Bee: a few easy finds at the start, a long middle stretch of searching, and a satisfying late-game where you scrape out the last few words you didn't see at first.

## The central design problem

NYT Spelling Bee omits the letter S to suppress noun plurals and third-person singular verbs. The point of that omission is morphological: without it, every singular noun and every third-person verb form would appear as separate entries, padding the puzzle with mechanical low-information solutions.

Russian inflection cannot be controlled by a single-letter omission. A noun like *дом* has twelve singular and plural forms across six cases. A verb like *читать* has dozens of conjugated and participial forms before counting prefixed perfectives. An adjective like *красивый* declines for three genders, six cases, two numbers, and carries separate short forms. The inflectional load is carried by many suffixes and stem alternations, none of which reduce to a single letter. A direct S-omission analog — banning Ь, for instance — would either gut a major part of speech (verbs in -ть) or fail to address the underlying problem (noun cases survive any single-letter ban).

The correct analog is one level up the abstraction stack: **lemma-level scoring**. The player types any inflected form. The game maps that form to its dictionary headword via a morphological analyzer and credits the headword once. Subsequent forms of the same headword return *уже найдено*. This collapses the entire inflectional space — all cases, numbers, genders, tenses, aspects, persons — in a single rule, and it does so without restricting which parts of speech the puzzle admits.

## Lemma specification

Each valid word resolves to exactly one canonical form. The mapping by part of speech:

| Part of speech | Canonical form | Examples |
|---|---|---|
| Noun | Nominative singular | дом, окно, дверь |
| Pluralia tantum | Nominative plural | ножницы, сани, очки, сутки |
| Indeclinable loanword | The single attested form | метро, кафе, такси |
| Adjective | Masculine nominative singular, long form | красивый, тёплый, синий |
| Verb | Infinitive | читать, идти, мочь |
| Adverb | The attested form | быстро, вчера, наверху |
| Numeral | Nominative | пять, сто, тысяча |
| Predicative | The attested form | можно, нужно, жаль |
| Verbal noun in -ние/-тие | Nominative singular | чтение, решение, развитие |

Pronouns are excluded as a class. They are closed-class, their nominative forms are mostly short and over-familiar, and admitting them would dilute the four-letter tier.

A few categories require explicit treatment:

**Aspect pairs are separate lemmas.** *Читать* and *прочитать* are distinct entries with distinct meanings, both accepted if the hive admits them. This follows Russian lexicographic convention and produces the occasional satisfying moment where a well-shaped hive yields both members of a pair.

**Reflexive -ся verbs follow dictionary precedent.** If the -ся form has its own dictionary entry with a separate definition, it counts as a separate lemma (*учить* vs. *учиться*, *встретить* vs. *встретиться*); if it appears under the base verb as a passive or reflexive use, it does not (*читать* vs. *читаться*).

**Diminutives are excluded as separate lemmas.** *Дом* counts; *домик, домишко, домище* do not. Diminutive formation in Russian is productive enough that admitting them would recreate the morphology-grinding problem under a different name.

**Substantivized adjectives** that have their own dictionary headwords are separate lemmas: *мороженое, столовая, учёный* (as noun), *прохожий*.

**Participles** collapse to their source verb. *Читающий, читавший, прочитанный, читаемый* all resolve to *читать* or *прочитать*. The exception is participles that have drifted into independent dictionary entries.

**Short adjective forms** collapse to the long form. **Synthetic comparatives** with their own headword (*лучше, хуже, больше, меньше*) count separately; productive comparatives (*красивее, новее*) collapse to the adjective.

## Alphabet and hive composition

The effective alphabet is 31 letters: the standard Russian 33, minus Ъ (excluded entirely — frequency below 0.05% makes pangram construction with it impractical) and with Ё treated as a typographic variant of Е. The hive displays Е; the lemmatizer accepts either Е or Ё on input.

No other letters are excluded. Ь is part of legitimate vocabulary across every open-class part of speech, and the lemma rule already does the work that letter omission was trying to do.

The seven-letter hive is sampled under the following constraints:

- Seven distinct letters from the 31-letter pool.
- At least two vowels from А, Е, И, О, У, Ы, Э, Ю, Я. A single-vowel hive admits almost no valid Russian lemmas.
- Letter selection is frequency-weighted, with floors that ensure rare letters (Ф, Ц, Щ, Э) rotate through over weeks.
- The center letter is chosen from the seven, weighted by the number of dictionary lemmas containing it. This avoids centers like Ф that would produce sparse puzzles, while still permitting them occasionally for variety.

## Dictionary

The base list is the intersection of OpenCorpora (the morphological dictionary backing pymorphy3) with the Lyashevskaya & Sharov 2009 frequency list from the Russian National Corpus. The frequency threshold for inclusion is **0.5 ipm** — approximately the top 30,000–40,000 lemmas. This is more generous than the threshold a public game would use; the audience here is fluent and literary, and capable of (and entertained by) encountering the occasional less-common word.

Standard exclusions:

- Proper nouns and adjectives derived from them.
- Diminutives, augmentatives, and other productively-derived forms whose base is already in the list.
- Recent anglicisms not yet naturalized in mainstream dictionaries (*хайп, кринж, дайджест*). Naturalized loanwords (*интернет, метро, компьютер, кафе, такси*) stay.
- Crude vocabulary and мат.
- Initialisms and pronounceable acronyms (*вуз, ЦК, ГЭС*).
- Hyphenated and multi-token entries (*тёмно-синий, диван-кровать, кое-кто*).

Manual additions specific to the family are acceptable — household terms, in-jokes that have crossed into common use, place-name common-nouns. The list is editable; this is one of the privileges of running it for personal use rather than shipping it.

**Pangram quality threshold.** Every published puzzle includes at least one pangram whose lemma frequency exceeds **2 ipm**. This is looser than the 5 ipm threshold a public game would want, because the audience appreciates a slightly literary or archaic pangram as a small reward, but it filters out genuinely obscure dictionary curiosities that would only frustrate.

## Puzzle generation

The daily puzzle is selected by enumeration over the candidate space:

1. Sample a candidate seven-letter set under the alphabet and composition rules.
2. For each of the seven letters as a candidate center, compute the full set of dictionary lemmas containing only those seven letters and including the center.
3. Reject if any of: fewer than 25 valid lemmas; more than 70 valid lemmas; no pangram meeting the 2 ipm threshold; or any single lemma accounts for more than 25% of total available score (which produces a puzzle that feels binary — either you find the one big word or you don't).
4. Among accepted candidates, vary difficulty by day of week: closer to 25–35 lemmas Monday through Wednesday, closer to 50–70 lemmas Thursday through Sunday. NYT does this and the rhythm transfers cleanly.

A week of puzzles is generated in advance, skimmed for anything that looks off, and queued. The light editorial pass is something a public game can't sustain but a personal project can — and it's the single highest-leverage way to keep the puzzles feeling considered rather than algorithmic.

## Scoring and progression

Length-based scoring carries over from NYT directly:

- Four-letter words: 1 point.
- Five-or-more letter words: 1 point per letter (so a six-letter word is 6 points).
- Pangrams: +7 bonus on top of the length score.

The four-letter minimum stays. Russian has enough four-letter lemmas (*окно, поле, мост, ночь, день, путь, утро, пара, мера, лето, мама, мера, пора, рука*) to make the entry tier satisfying without descending to three-letter trivia.

Rank labels and thresholds follow the convention WordBee established, which Russian players who've played any Spelling-Bee-style game already recognize:

| Rank | Threshold (% of total) |
|---|---|
| Новичок | 0% |
| Ученик | 5% |
| Опытный | 12% |
| Мастер | 25% |
| Профи | 40% |
| Эксперт | 55% |
| Гуру | 70% |
| Легенда | 85% |
| Гений | 100% |

The percentages are NYT's, adjusted slightly upward at the top for the longer typical lemma length in Russian. They're a reasonable starting point and worth tuning after a few weeks of actual play data — see *Open questions*.

## UI / UX details that matter

A handful of small details largely determine whether the puzzle feels good. Most are cheap to implement; all are absent from existing Russian implementations.

**Show the lemma resolution when a word is accepted.** When the player types *домами*, the success message shows *домами → дом, зачтено*. After a few days this trains the implicit rule without ever explaining it, and it removes the chief source of player confusion when an inflected form is silently credited to its headword.

**Distinguish the three rejection modes.** Existing Russian implementations collapse them into a single *слово не найдено*, which is the dominant source of player frustration in their comment threads. The three cases:

- The input lemmatizes to a lemma not in the dictionary, or to a lemma that uses letters outside the hive: *такого слова нет в сегодняшнем наборе*.
- The input is a different inflected form of an already-found lemma: *уже найдено: дом*.
- The input doesn't lemmatize at all — typo, non-standard form, unrecognizable morphology: *неверная форма*.

**Pangram celebration.** When a pangram is found, a small visual flourish and *Панграмма!* with the +7 bonus called out. NYT does this and it works because it punctuates the long middle stretch of play.

**End-of-day review.** Once the daily puzzle's window closes, the missed-words list becomes a small review screen showing each missed lemma with a one-line definition. This is the place to add a "сохранить слово" affordance for words a player wants to remember, building a per-player personal vocabulary list over time.

**Yesterday's puzzle and past results.** Standard for daily-puzzle games and expected by players coming from NYT, Wordle, or WordBee.

## Family features

The puzzle is shared across the family. The daily letter set is the same for everyone; everyone plays against the same target. This is the right choice for a competitive household game and the wrong one for a study tool, which makes it the right choice here.

A simple shared scoreboard shows each family member's current day's score, current rank, and whether they've reached Гений. Names rather than logins.

A weekly summary at the end of each week shows who reached Гений how many days, average score per puzzle, and — most importantly — the words each person was the only one in the family to find. The *"сестра нашла слово X, а я нет"* moment is half the fun of a multi-player daily game, and it's also where vocabulary actually transfers between players.

An optional shared *новые слова* list — anyone in the family can flag a word from the daily missed-words review as one they'd like to remember. An end-of-week digest surfaces the small handful of words the household collectively learned that week. This is the quietly real study layer of the game, and it works only because it's a side effect of play rather than the point of play.

## Implementation sketch

The whole thing is a weekend project at this scope. A workable stack:

- **Backend:** Python with pymorphy3 for morphology. A weekly script generates the next seven days of puzzles and writes them to a JSON file or small SQLite database.
- **Frontend:** A static or near-static web app served from any cheap host (or a local server on a Raspberry Pi). Per-puzzle state — words found, current rank, completion — stored in localStorage per device.
- **Shared scoreboard:** a minimal shared backend, one endpoint that accepts a score submission and returns the current day's leaderboard. Auth is just a name; no passwords. A small Cloudflare Worker or equivalent does this in roughly fifty lines.

The morphological analyzer is the only piece that requires real care. pymorphy3 handles inflection cleanly for the well-attested vocabulary that's in the dictionary, but it has known edge cases around recent loanwords, ambiguous lemmatizations (Russian has rampant cross-paradigm homonymy — *стекла* is genitive of *стекло* or past of *стечь*), and marginal forms. At a dictionary of 30–40k lemmas these are infrequent enough that occasional manual exception entries are tractable. The right operational posture is: when a family member complains a word should have been accepted, add it (or its mapping) to a manual override file, and regenerate.

## Open questions

A few decisions are worth making after a few weeks of actual play rather than in advance:

**Whether aspect pairs feel like double-counting.** The rule above treats *писать* and *написать* as separate lemmas, which is lexicographically correct. In practice, a hive that admits both might feel rewarding or might feel cheap; only play will tell. The fallback rule is to merge prefixed perfectives with their imperfective base where the prefix doesn't change the lexical meaning. Don't implement the fallback unless the default proves annoying.

**Whether Гений threshold of 100% is achievable.** This is the NYT convention but Russian puzzles with a denser lemma space may push the time-to-Genius beyond what's fun. After two weeks of data, consider dropping it to 90% with a separate "Queen Bee" badge for actually finding everything, mirroring NYT's later split.

**Whether to show hints during play.** NYT shows a hint grid with words-by-letter and two-letter starters. For fluent speakers the bare puzzle may be more fun and the hint grid more of a learner's affordance. Worth A/B-ing within the family — show one person hints and one not, and see who has more fun.

**Whether to add a "редкое слово" badge.** A small extra reward for finding lemmas below 1 ipm frequency, displayed at end-of-day. Adds texture without changing scoring. Probably worth doing.

**Whether to allow a single "show me one word I missed" reveal per day.** A small grace mechanic that occasionally rescues a stuck puzzle without trivializing the game. NYT doesn't do this; many of its imitators do. Worth trying for a week.
