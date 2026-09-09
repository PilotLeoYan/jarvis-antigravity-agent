import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from jarvis_antigravity_agent.constants import Constants

logger = logging.getLogger(Constants.LOGGER_NAME)

PROTECTED_RELATIVE_FILES = [
    "config.yaml",
    "config.yml",
    "config.json",
    ".env",
    "state.json",
    "cognitive/MEMORY.md",
]


def get_repo_root(start_dir: Path | str | None = None) -> Path:
    """Find the root directory of the git repository."""
    start = Path(start_dir) if start_dir else Path(Constants.BASE_DIR)
    current = start.resolve()
    while current != current.parent:
        if (current / ".git").is_dir():
            return current
        current = current.parent
    return start.resolve()


def check_for_updates(
    repo_dir: Path | str | None = None,
    remote: str = "origin",
    branch: str = "main",
) -> tuple[bool, str, str, str]:
    """Check if remote origin has newer commits than local HEAD.

    Returns:
        (has_updates, local_sha, remote_sha, log_summary)
    """
    root = get_repo_root(repo_dir)
    git_bin = shutil.which("git") or "git"
    try:
        # Fetch remote safely
        subprocess.run(  # noqa: S603, S607
            [git_bin, "fetch", remote, branch],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )

        local_sha = subprocess.check_output(  # noqa: S603, S607
            [git_bin, "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            timeout=10,
        ).strip()

        remote_sha = subprocess.check_output(  # noqa: S603, S607
            [git_bin, "rev-parse", f"{remote}/{branch}"],
            cwd=root,
            text=True,
            timeout=10,
        ).strip()

        if local_sha == remote_sha:
            return False, local_sha[:8], remote_sha[:8], "System is up to date."

        # Fetch commit summary
        log_out = subprocess.check_output(  # noqa: S603, S607
            [
                git_bin,
                "log",
                f"{local_sha}..{remote_sha}",
                "--oneline",
                "-n",
                "5",
            ],
            cwd=root,
            text=True,
            timeout=10,
        ).strip()

        return True, local_sha[:8], remote_sha[:8], log_out

    except subprocess.CalledProcessError as e:
        logger.error("Git error checking for updates: %s", e.stderr)
        err_msg = f"Error checking updates: {e.stderr.strip()}"
        return False, "unknown", "unknown", err_msg
    except Exception as e:
        logger.error("Unexpected error checking for updates: %s", e)
        return False, "unknown", "unknown", f"Unexpected error: {e}"


def _snapshot_protected_files(root: Path) -> dict[str, bytes]:
    """Capture raw byte content of protected personal configuration files."""
    snapshots: dict[str, bytes] = {}
    for rel_path in PROTECTED_RELATIVE_FILES:
        target = root / rel_path
        if target.is_file():
            try:
                snapshots[rel_path] = target.read_bytes()
            except Exception as e:
                logger.warning("Could not snapshot %s: %s", rel_path, e)
    return snapshots


def _restore_protected_files(root: Path, snapshots: dict[str, bytes]) -> None:
    """Verify and restore any modified or removed protected personal files."""
    for rel_path, content in snapshots.items():
        target = root / rel_path
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.is_file() or target.read_bytes() != content:
                target.write_bytes(content)
                logger.info("Restored protected file: %s", rel_path)
        except Exception as e:
            logger.error("Failed to restore protected file %s: %s", rel_path, e)


def apply_update(
    repo_dir: Path | str | None = None,
    remote: str = "origin",
    branch: str = "main",
) -> tuple[bool, str]:
    """Pull remote updates safely preserving configs and user files.

    Returns:
        (success, status_message)
    """
    root = get_repo_root(repo_dir)
    has_update, local_sha, remote_sha, log_summary = check_for_updates(
        repo_dir, remote, branch
    )
    if not has_update:
        return False, f"Already up to date ({local_sha})."

    snapshots = _snapshot_protected_files(root)
    git_bin = shutil.which("git") or "git"
    try:
        # Fast-forward pull
        pull_proc = subprocess.run(  # noqa: S603, S607
            [git_bin, "merge", "--ff-only", f"{remote}/{branch}"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if pull_proc.returncode != 0:
            err = pull_proc.stderr.strip()
            logger.error("Fast-forward merge failed: %s", err)
            _restore_protected_files(root, snapshots)
            return (
                False,
                f"Update failed during merge: {err}\n"
                f"Configuration and local files remain untouched.",
            )

        # Update dependencies via uv if installed
        uv_bin = shutil.which("uv")
        if uv_bin:
            sync_proc = subprocess.run(  # noqa: S603, S607
                [uv_bin, "sync"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if sync_proc.returncode != 0:
                logger.warning("uv sync returned non-zero: %s", sync_proc.stderr)

        # Ensure all protected files remain completely untouched
        _restore_protected_files(root, snapshots)

        msg = (
            f"Successfully updated from `{local_sha}` to `{remote_sha}`.\n\n"
            f"*Changelog:*\n{log_summary}\n\n"
            f"_Personal configurations and state files preserved intact._"
        )
        logger.info("Successfully applied update to %s", remote_sha)
        return True, msg

    except Exception as e:
        _restore_protected_files(root, snapshots)
        logger.exception("Failed to apply update: %s", e)
        return False, f"Exception applying update: {e}"


def restart_daemon() -> None:
    """Trigger process restart.

    Uses SIGTERM exit code (143) which systemd automatically restarts,
    or falls back to os.execv for direct foreground runs.
    """
    logger.info("Restarting Jarvis process to apply code updates...")
    if "INVOCATION_ID" in os.environ:
        # Running under systemd unit - exiting with 143 triggers systemd restart
        sys.exit(143)
    else:
        # Standalone process - reload via execv
        try:
            os.execv(sys.executable, [sys.executable] + sys.argv)  # noqa: S606
        except Exception:
            sys.exit(143)


def main_cli() -> None:
    """CLI entry point for jarvis-update."""
    parser = argparse.ArgumentParser(
        description="Jarvis Antigravity Agent Safe Self-Updater"
    )
    parser.add_argument(
        "--check", action="store_true", help="Check for available updates only"
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Restart the daemon after successful update",
    )
    parser.add_argument(
        "--remote", default="origin", help="Git remote name (default: origin)"
    )
    parser.add_argument(
        "--branch", default="main", help="Git branch name (default: main)"
    )

    args = parser.parse_args()

    if args.check:
        has_up, loc, rem, summary = check_for_updates(
            remote=args.remote, branch=args.branch
        )
        if has_up:
            print(f"Update available: {loc} -> {rem}\n\nRecent commits:\n{summary}")
        else:
            print(f"Up to date at {loc}.")
        return

    success, msg = apply_update(remote=args.remote, branch=args.branch)
    print(msg)
    if success and args.restart:
        restart_daemon()


if __name__ == "__main__":
    main_cli()
