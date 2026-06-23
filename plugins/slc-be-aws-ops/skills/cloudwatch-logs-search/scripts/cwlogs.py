#!/usr/bin/env python3
"""
cwlogs.py — read-only CloudWatch Logs search helper (boto3).

Why this exists: a CloudWatch search is only trustworthy if it (a) never costs a
surprise, (b) distinguishes a real match from a coincidental substring, and
(c) proves a "0 results" is a TRUE zero and not a blind spot. This script bakes
those three things in so every search is consistent and reproducible.

It ONLY calls read APIs: describe_log_groups, filter_log_events, get_log_events.
It NEVER calls Logs Insights (per-GB billing) or any mutating API. Insights, if
ever needed, is an explicit manual decision documented in SKILL.md — not here.

Subcommands:
  discover  --prefix P                       list groups + retention + size
  sample    --group G --start S --end E      pull raw events to learn the format
  search    --group G --start S --end E (--term T | --raw-pattern P)
            [--context C] [--probe P] [--all A B] [--any X Y] [--not Z]
                                             paginate fully, classify hits,
                                             and sanity-check negatives.
            --all = extra required (AND); --any = require >=1 (OR);
            --not = exclude (NOT). Required+exclude run server-side; the OR
            group is enforced client-side on the narrowed set.
            --raw-pattern = a CloudWatch filterPattern sent VERBATIM (JSON metric
            filters etc.); bypasses term-wrapping and skips client-side classify.
  profile   --group G --start S --end E      group lines by source; report
            [--max-events N] [--top N]       count-share, BYTE-share (= the bill),
            [--sort bytes|count]             avg B/line; flags + redacts secrets.

Times are UTC. Accept 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM:SS'. The end time is
EXCLUSIVE (matches filter_log_events semantics), so '--end 2026-03-17' covers
through end of 2026-03-16.
"""
import argparse, datetime as dt, json, os, re, sys, urllib.parse
from collections import defaultdict

try:
    import boto3
except ImportError:
    sys.exit("boto3 not available — install it with 'pip install boto3' (no aws CLI needed).")


def to_ms(s):
    s = s.strip()
    fmt = "%Y-%m-%dT%H:%M:%S" if "T" in s else "%Y-%m-%d"
    d = dt.datetime.strptime(s, fmt).replace(tzinfo=dt.timezone.utc)
    return int(d.timestamp() * 1000), d


def fmt_ts(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def cw_enc(s):
    """CloudWatch console fragment encoding: encodeURIComponent twice, then %->$.
    Net effect: '/' -> '$252F', '[' -> '$255B', '$' -> '$2524', etc. This is the
    (undocumented) scheme the logsV2 console uses in its URL hash."""
    once = urllib.parse.quote(str(s), safe="")
    return urllib.parse.quote(once, safe="").replace("%", "$")


def console_links(region, group, stream, ts=None, event_id=None):
    """Build CloudWatch console deep links for an event. Returns
    (group_link, stream_link, event_link).

    - group_link  : the log group. Always reliable.
    - stream_link : the exact stream (path form). Reliable.
    - event_link  : the SINGLE-EVENT highlighted view (the blue-highlighted row
      you get when you click an event). Its route repeats the stream and pins the
      event by `refEventId` (= CloudWatch's `eventId`, returned by
      filter_log_events):
        .../log-events/<enc-stream>/<enc-stream>$3Fstart$3D<ms>$26refEventId$3D<eventId>
      The query is appended AFTER the full stream route (not after `/log-events`),
      which is why this form is accepted while a bare `/log-events$3F...` window is
      rejected (that leaks into logGroupName -> regex error)."""
    base = (f"https://{region}.console.aws.amazon.com/cloudwatch/home?region={region}"
            f"#logsV2:log-groups/log-group/{cw_enc(group)}")
    stream_link = f"{base}/log-events/{cw_enc(stream)}" if stream else None
    event_link = None
    if stream and event_id:
        es = cw_enc(stream)
        event_link = f"{base}/log-events/{es}/{es}$3Fstart$3D{ts}$26refEventId$3D{event_id}"
    return base, stream_link, event_link


def write_links_html(path, rows):
    """Write clickable console links to an HTML file. These URLs are long and
    contain '$'/'%' — copying them out of a wrapping terminal injects stray
    spaces (%20) that corrupt the logGroupName. Clicking from a file avoids that
    entirely."""
    out = ["<!doctype html><meta charset='utf-8'>",
           "<body style='font-family:system-ui;max-width:900px;margin:40px auto;line-height:1.7'>",
           "<h3>CloudWatch search — first-match links</h3>"]
    for name, ts, primary, group_link in rows:
        out.append(f"<p><b>{name}</b><br>first match @ {fmt_ts(ts)} UTC<br>"
                   f"<a href=\"{primary}\">open match (highlighted event)</a>"
                   + (f" &nbsp;·&nbsp; <a href=\"{group_link}\">open group</a>" if primary != group_link else "")
                   + "</p>")
    out.append("</body>")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))


def client(region):
    return boto3.client("logs", region_name=region)


def resolve_groups(c, name_or_prefix):
    """Return exact matches if the name exists, else all groups under the prefix."""
    found, tok = [], None
    while True:
        kw = {"logGroupNamePrefix": name_or_prefix, "limit": 50}
        if tok:
            kw["nextToken"] = tok
        r = c.describe_log_groups(**kw)
        found += r.get("logGroups", [])
        tok = r.get("nextToken")
        if not tok:
            break
    return found


def cmd_discover(c, args):
    groups = resolve_groups(c, args.prefix)
    if not groups:
        print(f"No log groups match prefix: {args.prefix}")
        return
    print(f"{'retention':>10} | {'sizeMB':>10} | name")
    for g in sorted(groups, key=lambda x: x["logGroupName"]):
        ret = g.get("retentionInDays", "never-expire")
        mb = round(g.get("storedBytes", 0) / 1e6, 1)
        print(f"{str(ret):>10} | {mb:>10} | {g['logGroupName']}")


def fetch_events(c, group, start, end, pattern=None, max_events=None):
    """Paginate filter_log_events.

    max_events=None -> EXHAUST the window (every matching event). Full pagination
    matters for search/count: the console shows partial results and humans miss
    matches by not scrolling.

    max_events=N -> stop as soon as N events are collected. For sample/probe/
    profile, which only need a peek; without the cap they page a multi-TB group
    to exhaustion just to slice a handful off the front (the bug behind Fix 1/3).

    A filtered call can return a page with 0 events but a nextToken (it scanned a
    chunk without a match). We keep paging on empty pages, so a bounded fetch
    still finds the first N *matches* across sparse pages rather than stopping
    short -- it just never pages PAST them."""
    events, tok = [], None
    while True:
        page_limit = 10000 if max_events is None else min(10000, max_events - len(events))
        kw = dict(logGroupName=group, startTime=start, endTime=end, limit=page_limit)
        if pattern:
            kw["filterPattern"] = pattern
        if tok:
            kw["nextToken"] = tok
        r = c.filter_log_events(**kw)
        events += r.get("events", [])
        tok = r.get("nextToken")
        if not tok or (max_events is not None and len(events) >= max_events):
            break
    return events[:max_events] if max_events is not None else events


def fetch_all(c, group, start, end, pattern=None):
    """Exhaust the window -- every matching event. Thin alias kept for the
    search call sites where exhaustion is the intended behavior and the name
    documents it."""
    return fetch_events(c, group, start, end, pattern, max_events=None)


def quoted_term(t):
    """Wrap a plain term for an unstructured filterPattern as f'\"t\"'. A term that
    already contains a double-quote would produce malformed syntax (e.g.
    '\"\"level\": ...') that CloudWatch rejects with a cryptic 'Invalid character(s)
    in term'. Fail fast with a pointer to --raw-pattern instead of shipping junk
    to the API."""
    if '"' in t:
        sys.exit(
            f"!! search value contains a double-quote and can't be term-wrapped: {t!r}\n"
            "   For a JSON/structured match, use search --raw-pattern (sent verbatim), e.g.:\n"
            '       --raw-pattern \'{ $.level = "DEBUG" }\'')
    return f'"{t}"'


def cmd_sample(c, args):
    """Pull a few raw events so the caller can learn the log shape (JSON keys,
    how ids are formatted) BEFORE trusting any filter pattern."""
    start, _ = to_ms(args.start)
    end, _ = to_ms(args.end)
    pattern = quoted_term(args.term) if args.term else None
    events = fetch_events(c, args.group, start, end, pattern, max_events=args.n)
    print(f"# {len(events)} sample event(s) from {args.group}")
    for e in events:
        print(f"--- {fmt_ts(e['timestamp'])} UTC ---")
        print(e["message"].strip()[: args.chars])


def classify(msg, term, context, ctx_window):
    """Decide whether an occurrence of `term` in `msg` is a REAL match or
    coincidental NOISE. The classic traps: the term sitting inside a longer
    number (SIM ICCID, epoch, float), inside a UUID/RequestId, or inside a
    microsecond timestamp fraction (e.g. .123456Z). Heuristic: a real match is
    bounded by non-alphanumeric delimiters ([ ] , : space ' "); a digit or hex
    neighbour means it's embedded in a larger token.

    Returns (label, reason, snippet) for the best occurrence in the event.
    label in {real, noise, context-miss}. A single real occurrence wins."""
    best = None
    for m in re.finditer(re.escape(term), msg):
        i = m.start()
        before = msg[i - 1] if i > 0 else ""
        after = msg[i + len(term)] if i + len(term) < len(msg) else ""
        snippet = msg[max(0, i - 60): i + len(term) + 30].replace("\n", " ")
        # embedded in a longer number → noise (ICCID, epoch ts, float fraction)
        if before.isdigit() or after.isdigit():
            label, reason = "noise", "embedded-in-longer-number"
        # adjacent hex letter → inside a UUID / RequestId / hash
        elif before in "abcdefABCDEF" or after in "abcdefABCDEF":
            label, reason = "noise", "inside-hex/uuid"
        # hyphen-adjacent with hex nearby → UUID segment
        elif (before == "-" or after == "-") and re.search(
            r"[0-9a-fA-F]{4,}-", msg[max(0, i - 12): i + len(term) + 12]):
            label, reason = "noise", "inside-uuid"
        else:
            label, reason = "real", "delimited"
            if context:
                win = msg[max(0, i - ctx_window): i + len(term) + ctx_window]
                if context not in win:
                    label, reason = "context-miss", f'no "{context}" within {ctx_window} chars'
        rank = {"real": 0, "context-miss": 1, "noise": 2}[label]
        if best is None or rank < best[0]:
            best = (rank, label, reason, snippet)
        if label == "real":
            break
    return best[1:] if best else ("noise", "term-not-found", "")


def cmd_search(c, args):
    raw_mode = args.raw_pattern is not None
    if raw_mode and (args.context or args.all_terms or args.any_terms or args.excl):
        sys.exit("!! --raw-pattern owns the whole filterPattern; remove --context/--all/--any/--not "
                 "and express the logic in the pattern itself (e.g. '{ $.a = 1 && $.b = 2 }'). "
                 "--probe is still allowed.")

    start, sdt = to_ms(args.start)
    end, edt = to_ms(args.end)
    groups = resolve_groups(c, args.group) if args.discover else [{"logGroupName": args.group}]
    if not groups:
        print(f"!! No log group matches '{args.group}'. Check the name/prefix (discover first).")
        return

    excl, any_terms = args.excl, args.any_terms
    if raw_mode:
        # Caller supplied a real CloudWatch filterPattern (JSON metric filter,
        # space-delimited, etc.). Send it VERBATIM — the term wrapper would mangle
        # quotes/braces. The server does the precise matching, so we skip the
        # client-side classify (no substring-noise risk) and treat every hit as real.
        pattern = args.raw_pattern
        qdesc = f"raw-pattern={args.raw_pattern!r}"
    else:
        # Assemble the query. Required terms (term + context + --all) and exclusions
        # (--not) go into the SERVER filterPattern: `"a" "b" -"x"` is well-defined
        # (AND of required, minus excluded) and shrinks transfer. The --any OR-group
        # can't safely share one unstructured pattern with required terms, so it's
        # enforced CLIENT-side on the already-narrowed results. Net match:
        #   term AND context? AND all... AND (any-of ...) AND NOT excl...
        # The server pattern is always a SUPERSET filter, so it never drops a true match.
        required = [args.term] + ([args.context] if args.context else []) + args.all_terms
        pattern = " ".join([quoted_term(t) for t in required] + ["-" + quoted_term(t) for t in excl])
        qdesc = f"term={args.term!r}"
        if args.context:  qdesc += f" AND near={args.context!r}"
        qdesc += "".join(f" AND {t!r}" for t in args.all_terms)
        if any_terms:     qdesc += " AND (" + " OR ".join(repr(t) for t in any_terms) + ")"
        qdesc += "".join(f" AND NOT {t!r}" for t in excl)

    print("=== CLOUDWATCH SEARCH REPORT ===")
    print(f"Region : {args.region}")
    print(f"Window : {sdt:%Y-%m-%d %H:%M:%S} -> {edt:%Y-%m-%d %H:%M:%S} UTC  (end exclusive)")
    print(f"Query  : {qdesc}")
    print(f"Server : filterPattern={pattern!r}" + ("   (--any applied client-side)" if (not raw_mode and any_terms) else ""))
    print("Cost   : filter_log_events (free — no Logs Insights used)")

    link_rows = []

    for g in groups:
        name = g["logGroupName"]
        meta = g if "retentionInDays" in g or "storedBytes" in g else \
            (resolve_groups(c, name) or [{}])[0]
        ret = meta.get("retentionInDays", "never-expire")
        covered = "UNKNOWN"
        if isinstance(ret, int):
            cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=ret))
            covered = "YES" if sdt >= cutoff else "NO — window predates retention!"
        events = fetch_all(c, name, start, end, pattern)
        server_n = len(events)
        if not raw_mode and any_terms:  # enforce the OR-group client-side on the narrowed set
            events = [e for e in events if any(t in e["message"] for t in any_terms)]
        buckets = {"real": [], "noise": [], "context-miss": []}
        for e in events:
            row_tail = (e.get("logStreamName", ""), e.get("eventId", ""))
            if raw_mode:
                # server-side filter already matched precisely — no substring-noise to classify
                snip = e["message"].strip()[:90].replace("\n", " ")
                buckets["real"].append((e["timestamp"], "raw-pattern (server-side)", snip, *row_tail))
            else:
                label, reason, snip = classify(e["message"], args.term, args.context, args.ctx_window)
                buckets[label].append((e["timestamp"], reason, snip, *row_tail))

        print(f"\n### {name}")
        print(f"    retention={ret}  window-covered={covered}  server-hits={server_n}"
              + (f"  after --any={len(events)}" if any_terms else ""))
        print(f"    REAL={len(buckets['real'])}  NOISE={len(buckets['noise'])}  CONTEXT-MISS={len(buckets['context-miss'])}")
        for ts, reason, snip, _, _ in sorted(buckets["real"])[: args.max]:
            print(f"    >>> REAL {fmt_ts(ts)}  ...{snip}...")
        if buckets["context-miss"] and not buckets["real"]:
            for ts, reason, snip, _, _ in sorted(buckets["context-miss"])[:3]:
                print(f"    ~~~ CONTEXT-MISS {fmt_ts(ts)} ({reason})  ...{snip}...")

        # Console link to the FIRST real match — lets the user jump straight to it
        # and (the first time) eyeball-verify the skill against the console.
        if buckets["real"]:
            ts0, _, _, stream0, eid0 = sorted(buckets["real"])[0]
            group_link, stream_link, event_link = console_links(args.region, name, stream0, ts0, eid0)
            primary = event_link or stream_link or group_link
            link_rows.append((name, ts0, primary, group_link))
            print(f"    LINK (first match @ {fmt_ts(ts0)} UTC{', highlighted' if event_link else ''}):")
            print(f"      → {primary}")
            print(f"      group fallback: {group_link}")
            print(f"      stream: {stream0}  | eventId: {eid0}")
            print("      NOTE: don't copy this URL from the terminal (long URLs wrap and copying injects spaces that")
            print("            corrupt the group name). Use --link-html <file> and click from there.")

        # NEGATIVE SANITY — the cardinal rule. A 0-real result is only
        # trustworthy if we can show the relevant event type IS logged here in
        # this window. Without the probe, a zero is "no matches found", NOT
        # "this didn't happen".
        if not buckets["real"]:
            if args.probe:
                # A probe only needs to prove EXISTENCE, so stop at the first match
                # (max_events=1) instead of counting every hit. The old
                # len(fetch_all(...)) paged a high-volume probe like INFO through
                # millions of events just to collapse it to '> 0' -- unusable on a
                # wide window (Fix 3). Cost is now O(1) when the probe is present.
                present = bool(fetch_events(c, name, start, end, quoted_term(args.probe), max_events=1))
                verdict = ("TRUE NEGATIVE — probe present, so logging is active and the term is genuinely absent"
                           if present else
                           "INCONCLUSIVE — probe also absent: wrong group, retention, or log level. NOT proof of absence")
                print(f"    SANITY: probe {args.probe!r} -> {'PRESENT' if present else 'ABSENT'} => {verdict}")
            else:
                print("    SANITY: no --probe given. A zero here is 'no matches found', NOT proof it didn't happen. "
                      "Re-run with --probe <term-that-should-exist-if-logging-works>.")

    if args.link_html and link_rows:
        write_links_html(args.link_html, link_rows)
        print(f"\nClickable link(s) written to {args.link_html} — open the file and click "
              "(don't copy long URLs from the terminal; the wrap corrupts them).")


def normalize_prefix(msg, n=70):
    """Collapse a plain-text line to a STABLE group key by masking variable tails
    (request ids, numbers, hashes) then truncating. Without this, every
    'START RequestId: <uuid>' is its own group; with it they collapse to one
    line-type -- the improvement over lumping all plain text as 'UNPARSED'."""
    s = msg.strip()
    s = re.sub(r"://[^/\s@]+@", "://<creds>@", s)              # collapse user:pass@ in URIs (per-org)
    s = re.sub(r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{8,}", "<id>", s)   # uuid / RequestId
    s = re.sub(r"\b[0-9a-f]{16,}\b", "<hex>", s)                # long hex blobs
    s = re.sub(r"\b\d[\d.,:]*\b", "#", s)                       # numbers / durations / sizes
    s = re.sub(r"\s+", " ", s)
    return s[:n]


# Credential patterns the team has actually leaked into these logs. Each rule both
# DETECTS (for the secrets report) and REDACTS (so a live value is never printed).
SECRET_RULES = [
    ("db-uri-password", re.compile(r"(://[^/\s:@]+:)[^@\s/]+(@)"), r"\1***\2"),
    ("aws-access-key", re.compile(r"AWSAccessKeyId=[^&\s]+"), "AWSAccessKeyId=***"),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AKIA***"),
    ("aws-signature", re.compile(r"Signature=[^&\s]+"), "Signature=***"),
    ("aws-sts-token", re.compile(r"(?i)(x-amz-security-token=)[^&\s]+"), r"\1***"),
]


def scan_and_redact(msg):
    """Return (set-of-secret-labels, redacted_msg). Detection runs on the full
    line; redaction masks values so the tool never prints a live credential."""
    labels, s = set(), msg
    for label, rx, repl in SECRET_RULES:
        if rx.search(s):
            labels.add(label)
            s = rx.sub(repl, s)
    return labels, s


def cmd_profile(c, args):
    """Profile what is FILLING a log group -- the first question of any cost
    investigation. Group lines by source (filename:lineno for JSON, normalized
    message prefix for plain text); report count-share, BYTE-share (= what
    CloudWatch bills), and avg bytes/line. Bounded by --max-events so it stays
    free and predictable on a multi-TB group. Flags lines that leak secrets."""
    start, sdt = to_ms(args.start)
    end, edt = to_ms(args.end)

    events = fetch_events(c, args.group, start, end, max_events=args.max_events)
    n = len(events)
    if n == 0:
        print(f"No events in window for {args.group}.")
        return

    cnt, byts, sample, secrets, total = defaultdict(int), defaultdict(int), {}, defaultdict(set), 0
    for e in events:
        m = e["message"]; total += len(m)
        try:
            j = json.loads(m)
        except (ValueError, TypeError):
            j = None
        if isinstance(j, dict) and j.get("filename") is not None:
            key = f"{j['filename']}:{j.get('lineno', '?')}"
            disp = str(j.get("message", ""))
        else:
            key, disp = normalize_prefix(m), m
        cnt[key] += 1; byts[key] += len(m)
        labels, _ = scan_and_redact(m)
        if labels:
            secrets[key] |= labels
        if key not in sample:
            sample[key] = scan_and_redact(disp)[1][:90].replace("\n", " ")

    order = byts if args.sort == "bytes" else cnt
    rows = sorted(cnt, key=lambda k: order[k], reverse=True)

    capped = ("  ⚠ --max-events cap reached; sample may not cover the full window "
              "(narrow the window or raise --max-events)") if n >= args.max_events else ""
    print("=== CLOUDWATCH PROFILE ===")
    print(f"Region : {args.region}")
    print(f"Group  : {args.group}")
    print(f"Window : {sdt:%Y-%m-%d %H:%M:%S} -> {edt:%Y-%m-%d %H:%M:%S} UTC  (end exclusive)")
    print("Cost   : filter_log_events (free — no Logs Insights used)")
    print(f"Sampled: {n} events | {total / 1e6:.2f} MB | avg {total // n} B/line{capped}")
    print(f"Grouped: {len(cnt)} line-types | sorted by {args.sort.upper()} share | top {args.top}")
    print()
    print(f"    {'count':>7} {'cnt%':>6} {'bytes':>11} {'byte%':>6} {'avgB':>6}  source")
    shown = 0
    for k in rows[: args.top]:
        shown += byts[k]
        flag = "  ⚠ SECRET" if k in secrets else ""
        print(f"    {cnt[k]:>7} {cnt[k] / n * 100:>5.1f}% {byts[k]:>11} {byts[k] / total * 100:>5.1f}% "
              f"{byts[k] // cnt[k]:>6}  {k}{flag}")
        print(f"            → {sample[k]}")
    print(f"\n    top {min(args.top, len(rows))} of {len(cnt)} line-types = "
          f"{shown / total * 100:.1f}% of sampled bytes")

    if secrets:
        print("\n⚠ SECRETS DETECTED (values redacted — logging bugs, fix regardless of cost):")
        for k in sorted(secrets, key=lambda k: byts[k], reverse=True):
            print(f"    {k}  [{', '.join(sorted(secrets[k]))}]")
            print(f"        e.g. {sample[k]}")


def main():
    p = argparse.ArgumentParser(description="Read-only CloudWatch Logs search helper")
    p.add_argument("--region", default=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("discover"); d.add_argument("--prefix", required=True)

    s = sub.add_parser("sample")
    s.add_argument("--group", required=True); s.add_argument("--start", required=True)
    s.add_argument("--end", required=True); s.add_argument("--term", default=None)
    s.add_argument("--n", type=int, default=5); s.add_argument("--chars", type=int, default=400)

    f = sub.add_parser("search")
    f.add_argument("--group", required=True)
    f.add_argument("--discover", action="store_true", help="treat --group as a prefix; search all matches")
    f.add_argument("--start", required=True); f.add_argument("--end", required=True)
    mode = f.add_mutually_exclusive_group(required=True)
    mode.add_argument("--term", default=None, help="substring to match (wrapped as an exact phrase, server-side)")
    mode.add_argument("--raw-pattern", dest="raw_pattern", default=None,
                      help="CloudWatch filterPattern sent VERBATIM (no quote-wrapping) — for JSON metric filters "
                           "like '{ $.level = \"DEBUG\" }' or other structured syntax. Owns the whole pattern: "
                           "can't combine with --context/--all/--any/--not.")
    f.add_argument("--context", default=None, help="require this substring near the match (AND-narrows + classifies)")
    f.add_argument("--all", dest="all_terms", nargs="+", metavar="STR", default=[],
                   help="extra REQUIRED substrings (AND) — pushed to the server filter to cut transfer")
    f.add_argument("--any", dest="any_terms", nargs="+", metavar="STR", default=[],
                   help="require AT LEAST ONE of these (OR group), AND'd with the rest")
    f.add_argument("--not", dest="excl", nargs="+", metavar="STR", default=[],
                   help="EXCLUDE events containing any of these (NOT) — pushed to the server filter")
    f.add_argument("--probe", default=None, help="term that SHOULD appear if logging is active; validates negatives")
    f.add_argument("--ctx-window", type=int, default=80)
    f.add_argument("--max", type=int, default=25, help="max REAL hits to print")
    f.add_argument("--link-html", default=None,
                   help="write clickable console link(s) to this HTML file (click from the file; "
                        "long CloudWatch URLs get corrupted if copied from a wrapping terminal)")

    pr = sub.add_parser("profile")
    pr.add_argument("--group", required=True)
    pr.add_argument("--start", required=True); pr.add_argument("--end", required=True)
    pr.add_argument("--max-events", dest="max_events", type=int, default=60000,
                    help="cap events sampled (default 60000) — keeps the profile free and bounded")
    pr.add_argument("--top", type=int, default=20, help="how many line-types to print (default 20)")
    pr.add_argument("--sort", choices=["bytes", "count"], default="bytes",
                    help="rank by byte-share (default, = the bill) or count-share")

    args = p.parse_args()
    c = client(args.region)
    {"discover": cmd_discover, "sample": cmd_sample, "search": cmd_search,
     "profile": cmd_profile}[args.cmd](c, args)


if __name__ == "__main__":
    main()
