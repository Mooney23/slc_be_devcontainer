# `slc-plugins` — Shoreline Claude Code marketplace

A Claude Code **plugin marketplace** of shared skills for Shoreline teams. It is one
of the two independent pieces of this repo (the other is the
[devcontainer sandbox](../devcontainer/README.md)), and it is **self-contained — it does not
require the container.** It installs straight onto your host and behaves the same whether you
run Claude Code on the host or inside a service's dev container.

> **Just want the plugins?** You're in the right place — jump to [Install](#install).
> You do **not** need to build or run the devcontainer.

## Why a marketplace instead of skills in each repo

The alternative is committing skills directly into each service repo under `.claude/skills/`.
That works for one repo, but breaks down quickly across a team that works across many:

**Drift.** A skill copied into five repos will diverge. One gets a bug fix, another gets a new
flag, a third never gets either. The "same" skill ends up doing slightly different things
depending on which repo you're in — which is worse than a consistent, slightly older version,
because it's invisible.

**Maintenance overhead.** Every improvement means opening PRs across every repo that has a copy.
That's friction that compounds — in practice it means skills stop being improved because the cost
of shipping a fix is too high.

**Ownership is unclear.** A skill sitting in a service repo looks like it belongs to that service.
It gets reviewed as if it's application code, changed for local reasons, and nobody is watching
whether it has drifted from the canonical version.

**Discoverability.** Skills scattered across repos are hard to find. A teammate can't easily see
what's available or install only what's relevant to their work.

The marketplace solves all of these. Skills have one home, one owner, and one history. An
improvement ships once and every developer picks it up with a single `marketplace update`. Teams
can install only the plugins relevant to them, and anyone can add a new plugin without touching
application code.

The one tradeoff: a skill in the marketplace can't be tailored to a specific repo without
forking it into a new plugin. For a genuinely repo-specific skill (one that would never make
sense anywhere else), committing it locally is still the right call.

## Prerequisites

- **Claude Code** installed on your host (`claude --version`).
- **Read access** to the private `shorelineiot/claude_utils` repo with working git auth — an SSH
  key, or an app-password / token over HTTPS. `marketplace add` / `update` runs `git clone` /
  `fetch` under your own credentials; there is no separate auth path, so without repo access
  you'll get a clone auth failure.

## Install

Run these **on your host**, not inside a container:

```bash
# Register the marketplace, then install the plugins you want
claude plugin marketplace add git@bitbucket.org:shorelineiot/claude_utils.git \
  --sparse .claude-plugin plugins
claude plugin install <plugin-name>@slc-plugins   # e.g. slc-be-aws-ops@slc-plugins
```

Run the `install` line once per plugin you want — see [What's in it](#whats-in-it) below for the
available plugin names.

A new Claude Code session is needed for newly installed plugins to appear — skills are
enumerated at session start.

### Why `--sparse .claude-plugin plugins`

This repo is the whole scoped-agent-harness monorepo (the `devcontainer/` infra, `docs/`, …),
but the marketplace only needs the manifest (`.claude-plugin/marketplace.json`) and the plugin
sources (`plugins/`). `--sparse` uses git sparse-checkout to fetch just those two directories
instead of cloning the entire repo into `~/.claude/plugins/marketplaces/slc-plugins/`. The
sparse config persists in the clone, so later `claude plugin marketplace update slc-plugins`
pulls stay scoped to the same paths.

Sparse paths are fixed at `add` time — to change them (or to switch an existing non-sparse
registration to sparse), `claude plugin marketplace remove slc-plugins` and re-add.

## What's in it

The source of truth for what's in the marketplace is
[`../.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json) — every plugin is
declared there, with its sources under `plugins/<plugin>/`. Plugins are independent, so you can
install only the ones you need (see [Install](#install) above).

The table below is a hand-maintained index for browsing; keep it in sync with
`marketplace.json` when you add or rename a plugin (step 4 of
[Adding a plugin](#adding-a-plugin)).

| Plugin | What it does |
|---|---|
| [`slc-be-aws-ops`](slc-be-aws-ops/README.md) | Safe, read-only AWS operations from the terminal — CloudWatch Logs search with built-in cost guards. |
| [`slc-be-knowledge`](slc-be-knowledge/README.md) | Capture and maintain a service's knowledge base (concepts, runbooks, gotchas) and architecture decision records. |
| [`slc-be-dev`](slc-be-dev/README.md) | Inner dev loop — manage the local Flask dev server and make test requests against it. |
| [`slc-be-bitbucket`](slc-be-bitbucket/README.md) | Review Bitbucket pull requests — view, list, diff, read comments, and post review comments (no approve/merge). |
| [`notes-workflow`](notes-workflow/README.md) | Personal notes vault — daily logs, weekly summaries, and cross-session memory. |

## Updating

Skills aren't baked into any image — they live in this repo. To ship a change: edit the skill
under `plugins/`, push, and developers pick it up with a normal plugin update:

```bash
claude plugin marketplace update slc-plugins
```

(Again, a fresh Claude Code session is needed for the update to take effect.)

## Using it inside the devcontainer

You don't install anything extra in the container. Install the marketplace **on your host** as
above; the dev container inherits the plugins for free, because `~/.claude` (including
`~/.claude/plugins/`) is bind-mounted in. See
[`../devcontainer/README.md`](../devcontainer/README.md#claude-skills) for the container-side
plumbing — and for how a developer's loose host skills under `~/.claude/skills/` also reach the
container.

## Adding a plugin

> **Shortcut:** ask the repo-local `plugin-scaffolder` skill to do all of this for you — say
> something like *"scaffold a new plugin"*. It collects the plugin name (validating the
> convention below), creates the files, registers the plugin, updates the index table, validates
> the manifests, and hands off to `skill-creator` for the skill content. The manual steps below
> are the fallback and the reference for what it does.

### 1. Create the plugin directory

Start with a fresh branch with a clean working tree.

**Naming convention.** A plugin tied to a specific team or stack is named
`slc-<team>-<name>` — `slc` for the org (Shoreline), the middle segment for the team/stack
(`be` = backend, `fe` = frontend, `mob` = mobile, `fw` = firmware, `qa` = qa, `hw` = hardware), and the rest describing what it does (e.g. `slc-be-aws-ops`,
`slc-be-knowledge`). A general-purpose plugin that isn't team- or stack-specific takes a plain
descriptive name with no prefix (e.g. `notes-workflow`). Use kebab-case throughout.

```
plugins/<plugin-name>/
├── .claude-plugin/
│   └── plugin.json
├── README.md
└── skills/
```

Write a `README.md` following the pattern of the existing ones: a short intro paragraph
describing what the plugin is for, then a **Skills** section with one entry per skill.

### 2. Add the plugin manifest

Add a `.claude-plugin/plugin.json` manifest. Per Claude Code's
[plugin reference](https://code.claude.com/docs/en/plugins-reference) the manifest is
technically *optional* — without one, Claude Code auto-discovers `skills/` and derives the
name from the directory. But it's the only place to declare metadata (author, version,
license, …), and every plugin in this marketplace has one, so **always include it** to match
the convention. Follow the existing plugins' shape:

```json
{
  "name": "<plugin-name>",
  "description": "<one sentence — what the plugin does>",
  "author": {
    "name": "<your name>",
    "email": "<your email>"
  }
}
```

`name` is the only required field; it must be kebab-case and match both the directory name
and the marketplace entry you add in step 4. `description` and `author` are our baseline;
other optional fields (`version`, `homepage`, `repository`, `license`, `keywords`) are
available if useful. Where a field appears in both this manifest and the marketplace entry,
`plugin.json` wins — so the `description` duplicated across the two should be kept in sync.

> The `.claude-plugin/` directory holds **only** `plugin.json`. The `skills/` directory (and
> any other component dirs) must live at the plugin root, not inside `.claude-plugin/`.

### 3. Add skills

Each skill is a subdirectory under `skills/`:

```
skills/<skill-name>/
├── SKILL.md
└── README.md   # optional, recommended for non-trivial skills
```

`SKILL.md` is what Claude Code loads. It requires a YAML frontmatter block at the top:

```yaml
---
name: <skill-name>
description: >-
  <one or two sentences — this is the trigger mechanism. Claude reads this to decide
  when to invoke the skill, so describe the intent and list the natural-language
  phrases that should activate it.>
---
```

The body is the operating instruction for the skill — what Claude should do when it
triggers. See any existing `SKILL.md` for the pattern.

A skill-level `README.md` is optional but worth writing for anything with scripts,
non-obvious prerequisites, or enough complexity that a human needs a guide separate
from the operating instructions.

### 4. Register in the marketplace

Add an entry to [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json):

```json
{
  "name": "<plugin-name>",
  "source": "./plugins/<plugin-name>",
  "description": "<one sentence shown in plugin listings>"
}
```

This file is the source of truth for the marketplace. Also add a row to the
[What's in it](#whats-in-it) table so the human-facing index stays in sync.

### 5. Ship it

Push the branch and raise a pull request to main as you would normally. Once it is on main, developers pick it up by:

```bash
claude plugin marketplace update slc-plugins
```

A new Claude Code session is needed for the updated skills to appear.

## How this fits the bigger picture

In the [scoped agent harness](../docs/direction.md) framing, this marketplace is how the agent
gets its **capabilities** — each one scoped with its own guardrail (e.g. `cloudwatch-logs-search`'s
cost guards and read-only access). Plugins aimed at a specific team or stack carry that context in
their name (e.g. `slc-be-knowledge`, `slc-be-dev`), but the marketplace itself is open to
any team. New capabilities will land here the same way. See [`../docs/direction.md`](../docs/direction.md)
for the full direction, and the root [`../README.md`](../README.md) for the two-piece overview.
