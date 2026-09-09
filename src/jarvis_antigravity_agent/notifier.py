import json
import logging
import os
import sys
import urllib.error
import urllib.request
from typing import Any

from jarvis_antigravity_agent.config import get_settings
from jarvis_antigravity_agent.constants import Constants
from jarvis_antigravity_agent.messages import Messages
from jarvis_antigravity_agent.utils import split_message

logger = logging.getLogger(Constants.LOGGER_NAME)


def load_notifier_config() -> dict[str, Any]:
    """Retrieve notifier-relevant configuration via Settings."""
    try:
        settings = get_settings()
        return {
            "bot_token": settings.telegram.bot_token,
            "default_chat_id": settings.telegram.default_chat_id,
            "request_timeout": settings.telegram.request_timeout,
        }
    except Exception as e:
        logger.debug("Failed to load notifier config: %s", e)
        return {}


def send_telegram_chunk(
    bot_token: str,
    chat_id: int | str,
    chunk: str,
    timeout: float | None = None,
) -> bool:
    settings = get_settings()
    req_timeout = timeout if timeout is not None else settings.telegram.request_timeout
    url = settings.telegram.api_send_url.format(bot_token=bot_token)

    if not url.startswith(("http:", "https:")):
        raise ValueError(f"Unsupported URL scheme in {url}")

    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": chunk,
        "parse_mode": "Markdown",
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(  # noqa: S310
        url, data=data, headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=req_timeout) as resp:  # noqa: S310
            ok: bool = resp.status == 200
            return ok
    except urllib.error.HTTPError:
        payload.pop("parse_mode", None)
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(  # noqa: S310
            url, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=req_timeout) as resp:  # noqa: S310
                ok = resp.status == 200
                return ok
        except Exception as e:
            print(Messages.NOTIFIER_SEND_ERROR.format(error=e), file=sys.stderr)
            return False
    except Exception as e:
        print(Messages.NOTIFIER_CONN_ERROR.format(error=e), file=sys.stderr)
        return False


def main() -> None:
    settings = get_settings()
    bot_token: str | None = settings.telegram.bot_token or os.environ.get(
        "TELEGRAM_BOT_TOKEN"
    )
    chat_id: int | str | None = settings.telegram.default_chat_id or os.environ.get(
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
        print(Messages.NOTIFIER_MISSING_CHAT_ID, file=sys.stderr)
        sys.exit(1)

    chunks = split_message(
        text.strip(), max_length=settings.telegram.max_message_length
    )
    all_ok = all(
        send_telegram_chunk(
            bot_token, chat_id, chunk, timeout=settings.telegram.request_timeout
        )
        for chunk in chunks
    )
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
