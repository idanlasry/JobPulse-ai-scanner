# %%
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")

GROUPS_FILE = Path(__file__).parent.parent / "config" / "groups.txt"
OUTPUT_FILE = Path(__file__).parent.parent / "data" / "raw_dump.json"


# %%
def load_groups() -> list[str | int]:
    groups = []
    for line in GROUPS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            groups.append(int(line))
        except ValueError:
            groups.append(line)
    return groups


# %%
async def fetch_recent_messages(
    client: TelegramClient,
    group: str | int,
    limit: int = 5,  # messages per group — change here or pass from main()
) -> list[dict]:
    messages = []
    try:
        entity = await client.get_entity(group)

        async for message in client.iter_messages(entity, limit=limit):
            if not message.text:
                continue
            messages.append(
                {
                    "text": message.text,
                    "timestamp": message.date.isoformat(),
                    "sender_id": message.sender_id,
                    "group": str(group),
                }
            )
    except Exception as e:
        print(f"[listener] Failed to fetch from {group}: {e}")
    return messages


# %%
async def main(limit: int = 5) -> None:  # limit controlled from here or from main.py
    groups = load_groups()
    all_messages: list[dict] = []

    async with TelegramClient("jobpulse_session", API_ID, API_HASH) as client:
        for group in groups:
            print(f"[listener] Fetching from {group}...")
            msgs = await fetch_recent_messages(
                client, group, limit=limit
            )  # passes limit down
            print(f"[listener]   → {len(msgs)} messages")
            all_messages.extend(msgs)
            await asyncio.sleep(2)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(all_messages, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[listener] Saved {len(all_messages)} messages to {OUTPUT_FILE}")


# %%
if __name__ == "__main__":
    asyncio.run(main())  # to change limit: asyncio.run(main(limit=50))
