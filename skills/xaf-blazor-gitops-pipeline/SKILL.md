---
name: xaf-blazor-gitops-pipeline
description: Set up the Docker image, Azure DevOps pipeline and Portainer/Swarm GitOps deployment for a DevExpress XAF Blazor Server app (XPO), from a proven worked example - Dockerfile with the DevExpress licence as BuildKit secret, Swarm stack with external versioned secrets, Traefik and automatic rollback, a Checks/Image/Deploy pipeline with pinned security scans and SBOM, the Portainer redeploy script with rollout and rollback detection, /run/secrets in the app, and the first-logon schema update XAF needs. Use whenever someone wants to containerize XAF Blazor, deploy XAF Blazor to Portainer or Docker Swarm, build a GitOps or CI/CD pipeline for an XAF app, write a Dockerfile or stack file for a DevExpress Blazor app, or invokes /xaf-blazor-gitops-pipeline - even if they only mention one of these pieces.
---

# XAF Blazor → Azure DevOps → Portainer/Swarm (GitOps)

The XAF Blazor variant of the colleague's skill `azure-devops-portainer-deploy` (the base for plain .NET apps). Same model: git owns the stack file, Portainer owns the per-environment values, the pipeline builds a versioned image and asks Portainer to redeploy the Repository stack at that tag, then waits for Swarm to converge. This skill adds what an XAF Blazor app needs and what the base lacks, proven end to end on one app (`references/worked-example.md`).

```
push {{BRANCH}} ─▶ Checks (unit tests [+ gitleaks, Semgrep, vulnerable packages])     ubuntu-24.04
              └─▶ Image  (buildx + licence secret, DX1000/1002 + history checks
                          [+ Trivy, SBOM]) ─▶ push {{ACR}}/{{IMAGE}}:1.0.n          ubuntu-24.04
              └─▶ Deploy (approval, lock) ─▶ portainer_redeploy.py {{STACK}} 1.0.n  {{AGENT_POOL}} (Swarm manager)
                          └─▶ Portainer pulls the stack file from git, Swarm rolls out,
                              healthcheck, rollback on failure, script fails red on rollback
first logon ─▶ DatabaseVersionMismatch ─▶ e.Updater.Update()  (schema update, not at start)
```

## Before you start

The templates and references here are self-contained: they are the worked example's files with names, hosts and IDs replaced, plus the lessons from its logs. Read the base skill if it is at hand (`SKILL.md`, its `references/` and `templates/`): its non-negotiables all still apply. The WwBscDb product files named in `references/worked-example.md` are an optional worked example that exists only on the author's machine; open them if you have access.

## Inputs (placeholders)

Collect these first; read what you can from the repo and ask the user only for the rest. Never ask for secret values.

| Placeholder | Meaning | Used in | Worked-example shape |
|---|---|---|---|
| `{{APP}}` | lowercase app / stack base name; also the `counter()` prefix and the pipeline folder | templates | `myapp` |
| `{{APP_PROJECT}}` | the Blazor.Server project (and its namespace and DLL name) | templates | `MyApp.Blazor.Server` |
| `{{ADO_ORG}}` / `{{ADO_PROJECT}}` | Azure DevOps organisation / project | setup | – |
| `{{ACR}}` | registry login server | templates, setup | `<registry>.azurecr.io` |
| `{{IMAGE}}` | repository path in the registry | templates, setup | `myapp/myapp-blazor` |
| `{{STACK}}` | Portainer stack name (exact, see pitfalls 7) | templates, setup | `myapp-dev` |
| `{{ENDPOINT_ID}}` | Portainer endpoint id of the Swarm (value of `PortainerEndpointId`) | setup | – |
| `{{DOMAIN}}` | public host name (value of the `DOMAIN` stack variable) | setup | – |
| `{{ROUTER}}` | Traefik router name, unique on the cluster (value of the `ROUTER` stack variable) | setup | `myapp-dev` |
| `{{PORT}}` | container port | templates | `8080` |
| `{{SERVICE}}` | Swarm service name in the stack | templates | `myapp-blazor` |
| `{{AGENT_POOL}}` | self-hosted pool on the Swarm manager (deploy only) | templates, setup | – |
| `{{VARIABLE_GROUP}}` | ADO variable group with `PortainerUrl`, `PortainerEndpointId`, `PortainerApiKey` (secret) | templates, setup | `myapp-portainer` |
| `{{ENVIRONMENT}}` | ADO environment, also `APP_ENVIRONMENT` and the default `ASPNETCORE_ENVIRONMENT` | templates, setup | `Dev` |
| `{{BRANCH}}` | the deploy branch | templates, setup | – |
| `{{SECRET_PREFIX}}` | prefix of the Swarm secret names | setup | `myapp_dev` |
| `{{SIGNOZ_SERVICE}}` | service name the app reports to SigNoz | setup | – |
| `{{MODULE_PROJECT}}` | added: the platform-agnostic XAF module project (`.Blazor` is appended for the Blazor module) | templates | `MyApp.Module` |
| `{{TEST_PROJECT}}` | added: unit test project under `Source/Test/` (and its namespace) | templates | `MyApp.Test` |
| `{{ACR_CONNECTION}}` | added: ADO Docker Registry service connection | templates, setup | `myapp-acr` |
| `{{APPLICATION_CLASS}}` / `{{APPLICATION_NAME}}` | added: the `BlazorApplication` subclass / `ApplicationName` | templates | – |
| `{{SDK_VERSION}}` / `{{ASPNET_VERSION}}` | added: pinned image tags | templates | `10.0.402` / `10.0.13-noble` |
| `{{TZ}}` | added: the app's time zone (IANA name) | templates | – |

The pipeline's deployment job id is fixed (`deployment: Deploy`): job ids allow only letters, digits and `_`, so `{{ENVIRONMENT}}` stays free.

The templates assume the worked example's layout: `Source/NuGet.config` (nuget.org only), `Source/Directory.Build.props`, `Source/Prod/Directory.Build.props`, `Source/Prod/<project>/`, `Source/Test/<project>/`, lock files (`packages.lock.json`) per project. Adapt the paths if the repo differs.

## Steps

1. **Read the references and, if available, the base skill and the worked example.** `references/worked-example.md` maps every template to its product file (optional, author's machine only). `references/decisions.md` says why the design is as it is.

2. **Fill the templates** (`templates/`) into the app repo:

   | Template | Goes to |
   |---|---|
   | `Dockerfile.blazor`, `NoLicx.targets` | `.devops/docker/` |
   | `dockerignore.template` | `.dockerignore` (add every project folder the host references, and every non-project folder the build needs) |
   | `gitattributes.template` | `.gitattributes`, then `git ls-files --eol` |
   | `gitleaks.toml` | `.gitleaks.toml`; fill the `<…>` placeholders, one entry per known finding, each with why and what is owed; delete the blocks that do not apply; a legacy tree's entry is deleted together with the tree |
   | `stack.yml` | `.devops/stacks/{{STACK}}.stack.yml`; keep the Traefik labels a list under `deploy.labels` driven by `${ROUTER}`/`${DOMAIN}`; network `traefik_proxy`, entrypoint `websecure` and resolver `le` as the cluster's Traefik names them (`certresolver` only with ACME; setup-checklist C4); replace the SMTP/SigNoz block with the app's own keys |
   | `azure-pipelines.yml` | `.devops/pipelines/{{APP}}/azure-pipelines.yml` |
   | `portainer_redeploy.py` | `.devops/scripts/` **unchanged** |

   One COPY line per project the host references (csproj + lock file) in the Dockerfile's restore layer, in dependency order; keep `App.razor` and `_Imports.razor` there. The healthcheck timings live in the Dockerfile (`15s/5s/60s/3`); the stack's `monitor: 120s` and the script's `--timeout 600` are derived from them (`pitfalls.md` 11). Change one, recheck the chain.

3. **App changes** (product code, on the user's go):
   - **Secrets from files**: `templates/SecretFiles.cs` into `<APP_PROJECT>/Hosting/`, the call from `templates/Program.snippet.cs` as the last configuration call, `templates/SecretFilesTests.cs`. File name = configuration key with `__`; `/run/secrets` overrides appsettings, environment and command line; a missing directory is ignored (local starts).
   - **First-logon update**: `templates/DatabaseVersionMismatch.snippet.cs` (`CheckCompatibilityType.DatabaseSchema`, handler `e.Updater.Update(); e.Handled = true;`, internal for the test), `templates/DatabaseVersionMismatchTests.cs`, `InternalsVisibleTo` for the test project. **No update at container start** (`pitfalls.md` 1). Keep `--updateDatabase` in `Program.Main` for a forced run.
   - **No seed users**: remove the template updater's `User`/`Admin` seed (empty passwords) entirely, with a guard test (`pitfalls.md` 2).
   - **No HSTS / HTTPS redirection**: remove `UseHsts()` and `UseHttpsRedirection()` from `Startup.Configure`; TLS ends at Traefik.
   - Fail fast on missing required configuration at start (the worked example's `StartupChecks`), so an empty stack variable stops the container instead of failing later.

4. **Local proof** (Docker on the developer machine; no remote write):
   - `docker buildx build --load --platform linux/amd64 --provenance=false -f .devops/docker/Dockerfile.blazor --secret id=dxlicense,src=<licence file> -t {{APP}}-blazor:local .` with a non-cached publish (`--no-cache-filter build`): exit 0, `DX100[02]` 0, MSB3245 counted and explained, 0 licence-substring hits in `docker history --no-trunc`, `docker image inspect` and an exported filesystem, no `nuget.config` under `/app`, `id` gives the non-root `app` user.
   - `docker stack config -c <stack file>` with dummy values for every `${VAR}`: exit 0, `app.environment` once, no `Password=`; `python -m py_compile` the script; `yaml.safe_load` the pipeline.
   - The pipeline's exact test command in the SDK image on a clean clone: same result as on Windows (`pitfalls.md` 19).
   - Run the image against a **fresh copy** of the database (restored from a backup, never production; a new copy needs the user's go) with dummy secret files mounted read-only at `/run/secrets` and `ASPNETCORE_ENVIRONMENT` as a real environment variable: healthy, `/LoginPage` 200, 0 secret hits in `docker logs` and `docker inspect`; schema dump before and after start (0 DDL: the start does not touch the database); first logon runs the update and reaches the main page; logon per role; schema dump after; second start (`docker restart`) and a logon: 0 DDL.

5. **Setup with the user**: `references/setup-checklist.md`, step by step. The user creates each item; the agent checks it. Gate every write to ADO, Portainer, the Swarm, the registry or the database on the user's go for that write.

6. **First pipeline run with `deploy=false`** (on the user's go, after registering the pipeline): image in the registry; with `securityScans=true` once, to record the stage and scan durations (worked example: `references/decisions.md`). Its tag becomes the stack's first `TAG`.

7. **First deploy and logon**: a run on `{{BRANCH}}` with the defaults, approved in the environment. Expect `==> Rollout converged: 1 task(s) running at 1.0.n`. Then `https://{{DOMAIN}}/` with a valid certificate, the first logon (schema update), per-role logons, a test mail that reaches only the test recipient.

8. **Monitoring check**: `ls /run/secrets` in the container (names only), SigNoz shows `{{SIGNOZ_SERVICE}}`, a forced error reaches Slack, host memory judged by `system.memory.utilization` state=used (`pitfalls.md` 23). Record what is deferred (`references/deferred.md`) with the user.

## Hard rules

- Never touch production: no production database, server, stack or secret, not even read access for "a quick check". The first database is a copy restored from a backup.
- No write to ADO, Portainer, the Swarm, the registry or any database without the user's go for **that** write. Registering the pipeline, each run, each approval, the branch policy and each secret are separate writes.
- On a shared Swarm never touch other projects' stacks, secrets, networks or Traefik routers. Router names come from `${ROUTER}` and must be unique on the cluster.
- Never print, log, copy or commit a secret: no licence content, API key, PAT, password, connection string or webhook URL in a chat, a log, a file or a stack variable. Secret values only into Swarm secrets (`printf '%s'`), ADO secret variables or the Secure File, by the user. Check with `ls`, never `cat`.
- Scanner images pinned (no `:latest`), no `continueOnError`, `set -euo pipefail` in every bash step, no secret in a pipeline log.
- Version tags only, never `latest`; one image for every environment.

## Deviations from the base skill

| Base skill | Here | Why |
|---|---|---|
| Copy `portainer_redeploy.py` verbatim | Changes: fail fast on `rollback_*`/`paused` of this redeploy, count only tasks of the new tag (digest-aware), ignore an older `UpdateStatus` (stale `paused`/`rollback_*` no longer block; "unsettled" means only a missing tag or `updating`) | The stack has `failure_action: rollback`; the base script would wait out the timeout or count an old-tag task as running. |
| No rollback, no healthcheck | `failure_action: rollback`, `monitor`, `rollback_config`, Dockerfile HEALTHCHECK with bash `/dev/tcp` on `/LoginPage` | Base images have no curl/wget; no health endpoint is added to the app. |
| Licence via `ARG`/`ENV` and a runtime `DevExpress_License` variable | BuildKit secret from a Secure File, length and history checks, `DX1000`/`DX1002` fail the build; no runtime licence | The base route leaves the key in the image metadata and in a Portainer variable. |
| EF Core: migrate at start-up (D90 applied that to XAF); the base's XPO/XAF section already points to `CheckCompatibilityType` and a one-off `--updateDatabase` | First-logon update through `DatabaseVersionMismatch` | The start-up update broke XAF (`pitfalls.md` 1). |
| Tag `$(Build.BuildId)` plus `latest` | `1.0.<counter()>`, variable `imageVersion`, no `latest` | The base's own Azure reference recommends `counter()`; `latest` drifts. |
| `ubuntu-latest`, `Docker@2 buildAndPush` | `ubuntu-24.04`; `buildx --load` → checks → (Trivy, SBOM) → login → push | Pinned agent; nothing is pushed before the checks. |
| No scans | Runtime parameters: gitleaks, Semgrep (report only), vulnerable packages, Trivy, CycloneDX SBOM; default off | Measured cost about 2.5 min per run (D96). |
| No tests in the pipeline | Unit tests in the pinned SDK container, `TestCategory!=Integration`, results published | Nothing installed on the agent. |
| Test and Prod environments | One environment with Exclusive Lock **and** Approval | Worked example's scope (D84, D89). |
| Variable group at pipeline level | Only in the Deploy stage | Narrower. |
| `traefik.docker.network` | `traefik.swarm.network` | The label Traefik's Swarm provider reads. |
| `.dockerignore` excludes one named private config (`Source/NuGet.config`); the root nuget.org-only config goes in | Every `NuGet.config` excluded, only the app's nuget.org-only one re-included; nuget.org-only proven inside the build | NuGet walks up the tree into a subtree's private feed config. |
| `TZ` in the stack | `TZ` in the image | One image, one time zone. |

## References

- `references/setup-checklist.md`: who does what, in order, with a check per step; stack variable names.
- `references/pitfalls.md`: every failure of the worked example (incl. SQL error 18488), symptom → cause → fix.
- `references/decisions.md`: D84–D96 generalized, measured stage and scan durations.
- `references/deferred.md`: rollback drill, Data Protection keys, ARM build agent, test mail and role logons, branch policy.
- `references/worked-example.md`: optional; template → product file and hub logs of the worked example (author's machine only).
