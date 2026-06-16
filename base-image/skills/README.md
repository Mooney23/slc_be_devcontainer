# Baked-in Claude skills

Skills placed here are baked into the base image and shipped to every service
that uses it (they propagate via `docker pull`, no per-service copy).

## Layout

One directory per skill, each with a `SKILL.md`:

```
base-image/skills/
  my-skill/
    SKILL.md        # required: frontmatter (name, description) + instructions
    helper.py       # optional: scripts/resources the skill references
```

The directory name becomes the skill's invocation name (`/my-skill`).

## Baked skills

Generated from each `SKILL.md`'s frontmatter — **do not edit by hand.** After
adding, removing, or renaming a skill, regenerate with
`./scripts/gen-skills-index.sh`.

<!-- BEGIN baked-skills (generated — run scripts/gen-skills-index.sh) -->
| Skill | Description |
|---|---|
| `architecture-decision-records` | Capture architectural decisions made during coding sessions as structured ADRs (Architecture Decision Records, Nygard format) under `docs/adr/`. |
| `cloudwatch-logs-search` | Search AWS CloudWatch Logs safely and accurately from the terminal via boto3 (read-only) — targeted log searches that match or beat clicking around the AWS console, with built-in c… |
| `update-kb` | Assess the current conversation and capture hard-won behavioural knowledge about a backend service into its knowledge base — a `docs/` KB of concepts, runbooks, and gotchas. |
<!-- END baked-skills -->

## How they reach the agent at runtime

The Dockerfile copies this dir to `/opt/claude-skills/` in the image. It is
**not** copied to `~/.claude/skills` directly, because that path is a mount
point at runtime and the image's copy would be shadowed.

On container start, `dev-post-start.sh` merges two sources into the real skills
dir (a tmpfs at `~/.claude/skills`):

1. these baked-in skills (`/opt/claude-skills/`)
2. the developer's host user-scope skills (`~/.claude/skills-host`, read-only)

Because everything lands in a single directory, Claude Code's cross-scope
precedence never applies — the merge order decides name collisions. The current
policy is **host-wins**: a developer's same-named host skill overrides the
baked one, so baked skills act as overridable defaults. To make baked skills
authoritative (locked), swap the loop order in `dev-post-start.sh`.
