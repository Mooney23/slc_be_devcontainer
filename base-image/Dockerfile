FROM python:3.13-slim

ARG TZ
ENV TZ="$TZ"

# System dependencies:
#   - Core tools: curl, git (needed by some pip packages), tmux, ripgrep, fd-find, unzip
#   - Firewall: iptables, ipset, iproute2, dnsutils, jq
#   - Note: 'aggregate' is needed if we were aggregating CIDR ranges (GitHub IPs),
#     but since we don't need GitHub access, we skip it
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    tmux \
    ripgrep \
    fd-find \
    unzip \
    ca-certificates \
    sudo \
    iptables \
    ipset \
    iproute2 \
    dnsutils \
    jq \
    gcc \
    make \
    libc6-dev \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Neovim (recent stable release)
ARG NVIM_VERSION=v0.11.6
RUN curl -fsSL "https://github.com/neovim/neovim/releases/download/${NVIM_VERSION}/nvim-linux-x86_64.tar.gz" \
    | tar xz -C /opt \
    && ln -s /opt/nvim-linux-x86_64/bin/nvim /usr/local/bin/nvim

# Install Node.js (required for Claude Code CLI and some Neovim tooling)
ARG NODE_VERSION=22
RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code globally
ARG CLAUDE_CODE_VERSION=latest
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}

# Create non-root user
ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=1000
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m -s /bin/bash $USERNAME \
    && mkdir -p /home/$USERNAME/.config /home/$USERNAME/.local/share /home/$USERNAME/.local/bin /home/$USERNAME/.claude /home/$USERNAME/.cache/nvim \
    && chown -R $USERNAME:$USERNAME /home/$USERNAME

# Install common Python dev tools into the global environment
RUN pip install --no-cache-dir \
    ruff \
    pyright \
    pytest \
    ipython \
    debugpy

# Copy firewall script and grant passwordless sudo for it only
COPY .devcontainer/init-firewall.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/init-firewall.sh \
    && echo "$USERNAME ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh" > /etc/sudoers.d/$USERNAME-firewall \
    && chmod 0440 /etc/sudoers.d/$USERNAME-firewall

# Set DEVCONTAINER env var so tools (like Neovim config) can detect
# they're running inside a container and skip network-dependent operations
ENV DEVCONTAINER=true

WORKDIR /workspace

USER dev
