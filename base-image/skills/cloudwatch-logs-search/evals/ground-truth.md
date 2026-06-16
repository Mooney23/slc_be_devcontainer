# Ground-truth checks (validate the skill before relying on it)

These are known-answer searches. Run them and confirm the skill's output matches
the expected result. If any diverges, fix the script/pattern logic before
trusting the skill for real work. Re-run after any change to `cwlogs.py`.

All UTC. Region us-east-1. Requires valid AWS creds in env.

## GT-1 — REAL hits found and correctly located

```bash
python scripts/cwlogs.py search \
  --group /aws/lambda/cloudv2device-dev-device__mainlambda \
  --start 2026-03-09 --end 2026-03-12 \
  --term 85634 --context alarm_ids --probe FIXED
```
**Expect:** REAL hits including `NEW` at `2026-03-10 10:20:22` and `ACK` at
`2026-03-10 10:37:32` (both with `'alarm_ids': [85634]`). Snippets should show
the `Got kwargs` / `Executing query` lines. Negative-sanity not triggered
(real hits exist).

## GT-2 — noise correctly rejected (the client-side classifier test)

Run WITHOUT `--context` so the classifier actually sees the noise (with
`--context alarm_ids` the server AND-filter pre-removes it — see GT-2b):
```bash
python scripts/cwlogs.py search \
  --group /aws/lambda/cloudv2device-dev-device__controlchannel_iotrule_lambda \
  --start 2026-03-12 --end 2026-03-17 \
  --term 85634 --probe FIXED
```
**Expect:** a few hundred raw hits, but **REAL = 0** — every hit is a SIM ICCID
(`…668563481`) or microsecond timestamp (`…785634Z`), all classified NOISE.
Negative-sanity prints **TRUE NEGATIVE** (probe `FIXED` present → closes are
logged here in-window; 85634 genuinely absent as an alarm id). This is the core
accuracy test: a naive search would wrongly "find" 85634 here.

## GT-2b — server-side context narrowing (same conclusion, cheaper)

```bash
python scripts/cwlogs.py search \
  --group /aws/lambda/cloudv2device-dev-device__controlchannel_iotrule_lambda \
  --start 2026-03-12 --end 2026-03-17 \
  --term 85634 --context alarm_ids --probe FIXED
```
**Expect:** **raw-hits = 0** (the `"alarm_ids" "85634"` AND-filter excludes the
noise server-side) and the same **TRUE NEGATIVE** verdict. Confirms `--context`
is a valid, cheaper path to the same answer when you know the field.

## GT-3 — true negative vs inconclusive

Pick a group/window where the relevant event type is NOT logged (or retention is
expired) and confirm the script reports **INCONCLUSIVE** (probe absent) rather
than asserting absence. This guards the cardinal rule.

## GT-5 — multi-term operators (--all / --any / --not)

Confirms the AND/OR/NOT flags assemble correctly and CloudWatch accepts the
server-side exclude. Same `mainlambda` window (4 events for 85634: two NEW-related
@10:20, two ACK-related @10:37). Offline assembly is unit-tested; this is the live leg.

```bash
# NOT — server-side exclude drops the ACK events
python scripts/cwlogs.py search --group /aws/lambda/cloudv2device-dev-device__mainlambda \
  --start 2026-03-09 --end 2026-03-12 --term 85634 --context alarm_ids --not ACK
# Expect: Server filterPattern  "85634" "alarm_ids" -"ACK" ; server-hits=2 ; REAL=2 (NEW events)

# ANY — client-side OR keeps only the ACK events
python scripts/cwlogs.py search --group /aws/lambda/cloudv2device-dev-device__mainlambda \
  --start 2026-03-09 --end 2026-03-12 --term 85634 --context alarm_ids --any ACK
# Expect: Server "85634" "alarm_ids" (4) ; after --any=2 ; REAL=2 (ACK events)
```
Note: first run (2026-06) hit an **expired STS token** before the API call — the
patterns assembled correctly in the output; rerun when authenticated to confirm
CloudWatch accepts `-"x"` end-to-end.

## GT-4 — console cross-check via the emitted deep link (one-time, manual)

GT-1 (and any search with REAL hits) now prints a **console deep link to the
first match**. Click it once and confirm it lands on the same event the skill
reported (the `85634` `NEW` at `2026-03-10 10:20:22` in `mainlambda`). That is
the parity check that earns trust in the programmatic path.

If the deep link's window/filter doesn't take (CloudWatch console-fragment
format can drift between versions), use the printed fallback — the canonical
group link + the exact stream name + timestamp — to navigate manually, and note
in `references/filter-syntax-and-accuracy.md` what the working format was so the
link builder in `cwlogs.py` (`console_links`) can be corrected.
