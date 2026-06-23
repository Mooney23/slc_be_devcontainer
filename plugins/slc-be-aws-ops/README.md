# `slc-be-aws-ops` — AWS operations

Read-only, cost-safe skills for working with AWS from the terminal. Skills in this plugin are
designed to be at least as accurate as the AWS console, with guardrails against common mistakes
(cost surprises, wrong conclusions, missing results).

## Skills

### `cloudwatch-logs-search`

Safe, read-only CloudWatch Logs search via boto3. Searches log groups with built-in cost guards
(defaults to the free `filter_log_events` API, treats Logs Insights as a confirm-first exception),
classifies every hit as real vs. coincidental noise, and proves negatives rather than asserting
them. See [`skills/cloudwatch-logs-search/README.md`](skills/cloudwatch-logs-search/README.md)
for the full guide.
