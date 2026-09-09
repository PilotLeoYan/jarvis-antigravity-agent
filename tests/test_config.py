import json

import yaml

from jarvis_antigravity_agent.config import (
    Settings,
    build_runtime_config,
    find_config_path,
    is_authorized,
    load_config,
    load_settings,
    load_state,
    save_state,
)


class TestIsAuthorized:
    def test_empty_allowed_users_permits_everyone(self):
        assert is_authorized(12345, set()) is True

    def test_user_in_allowed_list_is_authorized(self):
        assert is_authorized(42, {"42", "99"}) is True

    def test_user_not_in_allowed_list_is_denied(self):
        assert is_authorized(1, {"42", "99"}) is False

    def test_user_id_matched_as_string(self):
        assert is_authorized(987654321, {"987654321"}) is True

    def test_user_id_type_coercion(self):
        assert is_authorized(0, {"0"}) is True

    def test_list_of_allowed_users(self):
        assert is_authorized(123, [123, 456]) is True
        assert is_authorized(789, [123, 456]) is False


class TestBuildRuntimeConfig:
    def test_bot_token_from_config(self):
        cfg = build_runtime_config({"bot_token": "tok123"})
        assert cfg["bot_token"] == "tok123"

    def test_bot_token_fallback_to_env(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env_token")
        cfg = build_runtime_config({})
        assert cfg["bot_token"] == "env_token"

    def test_allowed_users_converted_to_set_of_strings(self):
        cfg = build_runtime_config({"allowed_users": [1, 2, 3]})
        assert cfg["allowed_users"] == {"1", "2", "3"}

    def test_empty_allowed_users_produces_empty_set(self):
        cfg = build_runtime_config({})
        assert cfg["allowed_users"] == set()

    def test_default_flags_used_when_not_in_config(self):
        cfg = build_runtime_config({})
        assert "--dangerously-skip-permissions" in cfg["default_flags"]

    def test_custom_flags_override_default(self):
        cfg = build_runtime_config({"default_flags": ["--my-flag"]})
        assert cfg["default_flags"] == ["--my-flag"]

    def test_working_dir_from_config(self, tmp_path):
        test_dir = str(tmp_path / "test")
        cfg = build_runtime_config({"working_directory": test_dir})
        assert cfg["working_dir"] == test_dir

    def test_model_from_config(self):
        cfg = build_runtime_config({"agy": {"model": "gemini-2.5-flash"}})
        assert cfg["model"] == "gemini-2.5-flash"

    def test_default_model_in_runtime_config(self):
        cfg = build_runtime_config({})
        assert cfg["model"] == "Gemini 3.1 Pro (High)"


class TestPydanticSettings:
    def test_default_settings_instantiation(self):
        settings = Settings()
        assert settings.telegram.request_timeout > 0
        assert settings.agy.process_timeout > 0
        assert settings.agy.model == "Gemini 3.1 Pro (High)"
        assert settings.whisper.model_size == "base"
        assert settings.system.logger_name == "jarvis-bridge"

    def test_load_from_yaml_file(self, tmp_path):
        yaml_content = {
            "telegram": {
                "bot_token": "yaml_bot_token",
                "allowed_users": [111, 222],
                "default_chat_id": 999,
            },
            "agy": {
                "working_dir": "/tmp/yaml_work",
                "process_timeout": 120.0,
            },
            "whisper": {
                "model_size": "medium",
                "device": "cuda",
            },
        }
        yaml_file = tmp_path / "custom_config.yaml"
        yaml_file.write_text(yaml.dump(yaml_content))

        settings = load_settings(yaml_file)
        assert settings.telegram.bot_token == "yaml_bot_token"
        assert settings.telegram.allowed_users == [111, 222]
        assert settings.telegram.default_chat_id == 999
        assert settings.agy.working_dir == "/tmp/yaml_work"
        assert settings.agy.process_timeout == 120.0
        assert settings.whisper.model_size == "medium"
        assert settings.whisper.device == "cuda"

    def test_load_from_json_file(self, tmp_path):
        json_content = {
            "telegram": {
                "bot_token": "json_token",
                "allowed_users": [333],
            },
            "agy": {
                "working_dir": "/tmp/json_work",
            },
        }
        json_file = tmp_path / "custom_config.json"
        json_file.write_text(json.dumps(json_content))

        settings = load_settings(json_file)
        assert settings.telegram.bot_token == "json_token"
        assert settings.telegram.allowed_users == [333]
        assert settings.agy.working_dir == "/tmp/json_work"

    def test_flat_legacy_keys_mapping(self):
        flat_data = {
            "bot_token": "legacy_flat_token",
            "allowed_users": [123, 456],
            "default_chat_id": 789,
            "working_directory": "/home/legacy",
            "agy_path": "/usr/bin/agy-custom",
            "default_flags": ["--flag-a"],
        }
        settings = Settings(**flat_data)
        assert settings.telegram.bot_token == "legacy_flat_token"
        assert settings.telegram.allowed_users == [123, 456]
        assert settings.telegram.default_chat_id == 789
        assert settings.agy.working_dir == "/home/legacy"
        assert settings.agy.agy_path == "/usr/bin/agy-custom"
        assert settings.agy.default_flags == ["--flag-a"]
        # Also test backward-compatibility properties
        assert settings.bot_token == "legacy_flat_token"
        assert settings.working_dir == "/home/legacy"

    def test_find_config_path_explicit(self, tmp_path):
        f = tmp_path / "test.yaml"
        f.touch()
        found = find_config_path(f)
        assert found == f

    def test_find_config_path_env_var(self, tmp_path, monkeypatch):
        f = tmp_path / "env_config.yml"
        f.touch()
        monkeypatch.setenv("JARVIS_CONFIG_PATH", str(f))
        found = find_config_path()
        assert found == f

    def test_find_config_path_user_config_dir(self, tmp_path, monkeypatch):
        monkeypatch.delenv("JARVIS_CONFIG_PATH", raising=False)
        monkeypatch.delenv("AGY_TELEGRAM_CONFIG", raising=False)
        fake_home = tmp_path / "fake_home"
        user_cfg_dir = fake_home / ".config" / "jarvis-antigravity-agent"
        user_cfg_dir.mkdir(parents=True)
        cfg_file = user_cfg_dir / "config.yaml"
        cfg_file.touch()

        monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)
        monkeypatch.setattr("pathlib.Path.cwd", lambda: tmp_path / "other")
        monkeypatch.setattr(
            "jarvis_antigravity_agent.config.Constants.BASE_DIR",
            str(tmp_path / "empty_base"),
        )
        found = find_config_path()
        assert found == cfg_file

    def test_load_config_helper(self, tmp_path, monkeypatch):
        yaml_content = {"telegram": {"bot_token": "load_cfg_test"}}
        f = tmp_path / "config.yaml"
        f.write_text(yaml.dump(yaml_content))
        monkeypatch.setenv("JARVIS_CONFIG_PATH", str(f))

        cfg = load_config()
        assert cfg["telegram"]["bot_token"] == "load_cfg_test"


class TestStateManagement:
    def test_returns_default_state_when_file_missing(self, tmp_path):
        missing_file = tmp_path / "nonexistent_state.json"
        state = load_state(missing_file)
        assert state == {"continue_session": False}

    def test_returns_default_on_corrupt_file(self, tmp_path):
        corrupt_file = tmp_path / "corrupt_state.json"
        corrupt_file.write_text("invalid json")
        state = load_state(corrupt_file)
        assert state == {"continue_session": False}

    def test_save_and_load_state_roundtrip(self, tmp_path):
        state_file = tmp_path / "saved_state.json"
        original_state = {"continue_session": True, "last_user": 12345}
        save_state(original_state, state_file)
        loaded = load_state(state_file)
        assert loaded == original_state
