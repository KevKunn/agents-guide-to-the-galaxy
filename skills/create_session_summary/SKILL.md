---
name: create_session_summary
description: Save an engineering journal of the current session, documenting approaches tried, why they succeeded or failed, decisions, verification, and remaining work. Update the CLAUDE.md summary table only when explicitly requested.
disable-model-invocation: true
---

# Create Session Summary

Create a detailed engineering journal of the available conversation. Preserve both the current state and the meaningful history of how it was reached, including failed, reverted, and superseded approaches. The summary should support future development and explain why one approach worked better than another.

## Content rules

- Capture the user's requests, corrections, constraints, and decisions. Later corrections take precedence; explain changes in direction when relevant.
- Record the sequence of meaningful attempts, including the motivation, implementation, observed results, and reason each was retained, revised, or rejected. Preserve useful failures even when the final task succeeded.
- Provide concise, evidence-based decision rationale in the summary. Check accuracy internally; output the journal without internal deliberation or analysis tags.
- Distinguish observed causes from hypotheses, and proposed changes from implemented changes and verified behavior. A failed test does not by itself prove a suspected root cause.
- Use only available history and evidence. State material context gaps or unknowns rather than reconstructing missing events. Do not invent timings for earlier attempts.
- Keep technical details that explain the work: relevant concepts, file paths, symbols, commands, errors, and focused code snippets. Include larger snippets when needed to understand an approach; avoid duplicating the same details across sections.

## Summary structure

Use plain Markdown with a descriptive title and these sections. Scale the detail to the session; explicitly mark sections with no applicable work rather than inventing content.

1. **Goal and user constraints**: What was requested, relevant requirements, and any changes to scope.
2. **Current state**: A brief overview of the outcome and the exact stopping point immediately before the summary request. State whether the task is complete, ongoing, or blocked.
3. **Approaches, results, and rationale**: The meaningful sequence of attempts. For each approach, describe what was tried, why it was chosen, supporting observations or results, why it succeeded or fell short, and what was learned or changed next. Compare alternatives where the session provides evidence; label untested alternatives as proposals.
4. **Changes and relevant files**: Files created, modified, or examined, important symbols or snippets, and their purpose. Distinguish the final implementation from reverted or merely proposed changes. Include repository and branch/commit identifiers when available and relevant.
5. **Verification**: Checks and tests actually run, their results, what state they covered, and remaining uncertainty. Preserve significant failures in the approach history; make clear whether later changes were rechecked.
6. **Remaining work and next authorized action**: Unfinished requested tasks, blockers, and the immediate next action consistent with the latest user instructions. Use a short direct quote when it clarifies where work stopped. If complete, state that; do not invent follow-up work or perform it as part of summarizing.

## Save the summary

1. Use the user's specified destination if provided. Otherwise use `ClaudeSessionSummaries/` under the active project root; for a projectless session, use the current working directory. Resolve this location explicitly and create the directory if needed.
2. Read the actual system clock immediately before saving. Use one timestamp for the filename and the summary's `Created` metadata; never infer it from the conversation date or invent seconds. Include seconds and the UTC offset in the metadata using ISO 8601. Use the user's configured timezone when available, otherwise the system timezone, and identify the timezone used.
3. Name the file `session-yyyy-MM-dd_HHmmss.md` using that timestamp, for example `session-2026-09-08_143052.md`. In PowerShell, capture `[DateTimeOffset]::Now` once (convert to the intended timezone if needed), then format that same value as `yyyy-MM-dd_HHmmss` for the filename and `yyyy-MM-dd'T'HH:mm:sszzz` for metadata. Other environments may use an equivalent clock API.
4. Create a new file without overwriting an existing summary. If the filename already exists, append `-01`, `-02`, and so on while preserving the actual timestamp. If a reliable clock cannot be read, report that limitation instead of fabricating a timestamp.
5. Include the project/workspace path in the metadata. After writing, verify that the file exists and its content and metadata match the intended summary.

## Optional CLAUDE.md table

Create or update the summary table only when the user explicitly requests it, for example `/create_session_summary with table` or `./create_session_summary with table`. A bare invocation saves only the summary: leave `CLAUDE.md` untouched even if it already has a summary table. An explicit request to add or update the summary index also opts in.

When requested, after successfully saving the summary:

- Use `CLAUDE.md` in the same project/workspace root, unless the user identifies a different index file.
- Reuse the existing session-summary table and its column/order conventions. Add one entry for the saved summary with its creation timestamp, a brief description, and a relative Markdown link. Keep the description or Topic cell to one brief hook, roughly 15 words or fewer; all detailed history belongs in the summary file. Do not duplicate an entry for the same file.
- If no summary table exists, append a `## Session Summaries` section with `Created`, `Summary`, and `File` columns. If `CLAUDE.md` is absent, create it with that section.
- Preserve all unrelated instructions and content. Verify that the entry points to the saved file. If the table update fails, retain the summary and report the partial result.

Finish with a brief confirmation linking to the saved summary and, when requested, reporting the table update result.
