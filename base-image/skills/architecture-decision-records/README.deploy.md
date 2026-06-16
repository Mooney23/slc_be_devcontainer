# Deploying `architecture-decision-records`

A repo-agnostic Claude skill that captures architectural **decisions** as structured ADRs (Nygard
format) under `docs/adr/`. It's the decision-log companion to the `update-kb` behavioural-KB skill —
the two live under the same `docs/` root and cross-reference each other.

Adapted from the original (origin: ECC) for backend Python/DB services: examples reframed, the
ECC-specific "Integration with Other Skills" section replaced with KB cross-linking, and the
bootstrap/confirm wording aligned with `update-kb` (bundled templates in `assets/`, confirm before any
write).

## Contents

```
architecture-decision-records/
  SKILL.md                       # capture + read + bootstrap; lifecycle; KB cross-linking
  assets/
    adr-template.md              # ADR skeleton — drafted from this, and dropped into docs/adr/template.md at bootstrap
    adr-index-template.md        # seeds docs/adr/README.md at bootstrap
```

## Bake into the base image (parity with `cloudwatch-logs-search` / `update-kb`)

1. Copy this whole `architecture-decision-records/` folder into the base-image repo's baked-skills dir
   (the one the Dockerfile copies to `/opt/claude-skills/`), alongside `cloudwatch-logs-search/` and
   `update-kb/`.
2. Rebuild / push the base image.
3. `docker pull` + restart each service container. `dev-post-start.sh` merges `/opt/claude-skills/`
   into `~/.claude/skills/` on start, so the skill appears everywhere.

End state: three baked skills — `cloudwatch-logs-search` (forensics), `update-kb` (behaviour),
`architecture-decision-records` (decisions).
