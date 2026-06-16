#!/usr/bin/env python3
"""
resolve_group.py — turn a lambda name/keyword into the exact CloudWatch log group
name, deterministically, from this repo's serverless config.

A CloudWatch Lambda log group is `/aws/lambda/<function-full-name>`, and under
Serverless Framework the full name is `<service>-<stage>-<functionKey>`:
  - service : `service: ${env:SLS_SERVICE_NAME}`  -> read from .env
  - stage   : `provider.stage`                    -> from serverless.yml (default dev)
  - key     : the keys under `functions:`         -> from serverless.yml
(unless a function sets an explicit `name:` override, which we honor.)

This exists so the skill can show the user the precise group name and get a
confirmation BEFORE searching — guessing the group is the #1 cause of a false
"0 results". For lambdas NOT defined in this repo (a different service, e.g. the
device service), it falls back to discovering matching groups live in CloudWatch.

Read-only. Verification uses describe_log_groups only.

Usage:
  resolve_group.py --lambda process_nb            # fuzzy match this repo's fns
  resolve_group.py --lambda alarm_state_change     # cross-service -> CW discovery
  resolve_group.py --list                          # list all fns in this repo
  resolve_group.py --lambda X --no-verify          # offline (skip CW lookup)
Flags: --repo PATH (default /workspace) --service S --stage S --region R
"""
import argparse, os, re, sys
from pathlib import Path


def find_repo_root(explicit):
    """Locate the service repo root — the directory containing serverless.yml.
    Works on a host or in a devcontainer; no hardcoded path. Order:
      1. --repo, if given.
      2. Walk up from the current directory for serverless.yml (normal case:
         you're working inside the repo, wherever it lives on disk).
      3. Skill-relative fallback: this script sits at
         <repo>/.claude/skills/<skill>/scripts/, so parents[4] is the repo root
         (covers running from outside the repo when the skill is committed to it).
    Returns the path, or None (caller errors and asks for --repo)."""
    if explicit:
        return explicit
    cwd = Path.cwd().resolve()
    for d in [cwd, *cwd.parents]:
        if (d / "serverless.yml").exists():
            return str(d)
    here = Path(__file__).resolve()
    if len(here.parents) > 4 and (here.parents[4] / "serverless.yml").exists():
        return str(here.parents[4])
    return None


def read_env_service(repo):
    """SLS_SERVICE_NAME from <repo>/.env, falling back to the process environment
    (serverless reads ${env:SLS_SERVICE_NAME}, which may be exported rather than
    in .env — e.g. on a host without a copied .env)."""
    path = os.path.join(repo, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8", errors="replace"):
            m = re.match(r"\s*SLS_SERVICE_NAME\s*=\s*(.+?)\s*$", line)
            if m:
                return m.group(1).strip().strip("'\"")
    return os.environ.get("SLS_SERVICE_NAME")


def parse_serverless(repo, service):
    """Return (stage, {functionKey: full_name}) via light line parsing (no yaml dep)."""
    path = os.path.join(repo, "serverless.yml")
    if not os.path.exists(path):
        return "dev", {}
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()

    # stage: first 2-space-indented `stage:` (under provider)
    stage = "dev"
    for ln in lines:
        m = re.match(r"^  stage:\s*(\S+)", ln)
        if m:
            stage = m.group(1).strip().strip("'\"")
            break

    # functions: collect keys (2-space indent) until the next top-level key
    fns, in_fns, cur = {}, False, None
    for ln in lines:
        if re.match(r"^functions:\s*$", ln):
            in_fns = True
            continue
        if in_fns:
            if re.match(r"^\S", ln):  # dedent to a top-level key -> functions block ended
                break
            mk = re.match(r"^  ([A-Za-z0-9_]+):\s*$", ln)
            if mk:
                cur = mk.group(1)
                fns[cur] = None  # default name filled in below
                continue
            mn = re.match(r"^    name:\s*(.+?)\s*$", ln)
            if mn and cur:
                fns[cur] = mn.group(1).strip().strip("'\"")
    # build full names
    out = {}
    for key, override in fns.items():
        if override:
            name = override.replace("${env:SLS_SERVICE_NAME}", service or "${env:SLS_SERVICE_NAME}")
        else:
            name = f"{service}-{stage}-{key}"
        out[key] = name
    return stage, out


def verify(region, group):
    """Return (exists, retentionDays, sizeMB) via describe_log_groups, or (None,..) offline."""
    try:
        import boto3
        c = boto3.client("logs", region_name=region)
        r = c.describe_log_groups(logGroupNamePrefix=group, limit=5)
        for g in r.get("logGroups", []):
            if g["logGroupName"] == group:
                return True, g.get("retentionInDays", "never-expire"), round(g.get("storedBytes", 0) / 1e6, 1)
        return False, None, None
    except Exception as e:
        print(f"   (verify skipped: {type(e).__name__})", file=sys.stderr)
        return None, None, None


def discover_live(region, term):
    """Cross-service fallback: find any CloudWatch lambda group whose name contains term."""
    try:
        import boto3
        c = boto3.client("logs", region_name=region)
        hits, tok = [], None
        while True:
            kw = {"logGroupNamePrefix": "/aws/lambda/", "limit": 50}
            if tok:
                kw["nextToken"] = tok
            r = c.describe_log_groups(**kw)
            for g in r.get("logGroups", []):
                if term.lower() in g["logGroupName"].lower():
                    hits.append((g["logGroupName"], g.get("retentionInDays", "never-expire"),
                                 round(g.get("storedBytes", 0) / 1e6, 1)))
            tok = r.get("nextToken")
            if not tok:
                break
        return hits
    except Exception as e:
        print(f"   (live discovery failed: {type(e).__name__})", file=sys.stderr)
        return []


def main():
    p = argparse.ArgumentParser(description="Resolve a lambda name to its CloudWatch log group")
    p.add_argument("--lambda", dest="lam", help="lambda name or keyword to resolve")
    p.add_argument("--list", action="store_true", help="list all functions in this repo")
    p.add_argument("--repo", default=None, help="repo root (default: auto-detect by finding serverless.yml)")
    p.add_argument("--service", default=None, help="override service name (else read .env / env)")
    p.add_argument("--stage", default=None, help="override stage (else serverless.yml)")
    p.add_argument("--region", default=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1")
    p.add_argument("--no-verify", action="store_true", help="skip live CloudWatch verification")
    args = p.parse_args()

    repo = find_repo_root(args.repo)
    if not repo:
        sys.exit("Could not locate the repo root: no serverless.yml found in or above the current directory.\n"
                 "Run from inside the service repo, or pass --repo /path/to/<service>.")
    service = args.service or read_env_service(repo)
    stage, fns = parse_serverless(repo, service)
    if args.stage:
        stage = args.stage
        fns = {k: (v if not v or "${" in v else f"{service}-{stage}-{k}") for k, v in fns.items()}
    print(f"repo    = {repo}")
    print(f"service = {service or '(unresolved — set SLS_SERVICE_NAME in .env/env, or pass --service)'}")
    print(f"stage   = {stage}  (serverless.yml provider.stage)")

    if args.list or not args.lam:
        print(f"\n{len(fns)} functions in this repo:")
        for k in sorted(fns):
            print(f"  {k:40} -> /aws/lambda/{fns[k]}")
        if not args.lam:
            return

    term = args.lam
    matches = {k: v for k, v in fns.items() if term.lower() in k.lower() or (v and term.lower() in v.lower())}

    if matches:
        print(f"\n--- {len(matches)} match(es) for {term!r} in this repo's serverless.yml ---")
        for k, name in sorted(matches.items()):
            group = f"/aws/lambda/{name}"
            line = f"RESOLVED: {group}"
            if not args.no_verify:
                exists, ret, mb = verify(args.region, group)
                if exists is True:
                    line += f"   [exists ✓ retention={ret} sizeMB={mb}]"
                elif exists is False:
                    line += "   [⚠ NOT FOUND in CloudWatch — name may differ or not deployed to this stage]"
            print(line)
        print("\n>>> CONFIRM the group name above with the user before searching.")
        return

    # No serverless match -> probably a different service. Discover live.
    print(f"\nNo function in this repo matches {term!r} (likely a different service).")
    if args.no_verify:
        print("Run without --no-verify to discover matching groups live, or pass the full group name.")
        return
    hits = discover_live(args.region, term)
    if hits:
        print(f"--- {len(hits)} CloudWatch group(s) containing {term!r} (cross-service) ---")
        for name, ret, mb in sorted(hits):
            print(f"  {name}   [retention={ret} sizeMB={mb}]")
        print("\n>>> CONFIRM which group with the user before searching.")
    else:
        print("No matching CloudWatch groups found. Check the term, or list this repo's fns with --list.")


if __name__ == "__main__":
    main()
