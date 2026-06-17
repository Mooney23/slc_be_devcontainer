---
name: notes-recall
description: >-
  Looks up project context (status, plans, recent work, decisions) by searching the user's Obsidian notes vault at `notes/` BEFORE scanning the repo. Use whenever the user says "let's continue work on X", "let's continue with X", "let's start with X", "let's pick up where we left off", "where are we with X", "where did we leave off on X", "what's the status of X", "what was the last action on X", "what do my notes say about X", "find X in my notes", or any other phrasing that signals they want to resume or recall context on a project, ticket, service, or topic. CRITICAL: do not launch `grep -r` across the repo, `find` from the workspace root, or an Explore subagent on the codebase as your first move — the user has repeatedly been burned by expensive repo-wide scans when the answer was sitting in their notes vault. Search the notes vault first; only fall back to the repo after asking the user. Use this skill aggressively even when the user doesn't explicitly mention notes.
---

# notes-recall

Look up project context from the user's Obsidian notes vault at `notes/` (mounted into the devcontainer at `/workspace/notes`). The vault is the user's authoritative store for project plans, status, decisions, and historical context. **Search it first. Then stop.**

## The cardinal rule

The repo is large and noisy; the notes vault is small and authoritative for project context. The user has flagged repo-wide scanning as a real pain point — it costs them time and tokens when the answer was already in their notes.

So: **no `grep -r` across the repo, no `find .` from the workspace root, no Explore subagent on the codebase as your first move.** Search the notes vault. If after going through the search ladder below you genuinely have nothing useful, say so out loud and ask before pivoting to a repo scan: *"Nothing in your notes about <X> — want me to grep the repo, or do you remember a different name for it?"* The user often remembers the exact file/topic name they used and that's faster than a scan.

## Where the vault lives

Paths in this skill are relative to the workspace root. The vault is mounted at `notes/`. If `notes/` isn't reachable from the CWD, check `$NOTES_PATH`; if neither resolves, tell the user the vault isn't reachable and stop.

## Vault layout

```
notes/
├── 01_Logs/YYYY/MM_MonthName/YYYY-MM-DD.md   # daily logs
├── 02_Meetings/                              # one note per sync
├── 03_People/                                # one note per teammate
├── 04_Services/                              # one note per service
├── 06_Weekly/                                # weekly summaries
├── 07_Memory/                                # memories captured by `notes-remember`
├── current_tasks.md                          # the user's "command center"
├── <PROJECT>.md                              # top-level project files (e.g. PROJ-205-report-csv-refactor.md)
└── <subdir>/                                 # ad-hoc topic dirs (e.g. pipeline-knowledge-base/)
```

## Identify the subject

Pull the subject from the user's message — usually a Jira ticket, project name, service name, or feature name. Keep two forms:
- **Slug** for filename matching: Jira tickets uppercase as-is (`PROJ-205`); free-text lowercase hyphen-separated (`monorepo restructure` → `monorepo-restructure`).
- **Original phrasing** for content greps (case-insensitive).

## Search ladder

Run these in order. **Stop as soon as you have enough to answer the user's question** — you don't need to exhaust every step.

1. **Memory file (exact filename match)** — `ls notes/07_Memory/<slug>.md`. If present, read it. Newest date header at the top is usually what the user wants.

2. **Top-level project files** — `ls notes/*.md`, look for filenames containing the subject as a substring (case-insensitive). The user files project plans at the vault root like `PROJ-205-report-csv-refactor.md`, `monorepo-restructure-plan.md`, `PROJ-198-data-export-update.md`. Read matches.

3. **`current_tasks.md`** — `grep -n -i "<subject>" notes/current_tasks.md`. The command center; active projects usually have a section here.

4. **Service notes** — `ls notes/04_Services/` and check for subject matches.

5. **Recent daily logs (last ~14 days only)** — don't scan all logs ever written; just the recent window:
   ```bash
   for i in $(seq 0 13); do
     d=$(date -d "today - $i days" +%Y-%m-%d 2>/dev/null || date -v-${i}d +%Y-%m-%d)
     y=$(echo $d | cut -c1-4); m=$(echo $d | cut -c6-7)
     ls "notes/01_Logs/$y/${m}_"*/"$d.md" 2>/dev/null
   done | xargs grep -l -i "<subject>" 2>/dev/null
   ```
   Read matches.

6. **Subdirectories** — `ls notes/` for ad-hoc dirs (e.g., `pipeline-knowledge-base/`). `grep -r -l -i "<subject>" notes/<subdir>/` is fine because subdirs are bounded.

7. **Fallback** — if all of the above turn up nothing, **tell the user and ask before scanning the repo or running anything wider**. Do not silently pivot.

## Presenting what you found

Synthesize, don't dump. The user asked "where are we with X" — give them the answer, not a file paste.

Format like:

> **PROJ-205 — report csv refactor**
> Last touched: 2026-05-18 (daily log mentions PR #120 merged for test infra)
> Plan: `notes/PROJ-205-report-csv-refactor.md` — switching to streaming chunks, default 10k rows
> Open items (from `current_tasks.md`): re-test the export endpoint after the storage migration

Cite file paths so the user can jump to them in Obsidian. Use `file_path:line_number` form when pointing at a specific line.

If you find stale or conflicting info across multiple files (one says "in progress", another says "done"), surface the conflict — don't pick a side silently.

## Costs and budget

Reading the vault should be cheap: a handful of `ls`, one or two targeted `grep`s, and 1–3 `Read` calls on matching files. If you find yourself spawning an Explore subagent, running `grep -r` across the whole vault, or reading a dozen daily logs, stop — you're probably searching wrong. Re-check the ladder.

The user explicitly flagged repo-wide scanning as expensive and slow. Honor that.

## Edge cases

- **No match on the slug, but partial matches in filenames**: present the top 2–3 candidate paths and let the user pick rather than guessing.
- **Vault not mounted**: if `notes/` doesn't exist and `$NOTES_PATH` isn't set, the user is probably running outside the devcontainer. Tell them and stop.
- **Subject is genuinely ambiguous**: ask one short clarifying question — e.g., *"`PROJ-205` shows up in both `07_Memory/PROJ-205.md` and `PROJ-205-report-csv-refactor.md`. Pull from both, or just one?"*

## Related

`notes-remember` writes new memories into `07_Memory/<topic>.md`, which this skill reads in step 1 of the search ladder.

