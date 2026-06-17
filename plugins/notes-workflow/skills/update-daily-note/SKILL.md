---
name: update-daily-note
description: Appends a session summary to the daily Obsidian work log in notes/01_Logs/YYYY/MM_MonthName/. Use this skill whenever the user wants to update their daily note, log their session, wrap up their day, end a session, capture progress, or record what was done. Triggers on phrases like "update my daily note", "log my session", "wrap up", "end session", "update my log", "save my progress", "what did we do today", or any request to record the current session's work into the daily note. Also use when the user says something like "I'm done for now" or "let's close out".
---

# Update Daily Note

Append a terse summary of the current session's work to today's daily note at `notes/01_Logs/YYYY/MM_MonthName/YYYY-MM-DD.md` (e.g., `notes/01_Logs/2026/03_March/2026-03-21.md`).

## Prerequisite

Check if today's note exists by running `ls notes/01_Logs/YYYY/MM_MonthName/YYYY-MM-DD.md` via Bash. Do NOT use the Glob tool for this check — it may not find files in mounted/external directories. If the file does not exist (ls returns an error), invoke the `create-daily-note` skill first, then continue with the update.

## Gather session data

Pull from every available source to build a complete picture of the session:

1. **Conversation context** — review what was discussed, built, debugged, or decided in this session. This is your richest source.
2. **Git activity** — run:
   - `git log --since="midnight" --oneline` for today's commits
   - `git diff --stat` for uncommitted changes
   - `git branch --show-current` for branch context
3. **Errors and resolutions** — any errors encountered during the session and how they were resolved.

## What to write

Generate terse bullet points for these sections. Think commit messages, not prose. Include commit hashes, file paths, error codes, and PR/issue references where relevant.

### Work Stream (The "Sensor")

The raw technical log of the session. Capture:
- Commands run and their outcomes (especially non-obvious ones)
- Error codes and fixes attempted/applied
- Links to PRs, docs, or external resources referenced
- Key realizations or insights ("aha!" moments)
- Files and modules touched, with brief context

Format: `- <short description> — <context/detail>`

### Done Today

Items completed during this session, as checked-off checkboxes:
- `- [x] <what was completed>`

### To Carry Forward

Unfinished work or next steps surfaced during this session, as unchecked checkboxes:
- `- [ ] <what still needs doing>`

### Top Priorities (suggestions only)

If the session revealed clear priorities, suggest 1-2 items. Prefix with "(suggested)" so the user can tell these apart from items they wrote themselves:
- `- [ ] (suggested) <priority item>`

Do not touch **Meetings & Syncs** or **Evening Prune** — those are for the user to fill in.

## How to append

This document is shared between the user, this skill, and possibly other sessions throughout the day. Treat it as append-only:

1. Read the current file content.
2. For each section to update, locate the section header by its emoji prefix:
   - `## 🎯 Top Priorities`
   - `## 🛠 Work Stream`
   - `## ✅ Done Today`
   - `## ⏭ To Carry Forward`
3. Find the end of that section's content — the line just before the next `## ` header or `---` separator.
4. Insert your new bullet points at that position.
5. If the section already has content, add a blank line before your new entries to visually separate them from previous content.

Never modify, reorder, or remove existing lines. If the user wrote something in a section, your entries go after theirs. The user trusts that their edits will persist exactly as written.

## Example output

Here's what a session's additions might look like across the sections:

```
## 🎯 Top Priorities
- [ ] (suggested) Add unit tests for widget_handler.py

## 🛠 Work Stream (The "Sensor")
- Fixed null check in widget_handler.py — widget_id was None for empty payloads
- Debugged queue visibility timeout — batch size 10→1 (commit abc1234)
- Created create-daily-note skill — bundled note template with date placeholder replacement
- Ref: PR #42 for PROJ-101

## ✅ Done Today
- [x] PROJ-101: handle widgets with missing identifiers
- [x] Set up create-daily-note skill with template and tests

## ⏭ To Carry Forward (Evening Cleanup)
- [ ] Write unit tests for widget_handler
- [ ] Review PR #235 feedback
```
