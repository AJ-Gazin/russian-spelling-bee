<script lang="ts">
  import { game } from "./store.svelte";

  let value = $state("");
  let shaking = $state(false);
  let shakeTimer: ReturnType<typeof setTimeout> | undefined;

  // The set of valid letters (in lowercase, Ё folded to Е) — used to show
  // a live "all letters legal?" hint without spoiling whether the word is in
  // the puzzle. This mirrors the server-side display rule.
  let allowedSet = $derived.by(() => {
    const ls = game.puzzle?.letters ?? "";
    return new Set(
      ls.toLowerCase().split("").map((c) => (c === "ё" ? "е" : c)),
    );
  });

  // Per-character analysis used to render the "preview strip" above the input.
  let chars = $derived.by(() => {
    const v = value.toLowerCase();
    return v.split("").map((c) => {
      const folded = c === "ё" ? "е" : c;
      const isCyr = /[а-яё]/.test(c);
      return {
        ch: c,
        valid: isCyr ? allowedSet.has(folded) : false,
      };
    });
  });

  let hasInvalid = $derived(chars.some((c) => !c.valid));
  let allLegal = $derived(chars.length > 0 && !hasInvalid);

  function onKey(e: KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      submit();
    }
  }

  async function submit() {
    if (!value.trim()) return;
    if (hasInvalid) {
      // Local-only rejection feedback — no server round-trip needed.
      shake();
      return;
    }
    const v = value;
    value = "";
    await game.guess(v);
  }

  function clear() { value = ""; }
  function backspace() { value = value.slice(0, -1); }

  function shake() {
    if (shakeTimer) clearTimeout(shakeTimer);
    shaking = true;
    shakeTimer = setTimeout(() => (shaking = false), 360);
  }

  function shuffle() {
    if (!game.puzzle) return;
    const center = game.puzzle.letters[0];
    const outer = game.puzzle.letters.slice(1).split("");
    for (let i = outer.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [outer[i], outer[j]] = [outer[j], outer[i]];
    }
    game.puzzle = { ...game.puzzle, letters: center + outer.join("") };
  }

  // Tap-from-hive support.
  export function appendLetter(letter: string) {
    value = value + letter;
  }

  // Display: fold Ё→Е like the hive does.
  function disp(ch: string): string {
    return ch.replace(/ё/g, "е").replace(/Ё/g, "Е");
  }
</script>

<div class="input-block" class:shake={shaking}>
  <!-- Preview strip: shows each typed letter with valid/invalid affordance. -->
  <div class="preview" aria-hidden="true">
    {#if chars.length === 0}
      <span class="preview-placeholder">введите слово</span>
    {:else}
      {#each chars as c, i (i + c.ch)}
        <span class="char" class:invalid={!c.valid}>{disp(c.ch).toUpperCase()}</span>
      {/each}
      <span class="caret" aria-hidden="true"></span>
    {/if}
  </div>

  <!-- The real input is visually hidden but still receives focus & IME. -->
  <input
    class="real-input"
    bind:value
    onkeydown={onKey}
    autocomplete="off"
    autocapitalize="off"
    autocorrect="off"
    spellcheck="false"
    aria-label="Введите слово"
    placeholder=""
  />

  <div class="status-row" aria-live="polite">
    {#if chars.length === 0}
      <span class="hint">Нажимай&nbsp;соты&nbsp;или&nbsp;печатай — Ё&nbsp;входит&nbsp;в&nbsp;Е</span>
    {:else if hasInvalid}
      <span class="hint warn">Есть&nbsp;буквы&nbsp;вне&nbsp;набора</span>
    {:else if allLegal}
      <span class="hint ok">{chars.length}&nbsp;{chars.length === 1 ? "буква" : chars.length < 5 ? "буквы" : "букв"}&nbsp;·&nbsp;готов&nbsp;к&nbsp;вводу</span>
    {/if}
  </div>
</div>

<div class="controls" role="toolbar" aria-label="Управление">
  <button class="ctl" onclick={shuffle} title="Перемешать (Tab)" aria-label="Перемешать">
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M16 3h5v5" />
      <path d="M4 20 21 3" />
      <path d="M21 16v5h-5" />
      <path d="M15 15l6 6" />
      <path d="M4 4l5 5" />
    </svg>
    <span class="ctl-label">мешать</span>
  </button>

  <button class="ctl" onclick={backspace} title="Удалить букву (Backspace)" aria-label="Удалить букву">
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 5H9l-7 7 7 7h12a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2z" />
      <path d="m18 9-6 6" />
      <path d="m12 9 6 6" />
    </svg>
  </button>

  <button class="ctl" onclick={clear} title="Очистить (Esc)" aria-label="Очистить">
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  </button>

  <span class="ctl-spacer" aria-hidden="true"></span>

  <button class="submit" onclick={submit} title="Подтвердить (Enter)" disabled={chars.length === 0}>
    <span class="submit-text">Ввод</span>
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
      <path d="M5 12h14" />
      <path d="m13 5 7 7-7 7" />
    </svg>
  </button>
</div>

<style>
  .input-block {
    width: 100%;
    max-width: 420px;
    position: relative;
  }

  /* The actual <input> is fully transparent and overlays the preview strip
     so keystrokes still capture but visual is driven by .preview. */
  .real-input {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    background: transparent;
    border: none;
    color: transparent;
    caret-color: transparent;
    font-family: var(--display);
    font-size: 2rem;
    letter-spacing: 0.08em;
    padding: 0;
    z-index: 2;
  }
  .real-input:focus { outline: none; }

  /* Preview strip — what the user actually sees. */
  .preview {
    min-height: 3.2rem;
    padding: 0.4rem 0.25rem 0.5rem;
    border-bottom: 2px solid var(--ink);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.08em;
    font-family: var(--display);
    font-size: clamp(1.8rem, 4.5vw, 2.4rem);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--ink);
    user-select: none;
    position: relative;
    transition: border-color 0.2s ease;
  }
  .input-block:focus-within .preview {
    border-bottom-color: var(--red);
  }

  .preview-placeholder {
    font-family: var(--body);
    font-style: italic;
    font-size: 1rem;
    color: var(--ink-faint);
    text-transform: none;
    letter-spacing: 0.02em;
  }

  .char {
    display: inline-block;
    line-height: 1;
    transition: color 0.15s ease, transform 0.18s var(--ease-spring);
    animation: charIn 0.22s var(--ease-spring);
  }
  .char.invalid {
    color: var(--red);
    text-decoration: line-through;
    text-decoration-thickness: 2px;
  }
  @keyframes charIn {
    from { opacity: 0; transform: translateY(0.15em); }
    to   { opacity: 1; transform: translateY(0); }
  }

  .caret {
    display: inline-block;
    width: 2px;
    height: 1.5em;
    background: var(--ink);
    margin-left: 0.05em;
    animation: blink 1.05s steps(2, start) infinite;
  }
  .input-block:focus-within .caret { background: var(--red); }
  @keyframes blink { 50% { opacity: 0; } }

  /* Shake on local rejection */
  .input-block.shake .preview {
    animation: shake 0.34s var(--ease-out);
    border-bottom-color: var(--red);
  }
  @keyframes shake {
    0%, 100% { transform: translateX(0); }
    20% { transform: translateX(-6px); }
    40% { transform: translateX(5px); }
    60% { transform: translateX(-3px); }
    80% { transform: translateX(2px); }
  }

  /* Status / hint row */
  .status-row {
    min-height: 1.25rem;
    margin-top: 0.4rem;
    display: flex;
    justify-content: center;
    font-family: var(--mono);
    font-size: 0.7rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--ink-mute);
  }
  .hint.warn { color: var(--red); }
  .hint.ok   { color: var(--green); }

  /* ===== Controls ===== */
  .controls {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 0.85rem auto 0;
    width: 100%;
    max-width: 420px;
  }
  .ctl-spacer { flex: 1; }

  .ctl {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    background: var(--paper-warm);
    border: 1px solid var(--ink);
    color: var(--ink);
    padding: 0.55rem 0.75rem;
    border-radius: 0;
    font-family: var(--mono);
    font-size: 0.7rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    box-shadow: 2px 2px 0 var(--shadow-card-ink);
    transition:
      transform 0.08s var(--ease-out),
      box-shadow 0.08s var(--ease-out),
      background 0.15s ease;
  }
  .ctl:hover:not(:disabled) { background: var(--paper-deep); }
  .ctl:active {
    transform: translate(2px, 2px);
    box-shadow: 0 0 0 var(--shadow-card-ink);
  }
  .ctl-label { display: inline; }
  @media (max-width: 420px) {
    .ctl-label { display: none; }
  }

  .submit {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    background: var(--red);
    color: var(--on-red);
    border: 1px solid var(--ink);
    padding: 0.65rem 1.1rem;
    border-radius: 0;
    font-family: var(--mono);
    font-weight: 700;
    font-size: 0.78rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    box-shadow: 3px 3px 0 var(--shadow-card-ink);
    transition:
      transform 0.08s var(--ease-out),
      box-shadow 0.08s var(--ease-out),
      background 0.15s ease;
  }
  .submit:hover:not(:disabled) { background: var(--red-deep); }
  .submit:active:not(:disabled) {
    transform: translate(3px, 3px);
    box-shadow: 0 0 0 var(--ink);
  }
  .submit:disabled {
    background: var(--paper-edge);
    color: var(--ink-mute);
    box-shadow: 3px 3px 0 var(--ink-mute);
    cursor: not-allowed;
    text-shadow: none;
  }
  .submit-text {
    /* slight optical tweak */
    margin-top: 1px;
  }
</style>
