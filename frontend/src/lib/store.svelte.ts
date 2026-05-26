/**
 * Game state as Svelte 5 runes. A single GameState instance owns the puzzle,
 * the found-lemmas list, the current toast, and derived score/rank values.
 * Components import the singleton and read/write via methods.
 *
 * Persistence: every mutation that changes `found` mirrors to localStorage
 * via persist.ts (keyed by puzzle id).
 */

import type { GuessResponse, Puzzle } from "./api";
import { submitGuess } from "./api";
import { loadFound, saveFound } from "./persist";

export type ToastKind = "accepted" | "already_found" | "not_in_set" | "unparseable" | "info";

export interface Toast {
  kind: ToastKind;
  message: string;
  // When kind === "accepted" and the form differs from lemma, show "form → lemma".
  form?: string;
  lemma?: string;
  points?: number;
  isPangram?: boolean;
  // Auto-incremented so Svelte sees a "new" toast even if message is identical.
  seq: number;
}

// Inline rejection feedback rendered next to the input — replaces the
// previous top-of-viewport toast for rejection cases so users can actually
// read the reason without time pressure.
export type FeedbackKind = "already_found" | "not_in_set" | "unparseable";

export interface Feedback {
  kind: FeedbackKind;
  form: string;
  lemma?: string;
  candidates?: string[];
  seq: number;
}

class GameState {
  puzzle = $state<Puzzle | null>(null);
  found = $state<string[]>([]);
  loading = $state<boolean>(false);
  error = $state<string | null>(null);
  toast = $state<Toast | null>(null);
  feedback = $state<Feedback | null>(null);

  // Derived: total points scored.
  score = $derived(this.computeScore());
  // Derived: current rank label.
  rank = $derived(this.computeRank());
  // Derived: points to next rank, or null at Гений.
  toNext = $derived(this.computeToNext());

  #toastSeq = 0;
  #feedbackSeq = 0;

  private computeScore(): number {
    if (!this.puzzle) return 0;
    const set = new Set(this.found);
    let s = 0;
    for (const l of this.puzzle.lemmas) if (set.has(l.lemma)) s += l.points;
    return s;
  }

  private computeRank(): string {
    if (!this.puzzle) return "—";
    const { labels, cutoffs } = this.puzzle.thresholds;
    let label = labels[0];
    const s = this.score;
    for (let i = 0; i < labels.length; i++) {
      if (s >= cutoffs[i]) label = labels[i];
      else break;
    }
    return label;
  }

  private computeToNext(): number | null {
    if (!this.puzzle) return null;
    const { cutoffs } = this.puzzle.thresholds;
    const s = this.score;
    for (const c of cutoffs) if (c > s) return c - s;
    return null;
  }

  setPuzzle(p: Puzzle): void {
    this.puzzle = p;
    this.found = loadFound(p.id);
    this.error = null;
  }

  showToast(t: Omit<Toast, "seq">): void {
    this.toast = { ...t, seq: ++this.#toastSeq };
  }

  showFeedback(f: Omit<Feedback, "seq">): void {
    this.feedback = { ...f, seq: ++this.#feedbackSeq };
  }

  clearFeedback(): void {
    this.feedback = null;
  }

  async guess(form: string): Promise<void> {
    if (!this.puzzle) return;
    const trimmed = form.trim().toLowerCase();
    if (!trimmed) return;
    let res: GuessResponse;
    try {
      res = await submitGuess(this.puzzle.id, trimmed, this.found);
    } catch (e) {
      this.showToast({ kind: "info", message: `Ошибка сети: ${String(e)}` });
      return;
    }
    this.handleGuessResponse(trimmed, res);
  }

  private handleGuessResponse(form: string, res: GuessResponse): void {
    switch (res.status) {
      case "accepted": {
        const lemma = res.lemma!;
        if (!this.found.includes(lemma)) {
          this.found = [...this.found, lemma];
          if (this.puzzle) saveFound(this.puzzle.id, this.found);
        }
        // A successful guess supersedes any lingering rejection feedback.
        this.clearFeedback();
        this.showToast({
          kind: "accepted",
          message: res.is_pangram ? "Панграмма!" : "Зачтено",
          form,
          lemma,
          points: res.points ?? 0,
          isPangram: !!res.is_pangram,
        });
        return;
      }
      case "already_found":
        this.showFeedback({
          kind: "already_found",
          form,
          lemma: res.lemma ?? undefined,
        });
        return;
      case "not_in_set":
        this.showFeedback({
          kind: "not_in_set",
          form,
          candidates: res.candidates,
        });
        return;
      case "unparseable":
        this.showFeedback({
          kind: "unparseable",
          form,
        });
        return;
    }
  }
}

export const game = new GameState();
