<script lang="ts">
  import type { GenerateOptions } from "./api";

  interface Props {
    onGenerate: (opts: GenerateOptions) => void;
    disabled?: boolean;
  }

  let { onGenerate, disabled = false }: Props = $props();

  // Preset difficulty bands. `top_n: null` means "use the whole dictionary."
  const PRESETS: Array<{
    key: string;
    label: string;
    top_n: number | null;
    hint: string;
    nominal: string;
  }> = [
    { key: "easy",   label: "Лёгкий",  top_n: 2000,  hint: "top-2,000 most common", nominal: "Easy"   },
    { key: "medium", label: "Средний", top_n: 6000,  hint: "top-6,000",             nominal: "Medium" },
    { key: "hard",   label: "Сложный", top_n: 15000, hint: "top-15,000",            nominal: "Hard"   },
    { key: "expert", label: "Эксперт", top_n: null,  hint: "all ~42k lemmas",       nominal: "Expert" },
  ];

  let selected = $state<string>("expert");
  let open = $state(false);
  let menuRef: HTMLDivElement | undefined;

  function pick(key: string) {
    selected = key;
    const p = PRESETS.find((p) => p.key === key)!;
    onGenerate({ top_n: p.top_n });
    open = false;
  }

  function regenSame() {
    const p = PRESETS.find((p) => p.key === selected)!;
    onGenerate({ top_n: p.top_n });
  }

  function onDocClick(e: MouseEvent) {
    if (!open) return;
    if (menuRef && !menuRef.contains(e.target as Node)) open = false;
  }

  let label = $derived(PRESETS.find((p) => p.key === selected)?.label ?? "Эксперт");
  let nominal = $derived(PRESETS.find((p) => p.key === selected)?.nominal ?? "Expert");
</script>

<svelte:window on:click={onDocClick} />

<div class="new-game" bind:this={menuRef}>
  <button
    class="primary"
    onclick={regenSame}
    {disabled}
    title="Сгенерировать новую игру"
    aria-label="Новая игра"
  >
    <span class="primary-eyebrow">Тираж</span>
    <span class="primary-label">Новая&nbsp;игра</span>
  </button>

  <button
    class="picker"
    onclick={() => (open = !open)}
    {disabled}
    aria-haspopup="listbox"
    aria-expanded={open}
    title="Сложность"
  >
    <span class="picker-eyebrow">Уровень</span>
    <span class="picker-label">
      {label}
      <svg viewBox="0 0 12 12" width="10" height="10" aria-hidden="true">
        <path d="M2 4 L6 8 L10 4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </span>
  </button>

  {#if open}
    <div class="menu" role="listbox" aria-label="Сложность">
      <div class="menu-eyebrow">Выбор&nbsp;уровня · Difficulty</div>
      {#each PRESETS as p (p.key)}
        <button
          class="item"
          class:active={selected === p.key}
          onclick={() => pick(p.key)}
          role="option"
          aria-selected={selected === p.key}
        >
          <span class="item-lbl">{p.label}</span>
          <span class="item-nominal">{p.nominal}</span>
          <span class="item-hint">{p.hint}</span>
          {#if selected === p.key}
            <span class="item-mark" aria-hidden="true">★</span>
          {/if}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .new-game {
    position: relative;
    display: flex;
    gap: 0;
    align-items: stretch;
  }

  button {
    background: var(--paper-warm);
    border: 1px solid var(--ink);
    border-radius: 0;
    color: var(--ink);
    font-family: inherit;
    text-align: left;
    padding: 0.55rem 0.95rem;
    transition:
      transform 0.08s var(--ease-out),
      box-shadow 0.08s var(--ease-out),
      background 0.15s ease;
  }
  button:disabled { opacity: 0.5; cursor: not-allowed; }

  .primary {
    background: var(--ink);
    color: var(--paper);
    box-shadow: 3px 3px 0 var(--shadow-card-red);
    display: flex;
    flex-direction: column;
    gap: 0.05rem;
  }
  .primary:hover:not(:disabled) { background: var(--red-deep); color: var(--on-red); box-shadow: 3px 3px 0 var(--shadow-card-ink); }
  .primary:hover:not(:disabled) .primary-eyebrow { color: var(--gold-soft); }
  .primary:active:not(:disabled) {
    transform: translate(3px, 3px);
    box-shadow: 0 0 0 var(--shadow-card-ink);
  }
  .primary-eyebrow {
    font-family: var(--mono);
    font-size: 0.55rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--on-ink-eyebrow);
  }
  .primary-label {
    font-family: var(--display);
    font-size: 1.1rem;
    line-height: 1;
    letter-spacing: 0.01em;
  }

  .picker {
    border-left: none;
    background: var(--paper-warm);
    color: var(--ink);
    box-shadow: 3px 3px 0 var(--shadow-card-ink);
    display: flex;
    flex-direction: column;
    gap: 0.05rem;
    min-width: 7.5rem;
  }
  .picker:hover:not(:disabled) { background: var(--paper-deep); }
  .picker:active:not(:disabled) {
    transform: translate(3px, 3px);
    box-shadow: 0 0 0 var(--shadow-card-ink);
  }
  .picker-eyebrow {
    font-family: var(--mono);
    font-size: 0.55rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--ink-mute);
  }
  .picker-label {
    font-family: var(--display);
    font-size: 1.1rem;
    line-height: 1;
    letter-spacing: 0.01em;
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
  }

  /* Menu */
  .menu {
    position: absolute;
    top: calc(100% + 0.4rem);
    right: 0;
    min-width: 16rem;
    background: var(--paper);
    border: 1px solid var(--ink);
    box-shadow: 6px 6px 0 var(--shadow-card-ink);
    z-index: 20;
    overflow: hidden;
    animation: menuIn 0.18s var(--ease-spring);
  }
  @keyframes menuIn {
    from { opacity: 0; transform: translateY(-6px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .menu-eyebrow {
    padding: 0.5rem 0.85rem 0.35rem;
    font-family: var(--mono);
    font-size: 0.6rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--ink-mute);
    background: var(--paper-warm);
    border-bottom: 1px solid var(--paper-edge);
  }

  .item {
    display: grid;
    grid-template-columns: auto 1fr auto;
    grid-template-rows: auto auto;
    column-gap: 0.55rem;
    row-gap: 0.05rem;
    width: 100%;
    background: var(--paper);
    border: none;
    border-bottom: 1px dotted var(--paper-edge);
    padding: 0.65rem 0.85rem;
    box-shadow: none;
    cursor: pointer;
  }
  .item:last-child { border-bottom: none; }
  .item:hover { background: var(--paper-warm); }
  .item.active { background: var(--paper-warm); }

  .item-lbl {
    grid-column: 1;
    grid-row: 1;
    font-family: var(--display);
    font-size: 1.1rem;
    color: var(--ink);
    line-height: 1;
  }
  .item-nominal {
    grid-column: 2;
    grid-row: 1;
    align-self: end;
    font-family: var(--mono);
    font-size: 0.65rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--ink-faint);
  }
  .item-hint {
    grid-column: 1 / span 2;
    grid-row: 2;
    font-family: var(--body);
    font-size: 0.82rem;
    color: var(--ink-mute);
    font-style: italic;
  }
  .item-mark {
    grid-column: 3;
    grid-row: 1 / span 2;
    align-self: center;
    color: var(--red);
    font-size: 1.1rem;
  }
</style>
