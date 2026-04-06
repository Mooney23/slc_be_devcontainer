#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

# =============================================================================
# Egress firewall for dev container
#
# Restricts outbound network access to only the domains Claude Code needs,
# plus the EC2 bastion host for database tunneling.
# This is a defense-in-depth measure against prompt injection attacks that
# try to exfiltrate data from the container.
#
# Since git is used from the host (not inside the container), GitHub IPs
# are NOT whitelisted. This keeps the attack surface minimal.
# =============================================================================

echo "=== Initializing container firewall ==="

# --- Preserve Docker internal DNS before flushing ---
# Docker uses an embedded DNS server at 127.0.0.11 for container name
# resolution. We need to save and restore these NAT rules.
DOCKER_DNS_RULES=$(iptables-save -t nat | grep "127\.0\.0\.11" || true)

# --- Flush all existing rules ---
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X
ipset destroy allowed-domains 2>/dev/null || true

# --- Restore Docker DNS rules ---
if [ -n "$DOCKER_DNS_RULES" ]; then
    echo "Restoring Docker DNS rules..."
    iptables -t nat -N DOCKER_OUTPUT 2>/dev/null || true
    iptables -t nat -N DOCKER_POSTROUTING 2>/dev/null || true
    echo "$DOCKER_DNS_RULES" | xargs -L 1 iptables -t nat
else
    echo "No Docker DNS rules to restore"
fi

# --- Allow DNS and localhost first (needed for everything else) ---
# Outbound DNS
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
# Inbound DNS responses
iptables -A INPUT -p udp --sport 53 -j ACCEPT
# Localhost (needed for Claude Code OAuth callback, LSP, etc.)
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# --- Detect and allow Docker host network ---
# This allows port forwarding between container and host (needed for
# Claude Code's OAuth browser flow and your application ports)
HOST_IP=$(ip route | grep default | cut -d" " -f3)
if [ -z "$HOST_IP" ]; then
    echo "ERROR: Failed to detect host IP"
    exit 1
fi
HOST_NETWORK=$(echo "$HOST_IP" | sed "s/\.[0-9]*$/.0\/24/")
echo "Host network detected as: $HOST_NETWORK"
iptables -A INPUT -s "$HOST_NETWORK" -j ACCEPT
iptables -A OUTPUT -d "$HOST_NETWORK" -j ACCEPT

# --- Create IP whitelist ---
ipset create allowed-domains hash:net

# Domains Claude Code needs to function:
#   api.anthropic.com     - Claude Code API (the actual LLM calls)
#   sentry.io             - Error reporting
#   statsig.anthropic.com - Feature flags / telemetry
#   statsig.com           - Feature flags / telemetry
#   registry.npmjs.org    - In case claude code needs packages
#
# EC2 bastion host for SSH tunneling to the database.
# This is your own infrastructure — whitelisting it does not weaken
# the threat model. A prompt injection still cannot exfiltrate data
# to an attacker-controlled server.
#
# Domains intentionally NOT included:
#   github.com / api.github.com  - git is done from the host
#   pypi.org / files.pythonhosted.org - pip install is done at container
#       build time; if you need to install packages at runtime, add these
#   *.visualstudio.com    - VS Code specific, not needed for Neovim

ALLOWED_DOMAINS=(
    "api.anthropic.com"
    # "sentry.io"
    # "statsig.anthropic.com"
    # "statsig.com"
    # "registry.npmjs.org"
    "bitbucket.org"
    "shorelineiot.atlassian.net"
    "github.com"
)

# EC2 bastion host(s) for SSH tunneling to the database.
# EC2_HOST is written to /tmp/.ec2_host by postStartCommand before
# this script runs, because sudo strips environment variables.
EC2_HOST=""
if [ -f /tmp/.ec2_host ]; then
    EC2_HOST=$(cat /tmp/.ec2_host | tr -d '[:space:]')
fi
if [ -n "$EC2_HOST" ]; then
    ALLOWED_DOMAINS+=("$EC2_HOST")
    echo "EC2 bastion host added to whitelist: $EC2_HOST"
else
    echo "WARNING: EC2_HOST not set — SSH tunneling to database will not work"
fi

for domain in "${ALLOWED_DOMAINS[@]}"; do
    echo "Resolving $domain..."

    # Check if it's already an IP address
    if [[ "$domain" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
        echo "  Adding $domain (direct IP)"
        ipset add allowed-domains "$domain" 2>/dev/null || true
        continue
    fi

    ips=$(dig +noall +answer A "$domain" | awk '$4 == "A" {print $5}')

    if [ -z "$ips" ]; then
        echo "WARNING: Failed to resolve $domain (may not be needed yet)"
        continue
    fi

    while read -r ip; do
        if [[ ! "$ip" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
            echo "ERROR: Invalid IP from DNS for $domain: $ip"
            exit 1
        fi
        echo "  Adding $ip ($domain)"
        ipset add allowed-domains "$ip" 2>/dev/null || true
    done <<< "$ips"
done

# --- Whitelist AWS service IP ranges by CIDR ---
# AWS endpoints rotate IPs frequently, so DNS-based resolution is unreliable.
# Instead, we fetch the official AWS IP ranges and whitelist the CIDRs for
# the specific services and region we need.
#
# This is safe because these are AWS service endpoints, not arbitrary internet
# destinations. A prompt injection cannot use ssm.us-east-1.amazonaws.com as
# an exfiltration channel.
#
# Source: https://docs.aws.amazon.com/general/latest/gr/aws-ip-ranges.html

AWS_REGION="us-east-1"
AWS_SERVICES=("SSM" "S3" "EC2" "AMAZON")

echo ""
echo "Fetching AWS IP ranges for $AWS_REGION..."
AWS_IP_RANGES=$(curl -s --connect-timeout 10 https://ip-ranges.amazonaws.com/ip-ranges.json)

if [ -z "$AWS_IP_RANGES" ]; then
    echo "ERROR: Failed to fetch AWS IP ranges"
    exit 1
fi

aws_cidrs_added=0
for service in "${AWS_SERVICES[@]}"; do
    cidrs=$(echo "$AWS_IP_RANGES" | jq -r \
        --arg region "$AWS_REGION" \
        --arg service "$service" \
        '.prefixes[] | select(.region == $region and .service == $service) | .ip_prefix')

    while read -r cidr; do
        [ -z "$cidr" ] && continue
        ipset add allowed-domains "$cidr" 2>/dev/null || true
        aws_cidrs_added=$((aws_cidrs_added + 1))
    done <<< "$cidrs"
done
echo "Added $aws_cidrs_added AWS CIDRs for services: ${AWS_SERVICES[*]}"

# --- Set default policies to DROP ---
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP

# --- Allow established connections (for already-approved traffic) ---
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# --- Allow outbound only to whitelisted IPs ---
iptables -A OUTPUT -m set --match-set allowed-domains dst -j ACCEPT

# --- Reject everything else with immediate feedback ---
# REJECT instead of DROP so tools fail fast instead of hanging
iptables -A OUTPUT -j REJECT --reject-with icmp-admin-prohibited

echo ""
echo "=== Firewall configuration complete ==="
echo ""

# --- Verification ---
echo "Running verification checks..."

# Should FAIL: random internet access
if curl --connect-timeout 5 https://example.com >/dev/null 2>&1; then
    echo "FAIL: Was able to reach example.com (should be blocked)"
    exit 1
else
    echo "PASS: example.com is blocked"
fi

# Should FAIL: common exfiltration targets
if curl --connect-timeout 5 https://webhook.site >/dev/null 2>&1; then
    echo "FAIL: Was able to reach webhook.site (should be blocked)"
    exit 1
else
    echo "PASS: webhook.site is blocked"
fi

# Should SUCCEED: Claude Code API
if curl --connect-timeout 5 https://api.anthropic.com >/dev/null 2>&1; then
    echo "PASS: api.anthropic.com is reachable"
else
    echo "FAIL: Cannot reach api.anthropic.com (Claude Code won't work)"
    exit 1
fi

# Should SUCCEED: EC2 bastion (if configured)
if [ -n "$EC2_HOST" ]; then
    if nc -z -w 5 "$EC2_HOST" 22 2>/dev/null; then
        echo "PASS: EC2 bastion ($EC2_HOST) is reachable on port 22"
    else
        echo "WARNING: Cannot reach EC2 bastion ($EC2_HOST) on port 22 — SSH tunnel may fail"
    fi
fi

echo ""
echo "All checks passed. Container is locked down."