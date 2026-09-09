import json
import logging
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from typing import Any

from jarvis_antigravity_agent.constants import Constants

logger = logging.getLogger(Constants.LOGGER_NAME)

RETRIEVE_USER_QUOTA_ENDPOINT = (
    "/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary"
)
CSRF_HEADER_NAME = "x-codeium-csrf-token"  # noqa: S105
DEFAULT_CANDIDATE_PORTS = [46433, 45669, 45297, 39615]


def _extract_ports_for_pid(pid: str) -> list[int]:
    """Inspect listening TCP ports associated with a process ID."""
    ports: list[int] = []
    ss_bin = shutil.which("ss") or "/usr/bin/ss"
    try:
        ss_out = subprocess.check_output(  # noqa: S603
            [ss_bin, "-tlpn"], stderr=subprocess.DEVNULL
        ).decode("utf-8", errors="ignore")
        for line in ss_out.splitlines():
            if f"pid={pid}" in line or f"pid={pid}," in line:
                m = re.search(r"127\.0\.0\.1:(\d+)", line)
                if m:
                    ports.append(int(m.group(1)))
    except Exception as e:
        logger.debug("Failed to inspect ports via ss: %s", e)

    # Fallback to inspecting candidate ports
    for p in DEFAULT_CANDIDATE_PORTS:
        if p not in ports:
            ports.append(p)
    return ports


def _discover_language_server() -> tuple[str | None, str | None, list[int]]:
    """Discover running language_server PID, CSRF token, and listening ports."""
    pgrep_bin = shutil.which("pgrep") or "/usr/bin/pgrep"
    try:
        # Check running processes using pgrep
        out = subprocess.check_output(  # noqa: S603
            [pgrep_bin, "-a", "-f", "language_server"], stderr=subprocess.DEVNULL
        ).decode("utf-8", errors="ignore")
        for line in out.splitlines():
            if "--csrf_token" in line:
                parts = line.strip().split()
                pid = parts[0]
                csrf_match = re.search(r"--csrf_token\s+([a-zA-Z0-9_-]+)", line)
                csrf_token = csrf_match.group(1) if csrf_match else None
                ports = _extract_ports_for_pid(pid)
                return pid, csrf_token, ports
    except Exception as e:
        logger.debug("Language server discovery via pgrep failed: %s", e)

    # Secondary check by scanning /proc if available
    try:
        if os.path.exists("/proc"):
            for entry in os.listdir("/proc"):
                if not entry.isdigit():
                    continue
                cmdline_path = os.path.join("/proc", entry, "cmdline")
                if not os.path.isfile(cmdline_path):
                    continue
                try:
                    with open(cmdline_path, "rb") as f:
                        cmdline = (
                            f.read()
                            .replace(b"\x00", b" ")
                            .decode("utf-8", errors="ignore")
                        )
                    if "language_server" in cmdline and "--csrf_token" in cmdline:
                        csrf_match = re.search(
                            r"--csrf_token\s+([a-zA-Z0-9_-]+)", cmdline
                        )
                        csrf_token = csrf_match.group(1) if csrf_match else None
                        ports = _extract_ports_for_pid(entry)
                        return entry, csrf_token, ports
                except (OSError, PermissionError):
                    continue
    except Exception as e:
        logger.debug("Language server discovery via /proc failed: %s", e)

    return None, None, []


def get_agy_quotas() -> dict[str, Any] | None:
    """Fetch current user quota summary from the local Antigravity Language Server."""
    _, csrf_token, ports = _discover_language_server()
    if not csrf_token or not ports:
        return None

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        CSRF_HEADER_NAME: csrf_token,
    }

    for port in ports:
        url = f"http://127.0.0.1:{port}{RETRIEVE_USER_QUOTA_ENDPOINT}"
        req = urllib.request.Request(url, data=b"{}", headers=headers)  # noqa: S310
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:  # noqa: S310
                if resp.status == 200:
                    raw_data = resp.read().decode("utf-8", errors="replace")
                    parsed = json.loads(raw_data)
                    if isinstance(parsed, dict):
                        resp_obj = parsed.get("response")
                        if isinstance(resp_obj, dict):
                            return resp_obj
                        return parsed
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            continue

    return None


def format_quotas_markdown(quota_data: dict[str, Any] | None) -> str:
    """Format quota data into clean Telegram Markdown."""
    if not quota_data or not isinstance(quota_data, dict):
        return (
            "⚠️ *Antigravity Quotas Unavailable*\n\n"
            "Could not connect to the local Antigravity language server.\n"
            "Ensure Google Antigravity (`agy`) is running on the host."
        )

    groups = quota_data.get("groups", [])
    if not groups:
        return (
            "ℹ️ *Antigravity Quotas*\n\n"
            "No quota groups were returned by the Antigravity engine."
        )

    lines: list[str] = ["📊 *Google Antigravity Quotas & Limits*\n"]

    for group in groups:
        g_name = group.get("displayName", "Model Group")
        g_desc = group.get("description", "")
        lines.append(f"🔷 *{g_name}*")
        if g_desc:
            lines.append(f"_{g_desc}_")

        buckets = group.get("buckets", [])
        for b in buckets:
            b_name = b.get("displayName", b.get("bucketId", "Limit"))
            frac = b.get("remainingFraction")
            pct_str = f"{frac * 100:.1f}%" if frac is not None else "N/A"
            b_desc = b.get("description", "")

            # Build readable status bullet
            if b_desc:
                lines.append(f"• *{b_name}*: `{pct_str}` — _{b_desc}_")
            else:
                lines.append(f"• *{b_name}*: `{pct_str}`")

        lines.append("")

    lines.append(
        "ℹ️ _Quotas are shared across models in each group and refresh automatically._"
    )
    return "\n".join(lines)
