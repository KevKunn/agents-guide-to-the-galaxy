# Skill import review

Imported on 2026-09-08. All 33 skill folders and 60 original files were copied byte-for-byte. Matching independent copies were compared again before import; none required a merge.

Targets preserve previous availability. This review identifies dependencies; it does not certify runtime compatibility or alter skill behavior. The four existing `agents/openai.yaml` files retain their explicit-only invocation policy.

| Skill | Initial targets | Recorded origin | Dependency notes |
| --- | --- | --- | --- |
| `ask-matt` | codex, claude | mattpocock/skills | References project context, instruction files, or other workflows. |
| `break-it-down` | codex, claude | Local; upstream not recorded | No specific dependency flagged in the initial scan. |
| `commit` | claude | Local; upstream not recorded | References project context, instruction files, or other workflows. |
| `convention-dx-review` | codex, claude | Local; upstream not recorded | Contains Claude model or subagent terminology; cross-agent behavior needs review. Requires specific agent or MCP tools. References project context, instruction files, or other workflows. |
| `create_session_summary` | codex, claude | Local; upstream not recorded | References project context, instruction files, or other workflows. Existing underscore name retained for compatibility. |
| `create-digest` | claude | Local; upstream not recorded | Requires specific agent or MCP tools. |
| `diagnose` | codex, claude | mattpocock/skills | No specific dependency flagged in the initial scan. |
| `document-feature` | codex, claude | Local; upstream not recorded | No specific dependency flagged in the initial scan. |
| `dx-lookup` | codex, claude | Local; upstream not recorded | Contains Claude model or subagent terminology; cross-agent behavior needs review. Requires specific agent or MCP tools. |
| `find-skills` | codex, claude | vercel-labs/skills | No specific dependency flagged in the initial scan. |
| `grill-me` | codex, claude | mattpocock/skills | No specific dependency flagged in the initial scan. |
| `grill-with-docs` | codex, claude | mattpocock/skills | No specific dependency flagged in the initial scan. |
| `handoff` | codex, claude | mattpocock/skills | No specific dependency flagged in the initial scan. |
| `learning-expedition` | codex, claude | Local; upstream not recorded | No specific dependency flagged in the initial scan. |
| `playwright-agent` | codex, claude | Local; upstream not recorded | Contains Claude model or subagent terminology; cross-agent behavior needs review. Requires specific agent or MCP tools. References project context, instruction files, or other workflows. |
| `prm-business-objects` | claude | Local; upstream not recorded | References project context, instruction files, or other workflows. |
| `prm-stateworkflow` | claude | Local; upstream not recorded | References project context, instruction files, or other workflows. |
| `prm-xaf-blazor-ui` | claude | Local; upstream not recorded | References project context, instruction files, or other workflows. |
| `prm-xaf-model` | claude | Local; upstream not recorded | References project context, instruction files, or other workflows. |
| `prototype` | codex, claude | mattpocock/skills | No specific dependency flagged in the initial scan. |
| `sanitize-doc` | codex, claude | Local; upstream not recorded | No specific dependency flagged in the initial scan. |
| `search-knowledgebase` | codex, claude | Local; upstream not recorded | Contains machine-specific Windows paths. References project context, instruction files, or other workflows. |
| `setup-matt-pocock-skills` | codex, claude | mattpocock/skills | References project context, instruction files, or other workflows. |
| `sql-lookup` | codex, claude | Local; upstream not recorded | Contains Claude model or subagent terminology; cross-agent behavior needs review. References project context, instruction files, or other workflows. |
| `sql-pipe-lookup` | claude | Local; upstream not recorded | Contains Claude model or subagent terminology; cross-agent behavior needs review. Contains machine-specific Windows paths. References project context, instruction files, or other workflows. |
| `tdd` | codex, claude | mattpocock/skills | No specific dependency flagged in the initial scan. |
| `teach` | codex, claude | mattpocock/skills | No specific dependency flagged in the initial scan. |
| `to-issues` | codex, claude | mattpocock/skills | No specific dependency flagged in the initial scan. |
| `to-prd` | codex, claude | mattpocock/skills | No specific dependency flagged in the initial scan. |
| `wayfinder` | codex, claude | mattpocock/skills | References project context, instruction files, or other workflows. |
| `write-a-skill` | codex, claude | mattpocock/skills | No specific dependency flagged in the initial scan. |
| `writing-great-skills` | codex, claude | mattpocock/skills | No specific dependency flagged in the initial scan. |
| `zoom-out` | codex, claude | mattpocock/skills | No specific dependency flagged in the initial scan. |

The existing broken `improve-codebase-architecture` junction was excluded because its source is missing. It remains unmanaged. The older `.codex/skills/learning-expedition` copy is explicitly listed for backup and retirement to avoid duplicate discovery.

The `create-digest` skill retains its personal Notion destination and Claude source label; `search-knowledgebase` retains its local KnowledgeBase path. PRM skills retain their project assumptions. These are preserved source details, not portable machine configuration.

The existing `create_session_summary` name uses underscores. It is retained to avoid changing invocation names during migration. Cross-agent adaptations, missing companion workflows, and naming changes can be reviewed separately after consolidation.
