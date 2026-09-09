from pathlib import Path

from jarvis_antigravity_agent.skills_inspector import (
    format_skills_markdown,
    list_global_skills,
    parse_skill_metadata,
)


class TestSkillsInspector:
    def test_parse_skill_metadata_valid_frontmatter(self, tmp_path: Path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: test-skill\n"
            "description: A test skill for validating metadata parsing.\n"
            "---\n\n"
            "# Skill Documentation\n",
            encoding="utf-8",
        )

        meta = parse_skill_metadata(skill_md)
        assert meta["name"] == "test-skill"
        assert meta["description"] == "A test skill for validating metadata parsing."

    def test_parse_skill_metadata_missing_file(self, tmp_path: Path):
        missing_md = tmp_path / "nonexistent" / "SKILL.md"
        meta = parse_skill_metadata(missing_md)
        assert meta["name"] == "nonexistent"
        assert meta["description"] == "No description provided."

    def test_list_global_skills_custom_dirs(self, tmp_path: Path):
        dir1 = tmp_path / "global_user"
        dir1.mkdir()
        s1 = dir1 / "skill-alpha"
        s1.mkdir()
        (s1 / "SKILL.md").write_text(
            "---\nname: skill-alpha\ndescription: Alpha skill description\n---\n",
            encoding="utf-8",
        )

        dir2 = tmp_path / "builtin"
        dir2.mkdir()
        s2 = dir2 / "skill-beta"
        s2.mkdir()
        (s2 / "SKILL.md").write_text(
            "---\nname: skill-beta\ndescription: Beta skill description\n---\n",
            encoding="utf-8",
        )

        custom_dirs = [("User", str(dir1)), ("Builtin", str(dir2))]
        skills = list_global_skills(custom_dirs=custom_dirs)

        assert len(skills) == 2
        names = [s["name"] for s in skills]
        assert "skill-alpha" in names
        assert "skill-beta" in names

    def test_format_skills_markdown_output(self, tmp_path: Path):
        skills_mock = [
            {
                "name": "sample-skill",
                "description": "Sample description of the skill.",
                "source": "Global User",
                "path": "/path/to/sample",
            }
        ]
        md = format_skills_markdown(skills_mock)
        assert "Google Antigravity Global Skills" in md
        assert "sample-skill" in md
        assert "Global User" in md
        assert "Sample description" in md

    def test_format_skills_markdown_empty(self):
        md = format_skills_markdown([])
        assert "No global skills detected" in md

    def test_parse_skill_metadata_no_frontmatter_body_fallback(self, tmp_path: Path):
        skill_dir = tmp_path / "custom-tool"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "# Custom Tool Title\n\n"
            "This tool provides autonomous testing workflows for the project.\n\n"
            "## Details\nSome details here.\n",
            encoding="utf-8",
        )
        meta = parse_skill_metadata(skill_md)
        assert meta["name"] == "custom-tool"
        assert (
            meta["description"]
            == "This tool provides autonomous testing workflows for the project."
        )

    def test_format_skills_markdown_escapes_underscores(self):
        skills_mock = [
            {
                "name": "generative_ui",
                "description": "Interactive HTML_widgets in chat.",
                "source": "Built-in",
            }
        ]
        md = format_skills_markdown(skills_mock)
        assert "generative\\_ui" in md
        assert "HTML\\_widgets" in md
