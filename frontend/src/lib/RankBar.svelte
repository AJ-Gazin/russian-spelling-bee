<script lang="ts">
  import { game } from "./store.svelte";

  let labels = $derived(game.puzzle?.thresholds.labels ?? []);
  let cutoffs = $derived(game.puzzle?.thresholds.cutoffs ?? []);
  let total = $derived(game.puzzle?.total_points ?? 0);

  let currentIdx = $derived.by(() => {
    if (!game.puzzle) return 0;
    let idx = 0;
    for (let i = 0; i < cutoffs.length; i++) {
      if (game.score >= cutoffs[i]) idx = i;
      else break;
    }
    return idx;
  });

  let pct = $derived(total ? Math.min(100, (game.score / total) * 100) : 0);
  let isMax = $derived(currentIdx === labels.length - 1);

  // Next rank info for the right-hand readout.
  let next = $derived.by(() => {
    if (!labels.length) return null;
    if (currentIdx >= labels.length - 1) return null;
    const idx = currentIdx + 1;
    return {
      label: labels[idx],
      cutoff: cutoffs[idx],
      delta: Math.max(0, cutoffs[idx] - game.score),
    };
  });
</script>

<section class="rankbar" aria-label="Прогресс ранга">
  <header class="rb-head">
    <div class="rb-current">
      <span class="rb-eyebrow">Текущий ранг · Current rank</span>
      <span class="rb-rank">{game.rank}</span>
    </div>
    <div class="rb-score">
      <span class="rb-score-num">{game.score}</span>
      <span class="rb-score-of">/&nbsp;{total}</span>
      <span class="rb-score-label">очков · pts</span>
    </div>
  </header>

  <div class="track" role="progressbar"
       aria-valuemin="0" aria-valuemax={total} aria-valuenow={game.score}
       aria-valuetext={`${game.score} of ${total}, rank ${game.rank}`}>
    <div class="track-bg"></div>
    <div class="track-fill" style="width: {pct}%"></div>

    {#each cutoffs as c, i}
      {@const left = total ? (c / total) * 100 : 0}
      {@const reached = i <= currentIdx}
      {@const isCurrent = i === currentIdx}
      <div
        class="node"
        class:reached
        class:current={isCurrent}
        class:future={!reached}
        style="left: {left}%"
        title={`${labels[i]} · ${c} очков`}
      >
        <div class="node-dot"></div>
        <div class="node-cutoff">{c}</div>
      </div>
    {/each}
  </div>

  <footer class="rb-foot">
    {#if isMax}
      <span class="rb-foot-crown">Гений&nbsp;достигнут — you've crowned the puzzle</span>
    {:else if next}
      <span class="rb-foot-line">
        <span class="rb-foot-delta">+{next.delta}</span>
        <span class="rb-foot-caption">до&nbsp;«<em>{next.label}</em>»</span>
      </span>
    {/if}
  </footer>
</section>

<style>
  .rankbar {
    background: var(--paper-warm);
    border: 1px solid var(--ink);
    padding: 1rem 1.25rem 1.5rem;
    position: relative;
    /* Hard newspaper offset shadow */
    box-shadow: 4px 4px 0 var(--shadow-card-ink);
  }
  .rankbar::before {
    content: "";
    position: absolute;
    top: -1px;
    left: 0.6rem;
    right: 0.6rem;
    height: 4px;
    background: var(--red);
  }

  /* Header */
  .rb-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 1rem;
    margin-bottom: 1.25rem;
    flex-wrap: wrap;
  }
  .rb-current { display: flex; flex-direction: column; gap: 0.1rem; }
  .rb-eyebrow {
    font-family: var(--mono);
    font-size: 0.6rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--ink-mute);
  }
  .rb-rank {
    font-family: var(--display);
    font-size: clamp(1.6rem, 4vw, 2.1rem);
    line-height: 1;
    color: var(--ink);
  }

  .rb-score { text-align: right; font-family: var(--mono); }
  .rb-score-num {
    font-family: var(--display);
    font-size: clamp(2.2rem, 5vw, 2.8rem);
    line-height: 1;
    color: var(--red);
    font-variant-numeric: tabular-nums;
  }
  .rb-score-of {
    font-family: var(--mono);
    font-size: 1rem;
    color: var(--ink-mute);
    margin-left: 0.2rem;
    font-variant-numeric: tabular-nums;
  }
  .rb-score-label {
    display: block;
    font-size: 0.6rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--ink-mute);
    margin-top: 0.15rem;
  }

  /* Track */
  .track {
    position: relative;
    height: 4px;
    margin: 1.25rem 0.75rem 2.25rem;
  }
  .track-bg {
    position: absolute;
    inset: 0;
    background: var(--paper-deep);
    border-top: 1px solid var(--ink);
    border-bottom: 1px solid var(--ink);
  }
  .track-fill {
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    background: var(--red);
    transition: width 0.5s var(--ease-out);
  }

  /* Nodes */
  .node {
    position: absolute;
    top: 50%;
    transform: translate(-50%, -50%);
    z-index: 2;
    width: 14px;
    height: 14px;
  }
  .node-dot {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--paper);
    border: 2px solid var(--ink);
    transition: all 0.2s var(--ease-spring);
  }
  .node.reached .node-dot {
    background: var(--ink);
  }
  .node.current .node-dot {
    width: 22px;
    height: 22px;
    margin: -4px;
    background: var(--gold);
    border: 2px solid var(--ink);
    box-shadow: 0 0 0 4px var(--paper-warm), 0 0 0 5px var(--ink);
  }

  /* Cutoffs below the node */
  .node-cutoff {
    position: absolute;
    top: calc(100% + 0.55rem);
    left: 50%;
    transform: translateX(-50%);
    font-family: var(--mono);
    font-size: 0.65rem;
    color: var(--ink-faint);
    font-variant-numeric: tabular-nums;
  }
  .node.current .node-cutoff {
    color: var(--ink);
    font-weight: 700;
  }
  .node.future .node-cutoff { color: var(--ink-faint); }

  /* Foot — one typeface (Spectral italic), baseline-aligned, color hierarchy
     by hue rather than weight/family. The number gets the red accent and a
     touch more size; the prose stays muted. */
  .rb-foot {
    min-height: 1.4rem;
    display: flex;
    justify-content: center;
    align-items: baseline;
    font-family: var(--body);
    color: var(--ink-mute);
  }
  .rb-foot-line {
    display: inline-flex;
    align-items: baseline;
    gap: 0.4rem;
  }
  .rb-foot-delta {
    font-family: var(--body);
    font-style: italic;
    font-weight: 700;
    font-size: 1.15rem;
    color: var(--red);
    font-variant-numeric: tabular-nums;
    line-height: 1;
  }
  .rb-foot-caption {
    font-style: italic;
    font-weight: 400;
    font-size: 0.95rem;
    color: var(--ink-mute);
    line-height: 1;
  }
  .rb-foot-caption em {
    font-style: italic;
    font-weight: 500;
    color: var(--ink);
  }
  .rb-foot-crown {
    font-family: var(--body);
    font-style: italic;
    font-weight: 500;
    font-size: 1rem;
    color: var(--gold-deep);
    line-height: 1;
  }
</style>
