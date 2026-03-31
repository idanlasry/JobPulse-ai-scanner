"""
Validation only — not part of the pipeline.

Purpose: verify that URLExtract can reliably find the same link the LLM extracted,
so we can decide whether to use it as a pre-LLM deduplication gate in checker.py.

Run with:  uv run python scripts/validate_urlextract.py
"""

# %%
import hashlib
import sys
from pathlib import Path

import pandas as pd
from urlextract import URLExtract

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CSV_PATH = Path(__file__).parent.parent / "data" / "jobs.csv"
SAMPLE_SIZE = 150
RANDOM_STATE = 42


# ---------------------------------------------------------------------------
# Helpers — must mirror database.py exactly
# ---------------------------------------------------------------------------
def _hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    # 1. Load CSV
    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} not found.")
        sys.exit(1)

    df = pd.read_csv(CSV_PATH, dtype=str)
    print(f"Loaded {len(df)} rows from {CSV_PATH.name}")

    # 2. Drop rows where raw_text or job_hash is null / empty
    before = len(df)
    df = df.dropna(subset=["raw_text", "job_hash"])
    df = df[df["raw_text"].str.strip() != ""]
    df = df[df["job_hash"].str.strip() != ""]
    print(f"After dropping nulls/empty: {len(df)} rows  (dropped {before - len(df)})")

    # 3. Sample
    n = min(SAMPLE_SIZE, len(df))
    sample = df.sample(n=n, random_state=RANDOM_STATE).reset_index(drop=True)
    print(f"Sampling {n} rows (random_state={RANDOM_STATE})\n")

    # 4. Run URLExtract on each row
    extractor = URLExtract()

    matches = 0
    mismatches = 0
    no_url = 0
    mismatch_details: list[dict] = []

    for _, row in sample.iterrows():
        raw_text: str = row["raw_text"]
        stored_hash: str = row["job_hash"].strip()

        http_urls = [u for u in extractor.gen_urls(raw_text) if u.startswith("http")]

        if not http_urls:
            no_url += 1
            continue

        hashed_urls = {_hash(u): u for u in http_urls}

        if stored_hash in hashed_urls:
            matches += 1
        else:
            mismatches += 1
            mismatch_details.append(
                {
                    "stored_hash": stored_hash,
                    "all_extracted_urls": http_urls,
                    "raw_text_preview": raw_text[:200],
                }
            )

    # 5. Summary report
    total = matches + mismatches + no_url
    pct = lambda k: f"{k / total * 100:.1f}%" if total else "n/a"

    print("=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total rows sampled : {total}")
    print(f"Matches            : {matches} ({pct(matches)})")
    print(f"Mismatches         : {mismatches} ({pct(mismatches)})")
    print(f"No URL found       : {no_url} ({pct(no_url)})")
    print("=" * 60)

    # 6. Per-mismatch detail
    if mismatch_details:
        print(f"\nMISMATCH DETAILS ({len(mismatch_details)} rows)\n")
        for i, d in enumerate(mismatch_details, 1):
            print(f"--- Mismatch #{i} ---")
            print(f"  stored_hash    : {d['stored_hash']}")
            for u in d["all_extracted_urls"]:
                print(f"  extracted_url  : {u}")
            preview = d["raw_text_preview"].encode("ascii", errors="replace").decode("ascii")
            print(f"  raw_text[:200] : {preview!r}")
            print()
    else:
        print("\nNo mismatches — perfect alignment.")


if __name__ == "__main__":
    main()
