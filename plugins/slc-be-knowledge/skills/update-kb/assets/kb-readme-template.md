# {{SERVICE_NAME}} Knowledge Base

> Last updated: {{DATE}}

A behavioural guide to {{SERVICE_DESCRIPTION}}. Focuses on operational knowledge that can't be easily derived from reading code or model files — gotchas, multi-step procedures, cross-DB coordination, and how things actually behave in practice.

## How to Use This KB

- **"What is X and how does it behave?"** — start in `concepts/`
- **"How do I do X?"** — start in `runbooks/`
- **"What will bite me?"** — check `gotchas/`
- **Full docs index:** [INDEX.md](INDEX.md)

Built incrementally. Each doc has a `Last verified` date and commit hash. If you find something outdated, update the doc or flag it.

## What Belongs Here (and What Doesn't)

Apply this test to every piece of content:

> If a competent engineer opened the relevant source file and spent 10 minutes reading it, would they learn this?

If **yes** — don't add it. If **no** — it belongs here.

**DO include:**
- Cross-service interactions and cross-DB coordination (no single file shows these)
- Silent failures and things that *don't* get updated when you'd expect them to
- Ordering constraints and multi-step procedures where the sequence matters
- Gotchas that cost someone real debugging time
- Behavioural quirks not obvious from reading any single source file

**NEVER include:**
- Table schemas (Column/Type/Description grids) — the model file is the source of truth. Maximum allowed: a one-line prose mention with composite PK and model path.
- Function signatures, parameter lists, or route definitions — readable from the code
- JSON field inventories — only include JSON examples when nesting/naming is non-obvious
- ER diagrams that restate a single model file's relationships — only include diagrams that show relationships spanning multiple files or databases
- Stub placeholders for unwritten docs

## Maintenance Guide

### Quality Standards

Every sentence should pass the "would reading the code tell you this?" filter. If a section is just restating what the code does without adding insight about *why* it matters or *what goes wrong*, cut it.

**Concept docs:** Behavioural explanations not obvious from code, cross-references. Use tables only when they show relationships, sequences, or mappings (e.g., "what triggers what", "deletion order", "cross-DB references") — never for listing columns.

**Runbook docs:** Code trace with file:line at every step, "What Gets Updated" table, "What does NOT get updated", verification queries.

**Gotcha docs:** Location in code, severity, impact, detection, workaround, cross-references to related runbooks.

### Conventions

- **File naming:** `kebab-case-name.md` (no number prefixes — INDEX.md provides ordering)
- **Headers:** `> Last verified: YYYY-MM-DD | Commit: HASH | Author: Name` and `> Sources: ...`
- **Cross-references:** `[[doc-name]]` for wiki-style links between KB docs
- **Code references:** Always include `file_path:line_number`
- **Status tracking:** Keep [INDEX.md](INDEX.md) in sync with actual doc status
- **No stubs:** Don't create placeholder files. Add planned topics to INDEX.md as a "Planned" section instead.

### Scope Boundary

<!-- FILL THIS IN: what this KB covers and, just as importantly, what it does NOT.
     e.g. "Covers CRUD operations, entity relationships, update flows, and cross-DB
     coordination for this service. Does NOT cover <adjacent system> beyond the
     handoff point documented in <doc>." -->
