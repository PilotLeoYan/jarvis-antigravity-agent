---
name: systematic-debugging
description: 4-phase methodology for investigating and resolving bugs: reproduce, isolate, hypothesize, and verify.
---

# Systematic Debugging

A disciplined 4-phase methodology to eliminate root causes without introducing regressions.

## Phase 1: Reproduce
- Create a minimal, deterministic command or test script reproducing the failure.
- Capture exact stack traces, stderr outputs, and exit codes.

## Phase 2: Isolate
- Determine the failure boundary by contrasting working vs failing inputs.
- Inspect logs, process environments, and network states before editing code.

## Phase 3: Hypothesize & Test
- Formulate a precise hypothesis explaining why the bug occurs.
- Design a targeted test specifically to validate or refute the hypothesis.

## Phase 4: Correct & Verify
- Implement the minimal sufficient fix addressing the root cause.
- Run the full test suite to guarantee zero collateral regressions.
