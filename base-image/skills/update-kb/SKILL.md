---
name: update-kb
description: >-
  Assess the current conversation and capture hard-won behavioural knowledge about a backend service
  into its knowledge base — a `docs/` KB of concepts, runbooks, and gotchas. Use this AFTER
  investigating, debugging, tracing, or building anything where you uncovered non-obvious behaviour:
  silent failures, cross-DB coordination, multi-step flows, ordering constraints, things that don't
  update when you'd expect. Triggers on "update the kb", "add to the knowledge base", "document this in
  the kb", "kb update", "capture this in the kb", or any request to record learnings about how a service
  behaves. Also handles bootstrapping — if the repo has no KB yet, this skill scaffolds one ("set up a
  knowledge base here", "start a kb for this service"). Works in any backend (Python / DB) service repo:
  it discovers the KB or offers to create one. Use it proactively at the end of a task if significant
  service knowledge was uncovered that would otherwise be lost.
---

# Update Knowledge Base

Assess the current conversation and update (or bootstrap) the **service knowledge base** for whatever
backend repo you're in. A KB documents the *behavioural* internals of a service — concepts, runbooks,
and gotchas — the operational knowledge you can't easily get back by re-reading the code.

This skill is repo-agnostic. The per-service specifics (what's in scope, what conventions apply, what
already exists) live in the **target repo's own** `docs/README.md` and `docs/INDEX.md`, not in this
skill. Your job is to run the engine: find the KB, figure out what was learned, filter it down to the
parts worth keeping, and write them where they belong.

## KB structure

```
docs/
  README.md         — how to use the KB, quality standards, conventions, scope boundary
  INDEX.md          — full docs index with status tracking
  concepts/         — "What is X and how does it behave?"
  runbooks/         — "How do I do X?"
  gotchas/          — "What will bite me?"
```

**File naming:** `kebab-case-name.md` (no number prefixes — INDEX.md provides ordering).

## Templates

The doc skeletons live in **this skill's own `assets/` directory** (the skill's base directory is shown
to you when this skill loads — don't hardcode an absolute path, it differs between a baked install and a
project install). Read the relevant template before writing a doc:

- `assets/concept-template.md`
- `assets/runbook-template.md`
- `assets/gotcha-template.md`
- `assets/kb-readme-template.md` — used only when bootstrapping a new KB
- `assets/kb-index-template.md` — used only when bootstrapping a new KB

---

## Step 0: Locate the KB (do this first, every time)

The KB lives at `docs/` by convention. Confirm it's actually a behavioural KB (not, say, a Sphinx site
or a generic `docs/` folder) by checking for both a KB-style README and an INDEX:

```bash
ls docs/README.md docs/INDEX.md 2>/dev/null
```

- **Both exist** and the README's top heading reads like a knowledge base (e.g. ends in "Knowledge
  Base") → a KB is present. Go to **Mode A: Update an existing KB**.
- **Neither exists** (or only a generic `docs/` with no INDEX) → no KB here yet. Go to
  **Mode B: Bootstrap a new KB**.

If the user explicitly asks to *set up / start* a KB, go straight to Mode B even if a stray `docs/`
exists — but check first so you don't clobber something real (read what's there and tell the user what
you found before writing).

---

## Mode A: Update an existing KB

### Prerequisites

1. **Read the README** at `docs/README.md` — it holds *this service's* quality standards, conventions,
   and scope boundary. You MUST read it before writing anything; it's the source of truth for what
   belongs in this particular KB and overrides any generic guidance here if they differ.
2. **Read the INDEX** at `docs/INDEX.md` — the full docs index with status tracking, so you know what
   already exists.
3. **Get the current commit hash** via `git rev-parse --short HEAD` — needed for the `Last verified`
   header on any doc you create or update.

### Step 1: Assess what was learned

Review the conversation and identify knowledge about the service that was uncovered. Look for:

- **Concepts investigated** — how entities behave, relationships between tables, JSON structures,
  multi-step processes.
- **Procedures traced** — code paths from entry point to DB commit: what gets updated, what gets
  skipped.
- **Bugs or gotchas discovered** — surprising behaviour, silent failures, cross-DB consistency issues.

Categorize each piece:
- **Concept** — what something is and how it behaves → `concepts/`
- **Runbook** — step-by-step procedure for a specific operation → `runbooks/`
- **Gotcha** — surprising behaviour that will bite you → `gotchas/`

#### The "Would Reading the Code Tell You This?" filter

This is the single most important quality gate, and it's why a KB is worth keeping at all. Before adding
ANY content, apply this test to each piece of knowledge:

> If a competent engineer opened the relevant source file and spent 10 minutes reading it, would they
> learn this?

If **yes** → do NOT add it. It's noise, and it'll be stale the moment the code changes. Examples that
fail the test (don't add them):
- Table column names and types (readable from the model / ORM file)
- Function signatures and parameter names
- What a route does (readable from the routes + controller)
- Import relationships between modules

If **no** → it's KB-worthy. Examples that pass (these are the cream):
- "PATCH silently ignores certain fields in the request body — you'd only find this by tracing the
  whole update flow and noticing what's *missing*."
- "The same logical key maps to a different surrogate id across revisions, so 'the same thing' has
  different ids in different versions — not visible in the schema."
- "The consumer reads from config table A, NOT from table B directly — a cross-service coupling no
  single file reveals."
- "Old rows are never cleaned up on a switch because the upsert keys on X, and the old records have a
  different X — requires understanding two systems together."
- Multi-step procedures spanning several files/services where the **order** and **coordination** matter.
- Cross-DB relationships with no FK constraints that must be maintained by hand.

The KB should hold only the **cream** — insights that save someone hours. If in doubt, leave it out.

### Step 2: Compare against the existing KB

Using the INDEX you read, decide for each piece of knowledge:

1. **New doc needed** — not covered by any existing doc.
2. **Existing Stub to fill** — a placeholder exists with no real content.
3. **Existing doc to update** — a Seed or Written doc is missing what you learned.
4. **Already covered** → skip.

Present the assessment and wait for confirmation before writing anything:

```
KB update assessment:

New docs to create:
  - concepts/<name>.md — <one line on what it captures>

Existing docs to update:
  - concepts/<name>.md — <the new behaviour you'd add>

New gotcha:
  - gotchas/<name>.md — <one line>

Already covered (no action):
  - <doc> — <why it's already there>

Proceed with all? Or select specific items?
```

### Step 3: Create or update docs

**Creating a new doc:**

1. Pick the category (`concepts/`, `runbooks/`, `gotchas/`).
2. Read the matching template from this skill's `assets/`, then use it as the skeleton — replace every
   placeholder with real content.
3. Write the doc to the standard from the repo's README. In general:
   - **Concept docs** — behavioural explanation not obvious from code, plus cross-references. Do NOT
     dump full table schemas (Column/Type/Description grids). Use a one-line prose mention of the table
     (name, its DB, composite PK, model file path). Include tables only when they show *relationships,
     sequences, or mappings* (what triggers what, deletion order, cross-DB references).
   - **Runbook docs** — a code trace with `file:line` at each step, a "What Gets Updated" table, a
     "What does NOT get updated" section (where bugs hide), and verification queries.
   - **Gotcha docs** — location in code, severity, impact, detection, workaround, cross-references.
   - **All docs** — every sentence should pass the "would reading the code tell you this?" filter. If a
     section just restates what the code does without adding insight about *why it matters* or *what
     goes wrong*, cut it.
4. Cross-reference related docs with `[[doc-name]]` wiki-style links.

> **Don't fabricate `file:line` references.** The standards above ask for `file:line` traces because
> they make a doc verifiable. But when your knowledge comes from the *conversation* rather than from
> reading the code, you often won't have exact line numbers — and inventing them is worse than omitting
> them. Cite what you genuinely know (the function or flow name, the file if you actually saw it) and
> leave the rest. If a learning is procedurally shaped (it wants to be a runbook) but you lack the code
> trace a runbook needs, write the **gotcha or concept** that captures the insight now, and park the
> runbook under a **Planned** entry in `INDEX.md` noting what trace detail is still needed. Don't pad a
> runbook with guessed line numbers.

> **Header format follows the repo's conventions, not these templates.** The `docs/README.md` you read
> in the prerequisites is authoritative for header fields and formatting; the bundled templates are just
> a reasonable default. Match the header style of the docs already in *this* KB so new docs stay
> consistent with what's there.

**Updating an existing doc:**

1. Read the current doc and its `Last verified` / `Commit` header.
2. Add the new content in the right section — don't reorganize existing content unless it's wrong.
3. Bump the `Last verified` date and commit hash in the header.
4. Update status if it changed (Stub → Seed → Written).

### Step 4: Update the INDEX

After any create/update, sync `docs/INDEX.md`:
- **New doc** — add a row to the right table (Concepts / Runbooks / Gotchas).
- **Status change** — update the Status column.
- **Scope change** — revise the Description column if the doc grew.

### Step 5: Confirm

Tell the user what changed:

```
KB updated:
  - Created concepts/<name>.md (Seed) — <summary>
  - Created gotchas/<name>.md — <summary>
  - Updated INDEX.md — added new entries

Files changed: <n>
```

---

## Mode B: Bootstrap a new KB

Use this when Step 0 found no KB, or the user asked to set one up. Bootstrapping is rare (once per
repo), so it's a mode here rather than a separate skill.

### Step B1: Confirm intent and detect the service name

Bootstrapping creates files at the repo root — confirm before writing. First detect a sensible service
name for the README header, in this order:
- `SLS_SERVICE_NAME` in a `.env` file, or `service:` in `serverless.yml`
- otherwise the git repo name (`basename` of the repo root) or the directory name

Tell the user what you'll create and where, and let them correct the name/path:

```
No knowledge base found in this repo. I can bootstrap one:

  docs/
    README.md      — quality standards + conventions + scope (seeded, you fill the scope boundary)
    INDEX.md       — empty index with Concepts / Runbooks / Gotchas tables
    concepts/      runbooks/      gotchas/

Service name detected: <name>   (override if wrong)
Create it? (yes / adjust)
```

### Step B2: Scaffold

After confirmation:
1. Read `assets/kb-readme-template.md`, fill in the service name and a one-line service description,
   and write it to `docs/README.md`. Leave the **Scope Boundary** for the user — fill what you can from
   context and flag it as needing their review.
2. Read `assets/kb-index-template.md` and write it to `docs/INDEX.md` (empty tables).
3. Create the three directories. Git won't track empty dirs, so drop a `.gitkeep` in each
   (`concepts/.gitkeep`, `runbooks/.gitkeep`, `gotchas/.gitkeep`). Delete a directory's `.gitkeep` as
   soon as it gets its first real doc — including the one you seed next in Step B3.

### Step B3: Seed the first content

A fresh KB is only useful once it has content. If the current conversation already uncovered
KB-worthy knowledge, immediately continue into **Mode A from Step 1** to add the first docs. If there's
nothing to add yet, say so — the empty KB is ready for next time.

---

## What NOT to add to the KB

This KB is shared across the team. Every line must earn its place; if it doesn't save someone hours, it
is noise that will rot.

**Never add:**
- **Table schemas** — no Column/Type/Description grids, ever. The model file is the source of truth. A
  one-line prose mention (composite PK `(a, b)`, model: `models.py:31`) is the maximum.
- **Function signatures or parameter lists** — read the code.
- **What a route/endpoint does** — readable from routes + controller.
- **Import relationships** — readable from the code.
- **JSON field inventories** — include a JSON example only when the nesting/naming is non-obvious and
  can't be inferred from the code that builds it.
- **Ephemeral task context** — that belongs in a work log, not the KB.

**The test, again:** before writing any section, ask "would the reader discover this within 10 minutes
of reading the relevant source file?" If yes, don't write it.

**What DOES belong:** cross-service interactions, silent failures, things that don't update when you'd
expect, ordering constraints, cross-DB coordination, gotchas that cost real debugging time.

## Diagrams

Include a diagram (Mermaid or ASCII) only when it shows relationships that **span multiple files or
databases** and can't be understood from any single source file (e.g. a cross-DB ER diagram). Don't add
diagrams that just restate one model file's relationships.

If a new doc introduces cross-DB tables not yet in an existing ER diagram, mention this to the user but
do NOT auto-update diagrams — suggest which diagram file to update and what to add.
