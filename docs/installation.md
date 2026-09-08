# Install and maintain the skills

## Requirements

Use PowerShell 7 on Windows (`pwsh`). Keep the checkout on a local filesystem that
supports directory junctions. The installer deliberately rejects linked parent
directories and skill folders containing nested links.

Commands below run from the repository root. `Plan` is the default mode. No
command creates a Git commit or stages files.

## First installation or migration

```powershell
# Review existing choices, or change them interactively.
pwsh -File ./install.ps1 -Mode Configure

# Review adoption of existing folders whose contents match the repository.
pwsh -File ./install.ps1 -Mode Plan -AdoptExisting

# Back up those entries and install the selected junctions.
pwsh -File ./install.ps1 -Mode Apply -AdoptExisting
```

`-AdoptExisting` is only needed to take ownership of existing, matching skill
folders or junctions. It does not permit replacing differing content. Compare and
merge such content into the repository first, then rerun the plan. Text comparison
allows UTF-8 BOM and CRLF/LF differences; other content is hashed without changes.

On a new machine with empty discovery locations, `-Mode Apply` is sufficient.
The initial manifest preserves the old selections: 26 skills for Codex and 33 for
Claude Code. Selecting neither retains a skill in the repository without linking
it into either tool.

| Manifest agent | Personal discovery location |
| --- | --- |
| `codex` | `.agents/skills/<name>` |
| `claude` | `.claude/skills/<name>` |

These paths are relative to the current user's profile. Other tools may also
discover skills under `.agents/skills`; a Codex selection is not an access control
boundary. The manifest's `legacyCopies` list retires the duplicate
`.codex/skills/learning-expedition` only after verifying and backing it up.

## Change one skill's targets

```powershell
pwsh -File ./install.ps1 -Mode Configure -Skill diagnose
```

For noninteractive configuration, invoke from PowerShell:

```powershell
./install.ps1 -Mode Configure -Skill diagnose -Agents codex,claude
./install.ps1 -Mode Configure -Skill diagnose -Agents @()
./install.ps1 -Mode Plan
./install.ps1 -Mode Apply
```

Configure only changes the manifest. Apply updates the installation. Deselection
removes a managed junction but retains its original backup for recovery. It does
not restore the old copy automatically, which would make the deselected skill
visible to the agent again.

## Edit, pull, add, rename, remove

- **Edit or pull an existing skill:** linked paths expose the current repository
  files immediately. Editing through a linked path also changes the repository.
  Start a fresh agent session when its loaded instructions are stale.
- **Add a skill:** create `skills/<name>/SKILL.md` and supporting resources. Run
  Configure; it discovers new skill folders with no targets selected. Choose
  targets, then run Plan and Apply. Record provenance for imported material.
- **Rename a skill:** update its directory, frontmatter name, and manifest entry.
  Update any corresponding `legacyCopies` entry. Plan and Apply reconcile old
  managed links and new destinations.
- **Remove a skill:** remove its manifest entry and any `legacyCopies` entry,
  then remove the source folder with Git. Plan and Apply remove the old managed
  links even if they are now dangling. Original backups remain recoverable.
- **Move the checkout:** run Plan and Apply from the new location. The local
  installation state retains the old targets so the installer can retarget its
  own junctions. Keep only one active checkout for this installation state.
- **Update upstream material:** review updates in this repository, preserve local
  changes and licensing, and update provenance. Old third-party installers can
  replace junctions or edit through them; use this repository for maintained
  skills and review Git diffs after external tooling changes.

## Backups and restoration

Default state location:

```text
<user-profile>/AppData/Local/agents-guide-to-the-galaxy/
  state.json
  install.lock
  backups/<run-id>/<location>/<skill-name>/
```

The state records destinations, original backups, and managed junction targets.
Keep the state directory and backups together. Absolute paths are local state;
the versioned manifest contains portable skill names and target selections.

To undo installation and restore pre-migration entries:

```powershell
pwsh -File ./install.ps1 -Mode Restore -DryRun
pwsh -File ./install.ps1 -Mode Restore
```

Restore removes managed junctions and moves original backups to their original
locations. It preserves edits in the repository, but the restored originals are
the pre-migration copies and will no longer expose those repository edits. New
installations with no original entry simply have their managed junction removed.
An unexpected folder or retargeted junction is a conflict; the installer stops
before making changes. Restore affects all records in this installation state.

Ordinary failures roll back the current run in reverse order. A forcibly stopped
process can leave `pending.json`, which blocks further installation. Its
`originalState` and ordered `steps` record what was about to change and which
steps completed. If this happens:

1. Keep the journal, state, repository, and backups intact. Ensure no installer
   process is still running.
2. Inspect the actual filesystem against each journal step. A step marked
   `done: false` may still have executed if interruption occurred between the
   filesystem change and journal update.
3. Reconcile in reverse order: remove only verified newly created junctions,
   recreate removed junctions, and move backups back only when their original
   paths are vacant. Never recursively delete a junction or its target.
4. Restore `state.json` from `originalState` after rolling back the filesystem,
   then archive the journal outside its active `pending.json` path. Rerun Plan.

Crash recovery is deliberately manual; automatic rollback is tested for normal
exceptions. The exclusive local lock prevents simultaneous Apply/Restore writes.

## Verification

```powershell
pwsh -File ./tests/installer.tests.ps1
pwsh -File ./install.ps1 -Mode Plan
```

The test uses isolated temporary profiles and retains them for inspection. It
does not operate on the real agent folders. Plan after a successful installation
should report `Keep` for each managed entry. Finally, start fresh Codex and Claude
Code sessions and check their skill lists. Filesystem checks do not exercise each
skill's external tools or workflows.

Use `-ProfileRoot` and `-StateRoot` only when deliberately installing into another
profile or testing. Reuse the same overrides for Plan, Apply, and Restore.
