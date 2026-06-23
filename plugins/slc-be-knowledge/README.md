# `slc-be-knowledge` — knowledge base & decisions

Skills for capturing and maintaining durable knowledge about a backend service — the operational
context and architectural rationale that you can't recover by re-reading the code. Both skills
are repo-agnostic and work in any backend Python/DB service repo.

## Skills

### `update-kb`

Captures hard-won behavioural knowledge about a service into its `docs/` knowledge base —
concepts, runbooks, and gotchas uncovered during debugging, tracing, or building. Also
bootstraps a KB from scratch if the repo has none yet.

### `architecture-decision-records`

Captures architectural decisions as structured ADRs (Nygard format) under `docs/adr/` —
the context, alternatives considered, rationale, and consequences behind significant technical
choices. Pairs with `update-kb`: ADRs record the *why*; the KB records the *behaviour*.
