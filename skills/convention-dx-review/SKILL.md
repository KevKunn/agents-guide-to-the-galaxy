---
name: convention-dx-review
description: Review code-quality of current git changes (or specified files/module) against the local coding conventions AND DevExpress/XAF/XPO API fitness. Fans out convention checks to non-haiku subagents and DevExpress MCP checks to haiku subagents, then reports findings without committing. Use when the user asks to "check code quality", "review against conventions", "check DevExpress API usage / method fitness", or before committing PRM/XAF changes.
---

# Convention + DevExpress API Review

Two independent quality checks over a set of changed files, fanned out to subagents. **Report only — never commit or modify code unless the user explicitly confirms.**

## Scope

Default target = current uncommitted git changes. If the user names files, a module, or a commit range, use that instead.

1. Resolve the file list (`git status --porcelain`, `git diff --name-only`, or the user's selection).
2. Group files into logical batches (by module / concern / layer). One batch ≈ one subagent.

## Check 1 — Coding conventions (non-haiku subagents)

- Conventions live in `file://C:/Users/KevinCsele/.coding-conventions/` — `naming-conventions.md`, `xaf-xpo-guidelines.md`, `code-style.md`, `architecture-patterns.md`, `build-configuration.md`.
- Each subagent loads only the reference file(s) relevant to its batch and checks the batch against them.
- Subagents do NOT need to be haiku — use the default model.
- Each subagent returns: file, line, rule violated, severity, suggested fix.

## Check 2 — DevExpress API fitness (haiku subagents)

- For each non-trivial DevExpress / XAF / XPO API used in the changes, verify via the **DevExpress MCP server** whether it is the best-fitting method for the situation.
- Delegate these MCP calls to **haiku** subagents (use the `devexpress-mcp-proxy` agent) so the verbose MCP output stays out of the main context. The proxy returns a concise verdict.
- Each subagent returns per API: the call site, whether it is idiomatic/best-fit, and a better alternative if one exists.

## Process

1. Analyze + group files into batches.
2. Fan out both check types in parallel (independent batches → one message, multiple Agent calls).
   - Convention batches → default-model subagents.
   - DevExpress API batches → haiku `devexpress-mcp-proxy` subagents.
3. Collect findings. **Separate real issues from false positives** — known-good codebase patterns (e.g. `SetPropertyValue(nameof(X), ref _x, value)` in PRM BOs) are NOT violations; flag and discard them.
4. Report grouped by file/batch: ✅ passed, ⚠️ needs fixing (with fix), ℹ️ note. State convention findings and DevExpress findings separately.
5. Stop. Await user confirmation before any fix or commit.

## Notes

- MCP "unknown / not found" ≠ wrong API — the proxy may lack that doc. Cross-check against existing codebase usage before flagging.
- Conventions OVERRIDE general best-practice when they conflict.
