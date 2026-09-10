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


def _extract_ports_from_proc_net_tcp() -> list[int]:
    """Inspect listening localhost ports via /proc/net/tcp."""
    ports: list[int] = []
    for proc_path in ("/proc/net/tcp", "/proc/net/tcp6"):
        if not os.path.isfile(proc_path):
            continue
        try:
            with open(proc_path, encoding="utf-8") as f:
                lines = f.readlines()[1:]
            for line in lines:
                parts = line.strip().split()
                if len(parts) > 3 and parts[3] == "0A":  # TCP_LISTEN
                    local_addr = parts[1]
                    if ":" in local_addr:
                        ip_hex, port_hex = local_addr.split(":", 1)
                        if ip_hex.upper() in {"0100007F", "00000000"}:
                            port = int(port_hex, 16)
                            if port not in ports:
                                ports.append(port)
        except (OSError, ValueError):
            continue
    return ports


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

    # Fallback to inspecting /proc/net/tcp if ss yielded no ports
    if not ports:
        for p in _extract_ports_from_proc_net_tcp():
            if p not in ports:
                ports.append(p)

    # Fallback to inspecting candidate ports
    for p in DEFAULT_CANDIDATE_PORTS:
        if p not in ports:
            ports.append(p)
    return ports


def _discover_language_server() -> tuple[str | None, str | None, list[int]]:
    """Discover running language_server PID, CSRF token, and listening ports."""
    csrf_pattern = re.compile(r"--csrf[_-]token(?:=|\s+)([a-zA-Z0-9_-]+)")
    host_bridge_pattern = re.compile(r"--host_bridge_url=https?://127\.0\.0\.1:(\d+)")

    pgrep_bin = shutil.which("pgrep") or "/usr/bin/pgrep"
    try:
        # Check running processes using pgrep
        out = subprocess.check_output(  # noqa: S603
            [pgrep_bin, "-a", "-f", "language_server"], stderr=subprocess.DEVNULL
        ).decode("utf-8", errors="ignore")
        for line in out.splitlines():
            if "csrf" in line.lower():
                parts = line.strip().split()
                pid = parts[0]
                csrf_match = csrf_pattern.search(line)
                csrf_token = csrf_match.group(1) if csrf_match else None
                ports = _extract_ports_for_pid(pid)

                hb_match = host_bridge_pattern.search(line)
                if hb_match:
                    hb_port = int(hb_match.group(1))
                    if hb_port not in ports:
                        ports.insert(0, hb_port)

                if csrf_token:
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
                    if "language_server" in cmdline and "csrf" in cmdline.lower():
                        csrf_match = csrf_pattern.search(cmdline)
                        csrf_token = csrf_match.group(1) if csrf_match else None
                        ports = _extract_ports_for_pid(entry)

                        hb_match = host_bridge_pattern.search(cmdline)
                        if hb_match:
                            hb_port = int(hb_match.group(1))
                            if hb_port not in ports:
                                ports.insert(0, hb_port)

                        if csrf_token:
                            return entry, csrf_token, ports
                except (OSError, PermissionError):
                    continue
    except Exception as e:
        logger.debug("Language server discovery via /proc failed: %s", e)

    return None, None, []


def _resolve_agy_binary(agy_path: str = "agy") -> str:
    """Locate the agy binary from config, PATH, or standard user directories."""
    if (
        os.path.isabs(agy_path)
        and os.path.isfile(agy_path)
        and os.access(agy_path, os.X_OK)
    ):
        return agy_path
    resolved = shutil.which(agy_path)
    if resolved:
        return resolved
    for candidate in (
        os.path.expanduser("~/.local/bin/agy"),
        "/usr/local/bin/agy",
        "/usr/bin/agy",
    ):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return agy_path


def _query_agy_cli_quota(
    agy_path: str = "agy",
    timeout: float = 15.0,
) -> dict[str, Any] | None:
    """Execute agy CLI non-interactively to query model quota and usage."""
    agy_bin = _resolve_agy_binary(agy_path)
    if not (
        shutil.which(agy_bin) or (os.path.isabs(agy_bin) and os.path.isfile(agy_bin))
    ):
        return None

    env = os.environ.copy()
    user_local_bin = os.path.expanduser("~/.local/bin")
    if user_local_bin not in env.get("PATH", ""):
        env["PATH"] = f"{user_local_bin}:{env.get('PATH', '')}"

    # agy CLI supports both /quota and /usage
    for flag in ("/quota", "/usage"):
        for cmd in (
            [agy_bin, "--output-format", "json", "-p", flag],
            [agy_bin, "-p", flag],
        ):
            try:
                res = subprocess.run(  # noqa: S603
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=env,
                    check=False,
                )
                if res.returncode == 0 and res.stdout.strip():
                    try:
                        data = json.loads(res.stdout)
                        cmd_data = data.get("command", {}).get("data")
                        if isinstance(cmd_data, dict) and "groups" in cmd_data:
                            return cmd_data
                        resp_str = data.get("response", "").strip()
                        if resp_str:
                            return {
                                "raw_response": resp_str,
                                "description": data.get("command", {})
                                .get("data", {})
                                .get("description", ""),
                            }
                    except json.JSONDecodeError:
                        if res.stdout.strip():
                            return {"raw_response": res.stdout.strip()}
            except (subprocess.SubprocessError, OSError) as e:
                logger.debug("Failed querying agy quota via %s: %s", cmd, e)
                continue
    return None


def _query_language_server_quota() -> dict[str, Any] | None:
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


def get_agy_quotas(
    agy_path: str = "agy",
    timeout: float = 15.0,
) -> dict[str, Any] | None:
    """Fetch current user quota summary from agy CLI or local Language Server."""
    cli_quotas = _query_agy_cli_quota(agy_path=agy_path, timeout=timeout)
    if cli_quotas:
        return cli_quotas
    return _query_language_server_quota()


def format_quotas_markdown(quota_data: dict[str, Any] | None) -> str:
    """Format quota data into clean Telegram Markdown."""
    if not quota_data or not isinstance(quota_data, dict):
        return (
            "⚠️ *Antigravity Quotas Unavailable*\n\n"
            "Could not query quotas via Google Antigravity CLI (`agy -p /quota`) "
            "or local Language Server.\n"
            "Ensure Google Antigravity (`agy`) is installed and authenticated."
        )

    groups = quota_data.get("groups", [])
    if not groups and "raw_response" in quota_data:
        raw = quota_data["raw_response"]
        raw_lines = ["📊 *Google Antigravity Quotas & Limits*\n"]
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                model_grp = parts[0].strip().replace("_", "\\_").replace("*", "\\*")
                limit_type = parts[1].strip().replace("_", "\\_").replace("*", "\\*")
                pct = parts[2].strip()
                reset_info = ""
                if len(parts) > 3:
                    clean_time = parts[3].strip().replace("T", " ").replace("Z", " UTC")
                    reset_info = f" _(resets: {clean_time})_"
                raw_lines.append(f"• *{model_grp}* — {limit_type}: `{pct}`{reset_info}")
            else:
                raw_lines.append(f"• `{line}`")
        raw_lines.append("\nℹ️ _Quotas refresh automatically._")
        return "\n".join(raw_lines)

    if not groups:
        return (
            "ℹ️ *Antigravity Quotas*\n\n"
            "No quota groups were returned by the Antigravity engine."
        )

    lines: list[str] = ["📊 *Google Antigravity Quotas & Limits*\n"]

    desc = quota_data.get("description", "")
    if desc:
        clean_desc = desc.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[")
        lines.append(f"_{clean_desc}_\n")

    for group in groups:
        g_name = group.get("displayName") or group.get("name", "Model Group")
        g_desc = group.get("description", "")
        escaped_g_name = g_name.replace("_", "\\_").replace("*", "\\*")
        clean_g_desc = (
            g_desc.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[")
        )
        lines.append(f"🔷 *{escaped_g_name}*")
        if clean_g_desc:
            lines.append(f"_{clean_g_desc}_")

        buckets = group.get("buckets", [])
        for b in buckets:
            b_name = (
                b.get("displayName")
                or b.get("name")
                or b.get("bucketId")
                or b.get("id", "Limit")
            )
            frac = (
                b.get("remaining_fraction")
                if "remaining_fraction" in b
                else b.get("remainingFraction")
            )
            pct_str = f"{frac * 100:.1f}%" if frac is not None else "N/A"
            b_desc = b.get("description", "")
            reset_time = b.get("reset_time") or b.get("resetTime")

            escaped_b_name = b_name.replace("_", "\\_").replace("*", "\\*")
            clean_b_desc = (
                b_desc.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[")
            )

            bullet = f"• *{escaped_b_name}*: `{pct_str}`"
            if reset_time:
                clean_time = reset_time.replace("T", " ").replace("Z", " UTC")
                bullet += f" _(resets: {clean_time})_"
            if clean_b_desc:
                bullet += f"\n  _{clean_b_desc}_"
            lines.append(bullet)

        lines.append("")

    lines.append(
        "ℹ️ _Quotas are shared across models in each group and refresh automatically._"
    )
    return "\n".join(lines)
