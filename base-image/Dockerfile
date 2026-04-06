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
    && mkdir -p /home/$USERNAME/.config /home/$USERNAME/.local/share /home/$USERNAME/.local/bin /home/$USERNAME/.claude /home/$USERNAME/.cache/nvim \
    && chown -R $USERNAME:$USERNAME /home/$USERNAME

# ── Claude Code (native installer) ──────────────────────────────
# Installs to ~/.local/bin/claude as the dev user.
# Pin a specific version or use "latest".
ARG CLAUDE_CODE_VERSION=latest
USER $USERNAME
RUN curl -fsSL https://claude.ai/install.sh | bash -s -- -y ${CLAUDE_CODE_VERSION} \
    && echo 'export PATH="$HOME/.local/bin:$PATH"' >> /home/$USERNAME/.bashrc
USER root

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

# ── Firewall script + sudo ───────────────────────────────────────
COPY init-firewall.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/init-firewall.sh \
    && echo "$USERNAME ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh" \
       > /etc/sudoers.d/$USERNAME-firewall \
    && chmod 0440 /etc/sudoers.d/$USERNAME-firewall

ENV DEVCONTAINER=true
ENV PATH="/home/${USERNAME}/.local/bin:${PATH}"

USER dev
