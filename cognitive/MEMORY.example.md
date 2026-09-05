# Assistant Persistent Memory (Template)

This file stores long-term persistent facts, system topology, automation schedules, and user preferences.
The AI agent consults and updates this file across sessions to maintain context.

## Host & Network Topology
- Host: `primary-workstation` (Linux OS, local network).
- Remote Nodes: Remote compute clusters or secondary machines accessible via SSH alias (e.g., `ssh gpu-server`).

## Projects & File Hierarchy
- Standard workspace root: `~/projects/`
  - `~/projects/research/`: Machine Learning and Deep Learning research implementations.
  - `~/projects/experiments/`: Prototype scripts, architectural experiments, and model training.
  - `~/projects/audits/`: Automated repository auditing and static analysis tools.
  - `~/projects/setup/`: System automations, cron jobs, and environment maintenance.
- Python Environment: Dedicated virtual environment (e.g., `~/env` or project-local `venv/`).
- Telegram Bridge Daemon: `~/projects/jarvis-antigravity-agent/` managed via user `systemd`.

## Git Version Control & Automation Conventions
- Git Identity: `Assistant <assistant@local.machine>`, default branch `main`.
- Automation Policies:
  - Atomic, semantic commits (`feat(...)`, `fix(...)`, `refactor(...)`).
  - Strict exclusion of secrets, `.pem` keys, tokens, and database states in `.gitignore`.
  - Automated integrity checks prior to committing changes.

## Telegram Formatting & Communication Preferences
- Formatting Verified Rules:
  - Bold (`**text**`) and italic (`*text*`) individually supported.
  - Never combine bold and italic (`***text***`) due to parser incompatibility.
  - No Markdown `#` headings: use bold text prefixed with descriptive emojis (`📌 **Title**`).
  - No LaTeX formulas or markdown tables on mobile clients.
  - Rich and functional emoji usage (`💡`, `🚀`, `⚙️`, `✅`, `📌`, `⚠️`, `📊`, `🧠`) for visual hierarchy.
  - Concise, high information density, free of boilerplate pleasantries.
- Multi-step Task Tracking:
  - Accumulate executed steps in a live progress message (`+ 📝 Modifying: ...`, `+ ⚙️ Running: ...`).
  - Finalize progress status with `✅ Completed steps:` for full execution traceability.
