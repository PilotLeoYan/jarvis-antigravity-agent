import json
from unittest.mock import MagicMock, patch

from jarvis_antigravity_agent.quotas import (
    _discover_language_server,
    _extract_ports_for_pid,
    format_quotas_markdown,
    get_agy_quotas,
)


class TestQuotasModule:
    def test_extract_ports_for_pid_parsing(self):
        fake_ss = (
            "LISTEN 0 4096 127.0.0.1:46433 0.0.0.0:* "
            'users:(("language_server",pid=9999,fd=22))\n'
            "LISTEN 0 4096 127.0.0.1:45669 0.0.0.0:* "
            'users:(("language_server",pid=9999,fd=20))\n'
            'LISTEN 0 10 127.0.0.1:8080 0.0.0.0:* users:(("other",pid=1111,fd=5))\n'
        )
        with patch("subprocess.check_output", return_value=fake_ss.encode("utf-8")):
            ports = _extract_ports_for_pid("9999")
            assert 46433 in ports
            assert 45669 in ports
            assert 8080 not in ports[:2]

    def test_discover_language_server_via_pgrep(self):
        fake_pgrep = (
            "9999 /path/language_server --standalone "
            "--csrf_token my-secret-token --other\n"
        )
        fake_ss = (
            b"LISTEN 0 4096 127.0.0.1:46433 0.0.0.0:* "
            b'users:(("language_server",pid=9999,fd=22))\n'
        )
        with patch("subprocess.check_output") as mock_exec:
            # First call is pgrep, second is ss
            mock_exec.side_effect = [
                fake_pgrep.encode("utf-8"),
                fake_ss,
            ]
            pid, token, ports = _discover_language_server()
            assert pid == "9999"
            assert token == "my-secret-token"
            assert 46433 in ports

    def test_get_agy_quotas_success(self):
        sample_response = {
            "response": {
                "groups": [
                    {
                        "displayName": "Gemini Models",
                        "buckets": [
                            {
                                "displayName": "Weekly Limit",
                                "remainingFraction": 0.85,
                                "description": "Refreshes in 2 days",
                            }
                        ],
                    }
                ]
            }
        }
        mock_http_resp = MagicMock()
        mock_http_resp.status = 200
        mock_http_resp.read.return_value = json.dumps(sample_response).encode("utf-8")
        mock_http_resp.__enter__.return_value = mock_http_resp

        with (
            patch(
                "jarvis_antigravity_agent.quotas._discover_language_server",
                return_value=("9999", "secret", [46433]),
            ),
            patch("urllib.request.urlopen", return_value=mock_http_resp),
        ):
            quotas = get_agy_quotas()
            assert quotas is not None
            assert "groups" in quotas
            assert quotas["groups"][0]["displayName"] == "Gemini Models"

    def test_get_agy_quotas_server_not_running(self):
        with patch(
            "jarvis_antigravity_agent.quotas._discover_language_server",
            return_value=(None, None, []),
        ):
            quotas = get_agy_quotas()
            assert quotas is None

    def test_format_quotas_markdown_none(self):
        md = format_quotas_markdown(None)
        assert "Antigravity Quotas Unavailable" in md

    def test_format_quotas_markdown_valid(self):
        quota_data = {
            "groups": [
                {
                    "displayName": "Gemini Models",
                    "description": "Flash and Pro",
                    "buckets": [
                        {
                            "displayName": "Weekly Limit Remaining",
                            "remainingFraction": 0.6749,
                            "description": "Refreshes in 1 day",
                        },
                        {
                            "displayName": "5-Hour Limit Remaining",
                            "remainingFraction": 1.0,
                        },
                    ],
                }
            ]
        }
        md = format_quotas_markdown(quota_data)
        assert "Google Antigravity Quotas & Limits" in md
        assert "Gemini Models" in md
        assert "Flash and Pro" in md
        assert "67.5%" in md
        assert "100.0%" in md
