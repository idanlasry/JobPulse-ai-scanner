# JobPulse — Claude Code Context File

> This file is read automatically by Claude Code at the start of every session.
> It contains full project context, architecture, and the current build plan.

---

## 🧠 Project Overview

**JobPulse** is an automated pipeline that:
1. Monitors Telegram job groups using Telethon (MTProto API)
2. Scores job offers against a Data Analyst portfolio using GPT-4o mini
3. Sends high-scoring alerts via Telegram Bot to a personal chat
4. Stores all jobs in SQLite with SHA-256 deduplication

**Goal:** Fully automated, running on GitHub Actions every 3 hours — no local machine needed.

---

## 🏗️ Stack

| Layer | Tool | Purpose |
|---|---|---|
| Ingestion | Python + Telethon | Read Telegram groups as a user (MTProto) |
| Data Modeling | Pydantic v2 | Validate and structure LLM outputs |
| Scoring | OpenAI GPT-4o mini | Score jobs against portfolio.txt |
| Storage | SQLite | Persist jobs, prevent duplicates |
| Alerts | Telegram Bot API | Send scored job alerts to personal chat |
| Scheduling | GitHub Actions | Run pipeline every 3 hours, free tier |
| Package Manager | uv | Python 3.13, pyproject.toml |

---

## 📁 Project Structure

```
/jobs-ai-scanner
├── engine/
│   ├── listener.py     # Telethon client — fetches messages from Telegram groups
│   ├── models.py       # Pydantic schemas: JobOpportunity, ScoredJob
│   ├── brain.py        # GPT-4o mini scoring logic
│   ├── database.py     # SQLite storage and deduplication
│   └── notify.py       # Telegram Bot alert sender
├── config/
│   ├── portfolio.txt   # Candidate profile — used as LLM scoring context
│   └── groups.txt      # Telegram group usernames/IDs to monitor
├── data/
│   ├── raw_dump.json   # Intermediary: listener → brain
│   └── jobs.db         # Persistent job storage (gitignored)
├── main.py             # Orchestrator — runs full pipeline
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

---

## 🧩 Data Models (engine/models.py — Pydantic v2)

```python
class JobOpportunity(BaseModel):
    title: str
    company: str | None
    location: str | None
    is_junior: bool
    tech_stack: list[str]
    contact_info: str | None
    raw_text: str

class ScoredJob(JobOpportunity):
    confidence_score: int  # 1-10, validated
    fit_reasoning: str
```

---

## ⚙️ Code Style Rules

- **Async** — use `async/await` and `asyncio.run()` for all Telethon code
- **Type hints** — on all functions
- **Pydantic v2 syntax** — use `model_validator`, `field_validator` (not v1 decorators)
- **Cell markers** — add `# %%` markers for VS Code interactive kernel execution
- **dotenv** — always load `.env` at the top of each engine file
- **uv** — run scripts with `uv run python filename.py`

---

## 🗂️ GitHub Setup

- Repo: https://github.com/idanlasry/jobs-ai-scanner
- Secrets stored in: Settings → Secrets and variables → Actions
- Workflow file: `.github/workflows/run_scanner.yml`
- Schedule: every 3 hours (`cron: '0 */3 * * *'`)

---

## ✅ Current Build Status

### Stage 1 — Repo & Environment ✅ COMPLETE
- Repo initialized and pushed to GitHub
- All Telegram credentials in `.env`
- All packages installed via uv (telethon, openai, pydantic, python-dotenv, ipykernel)
- portfolio.txt written and structured
- groups.txt populated with 4 groups

### Stage 2 — Ingestion & Data Modeling 🔄 IN PROGRESS
- [ ] Write engine/listener.py
- [ ] Run listener.py — first-time phone verification
- [ ] Write engine/models.py
- [ ] Verify raw_dump.json populates correctly

### Stage 3 — Brain, Persistence & Alerts ⏳ PENDING
- [ ] Write engine/brain.py
- [ ] Write engine/database.py
- [ ] Write engine/notify.py
- [ ] Test scoring + alerts end-to-end

### Stage 4 — Orchestration & Deployment ⏳ PENDING
- [ ] Write main.py
- [ ] Write .github/workflows/run_scanner.yml
- [ ] Add GitHub Secrets
- [ ] Confirm automated run on GitHub Actions

---

## 🛠️ Prompts for Each File

### engine/listener.py
```
In engine/listener.py, write a Python script using the Telethon library.
- Load TELEGRAM_API_ID and TELEGRAM_API_HASH from .env using python-dotenv
- Load group usernames/IDs from config/groups.txt (one per line)
- Create an async function fetch_recent_messages(group, limit=50) that
  connects to Telegram, fetches the last 50 messages, and returns a
  list of dicts with keys: text, timestamp, sender_id, group
- Loop over all groups, collect all messages into one list
- Save the combined output to data/raw_dump.json
- Add a 2-3 second asyncio sleep between group requests
- Handle both @username strings and numeric IDs (like -1002423121294)
- Use asyncio.run() to execute
- Add # %% cell markers for VS Code interactive execution
```

### engine/models.py
```
In engine/models.py, define two Pydantic v2 classes:
- JobOpportunity with fields: title (str), company (str | None),
  location (str | None), is_junior (bool), tech_stack (list[str]),
  contact_info (str | None), raw_text (str)
- ScoredJob inherits from JobOpportunity and adds:
  confidence_score (int, 1-10) and fit_reasoning (str)
- Add a field_validator to enforce confidence_score is between 1 and 10
- Add a model example in a __main__ block for quick testing
- Add # %% cell markers
```

### engine/brain.py
```
Write engine/brain.py using the OpenAI API (GPT-4o mini).
- Load OPENAI_API_KEY from .env
- Load config/portfolio.txt and data/raw_dump.json
- For each message, use GPT-4o mini to:
  1. Determine if it's a job offer (skip if not)
  2. If yes, parse it into a JobOpportunity object
  3. Compare requirements against portfolio.txt content
  4. Assign a confidence_score (1-10) and fit_reasoning
- Use a system prompt with role: "Expert Technical Recruiter"
- Messages may be in Hebrew, English, or mixed — handle both
- Return a list of ScoredJob objects
- Import JobOpportunity and ScoredJob from engine/models.py
- Add # %% cell markers
```

### engine/database.py + engine/notify.py
```
Create engine/database.py:
- Setup a SQLite database at data/jobs.db
- Create a table: jobs with columns:
  message_hash TEXT PRIMARY KEY, title TEXT, company TEXT,
  confidence_score INTEGER, fit_reasoning TEXT,
  contact_info TEXT, timestamp TEXT
- Use SHA-256 hash of raw_text as message_hash
- Functions: init_db(), is_duplicate(hash), save_job(ScoredJob)

Create engine/notify.py:
- Load TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from .env
- Function send_alert(job: ScoredJob) that sends a formatted Telegram
  message including: title, company, score, fit_reasoning, contact_info
- Only send if confidence_score > 7
- Add # %% cell markers
```

### main.py
```
Write main.py as the orchestrator for the full JobPulse pipeline:
1. Call listener.py → fetch messages → save to data/raw_dump.json
2. Call brain.py → score messages → return list of ScoredJob objects
3. For each ScoredJob:
   - Call database.py: check if message_hash already exists
   - If new: save to jobs.db
   - If score > 7: call notify.py to send Telegram alert
4. Print a summary log: "X messages scanned, Y job offers found, Z alerts sent"
5. Handle errors gracefully — one failed group should not crash the whole run
```

### .github/workflows/run_scanner.yml
```
Write a GitHub Actions workflow file at .github/workflows/run_scanner.yml that:
- Triggers on a schedule every 3 hours (cron)
- Also has a manual trigger (workflow_dispatch)
- Runs on ubuntu-latest with Python 3.11
- Installs dependencies via pip from pyproject.toml
- Runs python main.py
- Injects these secrets as env variables: OPENAI_API_KEY,
  TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
```

---

## 🔭 Future Scaling (Post-MVP)

| Feature | Description |
|---|---|
| Keyword Trends | Analyze jobs.db for most in-demand skills |
| CV Recommendations | LLM compares job patterns against portfolio.txt |
| Fit Score Tuning | Review scoring history, refine prompts |
| Multi-source Ingestion | Add LinkedIn RSS or other sources to listener.py |