# JobPulse — AI-Powered Job Scanner
**Stop scrolling. Start getting alerts.**

Job hunting is noise. Thousands of posts across Telegram groups. 95% irrelevant posts. Manual filtering = hours per week wasted.

JobPulse solves this: an autonomous pipeline built with Claude Code that monitors job groups 24/7, scores every post against **your profile** using GPT-4o mini, and alerts you only when there's a strong match. Fully automated on GitHub Actions. Zero local machine needed.

The scoring engine is **fully profile-driven** — all the hard exclusions, calibration rules, and worked examples live in [config/portfolio.txt](config/portfolio.txt). Fork the repo, swap in your own profile, and you've got a personalised job scanner. No Python edits required.

## What It Does

- Monitors 5 Telegram job groups in real-time
- Extracts job data using Telethon (MTProto API)
- Scores each job against your portfolio (1–10 confidence scale)
- Sends Telegram alerts **only for matches scoring > 7** (reduces noise)
- Stores all jobs in dual-layer storage (Supabase as primary DB, CSV as cross-run backup)
- **Runs 3× daily on weekdays — fully autonomous, zero babysitting**

## The Pipeline
```
Telegram groups (Telethon listener)
    ↓
Raw job posts (raw_dump.json)
    ↓
GPT-4o mini scoring (brain.py)
    ↓
Scored jobs (scored_dump.json)
    ↓
Dual storage (Supabase + CSV backup)
    ↓
Telegram Bot alerts (notify.py) → only if score > 7
```

## Tech Stack

| Layer | Tool |
|---|---|
| Ingestion | Python + Telethon (MTProto) |
| Scoring | OpenAI GPT-4o mini |
| Data Modeling | Pydantic v2 (structured outputs) |
| Primary Storage | Supabase (PostgreSQL) — cloud DB, persists across all runs |
| Backup Storage | CSV (`data/jobs.csv`) — committed to repo, cross-run dedup |
| Alerts | Telegram Bot API |
| Scheduling | GitHub Actions (Mon–Fri, 3× daily) |
| Package Manager | uv (Python 3.13) |

## Key Design Decisions

**Why dual storage?**
- **Supabase (primary):** Cloud PostgreSQL — persists across all runs, queryable for analytics and trends.
- **CSV (backup):** GitHub Actions runners are ephemeral. Committing to repo ensures dedup survives between runs even if Supabase is unavailable.

**Why dedup by `job_link`?**
- Same job posted across multiple groups = one alert (reduces noise, focuses attention)

**Why score threshold at 7?**
- High signal-to-noise ratio. Only actionable matches get alerts.

**Why autonomous?**
- GitHub Actions handles scheduling. No need to keep a local machine running.

## What This Taught Me

**System Design**
- Architecting dual-layer storage for both immediate needs (GitHub Actions ephemeral runners) and future scaling (analytics, multi-device sync)
- Trade-offs: simplicity now vs. flexibility later

**API Integration**
- Telethon (user-level MTProto), OpenAI (LLM scoring), Telegram Bot (alerts) — all async
- Structured outputs (Pydantic) keep LLM responses clean and consistent

**CI/CD & Automation**
- GitHub Actions scheduling, environment secrets, automated file commits
- Graceful degradation: one failed group or bad LLM response never crashes the pipeline

**AI as Teammate**
- Prompt engineering for job scoring (clarity, consistency, structure)
- Critical thinking on LLM outputs: validating, questioning, improving

## Project Structure
```
├── engine/
│   ├── listener.py      # Fetch messages from Telegram groups via Telethon
│   ├── brain.py         # Score jobs with GPT-4o mini
│   ├── database.py      # Dual storage: Supabase (primary) + CSV (backup), dedup by job_link
│   ├── notify.py        # Send alerts via Telegram Bot
│   └── models.py        # Pydantic schemas: JobOpportunity, ScoredJob
├── config/
│   ├── portfolio.txt              # Your profile — LLM scoring context (prose, edited by you)
│   ├── portfolio.template.txt     # Starting template for a new profile
│   ├── scoring_overrides.py       # Code-level guards for known LLM failure patterns (optional)
│   ├── scoring_overrides.template.py
│   └── groups.txt                 # Telegram groups to monitor
├── data/
│   ├── jobs.csv         # Cross-run job backup (committed)
│   └── last_seen.csv    # Checkpoint file — group_id → last_seen_ts (committed)
├── main.py              # Pipeline orchestrator
├── notify_all.py        # One-shot: send alerts for all high-fit jobs in DB
├── DB_search.py         # Dev utility: print high-fit jobs to terminal
├── connection_test.py   # Dev utility: test Telethon and bot connection
└── .github/workflows/
    └── run_scanner.yml  # Scheduled automation
```

## Setup

### 1. Clone and install
```bash
git clone https://github.com/idanlasry/jobs-ai-scanner
cd jobs-ai-scanner
uv sync
```

### 2. Environment variables

Create `.env`:
```env
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
OPENAI_API_KEY=
SUPABASE_URL=
SUPABASE_KEY=
```

- `TELEGRAM_API_ID/HASH`: [my.telegram.org](https://my.telegram.org)
- `TELEGRAM_BOT_TOKEN`: [@BotFather](https://t.me/botfather)
- `OPENAI_API_KEY`: [OpenAI Console](https://platform.openai.com)
- `SUPABASE_URL/KEY`: [Supabase Dashboard](https://supabase.com)

### 3. Configure

- `config/groups.txt` — Telegram groups to monitor (one per line)
- `config/portfolio.txt` — your skills, hard exclusions, calibration rules, scored examples (see **Customize Your Profile** below)

### 4. Customize Your Profile

All scoring personalisation lives in two files. The Python scoring engine ([engine/brain.py](engine/brain.py)) is generic and untouched.

| File | What it holds | When you need it |
|---|---|---|
| [config/portfolio.txt](config/portfolio.txt) | Plain-prose profile: role target, seniority, location, skills, hard exclusions, calibration tables, scored examples | **Always.** This is the LLM's source of truth. |
| [config/scoring_overrides.py](config/scoring_overrides.py) | Code-level guards that override the LLM's `fit_score` post-hoc when specific conditions match (e.g. title + tech stack + low score) | **Only if** you observe a systematic LLM mis-scoring that prompt calibration in `portfolio.txt` cannot fix. |

**Start by copying the templates:**
```bash
cp config/portfolio.template.txt config/portfolio.txt
cp config/scoring_overrides.template.py config/scoring_overrides.py
```

**Fill in `portfolio.txt` section by section:**

1. **ROLE TARGET** — primary title + acceptable variants + NOT-relevant titles
2. **SENIORITY** — target band (junior/mid/senior) + which levels are off-limits
3. **LOCATION & AVAILABILITY** — preferred cities, remote/hybrid stance, what counts as a hard exclude
4. **TECHNICAL SKILLS** — primary stack (strong match → high score), secondary stack (partial match), methodologies
5. **EDUCATION / PROJECT HIGHLIGHTS / DOMAIN PREFERENCES** — context for the LLM
6. **HARD EXCLUSIONS** — 2–4 unconditional triggers that drop a job to score 1–2. *Most important section.* Keep it short — every trigger you add is one the LLM will fire on aggressively.
7. **NOT HARD EXCLUSIONS** — signals that LOOK like exclusions but should only modify the score (e.g. "5+ years required" → penalise, don't exclude). Without this section, the LLM tends to over-penalise.
8. **CALIBRATION RULES** — score bands per seniority/location/role-type. Be explicit: ranges like `Junior, preferred city, full stack → 9–10`.
9. **SCORED EXAMPLES** — 3–5 worked examples that anchor the 1–10 scale. Span your full range (perfect match, hard exclude, borderline, "looks bad but actually OK"). The LLM uses these as ground truth.

**About `scoring_overrides.py`:**

Start with `RULES = []` — empty. Only add rules when you spot a pattern the LLM gets wrong repeatedly. Example: GPT-4o mini systematically under-scores "Data Scientist" roles even when the actual responsibilities are LLM/Prompt Engineering work. A code-level override floors those at `fit_score = 5`.

Each rule lists conditions (substrings in title, items in tech stack, score thresholds, etc.) and an action (set `fit_score`, append to `fit_reasoning`). A malformed rule **crashes the pipeline at startup with a clear error** — silent failures are not possible.

See [config/scoring_overrides.template.py](config/scoring_overrides.template.py) for the full schema and a commented example.

### 5. Authenticate (first run only)
```bash
uv run python engine/listener.py
```

Creates `jobpulse_session.session` after phone verification.

### 6. Run locally
```bash
uv run python main.py
```

## Deploy to GitHub Actions

The pipeline runs automatically **Mon–Fri at 08:00, 14:00, 18:00 Israel time.**

**Add these GitHub Secrets** (Settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `TELEGRAM_API_ID` | From my.telegram.org |
| `TELEGRAM_API_HASH` | From my.telegram.org |
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `TELEGRAM_CHAT_ID` | Your personal chat ID |
| `OPENAI_API_KEY` | OpenAI API key |
| `TELEGRAM_SESSION_B64` | Base64-encoded `jobpulse_session.session` |
| `SUPABASE_URL` | From Supabase project settings |
| `SUPABASE_KEY` | From Supabase project settings (anon key) |

To encode your session:
```bash
base64 jobpulse_session.session
```

After each run, `data/jobs.csv` auto-commits to the repo for cross-run deduplication.

## Why Profile-Driven?

The original version of JobPulse had a single 200-line prompt in [engine/brain.py](engine/brain.py) that mixed generic scoring framework (1–10 scale, JSON schema, reflection rules) with one specific candidate's calibration (Israel-only, Data Analyst, junior–mid, Power BI/SQL/Python). Anyone forking the repo had to read Python and re-tune the prompt before getting useful scores.

The refactor splits these cleanly: `engine/brain.py` holds the **generic scoring engine** — JSON contract, reflection rules, confidence scoring rubric, the override application logic. [config/portfolio.txt](config/portfolio.txt) holds **everything personal** — hard exclusions, calibration tables, scored examples, role-type rules. [config/scoring_overrides.py](config/scoring_overrides.py) is the escape hatch for model-level failures that prompt calibration cannot fix.

You can fork JobPulse for a backend engineer, a marketing lead, or a UX researcher by editing only the two `config/` files. The Python stays the same.

## Future Roadmap

- ⏳ Analyze job trends: in-demand skills, salary ranges, hiring patterns (query Supabase)
- ⏳ Wire `alerted` flag — mark rows in Supabase after a successful alert is sent
- ⏳ Multi-source ingestion: LinkedIn RSS, WhatsApp groups, other job boards

## Current Status

✅ **Live and running** — deployed to GitHub Actions, 3× daily on weekdays
✅ All stages complete: ingestion → scoring → dual storage (Supabase + CSV) → alerts → automation
✅ Checkpoint-based listening — skips already-processed messages per group
```

---

