# The Agents' Guide to the Galaxy

Don't panic. There's a skill for that.

A personal, version-controlled home for reusable AI agent skills and, eventually,
shared instructions and tooling for Codex and Claude Code.

## Current status

This initial revision establishes the repository and records the migration plan.
No skills have been imported, no installer has been implemented, and existing
agent installations have not been changed.

## How it will work

- Maintain each canonical skill in `skills/<name>/`, including its `SKILL.md`,
  scripts, references, and templates.
- Store per-skill installation choices in a versioned manifest: Codex, Claude
  Code, both, or neither.
- Use a PowerShell installer to create individual Windows directory junctions
  from agent discovery folders to the canonical skill folders.
- Edit skills in this repository and review changes with Git. Existing links
  expose updates after edits or pulls without copying files. Running agent
  sessions may need a refresh or restart to reload instructions.
- Rerun the installer after adding, renaming, or removing skills, changing
  installation choices, moving the checkout, or cloning onto another machine.

Junctions are local installation artifacts. Git tracks the actual skill files and
installation choices; the installer recreates the junctions on each machine.
Editing through a junction also edits the repository's files.

## Repository layout

```text
skills/             Canonical skills after migration
docs/migration.md   Inventory findings, migration sequence, and installer design
```

The next phase will introduce `manifest.json` and `install.ps1`. Agent-specific
instructions, hooks, and configuration templates will follow after the skills
migration is complete.

## Scope

Keep reusable skills and their supporting resources here. Preserve third-party
licenses and attribution, and record upstream sources and revisions as they are
verified during import. Tool-managed bundled skills stay under their tool's
management. Project-specific instructions belong with the project they describe.

Credentials, authentication state, sessions, caches, generated memories, and local
installation backups stay outside versioned content.

See [the migration plan](docs/migration.md) for the initial inventory and next steps.
