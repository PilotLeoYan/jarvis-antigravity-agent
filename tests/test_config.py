from jarvis_antigravity_agent.config import build_runtime_config, is_authorized


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


class TestLoadState:
    def test_returns_default_state_when_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "jarvis_antigravity_agent.constants.Constants.STATE_PATH",
            str(tmp_path / "nonexistent.json"),
        )
        from jarvis_antigravity_agent import config as cfg_module

        monkeypatch.setattr(
            cfg_module.Constants,
            "STATE_PATH",
            str(tmp_path / "nonexistent.json"),
        )
        state = cfg_module.load_state()
        assert state == {"continue_session": False}

    def test_returns_default_on_corrupt_file(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        state_file.write_text("not valid json")

        from jarvis_antigravity_agent import config as cfg_module

        monkeypatch.setattr(cfg_module.Constants, "STATE_PATH", str(state_file))
        state = cfg_module.load_state()
        assert state == {"continue_session": False}
