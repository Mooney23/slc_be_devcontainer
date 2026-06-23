# Scoped Agent Harness — Shoreline Backend

A least-privilege environment for running an AI coding agent (Claude Code) across the
full backend developer lifecycle — **dev → deploy → invoke → observe** — with each
capability scoped so that a mistake, or a hijacked agent, can't reach further than
intended.

This repo is **infrastructure, not an application.** It ships two independent pieces.

## 1. The `slc-plugins` marketplace — the agent's capabilities

A Claude Code plugin marketplace of shared skills for everyone.

It installs directly on a developer's host **or** is inherited inside the dev container —
it works the same either way, because the marketplace is independent of the container.

→ **Install commands and the capability catalog:** [`plugins/README.md`](plugins/README.md)

## 2. The dev container — the sandbox

A hardened, firewall-restricted Python dev-container base image plus the per-service
scaffolding that inherits from it. Default-deny egress; services `docker pull` the image.
This is the bounded place the agent runs.

→ **Build, setup, and firewall internals:** [`devcontainer/README.md`](devcontainer/README.md)

## Why it's shaped this way

The organizing principle is **least privilege across the lifecycle.** Every capability the
agent is given carries a guardrail in the same shape — a narrow credential, a validation
gate, and a fail-closed check — the same pattern as the firewall. New capabilities
(read-only DB access, scoped deploy / invoke) get added the same way, each bounding one
more blast radius, until the agent can take a ticket from spec to verified-in-test-env
without a human handing it broad credentials at any step.

→ **Full design rationale, the maturity ladder, and open questions:** [`docs/direction.md`](docs/direction.md)

## Layout

```
.claude-plugin/   # marketplace manifest — pinned to the repo root by Claude Code
plugins/          # marketplace plugin sources (the capabilities)
devcontainer/     # the dev-container sandbox: base image + scaffolding + its own README
docs/             # design docs (direction / north star)
CLAUDE.md         # guidance for Claude Code working in this repo
```
