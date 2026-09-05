from jarvis_antigravity_agent.constants import Constants


class TestConstants:
    def test_max_message_length_is_positive(self):
        assert Constants.MAX_MESSAGE_LENGTH > 0

    def test_agy_process_timeout_is_positive(self):
        assert Constants.AGY_PROCESS_TIMEOUT > 0

    def test_restart_return_codes_contains_sigterm(self):
        assert -15 in Constants.RESTART_RETURN_CODES

    def test_restart_return_codes_contains_sigkill(self):
        assert -9 in Constants.RESTART_RETURN_CODES

    def test_restart_return_codes_contains_143(self):
        assert 143 in Constants.RESTART_RETURN_CODES

    def test_restart_return_codes_contains_137(self):
        assert 137 in Constants.RESTART_RETURN_CODES

    def test_edit_throttle_is_positive(self):
        assert Constants.EDIT_THROTTLE_SECONDS > 0

    def test_max_status_items_is_positive(self):
        assert Constants.MAX_STATUS_ITEMS > 0

    def test_max_completed_items_gte_max_status_items(self):
        assert Constants.MAX_COMPLETED_ITEMS >= Constants.MAX_STATUS_ITEMS

    def test_telegram_api_url_template_has_placeholder(self):
        assert "{bot_token}" in Constants.TELEGRAM_API_SEND_URL

    def test_agy_output_format_is_stream_json(self):
        assert Constants.AGY_OUTPUT_FORMAT == "stream-json"

    def test_whisper_model_size_is_string(self):
        assert isinstance(Constants.WHISPER_MODEL_SIZE, str)

    def test_whisper_compute_type_is_string(self):
        assert isinstance(Constants.WHISPER_COMPUTE_TYPE, str)

    def test_state_key_continue_is_string(self):
        assert isinstance(Constants.STATE_KEY_CONTINUE, str)
