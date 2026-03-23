# %%
import csv
import hashlib
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to Python's module search path so engine.models can be imported
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from engine.models import ScoredJob

load_dotenv()

# Absolute path to jobs.db — works from any working directory
DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"
CSV_PATH = Path(__file__).parent.parent / "data" / "jobs.csv"
CSV_HEADERS = ["job_hash", "title", "company", "confidence_score", "fit_reasoning", "contact_info", "job_link", "timestamp"]


# %%
def init_db() -> None:
    # Create data/ folder if it doesn't exist
    DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        # Safe to call every run — does nothing if table already exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_hash      TEXT PRIMARY KEY,  -- SHA-256 of job_link, enforces uniqueness
                title         TEXT,
                company       TEXT,
                confidence_score INTEGER,
                fit_reasoning TEXT,
                contact_info  TEXT,
                job_link      TEXT,
                timestamp     TEXT               -- UTC ISO format
            )
        """)
        conn.commit()


# %%
def _hash(job_link: str) -> str:
    # Private helper — converts job_link to a 64-char hex fingerprint
    # Hashing the link (not raw_text) means same job posted in multiple groups = one hash
    return hashlib.sha256(job_link.encode()).hexdigest()


# %%
def is_duplicate(job_hash: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        # SELECT 1 = just check existence, don't fetch real data — faster
        # ? placeholder = safe against SQL injection
        # job_hash is PRIMARY KEY = indexed lookup, not a full table scan
        row = conn.execute(
            "SELECT 1 FROM jobs WHERE job_hash = ?", (job_hash,)
        ).fetchone()
    return row is not None  # True = duplicate, False = new job


# %%
def save_job(job: ScoredJob) -> None:
    job_hash = _hash(job.job_link)
    timestamp = datetime.now(timezone.utc).isoformat()  # UTC timestamp
    with sqlite3.connect(DB_PATH) as conn:
        # INSERT OR IGNORE = silent no-op if job_hash already exists
        conn.execute(
            """
            INSERT OR IGNORE INTO jobs
                (job_hash, title, company, confidence_score, fit_reasoning, contact_info, job_link, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            # Each ? maps positionally to one value in this tuple
            (
                job_hash,
                job.title,
                job.company,
                job.confidence_score,
                job.fit_reasoning,
                job.contact_info,
                job.job_link,
                timestamp,
            ),
        )
        conn.commit()  # Writes the transaction to disk permanently


# %%
def export_to_csv(jobs: list[ScoredJob]) -> None:
    """Append new jobs to CSV. Creates file with headers on first run; appends only on subsequent runs."""
    if not jobs:
        return
    csv_exists = CSV_PATH.exists()
    mode = "a" if csv_exists else "w"
    with open(CSV_PATH, mode, newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not csv_exists:
            writer.writerow(CSV_HEADERS)
        for job in jobs:
            writer.writerow([
                _hash(job.job_link),
                job.title,
                job.company,
                job.confidence_score,
                job.fit_reasoning,
                job.contact_info,
                job.job_link,
                datetime.now(timezone.utc).isoformat(),
            ])


# %%
if __name__ == "__main__":
    # Only runs when executed directly — not when imported by main.py
    import csv
    import json

    init_db()

    raw = Path(__file__).parent.parent / "data" / "scored_dump.json"
    data = json.loads(raw.read_text(encoding="utf-8"))

    processed = saved = skipped = 0
    for item in data:
        try:
            job = ScoredJob(**item)  # Skip malformed entries gracefully
        except Exception:
            continue

        processed += 1
        job_hash = _hash(job.job_link)
        if is_duplicate(job_hash):
            skipped += 1
        else:
            save_job(job)
            saved += 1

    print(f"Processed: {processed} | Saved: {saved} | Skipped (duplicate): {skipped}")

    # Replicate full DB to CSV — complete snapshot, overwritten each run
    csv_path = Path(__file__).parent.parent / "data" / "jobs.csv"
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT * FROM jobs")
        rows = cursor.fetchall()
        headers = [
            d[0] for d in cursor.description
        ]  # Column names from SQLite metadata

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)  # Write column headers first
        writer.writerows(rows)  # Write all rows

    print(f"Exported {len(rows)} rows → {csv_path}")
