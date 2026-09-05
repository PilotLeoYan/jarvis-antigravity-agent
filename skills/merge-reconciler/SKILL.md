---
name: merge-reconciler
description: Systematic Git merge conflict reconciliation preserving technical intent from both branches.
---

# Git Merge Reconciler

Structured methodology to resolve merge conflicts while maintaining functional correctness:

1. Identify conflicting files via `git status`.
2. Analyze conflicting blocks denoted by `<<<<<<<`, `=======`, and `>>>>>>>`.
3. Reconcile logic by integrating valid changes without discarding critical upstream logic.
4. Execute test suites and linters to verify reconciled code integrity.
5. Stage resolved files (`git add`) and finalize the merge commit.
