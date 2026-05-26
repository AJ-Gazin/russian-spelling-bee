"""Generate a sample of puzzles across all difficulty presets and write a
reproducible benchmark report.

Why: as we iterate on word-selection strategies (citation-form vs form-fitness,
per-POS folding rules, etc.) we need objective, side-by-side numbers — not just
gut checks. This script is the canonical way to produce those numbers.

Inputs:
  - Real dictionary at $RSB_DB (default backend/data/rsb.db). Stub TSV is fine
    for sanity but produces too few samples to compare.
  - The four production difficulty presets, applied with the *same* per-top_n
    softening the API does in api.py (min_lemmas, pangram_freq_floor).

Outputs (under <output-root>/<date>-<label>/):
  - report.md  : human-readable summary table + length histogram per preset.
  - raw.json   : per-puzzle records (seed, hive, lemmas, scores) so future
                 runs can compute deltas without re-sampling.

Reproducibility:
  - Seeds are deterministic: 0..N-1 per preset.
  - The dictionary identity (size, sha-like hash of sorted lemmas) is captured
    in the JSON so we know whether a delta is from a strategy change or a
    dictionary refresh.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

# Windows consoles default to cp1252 — reconfigure for Cyrillic progress prints.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from collections import Counter
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path
from statistics import mean, median, stdev

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rsb.dictionary import Dictionary  # noqa: E402
from rsb.generator import GeneratorConfig, NoPuzzleFound, generate  # noqa: E402
from rsb.store import open_db  # noqa: E402

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
DEFAULT_DB = BACKEND_ROOT / "data" / "rsb.db"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "docs" / "benchmarks" / "runs"

# Production base config — mirrors api.py:_DEFAULT_REAL_CFG.
BASE_CFG = GeneratorConfig(
    min_lemmas=25,
    max_lemmas=70,
    require_pangram=True,
    pangram_freq_floor=2.0,
    dominance_cap=0.25,
    max_attempts=4000,
)

# Production presets — keep in sync with frontend/src/lib/NewGame.svelte.
PRESETS: list[tuple[str, int | None]] = [
    ("Лёгкий",  2000),
    ("Средний", 6000),
    ("Сложный", 15000),
    ("Эксперт", None),
]


def cfg_for(top_n: int | None, seed: int) -> GeneratorConfig:
    """Replicate the per-preset softening the API applies in admin_generate."""
    overrides: dict = {"seed": seed}
    if top_n is not None:
        overrides["top_n"] = top_n
        if top_n <= 5000:
            overrides["min_lemmas"] = max(8, min(25, top_n // 200))
            overrides["pangram_freq_floor"] = 0.0
    return replace(BASE_CFG, **overrides)


def dictionary_fingerprint(d: Dictionary) -> str:
    """Stable short hash of the dictionary's lemma set — for change detection."""
    h = hashlib.sha1()
    for l in sorted(l.lemma for l in d):
        h.update(l.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()[:12]


def histogram(values: list[int], buckets: list[tuple[int, int | None]]) -> dict[str, int]:
    """Count `values` falling into each (lo, hi) bucket (inclusive lo, exclusive hi).
    hi=None means open-ended upper bound."""
    out: dict[str, int] = {}
    for lo, hi in buckets:
        label = f"{lo}" if hi == lo + 1 else (f"{lo}+" if hi is None else f"{lo}-{hi-1}")
        out[label] = sum(1 for v in values if v >= lo and (hi is None or v < hi))
    return out


LEN_BUCKETS = [(4, 5), (5, 6), (6, 7), (7, 8), (8, 9), (9, 11), (11, None)]


def sample_preset(
    d: Dictionary,
    label: str,
    top_n: int | None,
    n: int,
) -> dict:
    """Generate `n` puzzles for one preset; return stats + per-puzzle records."""
    word_lengths: list[int] = []
    counts: list[int] = []
    pangram_lens: list[int] = []
    puzzles: list[dict] = []
    n_ok = 0
    t0 = time.time()
    for seed in range(n):
        try:
            p = generate(d, cfg_for(top_n, seed))
        except NoPuzzleFound:
            puzzles.append({"seed": seed, "ok": False})
            continue
        n_ok += 1
        lemmas = [
            {"lemma": s.lemma, "len": len(s.lemma), "points": s.points, "pangram": s.is_pangram}
            for s in p.lemmas
        ]
        puzzles.append({
            "seed": seed,
            "ok": True,
            "letters": p.letters,
            "center": p.center,
            "total_points": p.total_points,
            "pangram_count": p.pangram_count,
            "lemma_count": len(p.lemmas),
            "lemmas": lemmas,
        })
        counts.append(len(p.lemmas))
        for s in p.lemmas:
            word_lengths.append(len(s.lemma))
            if s.is_pangram:
                pangram_lens.append(len(s.lemma))
    dt = time.time() - t0
    return {
        "label": label,
        "top_n": top_n,
        "n_requested": n,
        "n_ok": n_ok,
        "elapsed_s": round(dt, 1),
        "stats": _stats_block(word_lengths, counts, pangram_lens),
        "length_histogram": histogram(word_lengths, LEN_BUCKETS),
        "puzzles": puzzles,
    }


def _stats_block(word_lengths, counts, pangram_lens) -> dict:
    def f(xs):
        if not xs:
            return None
        return {
            "n": len(xs),
            "mean": round(mean(xs), 2),
            "median": float(median(xs)),
            "stdev": round(stdev(xs), 2) if len(xs) > 1 else 0.0,
            "min": min(xs),
            "max": max(xs),
        }
    return {
        "word_length": f(word_lengths),
        "lemmas_per_puzzle": f(counts),
        "pangram_length": f(pangram_lens),
        "pangrams_per_puzzle": round(len(pangram_lens) / max(1, len(counts)), 2) if counts else None,
    }


def render_report(run_meta: dict, presets: list[dict]) -> str:
    """Produce the human-readable markdown report."""
    lines: list[str] = []
    lines.append(f"# Benchmark run — {run_meta['label']}")
    lines.append("")
    lines.append(f"- **Date:** {run_meta['date']}")
    lines.append(f"- **Strategy:** {run_meta['strategy']}")
    lines.append(f"- **Samples per preset:** {run_meta['n_per_preset']}")
    lines.append(f"- **Dictionary:** {run_meta['dictionary_size']:,} lemmas (fingerprint `{run_meta['dictionary_fingerprint']}`)")
    lines.append(f"- **Base config:** `{run_meta['base_cfg']}`")
    if run_meta.get("notes"):
        lines.append("")
        lines.append(f"**Notes:** {run_meta['notes']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Preset | top_n | n ok | Avg word len | Median | Stdev | Range | Avg lemmas/puzzle | Pangrams/puzzle |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in presets:
        s = r["stats"]
        wl = s["word_length"]
        lc = s["lemmas_per_puzzle"]
        lines.append(
            f"| {r['label']} | {r['top_n']} | {r['n_ok']}/{r['n_requested']} | "
            f"{wl['mean']:.2f} | {wl['median']} | {wl['stdev']:.2f} | {wl['min']}–{wl['max']} | "
            f"{lc['mean']:.1f} (median {lc['median']}, range {lc['min']}–{lc['max']}) | "
            f"{s['pangrams_per_puzzle']} |"
        )
    lines.append("")
    lines.append("## Word-length distribution (% of all sampled lemmas per preset)")
    lines.append("")
    bucket_labels = list(presets[0]["length_histogram"].keys())
    header = "| Preset | " + " | ".join(bucket_labels) + " |"
    sep = "|" + "---|" * (len(bucket_labels) + 1)
    lines.append(header)
    lines.append(sep)
    for r in presets:
        h = r["length_histogram"]
        total = sum(h.values()) or 1
        row = f"| {r['label']} | " + " | ".join(f"{100*h[b]/total:.1f}%" for b in bucket_labels) + " |"
        lines.append(row)
    lines.append("")
    lines.append("Raw per-puzzle data lives in `raw.json` next to this file.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", required=True, help="Short slug identifying the strategy under test (e.g. 'form-fitness-v1').")
    ap.add_argument("--strategy", default="", help="One-line prose description of what's being measured.")
    ap.add_argument("--n", type=int, default=50, help="Puzzles per preset (default 50).")
    ap.add_argument("--db", type=Path, default=Path(os.environ.get("RSB_DB", DEFAULT_DB)))
    ap.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    ap.add_argument("--notes", default="", help="Free-text notes appended to the report header.")
    args = ap.parse_args()

    print(f"Opening dictionary at {args.db} ...", flush=True)
    conn = open_db(args.db)
    d = Dictionary.from_db(conn)
    fp = dictionary_fingerprint(d)
    print(f"Loaded {len(d):,} lemmas (fingerprint {fp})", flush=True)

    today = date.today().isoformat()
    out_dir = args.output_root / f"{today}-{args.label}"
    out_dir.mkdir(parents=True, exist_ok=True)

    preset_results = []
    for label, top_n in PRESETS:
        print(f"\n[{label}] top_n={top_n} ...", flush=True)
        r = sample_preset(d, label, top_n, args.n)
        s = r["stats"]
        print(
            f"  {r['n_ok']}/{r['n_requested']} ok in {r['elapsed_s']}s | "
            f"avg word len {s['word_length']['mean']:.2f} | "
            f"avg lemmas/puzzle {s['lemmas_per_puzzle']['mean']:.1f}",
            flush=True,
        )
        preset_results.append(r)

    run_meta = {
        "date": today,
        "label": args.label,
        "strategy": args.strategy or args.label,
        "n_per_preset": args.n,
        "dictionary_size": len(d),
        "dictionary_fingerprint": fp,
        "base_cfg": asdict(BASE_CFG),
        "notes": args.notes,
    }

    (out_dir / "raw.json").write_text(
        json.dumps({"run": run_meta, "presets": preset_results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "report.md").write_text(render_report(run_meta, preset_results), encoding="utf-8")
    conn.close()

    print(f"\nWrote {out_dir / 'report.md'}")
    print(f"Wrote {out_dir / 'raw.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
