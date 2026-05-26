<script lang="ts">
  import { onMount } from "svelte";

  type Theme = "light" | "dark";
  const KEY = "rsb:theme";

  let theme = $state<Theme>("light");

  function systemPref(): Theme {
    if (typeof window === "undefined") return "light";
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function apply(t: Theme) {
    document.documentElement.setAttribute("data-theme", t);
    document.documentElement.style.colorScheme = t;
  }

  onMount(() => {
    let initial: Theme;
    try {
      const stored = localStorage.getItem(KEY) as Theme | null;
      initial = stored === "dark" || stored === "light" ? stored : systemPref();
    } catch {
      initial = systemPref();
    }
    theme = initial;
    apply(initial);
  });

  function toggle() {
    theme = theme === "dark" ? "light" : "dark";
    apply(theme);
    try {
      localStorage.setItem(KEY, theme);
    } catch {
      // localStorage unavailable — preference holds for this session only.
    }
  }
</script>

<button
  class="toggle"
  class:is-dark={theme === "dark"}
  onclick={toggle}
  title={theme === "dark" ? "Светлая тема · Light" : "Тёмная тема · Dark"}
  aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
  aria-pressed={theme === "dark"}
>
  <span class="track" aria-hidden="true">
    <!-- sun (left) -->
    <svg class="ic ic-sun" viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="4"/>
      <path d="M12 2v2"/><path d="M12 20v2"/>
      <path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/>
      <path d="M2 12h2"/><path d="M20 12h2"/>
      <path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>
    </svg>
    <!-- knob -->
    <span class="knob"></span>
    <!-- moon (right) -->
    <svg class="ic ic-moon" viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
    </svg>
  </span>
  <span class="label">{theme === "dark" ? "ночь" : "день"}</span>
</button>

<style>
  .toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: transparent;
    border: 1px solid var(--paper-edge);
    padding: 0.15rem 0.45rem 0.15rem 0.2rem;
    color: var(--ink-mute);
    font-family: var(--mono);
    font-size: 0.6rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    transition: border-color 0.15s ease, color 0.15s ease, background 0.15s ease;
  }
  .toggle:hover {
    border-color: var(--ink);
    color: var(--ink);
    background: var(--paper-warm);
  }

  .track {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: space-between;
    width: 38px;
    height: 18px;
    padding: 0 4px;
    background: var(--paper-deep);
    border: 1px solid var(--ink);
    /* Inset shadow gives the channel a printed depth */
    box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.25);
  }
  .ic {
    color: var(--ink-faint);
    transition: color 0.2s ease;
    pointer-events: none;
  }
  .toggle:not(.is-dark) .ic-sun { color: var(--red); }
  .toggle.is-dark .ic-moon { color: var(--gold); }

  .knob {
    position: absolute;
    top: 1px;
    left: 1px;
    width: 14px;
    height: 14px;
    background: var(--ink);
    border-radius: 0;
    transition: transform 0.28s var(--ease-spring), background 0.2s ease;
  }
  .toggle.is-dark .knob {
    transform: translateX(20px);
    background: var(--gold);
  }

  .label {
    min-width: 2.3em;
    text-align: left;
  }
</style>
