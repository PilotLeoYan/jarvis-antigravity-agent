---
name: skills-manager
description: Discover, read, create, and maintain agent skills adhering to the Open Agent Skills specification.
---

# Skills Management Guide

Agent skills are modular directories containing instructions, workflows, and reference materials that teach agents specific capabilities.

## Skill Directory Structure

Every skill lives in its own directory within `skills/` (project-level) or `~/.agents/skills/` (user-level):

```
skills/my-skill/
├── SKILL.md                 # Primary instruction manifest (required)
├── scripts/                 # Optional helper scripts (bash/python)
└── references/              # Optional documentation and examples
```

## Creating a New Skill

1. **Frontmatter Specification**:
   Every `SKILL.md` must start with YAML frontmatter containing:
   - `name`: Lowercase alphanumeric identifier with dashes (e.g. `docker-operations`).
   - `description`: A clear 1-2 sentence description explaining when and why to use the skill.

2. **Content Guidelines**:
   - Provide concrete, copy-pasteable CLI commands or code examples.
   - Specify edge cases, common pitfalls, and security considerations.
   - Keep instructions concise, factual, and strictly relevant.

3. **Example `SKILL.md`**:
   ```markdown
   ---
   name: sqlite-analytics
   description: Query and analyze local SQLite databases using sqlite3 CLI.
   ---

   # SQLite Analytics

   Instructions for querying and dumping SQLite databases safely.

   ## Common Commands
   - Query in column format:
     ```bash
     sqlite3 -header -column database.db "SELECT * FROM users LIMIT 10;"
     ```
   ```

## Finding & Reading Skills
- Inspect available skills: `ls -la skills/` and `ls -la ~/.agents/skills/`
- Read a skill's instructions: `cat skills/<skill-name>/SKILL.md`
- Search community skills: `npx skills find [query]`
