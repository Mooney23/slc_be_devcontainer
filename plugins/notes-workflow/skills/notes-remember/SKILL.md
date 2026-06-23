---
name: notes-remember
description: Captures something the user wants remembered into a topic-scoped file under `notes/06_Memory/<topic>.md` in the Obsidian notes vault. Use whenever the user says "remember", "remember that", "remember about <project>", "save this", "save this for later", "note that", "keep in mind", "don't forget", "file this under X", "jot this down", or otherwise signals they want a fact retained beyond this session. Don't be shy — if the user is telling you a fact they clearly want preserved across sessions (a config value, a gotcha, a decision, a file:line reference), file it even if "remember" wasn't the literal word. Pairs with `notes-recall` (recall reads from the same `06_Memory/` plus the rest of the notes vault).
---

# notes-remember

Capture a memory into the user's Obsidian notes vault at `notes/06_Memory/<topic>.md`. The user treats the vault as Claude's primary persistent memory store.

## Where the vault lives

Paths below are relative to the notes vault. Resolve it without assuming a devcontainer: use `$NOTES_PATH` if it's set, otherwise a `notes/` directory under the workspace (in a devcontainer that's `/workspace/notes`). Where a command below says `notes/`, that's the vault root — if `$NOTES_PATH` is set, use it instead. If neither resolves, tell the user the vault isn't reachable and stop — don't write to an arbitrary location.

## Steps

1. **Identify the topic.** In order of preference:
   - Explicit reference in the user's message ("remember about PROJ-205 that…" → topic is `PROJ-205`).
   - Jira ticket from the current branch (`git branch --show-current` — `feature/PROJ-210` → topic `PROJ-210`).
   - The file or module the conversation has been focused on (`widget_handler.py` → `widget-handler`).
   - If still ambiguous, ask once with a concrete proposal: *"Filing under `06_Memory/<your-guess>.md` — sound right, or pick a different topic?"* Don't ask twice.

2. **Slugify the topic** into a filename:
   - Jira tickets stay uppercase as-is: `PROJ-205` → `PROJ-205.md`.
   - Free-text: lowercase, hyphenate spaces/underscores, strip punctuation. `Monorepo restructure` → `monorepo-restructure.md`.

3. **Ensure the dir exists**: `mkdir -p notes/06_Memory` (idempotent).

4. **Check whether the file exists**: `ls notes/06_Memory/<slug>.md` via Bash. Don't use Glob — it can miss files in mounted directories.

5. **If the file does not exist**, create it with a top-level header:
   ```markdown
   # <Human-readable topic>

   ```
   E.g., `# PROJ-205` or `# Monorepo Restructure`.

6. **Insert the memory** under a date header at the **top** of the file (after the H1):
   - Today's date in ISO form: `YYYY-MM-DD`.
   - If `## YYYY-MM-DD` for today already exists, append the new bullet under it.
   - Otherwise insert a new `## YYYY-MM-DD` section directly after the H1, with the bullet under it.
   - Newest entries go at the top — this is rolling capture, not a chronological log, so latest context is the most useful when the user opens the file later.

7. **Confirm** to the user with the file path and a one-line preview. E.g., *"Saved to `notes/06_Memory/PROJ-205.md` — 'report csv refactor uses streaming chunks, 10k row default'."* Keep it short; the user is mid-flow.

## File format

```markdown
# PROJ-205

## 2026-05-20
- report csv refactor uses streaming chunks, default chunksize 10000
- null-as-fresh fix at handlers/widget_handler.py:147

## 2026-05-18
- lookup must drop the revision filter — query by ID only
```

One bullet per memory. Terse — think commit messages, not prose. Include file paths, line numbers, commit SHAs, PR/issue refs, exact commands when relevant. Those details are why the user is asking you to remember it — preserve them verbatim, don't paraphrase.

## What counts as a memory worth capturing

The trigger word doesn't have to be literally "remember." Capture into `06_Memory/` when the user signals durable intent: *"save this for later"*, *"note that"*, *"keep in mind"*, *"don't forget"*, *"file this under X"*, *"jot this down"*. Also reasonable to capture when the user volunteers a hard-won fact in a way that clearly expects it to stick (an exact config value with a "btw" preamble, a gotcha they want recorded). When in doubt and the cost of asking is low, ask: *"Want me to file that under `06_Memory/<topic>.md`?"*

If the user is just narrating the present session ("I'm going to refactor the handler now"), that's not a memory — leave it alone, or suggest `/update-daily-note` if they're trying to log session work.

## Edge cases

- **Vault not found**: if neither a `notes/` directory nor `$NOTES_PATH` resolves, the vault isn't reachable from here. Tell the user and stop.
- **Topic better suits a daily log**: if the user says "remember today I shipped X", that's daily-log territory — point them at `/update-daily-note` but offer to file it in `06_Memory/` if they want durable capture instead.
- **Two plausible topics**: pick the more specific one (Jira ticket beats generic module name) and mention your choice in the confirmation so the user can redirect if it's wrong.

## Related

`notes-recall` reads from the same `06_Memory/` files plus the rest of the notes vault when the user asks to resume work, check status, or look something up.

