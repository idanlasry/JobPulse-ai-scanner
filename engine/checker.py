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
    return hashlib.sha256(url.encode()).hexdigest()


def _normalize(url: str) -> str:
    return url.rstrip("/").lower()


def _load_known_data() -> tuple[set[str], set[str], bool]:
    if _supabase is None:
        logging.warning("[checker] Supabase client not initialised — skipping dedup gate")
        return set(), set(), False
    try:
        known_hashes: set[str] = set()
        known_links: set[str] = set()
        page = 0
        page_size = 1000
        while True:
            response = (
                _supabase.table("jobs")
                .select("job_hash,job_link")
                .range(page * page_size, (page + 1) * page_size - 1)
                .execute()
            )
            rows = response.data or []
            for row in rows:
                if row.get("job_hash"):
                    known_hashes.add(row["job_hash"])
                if row.get("job_link"):
                    known_links.add(_normalize(row["job_link"]))
            if len(rows) < page_size:
                break
            page += 1
        logging.info("[checker] Loaded %d known hashes from Supabase", len(known_hashes))
        return known_hashes, known_links, True
    except Exception as e:
        logging.error("[checker] Failed to load data from Supabase: %s", e)
        return set(), set(), False


# %%
def filter_new_messages(messages: list[dict]) -> tuple[list[dict], int, int, bool]:
    known_hashes, known_links, checker_available = _load_known_data()

    fresh: list[dict] = []
    no_link_count = 0
    duplicate_count = 0

    for msg in messages:
        raw_text: str = msg.get("text", "")
        http_urls = [u for u in _extractor.gen_urls(raw_text) if u.startswith("http")]

        if not http_urls:
            no_link_count += 1
            continue

        is_duplicate = checker_available and any(
            _hash(u) in known_hashes or _normalize(u) in known_links
            for u in http_urls
        )

        if is_duplicate:
            duplicate_count += 1
        else:
            fresh.append(msg)

    return fresh, no_link_count, duplicate_count, checker_available
