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
  search    --group G --start S --end E --term T [--context C] [--probe P]
            [--all A B] [--any X Y] [--not Z]  paginate fully, classify hits,
                                             and sanity-check negatives.
            --all = extra required (AND); --any = require >=1 (OR);
            --not = exclude (NOT). Required+exclude run server-side; the OR
            group is enforced client-side on the narrowed set.

Times are UTC. Accept 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM:SS'. The end time is
EXCLUSIVE (matches filter_log_events semantics), so '--end 2026-03-17' covers
through end of 2026-03-16.
"""
import argparse, datetime as dt, os, re, sys, urllib.parse

try:
    import boto3
except ImportError:
    sys.exit("boto3 not available — run inside the devcontainer venv (no aws CLI needed).")


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


def fetch_all(c, group, start, end, pattern=None):
    """Paginate filter_log_events to EXHAUSTION. Returns every matching event.
    Full pagination matters: the console shows partial results and humans miss
    matches by not scrolling."""
    events, tok = [], None
    while True:
        kw = dict(logGroupName=group, startTime=start, endTime=end, limit=10000)
        if pattern:
            kw["filterPattern"] = pattern
        if tok:
            kw["nextToken"] = tok
        r = c.filter_log_events(**kw)
        events += r.get("events", [])
        tok = r.get("nextToken")
        if not tok:
            break
    return events


def cmd_sample(c, args):
    """Pull a few raw events so the caller can learn the log shape (JSON keys,
    how ids are formatted) BEFORE trusting any filter pattern."""
    start, _ = to_ms(args.start)
    end, _ = to_ms(args.end)
    pattern = f'"{args.term}"' if args.term else None
    events = fetch_all(c, args.group, start, end, pattern)[: args.n]
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
    start, sdt = to_ms(args.start)
    end, edt = to_ms(args.end)
    groups = resolve_groups(c, args.group) if args.discover else [{"logGroupName": args.group}]
    if not groups:
        print(f"!! No log group matches '{args.group}'. Check the name/prefix (discover first).")
        return

    print("=== CLOUDWATCH SEARCH REPORT ===")
    print(f"Region : {args.region}")
    print(f"Window : {sdt:%Y-%m-%d %H:%M:%S} -> {edt:%Y-%m-%d %H:%M:%S} UTC  (end exclusive)")

    # Assemble the query. Required terms (term + context + --all) and exclusions
    # (--not) go into the SERVER filterPattern: `"a" "b" -"x"` is well-defined
    # (AND of required, minus excluded) and shrinks transfer. The --any OR-group
    # can't safely share one unstructured pattern with required terms, so it's
    # enforced CLIENT-side on the already-narrowed results. Net match:
    #   term AND context? AND all... AND (any-of ...) AND NOT excl...
    # The server pattern is always a SUPERSET filter, so it never drops a true match.
    required = [args.term] + ([args.context] if args.context else []) + args.all_terms
    excl, any_terms = args.excl, args.any_terms
    pattern = " ".join([f'"{t}"' for t in required] + [f'-"{t}"' for t in excl])

    qdesc = f"term={args.term!r}"
    if args.context:  qdesc += f" AND near={args.context!r}"
    qdesc += "".join(f" AND {t!r}" for t in args.all_terms)
    if any_terms:     qdesc += " AND (" + " OR ".join(repr(t) for t in any_terms) + ")"
    qdesc += "".join(f" AND NOT {t!r}" for t in excl)
    print(f"Query  : {qdesc}")
    print(f"Server : filterPattern={pattern!r}" + ("   (--any applied client-side)" if any_terms else ""))
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
        if any_terms:  # enforce the OR-group client-side on the narrowed set
            events = [e for e in events if any(t in e["message"] for t in any_terms)]
        buckets = {"real": [], "noise": [], "context-miss": []}
        for e in events:
            label, reason, snip = classify(e["message"], args.term, args.context, args.ctx_window)
            buckets[label].append((e["timestamp"], reason, snip, e.get("logStreamName", ""), e.get("eventId", "")))

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
                pc = len(fetch_all(c, name, start, end, f'"{args.probe}"'))
                verdict = ("TRUE NEGATIVE — probe present, so logging is active and the term is genuinely absent"
                           if pc > 0 else
                           "INCONCLUSIVE — probe also absent: wrong group, retention, or log level. NOT proof of absence")
                print(f"    SANITY: probe {args.probe!r} -> {pc} events => {verdict}")
            else:
                print("    SANITY: no --probe given. A zero here is 'no matches found', NOT proof it didn't happen. "
                      "Re-run with --probe <term-that-should-exist-if-logging-works>.")

    if args.link_html and link_rows:
        write_links_html(args.link_html, link_rows)
        print(f"\nClickable link(s) written to {args.link_html} — open the file and click "
              "(don't copy long URLs from the terminal; the wrap corrupts them).")


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
    f.add_argument("--term", required=True)
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

    args = p.parse_args()
    c = client(args.region)
    {"discover": cmd_discover, "sample": cmd_sample, "search": cmd_search}[args.cmd](c, args)


if __name__ == "__main__":
    main()
