/**
 * Thin client for the backend. All routes live under /api/*.
 *
 * In dev: Vite proxies /api/* to http://localhost:8000 (path preserved).
 * In prod (HF Space): the SPA and the API share the same origin, so /api/*
 * resolves to the FastAPI router directly.
 *
 * Shapes mirror backend/src/rsb/api.py — keep them in sync. When the backend
 * shape changes, update both this file and STATUS.md.
 */

export interface ScoredLemma {
  lemma: string;
  pos: string;
  freq_ipm: number;
  length: number;
  points: number;
  is_pangram: boolean;
  // Inflected forms constructible from this hive (the exact spellings a player
  // can type). The citation form may not itself fit, so this is the learning
  // payload shown in the answer key. Ordered shortest-first.
  forms: string[];
}

export interface Thresholds {
  total_points: number;
  cutoffs: number[];
  labels: string[];
}

export interface Puzzle {
  id: number;
  letters: string; // 7 chars; index 0 is the center
  center: string;
  total_points: number;
  pangram_count: number;
  lemmas: ScoredLemma[];
  thresholds: Thresholds;
}

export type GuessStatus =
  | "accepted"
  | "already_found"
  | "outside_hive" // form uses a letter not in the hive (server-side authority)
  | "missing_center" // form lacks the center letter
  | "not_in_set"
  | "unparseable";

export interface GuessResponse {
  status: GuessStatus;
  lemma?: string | null;
  points?: number | null;
  is_pangram?: boolean | null;
  candidates?: string[];
  // POS of the accepted lemma (NOUN/VERB/…) — used to label homonyms.
  pos?: string | null;
  // When true, the same typed string still reaches another unfound homonym;
  // the UI invites the player to enter it again to cycle to it.
  homonym_remaining?: boolean;
}

// Short Russian POS abbreviations for display (homonym disambiguation).
const POS_LABELS: Record<string, string> = {
  NOUN: "сущ.",
  VERB: "гл.",
  ADJF: "прил.",
  ADVB: "нареч.",
  NUMR: "числ.",
  PRED: "предик.",
  COMP: "сравн.",
};

export function posLabel(pos: string | null | undefined): string {
  if (!pos) return "";
  return POS_LABELS[pos] ?? pos.toLowerCase();
}

const BASE = "/api";

export async function fetchCurrentPuzzle(): Promise<Puzzle> {
  const url = `${BASE}/puzzle/current`;
  const r = await fetch(url);
  if (!r.ok) throw new Error(`GET ${url} → ${r.status}`);
  return (await r.json()) as Puzzle;
}

// The pinned daily/featured puzzle — what a brand-new visitor opens on. Stable
// across other players generating puzzles (see backend /api/puzzle/daily).
export async function fetchDailyPuzzle(): Promise<Puzzle> {
  const url = `${BASE}/puzzle/daily`;
  const r = await fetch(url);
  if (!r.ok) throw new Error(`GET ${url} → ${r.status}`);
  return (await r.json()) as Puzzle;
}

export async function fetchPuzzleById(id: number): Promise<Puzzle> {
  const url = `${BASE}/puzzle/${id}`;
  const r = await fetch(url);
  if (!r.ok) throw new Error(`GET ${url} → ${r.status}`);
  return (await r.json()) as Puzzle;
}

// One row of the recently-played history. Lightweight summary; the full puzzle
// (with lemmas) is fetched via fetchPuzzleById when the player reopens it.
export interface HistoryEntry {
  id: number;
  letters: string;
  center: string;
  total_points: number;
  started_at: string;
}

export async function fetchHistory(limit = 10): Promise<HistoryEntry[]> {
  const url = `${BASE}/history?limit=${limit}`;
  const r = await fetch(url);
  if (!r.ok) throw new Error(`GET ${url} → ${r.status}`);
  return (await r.json()) as HistoryEntry[];
}

export interface GenerateOptions {
  min_lemmas?: number | null;
  max_lemmas?: number | null;
  require_pangram?: boolean | null;
  seed?: number | null;
}

export async function generateNewPuzzle(opts: GenerateOptions = {}): Promise<Puzzle> {
  const body = Object.fromEntries(
    Object.entries(opts).filter(([, v]) => v !== undefined && v !== null),
  );
  const url = `${BASE}/admin/generate`;
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`POST ${url} → ${r.status}`);
  return (await r.json()) as Puzzle;
}

export async function submitGuess(
  puzzleId: number,
  form: string,
  foundLemmas: string[],
): Promise<GuessResponse> {
  const url = `${BASE}/puzzle/${puzzleId}/guess`;
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ form, found_lemmas: foundLemmas }),
  });
  if (!r.ok) throw new Error(`POST ${url} → ${r.status}`);
  return (await r.json()) as GuessResponse;
}
