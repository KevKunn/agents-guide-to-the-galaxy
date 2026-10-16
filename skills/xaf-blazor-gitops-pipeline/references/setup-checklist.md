# Setup checklist, in order

What only the user (the person who owns Azure DevOps, Portainer, the Swarm, the registry and the SQL server) does. The agent prepares the exact names, the user creates each item, and the agent checks each item the user reports as done (column "Check"). The agent creates none of it without the user's go for that one write.

For the ADO and Portainer steps that are the same for every app (WIF connection, ABAC registry role, git credentials, pool queue), the base skill `azure-devops-portainer-deploy` has the long form: `references/azure-setup.md` and `references/manual-setup.md`. This list follows the order that worked in the worked example and adds what is specific to an XAF Blazor app.

## Fixed names (fill before starting)

| What | Placeholder |
|---|---|
| ADO organisation / project / repo | `{{ADO_ORG}}` / `{{ADO_PROJECT}}` / the app's repo |
| Pipeline file | `.devops/pipelines/{{APP}}/azure-pipelines.yml` on `{{BRANCH}}` |
| Stack file | `.devops/stacks/{{STACK}}.stack.yml` |
| Portainer stack | `{{STACK}}` on endpoint `{{ENDPOINT_ID}}` |
| ADO environment | `{{ENVIRONMENT}}` |
| Variable group | `{{VARIABLE_GROUP}}` |
| Service connection (ACR) | `{{ACR_CONNECTION}}` |
| Secure file | `DevExpress_License.txt` |
| Registry / image | `{{ACR}}` / `{{IMAGE}}:<1.0.n>` |
| Traefik | network, entrypoint and cert resolver as the cluster's Traefik names them (worked example: `traefik_proxy`, `websecure`, `le`), router `{{ROUTER}}` |
| Domain | `{{DOMAIN}}`; `APP_URL=https://{{DOMAIN}}/` |
| Swarm secrets | `{{SECRET_PREFIX}}_<name>_v1` |
| Self-hosted pool (Swarm manager, deploy only) | `{{AGENT_POOL}}` |

## A. Database and DNS

| # | Who | Step | Check |
|---|---|---|---|
| A1 | user | Create the database on the target SQL server. For a migrated app: restore it from a backup in its state **before** the new DevExpress version, so the first logon shows the schema update. Switch off anything that would send mail from restored data (in the worked example: `UPDATE dbo.MailSchedule SET Active = 0`) and empty the passwords of the test role users if logins are needed for the proof. | Read-only query through the app login. |
| A2 | user | A SQL login for the app, `db_owner` on exactly this database (the first-logon update creates schema), no server roles. Create it **without** `MUST_CHANGE` (`CHECK_POLICY` as the server requires), otherwise the first logon fails with error 18488 (`pitfalls.md` 4a). The SQL server must be reachable from the Swarm node. | Login from the Swarm manager with `sqlcmd` (it connects without a password-change prompt). |
| A3 | user | DNS name `{{DOMAIN}}` pointing at the Swarm's Traefik entry. | `nslookup`; after the deploy a certificate from `le`. |

Connection string form: XPO picks its provider from the string itself, and only this form is accepted (see `pitfalls.md`):

```
Data Source=<host>,<port>;Initial Catalog=<database>;User ID=<user>;Password=<password>;TrustServerCertificate=True;Encrypt=True
```

## B. Azure DevOps

| # | Who | Step | Check |
|---|---|---|---|
| B1 | user | Service connection `{{ACR_CONNECTION}}`: Docker Registry → Azure Container Registry → **Workload Identity Federation**. Role of its principal on an ABAC registry: `Container Registry Repository Writer` (`AcrPush` is not enough there), then wait about 5 minutes. | `az acr show --query roleAssignmentMode`; read the role assignment. |
| B2 | user | Agent pool `{{AGENT_POOL}}` (the self-hosted agent on the Swarm manager): available in the project, pipeline permitted. Checks and Image run on Microsoft-hosted `ubuntu-24.04`; this pool only deploys. | Pool visible under Project settings → Agent pools. |
| B3 | user | Environment `{{ENVIRONMENT}}` with the checks **Exclusive Lock** and **Approval**. With the lock, `lockBehavior: runLatest` cancels an older run that still waits at the approval. | Read the environment and its checks. |
| B4 | user | Variable group `{{VARIABLE_GROUP}}`: `PortainerUrl` (from the agent on the manager, over loopback), `PortainerEndpointId` = `{{ENDPOINT_ID}}`, `PortainerApiKey` = access token of a Portainer CI user, **secret**. | Read the group (names, not values). |
| B5 | user | Secure file `DevExpress_License.txt` (Library → Secure files), the key of the DevExpress version in use (about 630 characters). | File present. |
| B6 | user, on go | Register the pipeline: New pipeline → Azure Repos Git → repo → Existing YAML → branch `{{BRANCH}}`, the pipeline file. Only after the push of the pipeline file, so the push itself starts no run. Set the pipeline's **default branch** to `{{BRANCH}}` (the worked example registered it from a feature branch first and changed the default branch at the merge). | Read the definition. |
| B7 | user | Pipeline permissions per resource: environment, variable group, secure file, service connection, pool. Otherwise the first run waits on "needs permission" (in the worked example about 22 minutes until both prompts were granted). | Read the pipeline permissions. |
| B8 | user, optional | Build Validation branch policy on `{{BRANCH}}` running this pipeline (YAML `pr:` has no effect on Azure Repos; the Image and Deploy stages are skipped for PR builds). Deferred in the worked example, see `deferred.md`. | `az repos policy list --branch {{BRANCH}}` |

## C. Portainer and Swarm

| # | Who | Step | Check |
|---|---|---|---|
| C1 | user | Registry: Registries → Custom registry `{{ACR}}` (no `https://`), own pull principal with `Container Registry Repository Reader` (+ `Catalog Lister` for Browse). The stack must use this registry. | Browse lists the repositories. |
| C2 | user | Git credential: My account → Git credentials → Basic, user without `@`, password a PAT with **Code (Read)** on the repo. | `git clone --depth 1 -b {{BRANCH}}` on the manager. |
| C3 | user | Swarm secrets on the manager, one per value, **versioned names**: `read -rs V; printf '%s' "$V" \| docker secret create {{SECRET_PREFIX}}_connection_v1 -` (no trailing newline, nothing in the shell history). Likewise `_urlsigningkey_v1` (`openssl rand -base64 48`), `_slack_webhook_v1`, `_smtp_password_v1`. Secrets are immutable: **rotation = a new secret `_v2`, switch the `SECRET_*` variable to it, redeploy**; never edit in place. Alternatively Portainer → Secrets → Add with Encode on (as the worked example did). The worked example went to `_v3` for the connection string (one wrong form, one missing `;`, see `pitfalls.md`). | `docker secret ls --filter name={{SECRET_PREFIX}}` (names only). |
| C4 | user | Network `traefik_proxy` exists (overlay, swarm scope) and the target host is a manager. | `docker network ls --filter name=traefik_proxy`, `docker node ls`. |
| C5 | user, after the first image | Repository stack `{{STACK}}`: build method Repository, repo URL without `user@`, authentication with C2, reference `refs/heads/{{BRANCH}}`, compose path `.devops/stacks/{{STACK}}.stack.yml`, **GitOps updates off**. Type the stack name exactly (a typo shows only at the first deploy as "stack not found"). Variables in advanced mode **before** the first deploy, `TAG` = the first pushed image tag (never `latest`). No secret value in a variable. | Read the stack variables: `SECRET_*` hold only names. |
| C6 | user | Slack incoming webhook for the app's log channel; the URL goes only into the secret from C3, never into a chat or a variable. | A forced error shows in the channel. |
| C7 | user | SigNoz: the OTLP endpoint reachable from the Swarm network goes into `SIGNOZ_OTLP_ENDPOINT`; a host-memory alert, if any, on `system.memory.utilization` state=used at a percentage (see `pitfalls.md`). | SigNoz shows the service `{{SIGNOZ_SERVICE}}` after the first start. |

Stack variables of the worked example (names only, as an example; take the final list from your stack file with `grep -o '\${[A-Za-z_]*' <stack file> | sort -u`; ignore `VAR` from the header comment):

```
ACR
TAG
APP_ENVIRONMENT
ASPNETCORE_ENVIRONMENT
ROUTER
DOMAIN
APP_URL
SMTP_HOST
SMTP_PORT
SMTP_FROM
SMTP_USERNAME
SMTP_USE_SSL
SMTP_TEST_MAIL_RECIPIENT
SMTP_SKIP_MAIL_SENDING
SIGNOZ_ENABLED
SIGNOZ_OTLP_ENDPOINT
SIGNOZ_SERVICE_NAME_SUFFIX
SECRET_CONNECTION_STRING
SECRET_URL_SIGNING_KEY
SECRET_SLACK_WEBHOOK
SECRET_SMTP_PASSWORD
```

`TAG` and `APP_ENVIRONMENT` are set again by the pipeline on every redeploy. `SMTP_USE_SSL` may be left out (`${SMTP_USE_SSL:-Auto}` substitutes `Auto` when unset or empty). `SIGNOZ_SERVICE_NAME_SUFFIX` may be empty. An empty `SMTP_PORT`, `SMTP_SKIP_MAIL_SENDING` or `SIGNOZ_ENABLED` stops the app at start.

## D. Runs (each on the user's go)

| # | Step | Expect |
|---|---|---|
| D1 | Push `{{BRANCH}}` with the pipeline, stack and Dockerfile, then B6. | No run starts before B6. |
| D2 | First run with `deploy=false` (optionally `securityScans=true` to measure the scans). | Image `1.0.n` in the registry; Deploy skipped. Use that tag as `TAG` in C5. |
| D3 | Run from `{{BRANCH}}` with defaults; approve the Deploy stage. | Log ends with `==> Rollout converged: 1 task(s) running at 1.0.n`. Check the branch first: the Deploy stage only runs on `refs/heads/{{BRANCH}}`. |
| D4 | First logon on `https://{{DOMAIN}}/`. | Valid certificate; the first logon runs the schema update and reaches the main page; a second start does no DDL. |
| D5 | Monitoring. | `docker exec <container> ls /run/secrets` lists names (never `cat`); SigNoz shows `{{SIGNOZ_SERVICE}}`; a forced error reaches Slack; host memory has headroom. |

Note: each run takes a `counter()` value, also a cancelled one (in the worked example the cancelled run 2 consumed `1.0.2` and the deploy went out as `1.0.3`).
