# %%
import asyncio
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

from engine.models import ScoredJob
from engine.notify import send_alert

load_dotenv()

DB_PATH = Path(__file__).parent / "data" / "jobs.db"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


# %%
def load_all_jobs() -> list[ScoredJob]:
    jobs = []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY confidence_score DESC"
        ).fetchall()

    for row in rows:
        try:
            jobs.append(
                ScoredJob(
                    title=row["title"],
                    company=row["company"],
                    location=None,
                    is_junior=False,
                    tech_stack=[],
                    contact_info=row["contact_info"],
                    job_link=row["job_link"],
                    raw_text="",
                    confidence_score=row["confidence_score"],
                    fit_reasoning=row["fit_reasoning"],
                )
            )
        except Exception as e:
            print(f"[notify_all] Skipping malformed row: {e}")

    return jobs


# %%
async def send_db_summary(total_jobs: int, fitting_jobs: list[ScoredJob]) -> None:
    run_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "*JobPulse — Full DB Scan*",
        f"Date: {run_time}",
        f"Total jobs in DB: {total_jobs}",
        f"High-fit jobs (score > 7): {len(fitting_jobs)}",
    ]
    text = "\n".join(lines)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                TELEGRAM_API_URL,
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": text,
                    "parse_mode": "Markdown",
                },
                timeout=10,
            )
            response.raise_for_status()
            print("[notify_all] DB summary sent")
    except httpx.HTTPStatusError as e:
        print(f"[notify_all] HTTP error sending summary: {e}")
    except httpx.RequestError as e:
        print(f"[notify_all] Network error sending summary: {e}")
    except Exception as e:
        print(f"[notify_all] Unexpected error sending summary: {e}")


# %%
async def main() -> None:
    jobs = load_all_jobs()
    fitting_jobs = [j for j in jobs if j.confidence_score > 7]

    print(
        f"[notify_all] {len(jobs)} total jobs in DB | {len(fitting_jobs)} high-fit (score > 7)"
    )

    # Summary first
    await send_db_summary(total_jobs=len(jobs), fitting_jobs=fitting_jobs)
    await asyncio.sleep(1)  # avoid Telegram rate limit between messages

    # Then per-job alerts for all fitting jobs
    sent = 0
    for job in fitting_jobs:
        try:
            await send_alert(job)
            sent += 1
            await asyncio.sleep(
                1
            )  # 1s pause between alerts — Telegram allows ~1 msg/sec per chat
        except Exception as e:
            print(f"[notify_all] Alert failed for '{job.title}': {e}")

    print(f"[notify_all] Done — {sent} alerts sent")


# %%
if __name__ == "__main__":
    asyncio.run(main())
