---
name: architecture-decision-records
description: >-
  Capture architectural decisions made during coding sessions as structured ADRs (Architecture Decision
  Records, Nygard format) under `docs/adr/`. Records the context, the alternatives considered, the
  rationale, and the consequences — the *why* behind the codebase that you can never recover by reading
  the code. Use whenever a significant technical choice is made or discussed: picking a
  framework/library/database/queue, choosing an architecture / API / data-modeling pattern, settling an
  auth, deployment, or testing strategy. Triggers on "record this decision", "ADR this", "we decided to
  use X instead of Y", "the reason we're doing X is…", and on "why did we choose X?" (reads existing
  ADRs). Also bootstraps an ADR log if the repo has none ("start recording decisions here"). Works in
  any backend (Python / DB) service repo. Suggest recording an ADR proactively when a real trade-off is
  settled that would otherwise be lost — but never write one without confirmation.
metadata:
  origin: ECC (adapted for backend Python/DB services; aligned with the update-kb skill)
---

# Architecture Decision Records

Capture architectural decisions as they happen. Instead of a decision living only in a PR comment, a
Slack thread, or someone's memory, this skill produces a structured ADR that lives in the repo so a
future engineer can see *why* the codebase is shaped the way it is.

ADRs are the **decision** half of the docs; the behavioural knowledge base (concepts / runbooks /
gotchas, maintained by the `update-kb` skill) is the **behaviour** half. They are different artifacts
with different lifecycles — see [Relationship to the behavioural KB](#relationship-to-the-behavioural-kb)
— but they live under the same `docs/` root and reference each other.

## When to activate

- The user explicitly says "let's record this decision", "ADR this", or "why did we choose X?"
- A choice is being made between significant alternatives — framework, library, database, queue,
  pattern, API shape, auth/deployment/testing strategy.
- The user says "we decided to…" or "the reason we're doing X instead of Y is…".
- During planning, when architectural trade-offs are weighed.

When you only *detect* a decision (rather than being asked), **suggest** recording an ADR — don't create
one unprompted. See [Decision detection signals](#decision-detection-signals).

## ADR format

The lightweight ADR format (Michael Nygard), adapted for AI-assisted development. Write in the **present
tense** ("We use X", not "We will use X"):

```markdown
# ADR-NNNN: [Decision Title]

**Date**: YYYY-MM-DD
**Status**: proposed | accepted | deprecated | superseded by ADR-NNNN
**Deciders**: [who was involved — often just the user + Claude; keep it short]

## Context

What is the issue motivating this decision or change?
[2-5 sentences on the situation, constraints, and forces at play.]

## Decision

What are we doing?
[1-3 sentences stating the decision clearly.]

## Alternatives Considered

### Alternative 1: [Name]
- **Pros**: [benefits]
- **Cons**: [drawbacks]
- **Why not**: [the specific reason it was rejected]

### Alternative 2: [Name]
- **Pros**: [benefits]
- **Cons**: [drawbacks]
- **Why not**: [the specific reason it was rejected]

## Consequences

What becomes easier or harder because of this change?

### Positive
- [benefit]

### Negative
- [trade-off]

### Risks
- [risk and its mitigation]
```

## Where ADRs live

```
docs/
  README.md  INDEX.md  concepts/  runbooks/  gotchas/   ← the behavioural KB (update-kb skill)
  adr/                                                   ← this skill
    README.md          ← index of all ADRs
    template.md        ← blank template for manual use
    0001-use-sqs-for-ingest-decoupling.md
    0002-separate-global-and-local-databases.md
```

ADRs sit at `docs/adr/`, under the same `docs/` root as the behavioural KB, so all literal
documentation lives in one tree. Files are numbered `NNNN-kebab-title.md`, zero-padded to four digits.

## Workflow

### Capturing a new ADR

1. **Initialize (first time only).** If `docs/adr/` doesn't exist, this repo has no ADR log yet. Tell
   the user what you'll create and get explicit confirmation before writing anything — bootstrapping is
   a one-time, rare action:

   ```
   No ADR log found. I can start one under docs/adr/:
     docs/adr/
       README.md      — index table (seeded)
       template.md    — blank ADR template for manual use
   Create it? (yes / adjust)
   ```

   On confirmation, read `assets/adr-index-template.md` → write `docs/adr/README.md`, and read
   `assets/adr-template.md` → write `docs/adr/template.md`. (The template's base path is shown to you
   when this skill loads — don't hardcode an absolute path; it differs between a baked install and a
   project install.) If a stray `docs/adr/` exists, read what's there and report it before touching
   anything.
2. **Identify the decision** — the core architectural choice being made.
3. **Gather context** — what problem prompted it, what constraints apply.
4. **Document alternatives** — what else was considered, and the *specific* reason each was rejected.
   "We just picked it" is not a rationale; if there genuinely were no alternatives, say so explicitly.
5. **State consequences** — the honest trade-offs: what gets easier, what gets harder, what's risky.
6. **Assign a number** — scan existing files in `docs/adr/` and increment to the next `NNNN`. Derive a
   short kebab-case slug from the title for the filename (`NNNN-short-slug.md`).
7. **Confirm and write** — present the drafted ADR for review. Only write
   `docs/adr/NNNN-decision-title.md` after explicit approval. If the user declines, discard the draft —
   write nothing.
8. **Update the index** — add a row to `docs/adr/README.md`. When it's the first real entry, replace
   the seeded `_none yet_` placeholder row rather than leaving it. When this ADR supersedes an older
   one, also flip that older entry's Status here (and in the old ADR file) to `superseded by ADR-NNNN`.
9. **Cross-link** — if this decision explains a behaviour documented in the KB (a gotcha or concept),
   add a link both ways (see [Relationship to the behavioural KB](#relationship-to-the-behavioural-kb)).

### Reading existing ADRs

When the user asks "why did we choose X?":

1. If `docs/adr/` doesn't exist → "No ADRs recorded in this project. Want to start an ADR log?"
2. Scan `docs/adr/README.md` for relevant entries.
3. Read the matching ADR(s) and present the **Context** and **Decision** sections (that's the answer to
   "why"); mention superseding ADRs if the status points to one.
4. No match → "No ADR found for that decision. Want to record one now?"

### ADR index format

```markdown
# Architecture Decision Records

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0001](0001-use-sqs-for-ingest-decoupling.md) | Use SQS to decouple ingest from processing | accepted | 2026-01-15 |
| [0002](0002-separate-global-and-local-databases.md) | Separate global and per-tenant local databases | accepted | 2026-01-20 |
```

## Decision detection signals

Patterns that indicate an architectural decision is happening:

**Explicit** (the user is asking for it): "let's go with X", "we should use X instead of Y", "the
trade-off is worth it because…", "record this as an ADR".

**Implicit** (suggest recording — do NOT auto-create without confirmation): comparing two
libraries/approaches and reaching a conclusion; a schema or data-modeling choice with stated rationale;
choosing between patterns (sync vs async processing, monolith vs service split, polling vs
event-driven); deciding an auth/authorization approach; selecting infrastructure after weighing options.

## What makes a good ADR

**Do:**
- **Be specific** — "Use SQLAlchemy Core for the ingest path", not "use an ORM".
- **Record the why** — the rationale matters more than the what.
- **Include rejected alternatives** — future engineers need to know what was considered.
- **State consequences honestly** — every decision has trade-offs.
- **Keep it short** — readable in ~2 minutes. If Context exceeds ~10 lines, it's too long.

**Don't:**
- Record trivial decisions — naming, formatting, a one-off helper choice.
- Write essays.
- Omit alternatives — "we just picked it" isn't a rationale.
- Backfill silently — when recording a past decision, note the original date in Context.
- Let ADRs go stale — a superseded decision must link its replacement.

## ADR lifecycle

```
proposed → accepted → [deprecated | superseded by ADR-NNNN]
```

- **proposed** — under discussion, not yet committed.
- **accepted** — in effect and being followed.
- **deprecated** — no longer relevant (e.g. the feature was removed).
- **superseded** — a newer ADR replaces it; always link the replacement.

**Which status to record at:** match reality. Most ADRs are captured *after* a decision is settled, so
they start at **accepted** — that's the common case. Use **proposed** only when the decision is
genuinely still open and you're recording it to frame the discussion. A superseding ADR is **accepted**
(a proposal can't supersede an in-effect decision).

**ADRs are immutable once accepted.** This is the key difference from KB docs, which you edit in place.
Don't rewrite an accepted ADR's Context or Decision when the situation changes — instead write a **new**
ADR and mark the old one `superseded by ADR-NNNN`. The log is a history of *what was decided when*, not
a description of the current state; rewriting it destroys the record. (Fixing a typo is fine.)

## Categories of decisions worth recording

| Category | Examples (backend) |
|----------|--------------------|
| **Technology choices** | language/runtime, database engine, message queue, cloud service |
| **Architecture patterns** | service split vs monolith, event-driven vs polling, sync vs async, CQRS |
| **API design** | REST vs RPC, versioning strategy, pagination, idempotency, auth mechanism |
| **Data modeling** | schema design, normalization, partitioning/sharding, multi-DB split, caching |
| **Infrastructure** | deployment model (Lambda vs container), CI/CD, IaC tool, monitoring/alerting |
| **Security** | authn/authz strategy, encryption, secret management, tenant isolation |
| **Testing** | framework, coverage targets, E2E vs integration balance, fixtures/mocking strategy |
| **Process** | branching strategy, review process, release cadence |

## Relationship to the behavioural KB

The `update-kb` skill maintains the behavioural KB (`docs/concepts/`, `docs/runbooks/`, `docs/gotchas/`);
this skill maintains the decision log (`docs/adr/`). They are complementary:

| | Behavioural KB (`update-kb`) | ADR (this skill) |
|---|---|---|
| Captures | how the system *behaves* | *why* it was built this way |
| Lifecycle | living — edited in place | immutable — superseded, never rewritten |
| Test for inclusion | "would reading the code tell you this?" | always passes — rationale & rejected options aren't in the code |

**Cross-link them.** A behaviour often exists *because* of a decision. When an ADR explains something
the KB documents, link both ways:
- From the ADR's Consequences/Context → the KB doc, e.g. `See [[../gotchas/orphaned-rows-on-delete]]`.
- From the KB doc's Related section → the ADR, e.g. `[[../adr/0002-separate-global-and-local-databases]]
  — why there's no FK to enforce this`.

This is where the two together beat either alone: the gotcha tells you *what bites*, the ADR tells you
*why it's that way and what the alternative would have cost*.

When you record an ADR for a design the KB already describes (or vice versa), suggest adding the
cross-link — but, as always, don't edit the KB without the user's go-ahead.
