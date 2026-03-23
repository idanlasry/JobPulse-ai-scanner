# JobPulse

Automated job scanner that monitors Telegram groups, scores offers against your portfolio using GPT-4o mini, and sends high-fit alerts to your personal chat.

## How It Works

1. **Listen** — Telethon reads messages from configured Telegram groups as a user (MTProto)
2. **Score** — GPT-4o mini evaluates each job against your `config/portfolio.txt` (1–10 fit score)
3. **Store** — Every job is saved to CSV (committed to repo) and SQLite (local analytics)
4. **Alert** — Jobs scoring above 7 trigger a Telegram Bot message to your personal chat
5. **Repeat** — GitHub Actions runs the full pipeline 3× daily on weekdays, no local machine needed

## Stack

| Layer | Tool |
|---|---|
| Ingestion | Python + Telethon (MTProto) |
| Scoring | OpenAI GPT-4o mini |
| Data Modeling | Pydantic v2 |
| Cross-run Storage | CSV (`data/jobs.csv`) — committed to repo |
| Local Storage | SQLite (`data/jobs.db`) — gitignored |
| Alerts | Telegram Bot API |
| Scheduling | GitHub Actions (Mon–Fri, 08:00 / 14:00 / 18:00 Israel time) |
| Package Manager | uv (Python 3.13) |

## Project Structure

```
├── engine/
│   ├── listener.py      # Fetch messages from Telegram groups via Telethon
│   ├── brain.py         # Score jobs with GPT-4o mini
│   ├── database.py      # Dual storage: CSV + SQLite, dedup by job_link
│   ├── notify.py        # Send alerts via Telegram Bot
│   └── models.py        # Pydantic schemas: JobOpportunity, ScoredJob
├── config/
│   ├── portfolio.txt    # Your profile — LLM scoring context
│   └── groups.txt       # Telegram groups to monitor
├── data/
│   ├── jobs.csv         # Cross-run job store (committed)
│   └── jobs.db          # Local job store (gitignored)
├── main.py              # Pipeline orchestrator
├── notify_all.py        # One-shot: send alerts for all high-fit jobs in DB
├── DB_search.py         # Dev utility: print high-fit jobs to terminal
└── .github/workflows/
    └── run_scanner.yml  # Scheduled automation
```

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/idanlasry/jobs-ai-scanner
cd jobs-ai-scanner
pip install uv
uv sync
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```env
# Telethon — read Telegram groups as a user
TELEGRAM_API_ID=
TELEGRAM_API_HASH=

# Telegram Bot — send alerts to personal chat
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# OpenAI
OPENAI_API_KEY=
```

Get `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` from [my.telegram.org](https://my.telegram.org).
Get `TELEGRAM_BOT_TOKEN` from [@BotFather](https://t.me/botfather).

### 3. Configure your profile and groups

- Edit `config/portfolio.txt` with your skills, experience, and preferences
- Edit `config/groups.txt` with Telegram group usernames or IDs (one per line)

### 4. Authenticate Telethon (first run only)

```bash
uv run python engine/listener.py
```

This creates `jobpulse_session.session` after phone verification. Do it once locally.

### 5. Run the pipeline

```bash
uv run python main.py
```

## GitHub Actions Deployment

The pipeline runs automatically Mon–Fri at 08:00, 14:00, and 18:00 Israel time.

**Required GitHub Secrets** (Settings → Secrets and variables → Actions):

| Secret | Description |
|---|---|
| `TELEGRAM_API_ID` | MTProto API ID |
| `TELEGRAM_API_HASH` | MTProto API hash |
| `TELEGRAM_BOT_TOKEN` | Bot token from BotFather |
| `TELEGRAM_CHAT_ID` | Your personal chat ID |
| `OPENAI_API_KEY` | OpenAI API key |
| `TELEGRAM_SESSION_B64` | Base64-encoded `.session` file |

To encode your session file:

```bash
base64 jobpulse_session.session
```

Paste the output as the `TELEGRAM_SESSION_B64` secret. After each run, `data/jobs.csv` is automatically committed back to the repo for cross-run deduplication.

## Storage Architecture

JobPulse uses two independent layers — a failure in one never blocks the other.

**CSV (`data/jobs.csv`)** — committed to the repo after every run. This is the deduplication source of truth on GitHub Actions, where the SQLite database is wiped between runs. Only CSV-new jobs with a score > 7 trigger alerts.

**SQLite (`data/jobs.db`)** — gitignored, persistent locally. Reserved for future analytics: keyword trends, fit score tuning, CV recommendations.

Dedup key for both layers: `job_link` (same job posted in multiple groups = one alert).
