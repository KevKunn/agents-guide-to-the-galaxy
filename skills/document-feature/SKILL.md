---
name: document-feature
description: Write developer documentation for a feature implemented in the current repository, grounded in the codebase as ground truth plus ClaudeSessionSummaries/ for design rationale. Produces a single doc_<feature_name>.md in the working directory with a fixed structure (Overview, Architecture, Usage, Pitfalls) using correct DevExpress/XAF terminology. Use when the user asks to "document the X feature", "write docs for X", "write developer documentation", or invokes /document-feature <feature name>.
---

# Document Feature

Act as a senior documentation engineer. Write developer documentation for the feature named in the arguments (e.g. "Rule Engine"). If no feature name was given, ask the user which feature to document before doing anything else.

## Sources and ground truth

Work from two sources, in this order of authority:

1. **The codebase** — the single source of truth for *what* is implemented. Never describe behavior you have not verified by reading the relevant files. If unsure how something works, read the code before writing about it; do not speculate or fill gaps from general knowledge.
2. **Session summaries in `ClaudeSessionSummaries/`** (if any exist for this feature) — the source for *why* things were built the way they were: design decisions, rejected alternatives, known limitations, and warnings discovered during implementation.

When the summaries and the code disagree, the code wins. Treat the summary as outdated, document the current behavior, and add a short note if the divergence is important (e.g. "an earlier design used X; the current implementation uses Y").

Document only what exists. Do not describe planned, aspirational, or half-finished functionality as if it works — if something is clearly incomplete, say so explicitly in the pitfalls section.

## Process

1. **Explore first.** Locate every file that belongs to the feature: entry points, core classes, attributes/tags, configuration, tests. Skim the tests — they show intended usage and edge cases.
2. **Read the session summaries** for this feature and extract: reasoning behind decisions, usage requirements, warnings, and anything described as a gotcha or workaround.
3. **Reconcile** the two: confirm each claim from the summaries against the current code before including it.
4. **Outline, then write.** Draft the document following the structure in [STRUCTURE.md](STRUCTURE.md) — read it before outlining.
5. **Verify.** Re-read the finished document as if you were a developer who has never seen this feature. Check that:
   - every code snippet is copied from (or compiles against) the actual code, with real type/method names and namespaces;
   - every file path exists;
   - a newcomer could use the feature end-to-end from the document alone, without reading the source.

   Fix anything that fails this test.

## Context management

Delegate heavy, high-volume work to subagents (Task tool) instead of doing it in the main context. In particular:

- **Codebase exploration** (process step 1): spawn a subagent to locate and read all files belonging to the feature. It must return only a condensed inventory: file paths, key classes/members with one-line responsibilities, the execution flow, and short relevant code excerpts — not full file contents.
- **Session summary mining** (process step 2): spawn a subagent to read `ClaudeSessionSummaries/` and return only the decisions, requirements, and warnings relevant to this feature.

In the main context, read a file in full only when you need it for a specific snippet or to verify a specific claim.

## Output

A single Markdown file named with a `doc_` prefix so documentation files can be distinguished from other Markdown files: `doc_<feature_name>.md` (e.g. `doc_rule_engine.md`). Store it in the current working directory (`./`) — do **not** create or use a `docs/` folder.

## Style

- Audience: developers on this team who have not worked on the feature. Assume general C#/.NET and basic XAF knowledge; assume zero knowledge of this feature.
- Prefer precise, concrete statements ("`RuleEngineService.Execute` is called from `XController.DoExecute`, see `Module/Services/RuleEngineService.cs`") over vague ones ("the service is invoked by a controller").
- Reference code by path (and member name) so readers can jump to it; keep quoted snippets short and current.
- Plain, direct language. No marketing tone, no filler. A short section is fine if there is little to say.
- If you discover open questions you cannot resolve from code or summaries, list them at the end under "Open questions" rather than guessing.
