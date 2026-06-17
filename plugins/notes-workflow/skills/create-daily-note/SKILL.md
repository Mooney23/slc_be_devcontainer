---
name: create-daily-note
description: Creates a daily Obsidian work log note in notes/01_Logs/YYYY/MM_MonthName/. Use this skill whenever the user wants to create a daily note, daily log, work log, start their day, or mentions anything about today's note or logging their work. Triggers on phrases like "daily note", "create today's log", "start my day", "work log", "daily log", "new log entry", or any request to create or open today's note.
---

# Daily Note Creator

Create today's daily work log note in `notes/01_Logs/YYYY/MM_MonthName/` using the bundled Obsidian template.

## Steps

1. Determine today's date.
2. Build the directory path: `notes/01_Logs/YYYY/MM_MonthName/` where `MM` is the zero-padded month number and `MonthName` is the full English month name (e.g., `notes/01_Logs/2026/03_March/`).
3. Build the filename: `YYYY-MM-DD.md` inside that directory (e.g., `notes/01_Logs/2026/03_March/2026-03-17.md`).
4. Check if the file already exists by running `ls notes/01_Logs/YYYY/MM_MonthName/YYYY-MM-DD.md` via Bash. Do NOT use the Glob tool for this check — it may not find files in mounted/external directories. If the file exists (ls succeeds), tell the user the note already exists for today and stop — do not overwrite it.
5. Create the year and month directories if they don't already exist (e.g., `mkdir -p notes/01_Logs/2026/03_March/`).
6. Read the template from `assets/daily-note-template.md` (relative to this skill's directory).
7. Replace the two date placeholders in the template:
   - `{{date:YYYY-MM-DD}}` → ISO date, e.g., `2026-03-17`
   - `{{date:dddd, MMMM Do, YYYY}}` → full human-readable date, e.g., `Tuesday, March 17th, 2026`
8. Write the rendered template to the file path from step 3.
9. Confirm to the user that the note was created.

## Date formatting details

The long-form date uses this format: **Weekday, Month Dayth, Year**

For the ordinal day suffix:
- 1st, 21st, 31st
- 2nd, 22nd
- 3rd, 23rd
- Everything else gets "th" (4th, 5th, ... 11th, 12th, 13th, ... 20th, 24th, etc.)

Note: 11th, 12th, and 13th are exceptions — they use "th", not "st"/"nd"/"rd".

## Important

- The top-level `notes/01_Logs/` directory is expected to already exist (mounted in the devcontainer). However, year and month subdirectories (e.g., `2026/03_March/`) should be created as needed.
- Never overwrite an existing note. If the file exists, just inform the user.
- Always use today's date. The user does not specify a date.
