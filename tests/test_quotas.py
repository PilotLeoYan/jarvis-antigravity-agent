import json
from unittest.mock import MagicMock, patch

from jarvis_antigravity_agent.quotas import (
    _discover_language_server,
    _extract_ports_for_pid,
    _query_agy_cli_quota,
    _resolve_agy_binary,
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

    def test_discover_language_server_csrf_variants(self):
        fake_pgrep = (
            "8888 /path/language_server --standalone "
            "--csrf-token=secret-token-equals --host_bridge_url=http://127.0.0.1:39615\n"
        )
        with patch("subprocess.check_output", return_value=fake_pgrep.encode("utf-8")):
            with patch(
                "jarvis_antigravity_agent.quotas._extract_ports_for_pid",
                return_value=[46433],
            ):
                pid, token, ports = _discover_language_server()
                assert pid == "8888"
                assert token == "secret-token-equals"
                assert 39615 in ports

    def test_format_quotas_markdown_escapes_special_chars(self):
        quota_data = {
            "groups": [
                {
                    "displayName": "custom_group_name",
                    "description": "desc_with_underscores",
                    "buckets": [
                        {
                            "displayName": "bucket_limit_1",
                            "remainingFraction": 0.5,
                            "description": "info_sample",
                        }
                    ],
                }
            ]
        }
        md = format_quotas_markdown(quota_data)
        assert "custom\\_group\\_name" in md
        assert "desc\\_with\\_underscores" in md
        assert "bucket\\_limit\\_1" in md

    def test_resolve_agy_binary_existing_file(self, tmp_path):
        fake_agy = tmp_path / "fake_agy"
        fake_agy.write_text("#!/bin/sh\n")
        fake_agy.chmod(0o755)
        resolved = _resolve_agy_binary(str(fake_agy))
        assert resolved == str(fake_agy)

    def test_query_agy_cli_quota_json_success(self):
        cli_output = {
            "status": "SUCCESS",
            "command": {
                "name": "usage",
                "data": {
                    "description": "Models share a weekly limit",
                    "groups": [
                        {
                            "name": "Gemini Models",
                            "description": "Flash and Pro",
                            "buckets": [
                                {
                                    "id": "gemini-weekly",
                                    "name": "Weekly Limit Remaining",
                                    "remaining_fraction": 0.82,
                                    "reset_time": "2026-09-16T18:03:49Z",
                                    "description": "Refreshes in 6 days",
                                }
                            ],
                        }
                    ],
                },
            },
        }
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps(cli_output)

        with (
            patch("shutil.which", return_value="/bin/agy"),
            patch("subprocess.run", return_value=mock_proc),
        ):
            data = _query_agy_cli_quota(agy_path="agy")
            assert data is not None
            assert "groups" in data
            assert data["groups"][0]["name"] == "Gemini Models"
            assert data["groups"][0]["buckets"][0]["remaining_fraction"] == 0.82

    def test_query_agy_cli_quota_fallback_to_usage(self):
        # First call fails (/quota), second succeeds (/usage)
        fail_proc = MagicMock()
        fail_proc.returncode = 1
        fail_proc.stdout = ""

        cli_output = {
            "status": "SUCCESS",
            "command": {
                "name": "usage",
                "data": {
                    "groups": [
                        {
                            "name": "Claude and GPT models",
                            "buckets": [
                                {
                                    "name": "Weekly Limit Remaining",
                                    "remaining_fraction": 1.0,
                                }
                            ],
                        }
                    ]
                },
            },
        }
        success_proc = MagicMock()
        success_proc.returncode = 0
        success_proc.stdout = json.dumps(cli_output)

        with (
            patch("shutil.which", return_value="/bin/agy"),
            patch("subprocess.run", side_effect=[fail_proc, success_proc]),
        ):
            data = _query_agy_cli_quota(agy_path="agy")
            assert data is not None
            assert data["groups"][0]["name"] == "Claude and GPT models"

    def test_query_agy_cli_quota_raw_tab_separated(self):
        raw_text = (
            "Gemini Models\tWeekly Limit Remaining\t82%\t2026-09-16T18:03:49Z\n"
            "Claude and GPT models\tWeekly Limit Remaining\t100%\t"
            "2026-09-17T01:07:47Z\n"
        )
        json_resp = {
            "status": "SUCCESS",
            "response": raw_text,
        }
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps(json_resp)

        with (
            patch("shutil.which", return_value="/bin/agy"),
            patch("subprocess.run", return_value=mock_proc),
        ):
            data = _query_agy_cli_quota(agy_path="agy")
            assert data is not None
            assert "raw_response" in data
            md = format_quotas_markdown(data)
            assert "Gemini Models" in md
            assert "82%" in md
            assert "Claude and GPT models" in md
            assert "100%" in md

    def test_get_agy_quotas_prefers_cli(self):
        with (
            patch(
                "jarvis_antigravity_agent.quotas._query_agy_cli_quota",
                return_value={"groups": [{"name": "CLI Group"}]},
            ),
            patch(
                "jarvis_antigravity_agent.quotas._query_language_server_quota",
                return_value={"groups": [{"name": "RPC Group"}]},
            ),
        ):
            quotas = get_agy_quotas()
            assert quotas is not None
            assert quotas["groups"][0]["name"] == "CLI Group"

    def test_get_agy_quotas_falls_back_to_rpc(self):
        with (
            patch(
                "jarvis_antigravity_agent.quotas._query_agy_cli_quota",
                return_value=None,
            ),
            patch(
                "jarvis_antigravity_agent.quotas._query_language_server_quota",
                return_value={"groups": [{"name": "RPC Group"}]},
            ),
        ):
            quotas = get_agy_quotas()
            assert quotas is not None
            assert quotas["groups"][0]["name"] == "RPC Group"

    def test_format_quotas_markdown_with_reset_time_and_desc(self):
        quota_data = {
            "description": "Weekly token budget",
            "groups": [
                {
                    "name": "Gemini Models",
                    "description": "Models within group",
                    "buckets": [
                        {
                            "name": "Weekly Limit Remaining",
                            "remaining_fraction": 0.8157,
                            "reset_time": "2026-09-16T18:03:49Z",
                            "description": "Refreshes in 6 days",
                        }
                    ],
                }
            ],
        }
        md = format_quotas_markdown(quota_data)
        assert "Weekly token budget" in md
        assert "81.6%" in md
        assert "2026-09-16 18:03:49 UTC" in md
        assert "Refreshes in 6 days" in md
