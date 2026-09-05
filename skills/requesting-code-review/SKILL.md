---
name: requesting-code-review
description: Pre-commit technical review checklist: security scanning, code quality standards, and regression detection.
---

# Pre-Commit Code Review

Mandatory verification checklist before committing code:
1. **Git Diff Inspection:** Review `git diff` line by line for unintended artifacts.
2. **Secret Scanning:** Verify no API tokens, private keys, or passwords are staged.
3. **Automated Testing:** Run relevant test suites and ensure 100% pass rate.
4. **Conventional Commits:** Format commit messages clearly (`feat:`, `fix:`, `refactor:`, `docs:`).
