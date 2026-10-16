# Pitfalls: symptom, cause, fix

Every lesson from the worked example (an XAF Blazor Server app on .NET 10 / DevExpress 26.1 / XPO, see `worked-example.md`). The base skill's `references/troubleshooting.md` covers the generic Portainer/Swarm/ADO failures; this list adds what an XAF Blazor app hits.

## Schema update and start-up

### 1. Schema update at container start breaks XAF (start-up update, then reverted)

| | |
|---|---|
| Symptom, step 1 | The update at start returns `UpdateCompleted`, then the host dies: `Cannot change the ValueManager.ValueManagerType property after it's initialized. Current type: SimpleValueManager`1, New type: AsyncValueManager`1`, exit 1, never healthy. |
| Symptom, step 2 | After forcing the ValueManager type in `Main`, the host starts healthy, but every logon fails with "Cannot reset an unchangeable node" in `XafApplication.LoadUserDifferences` → `AspNetCoreApplication.CollapseModel`, followed by `ArgumentOutOfRangeException` in `ModelNode.GetNode`; the login page is then broken for every visitor until the process restarts. |
| Cause | The EF Core pattern ("migrate before `host.Run()`") was applied to XAF: resolving `IDBUpdater` before `host.Run()` builds a `BlazorApplication` outside XAF's warm-up. That initialises `ValueManager` before the warm-up can set `AsyncValueManager<>`, and it creates the process-wide shared Application Model outside the warm-up protocol, so the first logon's model collapse hits an unchangeable root. DevExpress documents that at host start-up XAF creates no application instance, does not touch the database and does not initialise the model. |
| What worked, but was dropped | Calling `IApplicationWarmUpService.EnsureWarmUp()` before the updater fixed both errors (all role logons worked), but it relies on a service marked `[EditorBrowsable(Never)]`. |
| Fix | No update at start. The update runs in the `DatabaseVersionMismatch` handler at the first logon (`e.Updater.Update(); e.Handled = true;` with `CheckCompatibilityType.DatabaseSchema`), as existing XAF Blazor apps do; `--updateDatabase` stays for a forced run. Template `DatabaseVersionMismatch.snippet.cs`. |
| Consequence to accept | The healthcheck and the Swarm rollback do not see a failed schema update: the container is healthy before anyone logs on. A failing update shows as an error in the first user's session (and in Slack/SigNoz), not as a red pipeline. |

### 2. Seed users with empty passwords

| | |
|---|---|
| Symptom | After the first update the database holds a new user `User` (empty password, role `Default`); an existing `Admin` gets the `Administrators` role re-attached. On a public URL that is an open login. |
| Cause | The XAF template updater seeds `User` and `Admin` with empty passwords, ungated, on every update. `FindObject` skips soft-deleted rows, so a soft-deleted `User` in a restored database does not stop a new one. Under `DatabaseSchema` every module updater sees `CurrentDBVersion` 0.0.0.0, so version gates do not help. |
| Tried | A "no users yet" gate, then a "seed only in `Development`" gate (environment read from `IConfiguration["environment"]`); both were replaced. |
| Fix | Remove the seed step (`CreateDefaultRole`, `SeedDefaultUsers`, `SeedAdminUser`, `SeedDefaultUser`) from the updater in every environment, with a guard test that runs `UpdateDatabaseAfterUpdateSchema` on an in-memory object space without users and asserts 0 users and 0 roles (worked example: `NoDefaultUserSeedTests.cs`). Consequence: a new empty database gets no login user; create the first one some other way. |

### 3. XPO connection string form

| | |
|---|---|
| Symptom | `CannotFindAppropriateConnectionProviderException`. `--updateDatabase` exits 1; a web start stays healthy (the start does not open the database). |
| Cause | XPO picks the provider from the connection string itself; the keyword form `Server=…;Database=…;User Id=…` is not recognised. |
| Fix | `Data Source=<host>,<port>;Initial Catalog=<database>;User ID=<user>;Password=<password>;TrustServerCertificate=True;Encrypt=True`. |

### 4. Missing `;` after the port in the connection secret

| | |
|---|---|
| Symptom | First logons on the deployed stack fail with `CannotFindAppropriateConnectionProviderException` (password masked); both errors reach Slack. No database write. |
| Cause | The secret's connection string lacked the `;` after `<host>,<port>`. |
| Fix | A new secret version with the corrected string, switch `SECRET_CONNECTION_STRING`, redeploy. Never edit a Swarm secret in place (it cannot be). |

### 4a. SQL error 18488 at the first logon

| | |
|---|---|
| Symptom | A logon on the deployed stack fails with SQL Server error 18488 (the login must change its password). |
| Cause | The app's SQL login was created with `CHECK_POLICY`/`MUST_CHANGE`, so it cannot connect until its password is changed. |
| Fix | Create the login without `MUST_CHANGE` (`CHECK_POLICY` as the server requires), `db_owner` on the database. The worked example dropped the database and the login, restored a fresh database and recreated the login without the must-change flag; then the first logon worked. |

### 5. Empty stack variables stop the app

| | |
|---|---|
| Symptom | Exit 1 at start: "Failed to convert configuration value '' at 'SigNoz:Enabled' to type 'System.Boolean'". |
| Cause | An unset Portainer stack variable becomes an empty string, and `""` does not bind to `int`, `bool` or an enum. An empty `SmtpSettings:Username` is not null, so MailKit authenticates with an empty user. |
| Fix | Set every typed variable (`SMTP_PORT`, `SMTP_SKIP_MAIL_SENDING`, `SIGNOZ_ENABLED`); give a `:-default` only where the value is the same everywhere (`${SMTP_USE_SSL:-Auto}`). |

### 6. Secret file with a trailing newline

| | |
|---|---|
| Symptom | A value read from `/run/secrets` keeps a `\r`, or (on Windows) a `\n`. |
| Cause | `KeyPerFileConfigurationProvider` removes exactly one trailing `Environment.NewLine`: on Linux `\n`, so a CRLF file keeps `\r`. |
| Fix | Create secrets with `printf '%s'`. The tests `TrailingPlatformNewLine_IsRemoved` and `TrailingLineFeed_IsRemovedOnlyWhereItIsThePlatformNewLine` pin the behaviour. |

## Deploy

### 7. "stack not found"

| | |
|---|---|
| Symptom | Deploy stage fails: `stack '<name>' not found on endpoint <id>`. |
| Cause | The Portainer stack was created with a mistyped name (an extra letter). The script finds the stack by exact name and endpoint id. |
| Fix | Recreate the stack with the exact name (reference and `TAG` as before), then retry the Deploy stage. |

### 8. Deploy skipped on a feature branch

| | |
|---|---|
| Symptom | A run on a feature branch shows Deploy as skipped; a run meant to deploy does nothing. |
| Cause | The Deploy condition requires `Build.SourceBranch == refs/heads/{{BRANCH}}` and not a PR. |
| Fix | Check the branch condition before starting a run that should deploy; feature-branch runs are for `deploy=false` image builds. The worked example cancelled such a run (its counter value was consumed). |

### 9. The redeploy payload wipes stack settings

| | |
|---|---|
| Symptom | After a redeploy the stack has lost its variables, its git credentials, or switched to the default branch. |
| Cause | `PUT /api/stacks/{id}/git/redeploy` overwrites whatever the payload omits: no `env` clears every variable, no `repositoryAuthentication` clones anonymously, no `repositoryReferenceName` checks out and stores the default branch. |
| Fix | Use `portainer_redeploy.py` unchanged: it reads the stack, keeps every variable not driven by the pipeline, sends `repositoryAuthentication`, the reference, the compose path, user name and git credential id. |

### 10. Green pipeline, crash-looping or rolled-back service

| | |
|---|---|
| Symptom | Portainer answers 2xx while the service never runs the new tag, or Swarm has rolled back. |
| Cause | 2xx means "accepted". With `failure_action: rollback`, Swarm can roll back to the old tag; an old-tag task can also look "running". Swarm keeps the last `UpdateStatus` from an earlier update. |
| Fix | The script polls until every watched service runs the new tag and every task of that tag is running (with a healthcheck Swarm reports `running` only once healthy). It fails at once on `rollback_started`, `rollback_completed`, `rollback_paused` or `paused` whose `StartedAt` (or `CompletedAt`) is no earlier than 5 s before the redeploy call, printing the update message and the last task errors; an older status is ignored. If the agent clock runs more than 5 s ahead of the manager, a rollback is caught only at the timeout (still red). |

### 11. Timing chain: healthcheck, monitor, timeout

| | |
|---|---|
| Rule | `monitor` > `start_period + retries × interval` (60 + 3 × 15 = 105 s, +5 s probe timeout); the script's `--timeout` > image pull + 105 s + `monitor`. |
| Worked example | `start_period` 60 s (measured start to healthy about 5–6 s), `monitor: 120s`, `--timeout 600`. A start-up update had pushed these to 300 s / 360 s / 900 s; they went back when the update moved to the first logon. |

### 12. Data Protection keys are ephemeral

| | |
|---|---|
| Symptom | After every redeploy or restart, users are logged out, and the first request with an old cookie logs `AntiforgeryValidationException` ("key … was not found in the key ring") at Error level, which reaches Slack. SigNoz warnings `UsingEphemeralFileSystemLocationInContainer`, `NoXMLEncryptorConfiguredKeyMayBePersistedToStorageInUnencrypted`. |
| Cause | The keys live in `/home/app/.aspnet/DataProtection-Keys` inside the container. |
| Fix | Deferred in the worked example (see `deferred.md`): persist the keys (Swarm volume at the key directory, or a database-backed key store), optionally protect them with a certificate. |

### 13. HSTS and HTTPS redirection behind Traefik

| | |
|---|---|
| Symptom | "Failed to determine the https port" in the log; a redirect loop if anyone sets `ASPNETCORE_HTTPS_PORTS`. |
| Cause | TLS ends at Traefik; the container serves plain HTTP on `{{PORT}}`. The XAF template's `UseHsts()` / `UseHttpsRedirection()` do not belong there. |
| Fix | Remove both from `Startup.Configure` (the `else` keeps `UseExceptionHandler("/Error")`). An agent's permission classifier may refuse this edit as a TLS weakening; then the user makes it or allows it. |

## Image and build

### 14. DevExpress licence in the image

| | |
|---|---|
| Risk | `ARG`/`ENV` for the licence (the base skill's `dotnet-devexpress.md` route) puts the key into the build-stage metadata and cache. |
| Fix | BuildKit secret `dxlicense` from an ADO Secure File, mounted at `/root/.config/DevExpress/DevExpress_License.txt` for the publish only; pipeline length check (≥ 100 characters), `docker history --no-trunc` check with a 24-character substring that is never printed; `DX1000`/`DX1002` in the publish log fail the build. |

### 15. MSB3245 warnings in the publish

| | |
|---|---|
| Symptom | `warning MSB3245` lines in the publish log (5 in the worked example). |
| Cause | Legacy `<Reference Include="System.*"/>` .NET Framework assembly references in a shared framework project, which do not resolve on net8.0/net10.0. |
| Fix | Find the project and reference names (count distinct project+reference pairs); fix them if the project is the app's own, otherwise record them. The Dockerfile prints the count. |

### 16. `LC` task on .NET MSBuild (MSB4803)

| | |
|---|---|
| Symptom | `MSB4803`: the task `LC` is not supported on the .NET Core version of MSBuild. |
| Cause | `.licx` compilation in an XAF module. |
| Fix | `NoLicx.targets` (empty `CompileLicxFiles` target) via `-p:CustomAfterMicrosoftCommonTargets=…` in both the Dockerfile publish and the pipeline test step. |

### 17. NuGet walk-up and the private feed

| | |
|---|---|
| Risk | NuGet walks up the tree; a `NuGet.config` in a subfolder (in the worked example a shared framework subtree) lists the DevExpress feed with its key in the URL. `dotnet list package` without `--no-restore` restores again, without `--configfile` and not locked, through the walk-up config. |
| Fix | `.dockerignore` excludes every `NuGet.config` in any case and re-includes only the app's own nuget.org-only file; the Dockerfile proves per project that the only source is nuget.org and that the restore log contacted no other host; the vulnerable-packages step uses `--no-restore --configfile`; no `nuget.config` in the publish output. |

### 18. `blazor.server.js` missing

| | |
|---|---|
| Symptom | The published app lacks `blazor.server.js`. |
| Cause | No `.razor` item in the restore layer. |
| Fix | Copy `App.razor` and `_Imports.razor` into the restore layer; the Dockerfile fails if `blazor.server*.js` is missing from the publish. |

### 19. Windows-only unit tests fail on the Linux agent

| | |
|---|---|
| Symptom | Tests green on Windows, red in the pipeline's SDK container. |
| Cause | In the worked example: solution paths with `\` passed to `Path.Combine`, and an expected `\r\n` where the code writes the platform newline. |
| Fix | Make them platform-neutral, and run the pipeline's exact test command in the SDK image on a clean clone before the first run. |

### 20. CRLF on files the container or agent executes

| | |
|---|---|
| Risk | With `core.autocrlf=true`, the Dockerfile (its `COPY <<EOF` heredoc and the HEALTHCHECK line), `.dockerignore` and scripts become CRLF in a Windows working tree. |
| Fix | Root `.gitattributes` (template `gitattributes.template`); keep `*.cmd` as CRLF; `git ls-files --eol` to check. |

### 21. Local proof: container cannot resolve the SQL container

| | |
|---|---|
| Symptom | `SqlException` "Name or service not known" for the SQL container on a user-defined Docker network. |
| Cause | Docker's embedded DNS resolved nothing on that network in the worked example (cause not determined). |
| Fix | `--add-host <sql-container>:<its IP>` for the local proof. |

### 22. Healthcheck proves less than it seems

| | |
|---|---|
| Fact | `/LoginPage` answers 200 without a database, and so do `/` and unknown paths (Blazor fallback page). The healthcheck is a liveness check: it catches start crashes, not a broken database or a failed first-logon update. No curl/wget in the .NET images, so it uses bash `/dev/tcp`. |

## Host and monitoring

### 23. Build agent "Free memory is lower than 5%"

| | |
|---|---|
| Symptom | The self-hosted deploy agent warns about free memory. |
| Cause | The warning counts page cache as used; SigNoz showed several GB available after the deploy, and the app used about 0.5 GB. |
| Fix | Judge host memory by real used memory: `system.memory.utilization` with state=used. Do not sum the `system.memory.usage` states (they overlap; the worked example's first estimate was wrong that way). Alert at a percentage (worked example: > 85 %, recovery 80 %, 5 min window), not at fixed GB. A host above the limit is a reason to stop the stack (not delete it) and defer the remaining checks. |

### 24. Pipeline steps that leak or swallow

| | |
|---|---|
| Rules | Pin every scanner image (no `:latest`; the blueprint pipelines ran their scanners on `:latest`); no `continueOnError`; `set -euo pipefail` in every bash step; `docker history` into a variable first so its failure fails the step; `|| true` only on `grep -c`; never print the licence, the API key or a connection string; the variable group only in the Deploy stage; `PORTAINER_API_KEY` only through `env:`. |
