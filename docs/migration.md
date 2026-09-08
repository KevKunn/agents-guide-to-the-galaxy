# Skills migration

## Migration completed: 2026-09-08

The owner created foundation commit `dcb610f`. The skills phase imported 33 skill
folders and 60 original files without changing their content. `manifest.json`
preserves the original selections: 26 Codex skills and 33 Claude Code skills.
Source records, import hashes, and dependency notes are in `provenance.json` and
`docs/skill-review.md`.

The tested installer created 59 direct junctions to this repository. All 60
original entries were backed up in the user's local application-data directory,
including the extra `.codex/skills/learning-expedition` copy, which was retired.
The broken `improve-codebase-architecture` junction remains unchanged and
unmanaged because its source was absent.

Verification completed:

- All 60 imported file hashes matched the original snapshots.
- The isolated installer suite passed 36 assertions, including content conflicts,
  dry runs, adoption, configuration, shared edits, restoration, source retirement,
  checkout relocation, rollback, and parent-link protection.
- All 59 installed junctions and all 60 original backup entries were verified.
- A new installation plan reported `Keep` for all managed records.
- Codex's own app-server `skills/list` scan, with forced reload, found all 26
  selected skills at canonical repository paths, enabled, with no scanner errors.
- Claude's 33 junctions and entrypoint files were verified on disk. Discovery in a
  fresh Claude Code session and each skill's external workflow remain manual
  checks; no model task was launched for this migration.

The skills migration files are left unstaged and uncommitted for owner review.
Custom instructions have not been changed. See `docs/installation.md` for the
implemented installer commands and recovery procedures; the planned behavior
below records the original design.

## Initial inventory: 2026-09-08

The repository started empty on branch `master`, with no commits. At that point, the foundation
was ready for the owner to review and commit before importing skills.

The inspection covered immediate skill directories in the three personal skill
locations, their link targets, the presence of `SKILL.md`, and recursive file
comparisons for separately stored skills with matching directory names. Paths
below are relative to the user profile. Bundled `.codex/skills/.system` contents
and plugin caches were excluded.

| Location | Ordinary skill folders | Directory junctions | Total entries |
| --- | ---: | ---: | ---: |
| `.agents/skills` | 26 | 0 | 26 |
| `.claude/skills` | 17 | 17 | 34 |
| `.codex/skills` | 1 | 0 | 1 |

There are 34 distinct directory names: 33 have a usable `SKILL.md` in at least one
location, and one exists only as a broken junction. These are directory inventory
counts, not a verification of agent discovery or skill functionality.

### Identical independent copies

All ten groups of separately stored folders with matching names have identical
relative file lists and SHA-256 file hashes, including supporting resources:

- `break-it-down`
- `convention-dx-review`
- `create_session_summary`
- `document-feature`
- `dx-lookup`
- `learning-expedition`
- `playwright-agent`
- `sanitize-doc`
- `search-knowledgebase`
- `sql-lookup`

`learning-expedition` has copies in all three locations. The other nine have
copies in `.agents/skills` and `.claude/skills`. Byte equality means no content
merge is currently needed for these groups; source attribution and agent
compatibility still need review before import.

### Broken junction

`.claude/skills/improve-codebase-architecture` points to
`.agents/skills/improve-codebase-architecture`, whose target is missing.
Resolve whether to restore this skill or retire the stale link during migration.
The initial inspection did not modify the link.

### Scope still to review

- Identify custom skills versus third-party imports and verify provenance.
- Review agent-specific tools, model references, absolute paths, and dependencies.
- Choose installation targets per skill; existing availability is the starting
  point, not proof that every skill works with both agents.
- Recheck source files immediately before import in case they changed after this
  inventory.

## Migration sequence

1. Owner reviews and creates the foundation commit.
2. Review the skill sources and choose canonical versions, preserving all
   supporting files and verified upstream attribution.
3. Import skills and record per-skill installation targets in a manifest.
4. Implement and verify the PowerShell installer in an isolated fixture before
   pointing it at the real agent directories.
5. Review the installation dry run, back up replaced folders outside the
   repository, and establish the selected junctions.
6. Verify link targets, skill discovery in fresh agent sessions, and shared-file
   visibility. Document recovery and installation on another machine.
7. Address custom instructions as a separate phase after skills are working.

The owner creates the first commit. No automated commit is part of this phase.

## Planned installer behavior

The installer and manifest do not exist yet. The intended contract is:

- Configure mode lets the user select Codex, Claude Code, both, or neither for
  each skill and saves those selections in the manifest.
- Install/update mode applies the saved choices without asking the same questions
  again. A dry run reports planned changes before mutation.
- Codex selections use the personal `.agents/skills` discovery location; Claude
  Code selections use `.claude/skills`. Installation in `.agents/skills` may also
  expose a skill to other tools that scan that shared location.
- Create one junction per selected skill. Preserve other installed skills and
  tool-managed directories.
- Distinguish ordinary directories, expected links, links to other targets, and
  broken links. Stop on unresolved conflicts instead of overwriting them.
- Back up any ordinary folder being replaced, record recovery information in
  local installation state, and never recursively delete a junction target.
- Reconcile only links recorded as managed by this installer. A rerun with no
  changes should perform no modifications.
- Resolve targets from the checkout location and the current user profile; keep
  machine-specific absolute paths out of the portable manifest.
- Validate missing source skills and link targets after removals or renames.
- Keep recovery instructions available before activating the migration.

## First commit message

```text
In the beginning, the repository was created. This has made a lot of agents very angry and been widely regarded as a bad move.
```
