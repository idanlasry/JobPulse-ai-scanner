# %%
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "jobs.db"

# %%
with sqlite3.connect(DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT title, company, confidence_score, fit_reasoning, job_link "
        "FROM jobs WHERE confidence_score > 7 ORDER BY confidence_score DESC"
    ).fetchall()

print(f"High-fit jobs (score > 7): {len(rows)}\n")
for row in rows:
    print(f"[{row['confidence_score']}/10] {row['title']} — {row['company'] or 'N/A'}")
    print(f"  Fit: {row['fit_reasoning']}")
    print(f"  Link: {row['job_link']}")
    print()
