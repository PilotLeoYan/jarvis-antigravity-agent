import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

from jarvis_antigravity_agent.constants import Constants
from jarvis_antigravity_agent.messages import Messages
from jarvis_antigravity_agent.utils import split_message


def load_notifier_config() -> dict[str, Any]:
    if os.path.exists(Constants.CONFIG_PATH):
        try:
            with open(Constants.CONFIG_PATH, encoding="utf-8") as f:
                result: dict[str, Any] = json.load(f)
                return result
        except Exception:
            pass
    return {}


def send_telegram_chunk(bot_token: str, chat_id: int | str, chunk: str) -> bool:
    url = Constants.TELEGRAM_API_SEND_URL.format(bot_token=bot_token)
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": chunk,
        "parse_mode": "Markdown",
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(
            req, timeout=Constants.TELEGRAM_REQ_TIMEOUT
        ) as resp:
            ok: bool = resp.status == 200
            return ok
    except urllib.error.HTTPError:
        payload.pop("parse_mode", None)
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(
                req, timeout=Constants.TELEGRAM_REQ_TIMEOUT
            ) as resp:
                ok = resp.status == 200
                return ok
        except Exception as e:
            print(Messages.NOTIFIER_SEND_ERROR.format(error=e), file=sys.stderr)
            return False
    except Exception as e:
        print(Messages.NOTIFIER_CONN_ERROR.format(error=e), file=sys.stderr)
        return False


def main() -> None:
    config = load_notifier_config()
    bot_token: str | None = config.get("bot_token") or os.environ.get(
        "TELEGRAM_BOT_TOKEN"
    )
    chat_id: int | str | None = config.get("default_chat_id") or os.environ.get(
        "TELEGRAM_CHAT_ID"
    )

    if not bot_token:
        print(Messages.NOTIFIER_MISSING_TOKEN, file=sys.stderr)
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
        print(Messages.NOTIFIER_USAGE, file=sys.stderr)
        sys.exit(1)

    if chat_id is None:
        print(Messages.NOTIFIER_MISSING_TOKEN, file=sys.stderr)
        sys.exit(1)

    chunks = split_message(text.strip())
    all_ok = all(send_telegram_chunk(bot_token, chat_id, chunk) for chunk in chunks)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
