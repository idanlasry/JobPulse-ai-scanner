# %%
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# %%
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# %%
def fetch_recent_jobs(limit: int = 5) -> list[dict]:
    response = (
        supabase.table("jobs")
        .select("timestamp, title, company, location, confidence_score, job_link, alerted")
        .order("timestamp", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data


# %%
if __name__ == "__main__":
    jobs = fetch_recent_jobs(5)
    print(f"{'#':<3} {'Score':<7} {'Title':<40} {'Company':<20} {'Date'}")
    print("-" * 95)
    for i, job in enumerate(jobs, 1):
        date = job["timestamp"][:10]
        print(f"{i:<3} {job['confidence_score']:<7} {job['title'][:39]:<40} {(job['company'] or '')[:19]:<20} {date}")
