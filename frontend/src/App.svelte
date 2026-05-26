<script lang="ts">
  import { onMount } from "svelte";
  import { fetchCurrentPuzzle, generateNewPuzzle, type GenerateOptions } from "./lib/api";
  import { game } from "./lib/store.svelte";
  import Hive from "./lib/Hive.svelte";
  import Input from "./lib/Input.svelte";
  import FoundList from "./lib/FoundList.svelte";
  import NewGame from "./lib/NewGame.svelte";
  import RankBar from "./lib/RankBar.svelte";
  import ThemeToggle from "./lib/ThemeToggle.svelte";
  import Toast from "./lib/Toast.svelte";

  let inputRef: ReturnType<typeof Input> | undefined;

  onMount(async () => {
    game.loading = true;
    try {
      const p = await fetchCurrentPuzzle();
      game.setPuzzle(p);
    } catch (e) {
      game.error = String(e);
    } finally {
      game.loading = false;
    }
  });

  async function newPuzzle(opts: GenerateOptions) {
    game.loading = true;
    try {
      const p = await generateNewPuzzle(opts);
      game.setPuzzle(p);
    } catch (e) {
      game.error = String(e);
    } finally {
      game.loading = false;
    }
  }

  function onHiveTap(letter: string) {
    inputRef?.appendLetter(letter);
  }

  function puzzleNumber(id: number | undefined): string {
    if (id == null) return "—";
    return `№ ${String(id).padStart(3, "0")}`;
  }
</script>

<main>
  <header class="masthead">
    <div class="masthead-kicker">
      <span class="kicker-mark">★</span>
      <span class="kicker-text">Ежедневная&nbsp;пчела</span>
      <span class="kicker-dot">·</span>
      <span class="kicker-text">Daily&nbsp;Russian&nbsp;Lemma&nbsp;Puzzle</span>
      <span class="kicker-dot">·</span>
      <span class="kicker-text">Издание&nbsp;{puzzleNumber(game.puzzle?.id)}</span>
      <span class="kicker-spacer"></span>
      <ThemeToggle />
    </div>

    <div class="masthead-rule" aria-hidden="true"></div>

    <div class="masthead-main">
      <div class="masthead-title">
        <h1>
          <span class="title-line title-line-1">Пчела</span>
          <span class="title-line title-line-2">Russian&nbsp;Spelling&nbsp;Bee</span>
        </h1>
        <p class="masthead-tagline">
          Угадай&nbsp;корень — все&nbsp;его&nbsp;формы&nbsp;засчитываются.<br />
          <em>Type any inflection — lemmatized scoring credits the headword.</em>
        </p>
      </div>
      <div class="masthead-actions">
        <NewGame onGenerate={newPuzzle} disabled={game.loading} />
      </div>
    </div>

    <div class="masthead-rule masthead-rule-thin" aria-hidden="true"></div>
  </header>

  {#if game.error}
    <div class="overlay error" role="alert">
      <p class="overlay-eyebrow">Сбой соединения · Connection failed</p>
      <p class="overlay-msg">{game.error}</p>
      <p class="overlay-hint">Backend running at <code>localhost:8000</code>?</p>
    </div>
  {:else if game.loading && !game.puzzle}
    <div class="overlay loading" aria-live="polite">
      <p class="overlay-eyebrow">Подбираем буквы…</p>
      <div class="overlay-marquee">
        <span>А</span><span>Б</span><span>В</span><span>Г</span><span>Д</span>
        <span>Е</span><span>Ж</span><span>З</span>
      </div>
    </div>
  {:else if game.puzzle}
    <section class="stage">
      <div class="stage-left">
        <Hive letters={game.puzzle.letters} onTap={onHiveTap} />
        <Input bind:this={inputRef} />
      </div>
      <aside class="stage-right">
        <RankBar />
        <FoundList />
      </aside>
    </section>

    <footer class="footplate">
      <span class="foot-mark">⬢</span>
      <span class="foot-text">
        Пангр&#x430;мма {game.found.filter(l =>
          game.puzzle?.lemmas.find(x => x.lemma === l)?.is_pangram
        ).length} / {game.puzzle.pangram_count}
      </span>
      <span class="foot-dot">·</span>
      <span class="foot-text">
        Лемм {game.found.length} / {game.puzzle.lemmas.length}
      </span>
      <span class="foot-dot">·</span>
      <span class="foot-text">
        Очки <strong>{game.score}</strong> / {game.puzzle.total_points}
      </span>
    </footer>
  {/if}
</main>

<Toast />

<style>
  main {
    max-width: 1180px;
    margin: 0 auto;
    padding: clamp(1.25rem, 4vw, 3rem) var(--gutter) 4rem;
    position: relative;
  }

  /* ======== Masthead ======== */
  .masthead { margin-bottom: clamp(1.5rem, 3vw, 2.5rem); }

  .masthead-kicker {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.55rem;
    font-family: var(--mono);
    font-size: 0.68rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--ink-mute);
  }
  .kicker-mark {
    color: var(--red);
    font-size: 0.85rem;
    line-height: 1;
  }
  .kicker-dot { opacity: 0.4; }
  .kicker-spacer { flex: 1; min-width: 0.5rem; }

  .masthead-rule {
    height: 4px;
    background: var(--ink);
    margin: 0.55rem 0 0.4rem;
    box-shadow: 0 6px 0 -2px var(--ink); /* double-rule effect */
  }
  .masthead-rule-thin {
    height: 1px;
    background: var(--ink);
    box-shadow: none;
    margin: 0.4rem 0 0;
  }

  .masthead-main {
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: end;
    gap: 1.25rem 2rem;
  }

  .masthead-title h1 {
    margin: 0;
    line-height: 0.9;
    display: flex;
    flex-direction: column;
    gap: 0.05em;
  }
  .title-line { display: block; }
  .title-line-1 {
    font-family: var(--display);
    font-size: clamp(3.2rem, 11vw, 7rem);
    font-weight: 400;
    color: var(--ink);
    letter-spacing: -0.01em;
    text-transform: uppercase;
    line-height: 0.85;
    /* slight ink-press shadow */
    text-shadow: 0 1px 0 rgba(0, 0, 0, 0.05);
  }
  .title-line-2 {
    font-family: var(--body);
    font-style: italic;
    font-weight: 500;
    font-size: clamp(0.95rem, 1.8vw, 1.25rem);
    color: var(--red);
    letter-spacing: 0.02em;
    margin-top: 0.15em;
  }

  .masthead-tagline {
    margin: 0.85rem 0 0;
    font-family: var(--body);
    font-size: 0.95rem;
    line-height: 1.5;
    color: var(--ink-soft);
    max-width: 36ch;
  }
  .masthead-tagline em {
    font-style: italic;
    color: var(--ink-faint);
    font-size: 0.85rem;
  }

  .masthead-actions {
    align-self: end;
    padding-bottom: 0.25rem;
  }

  /* ======== Stage layout ======== */
  .stage {
    display: grid;
    grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
    gap: clamp(2rem, 5vw, 4rem);
    align-items: start;
    margin-top: 0.5rem;
  }

  .stage-left {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1.5rem;
    padding-top: 0.5rem;
  }
  .stage-right {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    min-width: 0;
  }

  @media (max-width: 820px) {
    .stage {
      grid-template-columns: 1fr;
      gap: 2rem;
    }
    .stage-right { order: 2; }
    .masthead-main {
      grid-template-columns: 1fr;
      align-items: start;
    }
    .masthead-actions { align-self: start; }
  }

  /* ======== Overlay states ======== */
  .overlay {
    margin: 3rem auto;
    max-width: 32rem;
    text-align: center;
    padding: 2rem 1.5rem;
    border: 1px solid var(--ink);
    background: var(--paper-warm);
    position: relative;
  }
  .overlay::before {
    content: "";
    position: absolute;
    inset: -8px 4px 4px -8px;
    border: 1px solid var(--ink);
    z-index: -1;
    background: var(--paper-deep);
  }
  .overlay-eyebrow {
    margin: 0 0 0.75rem;
    font-family: var(--mono);
    font-size: 0.72rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--red);
  }
  .overlay-msg {
    margin: 0 0 0.5rem;
    font-family: var(--display);
    font-size: 1.4rem;
    color: var(--ink);
  }
  .overlay-hint {
    margin: 0;
    font-size: 0.9rem;
    color: var(--ink-mute);
  }
  .overlay-hint code {
    font-family: var(--mono);
    background: var(--paper-deep);
    padding: 0.05em 0.4em;
    border-radius: 2px;
  }
  .overlay-marquee {
    display: flex;
    justify-content: center;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }
  .overlay-marquee span {
    font-family: var(--display);
    font-size: 1.6rem;
    color: var(--ink);
    animation: pulse 1.2s var(--ease-out) infinite;
  }
  .overlay-marquee span:nth-child(1) { animation-delay: 0.0s; }
  .overlay-marquee span:nth-child(2) { animation-delay: 0.08s; }
  .overlay-marquee span:nth-child(3) { animation-delay: 0.16s; }
  .overlay-marquee span:nth-child(4) { animation-delay: 0.24s; }
  .overlay-marquee span:nth-child(5) { animation-delay: 0.32s; }
  .overlay-marquee span:nth-child(6) { animation-delay: 0.40s; }
  .overlay-marquee span:nth-child(7) { animation-delay: 0.48s; }
  .overlay-marquee span:nth-child(8) { animation-delay: 0.56s; }

  @keyframes pulse {
    0%, 100% { opacity: 0.25; transform: translateY(0); }
    50%      { opacity: 1;    transform: translateY(-3px); }
  }

  /* ======== Footplate ======== */
  .footplate {
    margin-top: 2.5rem;
    padding-top: 0.85rem;
    border-top: 1px solid var(--ink);
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.6rem;
    font-family: var(--mono);
    font-size: 0.72rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--ink-mute);
  }
  .foot-mark {
    color: var(--gold-deep);
    font-size: 0.85rem;
  }
  .foot-text strong {
    color: var(--ink);
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }
  .foot-dot { opacity: 0.5; }
</style>
