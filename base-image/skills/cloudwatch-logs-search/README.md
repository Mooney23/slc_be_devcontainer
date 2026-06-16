# cloudwatch-logs-search

A read-only, cost-safe CloudWatch Logs search skill. It makes targeted log
searches that are **at least as accurate as the AWS console, and more
trustworthy** — because it paginates fully, classifies every hit as real vs.
coincidental noise, and *proves* its negatives instead of asserting them.

> This README is the human guide (use it, extend it, port it). `SKILL.md` is the
> operating instruction file that Claude loads when the skill triggers.

## Table of contents
- [Why it exists](#why-it-exists)
- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [The scripts](#the-scripts)
- [Search operators (cutting data)](#search-operators-cutting-data)
- [Reading the report](#reading-the-report)
- [Console links to a match](#console-links-to-a-match)
- [Cost & safety](#cost--safety)
- [Validating it](#validating-it)
- [Using it in another repo](#using-it-in-another-repo)
- [Layout](#layout)
- [Extending it](#extending-it)

## Why it exists

Two ways ad-hoc CloudWatch searching goes wrong, both of which this skill prevents:

1. **Cost.** Logs Insights bills *per GB scanned* — one careless `@message like /id/`
   across busy groups once scanned **5.26 TB ≈ $26**. `filter_log_events` (the API
   behind a basic console search) is **free**. This skill defaults to free and
   treats Insights as a confirm-first exception.
2. **Wrong conclusions.** A bare term matches inside UUIDs, timestamps, and longer
   numbers (false positives), and a "0 results" is easily misread as "it didn't
   happen" when the search actually *couldn't* have matched (wrong group, expired
   retention, log level off, bad pattern). The skill makes the checks that catch
   these automatic.

## Quick start

**Via Claude (the normal way).** Just ask in natural language — "search cloudwatch
for an id in a given lambda in March", "did a function log anything for a device
yesterday", "is there a timeout error in some function". The
skill triggers and walks the workflow, confirming the log group with you first.

**Directly (scripts).** `boto3` + AWS creds in your environment; region defaults to
`$AWS_REGION`/`$AWS_DEFAULT_REGION`/`us-east-1`. From anywhere in the repo:
```bash
# 0. resolve a lambda name -> exact log group (and confirm it)
python .claude/skills/cloudwatch-logs-search/scripts/resolve_group.py --lambda <function-or-keyword>

# 1. learn the log format
python .claude/skills/cloudwatch-logs-search/scripts/cwlogs.py sample \
  --group /aws/lambda/<resolved> --start 2026-03-12 --end 2026-03-13

# 2. search (classified + proven negative)
python .claude/skills/cloudwatch-logs-search/scripts/cwlogs.py search \
  --group /aws/lambda/<resolved> --start 2026-03-09 --end 2026-03-12 \
  --term <id> --context <field> --probe <probe>
```

## How it works

A CloudWatch search here is **two layers**:

**Layer 1 — server-side matching.** `filter_log_events` takes a *filter pattern* and
returns only matching events (same engine the console uses, and free). String logic
lives here: space-separated terms = AND, `?"term"` = OR, `-"term"` = exclude.

**Layer 2 — client-side trust.** For what comes back, the script:
- **classifies** each hit `REAL` / `NOISE` / `CONTEXT-MISS` — is the term in a real
  field/delimiter, or inside a UUID / microsecond timestamp / longer number?
- **proves negatives** — a 0 is only a *true* negative if a `--probe` term that
  *should* exist (if logging were active) is present in that group+window;
  otherwise it's "inconclusive", not "absent".
- **paginates to exhaustion** — no missed matches from partial results.
- **builds a deep link** to the exact matched event.

The workflow Claude runs: **Step 0** resolve + confirm the group → **Step 1** sample
the format → **Step 2** search with classification + probe → **Step 3** report.

Before any search, the skill shows an **approval block** and waits for your "yes" —
group (+ exists?), retention with a window-covered verdict, region, UTC window,
the assembled query, and the cost basis (free vs. the paid Insights gate). A new
group, a wider window, or any paid query re-prompts; refining the query within an
already-approved group+window doesn't. See "Approval" in `SKILL.md` for the exact
template.

## The scripts

### `resolve_group.py` — lambda name → exact log group
A Lambda log group is `/aws/lambda/<service>-<stage>-<functionKey>`. Nobody
remembers that, and guessing the wrong group is the #1 cause of a false "0 results".
This builds it from the repo's Serverless config and verifies it exists live.

```bash
resolve_group.py --lambda <name|keyword>   # resolve & verify (+ retention/size)
resolve_group.py --list                    # list all functions in this repo
```
| Flag | Meaning |
|---|---|
| `--lambda` | name or keyword to resolve (fuzzy-matches function keys) |
| `--list` | list every function in this repo's `serverless.yml` |
| `--repo` | repo root (default: auto-detected by finding `serverless.yml`) |
| `--service` | override service name (else read from `.env`/env `SLS_SERVICE_NAME`) |
| `--stage` | override stage (else `provider.stage`, default `dev`) |
| `--region` | AWS region (default from env, then `us-east-1`) |
| `--no-verify` | skip the live CloudWatch existence check |

It reads `SLS_SERVICE_NAME` from `.env` (falling back to the process env) and the
`functions:` keys + `provider.stage` from `serverless.yml`. For a lambda **not** in
this repo (a different service), it falls back to live discovery of matching groups
and prints them with retention so you can pick the prod one. It always ends with
"confirm the group before searching."

### `cwlogs.py` — the search engine (read-only)
Only ever calls `describe_log_groups`, `filter_log_events`, `get_log_events`. Three
subcommands:

```bash
cwlogs.py discover --prefix /aws/lambda/<service>     # groups + retention + size
cwlogs.py sample   --group <G> --start S --end E      # raw events, learn the format
cwlogs.py search   --group <G> --start S --end E --term T [operators] [--probe P]
```
`search` flags:
| Flag | Meaning |
|---|---|
| `--term` | the string you're looking for **and classifying** (REAL/NOISE) |
| `--context` | require this substring *near* the match (AND-narrow + proximity classify) |
| `--all A B …` | extra **required** substrings (AND) — server-side |
| `--any X Y …` | require **at least one** (OR), AND'd with the rest — client-side |
| `--not Z …` | **exclude** events containing any of these (NOT) — server-side |
| `--probe P` | a term that *should* exist if logging is active — validates negatives |
| `--link-html F` | write clickable console link(s) to file `F` (don't copy long URLs!) |
| `--max N` | max REAL hits to print (default 25) |
| `--ctx-window N` | chars around a match the `--context` proximity check uses (default 80) |
| `--discover` | treat `--group` as a prefix and search every matching group |

Times are **UTC**; `--end` is **exclusive** (`--end 2026-03-17` covers through end
of 03-16). Default to narrow windows.

## Search operators (cutting data)

Net match: `term AND context? AND all… AND (any-of …) AND NOT excl…`.

- **AND / 3+ terms** — `--all`: `--term <id> --all <fieldA> <fieldB> <fieldC>`
- **OR group** — `--any`: `--term <id> --any <valueA> <valueB>` ("either of two states")
- **NOT** — `--not`: `--term error --not <exclude1> <exclude2>`
- **Combine** — `--term <id> --context <field> --any <valueA> <valueB> --not <exclude>`

Required terms (`--term`, `--context`, `--all`) and exclusions (`--not`) are pushed
to the **server** filter pattern — that's where transfer volume is cut. The `--any`
OR-group is enforced **client-side**, because CloudWatch can't safely mix an OR group
with required terms in one unstructured pattern (a wrong pattern would silently drop
real matches). The server pattern is always a *superset* filter, so it never drops a
true match. The report shows the assembled `Query` and the exact `Server` pattern.

## Reading the report

```
### /aws/lambda/<group>
    retention=365  window-covered=YES  server-hits=4  after --any=2
    REAL=2  NOISE=0  CONTEXT-MISS=0
    >>> REAL 2026-03-10 10:20:22  ...<field>': [<id>]...
    LINK (first match @ 2026-03-10 10:20:22 UTC, highlighted): → <url>
```
- **window-covered** — `NO` means your window predates the group's retention; the
  result is meaningless, fix the window or group.
- **REAL / NOISE / CONTEXT-MISS** — real matches; coincidental substring matches
  (UUID/timestamp/longer number); clean matches missing the required `--context`.
- **server-hits / after --any** — what the server returned vs. what survived the OR.
- **SANITY** (on zero REAL) — `TRUE NEGATIVE` (probe present, term genuinely absent)
  vs. `INCONCLUSIVE` (probe also absent → wrong group/retention/level; not proof).
  **Never report a bare zero as "didn't happen" without a probe.**

## Console links to a match

When there's a REAL match, the report emits a deep link to the **single highlighted
event** (the blue-highlighted row), built from the event's `logStreamName`,
`timestamp`, and `eventId` (`refEventId`). Two things to know:
- **Deliver links via a file, never copy from the terminal.** These URLs are long
  and full of `$`/`%`; copying across a terminal wrap injects `%20` spaces that
  corrupt the group name (real failure: `…__m%20%20ainlambda…` → console regex
  error). Use `--link-html <file>` and **click from the file**.
- The link doubles as a one-time **console parity check**: if it highlights the
  event the skill reported, the programmatic path matches the console.

## Cost & safety

- **Read-only.** No mutation of groups, retention, or anything.
- **Free by default.** `filter_log_events`/`describe_*` aren't billed per GB. A wide
  window just makes them *slower*, not costlier (run in the background).
- **Logs Insights is the only paid path** — reserve it for true aggregation, on the
  smallest sufficient group, with an anchored filter, and **only after confirming
  cost**. The script never calls it.
- **⚠ Secrets in logs.** Applications sometimes log sensitive values (DB passwords,
  API keys, tokens) in plaintext to CloudWatch, so search output may contain secrets
  — redact before sharing, and raise the logging itself with the owning team.

## Validating it

This is a **stateless engine** — no bundled known-answer files. Earn trust once: run a
search for a term you *know* is present and confirm it comes back REAL where you expect,
then open the emitted `--link-html` and confirm the console highlights the same event
(the one check that can't be unit-tested). Cover the pure logic (classification, pattern
assembly, link building) with offline unit tests next to the scripts.

## Recording gotchas (optional)

The skill ships no knowledge files and discovers groups/retention/format live. If you
ever hit a non-obvious gotcha worth keeping — a field that looks like an id but isn't, a
mis-named group, a window where a function logged at INFO — jot it in **this repo's**
`docs/` (e.g. `docs/cloudwatch-logs-search.md`). It's project knowledge that persists in
your repo, not part of the baked skill.

## Using it in another repo

- `cwlogs.py` is **fully generic** — works against any account/region, just give it
  a group name. Copies over with no changes.
- `resolve_group.py` works in another repo **only if** it also uses Serverless with
  `serverless.yml` at root, `service: ${env:SLS_SERVICE_NAME}` (or pass `--service`),
  a literal `provider.stage` (or `--stage`), and inline `functions:` (not split via
  `${file()}`). Otherwise lean on `--service`/`--repo` or its live-discovery fallback.

## Layout
```
cloudwatch-logs-search/
├── SKILL.md                              # operating instructions (Claude reads this)
├── README.md                             # this guide (humans read this)
└── scripts/
    ├── resolve_group.py                  # lambda name -> exact log group
    └── cwlogs.py                         # discover / sample / search engine
```

## Extending it
Natural next steps, none required:
- Make `resolve_group.py` config-agnostic (read a literal `service:`, follow
  `${file()}` function includes, handle templated stages) for cleaner cross-repo use.
- Add a server-side OR mode for pure-OR searches (no required anchor term).
- Pipe links straight to the clipboard (`clip.exe`/`pbcopy`) as another copy-safe path.
