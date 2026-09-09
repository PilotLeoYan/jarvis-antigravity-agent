from pathlib import Path

from jarvis_antigravity_agent.mcp import (
    add_mcp_server,
    find_mcp_config_path,
    format_mcp_status,
    list_mcp_servers,
    load_mcp_config,
    remove_mcp_server,
    save_mcp_config,
)


class TestMcpManager:
    def test_find_mcp_config_path_explicit(self, tmp_path: Path):
        custom = tmp_path / "custom_mcp.json"
        assert find_mcp_config_path(custom) == custom

    def test_find_mcp_config_path_env_var(self, monkeypatch, tmp_path: Path):
        env_cfg = tmp_path / "env_mcp.json"
        monkeypatch.setenv("MCP_CONFIG_PATH", str(env_cfg))
        assert find_mcp_config_path() == env_cfg

    def test_load_mcp_config_missing_file(self, tmp_path: Path):
        missing = tmp_path / "non_existent.json"
        cfg = load_mcp_config(missing)
        assert cfg == {"mcpServers": {}}

    def test_load_mcp_config_corrupt_file(self, tmp_path: Path):
        corrupt = tmp_path / "corrupt.json"
        corrupt.write_text("{invalid json")
        cfg = load_mcp_config(corrupt)
        assert cfg == {"mcpServers": {}}

    def test_save_and_load_roundtrip(self, tmp_path: Path):
        target = tmp_path / "subdir" / "mcp_config.json"
        initial_data = {
            "mcpServers": {
                "test-server": {
                    "command": "npx",
                    "args": ["-y", "test-mcp"],
                }
            }
        }
        save_mcp_config(initial_data, target)
        loaded = load_mcp_config(target)
        assert loaded == initial_data
        assert "test-server" in list_mcp_servers(target)

    def test_add_mcp_server(self, tmp_path: Path):
        target = tmp_path / "mcp_config.json"
        ok = add_mcp_server(
            "context7",
            "npx",
            ["-y", "@upstash/context7-mcp"],
            {"KEY": "val"},
            config_path=target,
        )
        assert ok is True

        servers = list_mcp_servers(target)
        assert "context7" in servers
        assert servers["context7"]["command"] == "npx"
        assert servers["context7"]["args"] == ["-y", "@upstash/context7-mcp"]
        assert servers["context7"]["env"] == {"KEY": "val"}

    def test_add_mcp_server_invalid_inputs(self, tmp_path: Path):
        target = tmp_path / "mcp_config.json"
        assert add_mcp_server("", "cmd", config_path=target) is False
        assert add_mcp_server("name", "", config_path=target) is False

    def test_remove_mcp_server(self, tmp_path: Path):
        target = tmp_path / "mcp_config.json"
        add_mcp_server("to-remove", "echo", config_path=target)
        assert "to-remove" in list_mcp_servers(target)

        assert remove_mcp_server("to-remove", config_path=target) is True
        assert "to-remove" not in list_mcp_servers(target)
        assert remove_mcp_server("non-existent", config_path=target) is False

    def test_format_mcp_status_empty(self, tmp_path: Path):
        target = tmp_path / "mcp_config.json"
        msg = format_mcp_status(target)
        assert "No servers currently configured" in msg

    def test_format_mcp_status_populated(self, tmp_path: Path):
        target = tmp_path / "mcp_config.json"
        add_mcp_server(
            "github", "docker", ["run", "ghcr.io/github"], config_path=target
        )
        msg = format_mcp_status(target)
        assert "Configured MCP Servers" in msg
        assert "github" in msg
        assert "docker run ghcr.io/github" in msg

    def test_find_mcp_config_path_from_settings(self, tmp_path: Path):
        from unittest.mock import patch

        custom = tmp_path / "from_settings.json"
        with patch("jarvis_antigravity_agent.config.get_settings") as mock_settings:
            mock_settings.return_value.mcp.config_path = str(custom)
            assert find_mcp_config_path() == custom

    def test_mcp_cli_add_with_env(self, monkeypatch, tmp_path: Path):
        import sys

        from jarvis_antigravity_agent.mcp import main_cli

        target = tmp_path / "cli_mcp.json"
        monkeypatch.setenv("MCP_CONFIG_PATH", str(target))
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "jarvis-mcp",
                "add",
                "my-server",
                "python3",
                "-m",
                "srv",
                "-e",
                "API_KEY=secret123",
            ],
        )
        main_cli()

        servers = list_mcp_servers(target)
        assert "my-server" in servers
        assert servers["my-server"]["command"] == "python3"
        assert servers["my-server"]["args"] == ["-m", "srv"]
        assert servers["my-server"]["env"] == {"API_KEY": "secret123"}

    def test_global_mcp_status_formatting(self, monkeypatch, tmp_path: Path):
        from jarvis_antigravity_agent.mcp import (
            format_global_mcp_status,
            list_global_mcp_servers,
        )

        global_cfg = tmp_path / "global_mcp.json"
        monkeypatch.setattr(
            "jarvis_antigravity_agent.mcp.DEFAULT_GLOBAL_MCP_PATH", str(global_cfg)
        )
        add_mcp_server("context7", "npx", ["-y", "context7"], config_path=global_cfg)

        servers = list_global_mcp_servers()
        assert "context7" in servers

        msg = format_global_mcp_status()
        assert "Google Antigravity Global MCP Servers" in msg
        assert "context7" in msg
