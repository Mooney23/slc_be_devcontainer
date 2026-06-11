#!/bin/bash
echo $EC2_HOST > /tmp/.ec2_host

# Use a local firewall script if present, otherwise the base image's copy
if [ -f .devcontainer/init-firewall.sh ]; then
    echo "Using local firewall script (.devcontainer/init-firewall.sh)"
    sudo cp .devcontainer/init-firewall.sh /usr/local/bin/init-firewall.sh
    sudo chmod +x /usr/local/bin/init-firewall.sh
fi

sudo /usr/local/bin/init-firewall.sh

# --- Periodic DNS refresh for CDN IP rotation ---
# init-firewall.sh resolves EXTRA_DOMAINS to IPs only once, at startup.
# CloudFront-fronted domains rotate IPs, so re-resolve them every 5 minutes
# and add any new IPs to the allowed-domains ipset. See
# /usr/local/bin/refresh-firewall-domains.sh for the rationale.

# Use a local refresh script if present, otherwise the base image's copy
# (mirrors the init-firewall.sh override above).
if [ -f .devcontainer/refresh-firewall-domains.sh ]; then
    echo "Using local firewall refresh script (.devcontainer/refresh-firewall-domains.sh)"
    sudo cp .devcontainer/refresh-firewall-domains.sh /usr/local/bin/refresh-firewall-domains.sh
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

bash .devcontainer/print-setup-hint.sh

# Workaround for Claude Code plugin path bug in devcontainers
# See: https://github.com/anthropics/claude-code/issues/10379
# See: https://github.com/anthropics/claude-code/issues/19965
if [ -n "$HOST_HOME" ] && [ "$HOST_HOME" != "$HOME" ]; then
  sudo mkdir -p "$HOST_HOME/.claude/plugins/marketplaces"
  sudo ln -sf /home/dev/.claude/plugins/marketplaces/claude-plugins-official \
              "$HOST_HOME/.claude/plugins/marketplaces/claude-plugins-official"

  sudo ln -sf /home/dev/.claude/skills "$HOST_HOME/.claude/skills"
fi
