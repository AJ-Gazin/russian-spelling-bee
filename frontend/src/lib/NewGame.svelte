<script lang="ts">
  import type { GenerateOptions } from "./api";

  interface Props {
    onGenerate: (opts: GenerateOptions) => void;
    disabled?: boolean;
  }

  let { onGenerate, disabled = false }: Props = $props();
</script>

<button
  class="new-game"
  onclick={() => onGenerate({})}
  {disabled}
  title="Сгенерировать новую игру"
  aria-label="Новая игра"
>
  <span class="eyebrow">Тираж</span>
  <span class="label">Новая&nbsp;игра</span>
</button>

<style>
  .new-game {
    background: var(--ink);
    color: var(--paper);
    border: 1px solid var(--ink);
    border-radius: 0;
    font-family: inherit;
    text-align: left;
    padding: 0.55rem 0.95rem;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 0.05rem;
    box-shadow: 3px 3px 0 var(--shadow-card-red);
    transition:
      transform 0.08s var(--ease-out),
      box-shadow 0.08s var(--ease-out),
      background 0.15s ease;
  }
  .new-game:hover:not(:disabled) {
    background: var(--red-deep);
    color: var(--on-red);
    box-shadow: 3px 3px 0 var(--shadow-card-ink);
  }
  .new-game:hover:not(:disabled) .eyebrow { color: var(--gold-soft); }
  .new-game:active:not(:disabled) {
    transform: translate(3px, 3px);
    box-shadow: 0 0 0 var(--shadow-card-ink);
  }
  .new-game:disabled { opacity: 0.5; cursor: not-allowed; }

  .eyebrow {
    font-family: var(--mono);
    font-size: 0.55rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--on-ink-eyebrow);
  }
  .label {
    font-family: var(--display);
    font-size: 1.1rem;
    line-height: 1;
    letter-spacing: 0.01em;
  }
</style>
