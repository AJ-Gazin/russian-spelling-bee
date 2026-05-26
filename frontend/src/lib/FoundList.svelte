<script lang="ts">
  import { game } from "./store.svelte";
  import AnswersModal from "./AnswersModal.svelte";

  let showAnswers = $state(false);

  let pangramSet = $derived(
    new Set((game.puzzle?.lemmas ?? []).filter((l) => l.is_pangram).map((l) => l.lemma)),
  );

  // Most-recent first (chronological from store) for the live ticker;
  // alphabetical for the full grid.
  let alphabetical = $derived(
    [...game.found].sort((a, b) => a.localeCompare(b, "ru")),
  );
  let recent = $derived(game.found.slice(-3).reverse());

  // Compute the per-letter index (first letter of each lemma) so we can show
  // alphabet headers — a small but high-value touch for a 50-100 word grid.
  let groups = $derived.by(() => {
    const out: { letter: string; words: string[] }[] = [];
    let cur = "";
    for (const w of alphabetical) {
      const l = (w[0] ?? "").toUpperCase();
      if (l !== cur) {
        cur = l;
        out.push({ letter: l, words: [] });
      }
      out[out.length - 1].words.push(w);
    }
    return out;
  });

  let total = $derived(game.puzzle?.lemmas.length ?? 0);
  let count = $derived(game.found.length);
  let pct = $derived(total ? Math.round((count / total) * 100) : 0);

  // Pangrams found vs available.
  let pangramTotal = $derived(game.puzzle?.pangram_count ?? 0);
  let pangramFound = $derived(
    game.found.filter((l) => pangramSet.has(l)).length,
  );
</script>

<section class="found">
  <header class="fl-head">
    <h2 class="fl-title">Найдено</h2>
    <div class="fl-head-right">
      <div class="fl-stats">
        <span class="fl-count">{count}</span>
        <span class="fl-of">/&nbsp;{total}</span>
        <span class="fl-pct">{pct}%</span>
      </div>
      <button
        class="fl-answers"
        onclick={() => (showAnswers = true)}
        title="Показать все ответы"
        aria-label="Показать ответы"
      >
        <span class="fl-answers-eyebrow">Подсмотр</span>
        <span class="fl-answers-label">Ответы</span>
      </button>
    </div>
  </header>

  {#if pangramTotal > 0}
    <div class="fl-pangram-strip">
      <span class="pg-eyebrow">Панграммы</span>
      <span class="pg-pips" aria-label={`${pangramFound} of ${pangramTotal} pangrams`}>
        {#each Array(pangramTotal) as _, i}
          <span class="pg-pip" class:filled={i < pangramFound}></span>
        {/each}
      </span>
      <span class="pg-readout">{pangramFound}&nbsp;/&nbsp;{pangramTotal}</span>
    </div>
  {/if}

  {#if recent.length > 0}
    <div class="fl-recent" aria-label="Недавние">
      {#each recent as w, i (w + i)}
        <span class="recent-word" class:pangram={pangramSet.has(w)}>
          {w}
        </span>
      {/each}
    </div>
  {/if}

  <div class="fl-body" class:empty={count === 0}>
    {#if count === 0}
      <div class="fl-empty">
        <span class="empty-mark">⬢</span>
        <p>Пока пусто.</p>
        <p class="empty-sub">Любая&nbsp;форма&nbsp;слова — лемма&nbsp;будет&nbsp;найдена.</p>
      </div>
    {:else}
      {#each groups as g (g.letter)}
        <div class="group">
          <div class="group-letter" aria-hidden="true">{g.letter}</div>
          <ul class="group-words">
            {#each g.words as w (w)}
              <li
                class:pangram={pangramSet.has(w)}
                aria-label={pangramSet.has(w) ? `${w} (панграмма)` : undefined}
              >
                {w}
              </li>
            {/each}
          </ul>
        </div>
      {/each}
    {/if}
  </div>
</section>

<AnswersModal open={showAnswers} onClose={() => (showAnswers = false)} />

<style>
  .found {
    background: var(--paper);
    border: 1px solid var(--ink);
    padding: 1rem 1.25rem 1.25rem;
    box-shadow: 4px 4px 0 var(--shadow-card-ink);
    position: relative;
  }
  .found::before {
    content: "";
    position: absolute;
    top: -1px;
    left: 0.6rem;
    right: 0.6rem;
    height: 4px;
    background: var(--ink);
  }

  .fl-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    border-bottom: 1px solid var(--ink);
    padding-bottom: 0.55rem;
    margin-bottom: 0.85rem;
  }
  .fl-title {
    margin: 0;
    font-family: var(--display);
    font-size: 1.6rem;
    line-height: 1;
    color: var(--ink);
    letter-spacing: 0.01em;
  }
  .fl-head-right {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }
  .fl-stats {
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
    font-family: var(--mono);
    font-variant-numeric: tabular-nums;
  }
  .fl-answers {
    background: var(--paper-warm);
    border: 1px solid var(--ink);
    border-radius: 0;
    color: var(--ink);
    font-family: inherit;
    text-align: left;
    padding: 0.35rem 0.6rem;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 0.05rem;
    box-shadow: 2px 2px 0 var(--shadow-card-ink);
    transition:
      transform 0.08s var(--ease-out),
      box-shadow 0.08s var(--ease-out),
      background 0.15s ease;
  }
  .fl-answers:hover { background: var(--paper-deep); }
  .fl-answers:active {
    transform: translate(2px, 2px);
    box-shadow: 0 0 0 var(--shadow-card-ink);
  }
  .fl-answers-eyebrow {
    font-family: var(--mono);
    font-size: 0.5rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--ink-mute);
    line-height: 1;
  }
  .fl-answers-label {
    font-family: var(--display);
    font-size: 0.95rem;
    line-height: 1;
    color: var(--red);
    letter-spacing: 0.01em;
  }
  .fl-count {
    font-family: var(--display);
    font-size: 1.6rem;
    color: var(--red);
    line-height: 1;
  }
  .fl-of {
    font-size: 0.95rem;
    color: var(--ink-mute);
  }
  .fl-pct {
    font-size: 0.65rem;
    letter-spacing: 0.12em;
    color: var(--ink-faint);
    margin-left: 0.35rem;
    padding: 0.15rem 0.35rem;
    background: var(--paper-warm);
    border: 1px solid var(--paper-edge);
  }

  /* Pangram strip */
  .fl-pangram-strip {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 0.85rem;
    padding: 0.45rem 0.6rem;
    background: var(--paper-warm);
    border: 1px dashed var(--paper-edge);
  }
  .pg-eyebrow {
    font-family: var(--mono);
    font-size: 0.62rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--ink-mute);
  }
  .pg-pips { display: inline-flex; gap: 4px; }
  .pg-pip {
    width: 8px;
    height: 8px;
    background: var(--paper-deep);
    border: 1px solid var(--ink-mute);
    transform: rotate(45deg);
    transition: background 0.25s var(--ease-spring);
  }
  .pg-pip.filled { background: var(--gold); }
  .pg-readout {
    margin-left: auto;
    font-family: var(--mono);
    font-size: 0.75rem;
    color: var(--ink);
    font-variant-numeric: tabular-nums;
  }

  /* Recent ticker */
  .fl-recent {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-bottom: 0.95rem;
    min-height: 1.6rem;
  }
  .recent-word {
    display: inline-block;
    font-family: var(--display);
    font-size: 1rem;
    color: var(--ink);
    padding: 0.1rem 0.5rem;
    background: var(--paper-warm);
    border: 1px solid var(--ink);
    animation: recentIn 0.35s var(--ease-spring);
  }
  .recent-word.pangram {
    background: var(--gold);
    color: var(--on-gold);
    box-shadow: 2px 2px 0 var(--shadow-card-ink);
    animation: pangramFlash 0.6s var(--ease-spring);
  }
  @keyframes recentIn {
    from { opacity: 0; transform: translateY(-6px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes pangramFlash {
    0%   { transform: scale(0.9); }
    40%  { transform: scale(1.08); background: var(--gold-soft); }
    100% { transform: scale(1); }
  }

  /* Body — alphabetical groups */
  .fl-body {
    max-height: 26rem;
    overflow-y: auto;
    padding-right: 0.25rem;
    padding-bottom: 0.25rem;
  }
  .fl-body.empty {
    max-height: none;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1.5rem 0;
  }

  .group {
    display: grid;
    grid-template-columns: 2rem 1fr;
    gap: 0.6rem;
    padding: 0.4rem 0;
    border-bottom: 1px dotted var(--paper-edge);
  }
  .group:last-child { border-bottom: none; }
  .group-letter {
    font-family: var(--display);
    font-size: 1.5rem;
    color: var(--red);
    line-height: 1;
    text-align: center;
    border-right: 1px solid var(--paper-edge);
    padding-right: 0.5rem;
  }
  .group-words {
    list-style: none;
    margin: 0;
    padding: 0;
    column-count: 2;
    column-gap: 1rem;
  }
  @media (max-width: 520px) {
    .group-words { column-count: 1; }
  }
  .group-words li {
    padding: 0.12rem 0;
    font-family: var(--body);
    font-size: 1.02rem;
    color: var(--ink);
    break-inside: avoid;
    display: flex;
    align-items: baseline;
    gap: 0.3rem;
  }
  .group-words li.pangram {
    color: var(--plum);
    font-weight: 700;
  }

  /* Empty state */
  .fl-empty {
    text-align: center;
    color: var(--ink-faint);
  }
  .empty-mark {
    display: inline-block;
    font-size: 2.2rem;
    color: var(--paper-edge);
    margin-bottom: 0.5rem;
  }
  .fl-empty p {
    margin: 0.1rem 0;
    font-family: var(--display);
    font-size: 1.1rem;
    color: var(--ink-mute);
  }
  .fl-empty .empty-sub {
    font-family: var(--body);
    font-size: 0.85rem;
    font-style: italic;
  }
</style>
