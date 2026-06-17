---
name: weekly-summary
description: Generates a condensed weekly summary note from the previous Mon–Sun daily logs. Use this skill whenever the user wants to summarize the week, create a weekly update, generate a weekly note, wrap up the week, or review what happened this week. Triggers on phrases like "summarize the week", "weekly summary", "weekly update", "weekly note", "what did we do this week", "create a weekly recap", or any request to roll up the week's work into a summary. Also trigger when the user says something like "it's Friday, let's recap" or "end of week roundup".
---

# Weekly Summary Generator

Read the Mon–Sun daily logs for the most recent completed work week, extract meetings and completed work, condense it into a short weekly note, and save it to `notes/06_Weekly/`.

## Step 1: Determine the week range

- Today is available via the system date.
- The **target week** is always the most recent completed Mon–Sun period — i.e., the last full week that has already ended.
  - Find the most recent Sunday before today, then go back to the Monday of that same week.
  - Example: if today is Monday Mar 23, the target week is Mon Mar 16 – Sun Mar 22.
  - Example: if today is Wednesday Mar 25, the target week is still Mon Mar 16 – Sun Mar 22 (the last completed week).
  - Never include today or any day in the current (still-in-progress) week.
- Compute `week_start` (Monday) and `week_end` (Sunday) as ISO dates.

## Step 2: Collect daily note paths

For each calendar day from `week_start` to `week_end`:
1. Build the path: `notes/01_Logs/YYYY/NN_MonthName/YYYY-MM-DD.md`
   - `NN` = zero-padded month number (e.g., `03`)
   - `MonthName` = full English month name (e.g., `March`)
2. Check if the file exists — if not, skip it silently.
3. Read the file.

## Step 3: Extract sections

From each daily note, extract the content of three sections:
- `## 🛠 Work Stream (The "Sensor")` — read for context only
- `## 🤝 Meetings & Syncs`
- `## ✅ Done Today`

A section ends when the next `##` heading begins.

**Skip a day entirely if both Meetings and Done Today are empty** — "empty" means the section contains only blank lines, bare `-` bullets, or `- [ ]` / `- [x]` with no description text.

The Work Stream is background context: use it to understand the reasoning, root causes, and technical detail behind the Done Today items. Do not copy it directly into the summary — but do use it to write richer, more specific bullets (e.g., if Done Today says "fixed schema bug" and Work Stream explains it was `fields.Int` → `fields.Str` in `schema.py:126`, the summary bullet can include that specificity).

## Step 4: Synthesize a condensed summary

Write the weekly note body. The goal is brevity: someone should be able to read the entire note in under 2 minutes.

### Meetings section

List meetings grouped by day. For each day that had real meetings:
- One line per meeting: `- **Day Mon DD**: <concise description>`
- Include who was involved and what was decided/clarified, if present in the notes.
- Omit days with no meetings.

### Done This Week section

Condense the "Done Today" lists across all days into a tight grouped list:
- Merge related items (e.g., "Created server-start skill", "Created server-stop skill", "Created server-status skill" → "Created 3 Flask server lifecycle skills (start, stop, status)")
- Keep items that represent distinct outcomes or decisions — not process steps.
- Drop items that are purely administrative noise (e.g., "updated placeholder", "fixed typo").
- Aim for 5–10 bullets total, fewer if the week was light.

## Step 5: Write the output file

**Filename format:**
- Same month: `W{nn}_{MmmDD-DD}.md` (e.g., `W12_Mar16-22.md`)
- Spanning months: `W{nn}_{MmmDD-MmmDD}.md` (e.g., `W14_Mar31-Apr6.md`)
- `{nn}` is the ISO week number, zero-padded to 2 digits (e.g., `W01`, `W12`)
- Month abbreviations are 3-letter English (Jan, Feb, Mar, Apr, May, Jun, Jul, Aug, Sep, Oct, Nov, Dec)
- Day numbers have no zero-padding (e.g., `W12_Mar3-9.md`, not `W12_Mar03-09.md`)
- No spaces anywhere in the filename

**Computing the ISO week number:** ISO week 1 is the week containing the first Thursday of the year. Weeks start on Monday.

**File path:** `notes/06_Weekly/<filename>`

**File content:**

```markdown
---
type: weekly-summary
week_start: YYYY-MM-DD
week_end: YYYY-MM-DD
---
# Week of <Mon Abbr DD> – <Sun Abbr DD>, YYYY

## Meetings
- **<Day Abbr DD>**: <meeting summary>
...

## Done This Week
- <condensed bullet>
...
```

If there were no meetings at all that week, omit the Meetings section entirely.

## Step 6: Confirm to the user

Tell the user the file was created and give the path. Optionally note how many days had content and how many were skipped.

---

## Notes on judgment

The condensation step is where quality is made. Prefer grouping by theme or project rather than by day. For example:
- "Debugged `ble_sync_role` schema mismatch in `devices_info` endpoint and identified fix" is better than three separate bullets about reading the code, tracing the route, and identifying the root cause.
- "Migrated daily note skills to nested directory structure and validated with eval suite" is better than listing each skill individually.

When in doubt, keep the bullet that answers "what changed / what was decided" and drop the one that answers "what steps did I take".
