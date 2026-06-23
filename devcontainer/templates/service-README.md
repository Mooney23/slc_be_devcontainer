# Dev Container

This directory contains the dev container configuration for this service. It inherits from the shared [devcontainer-base](https://bitbucket.org/shorelineiot/claude_utils) image, which provides Python, Neovim, Claude Code, an egress firewall, and common dev tools.

For full documentation on the security model, firewall behavior, and architecture, see the [devcontainer-base README](https://bitbucket.org/shorelineiot/claude_utils/src/main/README.md#markdown-header-security-model).

## Prerequisites

Before your first use, complete the one-time host setup described in the [devcontainer-base setup guide](https://bitbucket.org/shorelineiot/claude_utils/src/main/README.md#markdown-header-2-set-up-the-host-environment-one-time-per-developer). In summary, you need:

- **Docker** (Docker Desktop or Docker Engine)
- **Dev Container CLI**: `npm install -g @devcontainers/cli`
- **AWS CLI**: for generating short-lived STS tokens
- **`dev-container-helpers.sh`** sourced in your shell (see base repo for installation)
- The following environment variables set on your host: `NOTES_PATH`, `EC2_KEY_PATH`, and `DEV_EC2_HOST` (the dev DB-tunnel bastion — distinct from this service's own `EC2_HOST`, which it loads from its `.env` per environment)
- Docker authenticated with the container registry (if the base image is private)
- *(Optional)* `BITBUCKET_EMAIL` + `BITBUCKET_TOKEN` — **not required** to use the devcontainer; only needed for Bitbucket access (mainly the PR-read skill). Leave them unset if you don't use it.

## Files

```
.devcontainer/
├── devcontainer.json      # Container config (mounts, env vars, ports)
├── Dockerfile             # Inherits from base image; add service-specific packages here
├── firewall-extras.sh     # (optional) Service-specific whitelisted domains
├── post-start.local.sh    # (optional) Service-specific startup steps
└── post-start.sh          # Thin wrapper → runs the baked /usr/local/bin/dev-post-start.sh
```

The real startup logic (firewall init, periodic DNS-refresh cron, workarounds) and the firewall scripts (`init-firewall.sh`, `refresh-firewall-domains.sh`) all live **baked into the base image** at `/usr/local/bin/`. `post-start.sh` here is just a one-line wrapper that hands off to the baked `dev-post-start.sh`, so startup-logic changes arrive with a `docker pull` of a new base image — you copy this wrapper in once and never touch it again. See [How post-start works](https://bitbucket.org/shorelineiot/claude_utils/src/main/README.md#markdown-header-how-post-start-works) in the base repo.

To add domains for this service, use `firewall-extras.sh`. For service-specific startup steps, use `post-start.local.sh` (both explained below).

## Quick Start

```bash
cd this-service
dcup          # build and start the container
dcdanger      # launch Claude Code with AWS creds
dcnvim        # open Neovim with AWS creds
dcshell       # get a bash shell with AWS creds
```

On first run, `dcdanger` will prompt you to authenticate Claude Code via a browser URL. The token is persisted in your host's `~/.claude` directory.

The first time you run `dcdanger`, `dcnvim`, or `dcshell` in a terminal session, the helper script will prompt for your MFA code (if configured) and cache an STS token for the session.

## Service-Specific Configuration

This service's `devcontainer.json` defines:

- **`postCreateCommand`**: Installs this service's Python dependencies (runs once on container creation)
- **`forwardPorts`**: Ports exposed from the container to your host
- **`containerEnv`**: Environment variables specific to this service

If this service needs system packages not in the base image, add them to the `Dockerfile`:

```dockerfile
FROM your-registry/devcontainer-base:latest

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
```

If no extra packages are needed, the Dockerfile is just:

```dockerfile
FROM your-registry/devcontainer-base:latest

WORKDIR /workspace
```

### Service-specific startup steps

If this service needs custom work on every container start (beyond the shared firewall/cron setup), add a `post-start.local.sh` to this directory. The baked `dev-post-start.sh` runs it automatically at the end of startup if present:

```bash
# .devcontainer/post-start.local.sh
# e.g. start a local mock dependency this service's tests need
nohup python scripts/dev_mock_sqs.py >/tmp/mocksqs.log 2>&1 &
```

Keep service-specific logic here rather than editing `post-start.sh` — that way base-image startup updates never conflict with it. Most services won't need this file.

## Claude skills & global CLAUDE.md

The Claude Code agent inside this container gets its skills from two sources:

- **Marketplace plugins** — the team's `slc-plugins` plugins you've installed **on your host** (`~/.claude/plugins/`). The container inherits them automatically because your host `~/.claude` is bind-mounted in, so there's nothing service-specific to configure. See the [Claude skills section in the base repo](https://bitbucket.org/shorelineiot/claude_utils/src/main/README.md#markdown-header-claude-skills) for the marketplace and how to install it.
- **Your own loose host skills** — any ad-hoc skills under your `~/.claude/skills/` that aren't packaged as a plugin. These are flattened on the host and mounted read-only, then copied into the directory Claude actually reads (`~/.claude/skills`, a tmpfs) at startup.

Your global `~/.claude/CLAUDE.md` is resolved and mounted the same way as the loose skills, so the agent picks up your user-scope instructions.

The plumbing for the loose skills and `CLAUDE.md` lives in **this service's `devcontainer.json`** (not the base image):

- an `initializeCommand` that flattens your host `~/.claude/skills` and `~/.claude/CLAUDE.md` into `~/.cache/` (the flatten dereferences symlinks — e.g. dotfiles-managed skills — that wouldn't resolve inside the container);
- mounts: `…/.claude/skills-host` (read-only staging), `…/.claude/skills` (a writable tmpfs the startup copy writes into), and a `…/.claude/CLAUDE.md` overlay.

> ⚠ **Keep these mounts in sync with the base repo.** Unlike startup logic (which arrives via `docker pull`), these mounts are part of *this* `devcontainer.json`. If the base repo's skills handling changes, update the mounts here too — e.g. an older single read-only mount directly on `~/.claude/skills` makes the startup copy fail with `Permission denied` and your loose skills won't load. (Marketplace plugins are unaffected — they ride in through the `~/.claude/plugins/` bind mount.) When in doubt, diff your `devcontainer.json` against the base repo's `templates/devcontainer.json`.

## Customizing the Firewall

### Adding domains for this service

If this service needs to reach domains beyond the base whitelist, edit `firewall-extras.sh`:

```bash
# .devcontainer/firewall-extras.sh
EXTRA_DOMAINS=(
    "your-atlassian-instance.atlassian.net"
    "bitbucket.org"
)
```

The base image's firewall script automatically sources this file and appends the domains to its whitelist. Restart the container to pick up changes:

```bash
dcup
```

This file is safe to commit — it only contains domain names, not firewall logic.

### Periodic DNS refresh (CDN-fronted domains)

The firewall resolves each domain to its IPs once, at container start. CDN-fronted domains (e.g. CloudFront-backed `*.shorelineiot.com`) rotate their IPs frequently, which would otherwise break connections mid-session.

To handle this, the baked startup script (`dev-post-start.sh`) installs a cron job that re-resolves your `firewall-extras.sh` domains every 5 minutes and adds any new IPs to the firewall whitelist (add-only). This is automatic — no action needed beyond listing the domain in `firewall-extras.sh`. Domains with stable IPs (e.g. `bitbucket.org`) are simply re-resolved to the same addresses, so there's no harm in listing them. See [Phase 6 in the base repo](https://bitbucket.org/shorelineiot/claude_utils/src/main/README.md#markdown-header-phase-6-periodic-dns-refresh-cdn-ip-rotation) for the rationale.

### Fully replacing the firewall script

If you need to change the firewall logic itself (not just add domains), you can place a full copy of `init-firewall.sh` in this directory. See the [base repo documentation](https://bitbucket.org/shorelineiot/claude_utils/src/main/README.md#markdown-header-fully-replacing-the-firewall-script) for details.

```bash
# Extract the current script from the running container
dcexec cat /usr/local/bin/init-firewall.sh > .devcontainer/init-firewall.sh

# Edit, then restart
vim .devcontainer/init-firewall.sh
dcup
```

Delete the local copy and restart to revert to the base image's version.

## Rebuilding

After changing `Dockerfile` or `devcontainer.json`:

```bash
devcontainer up --workspace-folder . --build-no-cache
```

To delete the existing container and start fresh:

```bash
devcontainer up --workspace-folder . --remove-existing-container --build-no-cache
```

If the base image has been updated and you want to pull the new version:

```bash
docker pull your-registry/devcontainer-base:latest
devcontainer up --workspace-folder . --remove-existing-container --build-no-cache
```

> **Startup logic updates come with the image — no script re-copy needed.** The real post-start logic is baked into the base image (`/usr/local/bin/dev-post-start.sh`); the `post-start.sh` here is just a permanent one-line wrapper. So pulling a new base image is enough to pick up startup-logic changes (firewall, DNS-refresh cron, etc.) — you do **not** need to re-copy any scripts into this directory. The only time you'd touch `post-start.sh` again is the rare case the base repo changes the wrapper itself (it shouldn't).
>
> **One exception — the Claude mounts.** The skills / `CLAUDE.md` mounts live in *this* `devcontainer.json`, not the image, so they do **not** update on `docker pull`. If the base repo's skills handling changes, sync these mounts too (see [Claude skills & global CLAUDE.md](#claude-skills--global-claudemd)).

## Stopping and Restarting

```bash
# Stop (preserves state)
docker stop $(docker ps -q --filter "label=devcontainer.local_folder=$(pwd)")

# Start again (firewall re-initializes automatically)
dcup
```
