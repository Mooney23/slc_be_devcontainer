#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

# =============================================================================
# Browser automation addon (Playwright + headless Chromium)
#
# This script is BAKED into the base image but does nothing on its own. A
# service opts in by calling it from its own .devcontainer/Dockerfile, gated
# on a build-arg, e.g.:
#
#     ARG INSTALL_BROWSER=false
#     USER root
#     RUN if [ "$INSTALL_BROWSER" = "true" ]; then \
#             bash /usr/local/bin/install-browser-addon.sh; \
#         fi
#     USER dev
#
# Why an addon instead of baking Chromium into every base image:
#   - Chromium + system libs add ~400-500 MB; most services don't browse.
#   - Keeping it opt-in means slim services stay slim.
#
# Why this runs at SERVICE BUILD time (not container start):
#   - It needs Playwright's CDN to fetch the browser. The iptables egress
#     firewall (init-firewall.sh) only runs at container START, so build
#     time has open network. Both the browser AND the MCP server are baked
#     here so that at RUNTIME nothing needs npm/CDN — the firewall blocks
#     registry.npmjs.org, so a runtime `npx @playwright/mcp` would hang.
#
# Run as root: `playwright install --with-deps` installs apt packages.
# =============================================================================

# Pin these for reproducible builds. Defaults to `latest`; override by
# exporting before the addon runs, or pass via the service Dockerfile.
PLAYWRIGHT_MCP_VERSION="${PLAYWRIGHT_MCP_VERSION:-latest}"

# System-wide browser path so the browser `root` installs is usable by `dev`.
# Mirrors the official mcr.microsoft.com/playwright image convention.
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/ms-playwright}"

echo "=== Installing browser automation addon ==="
echo "  @playwright/mcp version: ${PLAYWRIGHT_MCP_VERSION}"
echo "  PLAYWRIGHT_BROWSERS_PATH: ${PLAYWRIGHT_BROWSERS_PATH}"

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: this addon must run as root (it installs apt packages)." >&2
    exit 1
fi

# --- 1. Install the MCP server globally (baked, so runtime needs no npm) ---
# This pulls in the matching `playwright` package as a dependency, which
# provides the `playwright` CLI used to install browsers below.
echo "Installing @playwright/mcp@${PLAYWRIGHT_MCP_VERSION}..."
npm install -g "@playwright/mcp@${PLAYWRIGHT_MCP_VERSION}"

# --- 2. Install Chromium + system dependencies ---
# Use the playwright CLI that shipped with @playwright/mcp so the browser
# build matches what the MCP server expects. --with-deps adds the apt libs
# Chromium needs to render headlessly.
echo "Installing Chromium + system dependencies..."
mkdir -p "$PLAYWRIGHT_BROWSERS_PATH"
playwright install --with-deps chromium

# --- 3. Make the browser readable/executable by the non-root `dev` user ---
chmod -R a+rX "$PLAYWRIGHT_BROWSERS_PATH"

# --- 4. Sanity-check the MCP server binary the runtime .mcp.json relies on ---
# The committed .mcp.json invokes `mcp-server-playwright` directly (the global
# bin from @playwright/mcp) so runtime needs no npm fetch. If the package ever
# renames its bin, fail the build here rather than hanging at container start.
if ! command -v mcp-server-playwright >/dev/null 2>&1; then
    echo "ERROR: mcp-server-playwright not on PATH after install." >&2
    echo "       The @playwright/mcp bin name may have changed — update .mcp.json." >&2
    exit 1
fi

# --- 5. Tidy apt lists added by --with-deps to keep the layer small ---
rm -rf /var/lib/apt/lists/*

echo "=== Browser automation addon installed ==="
