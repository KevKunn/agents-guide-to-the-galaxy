# File shapes

All files live in the sweep dir (`$S`). JSON is UTF-8.

```
$S/
  sweep.config.json      config (below)
  adapter.mjs            app adapter (references/adapters.md)
  sweep-lib.mjs run-repros.mjs enum-nav.mjs gen-report.py   copied from the skill's scripts/
  BRIEF.md               filled brief-template.md
  nav.json               output of enum-nav.mjs
  work/<AREA>/           finder agents' scratch scripts
  findings/<AREA>/<AREA>-NN.json, <id>.before.png, <id>.after.png, coverage.json
  status.json            per-finding fix status (orchestrator)
  briefs.json            decision briefs for non-fixed findings (orchestrator)
  report/ui-sweep-report.html, report/review-decisions.json
  .auth/                 storage states when reuseStorageState is on (session cookies: delete at the end, never commit)
```

## sweep.config.json

See `scripts/sweep.config.example.json`. Keys:

| Key | Meaning |
|---|---|
| `title`, `subtitle` | Report heading and the line under it |
| `locale` | Browser context locale and report `lang` |
| `uiLanguage` | Expected UI language (check C8 text) |
| `adapter` | Path of the adapter module, default `./adapter.mjs` |
| `playwrightFrom` | Folder whose `node_modules` contains `playwright`; fallback: the sweep dir, then the global `@playwright/cli` install |
| `reuseStorageState` | `true`: `lib.open` saves/loads `.auth/<tenant>_<user>_<module>_<w>_<h>.json` and asks `adapter.isLoggedIn` before reusing |
| `settleMs` | Extra wait after `settle` (default 1500) |
| `failedRequestPattern` | Regex of request URLs whose ≥ 400 responses count as failed images |
| `viewports` | `[main, narrow]`; first is the default for findings without `viewport` |
| `tenants` | `{ name: { url, ...free } }` or `{ name: "url" }` |
| `navPlan` | `[{ tenant, user, modules?: [...] }]` for `enum-nav.mjs` |
| `areas` | `{ "A": "scope text" }` or `{ "P": { "title": "...", "preexisting": true } }` (preexisting areas are left out of the severity KPI) |
| `audit.rawExtra` | Extra regex for raw/technical names (C7), OR-ed with the adapter's |
| `audit.foreignWords` | Regex for C8 candidates; omit for the built-in English word list (for non-English UIs), `null` to switch off |
| `audit.ignore` | Selector of elements the audit skips |
| `checks` | Optional override `[[code, title, criterion], ...]` for the report table |
| `decisionsKey` | localStorage key of the review page |
| `beforeLabel`, `afterLabel` | Names of the two screenshot sides (default Before / After), e.g. Old app / New app |
| `eyebrow`, `pageTitle` | Line above the report title and the browser tab title |
| `coverage` | `false` hides the checks, areas and coverage sections (reviews without a coverage walk) |

## Finding — `findings/<AREA>/<AREA>-NN.json`

Full field list and rules in `brief-template.md` (Output, step 2). Required by the tools: `id`, `tenant`, `user` (`"none"` = no login), `steps`; optional `module`, `viewport` (default `viewports[0]`), `clip`, `marks`, `pad` (default 16), `fullPage`. Everything else is for the report and the human.

```json
{ "id": "B-02", "tenant": "T1", "user": "alice", "module": "Main", "viewport": { "width": 1600, "height": 900 },
  "page": "Task – list", "route": "Task_ListView", "check": "C1", "severity": "high",
  "title": "Task list: 9 of 14 column headers cut ('Recomm…', 'Meas…')",
  "description": "14 columns of ~89 px; header text area 47 px. 'Recommendation' 77/47, …",
  "measurements": { "columnWidthPx": 89, "headerTextVisiblePx": 47 },
  "expected": "Readable headers; long text columns 250–400 px.",
  "suspectedCause": "Task_ListView columns have no width (model file, line ~3317).",
  "alsoAffects": ["Task_ListView at 1280x720"],
  "steps": "async (page, lib) => { await lib.goView(page, 'T1', 'Task_ListView'); }",
  "clip": { "x": 286, "y": 112, "width": 1298, "height": 330 },
  "marks": [".grid-header-content > span"] }
```

Optional `pairs: [{"caption": "…", "before": "<file>.png", "after": "<file>.png"}]` adds more screenshot pairs to the card (files next to the JSON; `shotCaption` names the main pair). Screenshots: `<id>.<label>.png` next to the JSON (`before`, `after`, any extra label such as `smoke`).

## Coverage — `findings/<AREA>/coverage.json`

```json
[{ "tenant": "T1", "user": "none", "module": "", "page": "Login page", "route": "LoginPage",
   "state": "module dropdown open", "viewports": ["1600x900", "1280x720"],
   "checks": { "C1": "pass", "C2": "pass", "C3": "pass", "C4": "pass", "C5": "pass", "C6": "pass",
               "C7": "pass", "C8": "fail:A-10", "C9": "pass", "C10": "pass", "C11": "pass", "C12": "n/a", "C13": "pass" },
   "notes": "6 options, 337x30 each, no truncation." }]
```

## status.json (orchestrator)

```json
{
  "A-01": { "status": "fixed", "issue": "Column headers of most lists were cut to a few letters, so users could not tell the columns apart.", "fix": "New column min-width controller: …" },
  "B-02": { "status": "partly", "fix": "Headers fixed; long text columns still narrow (see brief)." },
  "E2-09": { "status": "legacy", "fix": "Same layout in the old app; accepted." },
  "_files": [["src/Controllers/GridColumnMinWidthController.cs (new)", "Minimum column width from the caption."]],
  "_notes": ["Every after image was taken on the final build with the same repro script as its before image."]
}
```

`status`: `fixed` · `partly` · `decision` (needs the user) · `open` · `legacy` (old app did the same, accepted) · `data` (data/deployment, not code) · `bydesign`. A finding without an entry shows as `open` and is listed by `gen-report.py` as "without status". `issue` is the plain-language description at the top of the card (one or two sentences: what the user sees and why it matters, no measurements); write it for every finding without a brief, since a brief's `issue` takes its place otherwise. Without either, the card falls back to the finder's technical `description` and `gen-report.py` lists the id as "without plain-language issue". Keep it generated from a small script (`make-status.py` with shared fix texts) when many findings share one fix.

## briefs.json (orchestrator)

One brief for every finding that is not `fixed`. Findings with the same cause share one group brief, so one decision in the report applies to all members.

```json
{
  "groups": {
    "WIDTH_TEXT": {
      "title": "Long text columns too narrow",
      "members": ["B-02", "B-04", "C-02"],
      "issue": "Headers readable now, but long text columns keep their old 50–70 px widths; rows grow to several hundred px.",
      "options": ["Explicit pixel widths in the model.", "Extend the min-width controller for memo/long text columns.", "Accept."],
      "rec": "Option 2: fixes every list without touching the model; user-dragged widths stay.",
      "recOption": 2,
      "effort": "M",
      "reply": "Answer to the user's comment from the last review round (optional).",
      "open": true
    }
  },
  "findings": {
    "A-05": { "issue": "Label sits on the edge between the green and red bar.", "options": ["Label next to the bar.", "Minimum red width.", "Accept."],
              "rec": "Option 1.", "recOption": 1, "effort": "S" }
  }
}
```

- `effort`: `S` (< 2 h), `M` (half a day to a day), `L`.
- `open: true` puts the finding under the report's "Open questions" filter (a question to the user is pending). Clear it once answered.
- After a decision, update `rec` to "Decided: …" and `reply` to what will be done, set `open` false, regenerate.

## review-decisions.json (written by serve-report.py or exported by the report, re-embedded on the next generation)

```json
{ "report": "UI sweep – MyApp", "saved": "2026-10-07T15:50:49+02:00",
  "decisions": {
    "A-01": { "decision": "approved", "option": 1, "at": "2026-10-07T11:50:49.996Z" },
    "B-02": { "decision": "rework", "comment": "option 2 please", "at": "2026-10-07T13:50:44.000Z" },
    "C-07": { "decision": "", "comment": "was this the same in the old app?", "at": "2026-10-07T12:01:10.000Z" } } }
```

`decision`: `approved` · `rework` · `""` (comment only, or a decision that was undone). `option`: the 1-based brief option the user approved (0 or missing when the step has no options). Every member of a group gets the same entry. The newer `at` wins when the server file, the embedded file, localStorage and an imported file disagree; an export uses `exported` instead of `saved`.
