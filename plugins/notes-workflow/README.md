# Personal Work Notes — Claude's Memory for Personal Knowledge

This vault is **Claude's persistent memory for your personal working knowledge** — the
cross-cutting, time-based context that spans every ticket and service you touch: what you're
doing, where you left off, who you're waiting on, and the facts and decisions you want to
remember. It belongs to *you*, not to any one codebase.

The approach balances the messy reality of technical work — captured continuously in a
**Daily Log** (the "sensor") — against a single clean **command center** (`current_tasks.md`)
that always tells you what's next.

A set of Claude Code skills automates the lifecycle so the vault stays current without manual
bookkeeping. Trigger each one with its slash command or just describe what you want in plain
language.

> Claude Code reads and writes the vault directly — no copying or syncing. In the dev container
> it's mounted at `/workspace/notes` and found automatically; on the host you point the skills at
> it yourself (see **Setup** below).

## Setup

In the **dev container**, the vault is mounted at `/workspace/notes` and the skills find it automatically — nothing to configure. Running Claude Code on the **host** (no container), do these two one-time steps.

### 1. Point the skills at your vault

The skills locate the vault as **`$NOTES_PATH` → a `notes/` directory under the workspace → otherwise they ask you.** On the host there's no mounted `notes/`, so set `NOTES_PATH` to your vault's absolute path in your shell profile (`~/.bashrc`, `~/.zshrc`, …):

```bash
export NOTES_PATH="$HOME/path/to/your-notes-vault"
```

Without it, the skills fall back to asking where the vault is on every run.

### 2. Teach the agent your memory conventions

Two behaviors need to hold in *every* session, so they belong in your **user-scope** `~/.claude/CLAUDE.md` (loaded automatically each session) rather than in the skills: **search the vault first** on recall questions, and **route each captured fact** to the right store (the same personal-vs-project split described below, in instruction form). Add these two sections to `~/.claude/CLAUDE.md`:

````markdown
## Notes vault is authoritative for project context

For any recall/status/resume question about a project, ticket, or topic, search the Obsidian notes vault before doing any repo-wide search.

**Locating the vault:** use `$NOTES_PATH` if set; otherwise a `notes/` directory under the workspace (in a devcontainer, `/workspace/notes`); otherwise ask — don't guess or scan.

The vault contains:
- Top-level project files (e.g., `SLC-12104-recovery-csv-refactor.md`)
- `current_tasks.md` — the command center
- `06_Memory/<topic>.md` — memories captured by the `notes-remember` skill
- `01_Logs/YYYY/MM_MonthName/YYYY-MM-DD.md` — daily logs

**Why:** repo-wide scans (`grep -r`, `find .`, an Explore subagent on the codebase) are slow and token-expensive, and the answer is usually already sitting in the small, structured vault.

**How to apply:** the `notes-recall` skill encodes the search ladder and triggers on most recall-shaped phrasings. Even when it doesn't fire, prefer a cheap targeted search over a wide scan; if the notes don't have it, say so and ask before pivoting to a repo scan.

## Memory routing: where a captured fact belongs

The auto-memory remembers the **collaborator**; the vault's `06_Memory/` remembers the **work**. Before saving any fact, apply one test: *would a brand-new session on an unrelated task tomorrow still need it?*

- **Task-independent** — who you are, how you want Claude to work, or a resource that always matters → **auto-memory** (`~/.claude/.../memory/`; types `user` / `feedback` / `reference`). It loads every session, so keep it tiny.
- **Task-scoped** — a ticket / service / feature fact (a bug, a decision, a gotcha, a `file:line`) → **vault `06_Memory/<topic>.md`** via the `notes-remember` skill.
- **Team-facing, single-service** behaviour or decisions → that service repo's `docs/` (`update-kb`) or `docs/adr/` (ADRs) — not memory.
- **Cross-cutting across services** (no single repo owns it) → the vault, published out by hand (e.g. Confluence).

**Why:** the auto-memory and `06_Memory/` are both "remembered facts," so without a clear line they duplicate and drift. Splitting on task-independence gives each fact one home, and matches how each is retrieved — auto-memory is always loaded; `06_Memory/` is fetched on demand by `notes-recall`.

**How to apply:** never put a work/project fact in the auto-memory — it belongs in `06_Memory/`. The auto-memory may carry a one-line `reference` pointer to a `06_Memory/` topic when Claude should be reminded it exists, but never a copy of the content.
````

## Personal memory vs. project memory

This vault is for **personal** knowledge. Durable knowledge about a *specific service* — the
kind the whole team relies on — lives in that service's own repo under `docs/`, maintained by
two separate skills, so the two never compete for the same facts:

| Memory | Lives in | Maintained by | Holds |
|---|---|---|---|
| **Personal** (this vault) | the notes vault | the notes-workflow skills below | your cross-cutting working context — logs, tasks, weekly recaps, meetings, people, and topic memories under `06_Memory/` |
| **Project — behaviour** | a service repo's `docs/` | `update-kb` | how *that* service behaves: concepts, runbooks, and gotchas you can't recover from the code |
| **Project — decisions** | a service repo's `docs/adr/` | `architecture-decision-records` | the *why* behind a service's architecture (ADRs) |

**Rule of thumb — go by ownership:**
- *How one service behaves, and the team needs it* → that **service's** KB / ADR log, in its repo.
- *Spans multiple services, so no single repo owns it* (e.g. a pipeline that crosses services) → **this vault**, then published by hand to the shared destination (e.g. Confluence).
- *Your own working context, or a cross-project fact you want Claude to remember* → **this vault**.

## Vault structure

Kept deliberately minimal so it stays easy to scan (and cheap to index):

| Path | What it holds |
|---|---|
| `01_Logs/YYYY/MM_MonthName/YYYY-MM-DD.md` | Daily logs — the "sensor" for errors, snippets, and progress. |
| `02_Meetings/` | One note per sync — decisions and action items. |
| `03_People/` | One note per teammate — 1-on-1s and what you're waiting on. |
| `04_Templates/` | Standard layouts for logs and service notes. |
| `05_Weekly/` | Weekly summaries rolled up from the daily logs. |
| `06_Memory/` | Topic-scoped **personal** memories (`<topic>.md`) — facts, decisions, and gotchas *you* want Claude to recall later. |
| `Archive/` | Finished projects, moved out of the active workspace. |
| `current_tasks.md` | The "command center" at the vault root — the one file that tells you what's next. |

Top-level `<PROJECT>.md` files (e.g. `SLC-12104-recovery-csv-refactor.md`) hold per-ticket /
per-topic working notes.

## The daily workflow

**Morning (pilot).** Open `current_tasks.md`, pick the top 1–3 tasks, and for anything complex
link out to a dedicated note (e.g. `[[SLC-12104-recovery-csv-refactor]]`) to keep the dashboard
clean.

**All day (sensor).** Keep today's Daily Log open and capture live: commands and outputs, error
codes and the fixes you tried, PR / doc links, and "aha" moments. A new task surfaces
mid-meeting? Drop a `- [ ]` into the log immediately. Hit a bug you've seen before? Have Claude
recall it from your notes (see `notes-recall`) instead of re-debugging from scratch.

**Evening (prune).** Review the log, consolidate what's done, migrate unfinished `- [ ]` items to
`current_tasks.md`, and strip the noise so only the signal remains for later recall.

**End of week.** Roll the week's daily logs into a single summary in `05_Weekly/`.

## The skills

### `create-daily-note` — start your day
Creates today's note from the daily-note template with the dates filled in, creating the
`YYYY/MM_MonthName/` subdirectories if they don't exist yet. Won't overwrite an existing note.
**Triggers:** "start my day", "create today's log", "daily note", "new log entry".

### `update-daily-note` — log a session
Appends a terse summary of the current session to today's note, drawn from conversation context,
git activity, and errors hit. Populates **Work Stream** (raw technical log), **Done Today**
(`- [x]`), **To Carry Forward** (`- [ ]`), and suggested **Top Priorities**. Append-only — never
edits or removes existing content; creates today's note first if it's missing.
**Triggers:** "update my daily note", "log my session", "wrap up", "save my progress", "I'm done
for now".

### `cleanup-daily-note` — evening prune
End-of-day tidy of today's note: consolidates completed items into Done Today, migrates unfinished
`- [ ]` items into `current_tasks.md`, flags noise in Work Stream for your review *before* removing
anything, and checks off the Evening Prune list.
**Triggers:** "cleanup my daily note", "evening cleanup", "prune my notes", "end of day cleanup".

### `weekly-summary` — end-of-week rollup
Reads the most recent **completed** Mon–Sun daily logs, extracts meetings and completed work,
condenses them into a short note, and saves it to `05_Weekly/`. Always targets the last finished
week, never the one still in progress.
**Triggers:** "summarize the week", "weekly update", "what did we do this week", "it's Friday,
let's recap".

### `notes-recall` — recall project context
Looks up status, plans, decisions, and recent work by searching the vault **first**, before any
repo scan — the vault is small and authoritative for project context, while repo-wide scans are
slow and noisy. Searches the daily logs, `06_Memory/`, and project files; only falls back to the
repo after checking with you.
**Triggers:** "where are we with X", "what's the status of X", "let's continue work on X", "what
do my notes say about X".

### `notes-remember` — capture a memory
Saves a fact worth keeping beyond the session into a topic-scoped `06_Memory/<topic>.md` (keyed by
Jira ticket, project, service, or feature), under a dated header. Pairs with `notes-recall`, which
reads the same files back.
**Triggers:** "remember that…", "save this", "note that…", "don't forget", "file this under X".

## Optional: local indexing

The vault is plain markdown, so you can also point a local tool at it — Obsidian's Smart
Connections, or a local model via Ollama — for offline semantic search. That's entirely optional;
the skills above are the primary interface.
