#!/usr/bin/env python3
"""Redeploy a Portainer *Repository* (GitOps) stack at a specific image tag.

Portainer pulls the stack definition from git itself; this script only
  1. sets the TAG environment variable on the stack -- plus any given with
     --set NAME=VALUE, such as APP_ENVIRONMENT -- preserving all others,
  2. triggers the git redeploy,
  3. waits for the Swarm rollout to converge, so a crash-looping container
     fails the pipeline instead of leaving it green. Converged means every
     watched service runs the new tag and every task of the new tag is
     running; with a healthcheck Swarm reports a task as running only once it
     is healthy. A rollback or a paused update of a watched service (Swarm
     UpdateStatus rollback_started, rollback_completed, rollback_paused,
     paused) that started with this redeploy fails at once, with the update
     message and the last task errors; an UpdateStatus from an earlier update
     is ignored.

Standard library only (json + urllib).

Environment:
  PORTAINER_URL      e.g. http://localhost:9000  (no trailing slash)
  PORTAINER_API_KEY  Portainer access token, secret pipeline variable
Usage:
  portainer_redeploy.py <stack-name> <endpoint-id> <image-tag> [--set NAME=VALUE ...]
                        [--reference REF] [--timeout 600] [--insecure]
"""
import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


class Portainer:
    def __init__(self, base_url, api_key, insecure=False):
        self.base = base_url.rstrip("/")
        self.key = api_key
        self.ctx = None
        if insecure:
            self.ctx = ssl.create_default_context()
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE

    def call(self, method, path, body=None):
        url = f"{self.base}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("X-API-Key", self.key)
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=60) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:500]
            fail(f"{method} {path} -> HTTP {e.code}: {detail}")
        except urllib.error.URLError as e:
            fail(f"{method} {path} -> cannot reach Portainer at {self.base}: {e.reason}")
        return json.loads(raw) if raw else None

    def docker(self, endpoint_id, resource, filters):
        q = urllib.parse.urlencode({"filters": json.dumps(filters)})
        return self.call("GET", f"/api/endpoints/{endpoint_id}/docker/{resource}?{q}")


def find_stack(api, name, endpoint_id):
    for st in api.call("GET", "/api/stacks") or []:
        eid = st.get("EndpointId", st.get("EndpointID", (st.get("Endpoint") or {}).get("Id")))
        if st.get("Name") == name and eid == endpoint_id:
            return st
    return None


# Only services with this label are watched; if no service carries it, every service is.
TRACK_LABEL = "redeploy.tracked"


def tracked_services(services):
    tracked = [s for s in services if (s["Spec"].get("Labels") or {}).get(TRACK_LABEL) == "true"]
    return tracked if tracked else services


FAILED_UPDATE_STATES = ("rollback_started", "rollback_completed", "rollback_paused", "paused")


def runs_tag(image, tag):
    # Task images carry the resolved digest: registry/repo:tag@sha256:...
    return (image or "").split("@", 1)[0].endswith(f":{tag}")


def parse_docker_time(value):
    # Docker reports nanoseconds (2026-10-14T14:20:01.123456789Z); datetime takes microseconds.
    if not value:
        return None
    match = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d+))?(Z|[+-]\d\d:\d\d)$", value)
    if not match:
        return None
    base, fraction, zone = match.groups()
    zone = "+00:00" if zone == "Z" else zone
    return datetime.fromisoformat(f"{base}.{(fraction or '0')[:6].ljust(6, '0')}{zone}")


def belongs_to_redeploy(status, redeploy_started):
    since = redeploy_started - timedelta(seconds=5)
    started = parse_docker_time(status.get("StartedAt"))
    if started is not None:
        return started >= since
    completed = parse_docker_time(status.get("CompletedAt"))
    return completed is not None and completed >= since


def print_recent_tasks(api, endpoint_id, ns):
    for t in sorted(api.docker(endpoint_id, "tasks", ns) or [],
                    key=lambda x: x.get("CreatedAt", ""), reverse=True)[:6]:
        st = t["Status"]
        print(f"       task {t['ID'][:12]} {st['State']}: "
              f"{st.get('Err') or st.get('Message') or '-'}", file=sys.stderr)


def wait_for_rollout(api, stack_name, endpoint_id, tag, timeout, redeploy_started):
    """The API equivalent of `docker stack deploy --detach=false`."""
    ns = {"label": [f"com.docker.stack.namespace={stack_name}"]}
    deadline = time.monotonic() + timeout
    unsettled = []
    while True:
        watched = tracked_services(api.docker(endpoint_id, "services", ns) or [])
        watched_ids = {s["ID"] for s in watched}

        # Swarm keeps the last UpdateStatus on the service, also from an earlier update.
        for s in watched:
            status = s.get("UpdateStatus") or {}
            if (status.get("State") in FAILED_UPDATE_STATES
                    and belongs_to_redeploy(status, redeploy_started)):
                print(f"       service {s['Spec']['Name']}: update {status['State']}: "
                      f"{status.get('Message') or '-'}", file=sys.stderr)
                print_recent_tasks(api, endpoint_id, ns)
                fail(f"rollout of {s['Spec']['Name']} failed: Swarm reports {status['State']}")

        unsettled = [
            s["Spec"]["Name"]
            for s in watched
            if f":{tag}" not in (s["Spec"]["TaskTemplate"]["ContainerSpec"].get("Image") or "")
            or (s.get("UpdateStatus") or {}).get("State") == "updating"
        ]
        if not unsettled:
            tasks = [t for t in (api.docker(endpoint_id, "tasks",
                                            dict(ns, **{"desired-state": ["running"]})) or [])
                     if t.get("ServiceID") in watched_ids
                     and runs_tag(t["Spec"]["ContainerSpec"].get("Image"), tag)]
            running = [t for t in tasks if t["Status"]["State"] == "running"]
            if running and len(running) == len(tasks):
                print(f"==> Rollout converged: {len(running)} task(s) running at {tag}")
                return

        if time.monotonic() >= deadline:
            if unsettled:
                print(f"       services still updating: {' '.join(unsettled)}", file=sys.stderr)
            print_recent_tasks(api, endpoint_id, ns)
            fail(f"rollout did not converge within {timeout}s")
        time.sleep(5)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("stack_name")
    p.add_argument("endpoint_id", type=int)
    p.add_argument("tag")
    p.add_argument("--reference",
                   help="git reference to deploy, e.g. refs/heads/test-dev-ops. "
                        "Defaults to whatever the stack currently points at.")
    p.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                   help="further stack variable driven by the pipeline, e.g. "
                        "APP_ENVIRONMENT=Prod. Repeatable.")
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--insecure", action="store_true",
                   help="skip TLS verification (self-signed Portainer certificate)")
    args = p.parse_args()

    driven = {"TAG": args.tag}
    for item in args.set:
        name, sep, value = item.partition("=")
        if not sep or not name:
            fail(f"--set expects NAME=VALUE, got '{item}'")
        if name == "TAG":
            fail("TAG is the positional image-tag argument, not a --set")
        if not value:
            fail(f"--set {name} has an empty value")
        driven[name] = value

    url = os.getenv("PORTAINER_URL") or fail("PORTAINER_URL not set")
    key = os.getenv("PORTAINER_API_KEY") or fail("PORTAINER_API_KEY not set")
    api = Portainer(url, key, args.insecure)

    print(f"==> Looking up stack '{args.stack_name}' on endpoint {args.endpoint_id}")
    stack = find_stack(api, args.stack_name, args.endpoint_id)
    if not stack:
        fail(f"stack '{args.stack_name}' not found on endpoint {args.endpoint_id}. "
             "Create it once in Portainer as a Repository stack.")
    stack_id = stack["Id"]

    detail = api.call("GET", f"/api/stacks/{stack_id}")
    if not (detail.get("GitConfig") or stack.get("GitConfig")):
        fail(f"stack {stack_id} is not a Repository stack - git redeploy does not apply.")

    # A redeploy without env clears every stack variable.
    env = [e for e in (detail.get("Env") or []) if e.get("name") not in driven]
    env.extend({"name": n, "value": v} for n, v in driven.items())

    # Without repositoryAuthentication Portainer drops the stored git credentials and
    # clones anonymously; without a password it reuses the stored one.
    payload = {
        "env": env,
        "prune": False,
        "pullImage": True,
        "repullImageAndRedeploy": True,
        "repositoryAuthentication": True,
    }
    # Without repositoryReferenceName Portainer checks out the default branch and stores it.
    git = detail.get("GitConfig") or {}
    ref = args.reference or git.get("ReferenceName")
    if ref:
        payload["repositoryReferenceName"] = ref
    if git.get("ConfigFilePath"):
        payload["configFilePath"] = git["ConfigFilePath"]

    auth = git.get("Authentication") or {}
    if auth.get("Username"):
        payload["repositoryUsername"] = auth["Username"]
    if auth.get("GitCredentialID"):
        payload["repositoryGitCredentialID"] = auth["GitCredentialID"]

    print(f"==> Redeploying stack {stack_id} at " + " ".join(f"{n}={v}" for n, v in driven.items()))
    redeploy_started = datetime.now(timezone.utc)
    api.call("PUT", f"/api/stacks/{stack_id}/git/redeploy?endpointId={args.endpoint_id}", payload)
    print("    redeploy accepted")

    print(f"==> Waiting up to {args.timeout}s for the rollout to converge")
    wait_for_rollout(api, args.stack_name, args.endpoint_id, args.tag, args.timeout, redeploy_started)


if __name__ == "__main__":
    main()
