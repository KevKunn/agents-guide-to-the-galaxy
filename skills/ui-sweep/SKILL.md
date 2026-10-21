---
name: ui-sweep
description: "Systematic UI sweep of every page, tab, popup and state per tenant/user/module against a 13-point checklist (incl. fonts in reports and exports), with parallel finders, before/after screenshots, a fix loop and an interactive review report. Use after migrations, upgrades or redesigns, for 'UI sweep', 'visual audit', or /ui-sweep."
---

# UI sweep

A sweep finds visual defects across a whole app, proves each one with a measured description and a replayable screenshot, fixes what the user approves and shows the result side by side. The orchestrator (you) plans, partitions, verifies and fixes; finder subagents only find and document.

Skill files (`~/.claude/skills/ui-sweep/`):
- `references/brief-template.md` – the finder brief: hard rules, checklist C1–C13 with exact thresholds, finding/coverage schema, output steps.
- `references/schemas.md` – config, finding, coverage, `status.json`, `briefs.json`, `review-decisions.json`.
- `references/adapters.md` – adapter contract, readiness, auth, persisted UI state, XAF Blazor example, notes for other stacks.
- `scripts/` – `sweep-lib.mjs` (generic core), `run-repros.mjs` (replays findings into `<id>.<label>.png`), `enum-nav.mjs` (navigation map), `gen-report.py` (review report), `serve-report.py` (serves the report and saves decisions), `sweep.config.example.json`, `adapter.xaf-blazor.example.mjs`, `ui-state.xaf-sql.example.ps1`.

## When to use

- After a migration (e.g. Web Forms → Blazor, AngularJS → Angular), a major framework/component version upgrade, a theme or CSS overhaul, or before a release, when "does every page still look right" has to be answered with evidence.
- Not for a single page or a single bug (just look at it), and not for functional/E2E testing.

## Phases (checklist)

### 1. Setup
- [ ] Agree with the user: tenants/environments, users (with their roles), modules, viewports (default 1600×900 + 1280×720), the expected UI language, and the **out-of-scope list** (excluded tenants, archived modules, accepted known issues). Write it down; it goes into the brief.
- [ ] Start the app(s) yourself, one host per tenant on its own port and DB, from an existing build, with background jobs/mail disabled and throw-away keys; poll the login page until it answers. Ask before touching shared or production-like data.
- [ ] Create the sweep dir (untracked, e.g. `<repo>/tmp/sweep`), copy `scripts/sweep-lib.mjs run-repros.mjs enum-nav.mjs gen-report.py serve-report.py` into it, copy `sweep.config.example.json` to `sweep.config.json` and fill it.
- [ ] Write `adapter.mjs` (start from `adapter.xaf-blazor.example.mjs` or from the contract in `references/adapters.md`). Find login, routes and the loading indicators with `playwright-cli` first.
- [ ] Make `playwright` resolvable for Node: the lib tries `playwrightFrom` from the config, then the sweep dir's `node_modules`, then the `playwright` bundled with the global `@playwright/cli` install (`$(npm root -g)/@playwright/cli/node_modules`). The original sweep pointed `createRequire` at another project's folder that had `node_modules/playwright`; that is what `playwrightFrom` is for. Browsers must be installed for that Playwright version.
- [ ] **Back up persisted per-user UI state before the first browser opens** – the app may save layouts, column widths, filters, sort order while you browse. For XAF use `ui-state.xaf-sql.example.ps1 -Mode Backup`; for other apps find the settings table/column and export it. Note the restore command in the log.
- [ ] **Font inventory (C13) before the finders start:** list every surface that draws text (browser pages, report preview, each export format, chart images, generated documents, mails), the fonts each one requests (CSS, report layouts, templates, inline styles in stored HTML such as pasted Word text) and the fonts installed where it is drawn (the browser machine, the server or container: `fc-list`/`fc-match`, Windows fonts folder). Ask the user which corporate font is expected where, and whether the production servers have it. Give the result to the finder of the reports/exports area; a font missing on the render host changes output that no browser screenshot shows.
- [ ] Smoke-test the adapter: one `node -e` script that logs in, runs `navTree`, `audit` and `shot` on one page; Read the PNG. Also open one detail page by the route pattern you will put into the brief and run any SQL hint once: a wrong route or table name in the brief costs every finder time (in the dry run the detail view of the listed class lived under a different class name).

### 2. Navigation map and areas
- [ ] Fill `navPlan` and run `node enum-nav.mjs` → `nav.json` (every leaf link per tenant/user/module). Users with different roles see different menus; map each.
- [ ] Partition into areas of similar size (e.g. A login/shell/navigation/start screens, B–D per-tenant core lists and detail views, E reports/charts, F master data/admin …), put them in `areas` in the config.
- [ ] Fill `references/brief-template.md` into `<sweep dir>/BRIEF.md` (write it with a script, check no `{{…}}` is left; write `sweep.config.json` with a JSON serializer, not a heredoc, so regex escapes survive).
- [ ] Spawn **one finder subagent per area, all in parallel**, each with: "Read BRIEF.md, you are agent X", its users/modules/pages from `nav.json`, and the Browser tooling rules below. Use a model that judges screenshots well. Finders return ≤ 40 lines.

### 3. Verification (orchestrator)
- [ ] Read every `coverage.json`: every page of `nav.json` covered, every check has `pass`/`fail:<ids>`/`n/a`. Send gaps back to the finder (SendMessage) or cover them yourself.
- [ ] Read every `<id>.before.png`. Reject findings the image does not show, measurements that do not hold, and anything in the out-of-scope list.
- [ ] Deduplicate across areas by root cause: one finding per cause, the rest into `alsoAffects`. Same CSS rule, same model default, same missing translation key = one finding.
- [ ] Optionally have an independent reviewer subagent check the before images against the descriptions.

### 4. Fix loop
- [ ] Branch off for the fixes (never on the main branch). For each finding first check whether the **old app already had the same defect** (legacy parity): if yes, default is accept (`status: legacy`), fix only if the user asks.
- [ ] Fix by root cause, preferring one general fix (a controller, a CSS rule, a model default) over many local ones. Fixes must never write into persisted user state (computed widths reverted before the app saves, etc.).
- [ ] Rebuild, restart the hosts on the fixed build, run `node run-repros.mjs --label after` (`--dir`, `--id`, `--per-tenant` to narrow or parallelise). Read every after image yourself.
- [ ] Write `status.json` (`fixed`/`partly`/`decision`/`open`/`legacy`/`data`/`bydesign` + fix text, a plain-language `issue` for every finding without a brief, `_files`, `_notes`). An independent reviewer per round comparing before/after pairs catches regressions (the original needed four rounds).

### 5. Review with the user
- [ ] Write `briefs.json`: a decision brief (Issue, Options, Recommendation, Effort) for **every non-fixed finding**; findings with the same cause share one group brief so a single decision covers the group.
- [ ] `python gen-report.py` → `report/ui-sweep-report.html` (self-contained). It opens in **review mode**: one step per finding or decision group, a hideable step list, compact (text left, screenshot right, with a draggable divider) or comfortable density, light/dark/system theme, before / after / both (next to or below each other, `L`) with a zoomable full-screen view, options as cards (the approved option is recorded), approve / needs work / comment with group propagation, undo toast plus Z/Ctrl+Z, an optional jump to the next undecided step, and keyboard shortcuts (`?`). **List mode** has KPIs, status/decision/open-question filters, quick decisions, import, copy summary, changed files, notes, checks, areas and the coverage matrix. Settings are remembered per browser.
- [ ] Serve it with `python serve-report.py <sweep dir>` (default `http://127.0.0.1:8765/ui-sweep-report.html`, a background command) and open it in the user's browser or the app's browser pane. Every change is saved to `report/review-decisions.json` (newest entry wins, so several browsers stay in sync, and decisions an older page kept in browser storage are uploaded on first open). Opened as a file, the page keeps decisions in that browser only and says so; Export/Import stay as a fallback. Never test-click decisions on the user's live page; if you must, clear the browser storage and remove the entries again.
- [ ] Read `report/review-decisions.json` (it is embedded on the next generation). Read the comments and chosen options, answer comments in the brief's `reply`, mark pending questions `open: true`, regenerate (the served page picks up the new file on reload), and discuss the open questions in chat.
- [ ] Implement in the order the user approves, re-run `--label after` for the touched findings, update `status.json`/`briefs.json`, regenerate. Repeat until every finding is decided.

### 6. Close
- [ ] Restore persisted UI state (with the user's go) and **verify it is unchanged** against the backup (XAF: `-Mode Compare` shows 0 changed). Report anything added by the sweep (e.g. a locale aspect) instead of deleting it silently.
- [ ] Stop the hosts you started, delete `.auth/` storage states.
- [ ] Write a summary log in the project's log/notes location: scope, counts by status, commits, side effects and their clean-up, what was not verified live, how to regenerate the report.

## Browser tooling

- **Exploration: `playwright-cli`** (not the Playwright MCP). One named session per tenant/user: `playwright-cli -s=T1-alice open <url>`; log in once, then `state-save .auth/T1-alice.json` and `state-load` it in new sessions to avoid re-logins. Use `--raw eval "<js>"` for measurements (bounding boxes, `scrollWidth` vs `clientWidth`, computed styles), `find "<text>"` and `snapshot --depth=3` / `snapshot <ref>` instead of reading full snapshots, and `screenshot --filename=<file>.png` to disk – Read only the images you actually judge.
- **Codify, then replay with Node.** Every confirmed finding becomes `steps`/`clip`/`marks` in its JSON; `run-repros.mjs` replays them with the Playwright library (zero tokens per replay, one login per tenant/user/module/viewport group, tenants in parallel). Finder scratch scripts use `import * as lib from '../../sweep-lib.mjs'` and `lib.audit` for candidates.
- playwright-cli pitfalls seen in practice: refs go stale after every navigation (take a fresh `snapshot` or use locator strings like `'getByRole("button", { name: "…" })'`); icon-only buttons that are `aria-hidden` have no ref (measure with `--raw eval`, then `mousemove`/`mousedown`/`mouseup`); `find` can miss items inside an open listbox (snapshot the listbox ref); pass absolute paths to `state-save`. Batch screenshots stay faster in Node (one login, about 5 s per state).
- `audit()` returns candidates only (truncated, clipped, broken images, tight padding, raw text, foreign-language words, empty buttons, overlaps, console errors, failed image requests). Nothing is a finding until it is confirmed on a screenshot.

## Hard rules (also in the brief)

- Never type a password and never script a third-party SSO/identity provider; use password-empty test users or a storage state the user created by signing in themselves.
- Never save or change data, never change persisted UI state (no column resize/reorder, header sort, grouping, saved filters/layouts, theme switch) while sweeping; no DB writes.
- Respect the out-of-scope list; do not report or "quickly fix" excluded areas.
- Finders do not edit product code, build, restart hosts or run git.

## Lessons learned

- **Legacy parity first.** Before fixing, ask "did the old app do the same?" (same layout record, same counting, same data). Default is accept; fix only on request.
- **One finding per root cause.** Forty cut headers from one column-width rule are one finding with a long `alsoAffects`, not forty.
- **Heuristics lie.** The audit flags hidden helpers, intentional ellipses, decorative overlaps. Always confirm by reading the screenshot; finders and orchestrator both.
- **Deterministic steps that survive the fix.** Start at `goView`, use captions/view ids/semantic classes, never generated ids or coordinates that move after the fix; `clip`/`marks` must still match after the fix so the after image frames the same spot.
- **Readiness decides speed and truth.** Wait for *visible* busy indicators, not present ones; a hidden permanent loader turned an 11-minute replay into over an hour. One login per group, tenants in parallel.
- **Fixes can leak into persisted state.** A runtime column-width controller saved its widths into users' layout rows; the backup made the clean-up a restore instead of a guess. Back up before, compare during, restore after.
- **Browser locale creates state too.** A sweep browser with a new locale can create per-user language entries; list them at the end.
- **Decision briefs scale the review.** Issue / Options / Recommendation / Effort per non-fixed finding, grouped by cause, let the user decide 100+ findings in one sitting; record answers in `reply` and keep `open` for pending questions.
- **Independent review rounds.** A reviewer comparing before/after pairs found regressions the fixer missed (cut sorted headers, 0 px columns, overlaps introduced by the fix). Re-shoot after every correction.
- **Re-sweeps find gaps in earlier fixes.** A fix applied per view (a default filter on two of seven generated mail tabs) or tuned on sample captions (a header width estimate that undercounted "m") leaves the rest broken. Prefer fixes that cover every generated view, and after a width/metric change re-shoot a sample of earlier width findings as a regression check.
- **Fonts break server-drawn output first.** A move from Windows/IIS to Linux containers kept every browser page identical but changed every report: the layouts asked for fonts the image did not carry, the renderer fell back silently, and chart labels in Word/Excel exports were cut with "…" so values could not be read, words broke mid-word in the PDF and page counts moved. Check each export format separately (they can render charts differently from the preview), count cut labels per side, and check what the production render host actually has before calling the old output the baseline.
- **Keep finder output small.** ≤ 40 lines back to the orchestrator; everything else lives in the JSON and PNG files.
