#!/usr/bin/env python3
"""
CLI Notifier for Telegram
Enables cron jobs, CI/CD pipelines, and shell scripts to push notifications to Telegram.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.environ.get("AGY_TELEGRAM_CONFIG", os.path.join(BASE_DIR, "config.json"))


def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def split_message(text: str, max_length: int = 4000) -> list[str]:
    if len(text) <= max_length:
        return [text]
    chunks = []
    lines = text.split("\n")
    current_chunk = ""
    for line in lines:
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            if len(line) > max_length:
                for i in range(0, len(line), max_length):
                    chunks.append(line[i:i + max_length])
            else:
                current_chunk = line
        else:
            current_chunk = (current_chunk + "\n" + line) if current_chunk else line
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def send_telegram_chunk(bot_token: str, chat_id: int, chunk: str) -> bool:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": chunk,
        "parse_mode": "Markdown"
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status == 200
    except urllib.error.HTTPError:
        # Fallback to plain text on Markdown syntax failure
        payload.pop("parse_mode", None)
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.status == 200
        except Exception as e:
            print(f"Error sending message to Telegram: {e}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"Error connecting to Telegram: {e}", file=sys.stderr)
        return False


def main():
    config = load_config()
    bot_token = config.get("bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = config.get("default_chat_id") or os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token:
        print("Error: Missing bot_token in config.json or TELEGRAM_BOT_TOKEN environment variable.", file=sys.stderr)
        sys.exit(1)

    args = sys.argv[1:]
    if "--chat-id" in args:
        idx = args.index("--chat-id")
        if idx + 1 < len(args):
            chat_id = args[idx + 1]
            args.pop(idx + 1)
            args.pop(idx)

    text = ""
    if args:
        text = " ".join(args)
    elif not sys.stdin.isatty():
        text = sys.stdin.read()

    if not text.strip():
        print("Usage: send_message.py [--chat-id <id>] <message> OR echo <message> | send_message.py", file=sys.stderr)
        sys.exit(1)

    chunks = split_message(text.strip())
    all_ok = True
    for chunk in chunks:
        if not send_telegram_chunk(bot_token, chat_id, chunk):
            all_ok = False

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
