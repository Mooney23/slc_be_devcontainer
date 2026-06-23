# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

This is **infrastructure, not an application.** It produces a shared, hardened Python dev-container base Docker image plus the per-service scaffolding that inherits from it. There is no app to run and no test suite here — the "artifacts" are a Docker image and a set of files copied into each service's `.devcontainer/`. Edits here ship to every service via `docker pull` of a rebuilt image (for baked content) or by re-copying templates (for per-service files).

The root `README.md` is the north-star overview. The full infra design rationale (~640 lines — the authoritative reference for the security model and firewall internals) lives in `devcontainer/README.md`, and the broader project direction in `docs/direction.md`. This file captures the structural decisions and gotchas that are easy to break.

## Commands

```bash
# Build the base image (run from devcontainer/base-image/)
cd devcontainer/base-image && docker build -t your-registry/devcontainer-base:latest .
docker build --build-arg CLAUDE_CODE_VERSION=2.1.52 -t ...:latest .   # pin Claude Code
docker build --build-arg PYTHON_VERSION=3.12 -t ...:3.12 .            # different Python

# Lint shell scripts (no CI enforces this; run manually if available)
shellcheck devcontainer/base-image/*.sh devcontainer/scripts/*.sh
```

Host-side helper commands (`dcup`, `dcdanger`, `dcnvim`, `dcshell`, `dcexec`, `dcrefresh`) are defined in `devcontainer/scripts/dev-container-helpers.sh` and run on the **host**, not in this repo's containers. They drive a service's container, injecting short-lived STS creds.

## Architecture: four buckets, four propagation paths

The single most important thing to internalize is **where a file lives determines how a change reaches services**:

- **`devcontainer/base-image/`** — everything baked into the image (`Dockerfile`, `init-firewall.sh`, `refresh-firewall-domains.sh`, `dev-post-start.sh`, `print-setup-hint.sh`). Changes propagate to services via **rebuild + push + `docker pull`**. This is where the real startup logic and firewall live.
- **`devcontainer/scripts/`** — files that live *with each service*. `post-start.sh` is a **thin wrapper** (just `exec bash /usr/local/bin/dev-post-start.sh`) copied into each service once and never touched again. `dev-container-helpers.sh` is sourced on the developer's host.
- **`devcontainer/templates/`** — starting points copied into a new service's `.devcontainer/` (`devcontainer.json`, `Dockerfile.example`, `service-README.md`, `firewall-extras.sh.example`).
- **`plugins/` + `.claude-plugin/marketplace.json`** — this repo doubles as the `slc-plugins` Claude Code plugin marketplace. Skills live here as plugins and propagate **not** through the image but by developers installing/updating the marketplace on their **host** (`~/.claude/plugins/`), which the container inherits through the bind-mounted `~/.claude`. See the Claude skills section below.

### The thin-wrapper post-start pattern

`postStartCommand` → `/workspace/.devcontainer/post-start.sh` (mounted thin wrapper, copy-once) → `/usr/local/bin/dev-post-start.sh` (baked, the real logic). This split exists so startup-logic changes ship via `docker pull` instead of re-copying a script into every service. **Do not put logic back into the per-service `post-start.sh`** — that defeats the whole design. Service-specific startup steps go in an optional `/workspace/.devcontainer/post-start.local.sh`, which `dev-post-start.sh` runs at the end if present.

`dev-post-start.sh` also lets a service override the firewall by dropping its own `init-firewall.sh` (or `refresh-firewall-domains.sh`) in `.devcontainer/` — the baked script copies the local one over the baked one before running.

### Firewall (`init-firewall.sh`)

Default-deny egress via `iptables`/`ipset`, run as root every container start. Phases: lock down IPv6 (via `ip6tables`, because `/proc/sys` is read-only so `sysctl` can't disable the stack) → preserve Docker's `127.0.0.11` DNS NAT rules → resolve `ALLOWED_DOMAINS` to an ipset → add AWS service CIDRs from `ip-ranges.amazonaws.com` (`AWS_REGION`/`AWS_SERVICES` vars; keep `AMAZON` in the list) → set policies to DROP, REJECT everything else → verify (blocks `example.com`, reaches `api.anthropic.com`; non-zero exit fails the container start). A 5-minute cron (installed by `dev-post-start.sh`) re-resolves only each service's `EXTRA_DOMAINS` (from `firewall-extras.sh`) to absorb CDN IP rotation — **add-only**, never removes IPs.

To add a domain for all services: edit `ALLOWED_DOMAINS` in `init-firewall.sh`, rebuild, push. For one service: it adds `EXTRA_DOMAINS` in its own `.devcontainer/firewall-extras.sh` (no rebuild).

### Claude skills

Skills ship as **marketplace plugins**, not baked into the image. This repo *is* the `slc-plugins` marketplace: `.claude-plugin/marketplace.json` + `plugins/<plugin>/skills/<skill>/SKILL.md` (one plugin holds many skills; current plugins: `slc-be-aws-ops`, `slc-be-knowledge`, `slc-be-dev`, `slc-be-bitbucket`, `notes-workflow`). To change a skill, edit it under `plugins/`, push, and developers pick it up via a normal `claude plugin` update — no image rebuild. The container sees plugins because the host's `~/.claude` (including `~/.claude/plugins/`) is bind-mounted in.

A developer's **loose host skills** under `~/.claude/skills/` (not yet packaged) still reach the container at runtime: `dev-post-start.sh` copies them from the read-only `~/.claude/skills-host` staging mount into the tmpfs `~/.claude/skills`. That's the only thing the startup script does with skills now — the old baked `/opt/claude-skills` source and its merge were removed when the marketplace replaced baking.

## Gotchas (these have bitten before — see README for full reasoning)

- **Skills/CLAUDE.md resolve in `devcontainer.json`'s `initializeCommand` use `cp -rL` / `cp -L` (clobber, no `rm`).** `~/.cache/.claude-skills-resolved` is a *single shared* dir every service bind-mounts; `rm -rf` + `mkdir` destroys the inode and empties the skills dir in every *other* running container. The tradeoff: deleted host skills linger (not pruned).
- **`touch` the CLAUDE.md source before mounting it.** A bind mount whose source file is missing makes Docker silently create an empty **directory** there, which breaks `CLAUDE.md`.
- **`DEV_EC2_HOST` is intentionally named differently from the service's own `EC2_HOST`.** Services load `EC2_HOST` from their `.env` via python-dotenv (which won't override an existing env var), so injecting `EC2_HOST` from the host would shadow it. The dev bastion gets its own name.
- **The narrow `init-firewall.sh`-only sudoers entry is NOT the effective policy.** The `common-utils` devcontainer feature grants `dev` broad passwordless sudo (`NOPASSWD:ALL`), which `dev-post-start.sh` relies on. This means the firewall is a guardrail against naive/accidental exfiltration, not a hard boundary against an adversary who specifically targets it (it could `sudo iptables -F`).
- **tmpfs skills dir is mounted root-owned**, so `dev-post-start.sh` `chown`s it to `dev` before the merge or the copies fail with permission denied.
- **The base image disables Claude Code auto-updates** (`{"autoUpdates": false}`) — version control is by rebuilding with a new `CLAUDE_CODE_VERSION`. Note this file can be overwritten by the bind-mounted host `~/.claude.json`.
