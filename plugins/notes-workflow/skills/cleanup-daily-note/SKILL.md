---
name: cleanup-daily-note
description: Performs evening cleanup on the daily Obsidian work log — moves unfinished tasks to current_tasks.md, consolidates completed items into Done Today, and flags noise for deletion while preserving signals. Use this skill whenever the user wants to clean up their daily note, do an evening prune, end their day, tidy their log, or review what to keep vs discard. Triggers on phrases like "cleanup my daily note", "evening cleanup", "prune my notes", "end of day cleanup", "tidy my log", "clean up today's note", or any request to organize and prune the daily work log.
---

# Cleanup Daily Note

Perform an evening cleanup on today's daily note at `notes/01_Logs/YYYY/MM_MonthName/YYYY-MM-DD.md`. This is the "signal vs noise" pass — consolidating completed work, migrating unfinished tasks, and flagging clutter for the user to review.

## Prerequisites

Check if today's daily note exists by running `ls notes/01_Logs/YYYY/MM_MonthName/YYYY-MM-DD.md` via Bash (e.g., `ls notes/01_Logs/2026/03_March/2026-03-21.md`). Do NOT use the Glob tool for this check — it may not find files in mounted/external directories. If the file doesn't exist (ls returns an error), inform the user and stop — there's nothing to clean up.

Also check that `notes/current_tasks.md` exists by running `ls notes/current_tasks.md` via Bash. If it doesn't, create it with a simple header:

```markdown
# Current Tasks

```

## Step 1: Move unfinished tasks to current_tasks.md

Scan the entire daily note for unchecked checkboxes (`- [ ]`). For each one found:

1. Append it to `notes/current_tasks.md`.
2. Delete it from the daily note.

This ensures nothing falls through the cracks overnight. The daily note is a snapshot of one day — open tasks belong in the persistent `current_tasks.md` file.

Items prefixed with `(suggested)` should be moved too — they were suggested during the session and haven't been acted on yet, so they're still open tasks.

## Step 2: Consolidate completed items into Done Today

Move checked checkboxes (`- [x]`) from these specific sections into the `## ✅ Done Today` section:

- **Top Priorities** (`## 🎯 Top Priorities`) — move `- [x]` items to Done Today, delete from Top Priorities
- **Carry Forward** (`## ⏭ To Carry Forward`) — move `- [x]` items to Done Today, delete from Carry Forward
- **current_tasks.md** (`notes/current_tasks.md`) — move `- [x]` items to Done Today in the daily note, delete from current_tasks.md

Do **not** move checked items from Work Stream (`## 🛠 Work Stream`). That section is a raw technical log and its checked items are part of the narrative record.

When adding items to Done Today, append them after any existing content in that section (same append-only pattern as the update-daily-note skill).

## Step 3: Flag noise for user review

Read through the Work Stream section and identify content that matches the "noise" patterns below. Do not delete anything automatically — present a summary to the user and let them decide what to remove.

### What counts as noise

- **Failed experiments**: Multiple attempts where only the last one worked. Example: three broken `curl` commands before the fourth succeeded — the first three are noise.
- **Transitory logs**: Long stack traces or verbose terminal output. The error message and fix are signal; the bulk of the raw log is noise.
- **Administrative friction**: Notes like "Waiting for IT to reset my password" or "Slack was down for 10 minutes" — no future technical value.
- **Duplicate links**: The same URL or Jira ticket pasted multiple times.

### What counts as signal (keep these)

- **The "why"**: Reasoning behind decisions — "Switched to Library B because Library A doesn't support concurrency in Go 1.21."
- **Working snippets**: The exact SQL query, regex, or command that solved the problem.
- **Decision logic**: "Team decided to use Sidecar pattern for logging to reduce latency."
- **People references**: "Spoke to Sarah from DevOps; she's the lead for the K8s migration."

### How to present noise suggestions

Show the user a numbered list of items you think are noise, with brief reasoning:

```
I found a few items in Work Stream that look like noise:

1. Lines 24-27: Three failed curl commands before the working one on line 28 — keep only the working version?
2. Line 35: "Waiting for VPN to reconnect" — administrative friction, no technical value.
3. Lines 41-58: Full stack trace — the error message on line 41 and fix on line 60 capture the signal.

Want me to remove any of these? (e.g., "remove 1 and 2", "remove all", "skip")
```

Wait for the user's response before deleting anything. If the user says "skip" or doesn't want to remove anything, move on.

## Step 4: Check off the Evening Prune checklist

The daily note has an Evening Prune section (`## 🧹 Evening Prune`) with a checklist. As you complete each step, check off the corresponding item:

- `- [x] **Delete Noise**` — after the user confirms noise removal (or skips)
- `- [x] **Highlight Signals**` — after reviewing and preserving signals in Work Stream
- `- [x] **Task Migration**` — after moving unfinished tasks to `current_tasks.md`
- `- [x] **Link People/Services**` — check this off if people/service references were already linked, or note if any are missing

## Order of operations

Run the steps in this order to avoid conflicts:

1. Read both files (`notes/01_Logs/YYYY/MM_MonthName/YYYY-MM-DD.md` and `notes/current_tasks.md`) — use `ls` via Bash to verify existence first
2. Step 2 first — consolidate completed items (moves from current_tasks.md and daily note sections into Done Today)
3. Step 1 — move unfinished tasks to current_tasks.md
4. Step 3 — flag noise for review (interactive, waits for user)
5. Step 4 — check off Evening Prune items
6. Confirm to the user what was done

This order matters because Step 2 pulls completed items from current_tasks.md before Step 1 pushes new unfinished items into it — avoids accidentally moving items that were just added.

## Example workflow

```
Cleanup summary for 2026-03-17:

✅ Moved to Done Today (from Top Priorities, Carry Forward, current_tasks.md):
  - [x] PROJ-101: handle widgets with missing identifiers
  - [x] Review PR #44 feedback

📋 Moved to current_tasks.md (unfinished):
  - [ ] Write unit tests for widget_handler
  - [ ] (suggested) Add integration test for widget handling

🔍 Noise review:
  1. Lines 24-27: Three failed curl commands — keep only the working one?
  2. Line 35: "Waiting for VPN" — no technical value

Want me to remove any of these?
```
