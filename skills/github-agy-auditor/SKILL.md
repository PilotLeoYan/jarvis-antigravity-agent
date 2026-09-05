---
name: github-agy-auditor
description: Orchestrate automated GitHub repository audits using agy agents and GitHub App authentication.
---

# GitHub AGY Auditor

Automated pipeline for scanning GitHub repositories, identifying security vulnerabilities, outdated patterns, and code smells via Antigravity CLI (`agy`).

## Pipeline Architecture
- **Orchestrator**: Python orchestration script managing repository cloning, git diff analysis, and batch runs.
- **Authentication**: GitHub App private key (`.pem`) or GitHub Personal Access Token.
- **Telegram Notification**: Push delivery of summarized audit findings via `send_message.py`.

## Execution
```bash
python -m audits.audit_orchestrator
```
