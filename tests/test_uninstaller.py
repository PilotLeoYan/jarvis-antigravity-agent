from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis_antigravity_agent.handlers import BotHandlers
from jarvis_antigravity_agent.messages import Messages
from jarvis_antigravity_agent.uninstaller import (
    copy_cognitive_rules,
    copy_project_skills,
    link_project_binaries,
    main_cli,
    perform_uninstall,
    purge_agy_data,
    purge_personal_data,
    stop_and_disable_service,
    unlink_cognitive_rules,
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

    def test_unlink_project_skills_copied_directory(self, tmp_path: Path):
        repo_dir = tmp_path / "my_repo"
        repo_skills = repo_dir / "skills" / "telegram-formatting"
        repo_skills.mkdir(parents=True)
        (repo_skills / "SKILL.md").write_text("---\nname: telegram-formatting\n---\n")

        target_dir = tmp_path / "gemini_skills"
        target_dir.mkdir()

        # Copied skill from this repo
        copied_skill = target_dir / "telegram-formatting"
        copied_skill.mkdir()
        (copied_skill / "SKILL.md").write_text("---\nname: telegram-formatting\n---\n")

        # Other unrelated skill in the same target dir
        unrelated_skill = target_dir / "find-skills"
        unrelated_skill.mkdir()
        (unrelated_skill / "SKILL.md").write_text("---\nname: find-skills\n---\n")

        # Dry run does not remove
        dry_removed = unlink_project_skills(
            project_dir=repo_dir,
            skills_target_dir=str(target_dir),
            dry_run=True,
        )
        assert "telegram-formatting" in dry_removed
        assert copied_skill.exists()
        assert unrelated_skill.exists()

        # Actual run removes only project skill directory
        removed = unlink_project_skills(
            project_dir=repo_dir,
            skills_target_dir=str(target_dir),
            dry_run=False,
        )
        assert "telegram-formatting" in removed
        assert not copied_skill.exists()
        assert unrelated_skill.exists()

    def test_copy_project_skills_success(self, tmp_path: Path):
        repo_dir = tmp_path / "jarvis_repo"
        (repo_dir / "skills" / "telegram-formatting").mkdir(parents=True)
        (repo_dir / "skills" / "telegram-formatting" / "SKILL.md").write_text(
            "---\nname: telegram-formatting\n---\n"
        )
        (repo_dir / "skills" / "agy-cli").mkdir(parents=True)
        (repo_dir / "skills" / "agy-cli" / "SKILL.md").write_text(
            "---\nname: agy-cli\n---\n"
        )

        target1 = tmp_path / "target1"
        target2 = tmp_path / "target2"
        target1.mkdir()
        target2.mkdir()

        # Pre-create an obsolete symlink in target1 to verify overwrite
        dummy_dir = tmp_path / "dummy"
        dummy_dir.mkdir()
        (target1 / "telegram-formatting").symlink_to(dummy_dir)

        copied = copy_project_skills(
            project_dir=repo_dir,
            skills_target_dirs=[str(target1), str(target2)],
        )

        assert "telegram-formatting" in copied
        assert "agy-cli" in copied

        # Verify target1
        assert (target1 / "telegram-formatting").is_dir()
        assert not (target1 / "telegram-formatting").is_symlink()
        assert (target1 / "telegram-formatting" / "SKILL.md").exists()
        assert (target1 / "agy-cli" / "SKILL.md").exists()

        # Verify target2
        assert (target2 / "telegram-formatting" / "SKILL.md").exists()
        assert (target2 / "agy-cli" / "SKILL.md").exists()

    def test_copy_project_skills_missing_skills_dir(self, tmp_path: Path):
        empty_repo = tmp_path / "empty_repo"
        empty_repo.mkdir()
        copied = copy_project_skills(project_dir=empty_repo)
        assert copied == []

    def test_copy_project_skills_ignores_non_skill_dirs(self, tmp_path: Path):
        repo_dir = tmp_path / "jarvis_repo"
        # Valid skill
        (repo_dir / "skills" / "telegram-formatting").mkdir(parents=True)
        (repo_dir / "skills" / "telegram-formatting" / "SKILL.md").write_text(
            "---\nname: telegram-formatting\n---\n"
        )
        # Non-skill directory (no SKILL.md)
        (repo_dir / "skills" / "__pycache__").mkdir(parents=True)
        (repo_dir / "skills" / "__pycache__" / "temp.pyc").write_text("fake")

        target = tmp_path / "target"
        target.mkdir()

        copied = copy_project_skills(
            project_dir=repo_dir,
            skills_target_dirs=[str(target)],
        )

        assert copied == ["telegram-formatting"]
        assert (target / "telegram-formatting").is_dir()
        assert not (target / "__pycache__").exists()

    def test_unlink_project_skills_deduplication_across_multiple_dirs(
        self, tmp_path: Path
    ):
        repo_dir = tmp_path / "my_repo"
        repo_skill = repo_dir / "skills" / "telegram-formatting"
        repo_skill.mkdir(parents=True)
        (repo_skill / "SKILL.md").write_text("---\nname: telegram-formatting\n---\n")

        # Create multiple target dirs
        target1 = tmp_path / "agents_skills"
        target2 = tmp_path / "gemini_skills"
        target1.mkdir()
        target2.mkdir()

        copied_skill1 = target1 / "telegram-formatting"
        copied_skill1.mkdir()
        (copied_skill1 / "SKILL.md").write_text("---\nname: telegram-formatting\n---\n")

        copied_skill2 = target2 / "telegram-formatting"
        copied_skill2.mkdir()
        (copied_skill2 / "SKILL.md").write_text("---\nname: telegram-formatting\n---\n")

        removed = unlink_project_skills(
            project_dir=repo_dir,
            skills_target_dir=[str(target1), str(target2)],
            dry_run=False,
        )

        # Must not contain duplicates
        assert removed == ["telegram-formatting"]
        assert not copied_skill1.exists()
        assert not copied_skill2.exists()

    def test_unlink_project_skills_ignores_non_skill_dirs(self, tmp_path: Path):
        repo_dir = tmp_path / "my_repo"
        # Non-skill folder in repo skills
        (repo_dir / "skills" / "random_folder").mkdir(parents=True)

        target_dir = tmp_path / "target"
        target_dir.mkdir()
        folder_in_target = target_dir / "random_folder"
        folder_in_target.mkdir()

        removed = unlink_project_skills(
            project_dir=repo_dir,
            skills_target_dir=str(target_dir),
            dry_run=False,
        )
        assert removed == []
        assert folder_in_target.exists()

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

    def test_copy_cognitive_rules_deployment(self, tmp_path: Path):
        repo_dir = tmp_path / "repo"
        cog_dir = repo_dir / "cognitive"
        cog_dir.mkdir(parents=True)
        soul_md = cog_dir / "SOUL.md"
        soul_md.write_text("Persona: Jarvis Autonomous Agent")
        mem_ex = cog_dir / "MEMORY.example.md"
        mem_ex.write_text("# Memory Template")

        target_rules_1 = tmp_path / "rules1"
        target_rules_2 = tmp_path / "rules2"

        deployed = copy_cognitive_rules(
            project_dir=repo_dir,
            rules_target_dirs=[str(target_rules_1), str(target_rules_2)],
        )

        assert len(deployed) >= 4
        assert (
            target_rules_1 / "SOUL.md"
        ).read_text() == "Persona: Jarvis Autonomous Agent"
        assert (
            target_rules_1 / "AGENTS.md"
        ).read_text() == "Persona: Jarvis Autonomous Agent"
        assert (
            target_rules_2 / "SOUL.md"
        ).read_text() == "Persona: Jarvis Autonomous Agent"
        assert (
            target_rules_2 / "AGENTS.md"
        ).read_text() == "Persona: Jarvis Autonomous Agent"
        # Verify MEMORY.md initialized from example
        assert (cog_dir / "MEMORY.md").read_text() == "# Memory Template"

    def test_unlink_cognitive_rules(self, tmp_path: Path):
        repo_dir = tmp_path / "repo"
        cog_dir = repo_dir / "cognitive"
        cog_dir.mkdir(parents=True)
        soul_md = cog_dir / "SOUL.md"
        soul_md.write_text("Persona: Jarvis Autonomous Agent")

        target_rules = tmp_path / "rules"
        target_rules.mkdir(parents=True)
        (target_rules / "SOUL.md").write_text("Persona: Jarvis Autonomous Agent")
        (target_rules / "AGENTS.md").write_text("Persona: Jarvis Autonomous Agent")
        (target_rules / "OTHER.md").write_text("Unrelated")

        # Dry run does not delete
        dry_unlinked = unlink_cognitive_rules(
            project_dir=repo_dir,
            rules_target_dirs=[str(target_rules)],
            dry_run=True,
        )
        assert len(dry_unlinked) >= 2
        assert (target_rules / "SOUL.md").exists()

        # Actual delete
        unlinked = unlink_cognitive_rules(
            project_dir=repo_dir,
            rules_target_dirs=[str(target_rules)],
            dry_run=False,
        )
        assert len(unlinked) >= 2
        assert not (target_rules / "SOUL.md").exists()
        assert not (target_rules / "AGENTS.md").exists()
        assert (target_rules / "OTHER.md").exists()

    def test_perform_uninstall_includes_rules_unlinked(self, tmp_path: Path):
        repo_dir = tmp_path / "repo"
        results = perform_uninstall(
            purge_personal=False,
            purge_agy=False,
            purge_service=False,
            dry_run=True,
            project_dir=repo_dir,
        )
        assert "rules_unlinked" in results
