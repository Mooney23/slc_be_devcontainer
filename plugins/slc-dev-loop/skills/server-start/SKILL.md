---
name: server-start
description: Start the Flask development server in a background tmux session. Use when the user asks to start, launch, or run the server, or says things like "spin up the app", "get the server going", or "run the backend".
---

Start the Flask development server in a background tmux session so it doesn't block the conversation.

## Determine the tmux session name

The session name is derived from the service name in the `.env` file so that multiple services can run side by side without collision. Run:

```bash
grep -m1 '^SLS_SERVICE_NAME=' .env | cut -d= -f2 | tr -d '"' || grep -m1 '^SLS_VA_SERVICE_NAME=' .env | cut -d= -f2 | tr -d '"'
```

Check for `SLS_SERVICE_NAME` first (most common), then fall back to `SLS_VA_SERVICE_NAME`. The tmux session name is `flask_<value>` (e.g., `SLS_SERVICE_NAME=devices` → `flask_devices`, `SLS_VA_SERVICE_NAME=org` → `flask_org`).

If neither variable is found in `.env`, tell the user that one of `SLS_SERVICE_NAME` or `SLS_VA_SERVICE_NAME` must be set and stop.

Store this value and use it as the tmux session name (`SESSION_NAME`) in every command below. Do NOT hardcode `flask_device` or any other fixed name.

## Pre-flight checks

Before starting anything, verify the `.env` file exists at the project root and contains all required variables. Read the `.env` file and check that each of the following variables is present and has a non-empty value:

- `EC2_HOST`
- `EC2_PRIVATE_KEY_PATH`
- `SERVICE_DB_URI`
- `ORG_SLUG`
- `ORG_UUID`
- `SUBORG_SLUG`
- `SUBORG_UUID`
- `COGNITO_UUID`
- `GIVEN_NAME`
- `ROLE_NAME`
- `LOCAL` — must be set to exactly `"True"`

If the `.env` file is missing, tell the user to create one. If any variables are missing or empty, list exactly which ones are missing so the user can fix them. If `LOCAL` is not `"True"`, flag that specifically — the server won't behave correctly in local development without it.

## Starting the server

1. Check if a tmux session named `SESSION_NAME` already exists:
   ```bash
   tmux has-session -t $SESSION_NAME 2>/dev/null
   ```
   If it does, the server is already running. Show the last 10 lines of its output, then skip ahead to **Verify the server and load the API spec**:
   ```bash
   tmux capture-pane -t $SESSION_NAME -p | tail -10
   ```

2. If no session exists, start one:
   ```bash
   tmux new-session -d -s $SESSION_NAME 'make run'
   ```

3. Wait briefly, then verify the session is alive:
   ```bash
   sleep 7 && tmux has-session -t $SESSION_NAME 2>/dev/null && echo "running" || echo "crashed"
   ```

4. If running, capture the startup output to show the user what Flask reported:
   ```bash
   tmux capture-pane -t $SESSION_NAME -p | tail -15
   ```
   This output will contain the actual URLs Flask is listening on (typically `http://127.0.0.1:5000` and the container's IP). Show these to the user as-is rather than guessing the URLs.

5. If the session crashed, grab the output and show what went wrong:
   ```bash
   tmux capture-pane -t $SESSION_NAME -p
   ```
   Look at the error output and help the user diagnose the issue. Do not proceed to the next step.

## Verify the server and load the API spec

Once the tmux session is alive, confirm the server is actually accepting HTTP requests by fetching the Swagger spec. This serves two purposes: it's a real health check (the tmux session can be alive while Flask is still initializing or has crashed internally), and it loads the full API surface into context so the user can immediately ask about available endpoints.

1. Poll until the Swagger spec endpoint responds (Flask may need a few seconds after tmux reports "running"):
   ```bash
   for i in 1 2 3 4 5; do
     STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/swagger.json --max-time 3)
     [ "$STATUS" = "200" ] && break
     sleep 2
   done
   echo "$STATUS"
   ```

2. If the status is `200`, fetch the full spec:
   ```bash
   curl -s http://127.0.0.1:5000/swagger.json
   ```
   Keep this spec in your context for the rest of the conversation — it contains every registered endpoint, supported HTTP methods, parameters, and request/response schemas. When the user asks about available endpoints or how to call something, refer to this spec rather than diving into the codebase.

3. After loading the spec, display the API surface as a markdown table. Run this command to generate it:
   ```bash
   curl -s http://127.0.0.1:5000/swagger.json | python3 -c "
   import json, sys
   spec = json.load(sys.stdin)
   paths = spec.get('paths', {})
   tags = {}
   for path, methods in paths.items():
       for method, details in methods.items():
           if method == 'parameters':
               continue
           for tag in details.get('tags', ['Other']):
               tags[tag] = tags.get(tag, 0) + 1
   total = sum(tags.values())
   sorted_tags = sorted(tags.items(), key=lambda x: -x[1])
   print(f'**API Surface: {total} endpoints across {len(tags)} resource groups**')
   print()
   print('| Resource Group | Endpoints |')
   print('|---|---|')
   for tag, count in sorted_tags:
       print(f'| {tag} | {count} |')
   "
   ```

   Show the output of this command exactly as printed — it is already valid markdown. Do NOT reformat, regroup, add columns, split into multiple tables, or editorialize the output in any way. Render it as-is.

4. If the swagger endpoint never returns `200`, the tmux session may be alive but Flask didn't start correctly. Fall back to reading the tmux pane output to diagnose the issue:
   ```bash
   tmux capture-pane -t $SESSION_NAME -p
   ```

Finally, remind the user:
- `tmux attach -t $SESSION_NAME` to view live server logs
- Ask me to stop the server when you're done
