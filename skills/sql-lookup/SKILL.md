---
name: sql-lookup
description: Run READ-ONLY SQL lookups against the PRM app database (SQL Server / LocalDB) via a haiku subagent, returning a concise result — never raw sqlcmd logs in the main context. Discovers the connection from appsettings, defaults to read-only (writes/DDL require explicit user confirmation). Use when the user asks to "check if a column/table exists in the db", "did the migration run / were the columns created", "run a SQL query", "query the PRM database", "verify the schema", or invokes /sql-lookup.
---

# SQL Lookup

Read-only SQL against the PRM app database. **Two hard rules:**

1. **Always run the query inside a subagent** (`general-purpose`, `model: haiku` for simple reads; `sonnet` only if the query needs reasoning). Never call `sqlcmd` directly from the main loop — it floods the context with connection banners and result spam. The subagent returns only a concise, shaped summary.
2. **Read-only by default.** `SELECT` / `INFORMATION_SCHEMA` / `sys.*` are fine. Any `INSERT`/`UPDATE`/`DELETE`/`MERGE`/`ALTER`/`DROP`/`CREATE`/`TRUNCATE` requires the user to explicitly confirm the write first — tell them exactly what will change and wait.

## When it fires

- "check if column/table X exists in the db"
- "did the migration run" / "were the columns created" / "verify the schema"
- "run this query" / "query the PRM database" / "how many rows…"
- Confirming an XPO `AssemblyVersion` bump actually applied against the dev DB
- `/sql-lookup <question or query>`

## Step 1 — discover the connection (main loop, cheap)

Read `ConnectionStrings:ConnectionString` from appsettings, preferring the dev config:

1. `Source/Prod/PRM.Blazor.Server/appsettings.Development.json`
2. fall back to `Source/Prod/PRM.Blazor.Server/appsettings.json`

These files are often UTF-8 **with BOM** — parse with `utf-8-sig`. **Never print the password.** Extract only server + database (mask any `Password=`/`Pwd=`):

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

The typical PRM dev target is `(localdb)\mssqllocaldb`, database `PRM_Blazor`, **Integrated Security** (no password — uses the current Windows user).

## Step 2 — delegate the query to a subagent

Spawn `general-purpose` / `model: haiku`, hand it the connection + query, and demand a concise shaped result. `sqlcmd` invocation template (clean, pipe-delimited, no rowcount/banner noise):

```
sqlcmd -S "<server>" -d "<database>" -E -h -1 -W -s "|" -Q "<read-only query>"
```

- `-E` = Integrated Security. For a SQL login use `-U <user> -P <pass>` instead (pass credentials to the subagent; keep them out of the main transcript).
- `-h -1` no headers, `-W` trim whitespace, `-s "|"` pipe separator — easy to parse and summarize.
- If `sqlcmd` isn't on PATH: `SqlLocalDB.exe info` confirms the LocalDB instance; `sqlcmd` also ships with SSMS / Azure Data Studio / the `sqlpackage` tools. If it genuinely can't connect, the subagent reports the exact error and stops (does not guess).

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

## XPO gotchas (interpret results with these in mind)

- **XPO adds columns on migration but NEVER drops them.** A deleted BO property leaves its column behind; a renamed property leaves the *old* column as an orphan alongside the new one. Finding an old column present is expected, not a bug — dropping it is a separate deliberate `ALTER TABLE ... DROP COLUMN`.
- **A new column existing = the `AssemblyVersion` bump migrated AND the app booted against that DB at least once.** If a new column is missing, the app likely hasn't been run against that DB since the bump.
- **Table name usually equals the BO class name; column name usually equals the property name** (1:1), unless overridden by `[Persistent("…")]`. Non-primitive / editor-backed properties can map to `varbinary`.

## Output

Relay the subagent's concise summary directly. Add interpretation only where it matters (e.g. "old column still present — expected XPO behavior, harmless"). Do not paste raw `sqlcmd` output into the main context.
