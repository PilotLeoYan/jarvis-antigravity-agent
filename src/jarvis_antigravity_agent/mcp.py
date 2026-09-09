import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from jarvis_antigravity_agent.constants import Constants

logger = logging.getLogger(Constants.LOGGER_NAME)

DEFAULT_GLOBAL_MCP_PATH = os.path.expanduser("~/.gemini/config/mcp_config.json")
WORKSPACE_MCP_PATH = ".agents/mcp_config.json"


def find_mcp_config_path(explicit_path: str | Path | None = None) -> Path:
    """Locate the active MCP configuration file."""
    if explicit_path is not None:
        return Path(explicit_path)

    env_path = os.environ.get("MCP_CONFIG_PATH")
    if env_path:
        return Path(env_path)

    # If workspace-specific config exists in current directory, prefer it
    workspace_p = Path(WORKSPACE_MCP_PATH)
    if workspace_p.is_file():
        return workspace_p

    # Fallback to standard global Antigravity/Gemini configuration
    return Path(DEFAULT_GLOBAL_MCP_PATH)


def load_mcp_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load MCP configuration from JSON file."""
    target_path = find_mcp_config_path(config_path)
    if not target_path.is_file():
        return {"mcpServers": {}}

    try:
        with open(target_path, encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {"mcpServers": {}}
            if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
                data["mcpServers"] = {}
            return data
    except Exception as e:
        logger.warning("Failed to load MCP configuration from %s: %s", target_path, e)
        return {"mcpServers": {}}


def save_mcp_config(
    config: dict[str, Any], config_path: str | Path | None = None
) -> None:
    """Persist MCP configuration safely to JSON file."""
    target_path = find_mcp_config_path(config_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def list_mcp_servers(
    config_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Return dictionary of configured MCP servers."""
    cfg = load_mcp_config(config_path)
    servers = cfg.get("mcpServers", {})
    if isinstance(servers, dict):
        return servers
    return {}


def add_mcp_server(
    name: str,
    command: str,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    config_path: str | Path | None = None,
) -> bool:
    """Register or update an MCP server configuration."""
    clean_name = name.strip()
    if not clean_name or not command.strip():
        return False

    cfg = load_mcp_config(config_path)
    servers = cfg.setdefault("mcpServers", {})

    server_entry: dict[str, Any] = {
        "command": command.strip(),
        "args": args or [],
    }
    if env:
        server_entry["env"] = env

    servers[clean_name] = server_entry
    save_mcp_config(cfg, config_path)
    logger.info("Registered MCP server '%s' (%s)", clean_name, command)
    return True


def remove_mcp_server(
    name: str,
    config_path: str | Path | None = None,
) -> bool:
    """Remove a registered MCP server by name."""
    clean_name = name.strip()
    cfg = load_mcp_config(config_path)
    servers = cfg.get("mcpServers", {})
    if clean_name not in servers:
        return False

    del servers[clean_name]
    save_mcp_config(cfg, config_path)
    logger.info("Removed MCP server '%s'", clean_name)
    return True


def format_mcp_status(config_path: str | Path | None = None) -> str:
    """Generate Markdown status message detailing registered MCP servers."""
    target_path = find_mcp_config_path(config_path)
    servers = list_mcp_servers(config_path)

    if not servers:
        return (
            f"🔌 *Model Context Protocol (MCP) Servers*\n\n"
            f"No servers currently configured in `{target_path}`.\n\n"
            f"_Use `/mcp add <name> <command> [args...]` to register a new server._"
        )

    lines = [
        f"🔌 *Configured MCP Servers* ({len(servers)})",
        f"_Path: `{target_path}`_\n",
    ]

    for s_name, spec in sorted(servers.items()):
        cmd = spec.get("command", "unknown")
        args_list = spec.get("args", [])
        args_str = f" {' '.join(str(a) for a in args_list)}" if args_list else ""
        env_dict = spec.get("env", {})
        env_str = f" (env: {len(env_dict)} vars)" if env_dict else ""
        lines.append(f"• *{s_name}*: `{cmd}{args_str}`{env_str}")

    return "\n".join(lines)


def main_cli() -> None:
    """CLI entry point for managing MCP servers."""
    parser = argparse.ArgumentParser(
        description="Jarvis MCP (Model Context Protocol) Manager"
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    # list
    subparsers.add_parser("list", help="List all configured MCP servers")

    # add
    add_parser = subparsers.add_parser("add", help="Add or update an MCP server")
    add_parser.add_argument("name", help="Server name")
    add_parser.add_argument(
        "command", help="Command executable (e.g. npx, uvx, docker)"
    )
    add_parser.add_argument("args", nargs="*", default=[], help="Command arguments")

    # remove
    rm_parser = subparsers.add_parser("remove", help="Remove an MCP server")
    rm_parser.add_argument("name", help="Server name to remove")

    args = parser.parse_args()

    if args.action == "list":
        print(format_mcp_status())
    elif args.action == "add":
        success = add_mcp_server(args.name, args.command, args.args)
        if success:
            print(f"Successfully registered MCP server: {args.name}")
        else:
            print("Failed to register MCP server: invalid parameters", file=sys.stderr)
            sys.exit(1)
    elif args.action == "remove":
        removed = remove_mcp_server(args.name)
        if removed:
            print(f"Successfully removed MCP server: {args.name}")
        else:
            print(f"Server '{args.name}' not found", file=sys.stderr)
            sys.exit(1)
