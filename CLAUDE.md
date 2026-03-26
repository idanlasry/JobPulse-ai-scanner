# JobPulse — Claude Code Context File

> This file is read automatically by Claude Code at the start of every session.
> It contains full project context, architecture, current build status, and design decisions.
> Read this before touching any file.

---

## 🧠 Project Overview

**JobPulse** is an automated pipeline that:
1. Monitors Telegram job groups using Telethon (MTProto API)
2. Scores job offers against a Data Analyst portfolio using GPT-4o mini
3. Sends high-scoring alerts via Telegram Bot to a personal chat
4. Stores all jobs in two independent layers: CSV (cross-run, committed to repo) + SQLite (local analytics)

**Goal:** Fully automated, running on GitHub Actions 3× daily on weekdays — no local machine needed.

---

## 🏗️ Stack

| Layer | Tool | Purpose |
|---|---|---|
| Ingestion | Python + Telethon | Read Telegram groups as a user (MTProto) |
| Data Modeling | Pydantic v2 | Validate and structure LLM outputs |
| Scoring | OpenAI GPT-4o mini | Score jobs against portfolio.txt |
| Storage (cross-run) | CSV (`data/jobs.csv`) | Committed to repo — survives GitHub Actions ephemeral runners |
| Storage (local) | SQLite (`data/jobs.db`) | Gitignored — local only, reserved for future analytics features |
| Alerts | Telegram Bot API | Send scored job alerts to personal chat |
| Scheduling | GitHub Actions | Run pipeline 3× daily on weekdays (Mon–Fri), free tier |
| Package Manager | uv | Python 3.13, pyproject.toml |

---

## 🗄️ Storage Architecture

JobPulse uses two independent storage layers. Neither depends on the other — a failure in one must never block the other.

**Unified schema — both layers store the same 12 columns:**

| Column | Type | Notes |
|---|---|---|
| `job_hash` | TEXT | SHA-256 of `job_link` — PRIMARY KEY in SQLite |
| `timestamp` | TEXT | ISO 8601 UTC, auto-added at save time |
| `title` | TEXT | |
| `company` | TEXT | nullable |
| `location` | TEXT | nullable |
| `is_junior` | INTEGER/bool | SQLite stores as 0/1; CSV stores as True/False |
| `tech_stack` | TEXT | JSON-encoded list in both layers |
| `contact_info` | TEXT | nullable |
| `job_link` | TEXT | dedup key |
| `raw_text` | TEXT | |
| `confidence_score` | INTEGER | 1–10 |
| `fit_reasoning` | TEXT | |

**CSV layer (`data/jobs.csv`) — cross-run deduplication**
- Committed to the repo after every GitHub Actions run
- This is the source of truth for deduplication on GitHub Actions, where `jobs.db` is wiped after each run
- Dedup key: `job_link` (exact string match, checked before every append)
- Append-only — new rows are added; existing rows are never rewritten
- Header is written only when the file is new or empty
- Implemented in `engine/database.py` → `save_to_csv(job: ScoredJob) -> bool`
  - Returns `True` if the job was new and appended, `False` if it was a duplicate and skipped
- Alert eligibility is determined by the CSV layer: only CSV-new jobs with `confidence_score > 7` trigger a Telegram alert

**SQLite layer (`data/jobs.db`) — local persistence**
- Gitignored — ephemeral on GitHub Actions, persistent on local machine
- Dedup key: SHA-256 hash of `job_link` (stored as `job_hash` PRIMARY KEY)
- Reserved for future analytics: keyword trends, fit score tuning, CV recommendations
- Implemented in `engine/database.py` → `save_job(job: ScoredJob)`, `is_duplicate(job_hash: str) -> bool`

**How they interact in `main.py`:**
Each scored job is written to both layers independently, each wrapped in its own `try/except`. A DB write failure does not affect the CSV write, and vice versa.

---

## 📁 Project Structure

```
/jobs-ai-scanner
├── engine/
│   ├── listener.py     # Telethon client — fetches messages from Telegram groups; load_last_seen() / save_last_seen() for timestamp checkpoints
│   ├── models.py       # Pydantic schemas: JobOpportunity, ScoredJob
│   ├── brain.py        # GPT-4o mini scoring logic
│   ├── database.py     # Dual storage: SQLite (local) + CSV (cross-run). Dedup key: job_link
│   └── notify.py       # Telegram Bot alert sender — send_summary (stats) + send_alert (per job), score > 7 only
│                       # Note: both send_alert and send_summary use parse_mode: "HTML" — Markdown breaks on URLs with underscores (e.g. utm_source=telegram)
│                       # Note: send_summary signature: send_summary(groups_scanned, jobs_found, new_jobs, fitting_jobs)
├── config/
│   ├── portfolio.txt   # Candidate profile — used as LLM scoring context
│   └── groups.txt      # Telegram group usernames/IDs to monitor
├── data/
│   ├── raw_dump.json   # Intermediary: listener → brain (overwritten each run)
│   ├── scored_dump.json # Intermediary: brain → notify / database (overwritten each run)
│   ├── jobs.csv        # Cross-run job store — committed to repo, survives GitHub Actions runners
│   ├── last_seen.csv   # Checkpoint file — group_id → last_seen_ts (ISO 8601 UTC), committed to repo
│   └── jobs.db         # Local job store — gitignored, ephemeral on GitHub Actions
├── main.py             # Orchestrator — runs full pipeline
├── notify_all.py       # Standalone script: loads all jobs from DB, sends full-DB summary + individual alerts for all high-fit jobs (score > 7)
├── DB_search.py        # Dev utility: prints all high-fit jobs (score > 7) from jobs.db to terminal
├── connection_test.py  # Dev utility: sends a test message via Telegram Bot API to verify credentials
├── CLAUDE.md           # This file
├── pyproject.toml      # uv dependencies
└── .github/
    └── workflows/
        └── run_scanner.yml  # GitHub Actions — scheduled automation
```

---

## 🔑 Environment Variables (.env)

```env
# MTProto API — used by Telethon to READ groups as a user
TELEGRAM_API_ID=
TELEGRAM_API_HASH=

# Bot API — used by notify.py to SEND alerts to personal chat
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# OpenAI — used by brain.py to score job offers
OPENAI_API_KEY=
```

Load with: `from dotenv import load_dotenv`

---

## 📋 Telegram Groups (config/groups.txt)

```
hitechjobsjunior
hitechjobsdata
-1002423121294
-1002875221568
```

Note: numeric IDs are private groups. Both formats work with Telethon.
Note: -1002423121294 currently throws PeerChannel error — fix by opening the group in the Telegram app and scrolling once before next run.

---

## 🧩 Data Models (engine/models.py — Pydantic v2) ✅ COMPLETE

```python
class JobOpportunity(BaseModel):
    title: str
    company: str | None = None
    location: str | None = None
    is_junior: bool
    tech_stack: list[str]
    contact_info: str | None = None
    job_link: str                   # REQUIRED — no default, not optional
    raw_text: str

class ScoredJob(JobOpportunity):
    confidence_score: int           # 1-10, enforced by field_validator
    fit_reasoning: str
```

### ⚠️ Critical Design Decisions — Do Not Change

**`job_link: str` is required with no default:**
- A job post without an apply link is not actionable — discard it
- `brain.py` must skip any message where GPT cannot extract a `job_link`
- Deduplication in `database.py` hashes by `job_link`, not `raw_text`
  - Reason: same job posted across multiple groups has same link but different raw_text
  - Hashing by `job_link` = one alert per job, regardless of how many groups posted it
- `notify.py` must include `job_link` in the alert message so user can tap and apply

**`confidence_score` validator:**
- Must be int between 1 and 10
- If GPT returns out-of-range value → `ValidationError` raised → object never created
- Wrap all `ScoredJob(...)` creation in `brain.py` with `try/except ValidationError` — skip bad responses, never crash the pipeline

---

## ⚙️ Code Style Rules

- **Async** — use `async/await` and `asyncio.run()` for all Telethon code
- **Type hints** — on all functions
- **Pydantic v2 syntax** — use `model_validator`, `field_validator` (not v1 decorators)
- **Cell markers** — add `# %%` markers for VS Code interactive kernel execution
- **dotenv** — always load `.env` at the top of each engine file
- **uv** — run scripts with `uv run python filename.py`
- **Graceful errors** — one failed group or bad LLM response must never crash the full run

---

## 🗂️ GitHub Setup

- Repo: https://github.com/idanlasry/jobs-ai-scanner
- Secrets stored in: Settings → Secrets and variables → Actions
- Workflow file: `.github/workflows/run_scanner.yml`
- Schedule: Mon–Fri at 08:00, 14:00, 18:00 Israel time (UTC+3) — `cron: '0 5 * * 1-5'`, `'0 11 * * 1-5'`, `'0 15 * * 1-5'`

---

## ✅ Current Build Status

### Stage 1 — Repo & Environment ✅ COMPLETE
- Repo initialized and pushed to GitHub
- All Telegram credentials in `.env`
- All packages installed via uv (telethon, openai, pydantic, python-dotenv, ipykernel)
- portfolio.txt written and structured
- groups.txt populated with 4 groups

### Stage 2 — Ingestion & Data Modeling ✅ COMPLETE
- [x] engine/listener.py written and tested
- [x] First-time phone verification completed — jobpulse_session.session created
- [x] 15 messages fetched from 3/4 groups, saved to raw_dump.json
- [x] engine/models.py written and tested
- [x] field_validator on confidence_score verified
- [x] job_link added as required field

### Stage 3 — Brain, Persistence & Alerts ✅ COMPLETE
- [x] Write engine/brain.py 13/15 jobs found
- [x] Write engine/database.py
- [x] Write engine/notify.py
- [x] Test scoring + alerts end-to-end

### Stage 4 — Orchestration & Deployment ✅ COMPLETE
- [x] Write main.py
- [x] Write .github/workflows/run_scanner.yml
- [x] Add GitHub Secrets
- [x] Confirm automated run on GitHub Actions

### Stage 5 — Storage & Deduplication ✅ COMPLETE
- [x] Dual storage architecture implemented — CSV + SQLite independent layers
- [x] CSV layer: cross-run deduplication on GitHub Actions via committed data/jobs.csv
- [x] SQLite layer: local persistence and future scaling infrastructure
- [x] Pipeline deployed and verified end-to-end on GitHub Actions

### Stage 6 — Schema Consolidation ✅ COMPLETE
- [x] Unified both CSV and SQLite to the same 12-column schema (was mismatched: CSV had 10 cols, SQLite had 8 cols, each missing different fields)
- [x] SQLite now stores all ScoredJob fields: added `location`, `is_junior`, `tech_stack` (JSON), `raw_text`, `timestamp`
- [x] CSV now includes `job_hash` and `timestamp`; column order matches SQLite
- [x] Stale `data/jobs.csv` and `data/jobs.db` deleted — will be recreated fresh on next run

### Stage 7 — Optimised Listening (Checkpoint-Based Skip) ✅ COMPLETE
- [x] `data/last_seen.csv` tracks `last_seen_ts` (ISO 8601 UTC) per group — committed to repo, survives GitHub Actions runners
- [x] `listener.py` loads checkpoint on startup (`load_last_seen()`), filters fetched messages by timestamp to skip already-processed ones
- [x] `main.py` calls `save_last_seen()` after a clean pipeline run to advance the checkpoint
- **Implementation note:** Uses timestamp-based filtering (not `min_id`) — each group's checkpoint is the datetime of the most recent message from the previous run. Messages with `date <= last_seen_ts` are skipped.

---

## 🔭 Future Scaling (Post-MVP)

| Feature | Description |
|---|---|
| Keyword Trends | Analyze jobs.db for most in-demand skills |
| CV Recommendations | LLM compares job patterns against portfolio.txt |
| Fit Score Tuning | Review scoring history, refine prompts |
| Multi-source Ingestion | Add LinkedIn RSS or other sources to listener.py |

---

## 🚨 Open Tasks

> No blocking tasks. The pipeline is fully deployed and running on GitHub Actions.

### Future Improvements (non-blocking)

- **Raise fetch limit** — `listener.py` currently uses `limit=5` per group. Now that checkpoint-based skipping is in place, this can be safely raised (e.g. `limit=50`) to catch more jobs per run without re-processing old messages.
- **PeerChannel error on `-1002423121294`** — fix by opening the group in the Telegram app and scrolling once, then re-running.
