#!/bin/bash
# dev-container-helpers.sh
# Copy to ~/.local/bin/ and source in your .bashrc or .zshrc:
#   cp .devcontainer/dev-container-helpers.sh ~/.local/bin/
#   echo '[ -f ~/.local/bin/dev-container-helpers.sh ] && source ~/.local/bin/dev-container-helpers.sh' >> ~/.bashrc
#
# Provides:
#   dcup        — start the dev container
#   dcexec      — exec a command with AWS creds injected
#   dcdanger    — launch Claude Code with AWS creds
#   dcnvim      — launch Neovim with AWS creds
#   dcshell     — get a bash shell with AWS creds
#   dcrefresh   — manually refresh the cached STS token
#
# AWS credentials are fetched once via STS and cached in memory
# for the lifetime of your shell session. They are passed into
# the container via `env` on each exec — never written to disk.

# --- Configuration -----------------------------------------------------------

# Default workspace folder (override per-call: dcup /path/to/project)
DC_WORKSPACE="${DC_WORKSPACE:-.}"

# STS token lifetime in seconds (default: 4 hours, max for IAM user: 129600 = 36 hrs)
DC_TOKEN_DURATION="${DC_TOKEN_DURATION:-14400}"

# If your IAM user has MFA, set these in your shell env:
#   export AWS_MFA_SERIAL="arn:aws:iam::123456789012:mfa/anant"
# Leave unset if MFA is not enabled.

# --- Internal state (do not edit) --------------------------------------------

_DC_AWS_ACCESS_KEY_ID=""
_DC_AWS_SECRET_ACCESS_KEY=""
_DC_AWS_SESSION_TOKEN=""
_DC_AWS_EXPIRATION=""

# --- Functions ---------------------------------------------------------------

_dc_log() {
  echo "[devcontainer] $*" >&2
}

_dc_is_token_valid() {
  # No token yet
  [[ -z "$_DC_AWS_EXPIRATION" ]] && return 1

  # Compare expiration (UTC ISO 8601) with current time.
  # Refresh 5 minutes early to avoid mid-session expiry.
  local exp_epoch now_epoch
  exp_epoch=$(date -d "$_DC_AWS_EXPIRATION" +%s 2>/dev/null) || return 1
  now_epoch=$(date +%s)
  (( now_epoch < exp_epoch - 300 ))
}

_dc_get_sts_token() {
  # If cached token is still valid, skip refresh
  if _dc_is_token_valid; then
    _dc_log "Using cached STS token (expires: $_DC_AWS_EXPIRATION)"
    return 0
  fi

  _dc_log "Requesting new STS session token (duration: ${DC_TOKEN_DURATION}s)..."

  local sts_args=(
    sts get-session-token
    --duration-seconds "$DC_TOKEN_DURATION"
    --output json
  )

  # If MFA is configured, prompt for the TOTP code
  if [[ -n "$AWS_MFA_SERIAL" ]]; then
    local mfa_code
    read -rp "MFA code for $(basename "$AWS_MFA_SERIAL"): " mfa_code
    sts_args+=(--serial-number "$AWS_MFA_SERIAL" --token-code "$mfa_code")
  fi

  local creds_json
  creds_json=$(aws "${sts_args[@]}") || {
    _dc_log "ERROR: aws sts get-session-token failed"
    return 1
  }

  _DC_AWS_ACCESS_KEY_ID=$(echo "$creds_json" | jq -r '.Credentials.AccessKeyId')
  _DC_AWS_SECRET_ACCESS_KEY=$(echo "$creds_json" | jq -r '.Credentials.SecretAccessKey')
  _DC_AWS_SESSION_TOKEN=$(echo "$creds_json" | jq -r '.Credentials.SessionToken')
  _DC_AWS_EXPIRATION=$(echo "$creds_json" | jq -r '.Credentials.Expiration')

  _dc_log "Token acquired (expires: $_DC_AWS_EXPIRATION)"
}

_dc_exec_with_creds() {
  # Fetch/refresh token
  _dc_get_sts_token || return 1

  # Run the command inside the container with creds injected via env
  devcontainer exec \
    --workspace-folder "$DC_WORKSPACE" \
    env \
      AWS_ACCESS_KEY_ID="$_DC_AWS_ACCESS_KEY_ID" \
      AWS_SECRET_ACCESS_KEY="$_DC_AWS_SECRET_ACCESS_KEY" \
      AWS_SESSION_TOKEN="$_DC_AWS_SESSION_TOKEN" \
      AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}" \
    "$@"
}

# --- Public commands ---------------------------------------------------------

dcup() {
  local workspace="${1:-$DC_WORKSPACE}"

  # Pre-flight: verify NOTES_PATH is set and points to a directory.
  if [[ -z "$NOTES_PATH" ]]; then
    _dc_log "ERROR: NOTES_PATH is not set. Export it in your shell config:"
    _dc_log "  export NOTES_PATH=/full/path/to/your/notes"
    return 1
  fi
  if [[ ! -d "$NOTES_PATH" ]]; then
    _dc_log "ERROR: NOTES_PATH does not point to a directory: $NOTES_PATH"
    [[ -f "$NOTES_PATH" ]] && _dc_log "  It's a file, not a directory."
    return 1
  fi

  # Pre-flight: verify EC2 key exists and is a file.
  # If Docker gets a bind mount source that doesn't exist, it silently
  # creates a directory — which replaces the real key file on the host.
  if [[ -z "$EC2_KEY_PATH" ]]; then
    _dc_log "ERROR: EC2_KEY_PATH is not set. Export it in your shell config:"
    _dc_log "  export EC2_KEY_PATH=/full/path/to/your-ec2-key.pem"
    return 1
  fi
  if [[ ! -f "$EC2_KEY_PATH" ]]; then
    _dc_log "ERROR: EC2_KEY_PATH does not point to a file: $EC2_KEY_PATH"
    [[ -d "$EC2_KEY_PATH" ]] && _dc_log "  It's a directory — Docker may have created it on a previous run."
    return 1
  fi

  devcontainer up --workspace-folder "$workspace"
}

dcexec() {
  _dc_exec_with_creds "$@"
}

dcdanger() {
  _dc_exec_with_creds claude --dangerously-skip-permissions "$@"
}

dcnvim() {
  _dc_exec_with_creds nvim "${@:-.}"
}

dcshell() {
  _dc_exec_with_creds bash "$@"
}

dcrefresh() {
  _DC_AWS_EXPIRATION=""  # Force refresh
  _dc_get_sts_token
}
