<script lang="ts">
  interface Props {
    letters: string; // 7 chars; index 0 is the center
    onTap?: (letter: string) => void;
  }

  let { letters, onTap }: Props = $props();

  // Hive displays Ё as Е (lemmas still resolve correctly server-side).
  function display(ch: string): string {
    return ch.replace(/ё/g, "е").replace(/Ё/g, "Е");
  }

  // Flat-top hex: vertices at 0°, 60°, …, 300°. Circumradius R, centered at (cx, cy).
  // (Pointy-top adds Math.PI / 6; we deliberately omit that here.)
  const R = 0.95; // hex circumradius in viewBox units

  function hexPoints(cx: number, cy: number, r: number): string {
    const pts: string[] = [];
    for (let i = 0; i < 6; i++) {
      const a = (Math.PI / 3) * i;
      pts.push(`${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`);
    }
    return pts.join(" ");
  }

  let center = $derived(letters?.[0] ?? "");
  let outer = $derived(letters ? letters.slice(1) : "");

  // Edge-sharing neighbors of a flat-top hex with circumradius R sit at
  // distance R * √3 along the six perpendiculars to its edges (30°, 90°,
  // 150°, 210°, 270°, 330° from +x). A small GAP factor opens visible seams
  // between the cells so they read as a honeycomb, not a single shape.
  const SQ3 = Math.sqrt(3);
  const GAP = 1.06;                  // ~6% gap between adjacent hexes
  const DX = 1.5 * R * GAP;          // horizontal offset for diagonals
  const DY = (SQ3 / 2) * R * GAP;    // vertical offset for diagonals
  const VY = SQ3 * R * GAP;          // straight-up/down offset

  // Order matters: this is what each outer-cell index maps to on screen.
  // 0:N, 1:NE, 2:SE, 3:S, 4:SW, 5:NW
  const POS: Array<{ x: number; y: number }> = [
    { x:  0,    y: -VY },
    { x:  DX,   y: -DY },
    { x:  DX,   y:  DY },
    { x:  0,    y:  VY },
    { x: -DX,   y:  DY },
    { x: -DX,   y: -DY },
  ];

  // ViewBox: outermost hex spans from -DX-R to DX+R horizontally and
  // -VY-(SQ3/2)R to +VY+(SQ3/2)R vertically. Add padding for shadow/glow.
  const PAD = 0.25;
  const HALF_W = DX + R + PAD;
  const HALF_H = VY + (SQ3 / 2) * R + PAD;
  const VIEWBOX = `${-HALF_W} ${-HALF_H} ${2 * HALF_W} ${2 * HALF_H}`;

  // Track the last-pressed letter for visual feedback.
  let pressed = $state<number | null>(null);
  let pressTimer: ReturnType<typeof setTimeout> | undefined;

  function press(idx: number, ch: string) {
    if (!ch) return;
    if (pressTimer) clearTimeout(pressTimer);
    pressed = idx;
    pressTimer = setTimeout(() => (pressed = null), 220);
    onTap?.(ch);
  }
</script>

<div class="hive" aria-label="Поле букв · letter hive">
  <!-- Decorative editorial marks anchored to the hive frame -->
  <span class="frame-mark mark-tl" aria-hidden="true">⬢</span>
  <span class="frame-mark mark-br" aria-hidden="true">7</span>
  <span class="frame-label" aria-hidden="true">центр · обязателен</span>

  <svg viewBox={VIEWBOX} class="board" role="img" preserveAspectRatio="xMidYMid meet">
    <defs>
      <!-- Drop shadow under each cell -->
      <filter id="cellShadow" x="-20%" y="-20%" width="140%" height="140%">
        <feGaussianBlur in="SourceAlpha" stdDeviation="0.04" />
        <feOffset dx="0" dy="0.05" result="o" />
        <feComponentTransfer><feFuncA type="linear" slope="0.35" /></feComponentTransfer>
        <feMerge>
          <feMergeNode />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>

      <!-- Gold gradient for the center cell. Stops use class selectors so
           CSS vars re-shade them per theme. -->
      <linearGradient id="goldFill" x1="0" y1="-1" x2="0" y2="1">
        <stop offset="0%"   class="g-gold-1" />
        <stop offset="55%"  class="g-gold-2" />
        <stop offset="100%" class="g-gold-3" />
      </linearGradient>

      <!-- Cream paper gradient for outer cells -->
      <linearGradient id="paperFill" x1="0" y1="-1" x2="0" y2="1">
        <stop offset="0%"   class="g-paper-1" />
        <stop offset="100%" class="g-paper-2" />
      </linearGradient>

      <!-- Press-state fills -->
      <linearGradient id="goldPress" x1="0" y1="-1" x2="0" y2="1">
        <stop offset="0%"   class="g-gold-press-1" />
        <stop offset="100%" class="g-gold-press-2" />
      </linearGradient>
      <linearGradient id="paperPress" x1="0" y1="-1" x2="0" y2="1">
        <stop offset="0%"   class="g-paper-press-1" />
        <stop offset="100%" class="g-paper-press-2" />
      </linearGradient>
    </defs>

    <!-- Outer ring -->
    {#each outer as ch, i}
      {@const p = POS[i]}
      {@const isPressed = pressed === i + 1}
      <g
        class="cell outer"
        class:pressed={isPressed}
        role="button"
        tabindex="0"
        aria-label={`Буква ${display(ch).toUpperCase()}`}
        onclick={() => press(i + 1, ch)}
        onkeydown={(e) => e.key === "Enter" && press(i + 1, ch)}
      >
        <polygon
          points={hexPoints(p.x, p.y, R)}
          fill={isPressed ? "url(#paperPress)" : "url(#paperFill)"}
          filter="url(#cellShadow)"
        />
        <polygon
          class="cell-inner"
          points={hexPoints(p.x, p.y, R * 0.91)}
        />
        <text
          x={p.x}
          y={p.y + 0.04}
          dominant-baseline="central"
          text-anchor="middle">{display(ch).toUpperCase()}</text>
      </g>
    {/each}

    <!-- Center cell -->
    {#key center}
      <g
        class="cell center"
        class:pressed={pressed === 0}
        role="button"
        tabindex="0"
        aria-label={`Центральная буква ${display(center).toUpperCase()}`}
        onclick={() => press(0, center)}
        onkeydown={(e) => e.key === "Enter" && press(0, center)}
      >
        <polygon
          points={hexPoints(0, 0, R)}
          fill={pressed === 0 ? "url(#goldPress)" : "url(#goldFill)"}
          filter="url(#cellShadow)"
        />
        <polygon
          class="cell-inner center-inner"
          points={hexPoints(0, 0, R * 0.91)}
        />
        <text x="0" y="0.04" dominant-baseline="central" text-anchor="middle"
          >{display(center).toUpperCase()}</text>
      </g>
    {/key}
  </svg>
</div>

<style>
  .hive {
    width: min(440px, 88vw);
    position: relative;
    padding: 1.25rem 0.5rem 1.5rem;
  }

  .board {
    width: 100%;
    height: auto;
    display: block;
    overflow: visible;
  }

  /* ===== Decorative frame marks ===== */
  .frame-mark {
    position: absolute;
    font-family: var(--mono);
    color: var(--ink-faint);
    pointer-events: none;
    user-select: none;
  }
  .mark-tl {
    top: 0;
    left: 0;
    font-size: 0.7rem;
    color: var(--red);
  }
  .mark-br {
    bottom: 0;
    right: 0.2rem;
    font-family: var(--display);
    font-size: 2rem;
    color: var(--paper-edge);
    line-height: 1;
  }
  .frame-label {
    position: absolute;
    top: 0;
    right: 0;
    font-family: var(--mono);
    font-size: 0.62rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--ink-mute);
    user-select: none;
  }

  /* ===== Cells ===== */
  .cell { cursor: pointer; outline: none; }

  .cell polygon {
    transition:
      transform 0.18s var(--ease-spring),
      fill 0.12s ease;
    transform-origin: center;
    transform-box: fill-box;
  }
  .cell-inner {
    fill: none;
    stroke: var(--hex-stroke);
    stroke-width: 0.018;
    pointer-events: none;
  }
  .center-inner {
    stroke: var(--hex-stroke-center);
    stroke-width: 0.022;
  }

  /* Gradient stops bound to theme tokens */
  .g-gold-1 { stop-color: var(--hex-gold-1); }
  .g-gold-2 { stop-color: var(--hex-gold-2); }
  .g-gold-3 { stop-color: var(--hex-gold-3); }
  .g-gold-press-1 { stop-color: var(--hex-gold-press-1); }
  .g-gold-press-2 { stop-color: var(--hex-gold-press-2); }
  .g-paper-1 { stop-color: var(--hex-paper-1); }
  .g-paper-2 { stop-color: var(--hex-paper-2); }
  .g-paper-press-1 { stop-color: var(--hex-paper-press-1); }
  .g-paper-press-2 { stop-color: var(--hex-paper-press-2); }

  .cell text {
    font-family: var(--display);
    font-size: 0.95px;
    fill: var(--ink);
    user-select: none;
    pointer-events: none;
    text-transform: uppercase;
    transition: transform 0.18s var(--ease-spring);
    transform-origin: center;
    transform-box: fill-box;
  }
  .cell.center text {
    fill: var(--ink);
    font-size: 1.1px;
  }

  /* Hover lift */
  @media (hover: hover) {
    .cell.outer:hover polygon:first-of-type {
      transform: translateY(-0.04px) scale(1.02);
    }
    .cell.center:hover polygon:first-of-type {
      transform: translateY(-0.04px) scale(1.03);
    }
  }

  /* Press / activate */
  .cell.pressed polygon:first-of-type {
    transform: scale(0.9);
  }
  .cell.pressed text {
    transform: scale(0.94);
  }

  /* Keyboard focus — visible ring around the hex */
  .cell:focus-visible polygon:first-of-type {
    stroke: var(--red);
    stroke-width: 0.06;
  }

  /* Slow pulse to draw the eye to the obligatory center letter */
  .cell.center polygon:first-of-type {
    animation: centerPulse 4.5s ease-in-out infinite;
  }
  @keyframes centerPulse {
    0%, 100% { filter: brightness(1)    drop-shadow(0 0.02px 0.10px rgba(212, 160, 23, 0.0)); }
    50%      { filter: brightness(1.04) drop-shadow(0 0.02px 0.18px rgba(212, 160, 23, 0.6)); }
  }
</style>
