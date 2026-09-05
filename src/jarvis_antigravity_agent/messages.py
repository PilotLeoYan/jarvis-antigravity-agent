class Messages:
    STARTING_TASK = "\u23f3 *Starting task...*"
    TASK_PROGRESS = "\u23f3 *Task progress:*\n"
    TIMEOUT_EXCEEDED_SAFETY = (
        "\u23f1\ufe0f *Timeout exceeded ({timeout}s).* Task aborted for safety."
    )
    TIMEOUT_EXCEEDED = "\u23f1\ufe0f *Timeout exceeded ({timeout}s).* Task aborted."
    COMPLETED_STEPS = "\u2705 *Completed steps:*\n"
    TASK_COMPLETED = "\u2705 *Task completed.*"
    TASK_COMPLETED_NO_TEXT = "\u2705 Task completed with no text output."
    RELOADING_UPDATES = (
        "\U0001f504 *Reloading Telegram Bridge...*\n"
        "Service is restarting to apply updates. Ready in a moment."
    )
    RELOADING_GENERAL = (
        "\U0001f504 *Reloading Telegram Bridge...*\n"
        "Service is restarting. Ready in a moment."
    )
    EXECUTION_ERROR = "\u26a0\ufe0f *AGY Execution Error (Code {code})*:\n"
    UNEXPECTED_ERROR = "\u274c Unexpected error: {error}"
    UNAUTHORIZED_ACCESS = "\u26d4 Unauthorized access."
    TASK_RUNNING_WARNING = (
        "\u23f3 An AGY task is already running. Please wait or use `/cancel` to abort."
    )
    PROCESSING_VOICE = "\U0001f399\ufe0f *Processing voice note...*"
    NO_CLEAR_SPEECH = "\u26a0\ufe0f No clear speech detected in audio file."
    TRANSCRIPTION_RESULT = (
        "\U0001f5e3\ufe0f *Transcription:* _{transcription}_\n\n"
        "_Processing with Jarvis / AGY..._"
    )
    AUDIO_PROCESSING_ERROR = "\u274c Audio processing error: {error}"
    HELP_TEXT = (
        "\U0001f916 *Jarvis \u2014 Antigravity Assistant*\n\n"
        "Autonomous assistant powered by **Google Antigravity CLI (`agy`)**.]\n\n"
        "\U0001f399\ufe0f *Voice Notes & Audio:*\n"
        "Send audio notes directly. "
        "Transcribed locally via Whisper (0 token cost, 100% private).\n\n"
        "\U0001f4cb *Commands:*\n"
        "\u2022 `/new` or `/nuevo` \u2014 Reset conversational context.\n"
        "\u2022 `/status` or `/estado` \u2014 "
        "Inspect system load, STT status, and current session.\n"
        "\u2022 `/cancel` or `/cancelar` \u2014 Abort currently executing task.\n"
        "\u2022 `/help` or `/ayuda` \u2014 Display this operational guide.\n\n"
        "Send a message or voice note to begin."
    )
    CONTEXT_RESET = (
        "\U0001f504 *Conversation context reset*\n\n"
        "Next message or voice note will begin a fresh session with Antigravity."
    )
    SESSION_ACTIVE = "\U0001f7e2 Active (context preserved)"
    SESSION_READY = "\u26aa Ready for clean session"
    STT_LOADED = "\U0001f7e2 Loaded in memory"
    STT_READY = "\u26aa Ready to initialize ({model} / {compute_type} {device})"
    SYSTEM_STATUS = (
        "\U0001f4ca *System & Bridge Status*\n\n"
        "\u2022 *AGY Status*: {agy_status}\n"
        "\u2022 *Session*: {session_status}\n"
        "\u2022 *Speech-to-Text*: {stt_status}\n"
        "\u2022 *Working Directory*: `{working_dir}`\n"
        "\u2022 *System Load*: `{load1}` (1m), `{load5}` (5m)\n"
        "\u2022 *Disk Usage*: `{disk_pct}`"
    )
    TASK_PROCESSING = "\U0001f7e1 Processing task..."
    IDLE_READY = "\U0001f7e2 Idle / Ready"
    TASK_CANCELLED = "\U0001f6d1 *Task cancelled.*"
    ERROR_CANCELLING = "\u26a0\ufe0f Error cancelling task: {error}"
    NO_ACTIVE_TASK = "\u2139\ufe0f No active task is currently running."
    MISSING_BOT_TOKEN = (
        "Please configure a valid Telegram Bot Token "
        "in config.json or TELEGRAM_BOT_TOKEN."
    )

    NOTIFIER_MISSING_TOKEN = (
        "Error: Missing bot_token in config.json or TELEGRAM_BOT_TOKEN "
        "environment variable."
    )
    NOTIFIER_USAGE = (
        "Usage: send_message.py [--chat-id <id>] <message> "
        "OR echo <message> | send_message.py"
    )
    NOTIFIER_SEND_ERROR = "Error sending message to Telegram: {error}"
    NOTIFIER_CONN_ERROR = "Error connecting to Telegram: {error}"

    WHISPER_INIT = (
        "Initializing local faster-whisper ({model}, {device}, {compute_type})..."
    )
    WHISPER_READY = "faster-whisper model ready."
    AGY_EXECUTING = "Executing AGY (continue={continue_flag}): {prompt}..."
    AGY_EXITED = "AGY exited with code {code} in {elapsed:.2f}s"
    VOICE_TRANSCRIBED = "Voice note transcribed [{lang}]: {transcription}"
    AUDIO_ERROR = "Error transcribing audio"
    AGY_UNEXPECTED_ERROR = "Unexpected error executing AGY"
    BRIDGE_STARTING = "Jarvis Antigravity Bridge starting polling..."

    TOOL_RUN_COMMAND = "+ \u2699\ufe0f `{cmd}`"
    TOOL_WRITE_FILE = "+ \U0001f4dd Modifying: `{filename}`"
    TOOL_READ_FILE = "+ \U0001f4d6 Reading: `{filename}`"
    TOOL_GREP = "+ \U0001f50d Searching code: `{query}`"
    TOOL_WEB_SEARCH = "+ \U0001f310 Searching web: `{query}`"
    TOOL_SUBAGENT = "+ \U0001f916 Invoking specialized subagent"
    TOOL_GENERIC = "+ \U0001f527 `{name}`"

    CONFIG_LOAD_ERROR = "Failed to load config.json: {error}"
    STATE_SAVE_ERROR = "Error saving state: {error}"
