# Skills

Canonical skill folders will be imported here after their source and installation
targets have been reviewed.

Each skill keeps its complete directory structure:

```text
<skill-name>/
  SKILL.md
  scripts/       # Optional
  references/    # Optional
  templates/     # Optional
```

Keep relative resource paths intact. Record verified upstream provenance and
retain any licenses when importing third-party material. Check agent-specific
tool references and local paths before enabling a skill for another agent.

The root README in this directory documents the collection; it is not itself an
installable skill. The planned installer will only install skills explicitly
listed in the manifest.
