# `slc-be-bitbucket` — Bitbucket

Skills for working with Bitbucket from the terminal, via the Bitbucket REST API.

## Skills

### `pr-review`

Review Bitbucket pull requests via the REST API — view, list, diff, read comments, and post
review comments. Does not approve or merge (those stay in the Bitbucket UI).

Requires `BITBUCKET_EMAIL` and `BITBUCKET_TOKEN` in the environment (Basic Auth with your
Atlassian email + an API token).
