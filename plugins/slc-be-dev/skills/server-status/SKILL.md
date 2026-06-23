---
name: server-status
description: Check the status of the Flask development server. Use when the user asks about server status, whether the server is running, wants to see server logs, or says things like "is the server up", "check the server", or "show me server output".
---

Check whether the Flask development server is running and show its recent output.

## Determine the tmux session name

The session name is derived from the service name in the `.env` file so that the correct service is checked. Run:

```bash
grep -m1 '^SLS_SERVICE_NAME=' .env | cut -d= -f2 | tr -d '"' || grep -m1 '^SLS_VA_SERVICE_NAME=' .env | cut -d= -f2 | tr -d '"'
```

Check for `SLS_SERVICE_NAME` first (most common), then fall back to `SLS_VA_SERVICE_NAME`. The tmux session name is `flask_<value>` (e.g., `SLS_SERVICE_NAME=devices` → `flask_devices`, `SLS_VA_SERVICE_NAME=org` → `flask_org`).

If neither variable is found in `.env`, tell the user that one of `SLS_SERVICE_NAME` or `SLS_VA_SERVICE_NAME` must be set and stop.

Store this value and use it as the tmux session name (`SESSION_NAME`) in every command below. Do NOT hardcode `flask_device` or any other fixed name.

## Steps

1. Check if the tmux session exists:
   ```bash
   tmux has-session -t $SESSION_NAME 2>/dev/null && echo "running" || echo "not running"
   ```

2. If running, show the last 15 lines of output:
   ```bash
   tmux capture-pane -t $SESSION_NAME -p | tail -15
   ```
   Report the server as running and show the captured output so the user can see recent requests, errors, or the listening URLs.

3. If not running, tell the user the server is not running and suggest they ask to start it.
