# `slc-be-dev` — inner dev loop

Skills for the day-to-day local development workflow — running the Flask dev server and
exercising API endpoints against it.

## Skills

### `server-start`

Starts the Flask development server in a background tmux session so it doesn't block the
conversation. Session name is derived from the service name so multiple services can run
side by side.

### `server-stop`

Stops the Flask development server gracefully (SIGINT first, then session removal) to allow
clean shutdown of DB connections and SSH tunnels.

### `server-status`

Checks whether the Flask development server is running and shows its recent output.

### `server-request`

Makes HTTP requests against the local Flask server on your behalf. Uses the Swagger spec to
discover available endpoints and help construct valid requests. Always confirms request details
before sending.
