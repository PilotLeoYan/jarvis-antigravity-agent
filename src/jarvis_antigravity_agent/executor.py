import asyncio
import json
import logging
import os
import time
from collections.abc import Callable
from typing import Any

from telegram import Message, Update, constants
from telegram.ext import ContextTypes

from jarvis_antigravity_agent.constants import Constants
from jarvis_antigravity_agent.messages import Messages
from jarvis_antigravity_agent.utils import keep_typing, send_reply_chunks

logger = logging.getLogger(Constants.LOGGER_NAME)

current_process: asyncio.subprocess.Process | None = None
process_lock = asyncio.Lock()


def _describe_tool(tool_name: str, params: dict[str, Any]) -> str:
    if tool_name == "run_command":
        cmd_line = str(params.get("CommandLine", "")).strip().split("\n")[0]
        return str(Messages.TOOL_RUN_COMMAND.format(cmd=cmd_line[:65]))
    if tool_name in {"write_to_file", "replace_file_content"}:
        filename = os.path.basename(str(params.get("TargetFile", "file")))
        return str(Messages.TOOL_WRITE_FILE.format(filename=filename))
    if tool_name == "view_file":
        filename = os.path.basename(str(params.get("AbsolutePath", "file")))
        return str(Messages.TOOL_READ_FILE.format(filename=filename))
    if tool_name == "grep_search":
        return str(Messages.TOOL_GREP.format(query=str(params.get("Query", ""))[:45]))
    if tool_name == "search_web":
        query = str(params.get("query", ""))[:45]
        return str(Messages.TOOL_WEB_SEARCH.format(query=query))
    if tool_name == "invoke_subagent":
        return str(Messages.TOOL_SUBAGENT)
    return str(Messages.TOOL_GENERIC.format(name=tool_name))


async def _process_stream(
    process: asyncio.subprocess.Process,
    update: Update,
    status_msg: Message | None,
    step_items: list[str],
) -> tuple[str, str, list[str], list[str]]:
    if process.stdout is None:
        raise RuntimeError("Process stdout stream is not available")

    final_response_text = ""
    current_step_text: dict[int, str] = {}
    pending_agent_text = ""
    dispatched_intermediate_texts: list[str] = []
    last_edit_time = 0.0
    raw_output_lines: list[str] = []

    while True:
        line = await process.stdout.readline()
        if not line:
            break
        decoded = line.decode("utf-8", errors="replace").strip()
        if not decoded:
            continue
        raw_output_lines.append(decoded)

        try:
            data: dict[str, Any] = json.loads(decoded)
        except json.JSONDecodeError:
            continue

        ev = data.get("event")

        if ev == "step":
            su: dict[str, Any] = data.get("step_update", {})
            s_idx: int = su.get("step_index", 0)
            stype: str = su.get("step_type", "")
            sstate: str = su.get("state", "")

            if stype == "agent_response":
                delta = str(su.get("text_delta", ""))
                current_step_text[s_idx] = current_step_text.get(s_idx, "") + delta
                if sstate == "DONE":
                    pending_agent_text = current_step_text[s_idx].strip()

            elif stype == "tool" and sstate == "ACTIVE":
                if pending_agent_text and update.message is not None:
                    try:
                        await update.message.reply_text(
                            pending_agent_text,
                            parse_mode=constants.ParseMode.MARKDOWN,
                        )
                    except Exception:
                        await update.message.reply_text(pending_agent_text)
                    dispatched_intermediate_texts.append(pending_agent_text)
                    pending_agent_text = ""

                tname = str(su.get("tool_name", ""))
                params: dict[str, Any] = su.get("tool_info", {}).get("parameters", {})
                desc = _describe_tool(tname, params)

                if desc and desc not in step_items:
                    step_items.append(desc)

                now = time.time()
                elapsed_since_edit = now - last_edit_time
                throttle_passed = elapsed_since_edit >= Constants.EDIT_THROTTLE_SECONDS
                if status_msg is not None and throttle_passed:
                    last_edit_time = now
                    try:
                        display = step_items[-Constants.MAX_STATUS_ITEMS :]
                        await status_msg.edit_text(
                            Messages.TASK_PROGRESS + "\n".join(display),
                            parse_mode=constants.ParseMode.MARKDOWN,
                        )
                    except Exception as e:
                        logger.debug("Failed to edit task progress message: %s", e)

        elif ev == "result":
            final_response_text = str(
                data.get("result", {}).get("response", "")
            ).strip()

    return (
        final_response_text,
        pending_agent_text,
        raw_output_lines,
        dispatched_intermediate_texts,
    )


def _deduplicate_final(
    final_response_text: str,
    dispatched_intermediate_texts: list[str],
) -> str:
    clean = final_response_text.strip()
    for disp in dispatched_intermediate_texts:
        disp_clean = disp.strip()
        if not disp_clean:
            continue
        if clean.startswith(disp_clean):
            clean = clean[len(disp_clean) :].lstrip()
        elif disp_clean in clean[: len(disp_clean) + 60]:
            idx = clean.find(disp_clean)
            if idx != -1 and idx < 60:
                clean = clean[idx + len(disp_clean) :].lstrip()
    return clean


async def execute_agy_prompt(
    prompt: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    runtime_cfg: dict[str, Any],
    state: dict[str, Any],
    save_state_fn: Callable[[dict[str, Any]], None],
) -> None:
    global current_process

    async with process_lock:
        continue_flag = bool(state.get(Constants.STATE_KEY_CONTINUE, False))

        cmd = (
            [runtime_cfg["agy_path"]]
            + runtime_cfg["default_flags"]
            + [Constants.AGY_OUTPUT_FORMAT_FLAG, Constants.AGY_OUTPUT_FORMAT]
        )
        if continue_flag:
            cmd.append(Constants.AGY_CONTINUE_FLAG)
        cmd.extend([Constants.AGY_PROMPT_FLAG, prompt])

        env = os.environ.copy()
        env["PATH"] = (
            f"{Constants.AGY_LOCAL_BIN}:{Constants.PATH_EXTRA}:{env.get('PATH', '')}"
        )

        stop_typing = asyncio.Event()
        chat_id = update.effective_chat.id if update.effective_chat else 0
        typing_task = asyncio.create_task(keep_typing(chat_id, context, stop_typing))

        status_msg: Message | None = None
        if update.message is not None:
            try:
                status_msg = await update.message.reply_text(
                    Messages.STARTING_TASK, parse_mode=constants.ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.debug("Failed to send starting task message: %s", e)

        start_time = time.time()
        logger.info(
            Messages.AGY_EXECUTING.format(
                continue_flag=continue_flag, prompt=prompt[:80]
            )
        )

        step_items: list[str] = []

        try:
            current_process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=runtime_cfg["working_dir"],
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                (
                    final_response_text,
                    pending_agent_text,
                    raw_output_lines,
                    dispatched_intermediate_texts,
                ) = await asyncio.wait_for(
                    _process_stream(current_process, update, status_msg, step_items),
                    timeout=Constants.AGY_PROCESS_TIMEOUT,
                )
                _, stderr = await asyncio.wait_for(
                    current_process.communicate(),
                    timeout=Constants.AGY_COMMUNICATE_TIMEOUT,
                )
            except asyncio.TimeoutError:
                if current_process and current_process.returncode is None:
                    current_process.kill()
                timeout_msg = Messages.TIMEOUT_EXCEEDED_SAFETY.format(
                    timeout=int(Constants.AGY_PROCESS_TIMEOUT)
                )
                if status_msg is not None:
                    try:
                        await status_msg.edit_text(
                            timeout_msg, parse_mode=constants.ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.debug("Failed to edit timeout message: %s", e)
                elif update.message is not None:
                    await update.message.reply_text(
                        Messages.TIMEOUT_EXCEEDED.format(
                            timeout=int(Constants.AGY_PROCESS_TIMEOUT)
                        )
                    )
                return

            elapsed = time.time() - start_time
            logger.info(
                Messages.AGY_EXITED.format(
                    code=current_process.returncode, elapsed=elapsed
                )
            )

            if status_msg is not None:
                try:
                    if step_items:
                        display = step_items[-Constants.MAX_COMPLETED_ITEMS :]
                        final_status = Messages.COMPLETED_STEPS + "\n".join(display)
                    else:
                        final_status = Messages.TASK_COMPLETED
                    await status_msg.edit_text(
                        final_status, parse_mode=constants.ParseMode.MARKDOWN
                    )
                except Exception as e:
                    logger.debug("Failed to edit final status message: %s", e)

            err_text = (
                stderr.decode("utf-8", errors="replace").strip() if stderr else ""
            )
            clean_final = _deduplicate_final(
                final_response_text, dispatched_intermediate_texts
            )
            output_text = clean_final or pending_agent_text

            if (
                not output_text
                and raw_output_lines
                and not any(raw_line.startswith("{") for raw_line in raw_output_lines)
            ):
                output_text = "\n".join(raw_output_lines).strip()

            if current_process.returncode == 0:
                state[Constants.STATE_KEY_CONTINUE] = True
                save_state_fn(state)
                if output_text:
                    await send_reply_chunks(update, output_text)
                elif update.message is not None:
                    await update.message.reply_text(Messages.TASK_COMPLETED_NO_TEXT)

            elif current_process.returncode in Constants.RESTART_RETURN_CODES:
                restart_notice = Messages.RELOADING_UPDATES
                if status_msg is not None:
                    try:
                        await status_msg.edit_text(
                            restart_notice, parse_mode=constants.ParseMode.MARKDOWN
                        )
                    except Exception:
                        if update.message is not None:
                            await update.message.reply_text(
                                restart_notice,
                                parse_mode=constants.ParseMode.MARKDOWN,
                            )
                elif update.message is not None:
                    await update.message.reply_text(
                        restart_notice, parse_mode=constants.ParseMode.MARKDOWN
                    )

            else:
                error_msg = Messages.EXECUTION_ERROR.format(
                    code=current_process.returncode
                )
                if output_text:
                    error_msg += f"\n```\n{output_text}\n```"
                if err_text:
                    error_msg += f"\n```\n{err_text}\n```"
                await send_reply_chunks(update, error_msg)

        except asyncio.CancelledError:
            if current_process and current_process.returncode is None:
                try:
                    current_process.kill()
                except Exception as e:
                    logger.debug("Failed to kill process on cancel: %s", e)
            restart_notice = Messages.RELOADING_GENERAL
            if status_msg is not None:
                try:
                    await status_msg.edit_text(
                        restart_notice, parse_mode=constants.ParseMode.MARKDOWN
                    )
                except Exception as e:
                    logger.debug("Failed to edit restart notice: %s", e)
            elif update.message is not None:
                try:
                    await update.message.reply_text(
                        restart_notice, parse_mode=constants.ParseMode.MARKDOWN
                    )
                except Exception as e:
                    logger.debug("Failed to send restart notice: %s", e)
            raise

        except Exception as e:
            logger.exception(Messages.AGY_UNEXPECTED_ERROR)
            if update.message is not None:
                await update.message.reply_text(
                    Messages.UNEXPECTED_ERROR.format(error=e)
                )

        finally:
            stop_typing.set()
            await typing_task
            current_process = None
