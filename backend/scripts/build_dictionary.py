"""Build the compiled lemma table from the Lyashevskaya–Sharov 2009 frequency
list (Freq2011 update) intersected with the OpenCorpora dictionary bundled
inside pymorphy3.

Inputs (fetched on first run, cached locally):
  - http://dict.ruslang.ru/Freq2011.zip
      → backend/data/sources/Freq2011.zip
      → freqrnc2011.csv extracted alongside

Output:
  - SQLite `lemmas` table at backend/data/rsb.db (or $RSB_DB)

Filters (see also overrides — todo #8):
  - Frequency ≥ 0.5 ipm (planning doc threshold)
  - Lemma uses only alphabet letters (per `HIVE_LETTERS` ∪ {Ё})
  - No hyphens, spaces, or non-letter chars
  - POS in open-class set {s (noun), v (verb), a (adjective), adv, num, praedic, comp}
    — closed-class (prepositions, conjunctions, particles, interjections, pronouns)
      are dropped per the planning doc
  - Proper nouns (pymorphy3 tag with Geox/Surn/Patr/Name/Init/Trad) are dropped
  - pymorphy3 must recognize the lemma (round-trip check)
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterator

# Ensure backend/src is importable when running as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rsb.alphabet import HIVE_LETTERS, letter_mask  # noqa: E402
from rsb.dictionary import compute_form_masks  # noqa: E402
from rsb.overrides import apply_to_rows, load as load_overrides  # noqa: E402
from rsb.store import open_db, replace_lemmas  # noqa: E402

# Try-import here keeps the script reportable when pymorphy3 isn't installed.
try:
    import pymorphy3  # noqa: E402
except ImportError as e:
    sys.exit(f"pymorphy3 not installed: {e}. Run `uv sync` in backend/ first.")


FREQ_URL = "http://dict.ruslang.ru/Freq2011.zip"

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SOURCES_DIR = BACKEND_ROOT / "data" / "sources"
DEFAULT_DB = BACKEND_ROOT / "data" / "rsb.db"

# Map L–S POS codes to a coarse internal label.
POS_KEEP: dict[str, str] = {
    "s": "NOUN",
    "v": "VERB",
    "a": "ADJF",
    "adv": "ADVB",
    "num": "NUMR",
    "praedic": "PRED",
    "comp": "COMP",  # synthetic comparatives that have their own headword
}

# pymorphy3 tags that indicate proper nouns or other excluded categories.
PROPER_NOUN_TAGS: set[str] = {"Geox", "Surn", "Patr", "Name", "Init", "Trad", "Orgn"}

# Hive alphabet plus Ё for input matching. Anything outside this set in a lemma
# (digits, punctuation, latin letters, Ъ) → drop.
ALLOWED = frozenset(HIVE_LETTERS) | {"ё"}


def fetch_and_extract(out_csv: Path, *, force: bool) -> None:
    """Download Freq2011.zip and extract freqrnc2011.csv to out_csv. Idempotent."""
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    if out_csv.exists() and not force:
        print(f"  cached: {out_csv}")
        return
    print(f"  downloading {FREQ_URL} ...")
    req = urllib.request.Request(FREQ_URL, headers={"User-Agent": "rsb-build/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    print(f"  got {len(raw)} bytes, extracting ...")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        with z.open("freqrnc2011.csv") as zf:
            out_csv.write_bytes(zf.read())
    print(f"  wrote {out_csv} ({out_csv.stat().st_size} bytes)")


def iter_rows(csv_path: Path) -> Iterator[tuple[str, str, float]]:
    """Yield (lemma, ls_pos, freq_ipm) from the TSV. Skips header."""
    with csv_path.open(encoding="utf-8") as f:
        header = f.readline()
        if not header.lower().startswith("lemma"):
            raise RuntimeError(f"Unexpected header: {header!r}")
        for raw in f:
            line = raw.rstrip("\n").rstrip("\r")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            lemma = parts[0].strip().lower()
            pos = parts[1].strip().lower()
            try:
                freq = float(parts[2].strip())
            except ValueError:
                continue
            yield lemma, pos, freq


def is_clean_lemma(lemma: str) -> bool:
    if not lemma or len(lemma) < 2:
        return False
    return all(ch in ALLOWED for ch in lemma)


def is_proper_noun(morph: "pymorphy3.MorphAnalyzer", lemma: str) -> bool:
    """True if pymorphy3's top parse for this lemma carries a proper-noun tag."""
    for p in morph.parse(lemma):
        if p.normal_form != lemma:
            continue
        grammemes = set(str(p.tag).replace(",", " ").split())
        if grammemes & PROPER_NOUN_TAGS:
            return True
        # First parse that matches is the canonical one; stop.
        break
    return False


def pymorphy_knows(morph: "pymorphy3.MorphAnalyzer", lemma: str) -> bool:
    """True if pymorphy3 can parse the lemma to itself (round-trip)."""
    for p in morph.parse(lemma):
        if p.normal_form == lemma:
            return True
    return False


def build(
    csv_path: Path,
    db_path: Path,
    *,
    freq_threshold: float,
    progress_every: int,
) -> int:
    morph = pymorphy3.MorphAnalyzer()

    # Step 1: parse + initial filter (frequency, POS, clean lemma).
    print("  filtering rows ...")
    candidates: dict[str, tuple[str, float]] = {}  # lemma -> (best_pos_label, summed_freq)
    seen, kept_initial, dropped_freq, dropped_pos, dropped_clean = 0, 0, 0, 0, 0
    for lemma, ls_pos, freq in iter_rows(csv_path):
        seen += 1
        if freq < freq_threshold:
            dropped_freq += 1
            continue
        pos_label = POS_KEEP.get(ls_pos)
        if pos_label is None:
            dropped_pos += 1
            continue
        if not is_clean_lemma(lemma):
            dropped_clean += 1
            continue
        # Aggregate per lemma: keep the highest-frequency POS as the canonical
        # entry; sum frequencies across POSes so e.g. "стекло (NOUN)" gets full credit.
        cur = candidates.get(lemma)
        if cur is None:
            candidates[lemma] = (pos_label, freq)
            kept_initial += 1
        else:
            cur_pos, cur_freq = cur
            new_total = cur_freq + freq
            # Prefer the highest-freq POS as canonical label.
            best_pos = pos_label if freq > cur_freq else cur_pos
            candidates[lemma] = (best_pos, new_total)

    print(f"    rows seen:                {seen}")
    print(f"    dropped by freq <{freq_threshold}: {dropped_freq}")
    print(f"    dropped by closed-class POS: {dropped_pos}")
    print(f"    dropped by alphabet check:   {dropped_clean}")
    print(f"    distinct lemmas kept:        {len(candidates)}")

    # Step 2: pymorphy3 round-trip + proper-noun filter + form-mask enumeration.
    print("  validating against pymorphy3 + enumerating forms ...")
    final: list[tuple[str, str, float, int, frozenset[int]]] = []
    dropped_unknown, dropped_proper = 0, 0
    for i, (lemma, (pos_label, freq)) in enumerate(candidates.items()):
        if progress_every and i and i % progress_every == 0:
            print(f"    ... {i} / {len(candidates)}")
        if not pymorphy_knows(morph, lemma):
            dropped_unknown += 1
            continue
        if pos_label == "NOUN" and is_proper_noun(morph, lemma):
            dropped_proper += 1
            continue
        form_masks = compute_form_masks(morph, lemma)
        final.append((lemma, pos_label, round(freq, 3), letter_mask(lemma), form_masks))

    print(f"    dropped by pymorphy3 unknown: {dropped_unknown}")
    print(f"    dropped by proper-noun:       {dropped_proper}")
    avg_forms = (sum(len(r[4]) for r in final) / len(final)) if final else 0.0
    print(f"    avg distinct form-masks/lemma: {avg_forms:.1f}")

    # Step 2.5: apply manual overrides (include/exclude).
    overrides_path = BACKEND_ROOT / "data" / "overrides.yaml"
    ov = load_overrides(overrides_path)
    before = len(final)
    final = apply_to_rows(final, ov)
    print(f"  overrides: include={len(ov.include)} exclude={len(ov.exclude)} net change: {len(final) - before:+d}")
    print(f"  final count: {len(final)}")

    # Step 3: write to DB.
    print(f"  writing to {db_path} ...")
    conn = open_db(db_path)
    try:
        replace_lemmas(conn, final)
    finally:
        conn.close()
    return len(final)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=Path(os.environ.get("RSB_DB", DEFAULT_DB)),
                    help=f"SQLite path (default: {DEFAULT_DB})")
    ap.add_argument("--threshold", type=float, default=0.5, help="Frequency threshold in ipm (default 0.5)")
    ap.add_argument("--force-download", action="store_true", help="Re-download the source even if cached")
    ap.add_argument("--progress-every", type=int, default=5000)
    args = ap.parse_args()

    csv_path = SOURCES_DIR / "freqrnc2011.csv"

    print("== Russian Spelling Bee — dictionary build ==")
    print(f"  freq threshold: {args.threshold} ipm")
    print(f"  db:             {args.db}")
    print(f"  source csv:     {csv_path}")

    print()
    print("STEP 1 / 2: ensure source CSV")
    fetch_and_extract(csv_path, force=args.force_download)

    print()
    print("STEP 2 / 2: compile + write")
    n = build(csv_path, args.db, freq_threshold=args.threshold, progress_every=args.progress_every)

    print()
    print(f"== done: {n} lemmas compiled ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
