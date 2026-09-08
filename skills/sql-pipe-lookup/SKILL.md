---
name: sql-pipe-lookup
description: Run READ-ONLY SQL lookups against a local app database (SQL Server / LocalDB) via a haiku subagent, returning a concise result — never raw sqlcmd logs in the main context. Discovers the connection from appsettings or Web.config, and includes the named-pipe fallback for when "(localdb)\mssqllocaldb" is unreachable ("SQL Server process failed to start", "Login timeout expired", State reported as Stopped). Use when the user asks to "check if a column/table exists in the db", "did the migration run / were the columns created", "run a SQL query", "query the PRM/WwReportDb database", "verify the schema", when a LocalDB connection fails or LocalDB looks broken, or invokes /sql-pipe-lookup.
---

# SQL Pipe Lookup

Read-only SQL against a local app database, with a hardened LocalDB connection path. **Two hard rules:**

1. **Always run the query inside a subagent** (`general-purpose`, `model: haiku` for simple reads; `sonnet` only if the query needs reasoning). Never call `sqlcmd` directly from the main loop — it floods the context with connection banners and result spam. The subagent returns only a concise, shaped summary. *Exception:* the connection diagnostics in Step 2 are terse and belong in the main loop — resolve the connection there, then delegate.
2. **Read-only by default.** `SELECT` / `INFORMATION_SCHEMA` / `sys.*` are fine. Any `INSERT`/`UPDATE`/`DELETE`/`MERGE`/`ALTER`/`DROP`/`CREATE`/`TRUNCATE` requires the user to explicitly confirm the write first — tell them exactly what will change and wait.

## When it fires

- "check if column/table X exists in the db"
- "did the migration run" / "were the columns created" / "verify the schema"
- "run this query" / "query the database" / "how many rows…"
- Confirming an XPO `AssemblyVersion` bump actually applied against the dev DB
- A LocalDB connection just failed, or LocalDB appears broken / "needs reinstalling"
- `/sql-pipe-lookup <question or query>`

## Step 1 — discover the connection (main loop, cheap)

**Never print the password.** Extract only server + database, masking any `Password=`/`Pwd=`.

**.NET Core / Blazor projects (appsettings):** read `ConnectionStrings:ConnectionString`, preferring the dev config — `appsettings.Development.json`, falling back to `appsettings.json`. These are often UTF-8 **with BOM** — parse with `utf-8-sig`:

```bash
python -c "
import json,re
d=json.load(open('Source/Prod/PRM.Blazor.Server/appsettings.Development.json',encoding='utf-8-sig'))
cs=d['ConnectionStrings']['ConnectionString']
print('server  :', (re.search(r'(?i)(data source|server)=([^;]*)',cs) or ['','','(n/a)'])[2])
print('database:', (re.search(r'(?i)(initial catalog|database)=([^;]*)',cs) or ['','','(n/a)'])[2])
print('auth    :', 'Integrated (SSPI)' if re.search(r'(?i)integrated security|sspi|trusted_connection',cs) else 'SQL login')
"
```

**.NET Framework / Web Forms projects (Web.config):** grep the `<connectionStrings>` block for `connectionString`. Expect **several** `<add name="ConnectionString">` entries with all but one commented out — the *active* (uncommented) one is the live target. In multi-tenant repos each tenant has its own entry, so read carefully rather than taking the first match:

```
Grep pattern "connectionString" in Source/Prod/<App>.Web/Web.config
```

Typical targets: `(localdb)\mssqllocaldb` with **Integrated Security** (no password — current Windows user). PRM → database `PRM_Blazor`; WwReportDb → one of `WwReportDb_IR` / `_MA40` / `_KAVIR_PROD` / etc.

## Step 2 — verify the server is reachable, and fall back to the pipe

Try the connection string as-is first (a one-line `SELECT 1` or the `sys.databases` probe below). If it connects, skip to Step 3.

### Recognising the LocalDB false negative

If `(localdb)\<instance>` fails with any of:

- `Error occurred during LocalDB instance startup: SQL Server process failed to start.`
- `Login timeout expired` / `Server is not found or not accessible`
- `SqlLocalDB.exe info <instance>` reporting `State: Stopped` with an empty `Instance pipe name`

**do NOT conclude LocalDB is corrupt and do NOT recommend a repair/reinstall.** That error is usually a lock collision, not a broken install.

**Why it happens.** `(localdb)\x` is not an address — the client driver (SNI) resolves it: look up the instance in the *calling session's* LocalDB state → auto-start it if it looks stopped → read back its named pipe → connect. A LocalDB instance with a blank `Shared name` is visible only to the logon session that started it. When the instance is already running from the user's interactive desktop session, a non-interactive session reads `State: Stopped`, so the driver tries to auto-start a **second** `sqlservr.exe` against the same `master.mdf` — which the live process holds an exclusive lock on. The spawn dies and surfaces as the misleading generic startup error. The engine was healthy the whole time.

**The tell:** the instance's `error.log` has entries *newer* than the reported `Last start time`. A stopped instance cannot write to its own log.

```bash
SqlLocalDB.exe info MSSQLLocalDB
```

```bash
Get-Content "$env:USERPROFILE\AppData\Local\Microsoft\Microsoft SQL Server Local DB\Instances\MSSQLLocalDB\error.log" -Tail 20
```

### The workaround — connect to the pipe directly

Skip the name-resolution layer and read the pipe off the running process. The instance's pipe is its `-s` argument:

```bash
Get-CimInstance Win32_Process -Filter "Name='sqlservr.exe'" | ForEach-Object { "PID $($_.ProcessId) :: $($_.CommandLine)" }
```

Look for the process whose `-d` path points at the instance's `master.mdf`; its `-s` value (e.g. `LOCALDB#C42CCE58`) is the pipe. Then:

```bash
sqlcmd -S "np:\\.\pipe\LOCALDB#C42CCE58\tsql\query" -d "<database>" -E -h -1 -W -s "|" -Q "SELECT name FROM sys.databases ORDER BY database_id;"
```

Confirm the expected database is in that list before running the real query — this also catches the case where the DB lives on a *different* instance than assumed.

**Pipe caveats:**

- The suffix is **regenerated on every LocalDB restart**. It is good only for the current instance lifetime — re-read it from the process if a previously working pipe stops resolving. Never cache it into a config file.
- The pipe works cross-session because its ACL grants the owning user; both sessions must be the same account.
- **Never kill the running `sqlservr.exe`** to "fix" the state — it is serving the user's running app.
- `SqlLocalDB start` is a dead end here: it fails precisely *because* the instance is already up. Don't retry it in a loop.

### Sibling checks when the DB isn't where expected

- A full SQL Server instance may also be installed and running alongside LocalDB — check `Get-Service MSSQL*` and probe `(local)`. Databases are **not** shared between instances; the same-named DB on the default instance may be a different copy, or absent.
- Tool paths, if not on PATH: `SqlLocalDB.exe` under `%ProgramFiles%\Microsoft SQL Server\<ver>\Tools\Binn\`, `sqlcmd` under `%ProgramFiles%\Microsoft SQL Server\Client SDK\ODBC\<ver>\Tools\Binn\` (also ships with SSMS / Azure Data Studio).

### Durable fix (offer, don't apply unprompted)

A shared instance is the supported cross-session mechanism:

```bash
SqlLocalDB.exe share MSSQLLocalDB SharedLocalDB
```

Then `(localdb)\.\SharedLocalDB` resolves from any session. Needs an **elevated** prompt and takes effect only on the next instance start — so it won't help until LocalDB is stopped and restarted from the user's desktop session. For a one-off lookup, reading the pipe is cheaper than restarting an instance the app is actively using.

## Step 3 — delegate the query to a subagent

Spawn `general-purpose` / `model: haiku`, hand it the **already-verified** server string + query, and demand a concise shaped result:

```
sqlcmd -S "<server-or-pipe>" -d "<database>" -E -h -1 -W -s "|" -Q "<read-only query>"
```

- `-E` = Integrated Security. For a SQL login use `-U <user> -P <pass>` instead (pass credentials to the subagent; keep them out of the main transcript).
- `-h -1` no headers, `-W` trim whitespace, `-s "|"` pipe separator — easy to parse and summarize.
- **If the verified server is a pipe, tell the subagent to use it verbatim and explicitly forbid substituting `(localdb)\…`** — otherwise it will "helpfully" fall back to the connection string from config and hit the same dead end.
- Instruct it: on connection failure, report the exact error text and stop — do not guess at data.

Tell the subagent: **return only the summary in the requested shape, no raw log.**

## Recipes

**Does a column exist (table-name-agnostic):**
```sql
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE COLUMN_NAME IN ('Col1','Col2')
ORDER BY TABLE_NAME, COLUMN_NAME;
```

**Full column list of one table:**
```sql
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'Notice' ORDER BY ORDINAL_POSITION;
```

**Table exists / row count:**
```sql
SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'Notice';
SELECT COUNT(*) AS Rows FROM Notice;
```

**Sample rows from a wide XPO table** — select a readable subset rather than `*`, truncate long text, skip `varbinary`:
```sql
SELECT TOP 5 OID, LEFT(CAST(Text AS nvarchar(max)),120) AS Text, CreationDate, GCRecord
FROM WwNote ORDER BY OID;
```

## XPO gotchas (interpret results with these in mind)

- **XPO adds columns on migration but NEVER drops them.** A deleted BO property leaves its column behind; a renamed property leaves the *old* column as an orphan alongside the new one. Finding an old column present is expected, not a bug — dropping it is a separate deliberate `ALTER TABLE ... DROP COLUMN`.
- **A new column existing = the `AssemblyVersion` bump migrated AND the app booted against that DB at least once.** If a new column is missing, the app likely hasn't been run against that DB since the bump.
- **Table name usually equals the BO class name; column name usually equals the property name** (1:1), unless overridden by `[Persistent("…")]`. Non-primitive / editor-backed properties can map to `varbinary`.
- **`GCRecord` is the soft-delete marker.** Non-NULL = deleted and invisible to the app, but still physically present. Always report it when dumping rows, and filter on `GCRecord IS NULL` when the question is about live data.
- **`OptimisticLockField`** is XPO concurrency bookkeeping — omit it from row dumps as noise.

## Output

Relay the subagent's concise summary directly. Add interpretation only where it matters (e.g. "old column still present — expected XPO behavior, harmless"; "these two rows are soft-deleted"). Do not paste raw `sqlcmd` output into the main context.

If the pipe fallback was needed, say so briefly and note that the pipe name is lifetime-scoped — the user's config is not broken and needs no edit.
