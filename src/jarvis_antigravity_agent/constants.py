import os


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
    AGY_OUTPUT_FORMAT_FLAG = "--output-format"
    AGY_DEFAULT_FLAGS = ["--dangerously-skip-permissions"]
    AGY_LOCAL_BIN = os.path.expanduser("~/.local/bin")
    AGY_FALLBACK_BIN = os.path.expanduser("~/.local/bin/agy")
    PATH_EXTRA = "/usr/local/bin:/usr/bin:/bin"
    VOICE_TEMP_SUFFIX = ".oga"

    BASE_DIR = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    CONFIG_PATH = os.environ.get(
        "AGY_TELEGRAM_CONFIG", os.path.join(BASE_DIR, "config.json")
    )
    STATE_PATH = os.path.join(BASE_DIR, "state.json")
    LOGGER_NAME = "jarvis-bridge"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    PLACEHOLDER_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"
    DEFAULT_WORKING_DIR = os.path.expanduser("~")
    STATE_KEY_CONTINUE = "continue_session"
    EMPTY_RESPONSE_PLACEHOLDER = "(Empty response)"
