# %%
import hashlib
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from supabase import create_client
from urlextract import URLExtract

load_dotenv()

_SUPABASE_URL = os.getenv("SUPABASE_URL", "")
_SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
_supabase = create_client(_SUPABASE_URL, _SUPABASE_KEY) if _SUPABASE_URL and _SUPABASE_KEY else None

_extractor = URLExtract()


# %%
def _hash(url: str) -> str:
    # Must mirror database.py _hash() exactly — same algorithm, same encoding
    return hashlib.sha256(url.encode()).hexdigest()


def _load_known_hashes() -> set[str]:
    """Fetch all job_hash values from Supabase jobs table.

    Returns an empty set if Supabase is unavailable — causing all messages to
    pass through to the LLM rather than risking false duplicate skips.
    """
    if _supabase is None:
        logging.warning("[checker] Supabase client not initialised — skipping dedup gate")
        return set()
    try:
        # Supabase REST pagination: max 1000 rows per request
        # Fetch in pages until we have all hashes
        known: set[str] = set()
        page = 0
        page_size = 1000
        while True:
            response = (
                _supabase.table("jobs")
                .select("job_hash")
                .range(page * page_size, (page + 1) * page_size - 1)
                .execute()
            )
            rows = response.data or []
            for row in rows:
                if row.get("job_hash"):
                    known.add(row["job_hash"])
            if len(rows) < page_size:
                break  # last page
            page += 1
        print(f"[checker] Loaded {len(known)} known hashes from Supabase")
        return known
    except Exception as e:
        logging.error("[checker] Failed to load hashes from Supabase: %s", e)
        return set()  # fail open — let everything through to the LLM


# %%
def filter_new_messages(messages: list[dict]) -> tuple[list[dict], int]:
    """Remove messages whose job link already exists in Supabase.

    Extracts all http-prefixed URLs from each message's raw text, hashes each one,
    and checks against the known hashes from Supabase. A message is considered a
    duplicate if ANY of its extracted URLs matches a stored hash.

    Returns:
        (fresh_messages, skipped_count)
        fresh_messages — messages that passed the gate (no URL matched a known hash)
        skipped_count  — number of messages dropped as duplicates
    """
    known_hashes = _load_known_hashes()

    if not known_hashes:
        # Supabase unavailable or empty DB (first run) — pass everything through
        return messages, 0

    fresh: list[dict] = []
    skipped = 0

    for msg in messages:
        raw_text: str = msg.get("text", "")
        http_urls = [u for u in _extractor.gen_urls(raw_text) if u.startswith("http")]

        if not http_urls:
            # No extractable link — pass through to the LLM (brain handles non-job messages)
            fresh.append(msg)
            continue

        is_duplicate = any(_hash(u) in known_hashes for u in http_urls)

        if is_duplicate:
            skipped += 1
            print(f"[checker] Duplicate — skipping: {http_urls[0][:80]}")
        else:
            fresh.append(msg)

    return fresh, skipped
