from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis_antigravity_agent.handlers import BotHandlers
from jarvis_antigravity_agent.messages import Messages
from jarvis_antigravity_agent.uninstaller import (
    link_project_binaries,
    main_cli,
    perform_uninstall,
    purge_agy_data,
    purge_personal_data,
    stop_and_disable_service,
    unlink_project_binaries,
    unlink_project_skills,
)


class TestUninstaller:
    def test_stop_and_disable_service_dry_run(self, tmp_path: Path):
        fake_service = tmp_path / "fake.service"
        fake_service.write_text("[Unit]\nDescription=Test\n")
        ok = stop_and_disable_service(
            service_name="fake.service",
            service_file=str(fake_service),
            dry_run=True,
        )
        assert ok is True
        assert fake_service.exists()

    def test_stop_and_disable_service_actual(self, tmp_path: Path):
        fake_service = tmp_path / "fake.service"
        fake_service.write_text("[Unit]\nDescription=Test\n")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            ok = stop_and_disable_service(
                service_name="fake.service",
                service_file=str(fake_service),
                dry_run=False,
            )
            assert ok is True
            assert not fake_service.exists()
            assert mock_run.call_count >= 2

    def test_unlink_project_skills(self, tmp_path: Path):
        repo_dir = tmp_path / "my_repo"
        repo_skills = repo_dir / "skills" / "custom_skill"
        repo_skills.mkdir(parents=True)

        other_dir = tmp_path / "other_project" / "skill_x"
        other_dir.mkdir(parents=True)

        target_agents_skills = tmp_path / "agents_skills"
        target_agents_skills.mkdir()

        # Create symlinks
        link_mine = target_agents_skills / "custom_skill"
        link_mine.symlink_to(repo_skills)

        link_other = target_agents_skills / "skill_x"
        link_other.symlink_to(other_dir)

        # Unlink for my_repo
        removed = unlink_project_skills(
            project_dir=repo_dir,
            skills_target_dir=str(target_agents_skills),
            dry_run=False,
        )

        assert "custom_skill" in removed
        assert not link_mine.exists()
        assert link_other.exists()

    def test_unlink_project_binaries(self, tmp_path: Path):
        repo_dir = tmp_path / "jarvis_repo"
        repo_bin = repo_dir / ".venv" / "bin"
        repo_bin.mkdir(parents=True)
        (repo_bin / "jarvis-antigravity-agent").write_text("#!/usr/bin/env python3")

        # Sibling directory that starts with the same string prefix "jarvis_repo"
        other_repo = tmp_path / "jarvis_repo_other" / "bin"
        other_repo.mkdir(parents=True)
        (other_repo / "jarvis-mcp").write_text("#!/usr/bin/env python3")

        target_bin_dir = tmp_path / "local_bin"
        target_bin_dir.mkdir()

        # Create symlinks
        link_mine = target_bin_dir / "jarvis-antigravity-agent"
        link_mine.symlink_to(repo_bin / "jarvis-antigravity-agent")

        link_other = target_bin_dir / "jarvis-mcp"
        link_other.symlink_to(other_repo / "jarvis-mcp")

        # Nonexistent dir returns empty
        assert unlink_project_binaries(bin_dir=tmp_path / "nonexistent") == []

        # Dry run does not remove
        dry_removed = unlink_project_binaries(
            project_dir=repo_dir,
            bin_dir=target_bin_dir,
            dry_run=True,
        )
        assert "jarvis-antigravity-agent" in dry_removed
        assert link_mine.exists()

        # Actual run removes repo link but preserves other
        # (preventing prefix collisions)
        removed = unlink_project_binaries(
            project_dir=repo_dir,
            bin_dir=target_bin_dir,
            dry_run=False,
        )
        assert "jarvis-antigravity-agent" in removed
        assert not link_mine.exists()
        assert link_other.exists()

    def test_link_project_binaries(self, tmp_path: Path):
        repo_dir = tmp_path / "jarvis_repo"
        repo_bin = repo_dir / ".venv" / "bin"
        repo_bin.mkdir(parents=True)
        (repo_bin / "jarvis-antigravity-agent").write_text("#!/usr/bin/env python3")
        (repo_bin / "jarvis-send-message").write_text("#!/usr/bin/env python3")

        target_bin_dir = tmp_path / "local_bin"

        # Nonexistent venv returns empty list
        assert link_project_binaries(project_dir=tmp_path / "nonexistent") == []

        # Successful linking
        linked = link_project_binaries(
            project_dir=repo_dir,
            bin_dir=target_bin_dir,
        )
        assert "jarvis-antigravity-agent" in linked
        assert "jarvis-send-message" in linked
        assert (target_bin_dir / "jarvis-antigravity-agent").is_symlink()
        assert (target_bin_dir / "jarvis-send-message").is_symlink()

        # Idempotent re-linking
        relinked = link_project_binaries(
            project_dir=repo_dir,
            bin_dir=target_bin_dir,
        )
        assert "jarvis-antigravity-agent" in relinked

    def test_purge_personal_data(self, tmp_path: Path):
        config_f = tmp_path / "config.yaml"
        config_f.write_text("bot_token: 'secret'")
        state_f = tmp_path / "state.json"
        state_f.write_text("{}")
        audio_f = tmp_path / "voice_sample.oga"
        audio_f.write_text("audio data")
        unrelated = tmp_path / "README.md"
        unrelated.write_text("readme")

        # Check .env and log files deletion as well
        env_f = tmp_path / ".env"
        env_f.write_text("TOKEN=123")
        log_f = tmp_path / "jarvis.log"
        log_f.write_text("log data")

        # Test dry-run first
        dry_removed = purge_personal_data(base_dir=tmp_path, dry_run=True)
        assert len(dry_removed) >= 5
        assert config_f.exists()
        assert env_f.exists()

        # Actual deletion
        removed = purge_personal_data(base_dir=tmp_path, dry_run=False)
        assert str(config_f) in removed
        assert not config_f.exists()
        assert not state_f.exists()
        assert not audio_f.exists()
        assert not env_f.exists()
        assert not log_f.exists()
        assert unrelated.exists()

    def test_purge_agy_data(self, tmp_path: Path):
        gemini_dir = tmp_path / ".gemini"
        gemini_dir.mkdir()
        (gemini_dir / "test.txt").write_text("agy test")

        agents_dir = tmp_path / ".agents"
        agents_dir.mkdir()

        cache_dir = tmp_path / ".cache" / "antigravity"
        cache_dir.mkdir(parents=True)

        # Dry run
        dry_purged = purge_agy_data(
            directories=[str(gemini_dir), str(agents_dir), str(cache_dir)],
            dry_run=True,
        )
        assert len(dry_purged) == 3
        assert gemini_dir.exists()
        assert cache_dir.exists()

        # Actual purge
        purged = purge_agy_data(
            directories=[str(gemini_dir), str(agents_dir), str(cache_dir)],
            dry_run=False,
        )
        assert len(purged) == 3
        assert not gemini_dir.exists()
        assert not agents_dir.exists()
        assert not cache_dir.exists()

    def test_stop_and_disable_service_broken_symlink(self, tmp_path: Path):
        broken_link = tmp_path / "broken.service"
        broken_link.symlink_to(tmp_path / "nonexistent.service")
        assert broken_link.is_symlink()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            ok = stop_and_disable_service(
                service_name="broken.service",
                service_file=str(broken_link),
                dry_run=False,
            )
            assert ok is True
            assert not broken_link.is_symlink()

    def test_perform_uninstall_orchestrator(self, tmp_path: Path):
        with patch(
            "jarvis_antigravity_agent.uninstaller.stop_and_disable_service",
            return_value=True,
        ) as mock_svc:
            results = perform_uninstall(
                purge_personal=False,
                purge_agy=False,
                purge_service=True,
                dry_run=True,
                project_dir=tmp_path,
            )
            assert results["service_stopped"] is True
            assert "binaries_unlinked" in results
            mock_svc.assert_called_once()

    @pytest.mark.anyio
    async def test_telegram_uninstall_command(self):
        mock_update = MagicMock()
        mock_update.effective_user.id = 12345
        mock_update.message.reply_text = AsyncMock()

        cfg = {"allowed_users": {"12345"}}
        handlers = BotHandlers(cfg, {})
        await handlers.uninstall_command(mock_update, MagicMock())

        mock_update.message.reply_text.assert_awaited_once_with(
            Messages.UNINSTALL_GUIDE, parse_mode="Markdown"
        )

    def test_main_cli_dry_run(self):
        with patch("sys.argv", ["jarvis-uninstall", "--dry-run", "-y", "--all"]):
            with patch(
                "jarvis_antigravity_agent.uninstaller.perform_uninstall"
            ) as mock_perform:
                main_cli()
                mock_perform.assert_called_once_with(
                    purge_personal=True,
                    purge_agy=True,
                    purge_service=True,
                    dry_run=True,
                    project_dir=None,
                )

    def test_main_cli_custom_project_dir(self, tmp_path: Path):
        with patch(
            "sys.argv",
            [
                "jarvis-uninstall",
                "-d",
                str(tmp_path),
                "--dry-run",
                "-y",
                "--purge-personal",
            ],
        ):
            with patch(
                "jarvis_antigravity_agent.uninstaller.perform_uninstall"
            ) as mock_perform:
                main_cli()
                mock_perform.assert_called_once_with(
                    purge_personal=True,
                    purge_agy=False,
                    purge_service=True,
                    dry_run=True,
                    project_dir=str(tmp_path),
                )
