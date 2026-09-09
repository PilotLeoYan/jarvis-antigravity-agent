import logging
import os
from pathlib import Path
from typing import Any

from jarvis_antigravity_agent.constants import Constants

logger = logging.getLogger(Constants.LOGGER_NAME)

GLOBAL_SKILL_DIRECTORIES = [
    ("Global User", os.path.expanduser("~/.agents/skills")),
    ("Global Config", os.path.expanduser("~/.gemini/config/skills")),
    ("Built-in", os.path.expanduser("~/.gemini/antigravity/builtin/skills")),
]


def parse_skill_metadata(skill_md_path: Path) -> dict[str, str]:
    """Extract name and description from a SKILL.md frontmatter."""
    metadata: dict[str, str] = {
        "name": skill_md_path.parent.name,
        "description": "No description provided.",
    }
    if not skill_md_path.is_file():
        return metadata

    try:
        with open(skill_md_path, encoding="utf-8", errors="ignore") as f:
            content = f.read(4096)

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                lines = frontmatter.splitlines()
                current_key: str | None = None
                multiline_val: list[str] = []

                for line in lines:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    if ":" in line and not line.startswith((" ", "\t")):
                        if current_key and multiline_val:
                            metadata[current_key] = " ".join(multiline_val).strip()
                            multiline_val = []
                        k, v = line.split(":", 1)
                        current_key = k.strip()
                        v_str = v.strip().strip("'\"")
                        if v_str in {">", ">-", "|", "|-"}:
                            multiline_val = []
                        else:
                            metadata[current_key] = v_str
                    elif current_key and line.startswith((" ", "\t")):
                        multiline_val.append(stripped)

                if current_key and multiline_val:
                    metadata[current_key] = " ".join(multiline_val).strip()

        # Fallback to first non-header markdown paragraph if no description
        # was specified in the frontmatter
        if metadata.get("description") in {None, "", "No description provided."}:
            for block in content.split("\n\n"):
                stripped_block = block.strip()
                if stripped_block and not stripped_block.startswith(("#", "---")):
                    metadata["description"] = " ".join(
                        stripped_block.splitlines()
                    ).strip()
                    break
    except Exception as e:
        logger.debug("Failed parsing skill metadata from %s: %s", skill_md_path, e)

    return metadata


def list_global_skills(
    custom_dirs: list[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Scan all standard Antigravity global skill directories."""
    directories = custom_dirs or GLOBAL_SKILL_DIRECTORIES
    seen_names: set[str] = set()
    skills: list[dict[str, Any]] = []

    for source_label, dir_path in directories:
        p = Path(dir_path)
        if not p.is_dir():
            continue

        try:
            for item in sorted(p.iterdir()):
                if not item.is_dir():
                    continue

                skill_name = item.name
                skill_md = item / "SKILL.md"
                meta = parse_skill_metadata(skill_md) if skill_md.is_file() else {}
                display_name = meta.get("name") or skill_name
                desc = meta.get("description") or "No description provided."

                # If duplicate name across origins, record source or deduplicate
                key = display_name.lower()
                if key in seen_names:
                    continue
                seen_names.add(key)

                skills.append(
                    {
                        "name": display_name,
                        "description": desc,
                        "source": source_label,
                        "path": str(item),
                    }
                )
        except (PermissionError, OSError):
            continue

    skills.sort(key=lambda s: s["name"].lower())
    return skills


def format_skills_markdown(
    skills: list[dict[str, Any]] | None = None,
    custom_dirs: list[tuple[str, str]] | None = None,
) -> str:
    """Format global skills into clear Telegram Markdown."""
    skill_list = (
        skills if skills is not None else list_global_skills(custom_dirs=custom_dirs)
    )

    if not skill_list:
        return (
            "🧠 *Google Antigravity Global Skills*\n\n"
            "No global skills detected in `~/.agents/skills` or "
            "`~/.gemini/config/skills`.\n"
            "_Deploy new skills adhering to Open Agent Skills specification._"
        )

    lines: list[str] = [
        f"🧠 *Google Antigravity Global Skills* ({len(skill_list)} active)\n"
    ]

    for s in skill_list:
        name = s["name"]
        source = s.get("source", "Global")
        desc = s.get("description", "No description provided.")
        # Truncate long descriptions to keep messages neat
        if len(desc) > 180:
            desc = desc[:177] + "..."

        escaped_name = name.replace("_", "\\_").replace("*", "\\*")
        clean_desc = desc.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[")
        lines.append(f"• *{escaped_name}* `({source})`\n  _{clean_desc}_\n")

    lines.append(
        "ℹ️ _Skills teach autonomous reasoning capabilities across all AGY sessions._"
    )
    return "\n".join(lines)
