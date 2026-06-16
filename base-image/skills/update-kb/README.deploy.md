# Deploying `update-kb`

This folder is a self-contained, repo-agnostic Claude skill. It generalizes the old
project-scoped `update-device-kb` skill so it works in any backend (Python / DB) service repo:
it discovers the service's `docs/` KB and updates it, or bootstraps a new KB if none exists.

## Contents

```
update-kb/
  SKILL.md                       # the skill (engine: locate → assess → cream-filter → write → index; + bootstrap mode)
  assets/
    concept-template.md          # doc skeletons
    runbook-template.md
    gotcha-template.md
    kb-readme-template.md        # used only by bootstrap mode
    kb-index-template.md         # used only by bootstrap mode
```

## Bake into the base image (parity with `cloudwatch-logs-search`)

Skills baked into the `slc_be_devcontainer` base image ship to every backend service via
`docker pull`. To add this one:

1. Copy this whole `update-kb/` folder into the base-image repo's baked-skills dir
   (the one the Dockerfile copies to `/opt/claude-skills/` — alongside `cloudwatch-logs-search/`).
2. Rebuild / push the base image.
3. In each service container, `docker pull` + restart. `dev-post-start.sh` merges
   `/opt/claude-skills/` into the tmpfs `~/.claude/skills/` on start, so the skill appears
   as `update-kb` everywhere.

Precedence is **host-wins**, so a developer can still override it with a same-named host skill.

## Retire the old project-scoped skill

Once `update-kb` is baked in, remove the repo-local `/workspace/.claude/skills/update-device-kb/`
from the device service repo so the two don't both trigger. The device repo's `docs/` KB is
untouched by this — only the *skill* moves out of the repo and into the image.
