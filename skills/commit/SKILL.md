---
name: commit
description: Create git commits the way this user prefers, in any repository — a single Conventional Commits subject line (no body, no AI/co-author trailer), selective staging of only the files that belong to the change, and never discarding unstaged work to exclude it. Use when the user asks to commit changes, make a commit, or stage and commit.
---

# Commit changes

Applies in **every** repo unless a project explicitly overrides it. Only commit when the user asks; prefer a new commit over amending an existing one.

## Message format

- **One subject line, nothing else.** Conventional Commits: `type: description` (`feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`, `build`, `ci`). No body, no bullet list, no explanatory paragraphs.
- **Issue/ticket reference** when the project uses one: `feat: [KEY-123] description`. Derive the key from the branch name (e.g. `feat/PRM-1623-…` → `PRM-1623`) or the project's CLAUDE.md conventions. Omit it in repos that don't use tickets.
- **No trailers.** No `Co-Authored-By`, no "Generated with …" line — unless the user explicitly asks for them.
- Keep it brief and imperative.

## Staging discipline

- Stage **only** the files that belong to this one logical change. Never `git add -A` / `git add .` blindly.
- To keep something out of the commit, **leave it unstaged** — do **not** `git checkout --` / `git restore` / overwrite to discard it. Unstaged working-tree edits are the user's; destroying them is data loss. A `// revert before commit`-style note is not authorization to delete a change. If something genuinely looks like it should be reverted, surface it and ask.
- Don't sweep tooling/agent config into a feature commit: `CLAUDE.md`, `AGENTS.md`, `.claude/`, `.codex/`, editor/settings files, scratch docs — leave them unstaged unless that config **is** the change.
- After committing a subset, tell the user which paths you deliberately left unstaged so they know what's still pending.

## Branch

- If on the default branch (`main`/`master`), create a feature branch first.
- Branch naming when the project uses tickets: `feat/KEY-123-short-desc` or `fix/KEY-123-short-desc`.

## Checklist

1. `git status` + `git diff` — know exactly what changed.
2. Select the files for this change; `git add` exactly those.
3. Commit with a single `-m` subject line.
4. Report the commit hash/subject and any paths left unstaged on purpose.
