/**
 * Per-puzzle local persistence. Keyed by puzzle id so multiple puzzles can
 * coexist in localStorage and switching back to an old one restores progress.
 *
 * Server-side per-player state is deferred (see todo.md "Future / deferred");
 * this is the interim mechanism.
 */

const KEY = (id: number) => `rsb:found:${id}`;

// The puzzle this browser is currently on. Per-browser so pressing "New Game"
// only rebinds the local view — it does not change what other visitors see.
// New visitors (no value here) fall back to the shared daily puzzle.
const ACTIVE_KEY = "rsb:active";

export function loadActivePuzzleId(): number | null {
  try {
    const raw = localStorage.getItem(ACTIVE_KEY);
    if (!raw) return null;
    const n = Number(raw);
    return Number.isInteger(n) ? n : null;
  } catch {
    return null;
  }
}

export function saveActivePuzzleId(id: number): void {
  try {
    localStorage.setItem(ACTIVE_KEY, String(id));
  } catch {
    /* noop — see saveFound */
  }
}

export function loadFound(puzzleId: number): string[] {
  try {
    const raw = localStorage.getItem(KEY(puzzleId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((x): x is string => typeof x === "string");
  } catch {
    return [];
  }
}

export function saveFound(puzzleId: number, lemmas: string[]): void {
  try {
    localStorage.setItem(KEY(puzzleId), JSON.stringify(lemmas));
  } catch {
    // localStorage may be unavailable (private mode, quota). The current
    // session continues to work; we just don't persist.
  }
}

export function clearFound(puzzleId: number): void {
  try {
    localStorage.removeItem(KEY(puzzleId));
  } catch {
    /* noop */
  }
}
