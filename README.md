# The Agents' Guide to the Galaxy

Don't panic. There's a skill for that.

A personal, version-controlled home for AI agent skills used by Codex and Claude
Code. It currently contains 33 canonical skills and a Windows installer that
links selected skills into each agent's discovery folder.

## Get started

Run these commands from the checkout in PowerShell 7 on Windows:

```powershell
# Pick targets per skill (Enter keeps the saved choice).
pwsh -File ./install.ps1 -Mode Configure

# Inspect the changes before applying them.
pwsh -File ./install.ps1 -Mode Plan -AdoptExisting
pwsh -File ./install.ps1 -Mode Apply -AdoptExisting
```

The initial choices match the previous installation: 26 skills for Codex and 33
for Claude Code. Existing matching folders and junctions are backed up before
adoption. Differing content is a conflict that must be resolved first.

## One source of truth

Each installed skill directory is a Windows junction to `skills/<name>` in this
checkout. Editing or pulling updates to existing skills immediately changes what
the linked paths expose. An already-running agent session may need to refresh or
restart to load updated instructions. Edits made through an agent's linked folder
also change the repository files.

Run Configure and Apply when selecting new targets or adding skills. Run Plan and
Apply after renaming/removing skills or moving the checkout. Git stores the source
files and manifest; junctions and installation backups are local to each machine.

## Repository layout

```text
skills/                   Canonical skills and their supporting resources
manifest.json             Per-skill agent selections and legacy-copy retirement
provenance.json           Initial source records and imported file hashes
install.ps1               Configure, plan, apply, and restore
tests/installer.tests.ps1  Isolated Windows installer checks
docs/installation.md      Usage, updates, backups, and recovery
docs/skill-review.md       Import review and dependency notes
docs/migration.md          Initial inventory and migration record
licenses/                 Third-party notices
THIRD_PARTY_NOTICES.md     Attribution and provenance scope
```

## Maintenance

Edit skills here and review their Git diffs. Preserve supporting resources and
upstream attribution. Existing tool-specific dependencies and invocation policies
are retained; linking a skill does not install its MCP servers or guarantee its
workflow works on both agents. See [the import review](docs/skill-review.md).

Tool-managed system skills and plugins remain under their tool's management.
Credentials, authentication state, caches, sessions, generated memories, and local
backups stay outside versioned content. Custom instructions and other agent
tooling are a later phase.

See [installation and recovery](docs/installation.md) for full instructions.
