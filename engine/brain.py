# %%
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.scoring_overrides import RULES as OVERRIDE_RULES
from config.scoring_overrides import OverrideRule
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
1. A CANDIDATE PORTFOLIO — defines the candidate's profile, skills, hard exclusions, calibration rules, and scored examples. This is the source of truth for what makes a good vs. bad fit.
2. A raw message from a job group (Telegram or similar).

Your job:
1. Decide if the message is a job offer. If not, respond with {"is_job": false}.
2. If it is a job offer, check it contains an application/job link (URL starting with http/https, t.me, linkedin.com, or similar).
   — If NO link is found, respond with {"is_job": false}.
3. If it's a job with a link, extract all fields and score the fit.

Note: Some postings are just keywords + a company name + a link. Treat these as valid job offers even if they lack full sentences.

Always respond with valid JSON only — no markdown, no explanation outside the JSON.

Response format when IS a job with a link:
{
  "is_job": true,
  "title": "...",
  "company": "...",
  "location": "...",
  "is_junior": true,
  "tech_stack": ["Python", "SQL"],
  "contact_info": "...",
  "job_link": "https://...",
  "fit_score": 7,
  "confidence_score": 8,
  "fit_reasoning": "POSITIVES: ...\\nNEGATIVES: ...\\nHARD BLOCK: NONE\\nSCORE: N — one sentence"
}

Response format when NOT a job or no link:
{
  "is_job": false
}

─────────────────────────────────────────
HOW TO SCORE
─────────────────────────────────────────
The CANDIDATE PORTFOLIO defines:
  • HARD EXCLUSIONS — triggers that force fit_score to 1 or 2. Apply them first.
  • CALIBRATION RULES — score modifiers based on seniority, location, role type, etc.
  • SCORED EXAMPLES — worked examples that anchor the 1–10 scale. Treat them as the ground truth.

Follow the portfolio exactly. Your role is to apply its rules to each message, not to substitute your own judgment about what is or isn't a good fit.

─────────────────────────────────────────
REQUIRED fit_reasoning FORMAT
─────────────────────────────────────────
POSITIVES: [signal 1, signal 2, ...]
NEGATIVES: [signal 1, signal 2, ...]
HARD BLOCK: NONE  — OR —  [name the exact rule from the portfolio's HARD EXCLUSIONS]
SCORE: [N] — [one sentence]

─────────────────────────────────────────
REFLECTION — verify before outputting
─────────────────────────────────────────
R1 — Block/score consistency:
  If HARD BLOCK is NONE → fit_score must be 3 or higher.
  If fit_score is 1 or 2 → HARD BLOCK must name a specific rule from the portfolio's HARD EXCLUSIONS.
  If these are inconsistent, fix the error before outputting.

R2 — Negative proportionality:
  If your only NEGATIVES are mild signals (e.g. "mid-level", "3+ years") AND fit_score is below 6:
  You have over-penalized. Revise upward or add a substantive second negative that justifies the low score.

─────────────────────────────────────────
CONFIDENCE SCORE (separate from fit_score)
─────────────────────────────────────────
Measures how much data was present in the posting vs. inferred.
  10  = all key fields explicit (title, seniority, location, tech stack, link)
  7–9 = most fields present, minor inference needed
  4–6 = significant inference (e.g. no stack, no location)
  1–3 = highly vague post, most fields inferred or missing

─────────────────────────────────────────
ADDITIONAL RULES
─────────────────────────────────────────
- fit_score and confidence_score must each be integers 1–10
- null is valid for company, location, contact_info if not mentioned
- tech_stack lists the tools the JOB requires (not filtered to candidate skills)
- tech_stack should list specific tools/technologies, not generic skill labels like "Business Analysis"
- Messages may be in any language — handle multilingual content equally
"""


# %%
_SUPPORTED_CONDITIONS = {
    "title_contains_any",
    "tech_stack_any_of",
    "location_contains_any",
    "fit_score_lte",
    "fit_score_gte",
    "is_junior_eq",
}
_SUPPORTED_ACTIONS = {"set_fit_score", "append_reasoning"}


def _validate_override_rules(rules: list[OverrideRule]) -> None:
    """Validate every rule at import time. Raises loudly on any malformed rule.

    Silent override failures would be worse than a startup crash — a rule that
    never matches because of a typo would let bad scores ship undetected.
    """
    for i, rule in enumerate(rules):
        for key in ("name", "description", "conditions", "action"):
            if key not in rule:
                raise RuntimeError(
                    f"[overrides] malformed rule at index {i}: missing required key '{key}'"
                )
        unknown_conds = set(rule["conditions"]) - _SUPPORTED_CONDITIONS
        if unknown_conds:
            raise RuntimeError(
                f"[overrides] rule '{rule['name']}': unknown condition keys {unknown_conds}. "
                f"Supported: {sorted(_SUPPORTED_CONDITIONS)}"
            )
        unknown_actions = set(rule["action"]) - _SUPPORTED_ACTIONS
        if unknown_actions:
            raise RuntimeError(
                f"[overrides] rule '{rule['name']}': unknown action keys {unknown_actions}. "
                f"Supported: {sorted(_SUPPORTED_ACTIONS)}"
            )
        if not rule["action"]:
            raise RuntimeError(f"[overrides] rule '{rule['name']}': action is empty")


_validate_override_rules(OVERRIDE_RULES)
print(f"[brain] Loaded {len(OVERRIDE_RULES)} scoring override rule(s)")


def _rule_matches(rule: OverrideRule, data: dict) -> bool:
    title = (data.get("title") or "").lower()
    location = (data.get("location") or "").lower()
    stack = {t.lower() for t in data.get("tech_stack", []) if isinstance(t, str)}
    fit_score = data.get("fit_score")
    is_junior = data.get("is_junior")

    for key, val in rule["conditions"].items():
        if key == "title_contains_any":
            if not any(sub.lower() in title for sub in val):
                return False
        elif key == "tech_stack_any_of":
            if not ({s.lower() for s in val} & stack):
                return False
        elif key == "location_contains_any":
            if not any(sub.lower() in location for sub in val):
                return False
        elif key == "fit_score_lte":
            if not isinstance(fit_score, int) or fit_score > val:
                return False
        elif key == "fit_score_gte":
            if not isinstance(fit_score, int) or fit_score < val:
                return False
        elif key == "is_junior_eq":
            if is_junior != val:
                return False
    return True


def apply_overrides(data: dict, rules: list[OverrideRule]) -> dict:
    """Apply all matching override rules to `data` in place. Returns the same dict."""
    for rule in rules:
        if _rule_matches(rule, data):
            action = rule["action"]
            if "set_fit_score" in action:
                data["fit_score"] = action["set_fit_score"]
            if "append_reasoning" in action:
                existing = data.get("fit_reasoning", "") or ""
                data["fit_reasoning"] = (existing + "\n" + action["append_reasoning"]).strip()
    return data


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

        apply_overrides(data, OVERRIDE_RULES)

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
            fit_score=data["fit_score"],
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
            print(
                f"[brain] [{i + 1}/{len(messages)}] Job found: {result.title} (fit={result.fit_score}, conf={result.confidence_score})"
            )

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
