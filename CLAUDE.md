# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

This is **infrastructure, not an application.** It produces a shared, hardened Python dev-container base Docker image plus the per-service scaffolding that inherits from it. There is no app to run and no test suite here — the "artifacts" are a Docker image and a set of files copied into each service's `.devcontainer/`. Edits here ship to every service via `docker pull` of a rebuilt image (for baked content) or by re-copying templates (for per-service files).

The full design rationale lives in `README.md` (~640 lines) — it is the authoritative reference for the security model and firewall internals. This file captures the structural decisions and gotchas that are easy to break.

## Commands

```bash
# Build the base image (run from base-image/)
cd base-image && docker build -t your-registry/devcontainer-base:latest .
docker build --build-arg CLAUDE_CODE_VERSION=2.1.52 -t ...:latest .   # pin Claude Code
docker build --build-arg PYTHON_VERSION=3.12 -t ...:3.12 .            # different Python

# Regenerate the baked-skills index table after adding/removing/renaming a skill
./scripts/gen-skills-index.sh

# Lint shell scripts (no CI enforces this; run manually if available)
shellcheck base-image/*.sh scripts/*.sh
```

Host-side helper commands (`dcup`, `dcdanger`, `dcnvim`, `dcshell`, `dcexec`, `dcrefresh`) are defined in `scripts/dev-container-helpers.sh` and run on the **host**, not in this repo's containers. They drive a service's container, injecting short-lived STS creds.

## Architecture: three buckets, three propagation paths

The single most important thing to internalize is **where a file lives determines how a change reaches services**:

- **`base-image/`** — everything baked into the image (`Dockerfile`, `init-firewall.sh`, `refresh-firewall-domains.sh`, `dev-post-start.sh`, `print-setup-hint.sh`, `skills/`). Changes propagate to services via **rebuild + push + `docker pull`**. This is where the real startup logic and firewall live.
- **`scripts/`** — files that live *with each service*. `post-start.sh` is a **thin wrapper** (just `exec bash /usr/local/bin/dev-post-start.sh`) copied into each service once and never touched again. `dev-container-helpers.sh` is sourced on the developer's host. `gen-skills-index.sh` is a repo maintenance tool.
- **`templates/`** — starting points copied into a new service's `.devcontainer/` (`devcontainer.json`, `Dockerfile.example`, `service-README.md`, `firewall-extras.sh.example`).

### The thin-wrapper post-start pattern

`postStartCommand` → `/workspace/.devcontainer/post-start.sh` (mounted thin wrapper, copy-once) → `/usr/local/bin/dev-post-start.sh` (baked, the real logic). This split exists so startup-logic changes ship via `docker pull` instead of re-copying a script into every service. **Do not put logic back into the per-service `post-start.sh`** — that defeats the whole design. Service-specific startup steps go in an optional `/workspace/.devcontainer/post-start.local.sh`, which `dev-post-start.sh` runs at the end if present.

`dev-post-start.sh` also lets a service override the firewall by dropping its own `init-firewall.sh` (or `refresh-firewall-domains.sh`) in `.devcontainer/` — the baked script copies the local one over the baked one before running.

### Firewall (`init-firewall.sh`)

Default-deny egress via `iptables`/`ipset`, run as root every container start. Phases: lock down IPv6 (via `ip6tables`, because `/proc/sys` is read-only so `sysctl` can't disable the stack) → preserve Docker's `127.0.0.11` DNS NAT rules → resolve `ALLOWED_DOMAINS` to an ipset → add AWS service CIDRs from `ip-ranges.amazonaws.com` (`AWS_REGION`/`AWS_SERVICES` vars; keep `AMAZON` in the list) → set policies to DROP, REJECT everything else → verify (blocks `example.com`, reaches `api.anthropic.com`; non-zero exit fails the container start). A 5-minute cron (installed by `dev-post-start.sh`) re-resolves only each service's `EXTRA_DOMAINS` (from `firewall-extras.sh`) to absorb CDN IP rotation — **add-only**, never removes IPs.

To add a domain for all services: edit `ALLOWED_DOMAINS` in `init-firewall.sh`, rebuild, push. For one service: it adds `EXTRA_DOMAINS` in its own `.devcontainer/firewall-extras.sh` (no rebuild).

### Baked skills

Author skills at `base-image/skills/<name>/SKILL.md` (frontmatter `name` + `description`, dir name = invocation name). The Dockerfile copies them to `/opt/claude-skills/` — **not** to `~/.claude/skills`, which is a tmpfs mount point at runtime and would shadow the image copy. At startup `dev-post-start.sh` merges baked skills + the host's user-scope skills into the tmpfs `~/.claude/skills` via whole-dir replacement. The **last source in the loop wins on name collisions** — currently `host` (so baked skills are overridable defaults; swap the loop order to lock them). After changing the skill set, run `./scripts/gen-skills-index.sh` to update the table in `base-image/skills/README.md`.

## Gotchas (these have bitten before — see README for full reasoning)

- **Skills/CLAUDE.md resolve in `devcontainer.json`'s `initializeCommand` use `cp -rL` / `cp -L` (clobber, no `rm`).** `~/.cache/.claude-skills-resolved` is a *single shared* dir every service bind-mounts; `rm -rf` + `mkdir` destroys the inode and empties the skills dir in every *other* running container. The tradeoff: deleted host skills linger (not pruned).
- **`touch` the CLAUDE.md source before mounting it.** A bind mount whose source file is missing makes Docker silently create an empty **directory** there, which breaks `CLAUDE.md`.
- **`DEV_EC2_HOST` is intentionally named differently from the service's own `EC2_HOST`.** Services load `EC2_HOST` from their `.env` via python-dotenv (which won't override an existing env var), so injecting `EC2_HOST` from the host would shadow it. The dev bastion gets its own name.
- **The narrow `init-firewall.sh`-only sudoers entry is NOT the effective policy.** The `common-utils` devcontainer feature grants `dev` broad passwordless sudo (`NOPASSWD:ALL`), which `dev-post-start.sh` relies on. This means the firewall is a guardrail against naive/accidental exfiltration, not a hard boundary against an adversary who specifically targets it (it could `sudo iptables -F`).
- **tmpfs skills dir is mounted root-owned**, so `dev-post-start.sh` `chown`s it to `dev` before the merge or the copies fail with permission denied.
- **The base image disables Claude Code auto-updates** (`{"autoUpdates": false}`) — version control is by rebuilding with a new `CLAUDE_CODE_VERSION`. Note this file can be overwritten by the bind-mounted host `~/.claude.json`.
