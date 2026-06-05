<script lang="ts">
  /**
   * Recently-played puzzles (last 10). The list is GLOBAL — served from the
   * backend's `history` table (a puzzle joins it the first time any visitor
   * correctly guesses a word). The per-row "найдено" count, by contrast, is
   * THIS browser's localStorage progress, so a fresh browser shows 0 for
   * puzzles it hasn't personally played.
   *
   * Structure/styling mirror AnswersModal.svelte (backdrop + dialog + head +
   * Esc/scroll-lock effect). Picking a row hands the id up to the parent, which
   * fetches the full puzzle and switches the active game.
   */
  import { fetchHistory, type HistoryEntry } from "./api";
  import { loadFound } from "./persist";
  import { game } from "./store.svelte";

  interface Props {
    open: boolean;
    onClose: () => void;
    onPick: (id: number) => void;
  }

  let { open, onClose, onPick }: Props = $props();

  let entries = $state<HistoryEntry[]>([]);
  let loading = $state(false);
  let error = $state<string | null>(null);

  function fmtNum(id: number): string {
    return `№ ${String(id).padStart(3, "0")}`;
  }

  function onBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) onClose();
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === "Escape") onClose();
  }

  // Fetch fresh each time the modal opens; lock scroll + wire Esc while open.
  $effect(() => {
    if (!open) return;
    loading = true;
    error = null;
    fetchHistory(10)
      .then((rows) => (entries = rows))
      .catch((e) => (error = String(e)))
      .finally(() => (loading = false));

    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  });
</script>

{#if open}
  <div class="backdrop" role="presentation" onclick={onBackdropClick}>
    <div class="dialog" role="dialog" aria-labelledby="history-title" aria-modal="true">
      <header class="head">
        <div class="head-text">
          <div class="eyebrow">Последние&nbsp;игры · Recent&nbsp;puzzles</div>
          <h2 id="history-title">История</h2>
        </div>
        <button class="close" onclick={onClose} aria-label="Закрыть" title="Закрыть (Esc)">
          ×
        </button>
      </header>

      <div class="body">
        {#if loading}
          <p class="note" aria-live="polite">Загрузка…</p>
        {:else if error}
          <p class="note note-err" role="alert">{error}</p>
        {:else if entries.length === 0}
          <div class="empty">
            <span class="empty-mark">⬢</span>
            <p>Пока нет сыгранных пазлов.</p>
            <p class="empty-sub">Отгадай&nbsp;хотя&nbsp;бы&nbsp;одно&nbsp;слово — пазл&nbsp;появится&nbsp;здесь.</p>
          </div>
        {:else}
          <ul class="list">
            {#each entries as e (e.id)}
              {@const foundCount = loadFound(e.id).length}
              {@const isCurrent = game.puzzle?.id === e.id}
              <li>
                <button
                  class="row"
                  class:current={isCurrent}
                  onclick={() => {
                    onPick(e.id);
                    onClose();
                  }}
                  aria-label={`Пазл ${fmtNum(e.id)}, найдено ${foundCount} слов`}
                >
                  <span class="row-num">{fmtNum(e.id)}</span>
                  <span class="row-letters" aria-hidden="true">
                    {#each e.letters as ch, i (i)}
                      <span class="cell" class:center={i === 0}>{ch.toUpperCase()}</span>
                    {/each}
                  </span>
                  <span class="row-meta">
                    <span class="row-found">{foundCount}&nbsp;найдено</span>
                    <span class="row-pts">{e.total_points}&nbsp;очк.</span>
                  </span>
                  {#if isCurrent}
                    <span class="row-mark" aria-hidden="true">★</span>
                  {/if}
                </button>
              </li>
            {/each}
          </ul>
        {/if}
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
    width: min(38rem, 100%);
    max-height: calc(100vh - 4rem);
    display: flex;
    flex-direction: column;
    position: relative;
    animation: dialogIn 0.26s var(--ease-spring);
  }
  .dialog::before {
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

  .body {
    overflow-y: auto;
    padding: 0.75rem 1.25rem 1.25rem;
    flex: 1 1 auto;
  }

  .note {
    font-family: var(--body);
    color: var(--ink-mute);
    text-align: center;
    padding: 1.5rem 0;
  }
  .note-err { color: var(--red); }

  .empty {
    text-align: center;
    color: var(--ink-faint);
    padding: 1.5rem 0;
  }
  .empty-mark {
    display: inline-block;
    font-size: 2.2rem;
    color: var(--paper-edge);
    margin-bottom: 0.5rem;
  }
  .empty p {
    margin: 0.1rem 0;
    font-family: var(--display);
    font-size: 1.1rem;
    color: var(--ink-mute);
  }
  .empty .empty-sub {
    font-family: var(--body);
    font-size: 0.85rem;
    font-style: italic;
  }

  .list {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .row {
    display: grid;
    grid-template-columns: auto 1fr auto auto;
    align-items: center;
    column-gap: 0.85rem;
    width: 100%;
    background: var(--paper);
    border: none;
    border-bottom: 1px dotted var(--paper-edge);
    padding: 0.7rem 0.4rem;
    cursor: pointer;
    text-align: left;
    transition: background 0.12s ease;
  }
  .row:hover { background: var(--paper-warm); }
  .row.current { background: var(--paper-warm); }
  .list li:last-child .row { border-bottom: none; }

  .row-num {
    font-family: var(--mono);
    font-size: 0.72rem;
    letter-spacing: 0.1em;
    color: var(--ink-mute);
    white-space: nowrap;
  }

  .row-letters {
    display: inline-flex;
    gap: 0.2rem;
    flex-wrap: wrap;
  }
  .cell {
    font-family: var(--display);
    font-size: 0.95rem;
    line-height: 1.4;
    width: 1.4rem;
    text-align: center;
    color: var(--ink);
    background: var(--paper-deep);
    border: 1px solid var(--paper-edge);
  }
  .cell.center {
    color: var(--on-gold);
    background: var(--gold);
    border-color: var(--ink);
    font-weight: 700;
  }

  .row-meta {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.1rem;
    white-space: nowrap;
  }
  .row-found {
    font-family: var(--display);
    font-size: 0.95rem;
    color: var(--red);
    line-height: 1;
  }
  .row-pts {
    font-family: var(--mono);
    font-size: 0.62rem;
    letter-spacing: 0.08em;
    color: var(--ink-faint);
    text-transform: uppercase;
  }

  .row-mark {
    color: var(--gold-deep);
    font-size: 1rem;
  }
</style>
