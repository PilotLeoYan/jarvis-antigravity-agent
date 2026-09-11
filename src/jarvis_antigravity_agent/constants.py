import os
from typing import Any


class Constants:
    MAX_MESSAGE_LENGTH = 4000
    TYPING_WAIT_TIMEOUT = 4.5
    WHISPER_MODEL_SIZE = "base"
    WHISPER_DEVICE = "cpu"
    WHISPER_COMPUTE_TYPE = "int8"
    WHISPER_BEAM_SIZE = 5
    AGY_PROCESS_TIMEOUT = 360.0
    AGY_COMMUNICATE_TIMEOUT = 10.0
    EDIT_THROTTLE_SECONDS = 1.2
    MAX_STATUS_ITEMS = 12
    MAX_COMPLETED_ITEMS = 15
    RESTART_RETURN_CODES = frozenset({-15, -9, 143, 137})
    TELEGRAM_API_SEND_URL = "https://api.telegram.org/bot{bot_token}/sendMessage"
    TELEGRAM_REQ_TIMEOUT = 20
    AGY_OUTPUT_FORMAT = "stream-json"
    AGY_CONTINUE_FLAG = "-c"
    AGY_PROMPT_FLAG = "-p"
    AGY_MODEL_FLAG = "--model"
    AGY_DEFAULT_MODEL: str | None = None
    AGY_EFFORT_FLAG = "--effort"
    AGY_DEFAULT_EFFORT: str | None = None
    AGY_OUTPUT_FORMAT_FLAG = "--output-format"
    AGY_DEFAULT_FLAGS = ["--dangerously-skip-permissions"]
    AGY_LOCAL_BIN = os.path.expanduser("~/.local/bin")
    AGY_FALLBACK_BIN = os.path.expanduser("~/.local/bin/agy")
    PATH_EXTRA = "/usr/local/bin:/usr/bin:/bin"
    VOICE_TEMP_SUFFIX = ".oga"

    BASE_DIR = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    CONFIG_PATH = (
        os.environ.get("JARVIS_CONFIG_PATH")
        or os.environ.get("AGY_TELEGRAM_CONFIG")
        or os.path.join(BASE_DIR, "config.yaml")
    )
    STATE_PATH = os.path.join(BASE_DIR, "state.json")
    LOGGER_NAME = "jarvis-bridge"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    PLACEHOLDER_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"  # noqa: S105
    DEFAULT_WORKING_DIR = os.path.expanduser("~")
    STATE_KEY_CONTINUE = "continue_session"
    STATE_KEY_MODEL = "active_model"
    STATE_KEY_EFFORT = "active_effort"
    EMPTY_RESPONSE_PLACEHOLDER = "(Empty response)"

    VALID_EFFORT_LEVELS: tuple[str, ...] = ("low", "medium", "high")
    GEMINI_MODELS: list[dict[str, Any]] = [
        {
            "id": "gemini-3.8-flash",
            "name": "Gemini 3.8 Flash",
            "description": "Fast, multimodal, frontier intelligence",
            "efforts": ["high", "medium", "low"],
            "default_effort": "high",
        },
        {
            "id": "gemini-3.7-flash",
            "name": "Gemini 3.7 Flash",
            "description": "Hybrid reasoning & low-latency execution",
            "efforts": ["high", "medium", "low"],
            "default_effort": "high",
        },
        {
            "id": "gemini-3.6-flash",
            "name": "Gemini 3.6 Flash",
            "description": "Reliable high-throughput daily coding & tools",
            "efforts": ["high", "medium", "low"],
            "default_effort": "high",
        },
        {
            "id": "gemini-3.1-pro",
            "name": "Gemini 3.1 Pro",
            "description": "Deep architectural reasoning & complex tasks",
            "efforts": ["high", "low"],
            "default_effort": "high",
        },
    ]
