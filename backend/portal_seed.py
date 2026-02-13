"""portal_seed.py - Convert existing chat log files into portal-compatible JSON.

Reads logs/chat_*.json files and produces a single JSON file that can be
imported into the Chat Log Portal via its Import feature (or pasted into
the browser console to seed localStorage directly).

Usage:
    python portal_seed.py                  # writes portal_seed_data.json
    python portal_seed.py --out seed.json  # custom output path
"""
import argparse
import json
import os
import sys
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")


def read_log_files(log_dir: str) -> list[dict]:
    """Read all chat_*.json log files and return portal-formatted conversations."""
    conversations = []

    if not os.path.isdir(log_dir):
        print(f"Log directory not found: {log_dir}")
        return conversations

    for filename in sorted(os.listdir(log_dir)):
        if not filename.startswith("chat_") or not filename.endswith(".json"):
            continue

        filepath = os.path.join(log_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Skipping {filename}: {e}")
            continue

        if not entries:
            continue

        session_id = filename[len("chat_"):-len(".json")]

        messages = []
        for entry in entries:
            ts = entry.get("timestamp", "")
            if entry.get("user"):
                messages.append({
                    "id": f"msg-{len(messages)+1}",
                    "sender": "user",
                    "text": entry["user"],
                    "timestamp": ts,
                })
            if entry.get("bot"):
                messages.append({
                    "id": f"msg-{len(messages)+1}",
                    "sender": "bot",
                    "text": entry["bot"],
                    "timestamp": ts,
                })

        if not messages:
            continue

        conversations.append({
            "id": session_id,
            "started": entries[0].get("timestamp", ""),
            "lastMessage": entries[-1].get("timestamp", ""),
            "messageCount": len(messages),
            "messages": messages,
            "source": "log_import",
        })

    # Sort newest-first
    conversations.sort(key=lambda c: c.get("lastMessage", ""), reverse=True)
    return conversations


def main():
    parser = argparse.ArgumentParser(description="Convert chat logs to portal seed JSON")
    parser.add_argument(
        "--logs",
        default=LOG_DIR,
        help=f"Path to logs directory (default: {LOG_DIR})",
    )
    parser.add_argument(
        "--out",
        default="portal_seed_data.json",
        help="Output file path (default: portal_seed_data.json)",
    )
    args = parser.parse_args()

    conversations = read_log_files(args.logs)

    if not conversations:
        print("No conversations found. Nothing to export.")
        sys.exit(0)

    output = {
        "exportedAt": datetime.now().isoformat(),
        "source": "portal_seed.py",
        "conversationCount": len(conversations),
        "conversations": conversations,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Exported {len(conversations)} conversations to {args.out}")
    total_msgs = sum(c["messageCount"] for c in conversations)
    print(f"Total messages: {total_msgs}")


if __name__ == "__main__":
    main()
