---
name: playwright-agent
description: Drive a running web app via the Playwright MCP during development (manual verification, bug repro, DOM exploration, UI smoke-tests) without flooding the main context window. Two levers — context-saving snapshot/evaluate tricks, and delegating click-storms to cheaper-model subagents that return only the verdict. Use when about to use Playwright MCP (mcp__playwright__browser_*) to inspect or interact with a live app, verify a UI change, reproduce a bug in the browser, or smoke-test a flow. NOT for authoring headless CI tests.
---

# Playwright via AI Agents

Goal: see the live app behave, spend almost no main-context tokens doing it.

**Why this matters:** a bare `browser_snapshot` dumps the entire accessibility tree (200–400 lines on a populated page) inline. Refs (`e123`) renumber on every DOM mutation, so re-snapshotting to refresh a ref is the main tax. Two levers cut it.

## Lever 1 — delegate the click-storm to a subagent (biggest win for multi-step flows)

Spawn an `Agent` to drive the browser sequence. It absorbs the giant snapshots in **its** context and returns only a pass/fail verdict + the specific values you asked for. Main context stays clean.

- **Model = cheapest that can do the job.** `model: haiku` for mechanical sequences (login, click-through, "does the view load"). `model: sonnet` when the step needs reasoning (CRUD correctness, behavior judgement). Reserve opus for the orchestrator.
- **`subagent_type: general-purpose`** (it needs to act, not just search).
- **One shared MCP browser → subagents MUST run sequentially.** Never spawn two browser-driving agents in parallel or in the background at once — they fight over the single browser/page. Wait for one to finish before the next.
- **Continue, don't re-spawn.** To extend a session with the browser state intact, `SendMessage` the same agent (its context + the live page persist). A fresh `Agent` call starts cold.

**Prompt the subagent with:** exact start URL/state · the precise steps · **exactly what to report back** · "report only the verdict + those values — do NOT paste snapshots or DOM."

> Example: "App at https://localhost:44318, logged in. Open `/AutomationRule_ListView`, click New, fill Name='X', Save. Report ONLY: did it save (yes/no), any validation/error text, the new grid row count. No snapshots."

## Lever 2 — if you drive it yourself, never snapshot raw

| Need | Do this | Not this |
|---|---|---|
| See page structure | `browser_snapshot` with `filename:` → then `Grep`/`Read` the file for the one element | bare `browser_snapshot` (dumps tree inline) |
| One fact (row count, cell text, URL, element present) | `browser_evaluate` returning a short string (it also takes `filename:`) | snapshot the whole tree to read one value |
| Inspect a subtree / dialog only | `browser_snapshot` with `target:` (parent ref/selector) + `depth:` | full-page snapshot |
| Click/type/navigate | pass a **stable selector** to `target:` (it accepts a unique selector, not just a ref) | re-snapshot just to grab a fresh `e###` ref |

More: `browser_evaluate` one-liners — `document.querySelector('[role=status]').textContent` → `"Data grid with 2 rows and 6 columns"`; current URL; `!!document.querySelector('…')` for presence.

**Suppress noise:** don't pull `browser_console_messages` / `browser_network_requests` unless actively debugging. `browser_take_screenshot` costs vision tokens and can't be acted on — save to `filename:` for a one-off visual check, don't spam it.

**Refs are disposable:** they're valid only within one snapshot and renumber after any post-back. Drive by selector via `target:`, don't chase fresh refs.

## App-specific DOM gotchas

If the target is the PRM Blazor / DevExpress XAF app, the selector pitfalls (virtual-twin buttons, `data-action-name`, modal scoping, accordion nav, composite editors with no accessible name, validation present-but-hidden) are documented in `resources/playwright/playwright-mcp-tips.md` and `playwright-devexpress-testing-guide.md` (in the PRM repo). Hand the subagent the relevant selector facts in its prompt so it doesn't rediscover them.

## When a flow proves out

Discovery via MCP is a **one-time** token spend. If a flow needs to run repeatedly (regression), codify it as a headless test instead of re-driving it with AI every time — see the testing guide above. (Out of scope here: this skill is for dev-time interaction, not CI.)
