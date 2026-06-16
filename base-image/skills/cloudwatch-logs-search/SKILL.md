---
name: cloudwatch-logs-search
description: >-
  Search AWS CloudWatch Logs safely and accurately from the terminal via boto3 (read-only) — targeted
  log searches that match or beat clicking around the AWS console, with built-in cost guards and
  false-negative protection. Use this whenever the user wants to search or grep CloudWatch logs, check
  what a Lambda logged, investigate a log group, find an id / event / error / request in logs, confirm
  whether something WAS or WASN'T logged, trace when something appeared, or do any CloudWatch log
  forensics. Triggers on phrasings like "search cloudwatch", "check the logs for X", "find X in the
  lambda logs", "grep cloudwatch", "did lambda Y log Z", "pull the logs for...", "when did X show up in
  the logs", "is there anything in the logs about...". ESPECIALLY use it for searches over a wide time
  window or a high-volume log group, where a naive search risks large cost or silently missed matches —
  this skill is the safe way to do those.
---

# CloudWatch Logs Search

## Why this skill exists

Two failure modes make ad-hoc CloudWatch searching risky, and this skill is built to prevent both:

1. **Cost.** Logs Insights bills per GB *scanned*. A single careless query (`@message like /85634/` across high-volume groups over months) once scanned **5.26 TB ≈ $26**. `filter_log_events` — the API behind a basic console search — is **free**. This skill defaults to free and treats Insights as a confirm-first exception.
2. **Wrong conclusions.** A bare term match is full of false positives (an id sitting inside a UUID, a timestamp, a longer number), and a "0 results" is dangerously easy to misread as "it didn't happen" when really the search couldn't have matched (wrong group, expired retention, log level off, mis-typed pattern). Humans skip the checks that catch these; this skill makes them automatic.

The goal: a search that is **at least as accurate as the console, and more trustworthy**, because it paginates fully, classifies every hit, and proves its negatives.

## Prerequisites

- `boto3` (any Python ≥3.7). **No `aws` CLI needed** — everything is boto3. Works the same on a host or in a devcontainer.
- AWS credentials in the environment (STS creds, a profile, or instance role). Verify with a quick `boto3.client("sts").get_caller_identity()` if unsure. If credentials are missing/expired, say so and stop — don't guess.
- Region defaults to `$AWS_REGION` → `$AWS_DEFAULT_REGION` → `us-east-1`; pass `--region` to override.

## The workflow

Two read-only scripts (only `describe_log_groups`, `filter_log_events`, `get_log_events`). They are location-independent:

- Paths below are relative to **this skill's own directory** — call it `$SKILL` (the base dir shown to you when the skill loads). Invoke as `python "$SKILL/scripts/<name>.py" …`. Don't assume the current directory.
- `cwlogs.py` needs no repo at all. `resolve_group.py` **auto-detects the repo root** by walking up from your current directory to find `serverless.yml` — so it works whether the repo is at `/workspace` in a container or `~/anywhere/<service-name>` on a host (override with `--repo <path>`).

**Step 0 — Resolve the log group and CONFIRM it with the user (do this first, every time).** This is the single most important guard: searching the wrong group produces a confident, wrong "0 results". A Lambda log group is `/aws/lambda/<service>-<stage>-<functionKey>` — users rarely remember the full string, so don't make them, and don't guess. Resolve it from this repo's serverless config:
```bash
python "$SKILL/scripts/resolve_group.py" --lambda <name-or-keyword>     # e.g. process_nb, sqs_process_anomaly
python "$SKILL/scripts/resolve_group.py" --list                          # see all functions in this repo
```
It reads `SLS_SERVICE_NAME` from `.env` and the `functions:` keys + `provider.stage` from `serverless.yml`, builds the exact group name, and verifies it exists in CloudWatch (with retention + size). For a lambda in a **different** service (e.g. the device service — not in this repo), it falls back to discovering matching groups live.

Then **present the [approval block](#approval-confirm-before-running) and wait for an explicit OK before searching.** Never search an unconfirmed group. If resolution is ambiguous (several matches) or cross-service, use the picker variant so the user chooses. (If the user hands you a full group name directly, you can skip resolution — but still show the approval block, especially before a wide-window or large-group search.)

### Approval: confirm before running

Searching the **wrong group**, an **unreachable window**, or a **paid query** are the costly mistakes — so before running, show a compact confirmation block and wait for an explicit "yes". Fill **every** field below; if a value is genuinely unknown (e.g. couldn't verify because creds are missing), print it as `unverified` rather than dropping it — a silent omission is how a wrong group slips through.

| Field | What to show |
|---|---|
| **Group(s)** | the exact resolved name + `exists ✓` / `⚠ NOT FOUND` / `unverified` |
| **Retention** | retention days **and** a `window covered ✓ / ✗` verdict against your window |
| **Region** | the AWS region |
| **Window** | `start → end` in **UTC**, noting the end is exclusive |
| **Query** | the assembled match — term + context/all/any/not, exactly what will match |
| **Cost/size** | `filter_log_events — free` (+ group size & rough duration), or the paid gate below |
| **Neg-proof** | the `--probe` term, when a zero result is plausible |

**Standard block** (free search):
```
Confirm before I search:
  Group     : /aws/lambda/cloudv2deviceingestion-dev-device__process_nb   [exists ✓]
  Retention : 365 d   →   window covered ✓
  Region    : us-east-1
  Window    : 2026-03-09 00:00 → 2026-03-12 00:00 UTC  (end exclusive)
  Query     : "85634" AND near "alarm_ids" AND ("FIXED" OR "FALSE") NOT "demo-org"
  Cost/size : filter_log_events — free   (group ~1.8 TB; expect ~1–2 min)
  Neg-proof : probe "FIXED"
Run this? (yes / adjust)
```

**Ambiguous or cross-service — let the user pick:**
```
Several groups match "alarm_state_change" — which one?
  1) /aws/lambda/cloudv2device-dev-…__alarm_state_change_lambda   [365 d, 163 MB]  ← prod
  2) /aws/lambda/testv2device-dev-…__alarm_state_change_lambda    [30 d, 0.5 MB]
  3) /aws/lambda/demov2device-dev-…__alarm_state_change_lambda    [7 d, 0 MB]
Pick a number, or paste a full group name.
```

**Paid path (Logs Insights) — a stronger, explicit gate** (only when aggregation truly needs it):
```
⚠ This needs Logs Insights, which is PAID (≈ $0.005 per GB scanned).
  Group(s)  : …
  Window    : …
  Est. scan : ~<GB> GB   →   ~$<cost>
  Why needed: <the aggregation filter_log_events can't do>
Approve this paid query? (yes / no)
```

**When to re-confirm:** a **new group**, a **wider window**, or **any paid query** needs fresh approval. Refining the query *within* an already-approved group + window doesn't — just state what you ran. Never run an unconfirmed group, and never run Insights without an explicit yes.

**Step 1 — Learn the log format before trusting a filter.** Pull a few raw events so you know how the thing you're searching for actually appears (JSON keys, whether an id is logged as `'alarm_ids': [123]` vs bare):
```bash
python "$SKILL/scripts/cwlogs.py" sample --group <G> --start 2026-03-12 --end 2026-03-13 --n 5
```
This is what stops you from inventing a filter pattern that can't match.

**Step 2 — Search, with classification and a sanity probe.**
```bash
python "$SKILL/scripts/cwlogs.py" search --group <G> \
  --start 2026-03-09 --end 2026-03-12 \
  --term 85634 \
  --context alarm_ids \
  --probe FIXED
```
- `--term` is what you're looking for — the string that gets REAL/NOISE-classified.
- `--context` (optional, recommended) requires that substring near the match — it both narrows server-side and filters noise (e.g. only count `85634` when it's near `alarm_ids`).
- `--all A B …` — extra **required** substrings (AND), e.g. `--all repair_summary FIXED`. Pushed to the **server** filter, so it cuts how much data comes back.
- `--any X Y …` — require **at least one** of these (OR), AND'd with everything else, e.g. `--any FIXED FALSE` ("either close state"). The OR group can't safely share one unstructured pattern with required terms, so it's enforced **client-side** on the already-narrowed set.
- `--not Z …` — **exclude** events containing any of these, e.g. `--not healthcheck demo-org`. Pushed to the **server** filter.
- `--probe` (optional, high value) is a term that *should* appear if the relevant event type is being logged in this group+window. It's how a zero gets proven (see below).

These compose to cut volume — net match is `term AND context? AND all… AND (any-of …) AND NOT excl…`. The report echoes the assembled **`Query`** and the exact **`Server`** filterPattern it sent (and, when `--any` is used, how much it trimmed client-side), so you can see precisely what ran:
```bash
python "$SKILL/scripts/cwlogs.py" search --group <G> --start 2026-03-09 --end 2026-03-12 \
  --term 85634 --context alarm_ids --any FIXED FALSE --not demo-org
```

Times are **UTC**; the `--end` is **exclusive** (so `--end 2026-03-17` covers through end of 03-16). Default to **narrow** windows and widen deliberately.

**Step 3 — Report.** Relay the script's structured report to the user: groups + retention + window-covered, raw hit count, the **REAL / NOISE / CONTEXT-MISS** breakdown, the real hits with timestamps and snippets, the negative-sanity verdict, and the cost basis. Don't just say "found 9 hits" — say how many were real and why the rest weren't.

When there's at least one REAL match, the report includes a **console link to the first match** — a deep link to the **single highlighted event** (the blue-highlighted row you get by clicking an event in the console). It's built from the event's `logStreamName`, `timestamp`, and `eventId` (all returned by `filter_log_events`) in the form the console itself uses:
```
…/log-group/<enc-group>/log-events/<enc-stream>/<enc-stream>$3Fstart$3D<ms>$26refEventId$3D<eventId>
```
The query is appended **after the full stream route** (note the stream repeats), pinning the exact event via `refEventId` (= `eventId`). This is why it works where a bare `…/log-events$3Fstart$3D…` window does **not** — that earlier form leaked the query into the `logGroupName` API call and failed its `[\.\-_/#A-Za-z0-9]+` regex. The report also prints group + stream fallbacks.

**Hand the link over via a file, never by pasting the URL into chat/terminal.** These URLs are long and full of `$`/`%`; when they wrap in a terminal and the user copies across the wrap, stray `%20` spaces get injected mid-name and the console rejects the `logGroupName` (observed: `…__m%20%20ainlambda…` → regex error). Pass `--link-html <file>` to `search` and tell the user to **open the file and click** — no copying. This link doubles as the one-time **console cross-check** (`evals/ground-truth.md` GT-4): if it lands on (and highlights) the event the skill reported, parity is confirmed.

## Cost discipline (hard gate)

- **Default to `filter_log_events`. It is free.** The script never calls anything else.
- A wide window or huge group makes `filter_log_events` *slower*, not more expensive — long runtime ≠ cost. Let it run; consider running it in the background.
- **Logs Insights is the only thing that costs money**, and only use it for genuine aggregation (counts/stats/parsing across fields) that `filter_log_events` can't do. Before any Insights query: pick the **smallest sufficient group**, **anchor** the filter, estimate scanned GB, and **get the user's explicit OK**. Never run a broad Insights `like` across high-volume groups — that's the $26 mistake.

## Noise classification (accuracy)

A search term routinely matches inside larger tokens. The script labels each hit:
- **NOISE** — the term is embedded in a longer number (SIM ICCID `…668563481`, epoch, float fraction `.785634Z`), or inside a UUID / RequestId / hash.
- **CONTEXT-MISS** — a clean match, but the `--context` you required isn't nearby.
- **REAL** — bounded by real delimiters (`[ ] , : space ' "`) and, if given, with the context present.

The classifier is a heuristic, so the script always prints the **snippet** for real hits — eyeball them, don't trust the label blindly. If a result looks misclassified, adjust `--context` or inspect with `sample`.

## Negative sanity — the cardinal rule

**Never report "0 results" as "it didn't happen" without proof.** A zero has two very different meanings:
- *No matches found* (the thing genuinely isn't there), vs.
- *Couldn't have matched* (wrong group, retention expired, log level too low, bad pattern).

The `--probe` distinguishes them: it counts events of the relevant *type* in the same group+window. If the probe is present and your term is absent → **true negative**. If the probe is also absent → **inconclusive**, and you must widen/redirect before concluding. Always state which one you're claiming.

## Validating accuracy before relying on it

Trust is earned against ground truth. `evals/ground-truth.md` holds known-answer queries; reproduce them and confirm the script's output matches. The seed case: in `/aws/lambda/cloudv2device-dev-device__mainlambda`, alarm **85634** has a REAL `NEW` at `2026-03-10 10:20:22` and `ACK` at `10:37:32` (both `'alarm_ids': [85634]`), while a bare `85634` search also returns many NOISE hits (SIM ICCIDs, timestamps) the classifier must reject. Also recommend the user do a **one-time cross-check** of one query against the AWS console so they trust the parity with their own eyes.

## ⚠️ Security caveat — secrets in logs

Some of this project's lambdas log **secrets in plaintext** to CloudWatch — DB passwords and AWS access keys have been seen in the `…device__*` groups (e.g. during DB-connect). So **search output may contain live secrets.** Don't paste raw event bodies into shared/persistent places without redacting, and flag it if you see credentials in results. (This is itself a bug worth raising with the owning team.)

## References

- `references/known-groups-and-gotchas.md` — growable list of known log groups, retention map, log formats, and gotchas. Consult it before discovering from scratch; **append** new findings as you learn them.
- `references/filter-syntax-and-accuracy.md` — CloudWatch filter-pattern semantics (term vs quoted substring, JSON patterns) and the subtle ways a pattern silently fails to match.
