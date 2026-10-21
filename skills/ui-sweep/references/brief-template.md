# Finder brief template

Fill every `{{PLACEHOLDER}}`, save the result as `<sweep dir>/BRIEF.md`, and give each finder agent: "Read `<sweep dir>/BRIEF.md` and follow it. You are agent `<AREA>`. Your assignment: …" plus its users, modules and pages (from `nav.json`).

| Placeholder | Content |
|---|---|
| `{{APP}}` | App name, stack, branch / build being swept |
| `{{AGENT_COUNT}}` | Number of finder agents |
| `{{ENVIRONMENT_TABLE}}` | Markdown table: tenant/environment, URL, DB (or "n/a") |
| `{{SWEEP_DIR}}` | Absolute sweep folder (forward slashes) |
| `{{ROUTING_HINTS}}` | How pages are addressed (`goView` routes, how to get record ids for detail pages, read-only SQL example) |
| `{{HARD_RULES_PROJECT}}` | Project-specific forbidden controls, in the UI language (save/delete/send/approve buttons, workflow actions, SSO button text) |
| `{{PERSISTED_UI_STATE}}` | Which UI actions the app saves per user (column widths, sort, grouping, filters, layouts, theme, size mode) |
| `{{OUT_OF_SCOPE}}` | Tenants, modules, known/accepted issues the user excluded |
| `{{SOURCE_ROOT}}` | Read-only source root for `suspectedCause` lookups, with the file kinds worth searching (model files, CSS, views, resources) |
| `{{UI_LANGUAGE}}` | Expected UI language |
| `{{MAIN_VIEWPORT}}` / `{{NARROW_VIEWPORT}}` | e.g. `1600×900` / `1280×720` |

---

# UI sweep brief ({{APP}})

You are one of {{AGENT_COUNT}} sweep agents. Your job is to **find and document** visual defects on your assigned pages, precisely. You do **not** fix anything and you do **not** edit product code.

## Environment (already running, do not restart or build anything)

{{ENVIRONMENT_TABLE}}

- Sweep folder: `{{SWEEP_DIR}}` (below: `$S`).
- Helper library: `$S/sweep-lib.mjs` (read it first, and `$S/adapter.mjs`). Exports `launch(w,h)`, `open({tenant,user,module,width,height})` (launch + login, returns `{browser, context, page}`), `login(page, tenant, user, module)`, `goView(page, tenant, route)`, `settle(page)`, `expandNav(page)`, `navTree(page)`, `audit(page, scopeSelector?)`, `shot(page, file, {clip, marks, pad, fullPage})`, `url(tenant, route)`, `TENANTS`, `VIEWPORTS`, `SWEEP_DIR`.
- Navigation map of every tenant/user/module: `$S/nav.json`.
- Run Node scripts with Bash: `cd $S && node work/<AGENT>/<script>.mjs`. Put your own scripts in `$S/work/<AGENT>/` and import the helper with `import * as lib from '../../sweep-lib.mjs'`.
- Each `node` run is its own headless browser and must log in at its start. Batch several pages per script.
- For exploration (finding a state, a selector, a measurement) you may use `playwright-cli` with a named session (`-s=<AGENT>-<tenant>`); see the "Browser tooling" rules you were given. Do not use the Playwright MCP.
{{ROUTING_HINTS}}

## Hard rules (violating any of these is worse than missing a finding)

1. **Never type a password.** Log in only through `lib.login` / `lib.open` with the users of your assignment. Never touch a third-party sign-in button (SSO, "Sign in with …").
2. **Never save or change data.** Do not click save, delete, send, approve/reject, clone/copy, mail-sending, workflow/status actions, or anything that executes a business action. You may open dropdowns, popups, tabs, "new record" views and lookup editors to *look* at them, then close with Escape / Cancel / Close; if asked whether to save changes, answer **No / Discard**. Never type into editors of existing records.
3. **Do not change persisted UI state.** {{PERSISTED_UI_STATE}} No column resizing/reordering, no sorting by header click, no grouping, no saving filters or layouts, no layout customization, no theme or size-mode switches. Typing into a list's search box or opening a column filter popup and closing it with Escape is fine. Switching detail tabs and opening popups to look at them is allowed even if the app remembers the active tab: the orchestrator restores persisted UI state from a backup at the end, so do not spend effort resetting it.
4. **No DB writes** of any kind. SQL only for `SELECT`.
5. Do not edit any file outside `$S/work/<AGENT>/` and `$S/findings/<AGENT>/`. Do not build, restart hosts, or run git.
6. Project-specific: {{HARD_RULES_PROJECT}}
7. Out of scope, do not report: {{OUT_OF_SCOPE}}; anything that only shows in browser devtools.

## What to check on every page and every state (the checklist)

Check each item explicitly. Use `lib.audit(page)` for measured candidates, then **look at a screenshot yourself with the Read tool** (mandatory for every page at {{MAIN_VIEWPORT}}) and confirm or reject every candidate. Heuristics produce false positives — only report what you have confirmed visually *and* by measurement.

| Code | Check | Defect threshold (be exact) |
|---|---|---|
| C1 | **Truncated text, horizontal** – captions, labels, column headers, tab titles, buttons, nav items, field values, combo values | Text visibly cut or ellipsized so that a word is not readable (e.g. "Ex…", "Pr… St…"). Report text, visible width vs needed width in px. Grid *data* cells ellipsized only count when the column cannot show typical values at all. |
| C2 | **Clipped text, vertical** – multi-line captions or values cut at top/bottom | Any glyph cut. Report text height vs visible height. |
| C3 | **Missing or broken icons** – 404 images, empty SVGs, nav items/actions/object types without icon where siblings have one, generic placeholder icons | Any. Report the image name/URL and where. |
| C4 | **Padding** – text touching a border, bar, background box or button edge | Gap between text and the box edge < 4 px. Report gap in px per side. |
| C5 | **Spacing** – distinct boxes/rows/groups/sections glued together or inconsistently spaced | Vertical or horizontal gap between visually distinct boxes < 4 px, or equivalent siblings with gaps differing by > 4 px. Report gaps in px. |
| C6 | **Alignment** – labels, values, columns, buttons that should line up | Left/right edges or baselines of elements meant to align differ by > 2 px; inconsistent label widths within one layout group. |
| C7 | **Missing/empty/raw text** – empty captions, buttons without text/icon/tooltip, "N/A", "null", "{0}", auto-generated group captions, technical names (property, class or view ids), placeholder text left in | Any. |
| C8 | **Language** – text not in {{UI_LANGUAGE}} or mixed (captions, buttons, tooltips, placeholders, empty-state text, dialogs, validation messages), spelling/grammar errors, inconsistent terminology inside one tenant | Any. Quote the exact text. |
| C9 | **Overlap** – elements drawn over each other | Overlap > 2 px between unrelated elements. |
| C10 | **Overflow / scrollbars** – unintended horizontal scrollbars, content wider than its container, popups cut off by the viewport, buttons out of view | Any unintended. |
| C11 | **Narrow viewport** – repeat C1, C2, C9, C10 at {{NARROW_VIEWPORT}} (`lib.launch(w, h)` or `page.setViewportSize`) | Report only what breaks at {{NARROW_VIEWPORT}} but not at {{MAIN_VIEWPORT}}, tagged with viewport. |
| C12 | **Console/network errors** – `audit()` returns `consoleErrors` and `failedImageRequests` | Record; report as a finding only if it causes a visible defect, otherwise list in coverage notes. |
| C13 | **Fonts and text metrics** – the font each surface asks for vs the one it gets, and what the difference does to the text. Browser: computed `font-family` of body, captions, grid cells, editors, rich-text content (incl. inline styles in stored HTML), `document.fonts.check()` for each requested face, font requests in the network log. Server-drawn output: reports (preview and every export: PDF, DOCX, XLSX, CSV), charts rendered as images, generated documents and mails — read the fonts the layouts/templates request, check them against the render host (`fc-list`/`fc-match` in a container, the fonts folder on Windows) and the fonts embedded in exported PDFs. Compare with the reference build (old app or previous release) on the same data. | Any requested face that silently falls back on one side; any label or value cut with "…" or hidden; a word broken mid-word; changed line breaks, row heights or page count; replacement glyphs (boxes, missing umlauts/€). Report per surface: requested font, resolved font, and counts (cut labels, mid-word breaks, pages) for each side. |

## Output

1. **Coverage** — `$S/findings/<AGENT>/coverage.json`: an array with one entry per page/state you examined:
   ```json
   { "tenant": "T1", "user": "alice", "module": "Main", "page": "Orders – list", "route": "Order_ListView", "state": "default | tab Items | popup New note | …", "viewports": ["1600x900", "1280x720"], "checks": { "C1": "fail:B-03", "C2": "pass", "...": "...", "C12": "pass", "C13": "pass" }, "notes": "short, optional" }
   ```
   Every check C1–C13 must have `pass`, `fail:<finding ids>` or `n/a` for every entry. This is what proves to the user exactly what was looked at.
2. **Findings** — one file per defect `$S/findings/<AGENT>/<AGENT>-NN.json` (NN = 01, 02, …):
   ```json
   {
     "id": "B-03",
     "tenant": "T1", "user": "alice", "module": "Main",
     "viewport": { "width": 1600, "height": 900 },
     "page": "Order – detail, tab Items",
     "route": "Order_DetailView/<id>",
     "check": "C1",
     "severity": "high | medium | low",
     "title": "Column headers of the Items grid are cut to 'Ex…', 'Pr… St…'",
     "description": "Exact description with measurements: element, text, px values, how many items affected.",
     "measurements": { "free form": "numbers you measured" },
     "expected": "What correct looks like.",
     "suspectedCause": "Best guess where it comes from (model/column width, layout group, CSS rule, missing caption, missing icon), incl. file and line if you can find it read-only in {{SOURCE_ROOT}}.",
     "alsoAffects": ["other tenants/pages with the same defect; keep one finding per root cause"],
     "steps": "async (page, lib) => { await lib.goView(page, 'T1', 'Order_DetailView/<id>'); await page.getByText('Items', { exact: true }).click(); }",
     "clip": "CSS selector or {x,y,width,height} framing the defect with context (not the whole page unless needed)",
     "marks": ["CSS selector(s) or {x,y,w,h} rects to outline in red"]
   }
   ```
   - `user` may be `"none"` for login-page findings; then `steps` must navigate to the login page itself.
   - `steps` must be **deterministic and re-runnable after a fix**: start with `lib.goView(...)`, then clicks to reach the state. Prefer stable selectors (text, captions, view ids, semantic classes) over generated ids. `clip`/`marks` selectors must also still match after a CSS/model fix. No data changes in steps.
   - Severity: **high** = information unreadable/missing or user cannot use the element; **medium** = clearly visible cosmetic defect on a frequently used page; **low** = minor cosmetic or rare page.
3. After writing the findings, generate the before screenshots with the shared runner (this verifies your repro):
   `cd $S && node run-repros.mjs --label before --dir findings/<AGENT>`
   Then **Read every `<id>.before.png`** and confirm it shows the defect clearly with the red outline. Fix the finding JSON and re-run until all are OK.
4. Deduplicate: the same root cause on many pages is **one** finding with `alsoAffects` listing the other places (one representative screenshot). If a finding obviously belongs to another agent's area, still report it if you saw it.

## Final answer to the orchestrator

Return only: number of pages/states covered, number of findings by severity, a one-line list of finding ids with titles, and any rule you could not follow or anything that blocked you. Keep it under 40 lines. No screenshots inline.
