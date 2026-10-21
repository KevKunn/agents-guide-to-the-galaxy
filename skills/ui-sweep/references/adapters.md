# App adapters

`sweep-lib.mjs` is stack-neutral. Everything that depends on the app lives in `<sweep dir>/adapter.mjs`, an ES module the lib imports at start. Every function receives the Playwright `page` and the `lib` object (`lib.url(tenant, route)`, `lib.settle(page, ms)`, `lib.CONFIG`, `lib.TENANTS`, …).

## Contract

| Export | Required | Purpose |
|---|---|---|
| `login(page, lib, { tenant, user, module })` | yes, unless every finding uses `user: "none"` | Reach a logged-in start page. **Never types a password** (see Auth below). Ends with `lib.settle`. |
| `navTree(page, lib)` | for `enum-nav.mjs` | Returns `[{ text, href, groups }]` for every leaf navigation link of the logged-in user; `groups` is the group path joined with `" / "`. Expand collapsed groups first. |
| `busySelectors` | recommended | Array of selectors of loading indicators; `settle` waits until none of them has a client rect (visible). |
| `ready(page, lib)` | optional | Extra readiness wait run inside `settle` (e.g. a framework idle flag). Errors are ignored. |
| `goView(page, lib, tenant, route)` | optional | Open a page by route. Default: `page.goto(lib.url(tenant, route))` + `settle`. |
| `expandNav(page, lib)` | optional | Expand all navigation groups (used by finders before screenshots of the menu). |
| `isLoggedIn(page, lib)` | with `reuseStorageState` | Called after loading a saved storage state and opening the root URL; `false` triggers a fresh login. |
| `auditOptions` | optional | `{ ignore: selector, rawExtra: regex }` – framework helper elements to skip, framework-specific technical names for C7. |

### Readiness is the hard part

A screenshot taken before the page is really done is a false finding. `settle` does: `networkidle` (≤ 15 s) → wait until no `busySelectors` element is visible (≤ 30 s) → `ready()` → fixed wait `settleMs`. Pick busy selectors by watching a slow page with `playwright-cli` (`snapshot --depth=3` while loading, `--raw eval` for `document.querySelectorAll('<candidate>').length` and `getClientRects().length`). Check that the selector is *not* present-but-hidden on idle pages; a permanently present hidden element is why the visibility test uses `getClientRects()`.

### Routes

Make pages addressable by URL wherever possible; `steps` that start with `lib.goView` survive fixes. When the app has no deep links, `goView` can navigate through the menu (`navTree` text) – keep it deterministic and avoid anything that persists state.

### Auth

- Preferred: test users with empty passwords or a dev-only passwordless login; `login` fills the user name only.
- If the app needs a password or an SSO provider: do **not** script it. Ask the user to sign in once in a headed `playwright-cli -s=<tenant>-<user> open <url> --headed` session, then `playwright-cli -s=<tenant>-<user> state-save <sweep dir>/.auth/<file>.json`, and load that file (`lib.launch(w, h, { storageState })`, or name it as `lib.open` expects and set `reuseStorageState`). The user types; the agent never sees or enters the secret.
- Storage state files hold session cookies: keep them in `.auth/`, out of git, delete them at the end.

### Persisted per-user UI state

Many enterprise UIs save column widths, sort order, grouping, filters, splitter positions, theme or layout per user on the server while you browse – sometimes even without an explicit action (a runtime width written back on close). Before the first browser opens, find where the app stores it and back it up; compare during the sweep and restore at the end (with the user's go). Typical places: a model-differences table (XAF), a user-settings/preferences table, localStorage (lost with the context anyway, harmless), a profile JSON column.

## Worked example: DevExpress XAF Blazor

`scripts/adapter.xaf-blazor.example.mjs` comes from a sweep of a multi-tenant XAF Blazor app (German UI).

- **Login.** XAF's logon page has DevExpress text editors (`input.dxbl-text-edit-input`); the example fills the user name of a password-empty test user and clicks the German "Anmelden" button. That app also had a custom module combobox on the logon page (`input[role=combobox]`, options in `[role=listbox] [role=option]`), which the example selects when a `module` is given. Wait for `waitForURL(u => !/LoginPage/)`, then `settle`.
- **Routes.** XAF Blazor views are routable by view id: `<base>/<ViewId>` for list/dashboard views, `<base>/<ClassName>_DetailView/<Oid>` for detail views, `LoginPage` for the logon page. Get Oids by double-clicking a list row and reading `page.url()`, or with a read-only `SELECT TOP 3 Oid …`.
- **Readiness.** Busy indicators: `.xaf-loading`, `.dxbl-loading-panel`, `.dxbl-wait-indicator`. A hidden `div.xaf-loading` stays in the DOM on idle pages, which is why `settle` tests visibility; waiting on its mere presence (timeouts on every step) was the main reason a full replay took over an hour, against ~11 minutes with the visibility test and one login per group.
- **Navigation.** Accordion groups: `.dxbl-accordion-group-header[aria-expanded=false] .dxbl-group-expand-btn` (click via `evaluate(e => e.click())`, the header can be covered); links: `.dxbl-accordion-items-container a[href]`; group captions: `.xaf-nav-link` under `.dxbl-accordion-group-header` of `dxbl-group-control.dxbl-accordion-item` / `.dxbl-accordion-item.has-children`.
- **Audit tweaks.** Skip `.dxbl-a11y-status-helper` (screen-reader helper with text); add `_(ListView|DetailView)` to the raw-name regex (a view id shown as caption).
- **User model differences are persisted state.** With `DisableModelSaving=false` XAF writes per-user layout changes (column widths, sort, grouping, filters, split positions, theme) into `ModelDifference` / `ModelDifferenceAspect`. A controller that changes widths at runtime can leak them into these rows when XAF saves the model on close. `scripts/ui-state.xaf-sql.example.ps1` backs up all aspects per database (`-Mode Backup`, refuses to overwrite), lists changed/added/missing aspects (`-Mode Compare`, `-DumpDir` for XML diffs) and writes the backed-up XML back (`-Mode Restore`, one transaction per DB). Verify the column names against your XAF version before the first run. New aspects created by the sweep (e.g. a language aspect from the browser locale) are only listed, never deleted automatically.
- **Hosts.** Start each tenant from the already built output (`dotnet run --no-build --no-launch-profile`) on its own port with its own DB, background jobs and mail disabled, throw-away signing keys, logs to files, and poll the login page until it answers.

## Notes for other stacks

- **SPA (React/Angular/Vue).** Route by URL; readiness = `networkidle` + absence of the app's spinner/skeleton classes + optionally a `ready()` that waits for `document.fonts.ready` or an app flag. Disable animations for stable screenshots (`page.emulateMedia({ reducedMotion: 'reduce' })` in `ready`).
- **Server-rendered (Razor Pages, MVC, Web Forms, Django, Rails).** `goView` is a plain `goto`; `busySelectors` often empty; watch for postback-driven tabs, which need clicks in `steps`.
- **Auth via storageState.** For OIDC/SSO apps use the headed sign-in plus `state-save` described above; tokens expire, so re-ask the user when `isLoggedIn` returns false instead of scripting the provider.
- **Multi-tenant via host names or headers.** Put the full base URL per tenant in `tenants`; for header-based tenants add `extraHTTPHeaders` by adapting `launch` in a project copy of the lib.
