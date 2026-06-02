# GitHub Actions PR Event Payloads — Complete Reference for AI Code Review Agents

> **Document Type:** Technical Reference  
> **Audience:** Development teams building AI-powered code review agents  
> **Last Updated:** 2026-06-01  
> **Sources:** GitHub Official Docs, GitHub REST API v3, GitHub Actions Toolkit, Community Best Practices

---

## Table of Contents

1. [Overview & Quick Reference](#1-overview--quick-reference)
2. [The `github.event.pull_request` Payload — Complete Schema](#2-the-githubeventpull_request-payload--complete-schema)
3. [The `github.event` Object for `pull_request` Triggers](#3-the-githubevent-object-for-pull_request-triggers)
4. [The `github` Context Object — Full Reference](#4-the-github-context-object--full-reference)
5. [Accessing Payloads from Python in Actions](#5-accessing-payloads-from-python-in-actions)
6. [`pull_request` vs `pull_request_target` — Security Deep Dive](#6-pull_request-vs-pull_request_target--security-deep-dive)
7. [Practical Patterns for AI Code Review Agents](#7-practical-patterns-for-ai-code-review-agents)
8. [Appendix: Environment Variable Mapping](#8-appendix-environment-variable-mapping)

---

## 1. Overview & Quick Reference

When a GitHub Actions workflow triggers on a `pull_request` event, three layers of context data become available:

| Layer | Access Pattern | What It Contains |
|-------|---------------|------------------|
| **Webhook Payload** | `github.event` | The full webhook event payload (same as `GITHUB_EVENT_PATH` file) |
| **Pull Request Object** | `github.event.pull_request` | The PR-specific subset: title, body, head/base refs, user, labels, etc. |
| **GitHub Context** | `github.*` | Workflow metadata: repo, sha, ref, actor, workflow name, run ID, etc. |

**Key Environment Variables:**

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `GITHUB_EVENT_PATH` | Path to JSON payload file | `/github/workflow/event.json` |
| `GITHUB_EVENT_NAME` | Event type | `pull_request` |
| `GITHUB_TOKEN` | Auth token for API calls | `ghs_xxxxxxxxxxxx` |
| `GITHUB_REPOSITORY` | `owner/repo` | `myorg/myrepo` |
| `GITHUB_REF` | Git ref | `refs/pull/42/merge` |
| `GITHUB_SHA` | Commit SHA | `abc123...` |
| `GITHUB_ACTOR` | User who triggered | `octocat` |
| `GITHUB_WORKFLOW` | Workflow name | `CI` |
| `GITHUB_RUN_ID` | Unique run ID | `1234567890` |
| `GITHUB_API_URL` | API base URL | `https://api.github.com` |

---

## 2. The `github.event.pull_request` Payload — Complete Schema

The `pull_request` object within the event payload contains the full Pull Request resource as defined by the GitHub REST API. Below is the complete field structure with descriptions, types, and AI-agent-relevant notes.

### 2.1 Top-Level Fields

```json
{
  "action": "opened",
  "number": 42,
  "pull_request": { /* ... see below ... */ },
  "repository": { /* Repository object */ },
  "sender": { /* User object */ },
  "installation": { /* App installation object (if applicable) */ }
}
```

| Field | Type | Description | AI Agent Relevance |
|-------|------|-------------|-------------------|
| `action` | `string` | Activity type: `opened`, `closed`, `reopened`, `synchronize`, `edited`, `labeled`, `unlabeled`, `assigned`, `unassigned`, `review_requested`, `review_request_removed`, `ready_for_review`, `converted_to_draft`, `locked`, `unlocked`, `enqueued`, `dequeued` | **Critical** — determines what logic to run. `synchronize` = new commits pushed. `edited` = title/body changed. |
| `number` | `integer` | PR number (e.g., `#42`) | Use for API calls, comments, status checks. |
| `pull_request` | `object` | The full PR resource | **Core data source** — see §2.2. |
| `repository` | `object` | Repository where PR was opened | Context for repo-specific rules. |
| `sender` | `object` | User who triggered the event | Attribution, filtering by author. |
| `installation` | `object` | GitHub App installation (if event from an App) | Needed for App-based agents. |

### 2.2 The `pull_request` Object — Complete Field Map

```json
{
  "url": "https://api.github.com/repos/octocat/Hello-World/pulls/42",
  "id": 1,
  "node_id": "MDExOlB1bGxSZXF1ZXN0MQ==",
  "html_url": "https://github.com/octocat/Hello-World/pull/42",
  "diff_url": "https://github.com/octocat/Hello-World/pull/42.diff",
  "patch_url": "https://github.com/octocat/Hello-World/pull/42.patch",
  "issue_url": "https://api.github.com/repos/octocat/Hello-World/issues/42",
  "number": 42,
  "state": "open",
  "locked": false,
  "title": "Add feature X",
  "user": { /* User object — see §2.3 */ },
  "body": "## Description\n\nThis PR adds...",
  "created_at": "2026-05-15T10:00:00Z",
  "updated_at": "2026-05-15T12:00:00Z",
  "closed_at": null,
  "merged_at": null,
  "merge_commit_sha": "e5bd3914e2e596debea16f433f57875b5b895cbc",
  "assignee": { /* User object or null */ },
  "assignees": [ /* Array of User objects */ ],
  "requested_reviewers": [ /* Array of User objects */ ],
  "requested_teams": [ /* Array of Team objects */ ],
  "labels": [ /* Array of Label objects */ ],
  "milestone": { /* Milestone object or null */ },
  "draft": false,
  "commits_url": "https://api.github.com/repos/octocat/Hello-World/pulls/42/commits",
  "review_comments_url": "https://api.github.com/repos/octocat/Hello-World/pulls/42/comments",
  "review_comment_url": "https://api.github.com/repos/octocat/Hello-World/pulls/comments{/number}",
  "comments_url": "https://api.github.com/repos/octocat/Hello-World/issues/42/comments",
  "statuses_url": "https://api.github.com/repos/octocat/Hello-World/statuses/abc123",
  "head": { /* Branch reference — see §2.4 */ },
  "base": { /* Branch reference — see §2.4 */ },
  "_links": {
    "self": { "href": "..." },
    "html": { "href": "..." },
    "issue": { "href": "..." },
    "comments": { "href": "..." },
    "review_comments": { "href": "..." },
    "review_comment": { "href": "..." },
    "commits": { "href": "..." },
    "statuses": { "href": "..." }
  },
  "author_association": "OWNER",
  "auto_merge": null,
  "active_lock_reason": null,
  "merged": false,
  "mergeable": true,
  "rebaseable": true,
  "mergeable_state": "clean",
  "merged_by": { /* User object or null */ },
  "comments": 0,
  "review_comments": 0,
  "maintainer_can_modify": false,
  "commits": 3,
  "additions": 100,
  "deletions": 50,
  "changed_files": 5
}
```

#### Field Descriptions — AI Agent Relevance

| Field | Type | Description | AI Agent Notes |
|-------|------|-------------|----------------|
| `url` | `string` | API URL for this PR | Use for direct API calls. |
| `id` | `integer` | Global PR ID | Internal identifier. |
| `node_id` | `string` | GraphQL node ID | For GraphQL API queries. |
| `html_url` | `string` | Human-readable URL | For linking in comments/reports. |
| `diff_url` | `string` | Raw diff URL | **Fetch this** for code analysis. |
| `patch_url` | `string` | Raw patch URL | Alternative to diff. |
| `issue_url` | `string` | Associated issue API URL | PRs are also issues — comments go here. |
| `number` | `integer` | PR number | Primary identifier for API calls. |
| `state` | `string` | `open`, `closed` | Filter logic — skip closed PRs. |
| `locked` | `boolean` | Is PR locked? | Skip if locked (can't comment). |
| `title` | `string` | PR title | **Analyze** for intent/context. |
| `user` | `object` | PR author | See §2.3 — filter by author, check permissions. |
| `body` | `string` | PR description (markdown) | **Analyze** for requirements, linked issues. |
| `created_at` | `string` (ISO 8601) | Creation timestamp | Age metrics, SLA tracking. |
| `updated_at` | `string` (ISO 8601) | Last update timestamp | Detect stale PRs. |
| `closed_at` | `string` or `null` | Close timestamp | Closure analytics. |
| `merged_at` | `string` or `null` | Merge timestamp | Merge analytics. |
| `merge_commit_sha` | `string` or `null` | SHA of merge commit | Reference for post-merge checks. |
| `assignee` | `object` or `null` | Primary assignee | Routing logic. |
| `assignees` | `array` | All assignees | Team workload distribution. |
| `requested_reviewers` | `array` | Requested individual reviewers | Check if AI agent should be one. |
| `requested_teams` | `array` | Requested team reviewers | Team routing. |
| `labels` | `array` | Labels | **Filter/skip** based on labels (e.g., `wip`, `draft`). |
| `milestone` | `object` or `null` | Milestone | Sprint/release tracking. |
| `draft` | `boolean` | Is draft PR? | Often skip drafts unless configured. |
| `commits_url` | `string` | API URL for commits | Fetch commit list for analysis. |
| `review_comments_url` | `string` | API URL for review comments | Post review comments here. |
| `comments_url` | `string` | API URL for issue comments | Post general comments here. |
| `statuses_url` | `string` | API URL for commit statuses | Set commit status checks. |
| `head` | `object` | Source branch | See §2.4 — the branch being merged FROM. |
| `base` | `object` | Target branch | See §2.4 — the branch being merged INTO. |
| `author_association` | `string` | Author's relationship to repo: `OWNER`, `COLLABORATOR`, `MEMBER`, `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR`, `FIRST_TIMER`, `NONE` | **Trust scoring** — treat external contributors differently. |
| `auto_merge` | `object` or `null` | Auto-merge settings | Check if auto-merge is enabled. |
| `merged` | `boolean` | Is PR merged? | State machine logic. |
| `mergeable` | `boolean` | Can be merged? | Gate check before auto-approval. |
| `rebaseable` | `boolean` | Can be rebased? | Rebase strategy decisions. |
| `mergeable_state` | `string` | `clean`, `dirty`, `unstable`, `blocked`, `behind`, `draft`, `unknown` | **Critical** — `clean` = safe to merge. |
| `merged_by` | `object` or `null` | Who merged it | Audit trail. |
| `comments` | `integer` | Comment count | Engagement metric. |
| `review_comments` | `integer` | Review comment count | Existing review activity. |
| `maintainer_can_modify` | `boolean` | Can maintainers push to PR branch | Fork PRs — affects auto-fix capability. |
| `commits` | `integer` | Number of commits | Scope estimation. |
| `additions` | `integer` | Lines added | Change size metric. |
| `deletions` | `integer` | Lines deleted | Change size metric. |
| `changed_files` | `integer` | Files changed | Scope estimation. |

### 2.3 The `user` Object (PR Author)

```json
{
  "login": "octocat",
  "id": 1,
  "node_id": "MDQ6VXNlcjE=",
  "avatar_url": "https://github.com/images/error/octocat_happy.gif",
  "gravatar_id": "",
  "url": "https://api.github.com/users/octocat",
  "html_url": "https://github.com/octocat",
  "type": "User",
  "site_admin": false
}
```

| Field | AI Agent Relevance |
|-------|-------------------|
| `login` | Username for attribution, allowlists, blocklists. |
| `id` | Stable user identifier. |
| `type` | `User` vs `Bot` — skip bot PRs or handle differently. |
| `site_admin` | GitHub staff — special handling if needed. |

### 2.4 The `head` and `base` Branch References

```json
{
  "label": "octocat:new-feature",
  "ref": "new-feature",
  "sha": "6dcb09b5b57875f334f61aebed695e2e4193db5e",
  "user": { /* User object */ },
  "repo": { /* Repository object — see below */ }
}
```

| Field | Description | AI Agent Relevance |
|-------|-------------|-------------------|
| `label` | Full branch label (`user:branch`) | Display purposes. |
| `ref` | Branch name | Git operations, checkout. |
| `sha` | Commit SHA | **Exact commit to analyze** — `head.sha` is the PR tip. |
| `user` | Branch owner | For fork PRs, the fork owner. |
| `repo` | Repository object | For fork PRs, the fork repo. |

**The `repo` sub-object (within head/base):**

```json
{
  "id": 1296269,
  "node_id": "MDEwOlJlcG9zaXRvcnkxMjk2MjY5",
  "name": "Hello-World",
  "full_name": "octocat/Hello-World",
  "private": false,
  "owner": { /* User object */ },
  "html_url": "https://github.com/octocat/Hello-World",
  "description": "This your first repo!",
  "fork": false,
  "url": "https://api.github.com/repos/octocat/Hello-World",
  "created_at": "2011-01-26T19:01:12Z",
  "updated_at": "2011-01-26T19:14:43Z",
  "pushed_at": "2011-01-26T19:06:43Z",
  "homepage": "https://github.com",
  "size": 108,
  "stargazers_count": 80,
  "watchers_count": 80,
  "language": null,
  "has_issues": true,
  "has_projects": true,
  "has_downloads": true,
  "has_wiki": true,
  "has_pages": false,
  "has_discussions": false,
  "forks_count": 9,
  "mirror_url": null,
  "archived": false,
  "disabled": false,
  "open_issues_count": 0,
  "license": { /* License object */ },
  "allow_forking": true,
  "is_template": false,
  "web_commit_signoff_required": false,
  "topics": ["octocat", "atom", "electron", "api"],
  "visibility": "public",
  "forks": 9,
  "open_issues": 0,
  "watchers": 80,
  "default_branch": "main"
}
```

### 2.5 The `label` Object (within `labels` array)

```json
{
  "id": 208045946,
  "node_id": "MDU6TGFiZWwyMDgwNDU5NDY=",
  "url": "https://api.github.com/repos/octocat/Hello-World/labels/bug",
  "name": "bug",
  "description": "Something isn't working",
  "color": "d73a4a",
  "default": true
}
```

### 2.6 The `requested_team` Object

```json
{
  "id": 1,
  "node_id": "MDQ6VGVhbTE=",
  "url": "https://api.github.com/organizations/1/team/1",
  "html_url": "https://github.com/orgs/github/teams/justice-league",
  "name": "Justice League",
  "slug": "justice-league",
  "description": "A great team.",
  "privacy": "closed",
  "notification_setting": "notifications_enabled",
  "permission": "admin",
  "members_url": "https://api.github.com/organizations/1/team/1/members{/member}",
  "repositories_url": "https://api.github.com/organizations/1/team/1/repos"
}
```

---

## 3. The `github.event` Object for `pull_request` Triggers

Beyond `pull_request`, the `github.event` object contains the **entire webhook payload**. The exact shape varies by `action` type.

### 3.1 Common Top-Level Event Fields

```json
{
  "action": "opened",
  "number": 42,
  "pull_request": { /* ... */ },
  "repository": { /* Repository object */ },
  "sender": { /* User object */ },
  "installation": { /* App installation */ },
  "organization": { /* Organization object (if applicable) */ }
}
```

### 3.2 Action-Specific Additional Fields

| Action | Extra Fields | Description |
|--------|-------------|-------------|
| `synchronize` | None (same as base) | Triggered when PR branch is updated (new commits pushed). |
| `edited` | `changes` | Contains `title` (from/to), `body` (from/to) if edited. |
| `labeled` / `unlabeled` | `label` | The label that was added/removed. |
| `assigned` / `unassigned` | `assignee` | The user assigned/unassigned. |
| `review_requested` / `review_request_removed` | `requested_reviewer` | The reviewer requested/removed. |
| `closed` | `pull_request.merged` | `true` if merged, `false` if closed without merge. |

### 3.3 The `changes` Object (for `edited` action)

```json
{
  "action": "edited",
  "number": 42,
  "changes": {
    "title": {
      "from": "Old title"
    },
    "body": {
      "from": "Old description"
    }
  },
  "pull_request": { /* ... */ }
}
```

**AI Agent Note:** When `action == "edited"`, check `changes` to see what was modified. Re-analyze if the body changed significantly.

### 3.4 The `repository` Object (in `github.event.repository`)

```json
{
  "id": 1296269,
  "node_id": "MDEwOlJlcG9zaXRvcnkxMjk2MjY5",
  "name": "Hello-World",
  "full_name": "octocat/Hello-World",
  "owner": { /* User object */ },
  "private": false,
  "html_url": "https://github.com/octocat/Hello-World",
  "description": "...",
  "fork": false,
  "url": "https://api.github.com/repos/octocat/Hello-World",
  "created_at": "2011-01-26T19:01:12Z",
  "updated_at": "2011-01-26T19:14:43Z",
  "pushed_at": "2011-01-26T19:06:43Z",
  "homepage": "https://github.com",
  "size": 108,
  "stargazers_count": 80,
  "watchers_count": 80,
  "language": null,
  "has_issues": true,
  "has_projects": true,
  "has_downloads": true,
  "has_wiki": true,
  "has_pages": false,
  "has_discussions": false,
  "forks_count": 9,
  "mirror_url": null,
  "archived": false,
  "disabled": false,
  "open_issues_count": 0,
  "license": { /* License object */ },
  "allow_forking": true,
  "is_template": false,
  "web_commit_signoff_required": false,
  "topics": [],
  "visibility": "public",
  "forks": 9,
  "open_issues": 0,
  "watchers": 80,
  "default_branch": "main"
}
```

### 3.5 The `sender` Object (Event Trigger User)

Same structure as `user` (§2.3). Note: `sender` may differ from `pull_request.user` — e.g., when a bot triggers the event or when someone else pushes commits to the PR branch.

---

## 4. The `github` Context Object — Full Reference

The `github` context is available in workflow expressions (`${{ github.xxx }}`) and contains metadata about the workflow run and the repository.

### 4.1 Complete Field List

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `github.action` | `string` | Name of the current action, or `__run` for workflow commands | `my-action` |
| `github.action_path` | `string` | Path where the action is defined | `/home/runner/work/_actions/owner/repo/v1` |
| `github.action_ref` | `string` | Ref of the action (for reusable workflows) | `v1` |
| `github.action_repository` | `string` | Repo of the action | `owner/repo` |
| `github.actor` | `string` | Username of the user/bot that triggered the run | `octocat` |
| `github.actor_id` | `string` | Numeric ID of the actor | `1234567` |
| `github.api_url` | `string` | GitHub API URL | `https://api.github.com` |
| `github.base_ref` | `string` | Base ref for PRs (target branch) | `main` |
| `github.env` | `string` | Path to env file for workflow commands | `/home/runner/work/_temp/_runner_file_commands/set_env...` |
| `github.event` | `object` | Full event payload | See §2-3 |
| `github.event_name` | `string` | Event name | `pull_request` |
| `github.event_path` | `string` | Path to event JSON file | `/home/runner/work/_temp/_github_workflow/event.json` |
| `github.graphql_url` | `string` | GitHub GraphQL API URL | `https://api.github.com/graphql` |
| `github.head_ref` | `string` | Head ref for PRs (source branch) | `feature-branch` |
| `github.job` | `string` | Current job ID | `build` |
| `github.path` | `string` | Path to PATH file for workflow commands | `/home/runner/work/_temp/_runner_file_commands/add_path...` |
| `github.ref` | `string` | Full ref | `refs/pull/42/merge` |
| `github.ref_name` | `string` | Short ref name | `42/merge` |
| `github.ref_protected` | `boolean` | Is ref protected? | `false` |
| `github.ref_type` | `string` | `branch`, `tag`, or `tree` | `branch` |
| `github.repository` | `string` | Owner/repo | `octocat/Hello-World` |
| `github.repository_id` | `string` | Numeric repo ID | `1296269` |
| `github.repository_owner` | `string` | Owner name | `octocat` |
| `github.repository_owner_id` | `string` | Numeric owner ID | `1` |
| `github.repositoryUrl` | `string` | Git URL | `git://github.com/octocat/Hello-World.git` |
| `github.retention_days` | `string` | Artifact retention days | `90` |
| `github.run_id` | `string` | Unique run ID | `1234567890` |
| `github.run_number` | `string` | Run number (per-workflow, increments) | `42` |
| `github.run_attempt` | `string` | Attempt number (for re-runs) | `1` |
| `github.secret_source` | `string` | `Actions` or `None` | `Actions` |
| `github.server_url` | `string` | GitHub server URL | `https://github.com` |
| `github.sha` | `string` | Commit SHA | `abc123...` |
| `github.token` | `string` | GITHUB_TOKEN value | `ghs_xxx...` |
| `github.triggering_actor` | `string` | User who triggered (may differ from actor on re-runs) | `octocat` |
| `github.workflow` | `string` | Workflow name | `CI` |
| `github.workflow_ref` | `string` | Full workflow ref | `octocat/Hello-World/.github/workflows/ci.yml@refs/heads/main` |
| `github.workflow_sha` | `string` | SHA of workflow file | `def456...` |
| `github.workspace` | `string` | Working directory | `/home/runner/work/Hello-World/Hello-World` |

### 4.2 PR-Specific Context Fields

For `pull_request` events, these fields are particularly useful:

| Expression | Value | Use Case |
|-----------|-------|----------|
| `${{ github.head_ref }}` | `feature-branch` | Checkout the PR branch |
| `${{ github.base_ref }}` | `main` | Compare against target |
| `${{ github.ref }}` | `refs/pull/42/merge` | The merge ref GitHub creates |
| `${{ github.sha }}` | `abc123...` | The merge commit SHA (not the PR tip!) |
| `${{ github.event.pull_request.number }}` | `42` | PR number for API calls |
| `${{ github.event.pull_request.head.sha }}` | `def456...` | The actual PR tip commit |

**⚠️ Critical Distinction:** `github.sha` in a `pull_request` event is the **merge commit SHA** (`refs/pull/42/merge`), NOT the PR branch tip. For the actual PR branch tip, use `github.event.pull_request.head.sha`.

---

## 5. Accessing Payloads from Python in Actions

### 5.1 Reading the Event Payload File

The `GITHUB_EVENT_PATH` environment variable points to a JSON file containing the full webhook payload.

```python
import json
import os

def load_event_payload() -> dict:
    """Load the GitHub Actions event payload from GITHUB_EVENT_PATH."""
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise RuntimeError("GITHUB_EVENT_PATH not set — not running in GitHub Actions?")
    
    with open(event_path, "r", encoding="utf-8") as f:
        return json.load(f)

# Usage
payload = load_event_payload()
pr = payload.get("pull_request", {})
print(f"PR #{pr.get('number')}: {pr.get('title')}")
```

### 5.2 Using the `github` Context via Environment Variables

All `github` context fields are also available as environment variables (prefixed with `GITHUB_` and uppercased):

```python
import os

# Direct environment variable access
repo = os.environ.get("GITHUB_REPOSITORY")        # "owner/repo"
event_name = os.environ.get("GITHUB_EVENT_NAME")   # "pull_request"
sha = os.environ.get("GITHUB_SHA")                # merge commit SHA
ref = os.environ.get("GITHUB_REF")                  # "refs/pull/42/merge"
actor = os.environ.get("GITHUB_ACTOR")              # "octocat"
workflow = os.environ.get("GITHUB_WORKFLOW")        # "CI"
run_id = os.environ.get("GITHUB_RUN_ID")            # "1234567890"
api_url = os.environ.get("GITHUB_API_URL")          # "https://api.github.com"
token = os.environ.get("GITHUB_TOKEN")              # "ghs_xxx..."
workspace = os.environ.get("GITHUB_WORKSPACE")      # "/home/runner/work/..."
```

### 5.3 Complete Python Helper Module for AI Agents

```python
"""
GitHub Actions PR Payload Utilities for AI Code Review Agents
"""

import json
import os
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class PullRequestPayload:
    """Structured access to pull_request event payload."""
    
    raw: Dict[str, Any]
    
    @property
    def action(self) -> str:
        return self.raw.get("action", "")
    
    @property
    def number(self) -> int:
        return self.raw.get("number", 0)
    
    @property
    def pr(self) -> Dict[str, Any]:
        return self.raw.get("pull_request", {})
    
    @property
    def title(self) -> str:
        return self.pr.get("title", "")
    
    @property
    def body(self) -> str:
        return self.pr.get("body", "")
    
    @property
    def state(self) -> str:
        return self.pr.get("state", "")
    
    @property
    def is_draft(self) -> bool:
        return self.pr.get("draft", False)
    
    @property
    def is_merged(self) -> bool:
        return self.pr.get("merged", False)
    
    @property
    def mergeable_state(self) -> str:
        return self.pr.get("mergeable_state", "unknown")
    
    @property
    def head_sha(self) -> str:
        return self.pr.get("head", {}).get("sha", "")
    
    @property
    def base_sha(self) -> str:
        return self.pr.get("base", {}).get("sha", "")
    
    @property
    def head_ref(self) -> str:
        return self.pr.get("head", {}).get("ref", "")
    
    @property
    def base_ref(self) -> str:
        return self.pr.get("base", {}).get("ref", "")
    
    @property
    def author_login(self) -> str:
        return self.pr.get("user", {}).get("login", "")
    
    @property
    def author_association(self) -> str:
        return self.pr.get("author_association", "")
    
    @property
    def additions(self) -> int:
        return self.pr.get("additions", 0)
    
    @property
    def deletions(self) -> int:
        return self.pr.get("deletions", 0)
    
    @property
    def changed_files(self) -> int:
        return self.pr.get("changed_files", 0)
    
    @property
    def labels(self) -> List[str]:
        return [label.get("name", "") for label in self.pr.get("labels", [])]
    
    @property
    def html_url(self) -> str:
        return self.pr.get("html_url", "")
    
    @property
    def diff_url(self) -> str:
        return self.pr.get("diff_url", "")
    
    @property
    def commits_url(self) -> str:
        return self.pr.get("commits_url", "")
    
    @property
    def review_comments_url(self) -> str:
        return self.pr.get("review_comments_url", "")
    
    @property
    def comments_url(self) -> str:
        return self.pr.get("comments_url", "")
    
    @property
    def requested_reviewers(self) -> List[str]:
        return [r.get("login", "") for r in self.pr.get("requested_reviewers", [])]
    
    def has_label(self, label_name: str) -> bool:
        return label_name in self.labels
    
    def is_external_contributor(self) -> bool:
        return self.author_association not in ("OWNER", "COLLABORATOR", "MEMBER")


class GitHubContext:
    """Access to the GitHub Actions context."""
    
    def __init__(self):
        self.payload = self._load_payload()
        self.pr = PullRequestPayload(self.payload) if self.event_name == "pull_request" else None
    
    @staticmethod
    def _load_payload() -> Dict[str, Any]:
        path = os.environ.get("GITHUB_EVENT_PATH", "/github/workflow/event.json")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    @property
    def event_name(self) -> str:
        return os.environ.get("GITHUB_EVENT_NAME", "")
    
    @property
    def repository(self) -> str:
        return os.environ.get("GITHUB_REPOSITORY", "")
    
    @property
    def sha(self) -> str:
        return os.environ.get("GITHUB_SHA", "")
    
    @property
    def ref(self) -> str:
        return os.environ.get("GITHUB_REF", "")
    
    @property
    def actor(self) -> str:
        return os.environ.get("GITHUB_ACTOR", "")
    
    @property
    def workflow(self) -> str:
        return os.environ.get("GITHUB_WORKFLOW", "")
    
    @property
    def run_id(self) -> str:
        return os.environ.get("GITHUB_RUN_ID", "")
    
    @property
    def api_url(self) -> str:
        return os.environ.get("GITHUB_API_URL", "https://api.github.com")
    
    @property
    def token(self) -> str:
        return os.environ.get("GITHUB_TOKEN", "")
    
    @property
    def workspace(self) -> str:
        return os.environ.get("GITHUB_WORKSPACE", "")
    
    @property
    def server_url(self) -> str:
        return os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    
    def get_auth_header(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }


# Convenience singleton
_ctx: Optional[GitHubContext] = None

def get_context() -> GitHubContext:
    global _ctx
    if _ctx is None:
        _ctx = GitHubContext()
    return _ctx


# Example usage
if __name__ == "__main__":
    ctx = get_context()
    
    if ctx.pr:
        print(f"PR #{ctx.pr.number}: {ctx.pr.title}")
        print(f"Author: {ctx.pr.author_login} ({ctx.pr.author_association})")
        print(f"Branch: {ctx.pr.head_ref} -> {ctx.pr.base_ref}")
        print(f"Changes: +{ctx.pr.additions}/-{ctx.pr.deletions} in {ctx.pr.changed_files} files")
        print(f"Labels: {ctx.pr.labels}")
        print(f"Draft: {ctx.pr.is_draft}")
        print(f"External: {ctx.pr.is_external_contributor()}")
        print(f"Diff URL: {ctx.pr.diff_url}")
```

### 5.4 Making Authenticated API Calls

```python
import requests
from github_context import get_context  # from above

ctx = get_context()
headers = ctx.get_auth_header()

# Get PR details
pr_url = f"{ctx.api_url}/repos/{ctx.repository}/pulls/{ctx.pr.number}"
response = requests.get(pr_url, headers=headers)
pr_data = response.json()

# Get changed files
files_url = f"{ctx.api_url}/repos/{ctx.repository}/pulls/{ctx.pr.number}/files"
files_response = requests.get(files_url, headers=headers)
changed_files = files_response.json()

# Post a review comment
comment_url = f"{ctx.api_url}/repos/{ctx.repository}/pulls/{ctx.pr.number}/reviews"
review_payload = {
    "body": "AI Code Review: No issues found! 🎉",
    "event": "COMMENT",  # or "APPROVE", "REQUEST_CHANGES"
    "comments": [
        {
            "path": "src/main.py",
            "line": 42,
            "side": "RIGHT",
            "body": "Consider adding a type hint here."
        }
    ]
}
requests.post(comment_url, headers=headers, json=review_payload)

# Post a general PR comment
issue_comment_url = f"{ctx.api_url}/repos/{ctx.repository}/issues/{ctx.pr.number}/comments"
requests.post(issue_comment_url, headers=headers, json={
    "body": "## AI Review Summary\n\n- 3 files changed\n- 2 suggestions\n- 1 security concern"
})
```

### 5.5 Fetching the Diff for Analysis

```python
import requests
from github_context import get_context

ctx = get_context()
headers = ctx.get_auth_header()
# Override Accept for diff format
headers["Accept"] = "application/vnd.github.v3.diff"

diff_url = f"{ctx.api_url}/repos/{ctx.repository}/pulls/{ctx.pr.number}"
response = requests.get(diff_url, headers=headers)
diff_content = response.text

# Now feed diff_content to your AI model for analysis
```

### 5.6 Setting Commit Status Checks

```python
import requests
from github_context import get_context

ctx = get_context()
headers = ctx.get_auth_header()

# Status checks are posted to the HEAD commit of the PR
status_url = f"{ctx.api_url}/repos/{ctx.repository}/statuses/{ctx.pr.head_sha}"

payload = {
    "state": "pending",  # "pending", "success", "failure", "error"
    "description": "AI code review in progress...",
    "context": "ai-code-review",
    "target_url": f"{ctx.server_url}/{ctx.repository}/actions/runs/{ctx.run_id}"
}

requests.post(status_url, headers=headers, json=payload)
```

---

## 6. `pull_request` vs `pull_request_target` — Security Deep Dive

### 6.1 Core Differences

| Aspect | `pull_request` | `pull_request_target` |
|--------|---------------|----------------------|
| **Execution Context** | The **merge commit** (`refs/pull/42/merge`) in the base repo | The **base branch** in the base repo |
| **Code Checked Out** | The merge of PR + base | The base branch (NOT the PR code by default) |
| **Token Permissions** | Read-only by default | Read/write by default |
| **Secrets Access** | ❌ No access to repository secrets | ✅ Full access to repository secrets |
| **GITHUB_TOKEN Scope** | Read-only (can be elevated via `permissions:`) | Read/write (can be restricted via `permissions:`) |
| **Use Case** | Build, test, lint the PR code | Comment, label, review PRs from forks; update checks |
| **Security Risk** | Low — untrusted code runs with limited permissions | **High** — untrusted code can access secrets and write to repo |

### 6.2 Visual Context Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    pull_request Event                                   │
│                                                                         │
│  ┌─────────────────┐         ┌─────────────────┐                      │
│  │   Fork Repo       │         │   Base Repo       │                      │
│  │   (untrusted)     │         │   (trusted)       │                      │
│  │                   │         │                   │                      │
│  │  feature-branch   │──────►│  refs/pull/42/merge│                      │
│  │                   │  PR     │  (merge commit)   │                      │
│  └─────────────────┘         └─────────────────┘                      │
│                                         │                              │
│                                         ▼                              │
│                              ┌─────────────────┐                      │
│                              │  Workflow Runs   │                      │
│                              │  - Checks out    │                      │
│                              │    merge commit  │                      │
│                              │  - Read-only     │                      │
│                              │    token         │                      │
│                              │  - No secrets    │                      │
│                              └─────────────────┘                      │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    pull_request_target Event                            │
│                                                                         │
│  ┌─────────────────┐         ┌─────────────────┐                      │
│  │   Fork Repo       │         │   Base Repo       │                      │
│  │   (untrusted)     │         │   (trusted)       │                      │
│  │                   │         │                   │                      │
│  │  feature-branch   │──────►│  base branch      │                      │
│  │                   │  PR     │  (main)           │                      │
│  └─────────────────┘         └─────────────────┘                      │
│                                         │                              │
│                                         ▼                              │
│                              ┌─────────────────┐                      │
│                              │  Workflow Runs   │                      │
│                              │  - Checks out    │                      │
│                              │    base branch   │                      │
│                              │  - Read/write    │                      │
│                              │    token         │                      │
│                              │  - Full secrets  │                      │
│                              │    access        │                      │
│                              └─────────────────┘                      │
│                                                                         │
│  ⚠️ DANGER: If you checkout the PR code, untrusted code runs with     │
│     write permissions and secret access!                                │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.3 When to Use Which

| Scenario | Recommended Trigger | Why |
|----------|-------------------|-----|
| Build and test PR code | `pull_request` | Runs untrusted code safely with limited permissions |
| Lint PR code | `pull_request` | Same as above |
| Run security scans on PR code | `pull_request` | Don't give untrusted code access to secrets |
| Post AI review comments on PRs from forks | `pull_request_target` | Needs write access to comment |
| Label PRs automatically | `pull_request_target` | Needs write access to add labels |
| Auto-approve safe PRs | `pull_request_target` | Needs write access to approve |
| Update PR status checks | `pull_request_target` | Needs write access to post status |
| Run integration tests requiring secrets | `pull_request_target` | Needs secret access (but be careful!) |

### 6.4 The `pull_request_target` Security Trap

**The Dangerous Pattern (DO NOT DO THIS):**

```yaml
# ❌ DANGEROUS — DO NOT USE
on:
  pull_request_target:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}  # ❌ CHECKING OUT UNTRUSTED CODE
      
      - run: pip install -r requirements.txt  # ❌ RUNNING UNTRUSTED CODE
      
      - run: python review.py  # ❌ WITH WRITE TOKEN + SECRETS
```

**Why this is dangerous:**
1. A malicious actor opens a PR that changes `review.py` to exfiltrate secrets
2. The workflow runs with `pull_request_target` — it has **write access** and **secret access**
3. The workflow checks out the PR code and runs it
4. The malicious script steals `GITHUB_TOKEN`, repository secrets, and can modify the repo

**This has led to real-world exploits** including:
- Secret exfiltration (npm tokens, AWS credentials, API keys)
- Repository takeover via compromised `GITHUB_TOKEN`
- Supply chain attacks via injected malicious code

### 6.5 Safe Patterns for `pull_request_target`

**Pattern 1: Two-Workflow Split (Label + Checkout)**

```yaml
# workflow-1: Untrusted code runs with pull_request (safe)
# .github/workflows/ci.yml
on:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4
      - run: pytest  # Safe: read-only, no secrets

# workflow-2: Trusted code runs with pull_request_target (has write access)
# .github/workflows/ai-review.yml
on:
  pull_request_target:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
      contents: read
    steps:
      # ✅ Check out the BASE branch (trusted code)
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.base_ref }}  # Base branch, NOT PR code
      
      # ✅ Run your trusted AI review script
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - run: pip install -r requirements.txt
      
      - run: python ai_review.py
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha }}
```

**Pattern 2: Fetch PR Data via API (No Checkout of PR Code)**

```python
# ai_review.py — runs in pull_request_target context
# Fetches PR data via API instead of checking out code

import requests
import os

TOKEN = os.environ["GITHUB_TOKEN"]
REPO = os.environ["GITHUB_REPOSITORY"]
PR_NUMBER = os.environ["PR_NUMBER"]
HEAD_SHA = os.environ["HEAD_SHA"]
API_URL = os.environ.get("GITHUB_API_URL", "https://api.github.com")

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json"
}

# Fetch diff via API (safe — no code execution)
diff_url = f"{API_URL}/repos/{REPO}/pulls/{PR_NUMBER}"
headers_diff = {**headers, "Accept": "application/vnd.github.v3.diff"}
diff = requests.get(diff_url, headers=headers_diff).text

# Analyze diff with AI...
# Post review comment
review_url = f"{API_URL}/repos/{REPO}/pulls/{PR_NUMBER}/reviews"
requests.post(review_url, headers=headers, json={
    "body": "AI review complete: LGTM!",
    "event": "COMMENT",
    "commit_id": HEAD_SHA
})
```

**Pattern 3: Required Workflow with `workflow_run`**

```yaml
# .github/workflows/ci.yml
on:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest

# .github/workflows/ai-review.yml
on:
  workflow_run:
    workflows: ["CI"]
    types: [completed]

jobs:
  review:
    runs-on: ubuntu-latest
    if: github.event.workflow_run.conclusion == 'success'
    permissions:
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
      - run: |
          # Download artifacts from CI workflow
          # Run AI review on the artifacts
          # Post review comments
```

### 6.6 Permission Lockdown Best Practices

```yaml
# Always minimize permissions
jobs:
  review:
    permissions:
      pull-requests: write      # Only what's needed
      contents: read            # If you need to checkout base
      # issues: write           # Only if needed
      # statuses: write        # Only if setting commit status
    # NEVER use:
    # permissions: write-all   # ❌ Too broad
```

### 6.7 Checking Out PR Code Safely in `pull_request_target`

If you absolutely must check out PR code in a `pull_request_target` workflow:

```yaml
jobs:
  review:
    permissions:
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.base_ref }}
      
      # Download PR code as artifact (read-only)
      - name: Fetch PR diff
        run: |
          curl -L \
            -H "Authorization: Bearer ${{ secrets.GITHUB_TOKEN }}" \
            -H "Accept: application/vnd.github.v3.diff" \
            "${{ github.event.pull_request.diff_url }}" \
            > pr.diff
      
      # Analyze the diff file (read-only operation)
      - run: python analyze_diff.py pr.diff
```

---

## 7. Practical Patterns for AI Code Review Agents

### 7.1 Workflow Configuration for AI Review

```yaml
# .github/workflows/ai-code-review.yml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]
    paths:
      - 'src/**'
      - 'lib/**'
      - '*.py'
      - '*.js'
      - '*.ts'
  pull_request_target:
    types: [opened, synchronize]

jobs:
  # Job 1: Analyze code (safe, runs on PR code)
  analyze:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - run: pip install -r requirements.txt
      
      - name: Run AI Analysis
        run: python analyze.py
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      
      - name: Upload Analysis Results
        uses: actions/upload-artifact@v4
        with:
          name: analysis-results
          path: analysis.json

  # Job 2: Post review (needs write access)
  review:
    if: github.event_name == 'pull_request_target'
    needs: analyze  # In practice, use workflow_run trigger
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.base_ref }}
      
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - run: pip install -r requirements.txt
      
      - name: Post AI Review
        run: python post_review.py
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
```

### 7.2 Complete AI Review Agent Script

```python
#!/usr/bin/env python3
"""
AI Code Review Agent for GitHub Actions
Handles both pull_request (analysis) and pull_request_target (posting) events.
"""

import json
import os
import sys
from typing import List, Dict, Any, Optional
import requests


class GitHubAPI:
    def __init__(self, token: str, repo: str, api_url: str = "https://api.github.com"):
        self.token = token
        self.repo = repo
        self.api_url = api_url
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
    
    def get_pr(self, number: int) -> Dict[str, Any]:
        url = f"{self.api_url}/repos/{self.repo}/pulls/{number}"
        resp = requests.get(url, headers=self.headers)
        resp.raise_for_status()
        return resp.json()
    
    def get_pr_files(self, number: int) -> List[Dict[str, Any]]:
        url = f"{self.api_url}/repos/{self.repo}/pulls/{number}/files"
        resp = requests.get(url, headers=self.headers)
        resp.raise_for_status()
        return resp.json()
    
    def get_diff(self, number: int) -> str:
        url = f"{self.api_url}/repos/{self.repo}/pulls/{number}"
        headers = {**self.headers, "Accept": "application/vnd.github.v3.diff"}
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.text
    
    def post_review(self, number: int, body: str, event: str = "COMMENT",
                    comments: Optional[List[Dict]] = None, commit_id: Optional[str] = None) -> Dict:
        url = f"{self.api_url}/repos/{self.repo}/pulls/{number}/reviews"
        payload = {"body": body, "event": event}
        if comments:
            payload["comments"] = comments
        if commit_id:
            payload["commit_id"] = commit_id
        resp = requests.post(url, headers=self.headers, json=payload)
        resp.raise_for_status()
        return resp.json()
    
    def post_comment(self, number: int, body: str) -> Dict:
        url = f"{self.api_url}/repos/{self.repo}/issues/{number}/comments"
        resp = requests.post(url, headers=self.headers, json={"body": body})
        resp.raise_for_status()
        return resp.json()
    
    def set_status(self, sha: str, state: str, description: str, context: str = "ai-review"):
        url = f"{self.api_url}/repos/{self.repo}/statuses/{sha}"
        payload = {
            "state": state,
            "description": description,
            "context": context
        }
        resp = requests.post(url, headers=self.headers, json=payload)
        resp.raise_for_status()
        return resp.json()


def load_event() -> Dict[str, Any]:
    path = os.environ.get("GITHUB_EVENT_PATH", "/github/workflow/event.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def should_skip_pr(pr: Dict[str, Any]) -> tuple[bool, str]:
    """Determine if PR should be skipped. Returns (skip, reason)."""
    if pr.get("draft", False):
        return True, "Draft PR"
    
    labels = [l.get("name", "") for l in pr.get("labels", [])]
    if "skip-ai-review" in labels:
        return True, "Label: skip-ai-review"
    
    if pr.get("changed_files", 0) > 50:
        return True, f"Too many files ({pr['changed_files']})"
    
    additions = pr.get("additions", 0)
    deletions = pr.get("deletions", 0)
    if additions + deletions > 2000:
        return True, f"Diff too large ({additions + deletions} lines)"
    
    return False, ""


def analyze_diff(diff: str) -> Dict[str, Any]:
    """Analyze diff with AI. Returns structured findings."""
    # Integration with your AI model here
    # Example: OpenAI, Anthropic, or local model
    return {
        "summary": "No critical issues found.",
        "suggestions": [],
        "security_concerns": [],
        "score": 85
    }


def main():
    event = load_event()
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    
    if event_name not in ("pull_request", "pull_request_target"):
        print(f"Unsupported event: {event_name}")
        sys.exit(0)
    
    pr = event.get("pull_request", {})
    pr_number = pr.get("number", 0)
    
    if not pr_number:
        print("No PR number found")
        sys.exit(1)
    
    # Check if we should skip
    skip, reason = should_skip_pr(pr)
    if skip:
        print(f"Skipping PR #{pr_number}: {reason}")
        sys.exit(0)
    
    # Initialize API client
    api = GitHubAPI(
        token=os.environ["GITHUB_TOKEN"],
        repo=os.environ["GITHUB_REPOSITORY"],
        api_url=os.environ.get("GITHUB_API_URL", "https://api.github.com")
    )
    
    # Set status to pending
    head_sha = pr.get("head", {}).get("sha", "")
    if head_sha:
        api.set_status(head_sha, "pending", "AI review in progress...")
    
    try:
        # Fetch diff
        diff = api.get_diff(pr_number)
        
        # Analyze
        results = analyze_diff(diff)
        
        # Post review
        if event_name == "pull_request_target":
            # We have write access — post review
            body = f"""## 🤖 AI Code Review

**Score:** {results['score']}/100

**Summary:** {results['summary']}

---
*This review was generated automatically. Please verify before acting.*
"""
            api.post_review(pr_number, body, event="COMMENT", commit_id=head_sha)
            api.set_status(head_sha, "success", "AI review complete")
        else:
            # Save results for later pickup
            with open("analysis.json", "w") as f:
                json.dump(results, f, indent=2)
            print("Analysis saved to analysis.json")
            
    except Exception as e:
        print(f"Error: {e}")
        if head_sha:
            api.set_status(head_sha, "error", f"AI review failed: {str(e)[:50]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

### 7.3 Filtering Rules for AI Agents

```python
# Common filtering logic for AI code review agents

class PRFilter:
    """Determine whether to run AI review on a PR."""
    
    SKIP_LABELS = {"skip-ai-review", "wip", "draft", "do-not-review"}
    MAX_FILES = 50
    MAX_LINES = 2000
    
    @classmethod
    def should_review(cls, pr: Dict[str, Any]) -> tuple[bool, str]:
        # Skip drafts
        if pr.get("draft", False):
            return False, "Draft PR"
        
        # Skip by label
        labels = {l.get("name", "").lower() for l in pr.get("labels", [])}
        if cls.SKIP_LABELS & labels:
            return False, f"Skip label present: {cls.SKIP_LABELS & labels}"
        
        # Skip by size
        if pr.get("changed_files", 0) > cls.MAX_FILES:
            return False, f"Too many files: {pr['changed_files']} > {cls.MAX_FILES}"
        
        total_lines = pr.get("additions", 0) + pr.get("deletions", 0)
        if total_lines > cls.MAX_LINES:
            return False, f"Diff too large: {total_lines} > {cls.MAX_LINES}"
        
        # Skip by author (e.g., bots)
        author = pr.get("user", {}).get("login", "")
        if author.endswith("[bot]") or author in {"dependabot", "renovate"}:
            return False, f"Bot PR: {author}"
        
        # Skip if locked
        if pr.get("locked", False):
            return False, "PR is locked"
        
        # Skip if already merged
        if pr.get("merged", False):
            return False, "Already merged"
        
        # Skip external contributors for sensitive repos
        assoc = pr.get("author_association", "")
        if assoc == "NONE":
            return False, "External contributor (first-time)"
        
        return True, ""
```

---

## 8. Appendix: Environment Variable Mapping

### 8.1 `github` Context → Environment Variable

| Context Expression | Environment Variable | Example Value |
|-------------------|----------------------|---------------|
| `github.action` | `GITHUB_ACTION` | `__run` |
| `github.actor` | `GITHUB_ACTOR` | `octocat` |
| `github.actor_id` | `GITHUB_ACTOR_ID` | `1234567` |
| `github.api_url` | `GITHUB_API_URL` | `https://api.github.com` |
| `github.base_ref` | `GITHUB_BASE_REF` | `main` |
| `github.env` | `GITHUB_ENV` | `/home/runner/...` |
| `github.event` | `GITHUB_EVENT_PATH` (file) | `/home/runner/.../event.json` |
| `github.event_name` | `GITHUB_EVENT_NAME` | `pull_request` |
| `github.graphql_url` | `GITHUB_GRAPHQL_URL` | `https://api.github.com/graphql` |
| `github.head_ref` | `GITHUB_HEAD_REF` | `feature-branch` |
| `github.job` | `GITHUB_JOB` | `build` |
| `github.path` | `GITHUB_PATH` | `/home/runner/...` |
| `github.ref` | `GITHUB_REF` | `refs/pull/42/merge` |
| `github.ref_name` | `GITHUB_REF_NAME` | `42/merge` |
| `github.ref_protected` | `GITHUB_REF_PROTECTED` | `false` |
| `github.ref_type` | `GITHUB_REF_TYPE` | `branch` |
| `github.repository` | `GITHUB_REPOSITORY` | `octocat/Hello-World` |
| `github.repository_id` | `GITHUB_REPOSITORY_ID` | `1296269` |
| `github.repository_owner` | `GITHUB_REPOSITORY_OWNER` | `octocat` |
| `github.repository_owner_id` | `GITHUB_REPOSITORY_OWNER_ID` | `1` |
| `github.run_id` | `GITHUB_RUN_ID` | `1234567890` |
| `github.run_number` | `GITHUB_RUN_NUMBER` | `42` |
| `github.run_attempt` | `GITHUB_RUN_ATTEMPT` | `1` |
| `github.server_url` | `GITHUB_SERVER_URL` | `https://github.com` |
| `github.sha` | `GITHUB_SHA` | `abc123...` |
| `github.token` | `GITHUB_TOKEN` | `ghs_xxx...` |
| `github.triggering_actor` | `GITHUB_TRIGGERING_ACTOR` | `octocat` |
| `github.workflow` | `GITHUB_WORKFLOW` | `CI` |
| `github.workflow_ref` | `GITHUB_WORKFLOW_REF` | `octocat/.../ci.yml@refs/heads/main` |
| `github.workflow_sha` | `GITHUB_WORKFLOW_SHA` | `def456...` |
| `github.workspace` | `GITHUB_WORKSPACE` | `/home/runner/work/...` |

### 8.2 Default Environment Variables (Always Available)

| Variable | Description |
|----------|-------------|
| `CI` | Always set to `true` |
| `GITHUB_ACTIONS` | Always set to `true` |
| `RUNNER_OS` | Operating system: `Linux`, `Windows`, `macOS` |
| `RUNNER_ARCH` | Architecture: `X64`, `ARM64`, `X86` |
| `RUNNER_NAME` | Name of the runner |
| `RUNNER_TOOL_CACHE` | Path to tool cache |
| `RUNNER_TEMP` | Path to temp directory |

---

## References

1. [GitHub Docs — Webhook events and payloads](https://docs.github.com/en/webhooks/webhook-events-and-payloads)
2. [GitHub Docs — Contexts](https://docs.github.com/en/actions/learn-github-actions/variables#default-environment-variables)
3. [GitHub Docs — Workflow syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
4. [GitHub Docs — pull_request_target security](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#pull_request_target)
5. [GitHub REST API — Pulls](https://docs.github.com/en/rest/pulls/pulls)
6. [Orca Security — pull_request_target RCE](https://orca.security/resources/blog/pull-request-nightmare-github-actions-rce/)
7. [GitHub Actions Toolkit — Event Payload](https://github-action-toolkit.readthedocs.io/en/latest/usage/event_payload.html)
8. [GitHub Gist — Example PR Payload](https://gist.github.com/GuillaumeFalourd/e53ec9b6bc783cce184bd1eec263799d)

---

*This document was compiled for AI code review agent development teams. For the latest schema changes, always refer to the official GitHub documentation.*
