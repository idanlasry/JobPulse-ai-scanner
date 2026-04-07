# %%
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent))
from engine.models import ScoredJob

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

PORTFOLIO_FILE = Path(__file__).parent.parent / "config" / "portfolio.txt"
RAW_DUMP_FILE = Path(__file__).parent.parent / "data" / "raw_dump.json"
SCORED_DUMP_FILE = Path(__file__).parent.parent / "data" / "scored_dump.json"

client = OpenAI(api_key=OPENAI_API_KEY)


# %%
def load_portfolio() -> str:
    return PORTFOLIO_FILE.read_text(encoding="utf-8")


def load_messages() -> list[dict]:
    return json.loads(RAW_DUMP_FILE.read_text(encoding="utf-8"))


# %%
SYSTEM_PROMPT = """You are an Expert Technical Recruiter evaluating job postings for a specific candidate.
You will be given:
1. A candidate portfolio (skills, experience, preferences)
2. A raw message from a Telegram job group

Your job is to:
1. Decide if the message is a job offer. If not, respond with {{"is_job": false}}.
2. If it is a job offer, check if it contains an application/job link (URL starting with http/https, or t.me, or linkedin.com, or similar).
   — If NO link is found, respond with {{"is_job": false}}.
3. If it's a job with a link, extract all fields and score the fit.

Always respond with valid JSON only — no markdown, no explanation outside the JSON.

Response format when IS a job with a link:
{{
  "is_job": true,
  "title": "...",
  "company": "...",
  "location": "...",
  "is_junior": true,
  "tech_stack": ["Python", "SQL"],
  "contact_info": "...",
  "job_link": "https://...",
  "confidence_score": 7,
  "fit_reasoning": "..."
}}

Response format when NOT a job or no link:
{{
  "is_job": false
}}

Scoring rules:
- confidence_score must be an integer 1-10
- Score based on match between job requirements and the candidate portfolio provided
- null is valid for company, location, contact_info if not mentioned
- tech_stack can be an empty list [] if no tools are mentioned
- Messages may be in Hebrew, English, or mixed — handle both equally
"""


# %%
def score_message(message: dict, portfolio: str) -> ScoredJob | None:
    user_content = f"""CANDIDATE PORTFOLIO:
{portfolio}

---

TELEGRAM MESSAGE (from group: {message.get("group", "unknown")}):
{message.get("text", "")}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        data = json.loads(raw)

        if not data.get("is_job", False):
            return None

        # data["job_link"] raises KeyError if missing — enforces: no link = no job
        job = ScoredJob(
            title=data["title"],
            company=data.get("company"),
            location=data.get("location"),
            is_junior=data["is_junior"],
            tech_stack=data.get("tech_stack", []),
            contact_info=data.get("contact_info"),
            job_link=data["job_link"],
            raw_text=message["text"],
            message_date=message.get("timestamp"),
            source_group=message.get("group", "unknown"),
            confidence_score=data["confidence_score"],
            fit_reasoning=data["fit_reasoning"],
        )
        return job

    except ValidationError as e:
        print(f"[brain] Skipping — ValidationError: {e}")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        print(f"[brain] Skipping — bad LLM response: {e}")
        return None
    except Exception as e:
        print(f"[brain] Skipping — unexpected error: {e}")
        return None


# %%
def run_brain() -> list[ScoredJob]:
    portfolio = load_portfolio()
    messages = load_messages()

    print(f"[brain] Processing {len(messages)} messages...")

    scored_jobs: list[ScoredJob] = []

    for i, message in enumerate(messages):
        result = score_message(message, portfolio)

        if result:
            scored_jobs.append(result)
            print(f"[brain] [{i + 1}/{len(messages)}] Job found: {result.title} (score={result.confidence_score})")

    print(
        f"[brain] Done — {len(scored_jobs)} jobs extracted from {len(messages)} messages"
    )

    try:
        SCORED_DUMP_FILE.write_text(
            json.dumps(
                [json.loads(job.model_dump_json()) for job in scored_jobs],
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[brain] Could not write scored_dump.json: {e}")

    return scored_jobs


# %%
if __name__ == "__main__":
    jobs = run_brain()  # dump is already written inside run_brain()
    for job in jobs:
        print(job.model_dump_json(indent=2))
