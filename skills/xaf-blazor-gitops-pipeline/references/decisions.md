# Decisions behind the design

The worked example's decisions D84 to D94 as they bear on the pipeline, generalized (D-numbers kept so the hub can be traced), plus the scan default (D96). "The owner" is the person who decided. Where the hub records no reason, the "Why" column says so.

| D | Decision | Why |
|---|---|---|
| D84 | One environment (Dev), deployed from the migration branch; the owner sets up its database and domain. Swarm `restart_policy` `on-failure` capped at `max_attempts: 3` (replacing "no attempt cap"). | Not recorded beyond the decision. Effect, as the deferred rollback drill describes it: a release that cannot start is restarted 3 times and then rolled back by `failure_action: rollback`. |
| D85 | GitOps as the base skill: Portainer Repository stack from a stack file in the repo, auto-update off, the pipeline redeploys through the Portainer API (`portainer_redeploy.py`) and waits for convergence. Secrets as external Swarm secrets read from `/run/secrets`; plain settings as Portainer stack variables; the DevExpress licence only at build time (Secure File, BuildKit secret, history check); version tags only, no `latest`; a container healthcheck on an existing page (no health endpoint) with `failure_action: rollback`. Scans, tests and deploy are runtime parameters. Everything builds inside Docker, so the agent needs no SDK pin. | Keeps the stack manageable in Portainer; keeps secrets out of Portainer variables and out of the image; adds what the base lacks (rollback, healthcheck, scans). |
| D86 | Schema update driven by XAF's own check: on a version mismatch the app runs the updater (`e.Updater.Update()`), no switch. (A go-live with `--updateDatabase` first was planned; later changed by D97: no separate update step, the first admin logon on the restored backup runs the update.) | As an existing XAF Blazor app of the same team does it (`BlazorApplication` handler); replaces a separate update step for normal operation. |
| D87 | Build on Microsoft-hosted `ubuntu-24.04` only. A selectable build agent (an ARM Mac mini with Docker via Colima) is a follow-up: the .NET SDK segfaults under amd64 emulation, so its build stage would have to run on `$BUILDPLATFORM` and the image be built with `--platform linux/amd64`. | Keep the first version on one known agent. |
| D88 | The Dev database lives on the new database server for migrated services, named for its later production role, so nothing is renamed at go-live. The old production server is never touched; the Dev connection secret must name the new server. | Avoid a rename at go-live; hard separation from production. |
| D89 | The ADO environment is `Dev` with Exclusive Lock **and** an Approval check, so every deploy waits for the owner's approval (changes D84's "automatically"). The Portainer endpoint id is the one other stacks on that Swarm use. | Not recorded beyond the decision. The Approval is what lets the owner reject a deploy while the shared host is short on memory. |
| D90 | (Superseded by D92.) Schema update at container start as the base skill's EF Core pattern: `Program.Main` runs `IDBUpdater.Update` before the web host; failure exits 1, Swarm restarts and rolls back, the pipeline turns red. | Would have let the rollout check catch a failed update; broke XAF (see `pitfalls.md` 1). |
| D91 | (Superseded by D93.) Seed `User`/`Admin` with empty passwords only in `Development`. | Intermediate step. |
| D92 | No schema update at container start. The update runs through the `DatabaseVersionMismatch` handler at the first logon; `--updateDatabase` stays for a forced run. | D90's start-up update applied the EF Core pattern to XAF and needed an undocumented DevExpress API (`IApplicationWarmUpService`). |
| D93 | The seed step that creates `User` and `Admin` with empty passwords (and with it the `Default` role creation and the `Administrators` link on an existing `Admin`) is removed from the updater entirely, in every environment. Re-added only if needed. | No empty-password login on any deployed stack. |
| D94 | The remaining XAF0035 warnings ("Avoid using SecuritySystem static members") go to 0 in a separate ticket after the pipeline, then become a build error. | Not a deployment blocker; kept out of the pipeline work. |
| D96 | Security scans off by default (`securityScans` default false, also for pushes to the deploy branch); a run with scans is started by hand. | Measured cost about 2.5 minutes per run (below). |

## Measured durations

Run 1 (feature branch, `securityScans=true tests=true deploy=false`), first-run resource authorisations not counted:

| Stage / step | Duration |
|---|---|
| Checks (stage) | 293 s |
| Unit tests (job) | 142 s (`dotnet test` 130 s) |
| Security scans (job) | 124 s |
| gitleaks | 11 s |
| Semgrep (report only) | 40 s |
| Vulnerable packages | 63 s |
| Image (stage) | 288 s |
| `docker buildx build` | 199 s |
| Trivy | 23 s |
| SBOM | 11 s |
| `docker push` | 29 s |

Run 3 (deploy branch, CI trigger, defaults: scans off, tests, deploy):

| Stage / step | Duration |
|---|---|
| Checks (unit tests only) | 2:25 |
| Image | 4:04 |
| Deploy (retry, after approval) | 2:39 |
| Redeploy script (Portainer redeploy + rollout wait) | 2:32 |

Local reference (developer machine, worked example): image build with a non-cached publish about 95–104 s; container start to healthy about 5–6 s.

## Settled by the design, not by a D-number

- Scanner versions pinned: gitleaks `v8.30.1`, Semgrep `1.178.0`, Trivy `0.74.0`; SDK `10.0.402`, runtime `aspnet:10.0.13-noble` (newest 10.0.x at the time). Newer scanner releases under two weeks old were not taken.
- gitleaks, vulnerable packages (High/Critical) and Trivy (fixable HIGH/CRITICAL) fail the run; Semgrep only reports a count as a warning; the SBOM is a pipeline artifact.
- No ACR build cache: it needs a `docker-container` buildx builder and a registry login before the build, for a build of under two minutes.
- The variable group is declared only in the Deploy stage.
- Router names come from `${ROUTER}` (router names are global to Traefik).
- `traefik.swarm.network` instead of `traefik.docker.network`: the Swarm provider reads that label.
