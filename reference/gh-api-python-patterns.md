# GitHub API Patterns for Python-Based AI Code Review Agents

**A comprehensive reference for development teams building AI-powered code review automation.**

*Compiled: 2026-06-01*

---

## Table of Contents

1. [Authentication & Setup](#1-authentication--setup)
2. [PyGithub Library Patterns](#2-pygithub-library-patterns)
3. [GitHub REST API Endpoints](#3-github-rest-api-endpoints)
4. [GitHub Action Authentication (GITHUB_TOKEN)](#4-github-action-authentication-github_token)
5. [Fetching BASE vs HEAD File Versions](#5-fetching-base-vs-head-file-versions)
6. [Getting Patch/Diff for Individual Files](#6-getting-patchdiff-for-individual-files)
7. [Rate Limiting & Pagination](#7-rate-limiting--pagination)
8. [Complete Working Example](#8-complete-working-example)
9. [Common Pitfalls & Troubleshooting](#9-common-pitfalls--troubleshooting)

---

## 1. Authentication & Setup

### 1.1 Personal Access Token (PAT)

For local development or external automation:

```python
from github import Github

# Classic PAT (fine-grained recommended for production)
g = Github("ghp_xxxxxxxxxxxxxxxxxxxx")

# Or with explicit base URL for GitHub Enterprise
# g = Github("ghp_xxxxxxxx", base_url="https://github.mycompany.com/api/v3")

repo = g.get_repo("owner/repo-name")
pr = repo.get_pull(42)
```

### 1.2 Environment-Based Authentication

```python
import os
from github import Github

TOKEN = os.environ.get("GITHUB_TOKEN")
if not TOKEN:
    raise ValueError("GITHUB_TOKEN environment variable is required")

g = Github(TOKEN)
repo = g.get_repo(os.environ.get("GITHUB_REPOSITORY", "owner/repo"))
```

### 1.3 PyGithub Installation

```bash
pip install PyGithub
```

**Current version:** 2.8.1 (as of early 2026). Check [PyGithub docs](https://pygithub.readthedocs.io/) for latest.

---

## 2. PyGithub Library Patterns

### 2.1 Fetching PR Diffs

PyGithub does **not** have a direct `get_diff()` method on `PullRequest`. You must use the `diff_url` property and make a raw HTTP request, or use the `compare()` method on the repository.

#### Method A: Using diff_url (Recommended for full PR diff)

```python
from github import Github
import requests

g = Github(TOKEN)
repo = g.get_repo("owner/repo")
pr = repo.get_pull(42)

# The diff_url is a public URL but requires auth for private repos
headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3.diff"
}

response = requests.get(pr.diff_url, headers=headers)
diff_text = response.text

print(f"PR #{pr.number} diff ({len(diff_text)} chars)")
print(diff_text[:1000])
```

#### Method B: Using repo.compare() for commit ranges

```python
# Get the base and head commits from the PR
base_sha = pr.base.sha   # The commit SHA on the base branch
head_sha = pr.head.sha   # The commit SHA on the PR branch

# Compare the two commits
comparison = repo.compare(base_sha, head_sha)

# This gives you a Comparison object with diff information
print(f"Files changed: {comparison.total_commits}")
for file in comparison.files:
    print(f"  {file.filename}: +{file.additions} -{file.deletions}")
    print(f"    patch: {file.patch[:200] if file.patch else 'N/A'}")
```

#### Method C: Using the raw API with media type

```python
import requests

# Get the full diff via the pulls endpoint with custom Accept header
url = f"https://api.github.com/repos/{repo.full_name}/pulls/{pr.number}"
headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github.v3.diff",  # Request diff format
    "X-GitHub-Api-Version": "2022-11-28"
}

response = requests.get(url, headers=headers)
if response.status_code == 200:
    diff_text = response.text
    # This is the unified diff of the entire PR
```

**Key insight:** The `Accept: application/vnd.github.v3.diff` header transforms the `/pulls/{number}` endpoint response from JSON into raw unified diff text.

### 2.2 Getting Changed Files

```python
# Method 1: Using get_files() on the PR (paginated, returns File objects)
files = pr.get_files()

for file in files:
    print(f"File: {file.filename}")
    print(f"  Status: {file.status}")        # 'added', 'removed', 'modified', 'renamed'
    print(f"  Additions: {file.additions}")
    print(f"  Deletions: {file.deletions}")
    print(f"  Changes: {file.changes}")
    print(f"  Patch:\n{file.patch[:500]}")    # The patch/diff for this file
    print(f"  Previous filename: {file.previous_filename}")  # For renames
    print(f"  Raw URL: {file.raw_url}")
    print(f"  Blob URL: {file.blob_url}")
    print(f"  Contents URL: {file.contents_url}")
    print("---")
```

**Important:** `get_files()` returns a `PaginatedList` of `File` objects. Each `File` has a `.patch` attribute containing the unified diff patch for that specific file.

```python
# Method 2: Using the raw REST API for more control
import requests

url = f"https://api.github.com/repos/{repo.full_name}/pulls/{pr.number}/files"
headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

all_files = []
page = 1
while True:
    response = requests.get(url, headers=headers, params={"page": page, "per_page": 100})
    response.raise_for_status()
    data = response.json()
    if not data:
        break
    all_files.extend(data)
    page += 1

for f in all_files:
    print(f"{f['filename']}: {f['status']} (+{f['additions']}/-{f['deletions']})")
    print(f"Patch preview: {f.get('patch', 'N/A')[:300]}")
```

### 2.3 Reading File Contents

#### Reading the HEAD version (current PR state)

```python
# Method 1: Using repo.get_contents() with the PR branch ref
file_path = "src/main.py"
pr_branch = pr.head.ref  # e.g., "feature/my-branch"

content_file = repo.get_contents(file_path, ref=pr_branch)
file_content = content_file.decoded_content.decode('utf-8')

print(f"File: {content_file.path}")
print(f"SHA: {content_file.sha}")
print(f"Size: {content_file.size} bytes")
print(f"Content:\n{file_content[:500]}")
```

#### Reading file contents via the Git blob API

```python
# Method 2: Using the Git blob API (works with any SHA)
# Get the blob SHA from the file object
file_obj = pr.get_files()[0]  # First changed file
blob_sha = file_obj.sha

blob = repo.get_git_blob(blob_sha)
import base64
file_content = base64.b64decode(blob.content).decode('utf-8')
```

#### Reading file contents via raw URL

```python
# Method 3: Using the raw URL from the file object
files = pr.get_files()
for file in files:
    if file.status == 'removed':
        continue  # Can't fetch raw content of deleted files
    
    headers = {"Authorization": f"token {TOKEN}"}
    response = requests.get(file.raw_url, headers=headers)
    if response.status_code == 200:
        content = response.text
        print(f"{file.filename}: {len(content)} chars")
```

### 2.4 Posting Review Comments vs PR Comments

This is **critically important** — there are two distinct comment types:

#### A. PR Review Comments (Line-Level / Inline)

These appear on specific lines in the diff view. They are part of a "review" and can be:
- Single comments
- Part of a full review (APPROVE, REQUEST_CHANGES, COMMENT)

```python
from github import PullRequest

# Get the latest commit in the PR
commits = list(pr.get_commits())
latest_commit = commits[-1]  # Last commit is the HEAD

# Create a single review comment on a specific line
# position = line number within the diff patch (NOT the file line number)
comment = pr.create_review_comment(
    body="Consider adding type hints here for better clarity.",
    commit=latest_commit,
    path="src/main.py",
    position=5  # Position within the diff patch (1-based)
)

print(f"Created comment: {comment.html_url}")
```

**CRITICAL:** The `position` parameter is the **position within the diff patch**, not the absolute line number in the file. It's the number of lines down from the first `@@` hunk header in the file's patch.

#### Creating a full review with multiple comments

```python
from github import PullRequest

# Build a list of comment dicts
comments_data = [
    {
        "path": "src/main.py",
        "position": 3,
        "body": "This function could benefit from docstring documentation."
    },
    {
        "path": "tests/test_main.py",
        "position": 7,
        "body": "Consider adding a test case for edge condition X=0."
    }
]

# Create a review with the comments
review = pr.create_review(
    body="## AI Code Review Summary\n\nOverall good work! A few suggestions:",
    comments=comments_data,
    event="COMMENT"  # Options: "APPROVE", "REQUEST_CHANGES", "COMMENT"
)

print(f"Review created: {review.id}")
print(f"State: {review.state}")
```

#### B. PR Comments (General / Issue Comments)

These appear in the PR conversation timeline, not on specific lines. They're like issue comments.

```python
# Create a general PR comment (appears in the conversation)
comment = pr.create_issue_comment(
    "## Automated Review Results\n\n"
    "All checks passed. Code quality score: 8.5/10\n\n"
    "* No security issues detected\n"
    "* Test coverage: 87%\n"
    "* 2 minor style suggestions posted as inline comments"
)

print(f"Comment URL: {comment.html_url}")
```

#### C. Review Comments on the PR as a whole (not line-specific)

```python
# Create a review without specific line comments (just the summary)
review = pr.create_review(
    body="This PR looks good to me. All automated checks passed.",
    event="APPROVE"
)
```

### 2.5 Comment Types Summary

| Type | Method | Appears On | Use Case |
|------|--------|------------|----------|
| Review Comment (inline) | `pr.create_review_comment()` | Specific diff line | Line-specific feedback |
| Review (with comments) | `pr.create_review()` | Diff lines + summary | Full code review |
| PR Comment | `pr.create_issue_comment()` | Conversation timeline | General summary, CI results |
| Review (summary only) | `pr.create_review(body=..., event=...)` | Review section | Approve/Request changes |

---

## 3. GitHub REST API Endpoints

### 3.1 PR Files Endpoint

```
GET /repos/{owner}/{repo}/pulls/{pull_number}/files
```

**Python (requests):**

```python
import requests

def get_pr_files(owner, repo, pr_number, token):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    all_files = []
    page = 1
    while True:
        response = requests.get(
            url,
            headers=headers,
            params={"page": page, "per_page": 100}
        )
        response.raise_for_status()
        
        files = response.json()
        if not files:
            break
            
        all_files.extend(files)
        
        # Check for next page
        if 'next' not in response.links:
            break
        page += 1
    
    return all_files

# Usage
files = get_pr_files("myorg", "myrepo", 42, TOKEN)
for f in files:
    print(f"{f['filename']}: {f['status']}")
    print(f"  patch: {f.get('patch', 'N/A')[:200]}")
```

**Response fields per file:**

```json
{
  "sha": "bbcd538c8e72b8c175046e27cc8f907076331401",
  "filename": "file1.txt",
  "status": "added",
  "additions": 103,
  "deletions": 21,
  "changes": 124,
  "blob_url": "https://github.com/octocat/Hello-World/blob/6dcb09b5b57875f334f61aebed695e2e4193db5e/file1.txt",
  "raw_url": "https://github.com/octocat/Hello-World/raw/6dcb09b5b57875f334f61aebed695e2e4193db5e/file1.txt",
  "contents_url": "https://api.github.com/repos/octocat/Hello-World/contents/file1.txt?ref=6dcb09b5b57875f334f61aebed695e2e4193db5e",
  "patch": "@@ -132,7 +132,7 @@ module Test @@ -1000,7 +1000,7 @@ module..."
}
```

### 3.2 PR Diff Endpoint

```
GET /repos/{owner}/{repo}/pulls/{pull_number}
```

With `Accept: application/vnd.github.v3.diff` header:

```python
import requests

def get_pr_diff(owner, repo, pr_number, token):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3.diff",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text  # Raw unified diff text

# Usage
diff = get_pr_diff("myorg", "myrepo", 42, TOKEN)
print(diff[:2000])
```

**Alternative: Get patch format**

```python
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github.v3.patch",  # Patch format instead of diff
}
```

### 3.3 File Contents Endpoint (with ref/SHA)

```
GET /repos/{owner}/{repo}/contents/{path}
```

```python
import requests
import base64

def get_file_contents(owner, repo, path, ref, token):
    """
    Get file contents at a specific ref (branch, tag, or commit SHA).
    
    Args:
        owner: Repository owner
        repo: Repository name
        path: File path within repo
        ref: Branch name, tag, or commit SHA
        token: GitHub token
    
    Returns:
        Tuple of (decoded_content: str, sha: str, size: int)
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.raw+json",  # Get raw content
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    response = requests.get(url, headers=headers, params={"ref": ref})
    response.raise_for_status()
    
    data = response.json()
    
    # Content is base64 encoded
    content = base64.b64decode(data["content"]).decode('utf-8')
    
    return content, data["sha"], data["size"]

# Usage
content, sha, size = get_file_contents(
    "myorg", "myrepo", "src/main.py", "feature-branch", TOKEN
)
print(f"File SHA: {sha}, Size: {size}")
print(content[:500])
```

**Important:** The `ref` query parameter can be:
- A branch name: `ref=main`
- A tag: `ref=v1.0.0`
- A commit SHA: `ref=abc123...`

#### Alternative: Get raw content directly

```python
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github.raw",  # Returns raw text, not JSON
}

response = requests.get(url, headers=headers, params={"ref": ref})
content = response.text  # Direct text, no base64 decoding needed
```

### 3.4 Git Blob API (for any file SHA)

```
GET /repos/{owner}/{repo}/git/blobs/{file_sha}
```

```python
def get_blob_content(owner, repo, blob_sha, token):
    """Get file content by blob SHA (works for any git object)."""
    url = f"https://api.github.com/repos/{owner}/{repo}/git/blobs/{blob_sha}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    data = response.json()
    # Blob content is base64 encoded
    content = base64.b64decode(data["content"]).decode('utf-8')
    return content

# Usage: Get blob SHA from PR file
files = get_pr_files("myorg", "myrepo", 42, TOKEN)
for f in files:
    if f['status'] != 'removed':
        content = get_blob_content("myorg", "myrepo", f['sha'], TOKEN)
        print(f"{f['filename']}: {len(content)} chars")
```

### 3.5 Review Comments (Line-Level) Endpoint

```
POST /repos/{owner}/{repo}/pulls/{pull_number}/comments
```

```python
def create_review_comment(owner, repo, pr_number, token, 
                          body, commit_id, path, position,
                          side="RIGHT", line=None, start_line=None,
                          start_side=None, in_reply_to=None):
    """
    Create a line-level review comment on a PR.
    
    Args:
        body: Comment text (markdown supported)
        commit_id: SHA of the commit you're commenting on
        path: File path relative to repo root
        position: Position in the diff (1-based, from first @@ hunk)
        side: "LEFT" (base) or "RIGHT" (head)
        line: For multi-line comments, the ending line
        start_line: For multi-line comments, the starting line
        start_side: Side for start_line
        in_reply_to: ID of comment to reply to
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    payload = {
        "body": body,
        "commit_id": commit_id,
        "path": path,
        "position": position,
        "side": side
    }
    
    # Optional: multi-line comment
    if line is not None:
        payload["line"] = line
    if start_line is not None:
        payload["start_line"] = start_line
    if start_side is not None:
        payload["start_side"] = start_side
    if in_reply_to is not None:
        payload["in_reply_to_id"] = in_reply_to
    
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()

# Usage
comment = create_review_comment(
    "myorg", "myrepo", 42, TOKEN,
    body="Consider using a constant here instead of magic number.",
    commit_id="abc123...",
    path="src/config.py",
    position=3,
    side="RIGHT"
)
print(f"Created: {comment['html_url']}")
```

#### Multi-line review comments

```python
# Comment on lines 10-15 of the file in the HEAD version
comment = create_review_comment(
    "myorg", "myrepo", 42, TOKEN,
    body="This entire block should be extracted into a helper function.",
    commit_id="abc123...",
    path="src/utils.py",
    side="RIGHT",
    line=15,           # End line
    start_line=10,     # Start line
    start_side="RIGHT"
)
```

**Important:** For multi-line comments, you must use the `line` + `start_line` parameters (not `position`). The `line` values are absolute line numbers in the file, not diff positions.

### 3.6 PR Comments (General) Endpoint

```
POST /repos/{owner}/{repo}/issues/{issue_number}/comments
```

Note: PRs are also issues, so use the issue number (same as PR number).

```python
def create_pr_comment(owner, repo, pr_number, token, body):
    """Create a general comment on the PR conversation."""
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    payload = {"body": body}
    
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()

# Usage
comment = create_pr_comment(
    "myorg", "myrepo", 42, TOKEN,
    body="## AI Review Complete\n\nAll automated checks passed!"
)
```

### 3.7 Create a Full Review

```
POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews
```

```python
def create_full_review(owner, repo, pr_number, token, 
                       body, comments, event="COMMENT"):
    """
    Create a full PR review with multiple inline comments.
    
    Args:
        body: Overall review summary
        comments: List of dicts with path, position, body, side
        event: "APPROVE", "REQUEST_CHANGES", or "COMMENT"
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    payload = {
        "body": body,
        "event": event,
        "comments": comments
    }
    
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()

# Usage
comments = [
    {
        "path": "src/main.py",
        "position": 3,
        "body": "Add type hints here.",
        "side": "RIGHT"
    },
    {
        "path": "src/main.py",
        "position": 8,
        "body": "This variable name is unclear.",
        "side": "RIGHT"
    }
]

review = create_full_review(
    "myorg", "myrepo", 42, TOKEN,
    body="## AI Code Review\n\nGood work overall! A few minor suggestions:",
    comments=comments,
    event="COMMENT"
)
print(f"Review: {review['html_url']}")
```

---

## 4. GitHub Action Authentication (GITHUB_TOKEN)

### 4.1 How GITHUB_TOKEN Works

When a GitHub Actions workflow runs, GitHub automatically creates a temporary `GITHUB_TOKEN` secret:

- **Type:** Installation access token for the `github-actions` bot
- **Scope:** Limited to the repository containing the workflow
- **Lifetime:** Expires when the job completes (max 24 hours)
- **Permissions:** Configurable via workflow YAML

### 4.2 Required Permissions for Code Review Agents

| Permission | Level | Purpose |
|------------|-------|---------|
| `contents` | `read` | Read file contents, diffs, commits |
| `pull-requests` | `write` | Post comments, create reviews, add labels |
| `issues` | `write` | Post general comments (PRs are issues) |

**Minimal permissions for a code review agent:**

```yaml
permissions:
  contents: read
  pull-requests: write
```

**If you also need to check issues or add labels:**

```yaml
permissions:
  contents: read
  pull-requests: write
  issues: write
```

### 4.3 Setting Permissions in Workflow YAML

#### Option A: Job-level permissions (recommended)

```yaml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  review:
    runs-on: ubuntu-latest
    
    # Minimal permissions for this job only
    permissions:
      contents: read
      pull-requests: write
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          pip install PyGithub requests
          
      - name: Run AI Review
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
        run: |
          python scripts/ai_review.py
```

#### Option B: Workflow-level permissions

```yaml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

# Permissions apply to ALL jobs in this workflow
permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      # ... same as above
```

#### Option C: Repository default permissions (NOT recommended for agents)

You can set default permissions at **Settings > Actions > General > Workflow permissions**, but this applies to ALL workflows. For code review agents, explicit job-level permissions are safer.

### 4.4 Using the Token in Python

```python
import os
from github import Github

# In GitHub Actions, GITHUB_TOKEN is automatically available
token = os.environ["GITHUB_TOKEN"]
repo_name = os.environ["GITHUB_REPOSITORY"]  # "owner/repo"
pr_number = int(os.environ["PR_NUMBER"])

g = Github(token)
repo = g.get_repo(repo_name)
pr = repo.get_pull(pr_number)

# Now you can use all the patterns above
```

### 4.5 Using the Token with GitHub CLI (gh)

```yaml
- name: Post review with gh CLI
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    gh pr comment ${{ github.event.pull_request.number }} \
      --body "AI Review: All checks passed!"
```

### 4.6 Token Permission Errors

If you see `403 Forbidden` or `Resource not accessible by integration`:

1. Check your `permissions` block in the workflow YAML
2. Verify the repository allows workflows to create PR comments:
   - **Settings > Actions > General > Workflow permissions**
   - Ensure "Read and write permissions" is selected (or use fine-grained permissions)
3. For private repos, the token automatically has access
4. For forks, `pull_request` events from forks get a read-only token by default — use `pull_request_target` (with caution) for write access

---

## 5. Fetching BASE vs HEAD File Versions

### 5.1 Understanding BASE and HEAD

| Term | Meaning | How to Access |
|------|---------|---------------|
| **BASE** | The version of the file on the target branch (before PR) | `pr.base.ref` or `pr.base.sha` |
| **HEAD** | The version of the file on the PR branch (after changes) | `pr.head.ref` or `pr.head.sha` |

### 5.2 Using PyGithub

```python
from github import Github

g = Github(TOKEN)
repo = g.get_repo("owner/repo")
pr = repo.get_pull(42)

# Branch names
base_branch = pr.base.ref   # e.g., "main"
head_branch = pr.head.ref  # e.g., "feature/my-branch"

# Commit SHAs
base_sha = pr.base.sha    # Latest commit on base branch
head_sha = pr.head.sha    # Latest commit on PR branch

# Read BASE version of a file
file_path = "src/main.py"

try:
    base_file = repo.get_contents(file_path, ref=base_branch)
    base_content = base_file.decoded_content.decode('utf-8')
    print(f"BASE ({base_branch}): {len(base_content)} chars")
except Exception as e:
    # File might not exist in base (new file in PR)
    print(f"File not found in BASE: {e}")
    base_content = None

# Read HEAD version of a file
try:
    head_file = repo.get_contents(file_path, ref=head_branch)
    head_content = head_file.decoded_content.decode('utf-8')
    print(f"HEAD ({head_branch}): {len(head_content)} chars")
except Exception as e:
    # File might have been deleted in PR
    print(f"File not found in HEAD: {e}")
    head_content = None

# Now you can diff them yourself if needed
if base_content and head_content:
    import difflib
    diff = difflib.unified_diff(
        base_content.splitlines(keepends=True),
        head_content.splitlines(keepends=True),
        fromfile=f"{file_path} (base)",
        tofile=f"{file_path} (head)"
    )
    print(''.join(diff))
```

### 5.3 Using the Compare API

```python
# Compare base and head to get full diff information
comparison = repo.compare(base_sha, head_sha)

for file in comparison.files:
    print(f"File: {file.filename}")
    print(f"  Status: {file.status}")
    print(f"  Additions: {file.additions}")
    print(f"  Deletions: {file.deletions}")
    print(f"  Patch:\n{file.patch[:500]}")
    
    # Get the previous version (before PR)
    if file.previous_filename:
        print(f"  Renamed from: {file.previous_filename}")
```

### 5.4 Using the Raw REST API

```python
import requests
import base64

def get_file_at_ref(owner, repo, path, ref, token):
    """Get file content at a specific ref."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.raw+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    response = requests.get(url, headers=headers, params={"ref": ref})
    
    if response.status_code == 404:
        return None  # File doesn't exist at this ref
    
    response.raise_for_status()
    data = response.json()
    return base64.b64decode(data["content"]).decode('utf-8')

# In a GitHub Action
owner, repo = os.environ["GITHUB_REPOSITORY"].split("/")
pr_number = int(os.environ["PR_NUMBER"])

# Get PR details to find base and head refs
pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
headers = {
    "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}
pr_data = requests.get(pr_url, headers=headers).json()

base_ref = pr_data["base"]["ref"]   # e.g., "main"
head_ref = pr_data["head"]["ref"]   # e.g., "feature-branch"

# Get a changed file's both versions
for file in pr_data.get("files", []):  # Or fetch from /pulls/{n}/files
    file_path = file["filename"]
    
    # BASE version (may be None for new files)
    base_content = get_file_at_ref(owner, repo, file_path, base_ref, TOKEN)
    
    # HEAD version (may be None for deleted files)
    head_content = get_file_at_ref(owner, repo, file_path, head_ref, TOKEN)
    
    print(f"{file_path}:")
    print(f"  BASE: {'Found' if base_content else 'N/A (new file)'}")
    print(f"  HEAD: {'Found' if head_content else 'N/A (deleted)'}")
```

### 5.5 Handling New and Deleted Files

```python
# When iterating PR files, check status
for file in pr.get_files():
    if file.status == "added":
        # Only HEAD version exists
        head_content = repo.get_contents(file.filename, ref=pr.head.ref).decoded_content.decode()
        base_content = None
        
    elif file.status == "removed":
        # Only BASE version exists
        base_content = repo.get_contents(file.filename, ref=pr.base.ref).decoded_content.decode()
        head_content = None
        
    elif file.status == "modified":
        # Both versions exist
        base_content = repo.get_contents(file.filename, ref=pr.base.ref).decoded_content.decode()
        head_content = repo.get_contents(file.filename, ref=pr.head.ref).decoded_content.decode()
        
    elif file.status == "renamed":
        # File moved from previous_filename to filename
        old_path = file.previous_filename
        new_path = file.filename
        # Fetch both as needed
```

---

## 6. Getting Patch/Diff for Individual Files

### 6.1 From PR File Objects

The easiest way — each file in a PR already has its patch:

```python
files = pr.get_files()

for file in files:
    if file.patch:
        print(f"=== {file.filename} ===")
        print(file.patch)
        print()
```

### 6.2 Parsing the Patch

```python
import re

def parse_patch(patch):
    """
    Parse a unified diff patch into hunks.
    
    Returns list of dicts with:
    - old_start: Starting line in old file
    - old_lines: Number of lines in old file hunk
    - new_start: Starting line in new file
    - new_lines: Number of lines in new file hunk
    - lines: List of (type, text) tuples where type is ' ' (context), '+' (added), '-' (removed)
    """
    hunks = []
    hunk_header = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')
    
    current_hunk = None
    
    for line in patch.split('\n'):
        match = hunk_header.match(line)
        if match:
            if current_hunk:
                hunks.append(current_hunk)
            old_start = int(match.group(1))
            old_lines = int(match.group(2)) if match.group(2) else 1
            new_start = int(match.group(3))
            new_lines = int(match.group(4)) if match.group(4) else 1
            current_hunk = {
                'old_start': old_start,
                'old_lines': old_lines,
                'new_start': new_start,
                'new_lines': new_lines,
                'lines': []
            }
        elif current_hunk is not None:
            if line.startswith('+'):
                current_hunk['lines'].append(('added', line[1:]))
            elif line.startswith('-'):
                current_hunk['lines'].append(('removed', line[1:]))
            elif line.startswith(' '):
                current_hunk['lines'].append(('context', line[1:]))
            elif line.startswith('\\'):
                # "\ No newline at end of file" - skip
                pass
    
    if current_hunk:
        hunks.append(current_hunk)
    
    return hunks

# Usage
files = pr.get_files()
for file in files:
    if file.patch:
        hunks = parse_patch(file.patch)
        for hunk in hunks:
            print(f"Hunk at old:{hunk['old_start']} new:{hunk['new_start']}")
            for line_type, text in hunk['lines']:
                symbol = {'added': '+', 'removed': '-', 'context': ' '}[line_type]
                print(f"{symbol} {text}")
```

### 6.3 Getting Diff Position for Commenting

The `position` parameter for review comments is the **1-based index** of the line within the file's patch, counting from the first `@@` hunk header.

```python
def get_added_line_positions(patch):
    """
    Find positions of all added lines in a patch.
    
    Returns list of (position, new_line_number, text) tuples.
    """
    positions = []
    position = 0
    new_line = 0
    
    for line in patch.split('\n'):
        if line.startswith('@@'):
            # Parse hunk header
            match = re.match(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
            if match:
                new_line = int(match.group(2))
            position += 1  # The @@ line itself counts as position
            
        elif line.startswith('+'):
            position += 1
            positions.append((position, new_line, line[1:]))
            new_line += 1
            
        elif line.startswith('-'):
            position += 1
            # Removed lines don't increment new_line
            
        elif line.startswith(' '):
            position += 1
            new_line += 1
            
        elif line.startswith('\\'):
            # "No newline at end of file" marker
            pass
    
    return positions

# Usage: Find positions of all added lines
files = pr.get_files()
for file in files:
    if file.patch:
        added = get_added_line_positions(file.patch)
        for pos, line_num, text in added:
            print(f"  Added line {line_num} at position {pos}: {text[:60]}")
```

### 6.4 Using the Compare API for File Diffs

```python
# Get detailed comparison between two commits
comparison = repo.compare(pr.base.sha, pr.head.sha)

for file in comparison.files:
    print(f"File: {file.filename}")
    print(f"Status: {file.status}")
    
    # The patch attribute has the unified diff
    if file.patch:
        print(f"Patch length: {len(file.patch)} chars")
        
    # Access the raw diff URL
    print(f"Diff URL: {file.diff_url}")  # If available
```

---

## 7. Rate Limiting & Pagination

### 7.1 GitHub API Rate Limits

| Token Type | Rate Limit | Notes |
|------------|-----------|-------|
| Unauthenticated | 60 requests/hour | Not useful for agents |
| `GITHUB_TOKEN` (Actions) | 1,000 requests/hour per repository | Shared across all workflows |
| Personal Access Token | 5,000 requests/hour | Per user |
| GitHub App | 15,000 requests/hour | Per app installation |
| GitHub App (Enterprise) | 15,000+ requests/hour | Higher for Enterprise |

### 7.2 Checking Rate Limit Status

```python
import requests

def check_rate_limit(token):
    """Check current rate limit status."""
    url = "https://api.github.com/rate_limit"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    response = requests.get(url, headers=headers)
    data = response.json()
    
    core = data["resources"]["core"]
    print(f"Core API:")
    print(f"  Limit: {core['limit']}")
    print(f"  Remaining: {core['remaining']}")
    print(f"  Reset: {core['reset']} (Unix timestamp)")
    print(f"  Used: {core['used']}")
    
    # Also check search and graphql limits
    search = data["resources"]["search"]
    print(f"Search API: {search['remaining']}/{search['limit']} remaining")
    
    return core

# Usage
rate_info = check_rate_limit(TOKEN)
if rate_info["remaining"] < 100:
    print("WARNING: Running low on API quota!")
```

### 7.3 Rate Limit Headers

Every API response includes rate limit headers:

```python
import requests
import time

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json"
}

response = requests.get("https://api.github.com/user", headers=headers)

# Check headers
print(f"X-RateLimit-Limit: {response.headers.get('X-RateLimit-Limit')}")
print(f"X-RateLimit-Remaining: {response.headers.get('X-RateLimit-Remaining')}")
print(f"X-RateLimit-Reset: {response.headers.get('X-RateLimit-Reset')}")
print(f"X-RateLimit-Used: {response.headers.get('X-RateLimit-Used')}")

# If running low, wait until reset
remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
if remaining < 10:
    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
    wait_seconds = reset_time - int(time.time()) + 5
    print(f"Rate limit low. Waiting {wait_seconds} seconds...")
    time.sleep(max(0, wait_seconds))
```

### 7.4 Implementing Rate Limit Handling

```python
import time
import requests
from functools import wraps

class RateLimitHandler:
    """Decorator/wrapper for API calls with rate limit handling."""
    
    def __init__(self, min_remaining=50, token=None):
        self.min_remaining = min_remaining
        self.token = token
        self.last_remaining = None
        self.reset_time = None
    
    def check_rate_limit(self):
        """Check current rate limit and sleep if needed."""
        if self.last_remaining is None or self.last_remaining < self.min_remaining:
            url = "https://api.github.com/rate_limit"
            headers = {"Authorization": f"Bearer {self.token}"}
            response = requests.get(url, headers=headers)
            data = response.json()
            
            core = data["resources"]["core"]
            self.last_remaining = core["remaining"]
            self.reset_time = core["reset"]
            
            if self.last_remaining < self.min_remaining:
                wait = self.reset_time - int(time.time()) + 5
                if wait > 0:
                    print(f"Rate limit low ({self.last_remaining}). Sleeping {wait}s...")
                    time.sleep(wait)
                    self.last_remaining = None  # Reset to check again
    
    def request(self, method, url, **kwargs):
        """Make a request with rate limit awareness."""
        self.check_rate_limit()
        
        headers = kwargs.pop('headers', {})
        headers.setdefault("Authorization", f"Bearer {self.token}")
        headers.setdefault("Accept", "application/vnd.github+json")
        
        response = requests.request(method, url, headers=headers, **kwargs)
        
        # Update rate limit tracking from response headers
        if 'X-RateLimit-Remaining' in response.headers:
            self.last_remaining = int(response.headers['X-RateLimit-Remaining'])
            self.reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
        
        # Handle rate limit exceeded
        if response.status_code == 403 and 'rate limit' in response.text.lower():
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            wait = reset_time - int(time.time()) + 5
            print(f"Rate limited! Waiting {wait}s...")
            time.sleep(max(0, wait))
            return self.request(method, url, headers=headers, **kwargs)
        
        return response

# Usage
handler = RateLimitHandler(min_remaining=100, token=TOKEN)
response = handler.request("GET", "https://api.github.com/user/repos")
```

### 7.5 Pagination for Large PRs

GitHub paginates most list endpoints with 30 items per page by default (max 100).

```python
import requests

def paginated_get(url, headers, params=None, per_page=100):
    """
    Generator that yields all items across all pages.
    """
    params = params or {}
    params["per_page"] = per_page
    page = 1
    
    while True:
        params["page"] = page
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        items = response.json()
        if not items:
            break
        
        for item in items:
            yield item
        
        # Check if there's a next page
        if 'next' not in response.links:
            break
        
        page += 1

# Usage: Get all files in a large PR
url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
headers = {"Authorization": f"Bearer {TOKEN}"}

all_files = list(paginated_get(url, headers, per_page=100))
print(f"Total files: {len(all_files)}")

# Usage: Get all commits in a PR
commits_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/commits"
all_commits = list(paginated_get(commits_url, headers, per_page=100))
print(f"Total commits: {len(all_commits)}")
```

### 7.6 PyGithub Pagination

PyGithub handles pagination automatically for most methods:

```python
# PyGithub's PaginatedList handles pagination transparently
files = pr.get_files()  # Returns PaginatedList

# Iterate — PyGithub fetches pages automatically
for file in files:
    print(file.filename)

# Get total count (may trigger a fetch)
print(f"Total files: {files.totalCount}")

# Get all items as a list (fetches all pages)
all_files = list(files)

# Get specific page
page_2 = files.get_page(1)  # 0-indexed

# Control page size (if supported by the method)
# Some methods accept per_page parameter
```

### 7.7 Optimizing for Large PRs

```python
def review_large_pr(repo, pr_number, max_files=50, max_lines_per_file=500):
    """
    Review a PR with limits to avoid rate limits and timeouts.
    
    Strategy:
    1. Limit number of files reviewed
    2. Limit file size
    3. Skip generated files (lock files, etc.)
    4. Prioritize by change size
    """
    pr = repo.get_pull(pr_number)
    
    # Get all files and sort by change size
    files = list(pr.get_files())
    files.sort(key=lambda f: f.changes, reverse=True)
    
    # Skip common generated files
    skip_patterns = [
        'package-lock.json',
        'yarn.lock',
        'poetry.lock',
        'Cargo.lock',
        'Gemfile.lock',
        '.snap',  # Snapshot files
        'dist/',
        'build/',
    ]
    
    reviewed = 0
    for file in files:
        if reviewed >= max_files:
            break
            
        # Skip generated files
        if any(pattern in file.filename for pattern in skip_patterns):
            continue
        
        # Skip very large files
        if file.changes > max_lines_per_file:
            print(f"Skipping {file.filename} (too large: {file.changes} changes)")
            continue
        
        # Skip binary files (no patch)
        if not file.patch:
            continue
        
        # Review this file
        print(f"Reviewing: {file.filename}")
        # ... your AI review logic here ...
        reviewed += 1
    
    return reviewed
```

### 7.8 Conditional Requests (ETag Caching)

```python
import requests

# Cache for ETags
etag_cache = {}

def conditional_get(url, headers, cache_key):
    """
    Make a conditional GET request using ETag.
    Returns (data, from_cache) tuple.
    """
    if cache_key in etag_cache:
        headers["If-None-Match"] = etag_cache[cache_key]
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 304:
        # Not modified — return cached data
        return None, True
    
    if response.status_code == 200:
        # Store ETag for next time
        if 'ETag' in response.headers:
            etag_cache[cache_key] = response.headers['ETag']
        return response.json(), False
    
    response.raise_for_status()

# Usage
headers = {"Authorization": f"Bearer {TOKEN}"}
data, cached = conditional_get(
    "https://api.github.com/repos/owner/repo/pulls/42/files",
    headers,
    cache_key="pr-42-files"
)
print(f"From cache: {cached}")
```

**Note:** Conditional requests that return 304 **do not count against your rate limit**.

---

## 8. Complete Working Example

Here's a complete, production-ready AI code review agent:

```python
#!/usr/bin/env python3
"""
AI Code Review Agent
A complete example of using GitHub API for automated PR review.
"""

import os
import re
import sys
import time
import base64
import requests
from github import Github


class GitHubReviewAgent:
    """AI-powered code review agent using GitHub API."""
    
    def __init__(self, token, repo_name, pr_number):
        self.token = token
        self.repo_name = repo_name
        self.pr_number = int(pr_number)
        
        self.g = Github(token)
        self.repo = self.g.get_repo(repo_name)
        self.pr = self.repo.get_pull(self.pr_number)
        
        # Rate limit tracking
        self.api_calls = 0
        self.rate_limit_remaining = None
    
    def check_rate_limit(self, min_remaining=100):
        """Check and respect rate limits."""
        if self.rate_limit_remaining is None or self.rate_limit_remaining < min_remaining:
            url = "https://api.github.com/rate_limit"
            headers = {"Authorization": f"Bearer {self.token}"}
            response = requests.get(url, headers=headers)
            data = response.json()
            
            core = data["resources"]["core"]
            self.rate_limit_remaining = core["remaining"]
            reset_time = core["reset"]
            
            if self.rate_limit_remaining < min_remaining:
                wait = reset_time - int(time.time()) + 5
                if wait > 0:
                    print(f"Rate limit low ({self.rate_limit_remaining}). Waiting {wait}s...")
                    time.sleep(wait)
    
    def get_changed_files(self, max_files=50):
        """Get list of changed files, skipping generated files."""
        skip_patterns = [
            'package-lock.json', 'yarn.lock', 'poetry.lock',
            'Cargo.lock', 'Gemfile.lock', '.snap',
        ]
        
        files = list(self.pr.get_files())
        files.sort(key=lambda f: f.changes, reverse=True)
        
        result = []
        for file in files:
            if len(result) >= max_files:
                break
            if any(p in file.filename for p in skip_patterns):
                continue
            if not file.patch:
                continue
            result.append(file)
        
        return result
    
    def get_file_content(self, path, ref):
        """Get file content at a specific ref."""
        try:
            content_file = self.repo.get_contents(path, ref=ref)
            return content_file.decoded_content.decode('utf-8')
        except Exception as e:
            print(f"Could not read {path} at {ref}: {e}")
            return None
    
    def parse_patch_positions(self, patch):
        """Parse patch to find positions of added lines."""
        positions = []
        position = 0
        new_line = 0
        
        for line in patch.split('\n'):
            if line.startswith('@@'):
                match = re.match(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
                if match:
                    new_line = int(match.group(2))
                position += 1
            elif line.startswith('+'):
                position += 1
                positions.append((position, new_line, line[1:]))
                new_line += 1
            elif line.startswith('-'):
                position += 1
            elif line.startswith(' '):
                position += 1
                new_line += 1
        
        return positions
    
    def analyze_file(self, file):
        """Analyze a file and return review comments."""
        comments = []
        
        # Get both versions
        base_content = self.get_file_content(file.filename, self.pr.base.ref)
        head_content = self.get_file_content(file.filename, self.pr.head.ref)
        
        # Get added line positions
        added_positions = self.parse_patch_positions(file.patch)
        
        # Simple heuristic analysis (replace with your AI model)
        for pos, line_num, text in added_positions:
            # Example: flag lines with "TODO" or "FIXME"
            if 'TODO' in text.upper():
                comments.append({
                    "path": file.filename,
                    "position": pos,
                    "body": f"⚠️ **TODO found** at line {line_num}: `{text.strip()}`\n\nConsider resolving this before merging.",
                    "side": "RIGHT"
                })
            
            # Example: flag very long lines
            if len(text) > 120:
                comments.append({
                    "path": file.filename,
                    "position": pos,
                    "body": f"📏 **Line too long** ({len(text)} chars). Consider breaking this into multiple lines.",
                    "side": "RIGHT"
                })
        
        return comments
    
    def post_review(self, comments, summary):
        """Post a review with inline comments."""
        if not comments:
            # Post a simple approval with summary
            self.pr.create_review(
                body=summary,
                event="COMMENT"
            )
            print("Posted summary review (no inline comments)")
            return
        
        # GitHub allows max 100 comments per review
        # If more, split into multiple reviews
        batch_size = 100
        for i in range(0, len(comments), batch_size):
            batch = comments[i:i+batch_size]
            is_first = (i == 0)
            
            self.pr.create_review(
                body=summary if is_first else f"Additional comments (batch {i//batch_size + 1})",
                comments=batch,
                event="COMMENT"
            )
            print(f"Posted review batch with {len(batch)} comments")
    
    def run(self):
        """Run the complete review process."""
        print(f"Reviewing PR #{self.pr_number}: {self.pr.title}")
        print(f"Branch: {self.pr.head.ref} -> {self.pr.base.ref}")
        print(f"Commits: {self.pr.commits}")
        print()
        
        # Check rate limit
        self.check_rate_limit()
        
        # Get changed files
        files = self.get_changed_files(max_files=50)
        print(f"Analyzing {len(files)} files...")
        
        all_comments = []
        for file in files:
            print(f"  Analyzing: {file.filename}")
            comments = self.analyze_file(file)
            all_comments.extend(comments)
        
        # Build summary
        summary = f"""## 🤖 AI Code Review

**Files reviewed:** {len(files)}
**Inline comments:** {len(all_comments)}

*This is an automated review. Please verify all suggestions before applying.*
"""
        
        # Post review
        print(f"\nPosting {len(all_comments)} comments...")
        self.post_review(all_comments, summary)
        
        print("\nReview complete!")


def main():
    """Entry point for GitHub Actions."""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    pr_number = os.environ.get("PR_NUMBER")
    
    if not all([token, repo, pr_number]):
        print("Error: GITHUB_TOKEN, GITHUB_REPOSITORY, and PR_NUMBER required")
        sys.exit(1)
    
    agent = GitHubReviewAgent(token, repo, pr_number)
    agent.run()


if __name__ == "__main__":
    main()
```

### Accompanying GitHub Actions Workflow

```yaml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  ai-review:
    runs-on: ubuntu-latest
    
    permissions:
      contents: read
      pull-requests: write
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          pip install PyGithub requests
          
      - name: Run AI Review
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
        run: |
          python scripts/ai_review.py
```

---

## 9. Common Pitfalls & Troubleshooting

### 9.1 Position vs Line Number Confusion

**Problem:** Using absolute file line numbers instead of diff positions.

**Solution:** The `position` parameter is the **1-based index** within the file's patch, counting from the first `@@` hunk header. Use the `parse_patch_positions()` helper from Section 6.3.

### 9.2 Commenting on Unchanged Lines

**Problem:** GitHub API only allows review comments on lines that appear in the PR diff.

**Solution:** You can only comment on:
- Added lines (`+` in the patch)
- Removed lines (`-` in the patch)
- Context lines (` ` in the patch) that are part of a hunk

You **cannot** comment on lines that are not part of the diff. For general feedback, use `create_issue_comment()` instead.

### 9.3 Wrong Commit SHA

**Problem:** Using the PR's base commit instead of the latest HEAD commit.

**Solution:** Always use the latest commit in the PR:

```python
commits = list(pr.get_commits())
latest_commit = commits[-1]  # NOT pr.head.sha for the review API
commit_id = latest_commit.sha
```

### 9.4 File Not Found for Removed Files

**Problem:** Trying to read content of deleted files.

**Solution:** Check `file.status` before fetching:

```python
if file.status == 'removed':
    # File was deleted — no HEAD version exists
    base_content = repo.get_contents(file.filename, ref=pr.base.ref)
else:
    head_content = repo.get_contents(file.filename, ref=pr.head.ref)
```

### 9.5 422 Validation Failed

**Problem:** Getting `422 Unprocessable Entity` when creating review comments.

**Common causes:**
- `position` is out of range (larger than the patch length)
- `commit_id` doesn't match the latest commit
- `path` doesn't match exactly (case-sensitive)
- `side` is wrong for the line type

**Solution:**

```python
# Verify the position is valid
patch_lines = file.patch.split('\n')
max_position = len([l for l in patch_lines if l.startswith(('@@', '+', '-', ' '))])

if position > max_position:
    print(f"Invalid position {position} for file with {max_position} positions")
    continue
```

### 9.6 Rate Limit Exhaustion in Large PRs

**Problem:** Hitting rate limits when reviewing PRs with many files.

**Solution:**
1. Limit files reviewed (see Section 7.7)
2. Use `per_page=100` to reduce API calls
3. Cache file contents between runs
4. Use conditional requests (ETag)
5. Consider using a GitHub App instead of PAT (15,000 vs 5,000/hour)

### 9.7 Fork PRs and GITHUB_TOKEN

**Problem:** `pull_request` events from forks get a read-only token.

**Solution:** Use `pull_request_target` event (with security caution):

```yaml
on:
  pull_request_target:
    types: [opened, synchronize]

# WARNING: This runs with write access to the base repo
# Only use if you fully trust the PR code (e.g., don't execute untrusted code)
```

**Security note:** Never execute untrusted code from forks when using `pull_request_target`. Only use the API to read PR metadata and post comments.

### 9.8 Binary Files in PRs

**Problem:** Binary files (images, compiled code) don't have a `.patch` attribute.

**Solution:**

```python
for file in pr.get_files():
    if not file.patch:
        print(f"Skipping binary file: {file.filename}")
        continue
    # ... process text files only
```

### 9.9 Large File Patches Truncated

**Problem:** GitHub truncates patches for very large files (>300 changes by default).

**Solution:** Fetch the full file content separately:

```python
if file.changes > 300:
    # Patch might be truncated — fetch full file
    content = repo.get_contents(file.filename, ref=pr.head.ref)
    full_text = content.decoded_content.decode('utf-8')
    # Analyze full_text instead of patch
```

---

## Appendix A: Quick Reference Card

### Endpoint Summary

| Task | Endpoint | PyGithub Method |
|------|----------|-----------------|
| Get PR details | `GET /pulls/{n}` | `repo.get_pull(n)` |
| Get PR files | `GET /pulls/{n}/files` | `pr.get_files()` |
| Get PR diff | `GET /pulls/{n}` + `Accept: diff` | `pr.diff_url` + requests |
| Get file contents | `GET /contents/{path}?ref={ref}` | `repo.get_contents(path, ref=...)` |
| Get git blob | `GET /git/blobs/{sha}` | `repo.get_git_blob(sha)` |
| Create review comment | `POST /pulls/{n}/comments` | `pr.create_review_comment(...)` |
| Create full review | `POST /pulls/{n}/reviews` | `pr.create_review(...)` |
| Create PR comment | `POST /issues/{n}/comments` | `pr.create_issue_comment(...)` |
| Compare commits | `GET /compare/{base}...{head}` | `repo.compare(base, head)` |

### Media Types

| Format | Accept Header |
|--------|--------------|
| JSON (default) | `application/vnd.github+json` |
| Raw diff | `application/vnd.github.v3.diff` |
| Raw patch | `application/vnd.github.v3.patch` |
| Raw file content | `application/vnd.github.raw` |
| Raw JSON content | `application/vnd.github.raw+json` |

### Required Permissions

| Feature | Permission |
|---------|-----------|
| Read files/diffs | `contents: read` |
| Post comments | `pull-requests: write` |
| Post issue comments | `issues: write` |
| Add labels | `pull-requests: write` |
| Request changes | `pull-requests: write` |

---

## Appendix B: Resources

- [PyGithub Documentation](https://pygithub.readthedocs.io/)
- [GitHub REST API Docs — Pulls](https://docs.github.com/en/rest/pulls/pulls)
- [GitHub REST API Docs — Review Comments](https://docs.github.com/en/rest/pulls/comments)
- [GitHub REST API Docs — Rate Limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
- [GitHub Actions — Workflow Permissions](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/controlling-permissions-for-github_token)
- [GitHub REST API Best Practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api)

---

*Document compiled for development teams building AI-powered code review automation. For questions or corrections, refer to the official GitHub API documentation linked above.*
