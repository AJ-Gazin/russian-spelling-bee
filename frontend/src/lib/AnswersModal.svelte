<script lang="ts">
  import type { ScoredLemma } from "./api";
  import { game } from "./store.svelte";

  interface Props {
    open: boolean;
    onClose: () => void;
  }

  let { open, onClose }: Props = $props();

  let foundSet = $derived(new Set(game.found));
  let totalCount = $derived(game.puzzle?.lemmas.length ?? 0);
  let foundCount = $derived(game.found.length);
  let remainingCount = $derived(totalCount - foundCount);

  let pangramTotal = $derived(game.puzzle?.pangram_count ?? 0);
  let pangramFound = $derived(
    (game.puzzle?.lemmas ?? []).filter(
      (l) => l.is_pangram && foundSet.has(l.lemma),
    ).length,
  );

  let groups = $derived.by(() => {
    if (!game.puzzle) return [];
    const sorted = [...game.puzzle.lemmas].sort((a, b) =>
      a.lemma.localeCompare(b.lemma, "ru"),
    );
    const out: { letter: string; lemmas: ScoredLemma[] }[] = [];
    let cur = "";
    for (const l of sorted) {
      const ch = (l.lemma[0] ?? "").toUpperCase();
      if (ch !== cur) {
        cur = ch;
        out.push({ letter: ch, lemmas: [] });
      }
      out[out.length - 1].lemmas.push(l);
    }
    return out;
  });

  function onBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) onClose();
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === "Escape") onClose();
  }

  $effect(() => {
    if (!open) return;
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  });
</script>

{#if open && game.puzzle}
  <div
    class="backdrop"
    role="presentation"
    onclick={onBackdropClick}
  >
    <div
      class="dialog"
      role="dialog"
      aria-labelledby="answers-title"
      aria-modal="true"
    >
      <header class="head">
        <div class="head-text">
          <div class="eyebrow">Все&nbsp;слова · Solution&nbsp;set</div>
          <h2 id="answers-title">Ответы</h2>
        </div>
        <button class="close" onclick={onClose} aria-label="Закрыть" title="Закрыть (Esc)">
          ×
        </button>
      </header>

      <div class="stats" aria-label="Сводка">
        <div class="stat stat-found">
          <span class="stat-n">{foundCount}</span>
          <span class="stat-l">Найдено</span>
        </div>
        <div class="stat-divider" aria-hidden="true"></div>
        <div class="stat stat-rem">
          <span class="stat-n">{remainingCount}</span>
          <span class="stat-l">Осталось</span>
        </div>
        <div class="stat-divider" aria-hidden="true"></div>
        <div class="stat stat-total">
          <span class="stat-n">{totalCount}</span>
          <span class="stat-l">Всего</span>
        </div>
        {#if pangramTotal > 0}
          <div class="stat-divider" aria-hidden="true"></div>
          <div class="stat stat-pangram">
            <span class="stat-n">{pangramFound}<span class="stat-of">/{pangramTotal}</span></span>
            <span class="stat-l">Панграммы</span>
          </div>
        {/if}
      </div>

      <div class="body">
        {#each groups as g (g.letter)}
          <section class="group">
            <div class="group-letter" aria-hidden="true">{g.letter}</div>
            <ul class="group-list">
              {#each g.lemmas as l (l.lemma)}
                {@const isFound = foundSet.has(l.lemma)}
                <li
                  class:found={isFound}
                  class:remaining={!isFound}
                  class:pangram={l.is_pangram}
                  aria-label={`${l.lemma}, ${l.points} очков${l.is_pangram ? ", панграмма" : ""}, ${isFound ? "найдено" : "не найдено"}`}
                >
                  <span class="mark" aria-hidden="true">
                    {isFound ? "✓" : "○"}
                  </span>
                  <span class="word">{l.lemma}</span>
                  {#if l.is_pangram}
                    <span class="badge" aria-hidden="true">пангр.</span>
                  {/if}
                  <span class="pts" aria-hidden="true">{l.points}</span>
                </li>
              {/each}
            </ul>
          </section>
        {/each}
      </div>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 60;
    background: rgba(20, 14, 8, 0.55);
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding: clamp(1rem, 4vw, 3rem) 1rem;
    overflow-y: auto;
    animation: backdropIn 0.18s var(--ease-out);
  }
  @keyframes backdropIn {
    from { opacity: 0; }
    to   { opacity: 1; }
  }

  .dialog {
    background: var(--paper);
    border: 1px solid var(--ink);
    box-shadow: 6px 6px 0 var(--shadow-card-ink);
    width: min(46rem, 100%);
    max-height: calc(100vh - 4rem);
    display: flex;
    flex-direction: column;
    position: relative;
    animation: dialogIn 0.26s var(--ease-spring);
  }
  .dialog::before {
    /* Editorial top-rule, same as the .found card */
    content: "";
    position: absolute;
    top: -1px;
    left: 0.6rem;
    right: 0.6rem;
    height: 4px;
    background: var(--ink);
  }
  @keyframes dialogIn {
    from { opacity: 0; transform: translateY(-12px) rotate(-0.3deg); }
    to   { opacity: 1; transform: translateY(0) rotate(0); }
  }

  .head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
    padding: 1rem 1.25rem 0.6rem;
    border-bottom: 1px solid var(--ink);
  }
  .head-text { min-width: 0; }
  .eyebrow {
    font-family: var(--mono);
    font-size: 0.62rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--ink-mute);
    line-height: 1;
  }
  .head h2 {
    margin: 0.35rem 0 0;
    font-family: var(--display);
    font-size: 2rem;
    color: var(--ink);
    line-height: 1;
    letter-spacing: 0.01em;
  }
  .close {
    background: var(--paper-warm);
    border: 1px solid var(--ink);
    color: var(--ink);
    font-family: var(--display);
    font-size: 1.4rem;
    line-height: 1;
    width: 2rem;
    height: 2rem;
    padding: 0;
    cursor: pointer;
    box-shadow: 2px 2px 0 var(--shadow-card-ink);
    transition: transform 0.08s var(--ease-out), box-shadow 0.08s var(--ease-out);
  }
  .close:hover { background: var(--paper-deep); }
  .close:active {
    transform: translate(2px, 2px);
    box-shadow: 0 0 0 var(--shadow-card-ink);
  }

  .stats {
    display: flex;
    align-items: stretch;
    gap: 0.85rem;
    padding: 0.85rem 1.25rem;
    background: var(--paper-warm);
    border-bottom: 1px dashed var(--paper-edge);
    flex-wrap: wrap;
  }
  .stat {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
    min-width: 4.5rem;
  }
  .stat-n {
    font-family: var(--display);
    font-size: 1.6rem;
    line-height: 1;
    color: var(--ink);
    font-variant-numeric: tabular-nums;
  }
  .stat-of {
    font-family: var(--mono);
    font-size: 0.85rem;
    color: var(--ink-mute);
    margin-left: 0.1em;
  }
  .stat-l {
    font-family: var(--mono);
    font-size: 0.6rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--ink-mute);
  }
  .stat-found .stat-n { color: var(--green); }
  .stat-rem .stat-n { color: var(--red); }
  .stat-pangram .stat-n { color: var(--gold-deep); }
  .stat-divider {
    width: 1px;
    background: var(--paper-edge);
    align-self: stretch;
  }

  .body {
    overflow-y: auto;
    padding: 0.5rem 1.25rem 1.25rem;
    flex: 1 1 auto;
  }

  .group {
    display: grid;
    grid-template-columns: 2rem 1fr;
    gap: 0.6rem;
    padding: 0.6rem 0;
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
    padding-top: 0.1rem;
  }
  .group-list {
    list-style: none;
    margin: 0;
    padding: 0;
    column-count: 2;
    column-gap: 1.5rem;
  }
  @media (max-width: 520px) {
    .group-list { column-count: 1; }
  }
  .group-list li {
    display: grid;
    grid-template-columns: 1.1rem 1fr auto auto;
    align-items: baseline;
    column-gap: 0.45rem;
    padding: 0.18rem 0;
    font-family: var(--body);
    font-size: 1rem;
    color: var(--ink);
    break-inside: avoid;
  }
  .group-list li.remaining {
    color: var(--ink-faint);
  }
  .group-list li.remaining .word {
    font-style: italic;
  }
  .group-list li.pangram .word {
    color: var(--plum);
    font-weight: 700;
    font-style: normal;
  }
  .group-list li.remaining.pangram .word {
    color: var(--plum);
    opacity: 0.65;
  }

  .mark {
    font-family: var(--mono);
    font-size: 0.85rem;
    line-height: 1;
    text-align: center;
  }
  .group-list li.found .mark { color: var(--green); }
  .group-list li.remaining .mark { color: var(--ink-faint); }

  .word {
    min-width: 0;
    overflow-wrap: anywhere;
  }

  .badge {
    font-family: var(--mono);
    font-size: 0.55rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--on-gold);
    background: var(--gold);
    border: 1px solid var(--ink);
    padding: 0.02rem 0.32rem;
    line-height: 1.3;
  }
  .group-list li.remaining .badge {
    background: transparent;
    color: var(--gold-deep);
    border-color: var(--paper-edge);
  }

  .pts {
    font-family: var(--mono);
    font-size: 0.78rem;
    color: var(--ink-mute);
    font-variant-numeric: tabular-nums;
    min-width: 1.4rem;
    text-align: right;
  }
  .group-list li.found .pts { color: var(--ink); }
</style>
