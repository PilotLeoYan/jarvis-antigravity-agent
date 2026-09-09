import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# If executed directly as a script, ensure src is in sys.path
_SRC_DIR = str(Path(__file__).resolve().parent.parent)
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

try:
    from jarvis_antigravity_agent.constants import Constants

    LOGGER_NAME = Constants.LOGGER_NAME
    DEFAULT_REPO_DIR = Path(Constants.BASE_DIR)
except ImportError:
    LOGGER_NAME = "jarvis-bridge"
    DEFAULT_REPO_DIR = Path(__file__).resolve().parent.parent.parent

logger = logging.getLogger(LOGGER_NAME)

SYSTEMD_SERVICE_FILE = os.path.expanduser("~/.config/systemd/user/agy-telegram.service")
SERVICE_NAME = "agy-telegram.service"

DEFAULT_PERSONAL_FILES = [
    "config.yaml",
    "config.yml",
    "config.json",
    "state.json",
    ".env",
    "jarvis.log",
]

DEFAULT_AGY_DIRECTORIES = [
    os.path.expanduser("~/.gemini"),
    os.path.expanduser("~/.agents"),
    os.path.expanduser("~/.config/Antigravity"),
    os.path.expanduser("~/.config/antigravity"),
    os.path.expanduser("~/.cache/antigravity"),
    os.path.expanduser("~/.antigravity"),
]

DEFAULT_BINARIES = [
    "jarvis-antigravity-agent",
    "jarvis-send-message",
    "jarvis-spawn-agent",
    "jarvis-mcp",
    "jarvis-update",
    "jarvis-uninstall",
]


def stop_and_disable_service(
    service_name: str = SERVICE_NAME,
    service_file: str = SYSTEMD_SERVICE_FILE,
    dry_run: bool = False,
) -> bool:
    """Stop, disable, and remove user systemd service."""
    systemctl = shutil.which("systemctl") or "/bin/systemctl"
    success = True

    if (
        os.path.isfile(service_file)
        or os.path.islink(service_file)
        or shutil.which("systemctl")
    ):
        if dry_run:
            print(f"[dry-run] Would stop and disable systemd service: {service_name}")
            print(f"[dry-run] Would remove service file: {service_file}")
            return True

        # Stop service
        try:
            subprocess.run(  # noqa: S603
                [systemctl, "--user", "stop", service_name],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(  # noqa: S603
                [systemctl, "--user", "disable", service_name],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.debug("Failed stopping/disabling service: %s", e)
            success = False

        # Remove service file
        if os.path.isfile(service_file) or os.path.islink(service_file):
            try:
                os.remove(service_file)
                print(f"[+] Removed service file: {service_file}")
            except Exception as e:
                logger.error("Failed to remove %s: %s", service_file, e)
                success = False

        # Reload daemon
        try:
            subprocess.run(  # noqa: S603
                [systemctl, "--user", "daemon-reload"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.debug("Failed daemon-reload: %s", e)

    return success


def _is_subpath(child: Path, parent: Path) -> bool:
    """Check if child resolves inside parent directory without false prefix matches."""
    try:
        return child.resolve().is_relative_to(parent.resolve())
    except Exception:
        try:
            child.resolve().relative_to(parent.resolve())
            return True
        except ValueError:
            return False


def unlink_project_skills(
    project_dir: Path | str | None = None,
    skills_target_dir: str | list[str] | None = None,
    dry_run: bool = False,
) -> list[str]:
    """Remove symlinks pointing to this project repository across global skill dirs."""
    base_dir = Path(project_dir or DEFAULT_REPO_DIR).resolve()
    if skills_target_dir is None:
        target_dirs = [
            os.path.expanduser("~/.agents/skills"),
            os.path.expanduser("~/.gemini/config/skills"),
        ]
    elif isinstance(skills_target_dir, str):
        target_dirs = [os.path.expanduser(skills_target_dir)]
    else:
        target_dirs = [os.path.expanduser(d) for d in skills_target_dir]

    unlinked: list[str] = []

    for s_dir in target_dirs:
        target_skills = Path(s_dir)
        if not target_skills.is_dir():
            continue

        for item in target_skills.iterdir():
            if item.is_symlink():
                try:
                    resolved = item.resolve()
                    if _is_subpath(resolved, base_dir):
                        if dry_run:
                            print(
                                f"[dry-run] Would remove skill symlink: "
                                f"{item} -> {resolved}"
                            )
                        else:
                            item.unlink()
                            print(f"[+] Removed skill symlink: {item.name}")
                        unlinked.append(item.name)
                except Exception as e:
                    logger.debug("Failed checking symlink %s: %s", item, e)

    return unlinked


def unlink_project_binaries(
    project_dir: Path | str | None = None,
    bin_dir: Path | str | None = None,
    dry_run: bool = False,
) -> list[str]:
    """Remove symlinks in ~/.local/bin pointing to this project repository."""
    base_dir = Path(project_dir or DEFAULT_REPO_DIR).resolve()
    target_bin = Path(bin_dir or os.path.expanduser("~/.local/bin")).resolve()
    if not target_bin.is_dir():
        return []

    unlinked: list[str] = []

    for binary_name in DEFAULT_BINARIES:
        target = target_bin / binary_name
        if target.is_symlink():
            try:
                resolved = target.resolve()
                if _is_subpath(resolved, base_dir):
                    if dry_run:
                        print(
                            f"[dry-run] Would remove binary symlink: "
                            f"{target} -> {resolved}"
                        )
                    else:
                        target.unlink()
                        print(f"[+] Removed binary symlink: {target.name}")
                    unlinked.append(target.name)
            except Exception as e:
                logger.debug("Failed checking binary symlink %s: %s", target, e)

    return unlinked


def link_project_binaries(
    project_dir: Path | str | None = None,
    bin_dir: Path | str | None = None,
) -> list[str]:
    """Create symlinks in ~/.local/bin pointing to project virtualenv entrypoints."""
    base_dir = Path(project_dir or DEFAULT_REPO_DIR).resolve()
    target_bin = Path(bin_dir or os.path.expanduser("~/.local/bin")).resolve()
    target_bin.mkdir(parents=True, exist_ok=True)

    venv_bin = base_dir / ".venv" / "bin"
    if not venv_bin.is_dir():
        venv_bin = base_dir / "venv" / "bin"
    if not venv_bin.is_dir():
        return []

    linked: list[str] = []
    for binary_name in DEFAULT_BINARIES:
        src = venv_bin / binary_name
        if src.is_file():
            dst = target_bin / binary_name
            try:
                if dst.is_symlink() or dst.exists():
                    dst.unlink()
                dst.symlink_to(src)
                dst.chmod(0o755)
                linked.append(binary_name)
            except Exception as e:
                logger.debug("Failed creating symlink %s -> %s: %s", dst, src, e)

    return linked


def purge_personal_data(
    base_dir: Path | str | None = None,
    extra_files: list[str] | None = None,
    dry_run: bool = False,
) -> list[str]:
    """Delete personal configuration files, states, logs, and voice caches."""
    root = Path(base_dir or DEFAULT_REPO_DIR).resolve()
    targets = list(DEFAULT_PERSONAL_FILES)
    if extra_files:
        targets.extend(extra_files)

    # Also include explicit paths from environment if set
    for env_k in ("JARVIS_CONFIG_PATH", "AGY_TELEGRAM_CONFIG"):
        env_val = os.environ.get(env_k)
        if env_val and env_val not in targets:
            targets.append(env_val)

    removed: list[str] = []
    seen: set[str] = set()

    for f_name in targets:
        p = Path(f_name)
        target_path = p if p.is_absolute() else (root / f_name)
        canon = str(target_path)
        if canon in seen:
            continue
        seen.add(canon)

        if target_path.is_file() or target_path.is_symlink():
            if dry_run:
                print(f"[dry-run] Would delete personal file: {target_path}")
            else:
                try:
                    target_path.unlink()
                    print(f"[+] Deleted personal file: {target_path.name}")
                except Exception as e:
                    logger.error("Failed to delete %s: %s", target_path, e)
            removed.append(str(target_path))

    # Also clean up any voice temp files (*.oga, *.wav) in root
    for ext in ("*.oga", "*.wav"):
        for p in root.glob(ext):
            canon = str(p)
            if canon not in seen:
                seen.add(canon)
                if dry_run:
                    print(f"[dry-run] Would delete voice temp file: {p}")
                else:
                    p.unlink(missing_ok=True)
                removed.append(canon)

    return removed


def purge_agy_data(
    directories: list[str] | None = None,
    dry_run: bool = False,
) -> list[str]:
    """Delete Google Antigravity data directories (~/.gemini, ~/.agents, etc.)."""
    target_dirs = directories or DEFAULT_AGY_DIRECTORIES
    purged: list[str] = []

    for d_path in target_dirs:
        resolved = Path(d_path).resolve()
        if resolved.exists():
            if dry_run:
                print(f"[dry-run] Would delete AGY directory: {resolved}")
            else:
                try:
                    if resolved.is_dir():
                        shutil.rmtree(resolved)
                    else:
                        resolved.unlink()
                    print(f"[+] Deleted AGY directory: {resolved}")
                except Exception as e:
                    logger.error("Failed to delete %s: %s", resolved, e)
            purged.append(str(resolved))

    return purged


def perform_uninstall(
    purge_personal: bool = False,
    purge_agy: bool = False,
    purge_service: bool = True,
    dry_run: bool = False,
    project_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Perform full or selective uninstallation of Jarvis Antigravity Agent."""
    target_project_dir = Path(project_dir or DEFAULT_REPO_DIR).resolve()
    results: dict[str, Any] = {
        "service_stopped": False,
        "skills_unlinked": [],
        "binaries_unlinked": [],
        "personal_files_removed": [],
        "agy_dirs_purged": [],
    }

    print("==========================================================")
    print("   Jarvis Antigravity Agent - Uninstaller")
    print("==========================================================")

    if dry_run:
        print("[*] Running in DRY-RUN mode. No changes will be made.\n")

    if purge_service:
        results["service_stopped"] = stop_and_disable_service(dry_run=dry_run)

    results["skills_unlinked"] = unlink_project_skills(
        project_dir=target_project_dir, dry_run=dry_run
    )

    results["binaries_unlinked"] = unlink_project_binaries(
        project_dir=target_project_dir, dry_run=dry_run
    )

    if purge_personal:
        results["personal_files_removed"] = purge_personal_data(
            base_dir=target_project_dir, dry_run=dry_run
        )

    if purge_agy:
        results["agy_dirs_purged"] = purge_agy_data(dry_run=dry_run)

    print("\n==========================================================")
    print("   Uninstallation Complete!")
    print("==========================================================")
    return results


def main_cli() -> None:
    """CLI entry point for jarvis-uninstall command."""
    parser = argparse.ArgumentParser(
        description=(
            "Uninstall Jarvis Antigravity Agent with options to delete "
            "personal configuration and Antigravity (agy) data."
        )
    )
    parser.add_argument(
        "--project-dir",
        "-d",
        default=None,
        help="Path to Jarvis project repository directory (default: auto-detected)",
    )
    parser.add_argument(
        "--purge-personal",
        action="store_true",
        help="Delete personal data (config.yaml, state.json, tokens, caches)",
    )
    parser.add_argument(
        "--purge-agy",
        action="store_true",
        help=(
            "Delete Google Antigravity data "
            "(~/.gemini, ~/.agents, ~/.config/Antigravity)"
        ),
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Purge everything: systemd daemon, personal data, and all AGY data",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the uninstallation without making any changes",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Non-interactive mode (proceed without confirmation prompts)",
    )

    args = parser.parse_args()

    purge_personal = args.purge_personal or args.all
    purge_agy = args.purge_agy or args.all

    # Interactive prompts if no flags specified and not in non-interactive mode
    if not (args.purge_personal or args.purge_agy or args.all or args.yes):
        print(
            "This tool will remove the Jarvis Antigravity Agent systemd daemon "
            "and linked skills."
        )
        ans_personal = (
            input("Delete personal data (config.yaml, tokens, session state)? [y/N]: ")
            .strip()
            .lower()
        )
        purge_personal = ans_personal in {"y", "yes"}

        ans_agy = (
            input(
                "Delete Google Antigravity (agy) data (~/.gemini, ~/.agents)? [y/N]: "
            )
            .strip()
            .lower()
        )
        purge_agy = ans_agy in {"y", "yes"}

        confirm = input("\nProceed with uninstallation? [Y/n]: ").strip().lower()
        if confirm in {"n", "no"}:
            print("Aborted.")
            sys.exit(0)

    perform_uninstall(
        purge_personal=purge_personal,
        purge_agy=purge_agy,
        purge_service=True,
        dry_run=args.dry_run,
        project_dir=args.project_dir,
    )


if __name__ == "__main__":
    main_cli()
