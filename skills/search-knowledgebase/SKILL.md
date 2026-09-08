---
name: search-knowledgebase
description: Searches Kevin's local structured KnowledgeBase and returns current, source-backed answers while respecting Jira state, provenance, archives, and the private boundary. Use when the user says "search the knowledgebase", "look in the knowledgebase", "check my notes", "find this in my second brain", asks what the KnowledgeBase says, or when local project, Jira, DevExpress, or AI-agent knowledge may answer the request.
---

# Search the KnowledgeBase

## Quick start

Use `C:\Users\KevinCsele\Developer\KnowledgeBase` as the default root. If
`KNOWLEDGEBASE_ROOT` is set and resolves to a directory, use it instead.

Run the bundled helper from this skill directory:

```powershell
.\scripts\search-knowledgebase.ps1 -Query "search terms"
```

Add `-Project prm`, `-Scope jira`, `-Scope all`, or `-Scope private` only when
the request calls for it. The private scope returns matching file paths, not
matching content.

## Search workflow

1. Classify the request as a topic, project, Jira key, plan/state question, or
   evidence/history question. Extract useful aliases and exact identifiers.
2. Search canonical knowledge first. Start with `_meta/indexes/canonical-notes.md`
   and `_meta/indexes/state-review.md`, then the relevant live theme or project.
3. For a Jira key, open its stable mirror under
   `10-projects/<project>/work-items/jira/` and search canonical frontmatter for
   the same key. Treat the mirror's status as authoritative only as of its
   recorded Jira `Updated` value.
4. For project questions, search `10-projects/<slug>` before reusable knowledge
   in `20-engineering`, `30-ai-agents`, and `40-toolbox`.
5. Search `00-inbox`, source registers, `90-archive`, and private raw history
   only when canonical material is absent, incomplete, or the user requests
   historical evidence.
6. Open the best matches and follow their first meaningful links, `Related`,
   and `Sources`. Stop when the answer is supported; do not dump every match.

If an exact phrase misses, retry with the important nouns separately, spelling
variants, aliases, ticket keys, and likely project slugs. Use `rg` directly
when a structural query is clearer than the helper.

## Evidence and freshness

- Prefer `current` or `active` canonical notes over `unknown`, `superseded`,
  raw, or archived material.
- Read YAML `status`, `updated`, `projects`, `jira`, and `sources` before
  treating a match as current.
- Distinguish canonical conclusions, managed Jira state, direct source
  evidence, and inference.
- Consult `_meta/indexes/state-review.md` for mutable, deferred, superseded, or
  uncertain claims.
- Consult _meta/update-checkpoints.md before claiming a source corpus is fully
  up to date.
- Do not claim that information is absent until the canonical, identifier,
  project, and appropriate evidence passes have all been tried.

## Private boundary

- Never broadly print content from `70-private`.
- Use `-Scope private` to discover candidate paths, then inspect only the
  minimum necessary file locally.
- Never reproduce credential, token, authentication, license, or secret values
  in an answer or log. Refer to their purpose and path instead.
- Raw AI histories are evidence, not canonical truth. Corroborate important
  conclusions and identify uncertainty.

## Answer contract

Lead with the answer, not the search process. Cite the most useful local files
with precise paths and line numbers when available. Mention the relevant
status or as-of date when state may have changed. If sources disagree, explain
the disagreement and which source has priority. Searching is read-only unless
the user separately asks to update the KnowledgeBase.
