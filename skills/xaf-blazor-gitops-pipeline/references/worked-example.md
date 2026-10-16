# Worked example: WwBscDb (Blazor host on .NET 10 / DevExpress 26.1, XPO)

Optional. The templates and the other references are self-contained; this page only points to the app they were taken from. The product repo `WwBscDb` (branch `DX26/master`) and the migration hub next to it exist only on the author's machine. If you have access, read the product file before filling a template, and the hub logs for the why. Product paths below are relative to the product repo.

## Template → product file

| Template | Product file | Changed for the template |
|---|---|---|
| `templates/Dockerfile.blazor` | `.devops/docker/Dockerfile.blazor` | Project names, the shared-framework COPY lines (one line per referenced project), SDK/runtime tags and time zone as placeholders. |
| `templates/NoLicx.targets` | `.devops/docker/NoLicx.targets` | none |
| `templates/dockerignore.template` | `.dockerignore` | Project folders as placeholders; the product also re-includes `Source/Prod/Shared/`, `Source/Scripts/` and every referenced framework project folder. |
| `templates/gitattributes.template` | `.gitattributes` | none |
| `templates/gitleaks.toml` | `.gitleaks.toml` | Allowlist structure only; the product's entries name its legacy trees and fixtures. |
| `templates/stack.yml` | `.devops/stacks/wwbscdb-dev.stack.yml` | Service, image path, stack name, default environment, port as placeholders. |
| `templates/azure-pipelines.yml` | `.devops/pipelines/wwbscdb-dx26/azure-pipelines.yml` | Branch, counter prefix, registry, image, service connection, test project, project list, group, pool, environment, stack as placeholders; deployment job id fixed to `Deploy`. |
| `templates/portainer_redeploy.py` | `.devops/scripts/portainer_redeploy.py` | none (byte copy) |
| `templates/SecretFiles.cs` | `Source/Prod/WwBscDb.Blazor.Server/Hosting/SecretFiles.cs` | Namespace. |
| `templates/Program.snippet.cs` | `Source/Prod/WwBscDb.Blazor.Server/Program.cs` (`CreateHostBuilder`) | Reduced to the call site; the product also registers SigNoz and Serilog there, and its fatal-start logger (`Logging/SerilogHostLogging.cs`) adds the secret files as its last source too. |
| `templates/SecretFilesTests.cs` | `Source/Test/WwBscDb.Test/SecretFilesTests.cs` | The two fatal-start-logger tests left out (app-specific logger); an app-specific static reset removed. |
| `templates/DatabaseVersionMismatch.snippet.cs` | `Source/Prod/WwBscDb.Blazor.Server/BlazorApplication.cs` | Class and application name; the product's `LinkNewObjectToParentImmediately = false` and unused usings left out. |
| `templates/DatabaseVersionMismatchTests.cs` | `Source/Test/WwBscDb.Test/DatabaseVersionMismatchTests.cs` | Class names. Needs `<InternalsVisibleTo Include="<test project>" />` in the Blazor.Server csproj (the handler is `internal`). |

Not templated, read in the product:

| What | Product file |
|---|---|
| No seed users, guard test | `Source/Test/WwBscDb.Test/NoDefaultUserSeedTests.cs` (runs `UpdateDatabaseAfterUpdateSchema` on an in-memory XPO object space with no users; asserts 0 users, 0 roles; app-specific entity list) |
| No HSTS / HTTPS redirection | `Source/Prod/WwBscDb.Blazor.Server/Startup.cs` (`Configure`: `UseExceptionHandler("/Error")` only, no `UseHsts`/`UseHttpsRedirection`) |
| Fail-fast start checks | `StartupChecks.Validate` called first in `Startup.ConfigureServices` (connection string, `AppUrl`, URL signing key, time zone) |

## Hub logs (author's machine)

| Log | What it holds |
|---|---|
| The pipeline work package | Tasks, acceptance, stops |
| The hub's GitOps blueprint study | Analysis of the GitOps model the design copies, and its weaknesses |
| The hub's pipeline security notes | The five security checks of the earlier blueprint pipelines |
| The base-skill comparison | Base skill vs. this build, row by row (written before D92; its "high" gap on the rollout check is the accepted consequence in `pitfalls.md` 1) |
| The executor reports, rounds 1–6, and their fact-checks | Round 1 Dockerfile, stack, pipeline, redeploy script, secret files, MSB3245 cause, Swarm states on a local swarm; round 2 the start-up update (D90), `.gitattributes`, `${ROUTER}`; the D86 proof (ValueManager, "Cannot reset an unchangeable node"); rounds 3–4 warm-up root cause, seed gate, connection string form; round 5 D92 and the console-leak analysis; round 6 D93 and the first-logon update on a fresh restore |
| The pipeline session logs | Funnel answers, Traefik facts, pipeline runs 1–3 with durations, first deploy, memory, error 18488 |
| The configuration-key list (Swarm secrets section) | Secrets, connection string form, stack variables |
| The Dev setup list | The setup list the owner worked through |
| The hub's state and backlog | Decisions D84–D97, deferred items B5–B8 |

## Base skill

`azure-devops-portainer-deploy` (a colleague's skill, for plain .NET apps). This skill keeps its model and its non-negotiables and deviates where SKILL.md's "Deviations from the base skill" table says.
