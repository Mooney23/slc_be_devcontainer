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

# --- Assemble Claude skills (host user scope) ---
# Host user-scope skills are staged read-only at ~/.claude/skills-host (flattened
# on the host by devcontainer.json's initializeCommand) and copied into the tmpfs
# at ~/.claude/skills here. Whole-skill-dir replacement (rm -rf before cp) avoids
# merging two same-named skills into a broken hybrid.
# (Skills are no longer baked into the image — they ship via the plugin
# marketplace now, which the container inherits through the bind-mounted
# host ~/.claude/plugins. This step only stages the host's loose user skills.)
SKILLS_DIR="$HOME/.claude/skills"
SKILLS_SRC="$HOME/.claude/skills-host"
mkdir -p "$SKILLS_DIR"
# The skills dir is a tmpfs, which Docker mounts root-owned. The copy below
# runs as the (non-root) dev user, so take ownership first or the cp's fail
# with "Permission denied". Harmless if already owned / not a tmpfs.
sudo chown "$(id -u):$(id -g)" "$SKILLS_DIR" 2>/dev/null || true
if [ -d "$SKILLS_SRC" ]; then
    for skill in "$SKILLS_SRC"/*/; do
        [ -d "$skill" ] || continue
        name=$(basename "$skill")
        rm -rf "$SKILLS_DIR/$name"
        cp -a "$skill" "$SKILLS_DIR/$name"
    done
fi

# --- Claude Code plugin path workaround ---
# Workaround for Claude Code plugin path bug in devcontainers
# See: https://github.com/anthropics/claude-code/issues/10379
# See: https://github.com/anthropics/claude-code/issues/19965
if [ -n "$HOST_HOME" ] && [ "$HOST_HOME" != "$HOME" ]; then
  sudo mkdir -p "$HOST_HOME/.claude"
  # Symlink the WHOLE plugins dir, not individual marketplaces. installPaths in
  # installed_plugins.json are absolute and recorded with the *host* home
  # (e.g. /home/anant/...), but the container home is $HOME (/home/dev). The
  # container must make the host path resolve to the bind-mounted plugins tree,
  # or any plugin installed on the host fails to load (its skills never
  # enumerate). Linking the whole dir covers cache/ (all plugins) and
  # marketplaces/ (all marketplaces) with no per-plugin upkeep.
  # rm -rf clears any root-owned stub dir from an earlier run; it only ever
  # removes a container-local path (or the prior symlink), never the mount, so
  # host data is untouched. -n stops ln from nesting inside an existing link.
  sudo rm -rf "$HOST_HOME/.claude/plugins"
  sudo ln -sfn "$HOME/.claude/plugins" "$HOST_HOME/.claude/plugins"

  sudo ln -sfn "$HOME/.claude/skills" "$HOST_HOME/.claude/skills"
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
