---
name: mcp-management
description: Guide to managing Model Context Protocol (MCP) servers, tools, and configuration in Google Antigravity.
---

# Model Context Protocol (MCP) Management Guide

Model Context Protocol (MCP) allows Google Antigravity CLI (`agy`) to integrate external tools, services, and live data sources (such as GitHub, Context7, SQLite, and custom toolkits).

## Configuration File Location

Antigravity resolves MCP configurations from:
- Global configuration: `~/.gemini/config/mcp_config.json`
- Project-scoped configuration: `.agents/mcp_config.json`

## Schema of `mcp_config.json`

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"],
      "env": {
        "CONTEXT7_API_KEY": "your_api_key_here"
      }
    },
    "github-mcp-server": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e",
        "GITHUB_PERSONAL_ACCESS_TOKEN",
        "ghcr.io/github/github-mcp-server"
      ],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_your_token_here"
      }
    }
  }
}
```

## Management via Telegram Bot & Jarvis CLI

Jarvis includes native MCP inspection and management:
- List active MCP servers:
  ```bash
  /mcp list
  ```
- Add a new server:
  ```bash
  /mcp add fetch uvx mcp-server-fetch
  ```
- Remove a server:
  ```bash
  /mcp remove fetch
  ```

## Best Practices
1. **Tool Verification**: After registering an MCP server, verify that the required binaries (e.g. `npx`, `docker`, `uvx`) are installed and executable on the host system.
2. **Permission Grants**: Ensure required tools are whitelisted in `~/.gemini/config/config.json` under `globalPermissionGrants` if operating outside `--dangerously-skip-permissions`.
