<script lang="ts">
  import { game } from "./store.svelte";

  let visible = $state(false);
  let lastSeq = $state(-1);
  let timer: ReturnType<typeof setTimeout> | undefined;

  $effect(() => {
    const t = game.toast;
    if (!t) return;
    if (t.seq === lastSeq) return;
    lastSeq = t.seq;
    visible = true;
    if (timer) clearTimeout(timer);
    const dur = t.kind === "accepted" && t.isPangram ? 2800 : 1700;
    timer = setTimeout(() => (visible = false), dur);
  });

  // Russian-aware "буква/буквы/букв" — used by points line.
  function plural(n: number, one: string, few: string, many: string): string {
    const mod10 = n % 10;
    const mod100 = n % 100;
    if (mod10 === 1 && mod100 !== 11) return one;
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few;
    return many;
  }
</script>

{#if visible && game.toast}
  {@const t = game.toast}
  <div class="toast-wrap">
    <div
      class="toast kind-{t.kind}"
      class:pangram={t.kind === "accepted" && t.isPangram}
      role="status"
      aria-live="polite"
    >
      <!-- Left rail: status mark + small kicker. -->
      <div class="rail">
        <span class="mark" aria-hidden="true">
          {#if t.kind === "accepted" && t.isPangram}★
          {:else if t.kind === "accepted"}✓
          {:else if t.kind === "already_found"}↺
          {:else if t.kind === "not_in_set"}✗
          {:else if t.kind === "unparseable"}?
          {:else}!{/if}
        </span>
        <span class="kicker">
          {#if t.kind === "accepted" && t.isPangram}Панграмма
          {:else if t.kind === "accepted"}Зачтено
          {:else if t.kind === "already_found"}Уже найдено
          {:else if t.kind === "not_in_set"}Не в наборе
          {:else if t.kind === "unparseable"}Нет формы
          {:else}Сообщение{/if}
        </span>
      </div>

      <!-- Body -->
      <div class="body">
        {#if t.kind === "accepted"}
          <div class="resolution">
            {#if t.form && t.lemma && t.form !== t.lemma}
              <span class="form">{t.form}</span>
              <span class="arrow" aria-hidden="true">→</span>
              <span class="lemma">{t.lemma}</span>
            {:else if t.lemma}
              <span class="lemma sole">{t.lemma}</span>
            {/if}
          </div>
          <div class="meta">
            <span class="points">
              +<strong>{t.points ?? 0}</strong>
              {plural(t.points ?? 0, "очко", "очка", "очков")}
            </span>
            {#if t.isPangram}
              <span class="badge">+7 panграмма</span>
            {/if}
          </div>
        {:else if t.kind === "already_found"}
          <div class="resolution">
            <span class="lemma sole">{t.lemma ?? t.message}</span>
          </div>
          <div class="meta meta-soft">в списке найденных</div>
        {:else if t.kind === "not_in_set"}
          <div class="msg">Слова&nbsp;нет&nbsp;в&nbsp;сегодняшнем&nbsp;наборе</div>
          <div class="meta meta-soft">не из этих 7 букв · or 4+ letter rule</div>
        {:else if t.kind === "unparseable"}
          <div class="msg">Не&nbsp;удалось&nbsp;распознать&nbsp;форму</div>
          <div class="meta meta-soft">морфология не вернула разбор</div>
        {:else}
          <div class="msg">{t.message}</div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .toast-wrap {
    position: fixed;
    top: clamp(1rem, 3vw, 2rem);
    left: 0;
    right: 0;
    display: flex;
    justify-content: center;
    pointer-events: none;
    z-index: 50;
  }

  .toast {
    pointer-events: auto;
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 1rem;
    min-width: 18rem;
    max-width: min(36rem, 92vw);
    padding: 0.85rem 1.1rem;
    background: var(--paper-toast);
    border: 1px solid var(--ink);
    box-shadow:
      5px 5px 0 var(--shadow-card-ink),
      0 12px 32px -8px rgba(0, 0, 0, 0.35);
    animation: toastIn 0.28s var(--ease-spring);
    position: relative;
  }
  @keyframes toastIn {
    from { opacity: 0; transform: translateY(-12px) rotate(-0.6deg); }
    to   { opacity: 1; transform: translateY(0) rotate(0); }
  }
  .toast::before {
    /* Color rail along the left edge */
    content: "";
    position: absolute;
    top: 0; bottom: 0; left: 0;
    width: 5px;
  }
  .toast.kind-accepted::before        { background: var(--green); }
  .toast.kind-already_found::before   { background: var(--ink-mute); }
  .toast.kind-not_in_set::before      { background: var(--red); }
  .toast.kind-unparseable::before     { background: var(--plum); }
  .toast.kind-info::before            { background: var(--ink); }
  .toast.pangram::before              { background: var(--gold); }

  .rail {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.2rem;
    padding-left: 0.4rem;
    border-right: 1px dotted var(--paper-edge);
    padding-right: 0.85rem;
    min-width: 4.5rem;
  }
  .mark {
    font-family: var(--display);
    font-size: 1.6rem;
    line-height: 1;
    color: var(--ink);
  }
  .toast.kind-accepted .mark { color: var(--green); }
  .toast.kind-not_in_set .mark { color: var(--red); }
  .toast.kind-already_found .mark { color: var(--ink-mute); }
  .toast.kind-unparseable .mark { color: var(--plum); }
  .toast.pangram .mark { color: var(--gold-deep); font-size: 1.9rem; }

  .kicker {
    font-family: var(--mono);
    font-size: 0.6rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--ink-mute);
    text-align: center;
    line-height: 1.1;
  }

  .body {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    min-width: 0;
  }

  .resolution {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 0.45rem;
    font-family: var(--display);
    font-size: 1.25rem;
    color: var(--ink);
    line-height: 1.1;
  }
  .form {
    font-family: var(--body);
    font-style: italic;
    font-size: 1.05rem;
    color: var(--ink-mute);
    text-decoration: line-through;
    text-decoration-color: var(--paper-edge);
  }
  .arrow {
    color: var(--ink-faint);
    font-family: var(--mono);
    font-size: 1rem;
  }
  .lemma {
    color: var(--red);
    font-weight: 400;
  }
  .lemma.sole { color: var(--ink); }
  .toast.pangram .lemma { color: var(--gold-deep); }

  .meta {
    font-family: var(--mono);
    font-size: 0.78rem;
    color: var(--ink);
    display: flex;
    gap: 0.6rem;
    align-items: baseline;
    flex-wrap: wrap;
  }
  .meta-soft {
    color: var(--ink-mute);
    font-size: 0.72rem;
    font-style: italic;
    font-family: var(--body);
  }
  .points strong {
    font-family: var(--display);
    font-size: 1.05rem;
    color: var(--red);
    margin: 0 0.05em;
  }
  .toast.pangram .points strong { color: var(--gold-deep); }

  .badge {
    background: var(--gold);
    color: var(--on-gold);
    padding: 0.05rem 0.45rem;
    font-family: var(--mono);
    font-size: 0.65rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    border: 1px solid var(--ink);
  }

  .msg {
    font-family: var(--display);
    font-size: 1.15rem;
    color: var(--ink);
    line-height: 1.2;
  }

  /* Pangram extras — gold sweep at the top fades into paper */
  .toast.pangram {
    background: linear-gradient(
      180deg,
      var(--gold-soft) 0%,
      var(--paper-toast) 45%
    );
    animation:
      toastIn 0.32s var(--ease-spring),
      pangramShake 0.6s 0.2s ease-in-out;
  }
  @keyframes pangramShake {
    0%, 100% { transform: rotate(0); }
    30%      { transform: rotate(-0.6deg); }
    60%      { transform: rotate(0.5deg); }
  }
</style>
