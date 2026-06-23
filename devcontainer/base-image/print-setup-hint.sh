#!/bin/bash
HINT_FILE="/tmp/.devcontainer-hint-shown"

if [[ ! -f "$HINT_FILE" ]]; then
  cat <<'EOF'

  ┌───────────────────────────────────────────────────────────────┐
  │                                                               │
  │  Dev container ready!                                         │
  │                                                               │
  │  If you haven't already, copy the helper script and           │
  │  source it in your shell config on the HOST:                  │
  │                                                               │
  │  1. Copy the script:                                          │
  │     cp .devcontainer/dev-container-helpers.sh ~/.local/bin/   │
  │                                                               │
  │  2. Add to your ~/.bashrc or ~/.zshrc:                        │
  │     source ~/.local/bin/dev-container-helpers.sh              │
  │                                                               │
  │  3. Reload your shell:                                        │
  │     source ~/.bashrc                                          │
  │                                                               │
  │  This provides: dcup, dcdanger, dcnvim, dcshell, dcrefresh    │
  │                                                               │
  └───────────────────────────────────────────────────────────────┘

EOF
  touch "$HINT_FILE"
fi
