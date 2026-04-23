# %%
import csv
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from engine.models import ScoredJob
from supabase import create_client

load_dotenv()

_SUPABASE_URL = os.getenv("SUPABASE_URL", "")
_SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
_supabase = create_client(_SUPABASE_URL, _SUPABASE_KEY) if _SUPABASE_URL and _SUPABASE_KEY else None

CSV_PATH = Path(__file__).parent.parent / "data" / "jobs.csv"
CSV_HEADERS = [
    "job_hash", "timestamp", "title", "company", "location", "is_junior",
    "tech_stack", "contact_info", "job_link", "raw_text",
    "confidence_score", "fit_score", "fit_reasoning",
]


# %%
def _hash(job_link: str) -> str:
    return hashlib.sha256(job_link.encode()).hexdigest()


# %%
def save_to_csv(job: ScoredJob) -> bool:
    CSV_PATH.parent.mkdir(exist_ok=True)

    file_empty = not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0

    existing_links: set[str] = set()
    if not file_empty:
        try:
            with open(CSV_PATH, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    existing_links.add(row["job_link"])
        except Exception:
            pass  # unreadable CSV treated as empty — will write header

    if job.job_link in existing_links:
        return False  # Duplicate — skip

    with open(CSV_PATH, "w" if file_empty else "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if file_empty:
            writer.writerow(CSV_HEADERS)
        job_hash = _hash(job.job_link)
        timestamp = datetime.now(timezone.utc).isoformat()
        writer.writerow([
            job_hash,
            timestamp,
            job.title,
            job.company,
            job.location,
            job.is_junior,
            json.dumps(job.tech_stack),
            job.contact_info,
            job.job_link,
            job.raw_text,
            job.confidence_score,
            job.fit_score,
            job.fit_reasoning,
        ])
    return True  # New job saved


# %%
def save_to_supabase(job: ScoredJob, source_group: str) -> bool:
    try:
        if _supabase is None:
            logging.warning("save_to_supabase: client not initialised (missing SUPABASE_URL or SUPABASE_KEY)")
            return False

        job_hash = _hash(job.job_link)
        timestamp = job.message_date or datetime.now(timezone.utc).isoformat()

        row = {
            "job_hash": job_hash,
            "timestamp": timestamp,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "is_junior": job.is_junior,
            "tech_stack": job.tech_stack,
            "contact_info": job.contact_info,
            "job_link": job.job_link,
            "raw_text": job.raw_text,
            "confidence_score": job.confidence_score,
            "fit_score": job.fit_score,
            "fit_reasoning": job.fit_reasoning,
            "source": "telegram",
            "source_group": source_group,
            "repo": "jobpulse",
            "alerted": False,
        }

        _supabase.table("jobs").insert(row).execute()
        return True

    except Exception as exc:
        msg = str(exc)
        if "23505" in msg or "duplicate" in msg.lower() or "unique" in msg.lower():
            return False
        logging.error("save_to_supabase error: %s", exc)
        return False
