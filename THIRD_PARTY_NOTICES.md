# Third-party skill provenance

The initial import preserves locally installed content, including local edits.
`provenance.json` records the source folder, original discovery locations, and
SHA-256 of every imported file. Its hashes describe the import snapshot; they are
not a requirement that future edits remain byte-identical.

The local `.agents/.skill-lock.json` records 15 of these installed skills as coming
from [Matt Pocock's skills](https://github.com/mattpocock/skills): `ask-matt`,
`diagnose`, `grill-me`, `grill-with-docs`, `handoff`, `prototype`,
`setup-matt-pocock-skills`, `tdd`, `teach`, `to-issues`, `to-prd`, `wayfinder`,
`write-a-skill`, `writing-great-skills`, and `zoom-out`.

It records `find-skills` as coming from
[Vercel Labs' skills](https://github.com/vercel-labs/skills).

The source repositories' MIT notices were checked on 2026-09-08 and included in
`licenses/`. Installer-recorded skill folder hashes are preserved as provenance;
they are not asserted to be Git commit IDs or proof of an exact upstream match.
The other 17 skills have no upstream entry in the local lock file. Their origin
is marked `local-source-unattributed`; absence of an entry is not proof of
authorship or a license grant. No blanket license is applied to this collection.

The missing `improve-codebase-architecture` skill also has a lock entry, but no
local source was available. It was not downloaded, imported, or enabled. Its
existing broken junction remains outside this installer's managed entries.
