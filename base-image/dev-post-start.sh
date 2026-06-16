#!/bin/bash
# =============================================================================
# Shared dev-container post-start logic (baked into the base image)
#
# This is the canonical startup script for ALL services. It is invoked on every
# container start, via a tiny per-service wrapper at
# /workspace/.devcontainer/post-start.sh that just does:
#
#     exec bash /usr/local/bin/dev-post-start.sh
#
# Keeping the real logic in the image means startup changes propagate to every
# service with a `docker pull` of a new base image — no need to re-copy a
# post-start.sh into each service's .devcontainer/.
#
# Runs INSIDE the container as the `dev` user. /workspace is the bind-mounted
# service repo, so service-provided override/extension files are read from
# /workspace/.devcontainer/.
#
# Service-specific startup steps go in an optional, per-service hook:
#     /workspace/.devcontainer/post-start.local.sh
# which this script runs at the end if present.
# =============================================================================

DEVCONTAINER_DIR="/workspace/.devcontainer"

echo "=== dev-post-start (base image) ==="

# DEV_EC2_HOST is the developer's bastion host (set on the host and injected via
# devcontainer.json). It is written to a file because sudo strips environment
# variables, and init-firewall.sh (run via sudo) needs it to whitelist the
# bastion. Kept separate from the service app's own EC2_HOST (loaded from the
# service .env per environment) so the devcontainer doesn't shadow it.
echo "$DEV_EC2_HOST" > /tmp/.dev_ec2_host

# --- Firewall init ---
# Use a service-local firewall script if present, otherwise the base image's
# baked copy. (Lets a service fully replace the firewall logic if it must.)
if [ -f "$DEVCONTAINER_DIR/init-firewall.sh" ]; then
    echo "Using local firewall script ($DEVCONTAINER_DIR/init-firewall.sh)"
    sudo cp "$DEVCONTAINER_DIR/init-firewall.sh" /usr/local/bin/init-firewall.sh
    sudo chmod +x /usr/local/bin/init-firewall.sh
fi

sudo /usr/local/bin/init-firewall.sh

# --- Periodic DNS refresh for CDN IP rotation ---
# init-firewall.sh resolves EXTRA_DOMAINS to IPs only once, at startup.
# CloudFront-fronted domains rotate IPs, so re-resolve them every 5 minutes
# and add any new IPs to the allowed-domains ipset. See
# /usr/local/bin/refresh-firewall-domains.sh for the rationale.

# Use a service-local refresh script if present, otherwise the baked copy
# (mirrors the init-firewall.sh override above).
if [ -f "$DEVCONTAINER_DIR/refresh-firewall-domains.sh" ]; then
    echo "Using local firewall refresh script ($DEVCONTAINER_DIR/refresh-firewall-domains.sh)"
    sudo cp "$DEVCONTAINER_DIR/refresh-firewall-domains.sh" /usr/local/bin/refresh-firewall-domains.sh
    sudo chmod +x /usr/local/bin/refresh-firewall-domains.sh
fi

# Install the entry in root's crontab so the refresh runs as root (ipset add
# needs it) without sudo. Idempotent: strip any prior entry before re-adding.
REFRESH_CRON='*/5 * * * * /usr/local/bin/refresh-firewall-domains.sh >/dev/null 2>&1'
( sudo crontab -l 2>/dev/null | grep -v 'refresh-firewall-domains.sh'; echo "$REFRESH_CRON" ) \
    | sudo crontab -

# Start the cron daemon (not running by default in this slim image).
if ! pgrep -x cron >/dev/null 2>&1; then
    sudo cron
fi

# --- One-time setup hint ---
bash /usr/local/bin/print-setup-hint.sh

# --- Assemble Claude skills (baked image skills + host user scope) ---
# Both sources are copied into the tmpfs at ~/.claude/skills. Whole-skill-dir
# replacement (rm -rf before cp) avoids merging two same-named skills into a
# broken hybrid. The LAST source in the loop wins on name collisions:
#   "baked host"  -> host wins  (baked skills are overridable defaults)  [current]
#   "host baked"  -> baked wins (baked skills are locked)
# Skills live in a single dir, so Claude Code's cross-scope precedence never
# applies — this copy order is the only thing deciding collisions.
SKILLS_DIR="$HOME/.claude/skills"
mkdir -p "$SKILLS_DIR"
# The skills dir is a tmpfs, which Docker mounts root-owned. The merge below
# runs as the (non-root) dev user, so take ownership first or the cp's fail
# with "Permission denied". Harmless if already owned / not a tmpfs.
sudo chown "$(id -u):$(id -g)" "$SKILLS_DIR" 2>/dev/null || true
for src in /opt/claude-skills "$HOME/.claude/skills-host"; do
    [ -d "$src" ] || continue
    for skill in "$src"/*/; do
        [ -d "$skill" ] || continue
        name=$(basename "$skill")
        rm -rf "$SKILLS_DIR/$name"
        cp -a "$skill" "$SKILLS_DIR/$name"
    done
done

# --- Claude Code plugin path workaround ---
# Workaround for Claude Code plugin path bug in devcontainers
# See: https://github.com/anthropics/claude-code/issues/10379
# See: https://github.com/anthropics/claude-code/issues/19965
if [ -n "$HOST_HOME" ] && [ "$HOST_HOME" != "$HOME" ]; then
  sudo mkdir -p "$HOST_HOME/.claude/plugins/marketplaces"
  sudo ln -sf /home/dev/.claude/plugins/marketplaces/claude-plugins-official \
              "$HOST_HOME/.claude/plugins/marketplaces/claude-plugins-official"

  sudo ln -sf /home/dev/.claude/skills "$HOST_HOME/.claude/skills"
fi

# --- Optional service-specific startup steps ---
# A service that needs custom startup work drops a post-start.local.sh in its
# .devcontainer/. This keeps service-specific logic out of the shared script
# so base updates never conflict with it.
if [ -f "$DEVCONTAINER_DIR/post-start.local.sh" ]; then
    echo "Running service-specific post-start hook (post-start.local.sh)..."
    bash "$DEVCONTAINER_DIR/post-start.local.sh"
fi

echo "=== dev-post-start complete ==="
