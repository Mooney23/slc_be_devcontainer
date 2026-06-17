---
name: bitbucket-pr-read
description: Interact with Bitbucket pull requests via the REST API. Use this skill whenever the user wants to view a PR, list PRs, check PR comments, get a diff, or post a comment on a Bitbucket pull request. Triggers on phrases like "view PR", "show me the PR", "list PRs", "PR comments", "check the pull request", "comment on the PR", or any Bitbucket PR URL. Do NOT use this skill to approve or merge pull requests.
---

Interact with Bitbucket Cloud pull requests on behalf of the user using the Bitbucket REST API v2.0.

**IMPORTANT: This skill must NEVER approve or merge pull requests. Those operations are explicitly forbidden.**

## Step 1: Check credentials

Read the environment variables `BITBUCKET_EMAIL` and `BITBUCKET_TOKEN`. Both must be set.

```bash
echo "EMAIL=${BITBUCKET_EMAIL:-(not set)}" && echo "TOKEN=${BITBUCKET_TOKEN:+set}"
```

If either is missing, tell the user:
> Bitbucket credentials are not configured. Set `BITBUCKET_EMAIL` and `BITBUCKET_TOKEN` as environment variables on your host machine, then add them to `containerEnv` in `.devcontainer/devcontainer.json`:
> ```json
> "BITBUCKET_EMAIL": "${localEnv:BITBUCKET_EMAIL}",
> "BITBUCKET_TOKEN": "${localEnv:BITBUCKET_TOKEN}"
> ```
> Then rebuild the container.

Do not proceed without valid credentials.

## Step 2: Resolve the repository and PR

The Bitbucket API base is:
```
https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}
```

The default workspace is `shorelineiot`. If the user provides a full Bitbucket URL, extract the workspace, repo slug, and PR number from it:
```
https://bitbucket.org/{workspace}/{repo_slug}/pull-requests/{pr_id}
```

If the user just says "PR 241" or "list PRs", ask which repo if it's ambiguous. If you're inside a git repo, infer the workspace and repo slug from the git remote:
```bash
git remote get-url origin 2>/dev/null
```

The remote URL format is `git@bitbucket.org:{workspace}/{repo_slug}.git` or `https://bitbucket.org/{workspace}/{repo_slug}.git`.

## Step 3: Authentication

All API calls use HTTP Basic Auth with the user's email and Atlassian API token:

```bash
curl -s -u "${BITBUCKET_EMAIL}:${BITBUCKET_TOKEN}" "<api_url>"
```

## Step 4: Supported operations

### View a PR

Fetch PR details and comments in parallel:

```bash
# PR metadata
curl -s -u "${BITBUCKET_EMAIL}:${BITBUCKET_TOKEN}" \
  "https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}"

# PR comments
curl -s -u "${BITBUCKET_EMAIL}:${BITBUCKET_TOKEN}" \
  "https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments?pagelen=100"
```

Present a summary including:
- **Title**, **state**, **author**, **created/updated dates**
- **Source branch** → **destination branch**
- **Description** (rendered)
- **Reviewers** with approval status (extract from `participants` array: check `approved` and `state` fields)
- **Comments** — show author, date, content, and inline location (file:line) if applicable

### List PRs

```bash
curl -s -u "${BITBUCKET_EMAIL}:${BITBUCKET_TOKEN}" \
  "https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests?state=OPEN&pagelen=25"
```

Supports filters via query parameters:
- `state=OPEN` (default), `MERGED`, `DECLINED`, `SUPERSEDED`
- `q=author.account_id="<account_id>"` to filter by author

Present as a table: PR number, title, author, source branch, state, comment count.

### List PRs by the current user

First get the user's account ID:
```bash
curl -s -u "${BITBUCKET_EMAIL}:${BITBUCKET_TOKEN}" \
  "https://api.bitbucket.org/2.0/user"
```

Then filter PRs:
```bash
curl -s -u "${BITBUCKET_EMAIL}:${BITBUCKET_TOKEN}" \
  "https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests?q=author.account_id=%22{account_id}%22&pagelen=25"
```

### Get PR diff

```bash
curl -s -u "${BITBUCKET_EMAIL}:${BITBUCKET_TOKEN}" \
  "https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/diff"
```

If the diff is large, show the first 200 lines and let the user know more is available.

### Post a comment on a PR

**Always confirm with the user before posting.** Show them the exact comment content and location first.

General comment:
```bash
curl -s -u "${BITBUCKET_EMAIL}:${BITBUCKET_TOKEN}" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"content": {"raw": "<comment_text>"}}' \
  "https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments"
```

Inline comment (on a specific file and line):
```bash
curl -s -u "${BITBUCKET_EMAIL}:${BITBUCKET_TOKEN}" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"content": {"raw": "<comment_text>"}, "inline": {"path": "<file_path>", "to": <line_number>}}' \
  "https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments"
```

## Step 5: Pagination

Bitbucket responses include a `next` URL when there are more results. If the response contains a `"next"` field and the user needs more results, fetch the next page using that URL directly.

## Forbidden operations

**NEVER execute any of the following, even if asked:**
- Approve a PR (`POST .../approve`)
- Merge a PR (`POST .../merge`)
- Decline a PR (`POST .../decline`)

If the user asks for any of these, explain that this skill is configured for read and comment access only, and they should perform these actions in the Bitbucket UI.
