#!/bin/bash
echo $EC2_HOST > /tmp/.ec2_host
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
