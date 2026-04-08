#!/bin/bash
echo $EC2_HOST > /tmp/.ec2_host

# Fix ownership of bind-mounted .claude directory.
# On Linux, bind mounts preserve the host's UID/GID. If the host user's
# UID differs from the container's dev user (1000), Claude Code can't
# create session directories and fails with EACCES on .claude/session-env/.
# Errors from the readonly skills submount are expected and harmless.
sudo chown -R "$(whoami):$(whoami)" /home/dev/.claude 2>/dev/null || true

# Use a local firewall script if present, otherwise the base image's copy
if [ -f .devcontainer/init-firewall.sh ]; then
    echo "Using local firewall script (.devcontainer/init-firewall.sh)"
    sudo cp .devcontainer/init-firewall.sh /usr/local/bin/init-firewall.sh
    sudo chmod +x /usr/local/bin/init-firewall.sh
fi

sudo /usr/local/bin/init-firewall.sh
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
