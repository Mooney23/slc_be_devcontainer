#!/bin/bash
# Thin wrapper — the real post-start logic lives in the base image at
# /usr/local/bin/dev-post-start.sh, so startup changes propagate via a
# `docker pull` of a new base image (no need to re-copy this file).
#
# Copy this file into your service's .devcontainer/ once and leave it; it
# should not need to change again. For service-specific startup steps, add a
# .devcontainer/post-start.local.sh instead (run automatically at the end of
# dev-post-start.sh) — do NOT add logic here.
exec bash /usr/local/bin/dev-post-start.sh
