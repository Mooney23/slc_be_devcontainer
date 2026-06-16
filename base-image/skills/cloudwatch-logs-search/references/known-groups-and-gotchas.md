# Known log groups & gotchas (growable)

This is accumulated, project-specific knowledge that makes searches faster and
safer. The skill works without it — but consult it before discovering groups
from scratch, and **append** anything you learn (new group, new format, a
retention surprise). Keep entries short and factual.

## Retention map (decides whether a window is even reachable)

- **`cloudv2*`** prod groups → **365-day** retention. Good for multi-month lookbacks.
- **`cloudv2a*`, `testv2*`, `demov2*`, `wip*`** → **1–30 day** retention. Useless for anything but recent windows. If your window is older, don't bother — `discover` will show the retention.

## Known groups (device service / ingestion)

| Group | What it logs | Notes |
|---|---|---|

(Add more as you find them: `device__nb_modules`, `device__generic_anomaly_creation_lambda`, `process_dd_alerts`, etc.)

## Log formats worth knowing

- Logs are **JSON** lines: `{"pathname":..., "lineno":..., "timestamp":"...Z", "level":"DEBUG", "org_slug":..., "app_message":"..."}`.
- **Alarm state writes** appear as `app_message: "Got kwargs: {'alarm_status': 'ACK', 'alarm_ids': [85634], ...}"` and `"Executing query: UPDATE alarm SET is_active = :is_active ... WHERE id IN :alarm_ids AND is_active = 1 with param {... 'alarm_ids': (85634,)}"`. So alarm ids are findable, but use `--context alarm_ids` to skip noise.
- `level` is DEBUG by default (`LOGGING_LEVEL` env unset → `DEBUG` in `shared/helper.py`). If a search comes back empty, confirm DEBUG wasn't overridden to INFO on that function for that period.

## Noise sources seen in practice (why classification matters)

- 

## The $26 lesson

A bare Logs Insights `@message like /85634/` across 7 high-volume ingestion groups over Mar–Jun scanned **5.26 TB ≈ $26**. Insights bills per GB scanned; `filter_log_events` does not. Default to `filter_log_events`; reserve Insights for true aggregation, smallest group, anchored filter, user-confirmed.

## Related

