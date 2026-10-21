# Spec format

One JSON file per review. Paths are relative to the spec file.

| Key | Meaning |
|---|---|
| `id` | Short id, used for file names and the decisions key (`slice-s1`) |
| `title`, `subtitle` | Page heading and the line under it (what was compared, where, when) |
| `shotsDir` | Folder of the screenshots (default: the spec's folder) |
| `workDir` | Where the work files and `<id>-review.html` go (default `review-<id>`); keep it out of git |
| `oldLabel`, `newLabel` | Captions over the left and right image (default "Old app", "New app") |
| `eyebrow`, `pageTitle`, `sidesTag` | Small heading, browser title, side tag on every card (optional) |
| `items` | `[["1.1", "Logon and landing", ""], …]`: walk items, shown as `<item> · <title>` on each card |
| `notes` | Lines for the "Verification and notes" panel (sides, rows without images, where the evidence lives, how to decide) |
| `rows` | The differences, below |

Row keys:

| Key | Meaning |
|---|---|
| `id`, `item`, `severity` | Row id, walk item, BLOCKER / MAJOR / MINOR / COSMETIC |
| `roles`, `page`, `title` | Who, where, one-line title |
| `issue` | Plain-language description for the user (required) |
| `detail`, `cause`, `expected`, `measurements` | Folded technical details (optional) |
| `old`, `new` | `{"file": "<shot>.png", "crop": [x0, y0, x1, y1], "marks": [[x0, y0, x1, y1], …]}` in full-shot pixels; omit both for rows without images |
| `pairs` | Extra image pairs: `[{"caption": "Whole page", "old": {…}, "new": {…}}]` |
| `options`, `rec`, `recOption`, `effort` | Choices, recommendation text, recommended option (1-based), S / M / L |
| `decision`, `reply` | The user's decision once given, your answer to their comment |
| `open` | `true` while a question to the user about this row is pending ("Open questions" filter); omit otherwise |

Example row:

```json
{
 "id": "F-S1.1-a", "item": "1.1", "severity": "MAJOR", "roles": "MVZ (Maßnahmen Vollzugriff)",
 "page": "Unternehmensziele list", "title": "\"Quartalsbericht\" button missing for Maßnahmen Vollzugriff",
 "issue": "In the old app these users have a \"Quartalsbericht\" button that downloads the quarter report as a ZIP. In the new app the button is not there for them.",
 "cause": "TaskDownloadController.cs:62-65 …",
 "old": {"file": "slice-s1-1.10-MVZ-WwBscTask_ListView-old.png", "crop": [205, 50, 1110, 84], "marks": [[845, 54, 959, 78]]},
 "new": {"file": "slice-s1-1.10-MVZ-WwBscTask_ListView-new.png", "crop": [280, 52, 1910, 98]},
 "pairs": [{"caption": "Whole page, same role", "old": {"file": "…-old.png", "marks": [[845, 54, 959, 78]]}, "new": {"file": "…-new.png"}}],
 "options": ["FIX: show the button again.", "ACCEPT: only admins get the ZIP."],
 "rec": "Option 1: a role loses a function it had.", "recOption": 1, "effort": "S"
}
```

Real example: `WwBscDb/Migration/comparison/review/slice-s1.json`.
