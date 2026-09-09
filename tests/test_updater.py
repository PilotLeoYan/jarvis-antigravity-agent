import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from jarvis_antigravity_agent.updater import (
    PROTECTED_RELATIVE_FILES,
    apply_update,
    check_for_updates,
    get_repo_root,
)


class TestUpdater:
    def test_protected_files_contains_essential_configs(self):
        assert "config.yaml" in PROTECTED_RELATIVE_FILES
        assert ".env" in PROTECTED_RELATIVE_FILES
        assert "state.json" in PROTECTED_RELATIVE_FILES
        assert "cognitive/MEMORY.md" in PROTECTED_RELATIVE_FILES

    def test_get_repo_root(self, tmp_path: Path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        sub_dir = tmp_path / "src" / "deep"
        sub_dir.mkdir(parents=True)

        root = get_repo_root(sub_dir)
        assert root == tmp_path

    @patch("subprocess.run")
    @patch("subprocess.check_output")
    def test_check_for_updates_already_up_to_date(
        self, mock_check_output, mock_run, tmp_path: Path
    ):
        mock_run.return_value = MagicMock(returncode=0)
        mock_check_output.side_effect = [
            "commit_abc123456\n",  # local_sha
            "commit_abc123456\n",  # remote_sha
        ]

        has_updates, local_sha, remote_sha, summary = check_for_updates(tmp_path)
        assert has_updates is False
        assert local_sha == "commit_a"
        assert remote_sha == "commit_a"
        assert "up to date" in summary

    @patch("subprocess.run")
    @patch("subprocess.check_output")
    def test_check_for_updates_new_commit_available(
        self, mock_check_output, mock_run, tmp_path: Path
    ):
        mock_run.return_value = MagicMock(returncode=0)
        mock_check_output.side_effect = [
            "old_commit_111111\n",  # local_sha
            "new_commit_222222\n",  # remote_sha
            "222222 feat: new capability added\n",  # git log
        ]

        has_updates, local_sha, remote_sha, summary = check_for_updates(tmp_path)
        assert has_updates is True
        assert local_sha == "old_comm"
        assert remote_sha == "new_comm"
        assert "feat: new capability" in summary

    @patch("subprocess.run")
    @patch("subprocess.check_output")
    def test_check_for_updates_git_error(
        self, mock_check_output, mock_run, tmp_path: Path
    ):
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["git", "fetch"], stderr="Could not resolve host"
        )

        has_updates, local_sha, remote_sha, summary = check_for_updates(tmp_path)
        assert has_updates is False
        assert "Could not resolve host" in summary

    @patch("jarvis_antigravity_agent.updater.check_for_updates")
    def test_apply_update_no_updates(self, mock_check, tmp_path: Path):
        mock_check.return_value = (False, "abc", "abc", "Up to date")
        success, msg = apply_update(tmp_path)
        assert success is False
        assert "Already up to date" in msg

    @patch("jarvis_antigravity_agent.updater.check_for_updates")
    @patch("subprocess.run")
    def test_apply_update_success(self, mock_run, mock_check, tmp_path: Path):
        mock_check.return_value = (True, "old123", "new456", "commit log")
        mock_run.return_value = MagicMock(returncode=0)

        success, msg = apply_update(tmp_path)
        assert success is True
        assert "Successfully updated" in msg
        assert "Personal configurations and state files preserved" in msg

    @patch("jarvis_antigravity_agent.updater.check_for_updates")
    @patch("subprocess.run")
    def test_apply_update_merge_failure(self, mock_run, mock_check, tmp_path: Path):
        mock_check.return_value = (True, "old123", "new456", "commit log")
        mock_run.return_value = MagicMock(
            returncode=1, stderr="Automatic fast-forward not possible"
        )

        success, msg = apply_update(tmp_path)
        assert success is False
        assert "Update failed during merge" in msg
        assert "remain untouched" in msg
