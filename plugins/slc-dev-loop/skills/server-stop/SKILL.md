---
name: server-stop
description: Stop the Flask development server. Use when the user asks to stop, kill, or shut down the server, or says things like "take the server down", "turn off the backend", or "kill the flask app".
---

Stop the Flask development server gracefully. Sending SIGINT (Ctrl+C) first gives Flask a chance to close database connections and clean up SSH tunnels before the session is removed.

## Determine the tmux session name

The session name is derived from the service name in the `.env` file so that the correct service is stopped. Run:

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

2. If not running, tell the user the server is already stopped. Nothing to do.

3. If running, send Ctrl+C for a graceful shutdown:
   ```bash
   tmux send-keys -t $SESSION_NAME C-c
   ```

4. Wait a moment for Flask to finish its cleanup:
   ```bash
   sleep 2
   ```

5. Check if the session is still around and clean it up:
   ```bash
   tmux has-session -t $SESSION_NAME 2>/dev/null && tmux kill-session -t $SESSION_NAME && echo "session cleaned up" || echo "stopped"
   ```

6. Confirm everything is gone:
   ```bash
   tmux has-session -t $SESSION_NAME 2>/dev/null && echo "still running" || echo "stopped"
   ```
   If it stopped successfully, tell the user. If it's still running, let them know something went wrong and suggest manually running `tmux kill-session -t $SESSION_NAME`.
