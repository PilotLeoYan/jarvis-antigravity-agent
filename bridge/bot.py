#!/usr/bin/env python3
"""
Jarvis Antigravity Agent - Telegram Bridge Daemon
Features:
- Full bidirectional text communication with Google Antigravity CLI (agy)
- Offline Speech-to-Text for voice notes via faster-whisper (base / int8 CPU)
- Streaming JSON-RPC parsing (stream-json) with real-time progress steps
- Session continuity (-c) with clean reset commands (/new, /nuevo)
- Bilingual command handling (English & Spanish)
- Graceful restart detection and process termination
"""
import asyncio
import json
import logging
import os
import shutil
import signal
import sys
import tempfile
import time
from typing import Optional

from telegram import BotCommand, Update, constants
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ── Paths & Configuration ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.environ.get("AGY_TELEGRAM_CONFIG", os.path.join(BASE_DIR, "config.json"))
STATE_PATH = os.path.join(BASE_DIR, "state.json")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("jarvis-bridge")

current_process: Optional[asyncio.subprocess.Process] = None
process_lock = asyncio.Lock()
_whisper_model = None


def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config.json: {e}")
    return {}


def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"continue_session": False}


def save_state(state: dict):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving state: {e}")


config = load_config()
state = load_state()

BOT_TOKEN = config.get("bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN")
ALLOWED_USERS = set(str(u) for u in config.get("allowed_users", []))
WORKING_DIR = config.get("working_directory", os.path.expanduser("~"))
AGY_PATH = config.get("agy_path", shutil.which("agy") or os.path.expanduser("~/.local/bin/agy"))
DEFAULT_FLAGS = config.get("default_flags", ["--dangerously-skip-permissions"])


def is_authorized(user_id: int) -> bool:
    if not ALLOWED_USERS:
        return True
    return str(user_id) in ALLOWED_USERS


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


async def send_reply_chunks(update: Update, text: str):
    chunks = split_message(text.strip() or "(Empty response)")
    for chunk in chunks:
        try:
            await update.message.reply_text(chunk, parse_mode=constants.ParseMode.MARKDOWN)
        except Exception:
            # Fallback to plain text if Telegram Markdown parsing fails
            await update.message.reply_text(chunk)


async def keep_typing(chat_id: int, context: ContextTypes.DEFAULT_TYPE, stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=4.5)
        except asyncio.TimeoutError:
            pass


# ── Speech-to-Text (Local Whisper) ──────────────────────────────────
def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        logger.info("Initializing local faster-whisper (base, CPU, int8)...")
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        logger.info("faster-whisper model ready.")
    return _whisper_model


def transcribe_audio_file(file_path: str) -> tuple[str, str]:
    model = get_whisper_model()
    segments, info = model.transcribe(file_path, beam_size=5)
    transcription = " ".join(seg.text.strip() for seg in segments).strip()
    return transcription, info.language


# ── Execution Engine ────────────────────────────────────────────────
async def execute_agy_prompt(prompt: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_process, state

    async with process_lock:
        continue_flag = state.get("continue_session", False)

        cmd = [AGY_PATH] + DEFAULT_FLAGS + ["--output-format", "stream-json"]
        if continue_flag:
            cmd.append("-c")
        cmd.extend(["-p", prompt])

        env = os.environ.copy()
        user_local_bin = os.path.expanduser("~/.local/bin")
        env["PATH"] = f"{user_local_bin}:/usr/local/bin:/usr/bin:/bin:{env.get('PATH', '')}"

        stop_typing = asyncio.Event()
        typing_task = asyncio.create_task(keep_typing(update.effective_chat.id, context, stop_typing))

        status_msg = None
        try:
            status_msg = await update.message.reply_text("⏳ *Starting task...*", parse_mode=constants.ParseMode.MARKDOWN)
        except Exception:
            pass

        start_time = time.time()
        logger.info(f"Executing AGY (continue={continue_flag}): {prompt[:80]}...")

        try:
            current_process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=WORKING_DIR,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            raw_output_lines = []
            final_response_text = ""
            current_step_text = {}
            pending_agent_text = ""
            dispatched_intermediate_texts = []
            step_items = []
            last_edit_time = 0.0

            async def process_stream():
                nonlocal final_response_text, pending_agent_text, last_edit_time
                while True:
                    line = await current_process.stdout.readline()
                    if not line:
                        break
                    decoded = line.decode("utf-8", errors="replace").strip()
                    if not decoded:
                        continue
                    raw_output_lines.append(decoded)

                    try:
                        data = json.loads(decoded)
                        ev = data.get("event")

                        if ev == "step":
                            su = data.get("step_update", {})
                            s_idx = su.get("step_index")
                            stype = su.get("step_type")
                            sstate = su.get("state")

                            if stype == "agent_response":
                                delta = su.get("text_delta", "")
                                current_step_text[s_idx] = current_step_text.get(s_idx, "") + delta
                                if sstate == "DONE":
                                    pending_agent_text = current_step_text[s_idx].strip()

                            elif stype == "tool" and sstate == "ACTIVE":
                                if pending_agent_text:
                                    try:
                                        await update.message.reply_text(pending_agent_text, parse_mode=constants.ParseMode.MARKDOWN)
                                    except Exception:
                                        await update.message.reply_text(pending_agent_text)
                                    dispatched_intermediate_texts.append(pending_agent_text)
                                    pending_agent_text = ""

                                tname = su.get("tool_name", "")
                                params = su.get("tool_info", {}).get("parameters", {})

                                desc = ""
                                if tname == "run_command":
                                    cmd_line = params.get("CommandLine", "").strip().split("\n")[0]
                                    desc = f"+ ⚙️ `{cmd_line[:65]}`"
                                elif tname in ["write_to_file", "replace_file_content"]:
                                    tf = os.path.basename(params.get("TargetFile", "file"))
                                    desc = f"+ 📝 Modifying: `{tf}`"
                                elif tname == "view_file":
                                    tf = os.path.basename(params.get("AbsolutePath", "file"))
                                    desc = f"+ 📖 Reading: `{tf}`"
                                elif tname == "grep_search":
                                    q = params.get("Query", "")
                                    desc = f"+ 🔍 Searching code: `{q[:45]}`"
                                elif tname == "search_web":
                                    q = params.get("query", "")
                                    desc = f"+ 🌐 Searching web: `{q[:45]}`"
                                elif tname == "invoke_subagent":
                                    desc = "+ 🤖 Invoking specialized subagent"
                                else:
                                    desc = f"+ 🔧 `{tname}`"

                                if desc and desc not in step_items:
                                    step_items.append(desc)

                                now = time.time()
                                if status_msg and (now - last_edit_time >= 1.2):
                                    last_edit_time = now
                                    try:
                                        display_items = step_items[-12:] if len(step_items) > 12 else step_items
                                        status_text = "⏳ *Task progress:*
" + "\n".join(display_items)
                                        await status_msg.edit_text(status_text, parse_mode=constants.ParseMode.MARKDOWN)
                                    except Exception:
                                        pass

                        elif ev == "result":
                            res_obj = data.get("result", {})
                            final_response_text = res_obj.get("response", "").strip()

                    except json.JSONDecodeError:
                        pass

            try:
                await asyncio.wait_for(process_stream(), timeout=360.0)
                _, stderr = await asyncio.wait_for(current_process.communicate(), timeout=10.0)
            except asyncio.TimeoutError:
                if current_process and current_process.returncode is None:
                    current_process.kill()
                if status_msg:
                    try:
                        await status_msg.edit_text("⏱️ *Timeout exceeded (360s).* Task aborted for safety.", parse_mode=constants.ParseMode.MARKDOWN)
                    except Exception:
                        pass
                else:
                    await update.message.reply_text("⏱️ *Timeout exceeded (360s).* Task aborted.")
                return

            elapsed = time.time() - start_time
            logger.info(f"AGY exited with code {current_process.returncode} in {elapsed:.2f}s")

            if status_msg:
                try:
                    if step_items:
                        display_items = step_items[-15:] if len(step_items) > 15 else step_items
                        final_status = "✅ *Completed steps:*
" + "\n".join(display_items)
                    else:
                        final_status = "✅ *Task completed.*"
                    await status_msg.edit_text(final_status, parse_mode=constants.ParseMode.MARKDOWN)
                except Exception:
                    pass

            err_text = stderr.decode("utf-8", errors="replace").strip() if stderr else ""

            clean_final = final_response_text.strip() if final_response_text else ""
            for disp in dispatched_intermediate_texts:
                disp_clean = disp.strip()
                if not disp_clean:
                    continue
                if clean_final.startswith(disp_clean):
                    clean_final = clean_final[len(disp_clean):].lstrip()
                elif disp_clean in clean_final[:len(disp_clean) + 60]:
                    idx = clean_final.find(disp_clean)
                    if idx != -1 and idx < 60:
                        clean_final = clean_final[idx + len(disp_clean):].lstrip()

            output_text = clean_final or pending_agent_text
            if not output_text and raw_output_lines and not any(l.startswith("{") for l in raw_output_lines):
                output_text = "\n".join(raw_output_lines).strip()

            if current_process.returncode == 0:
                state["continue_session"] = True
                save_state(state)

                if output_text:
                    await send_reply_chunks(update, output_text)
                else:
                    await update.message.reply_text("✅ Task completed with no text output.")
            elif current_process.returncode in [-15, -9, 143, 137]:
                restart_notice = "🔄 *Reloading Telegram Bridge...*
Service is restarting to apply updates. Ready in a moment."
                if status_msg:
                    try:
                        await status_msg.edit_text(restart_notice, parse_mode=constants.ParseMode.MARKDOWN)
                    except Exception:
                        await update.message.reply_text(restart_notice, parse_mode=constants.ParseMode.MARKDOWN)
                else:
                    await update.message.reply_text(restart_notice, parse_mode=constants.ParseMode.MARKDOWN)
            else:
                error_msg = f"⚠️ *AGY Execution Error (Code {current_process.returncode})*:\n"
                if output_text:
                    error_msg += f"\n```\n{output_text}\n```"
                if err_text:
                    error_msg += f"\n```\n{err_text}\n```"
                await send_reply_chunks(update, error_msg)

        except asyncio.CancelledError:
            if current_process and current_process.returncode is None:
                try:
                    current_process.kill()
                except Exception:
                    pass
            restart_notice = "🔄 *Reloading Telegram Bridge...*
Service is restarting. Ready in a moment."
            if status_msg:
                try:
                    await status_msg.edit_text(restart_notice, parse_mode=constants.ParseMode.MARKDOWN)
                except Exception:
                    pass
            else:
                try:
                    await update.message.reply_text(restart_notice, parse_mode=constants.ParseMode.MARKDOWN)
                except Exception:
                    pass
            raise
        except Exception as e:
            logger.exception("Unexpected error executing AGY")
            await update.message.reply_text(f"❌ Unexpected error: {e}")
        finally:
            stop_typing.set()
            await typing_task
            current_process = None


# ── Handlers ────────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized access.")
        return

    prompt = update.message.text
    if not prompt or not prompt.strip():
        return

    if process_lock.locked():
        await update.message.reply_text(
            "⏳ An AGY task is already running. Please wait or use `/cancel` to abort.",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    await execute_agy_prompt(prompt, update, context)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized access.")
        return

    if process_lock.locked():
        await update.message.reply_text(
            "⏳ An AGY task is already running. Please wait or use `/cancel` to abort.",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    voice = update.message.voice or update.message.audio
    if not voice:
        return

    status_msg = await update.message.reply_text("🎙️ *Processing voice note...*", parse_mode=constants.ParseMode.MARKDOWN)

    with tempfile.NamedTemporaryFile(suffix=".oga", delete=False) as tf:
        temp_path = tf.name

    try:
        voice_file = await context.bot.get_file(voice.file_id)
        await voice_file.download_to_drive(custom_path=temp_path)

        transcription, lang = await asyncio.to_thread(transcribe_audio_file, temp_path)
        logger.info(f"Voice note transcribed [{lang}]: {transcription}")

        if not transcription or not transcription.strip():
            await status_msg.edit_text("⚠️ No clear speech detected in audio file.")
            return

        await status_msg.edit_text(
            f"🗣️ *Transcription:* "_{transcription}_"\n\n_Processing with Jarvis / AGY..._",
            parse_mode=constants.ParseMode.MARKDOWN
        )

        await execute_agy_prompt(transcription, update, context)

    except Exception as e:
        logger.exception("Error transcribing audio")
        await status_msg.edit_text(f"❌ Audio processing error: {e}")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


# ── Commands ────────────────────────────────────────────────────────
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized access.")
        return
    help_text = (
        "🤖 *Jarvis — Antigravity Assistant*\n\n"
        "Autonomous assistant powered by **Google Antigravity CLI (`agy`)**.\n\n"
        "🎙️ *Voice Notes & Audio:*\n"
        "Send audio notes directly. Transcribed locally via Whisper (0 token cost, 100% private).\n\n"
        "📋 *Commands:*\n"
        "• `/new` or `/nuevo` — Reset conversational context.\n"
        "• `/status` or `/estado` — Inspect system load, STT status, and current session.\n"
        "• `/cancel` or `/cancelar` — Abort currently executing task.\n"
        "• `/help` or `/ayuda` — Display this operational guide.\n\n"
        "Send a message or voice note to begin."
    )
    await update.message.reply_text(help_text, parse_mode=constants.ParseMode.MARKDOWN)


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    global state
    state["continue_session"] = False
    save_state(state)
    await update.message.reply_text(
        "🔄 *Conversation context reset*\n\nNext message or voice note will begin a fresh session with Antigravity.",
        parse_mode=constants.ParseMode.MARKDOWN
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    global current_process, state, _whisper_model
    is_busy = current_process is not None and current_process.returncode is None
    session_status = "🟢 Active (context preserved)" if state.get("continue_session") else "⚪ Ready for clean session"
    stt_status = "🟢 Loaded in memory" if _whisper_model is not None else "⚪ Ready to initialize (base / int8 CPU)"

    try:
        load1, load5, _ = os.getloadavg()
        total, used, free = shutil.disk_usage(WORKING_DIR)
        disk_pct = f"{(used / total) * 100:.1f}% ({used // (1024 ** 3)}GB / {total // (1024 ** 3)}GB)"
    except Exception:
        load1, load5, disk_pct = "N/A", "N/A", "N/A"

    msg = (
        "📊 *System & Bridge Status*\n\n"
        f"• *AGY Status*: {'🟡 Processing task...' if is_busy else '🟢 Idle / Ready'}\n"
        f"• *Session*: {session_status}\n"
        f"• *Speech-to-Text*: {stt_status}\n"
        f"• *Working Directory*: `{WORKING_DIR}`\n"
        f"• *System Load*: `{load1:.2f}` (1m), `{load5:.2f}` (5m)\n"
        f"• *Disk Usage*: `{disk_pct}`"
    )
    await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    global current_process
    if current_process and current_process.returncode is None:
        try:
            current_process.kill()
            await update.message.reply_text("🛑 *Task cancelled.*", parse_mode=constants.ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"⚠️ Error cancelling task: {e}")
    else:
        await update.message.reply_text("ℹ️ No active task is currently running.")


def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error("Please configure a valid Telegram Bot Token in config.json or TELEGRAM_BOT_TOKEN.")
        sys.exit(1)

    app = Application.builder().token(BOT_TOKEN).build()

    # Register commands (English and Spanish aliases)
    app.add_handler(CommandHandler(["start", "help", "ayuda"], help_command))
    app.add_handler(CommandHandler(["new", "nuevo"], new_command))
    app.add_handler(CommandHandler(["status", "estado"], status_command))
    app.add_handler(CommandHandler(["cancel", "cancelar"], cancel_command))

    # Message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    logger.info("Jarvis Antigravity Bridge starting polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
