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
  | "not_in_set"
  | "unparseable";

export interface GuessResponse {
  status: GuessStatus;
  lemma?: string | null;
  points?: number | null;
  is_pangram?: boolean | null;
  candidates?: string[];
}

const BASE = "/api";

export async function fetchCurrentPuzzle(): Promise<Puzzle> {
  const url = `${BASE}/puzzle/current`;
  const r = await fetch(url);
  if (!r.ok) throw new Error(`GET ${url} → ${r.status}`);
  return (await r.json()) as Puzzle;
}

export interface GenerateOptions {
  top_n?: number | null;
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
