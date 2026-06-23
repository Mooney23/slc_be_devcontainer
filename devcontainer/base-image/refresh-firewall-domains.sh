#!/bin/bash
# =============================================================================
# Periodic DNS refresh for the egress firewall
#
# CloudFront (and other CDN-fronted) domains rotate their IPs frequently.
# init-firewall.sh resolves the service's EXTRA_DOMAINS to IPs only once, at
# container startup, so outbound connections break when the CDN moves to new
# IPs mid-session.
#
# This script re-resolves EXTRA_DOMAINS and adds any new IPs to the
# allowed-domains ipset. It is meant to run from cron every few minutes
# (the entry is installed by post-start.sh).
#
# Design notes:
#   * Add-only. We never remove stale IPs. Stale IPs are harmless — the CDN no
#     longer routes traffic through them, so they cannot be used for
#     exfiltration — and removing them could tear down in-flight connections.
#   * Scoped to EXTRA_DOMAINS only. This keeps the whitelist limited to the
#     domains each devcontainer explicitly opted into, rather than opening up
#     entire CDN CIDR ranges (which would weaken the exfiltration defense).
#   * Must run as root: `ipset add` requires it. The installed cron entry
#     lives in root's crontab, so no sudo is needed here.
# =============================================================================

set -uo pipefail

EXTRAS_FILE="/workspace/.devcontainer/firewall-extras.sh"
IPSET_NAME="allowed-domains"

# Nothing to refresh if the service didn't define extra domains.
[ -f "$EXTRAS_FILE" ] || exit 0

EXTRA_DOMAINS=()
# shellcheck disable=SC1090
source "$EXTRAS_FILE"

[ "${#EXTRA_DOMAINS[@]}" -eq 0 ] && exit 0

for domain in "${EXTRA_DOMAINS[@]}"; do
    # Literal IPs don't rotate — skip them.
    if [[ "$domain" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
        continue
    fi

    ips=$(dig +noall +answer A "$domain" | awk '$4 == "A" {print $5}')
    [ -z "$ips" ] && continue

    while read -r ip; do
        [[ "$ip" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]] || continue
        # `|| true` so an already-present IP (or a transient error) does not
        # abort the loop for the remaining domains.
        ipset add "$IPSET_NAME" "$ip" 2>/dev/null || true
    done <<< "$ips"
done
