# Published as: your-registry/devcontainer-python:3.13
# (or whatever naming convention your team uses)

ARG PYTHON_VERSION=3.13
FROM python:${PYTHON_VERSION}-slim

ARG TZ
ENV TZ="$TZ"

# ── System dependencies ──────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    tmux \
    ripgrep \
    fd-find \
    unzip \
    ca-certificates \
    sudo \
    cron \
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

# ── Neovim ───────────────────────────────────────────────────────
ARG NVIM_VERSION=v0.11.6
RUN curl -fsSL "https://github.com/neovim/neovim/releases/download/${NVIM_VERSION}/nvim-linux-x86_64.tar.gz" \
    | tar xz -C /opt \
    && ln -s /opt/nvim-linux-x86_64/bin/nvim /usr/local/bin/nvim

# ── Node.js (for some Neovim tooling) ───────────────────────────
ARG NODE_VERSION=22
RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# ── Non-root user ────────────────────────────────────────────────
ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=1000
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m -s /bin/bash $USERNAME \
    && mkdir -p /home/$USERNAME/.config \
               /home/$USERNAME/.local/share \
               /home/$USERNAME/.local/bin \
               /home/$USERNAME/.claude \
               /home/$USERNAME/.cache/nvim \
    && chown -R $USERNAME:$USERNAME /home/$USERNAME

# ── Claude Code (native binary) ──────────────────────────────────
# The official install.sh runs `claude install` interactively, which
# hangs in Docker. Instead, we download the binary directly.
ARG CLAUDE_CODE_VERSION=latest
RUN DOWNLOAD_DIR=$(mktemp -d) \
    && VERSION=$(curl -fsSL https://storage.googleapis.com/claude-code-dist-86c565f3-f756-42ad-8dfa-d59b1c096819/claude-code-releases/${CLAUDE_CODE_VERSION}) \
    && ARCH=$(uname -m | sed 's/x86_64/x64/' | sed 's/aarch64/arm64/') \
    && PLATFORM="linux-${ARCH}" \
    && curl -fsSL -o "${DOWNLOAD_DIR}/claude" \
       "https://storage.googleapis.com/claude-code-dist-86c565f3-f756-42ad-8dfa-d59b1c096819/claude-code-releases/${VERSION}/${PLATFORM}/claude" \
    && chmod +x "${DOWNLOAD_DIR}/claude" \
    && mv "${DOWNLOAD_DIR}/claude" /home/$USERNAME/.local/bin/claude \
    && chown $USERNAME:$USERNAME /home/$USERNAME/.local/bin/claude \
    && rm -rf "${DOWNLOAD_DIR}" \
    && echo 'export PATH="$HOME/.local/bin:$PATH"' >> /home/$USERNAME/.bashrc

# Disable auto-updates inside the container — version control
# happens by rebuilding the image with a new CLAUDE_CODE_VERSION.
# NOTE: this file gets overwritten if the host's ~/.claude.json
# is bind-mounted in, so also handle in post-start.sh if needed.
RUN echo '{"autoUpdates": false}' > /home/$USERNAME/.claude.json \
    && chown $USERNAME:$USERNAME /home/$USERNAME/.claude.json

# ── Python dev tools ─────────────────────────────────────────────
RUN pip install --no-cache-dir \
    ruff \
    pyright \
    pytest \
    ipython \
    debugpy

# ── Firewall scripts + sudo ──────────────────────────────────────
# refresh-firewall-domains.sh is run periodically from cron (installed in
# post-start.sh) to re-resolve CDN-fronted domains whose IPs rotate.
COPY init-firewall.sh /usr/local/bin/
COPY refresh-firewall-domains.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/init-firewall.sh /usr/local/bin/refresh-firewall-domains.sh \
    && echo "$USERNAME ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh" \
       > /etc/sudoers.d/$USERNAME-firewall \
    && chmod 0440 /etc/sudoers.d/$USERNAME-firewall

ENV DEVCONTAINER=true
ENV PATH="/home/${USERNAME}/.local/bin:${PATH}"

USER dev
