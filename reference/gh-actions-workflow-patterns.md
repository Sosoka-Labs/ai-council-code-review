# GitHub Actions Workflow Patterns for AI Code Review Agents

## Comprehensive Reference for Development Teams

**Date:** 2026-06-01  
**Scope:** PR-triggered workflows, checkout patterns, Python setup, inter-step data passing, GitHub API access, security, and large PR handling.

---

## Table of Contents

1. [Complete PR-Triggered Workflow YAML](#1-complete-pr-triggered-workflow-yaml)
2. [Checkout & Fetch-Depth for Diff History](#2-checkout--fetch-depth-for-diff-history)
3. [Checking Out the Base Branch for Comparison](#3-checking-out-the-base-branch-for-comparison)
4. [Python Setup in GitHub Actions](#4-python-setup-in-github-actions)
5. [Passing Data Between Workflow Steps](#5-passing-data-between-workflow-steps)
6. [Running Python Scripts with Repo & API Access](#6-running-python-scripts-with-repo--api-access)
7. [Security Best Practices](#7-security-best-practices)
8. [Handling Large PRs](#8-handling-large-prs)
9. [Complete Working Example](#9-complete-working-example)
10. [Quick Reference Cheat Sheet](#10-quick-reference-cheat-sheet)

---

## 1. Complete PR-Triggered Workflow YAML

### 1.1 Minimal AI Review Workflow

```yaml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
    branches: [main, develop]

permissions:
  contents: read
  pull-requests: write

jobs:
  ai-review:
    name: AI Code Review
    runs-on: ubuntu-latest
    if: github.event.pull_request.draft == false

    steps:
      - name: Checkout PR branch
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run AI Review Agent
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
          REPO: ${{ github.repository }}
          BASE_SHA: ${{ github.event.pull_request.base.sha }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha }}
        run: |
          python scripts/ai_review.py \
            --pr-number "$PR_NUMBER" \
            --repo "$REPO" \
            --base-sha "$BASE_SHA" \
            --head-sha "$HEAD_SHA"
```

### 1.2 Advanced Workflow with Multiple Review Modes

```yaml
name: Comprehensive AI Review

on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
  issue_comment:
    types: [created]

permissions:
  contents: read
  pull-requests: write
  issues: write

jobs:
  # Job 1: Automatic review on PR events
  auto-review:
    name: Automatic AI Review
    runs-on: ubuntu-latest
    if: |
      github.event_name == 'pull_request' &&
      github.event.pull_request.draft == false

    steps:
      - name: Checkout PR branch
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Get changed files
        id: changed-files
        run: |
          # Get list of changed files for this PR
          git fetch origin ${{ github.event.pull_request.base.ref }}
          CHANGED_FILES=$(git diff --name-only origin/${{ github.event.pull_request.base.ref }}...HEAD | tr '\n' ' ')
          echo "files=$CHANGED_FILES" >> $GITHUB_OUTPUT
          echo "count=$(echo "$CHANGED_FILES" | wc -w)" >> $GITHUB_OUTPUT

      - name: Run AI review (conditional on size)
        if: steps.changed-files.outputs.count != '0'
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
          REPO: ${{ github.repository }}
          CHANGED_FILES: ${{ steps.changed-files.outputs.files }}
        run: |
          python scripts/ai_review.py \
            --pr-number "$PR_NUMBER" \
            --repo "$REPO" \
            --files "$CHANGED_FILES" \
            --mode full

  # Job 2: On-demand review via PR comment
  on-demand-review:
    name: On-Demand AI Review
    runs-on: ubuntu-latest
    if: |
      github.event_name == 'issue_comment' &&
      github.event.issue.pull_request &&
      contains(github.event.comment.body, '/ai-review')

    steps:
      - name: Checkout PR branch
        uses: actions/checkout@v4
        with:
          ref: refs/pull/${{ github.event.issue.number }}/head
          fetch-depth: 0

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run on-demand review
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          PR_NUMBER: ${{ github.event.issue.number }}
          REPO: ${{ github.repository }}
          COMMENT_ID: ${{ github.event.comment.id }}
        run: |
          python scripts/ai_review.py \
            --pr-number "$PR_NUMBER" \
            --repo "$REPO" \
            --mode on-demand \
            --comment-id "$COMMENT_ID"
```

### 1.3 Workflow Trigger Event Reference

| Event | When It Fires | Use Case |
|-------|--------------|----------|
| `pull_request` `opened` | New PR created | Initial review |
| `pull_request` `synchronize` | New commits pushed to PR | Re-review on changes |
| `pull_request` `reopened` | Closed PR reopened | Re-review |
| `pull_request` `ready_for_review` | Draft PR marked ready | Review when ready |
| `issue_comment` `created` | Comment on PR/issue | On-demand `/ai-review` trigger |

---

## 2. Checkout & Fetch-Depth for Diff History

### 2.1 Understanding `fetch-depth`

The `fetch-depth` parameter in `actions/checkout` controls how many commits are fetched:

| Value | Behavior | Use Case |
|-------|----------|----------|
| `1` (default) | Only the latest commit | Fast checkout, no history needed |
| `2` | Last 2 commits | Basic diff against previous commit |
| `0` | Full history | Complete diff analysis, tags, branches |
| `N` | Last N commits | Specific history window |

### 2.2 Fetch-Depth for PR Diff Analysis

For AI code review agents, you typically need **full history** (`fetch-depth: 0`) because:

- You need the merge base to compute accurate diffs
- The PR may have many commits
- You may need to compare against the base branch

```yaml
- name: Checkout with full history
  uses: actions/checkout@v4
  with:
    fetch-depth: 0
```

### 2.3 Optimized Fetch for Large Repos

If the repo is very large and you only need PR history:

```yaml
- name: Checkout with shallow history
  uses: actions/checkout@v4
  with:
    fetch-depth: 100  # Fetch last 100 commits (usually sufficient)

- name: Fetch base branch for comparison
  run: |
    git fetch origin ${{ github.event.pull_request.base.ref }} --depth=100
```

### 2.4 Computing the Diff

```yaml
- name: Compute PR diff
  id: diff
  run: |
    # Method 1: Three-dot diff (merge-base to HEAD)
    git diff origin/${{ github.event.pull_request.base.ref }}...HEAD > pr_diff.txt

    # Method 2: Two-dot diff (base branch tip to HEAD)
    git diff origin/${{ github.event.pull_request.base.ref }}..HEAD > pr_diff.txt

    # Method 3: Diff with merge base
    MERGE_BASE=$(git merge-base origin/${{ github.event.pull_request.base.ref }} HEAD)
    git diff $MERGE_BASE HEAD > pr_diff.txt

    # Count changed files
    CHANGED_COUNT=$(git diff --name-only origin/${{ github.event.pull_request.base.ref }}...HEAD | wc -l)
    echo "changed_count=$CHANGED_COUNT" >> $GITHUB_OUTPUT

    # Count total lines changed
    TOTAL_LINES=$(git diff --stat origin/${{ github.event.pull_request.base.ref }}...HEAD | tail -1 | awk '{print $4}')
    echo "total_lines=$TOTAL_LINES" >> $GITHUB_OUTPUT
```

**Key difference:**
- `...` (three-dot): Shows changes introduced by the PR branch since it diverged from base
- `..` (two-dot): Shows changes between the current tips of both branches

For PR reviews, **three-dot diff** is almost always what you want.

---

## 3. Checking Out the Base Branch for Comparison

### 3.1 Single Checkout with Full History

The simplest approach: checkout the PR branch with full history, then fetch the base branch:

```yaml
- name: Checkout PR branch with full history
  uses: actions/checkout@v4
  with:
    fetch-depth: 0

- name: Fetch base branch
  run: |
    git fetch origin ${{ github.event.pull_request.base.ref }}:refs/remotes/origin/${{ github.event.pull_request.base.ref }}
```

### 3.2 Dual Checkout Pattern (Base + PR)

For scenarios where you need both branches checked out to separate directories:

```yaml
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      # Checkout PR branch (default)
      - name: Checkout PR branch
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      # Checkout base branch to subdirectory
      - name: Checkout base branch
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.base.ref }}
          path: base-branch
          fetch-depth: 0

      - name: Run comparison
        run: |
          # Compare specific files
          diff -u base-branch/src/file.py src/file.py || true
```

### 3.3 Using `actions/checkout` with `ref` for PR Head

When triggered by `issue_comment`, the default checkout doesn't give you the PR branch. Use the PR head ref:

```yaml
- name: Checkout PR head
  uses: actions/checkout@v4
  with:
    ref: refs/pull/${{ github.event.issue.number }}/head
    fetch-depth: 0

- name: Fetch base branch
  run: |
    git fetch origin ${{ github.event.pull_request.base.ref }}:refs/remotes/origin/${{ github.event.pull_request.base.ref }}
```

### 3.4 Complete Checkout Strategy for AI Review

```yaml
- name: Checkout and prepare for review
  uses: actions/checkout@v4
  with:
    fetch-depth: 0

- name: Setup git remotes and fetch base
  run: |
    # Ensure we have the base branch
    git fetch origin ${{ github.event.pull_request.base.ref }} --depth=100

    # Get the merge base
    MERGE_BASE=$(git merge-base origin/${{ github.event.pull_request.base.ref }} HEAD)
    echo "merge_base=$MERGE_BASE" >> $GITHUB_ENV

    # Get changed files list
    git diff --name-only origin/${{ github.event.pull_request.base.ref }}...HEAD > changed_files.txt

    # Get diff stats
    git diff --stat origin/${{ github.event.pull_request.base.ref }}...HEAD > diff_stats.txt
```

---

## 4. Python Setup in GitHub Actions

### 4.1 Basic Python Setup with Caching

```yaml
- name: Setup Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.11'
    cache: 'pip'
    cache-dependency-path: |
      requirements.txt
      requirements-dev.txt
```

### 4.2 Advanced Python Setup with Virtual Environment

```yaml
- name: Setup Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.11'

- name: Cache virtual environment
  uses: actions/cache@v4
  id: cache-venv
  with:
    path: .venv
    key: ${{ runner.os }}-venv-${{ hashFiles('requirements.txt', 'requirements-dev.txt') }}
    restore-keys: |
      ${{ runner.os }}-venv-

- name: Create virtual environment
  if: steps.cache-venv.outputs.cache-hit != 'true'
  run: |
    python -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip
    pip install -r requirements.txt

- name: Activate venv and run
  run: |
    source .venv/bin/activate
    python scripts/ai_review.py
```

### 4.3 Multi-Version Matrix (for testing your agent)

```yaml
strategy:
  matrix:
    python-version: ['3.10', '3.11', '3.12']
    os: [ubuntu-latest, macos-latest]

steps:
  - uses: actions/checkout@v4

  - name: Setup Python ${{ matrix.python-version }}
    uses: actions/setup-python@v5
    with:
      python-version: ${{ matrix.python-version }}
      cache: 'pip'

  - name: Install dependencies
    run: |
      python -m pip install --upgrade pip
      pip install -r requirements.txt
      pip install -r requirements-dev.txt
```

### 4.4 Poetry Setup (Alternative Dependency Manager)

```yaml
- name: Setup Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.11'

- name: Install Poetry
  uses: snok/install-poetry@v1
  with:
    version: 1.8.0
    virtualenvs-create: true
    virtualenvs-in-project: true

- name: Cache Poetry dependencies
  uses: actions/cache@v4
  id: cache-poetry
  with:
    path: .venv
    key: ${{ runner.os }}-poetry-${{ hashFiles('poetry.lock') }}

- name: Install dependencies
  if: steps.cache-poetry.outputs.cache-hit != 'true'
  run: poetry install --no-interaction --no-root

- name: Run agent
  run: |
    source .venv/bin/activate
    python scripts/ai_review.py
```

### 4.5 Requirements File for AI Review Agent

Example `requirements.txt`:

```
# GitHub API
PyGithub>=2.1.0

# HTTP client
requests>=2.31.0

# AI/LLM APIs
openai>=1.0.0
anthropic>=0.21.0

# Environment management
python-dotenv>=1.0.0

# Optional: Code parsing
tree-sitter>=0.20.0
Pygments>=2.16.0

# Testing (for agent development)
pytest>=7.4.0
pytest-cov>=4.1.0
```

---

## 5. Passing Data Between Workflow Steps

### 5.1 GITHUB_OUTPUT — Step Outputs (Same Job)

Use `GITHUB_OUTPUT` to pass data from one step to subsequent steps **within the same job**:

```yaml
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Analyze PR size
        id: analyze
        run: |
          # Set multiple outputs
          FILE_COUNT=$(git diff --name-only origin/main...HEAD | wc -l)
          LINE_COUNT=$(git diff --stat origin/main...HEAD | tail -1 | awk '{print $4}')
          
          echo "file_count=$FILE_COUNT" >> $GITHUB_OUTPUT
          echo "line_count=$LINE_COUNT" >> $GITHUB_OUTPUT
          echo "should_review=$([ $FILE_COUNT -lt 50 ] && echo 'true' || echo 'false')" >> $GITHUB_OUTPUT

      - name: Use outputs
        run: |
          echo "Files changed: ${{ steps.analyze.outputs.file_count }}"
          echo "Lines changed: ${{ steps.analyze.outputs.line_count }}"

      - name: Conditional review
        if: steps.analyze.outputs.should_review == 'true'
        run: |
          echo "Running review for ${{ steps.analyze.outputs.file_count }} files"
```

### 5.2 GITHUB_ENV — Environment Variables (Same Job)

Use `GITHUB_ENV` to set environment variables that persist across all subsequent steps **in the same job**:

```yaml
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set environment variables
        run: |
          echo "REVIEW_MODE=full" >> $GITHUB_ENV
          echo "MAX_FILES=50" >> $GITHUB_ENV
          echo "MERGE_BASE=$(git merge-base origin/main HEAD)" >> $GITHUB_ENV

      - name: Use environment variables
        run: |
          echo "Review mode: $REVIEW_MODE"
          echo "Max files: $MAX_FILES"
          echo "Merge base: $MERGE_BASE"
          python scripts/ai_review.py --mode "$REVIEW_MODE"
```

### 5.3 Artifacts — Sharing Files Between Jobs

Use artifacts to pass files between **different jobs** or preserve outputs:

```yaml
jobs:
  # Job 1: Extract and prepare data
  prepare:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Extract PR data
        run: |
          mkdir -p review-data
          git diff origin/main...HEAD > review-data/diff.txt
          git diff --name-only origin/main...HEAD > review-data/files.txt
          git log --oneline origin/main...HEAD > review-data/commits.txt

      - name: Upload PR data artifact
        uses: actions/upload-artifact@v4
        with:
          name: pr-data
          path: review-data/
          retention-days: 1

  # Job 2: Run AI review (depends on prepare)
  review:
    runs-on: ubuntu-latest
    needs: prepare
    steps:
      - uses: actions/checkout@v4

      - name: Download PR data
        uses: actions/download-artifact@v4
        with:
          name: pr-data
          path: review-data/

      - name: Run review
        run: |
          cat review-data/diff.txt | python scripts/ai_review.py

  # Job 3: Post results (depends on review)
  post:
    runs-on: ubuntu-latest
    needs: review
    steps:
      - name: Download review results
        uses: actions/download-artifact@v4
        with:
          name: review-results
```

### 5.4 Comparison: When to Use What

| Method | Scope | Data Type | Best For |
|--------|-------|-----------|----------|
| `GITHUB_OUTPUT` | Same job | Simple values | Step-to-step data passing |
| `GITHUB_ENV` | Same job | Environment variables | Configuration across steps |
| `Artifacts` | Between jobs | Files | Large data, job chaining, persistence |

### 5.5 Multi-Job Workflow with Artifacts

```yaml
jobs:
  extract:
    runs-on: ubuntu-latest
    outputs:
      file_count: ${{ steps.stats.outputs.file_count }}
      should_review: ${{ steps.stats.outputs.should_review }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Compute stats
        id: stats
        run: |
          COUNT=$(git diff --name-only origin/main...HEAD | wc -l)
          echo "file_count=$COUNT" >> $GITHUB_OUTPUT
          echo "should_review=$([ $COUNT -lt 100 ] && echo 'true' || echo 'false')" >> $GITHUB_OUTPUT

      - name: Upload diff
        uses: actions/upload-artifact@v4
        with:
          name: pr-diff
          path: diff.txt

  review:
    runs-on: ubuntu-latest
    needs: extract
    if: needs.extract.outputs.should_review == 'true'
    steps:
      - uses: actions/checkout@v4

      - name: Download diff
        uses: actions/download-artifact@v4
        with:
          name: pr-diff

      - name: Run AI review
        run: python scripts/ai_review.py --files ${{ needs.extract.outputs.file_count }}
```

---

## 6. Running Python Scripts with Repo & API Access

### 6.1 Complete Python Review Agent Script

```python
#!/usr/bin/env python3
"""
AI Code Review Agent for GitHub Actions

This script runs inside a GitHub Actions workflow and:
1. Accesses the checked-out repository
2. Computes the PR diff
3. Calls an AI API for review
4. Posts results as a PR comment

Environment variables expected:
  GITHUB_TOKEN      - GitHub API token (auto-provided by Actions)
  OPENAI_API_KEY    - OpenAI API key (from secrets)
  PR_NUMBER         - Pull request number
  REPO              - Repository in "owner/repo" format
  BASE_SHA          - Base commit SHA
  HEAD_SHA          - Head commit SHA
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from typing import List, Optional

import requests
from github import Github


class AIReviewAgent:
    def __init__(self):
        self.github_token = os.environ["GITHUB_TOKEN"]
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.pr_number = int(os.environ["PR_NUMBER"])
        self.repo_name = os.environ["REPO"]
        self.base_sha = os.environ.get("BASE_SHA", "")
        self.head_sha = os.environ.get("HEAD_SHA", "")

        # Initialize GitHub API client
        self.github = Github(self.github_token)
        self.repo = self.github.get_repo(self.repo_name)
        self.pr = self.repo.get_pull(self.pr_number)

    def get_changed_files(self) -> List[str]:
        """Get list of files changed in the PR."""
        # Method 1: Using git command
        result = subprocess.run(
            ["git", "diff", "--name-only", f"origin/{self.pr.base.ref}...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [f for f in result.stdout.strip().split("\n") if f]

    def get_diff_for_file(self, filepath: str) -> str:
        """Get the diff for a specific file."""
        result = subprocess.run(
            ["git", "diff", f"origin/{self.pr.base.ref}...HEAD", "--", filepath],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    def get_full_diff(self) -> str:
        """Get the full PR diff."""
        result = subprocess.run(
            ["git", "diff", f"origin/{self.pr.base.ref}...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    def get_file_content(self, filepath: str, ref: str = "HEAD") -> str:
        """Read file content from the checked-out repo."""
        try:
            result = subprocess.run(
                ["git", "show", f"{ref}:{filepath}"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError:
            return ""

    def call_openai_review(self, diff_text: str) -> str:
        """Call OpenAI API for code review."""
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY not set")

        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json",
        }

        # Truncate if too large
        max_diff_length = 15000  # Adjust based on model context
        truncated_diff = diff_text[:max_diff_length]
        if len(diff_text) > max_diff_length:
            truncated_diff += "\n\n[... diff truncated due to size ...]"

        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a senior software engineer conducting code review. "
                        "Analyze the diff and provide constructive feedback on: "
                        "1. Code quality and readability "
                        "2. Potential bugs or issues "
                        "3. Security concerns "
                        "4. Performance considerations "
                        "5. Best practices and style"
                    ),
                },
                {
                    "role": "user",
                    "content": f"Please review the following code diff:\n\n```diff\n{truncated_diff}\n```",
                },
            ],
            "temperature": 0.3,
            "max_tokens": 2000,
        }

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def post_pr_comment(self, body: str) -> None:
        """Post a comment on the PR."""
        self.pr.create_issue_comment(body)

    def post_review_comment(self, filepath: str, line: int, body: str) -> None:
        """Post a review comment on a specific line."""
        commit = self.repo.get_commit(self.head_sha)
        self.pr.create_review_comment(
            body=body,
            commit=commit,
            path=filepath,
            line=line,
        )

    def run_review(self, mode: str = "full") -> None:
        """Main review workflow."""
        print(f"Running AI review for PR #{self.pr_number} in {self.repo_name}")
        print(f"Mode: {mode}")

        # Get changed files
        changed_files = self.get_changed_files()
        print(f"Changed files: {len(changed_files)}")

        if not changed_files:
            print("No files to review.")
            return

        # Get diff
        diff_text = self.get_full_diff()
        diff_size = len(diff_text)
        print(f"Diff size: {diff_size} characters")

        # Skip if too large
        if diff_size > 50000:  # 50KB diff limit
            self.post_pr_comment(
                "## AI Code Review\n\n"
                "This PR is too large for automated review. "
                "Please consider breaking it into smaller PRs."
            )
            return

        # Call AI for review
        try:
            review_text = self.call_openai_review(diff_text)
        except Exception as e:
            print(f"AI review failed: {e}", file=sys.stderr)
            sys.exit(1)

        # Format and post review
        comment_body = (
            f"## AI Code Review\n\n"
            f"**Files reviewed:** {len(changed_files)}\n"
            f"**Diff size:** {diff_size} characters\n\n"
            f"---\n\n"
            f"{review_text}\n\n"
            f"---\n\n"
            f"*This review was generated automatically. Please verify all suggestions.*"
        )

        self.post_pr_comment(comment_body)
        print("Review posted successfully.")


def main():
    parser = argparse.ArgumentParser(description="AI Code Review Agent")
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--repo", type=str, required=True)
    parser.add_argument("--base-sha", type=str, default="")
    parser.add_argument("--head-sha", type=str, default="")
    parser.add_argument("--mode", type=str, default="full", choices=["full", "summary", "on-demand"])
    parser.add_argument("--files", type=str, default="")
    args = parser.parse_args()

    # Set environment variables from args if not already set
    os.environ.setdefault("PR_NUMBER", str(args.pr_number))
    os.environ.setdefault("REPO", args.repo)
    os.environ.setdefault("BASE_SHA", args.base_sha)
    os.environ.setdefault("HEAD_SHA", args.head_sha)

    agent = AIReviewAgent()
    agent.run_review(mode=args.mode)


if __name__ == "__main__":
    main()
```

### 6.2 Using GitHub API Directly (Alternative to PyGithub)

```python
import os
import requests

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = os.environ["REPO"]
PR_NUMBER = os.environ["PR_NUMBER"]

headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# Get PR details
pr_url = f"https://api.github.com/repos/{REPO}/pulls/{PR_NUMBER}"
response = requests.get(pr_url, headers=headers)
pr_data = response.json()

# Get PR diff
pr_diff_url = f"https://api.github.com/repos/{REPO}/pulls/{PR_NUMBER}"
diff_headers = {**headers, "Accept": "application/vnd.github.v3.diff"}
diff_response = requests.get(pr_diff_url, headers=diff_headers)
diff_text = diff_response.text

# Post a comment
comment_url = f"https://api.github.com/repos/{REPO}/issues/{PR_NUMBER}/comments"
comment_body = {"body": "AI Review: This looks good!"}
requests.post(comment_url, headers=headers, json=comment_body)

# Post a review (approving, requesting changes, etc.)
review_url = f"https://api.github.com/repos/{REPO}/pulls/{PR_NUMBER}/reviews"
review_data = {
    "body": "AI-generated review feedback",
    "event": "COMMENT",  # or "APPROVE", "REQUEST_CHANGES"
}
requests.post(review_url, headers=headers, json=review_data)
```

### 6.3 Accessing Workflow Context in Python

```python
import os
import json

# GitHub Actions provides a context file
GITHUB_EVENT_PATH = os.environ.get("GITHUB_EVENT_PATH")
if GITHUB_EVENT_PATH:
    with open(GITHUB_EVENT_PATH) as f:
        event_data = json.load(f)

# Key context variables
context = {
    "repository": os.environ.get("GITHUB_REPOSITORY"),
    "repository_owner": os.environ.get("GITHUB_REPOSITORY_OWNER"),
    "workflow": os.environ.get("GITHUB_WORKFLOW"),
    "run_id": os.environ.get("GITHUB_RUN_ID"),
    "run_number": os.environ.get("GITHUB_RUN_NUMBER"),
    "actor": os.environ.get("GITHUB_ACTOR"),
    "sha": os.environ.get("GITHUB_SHA"),
    "ref": os.environ.get("GITHUB_REF"),
    "head_ref": os.environ.get("GITHUB_HEAD_REF"),
    "base_ref": os.environ.get("GITHUB_BASE_REF"),
    "event_name": os.environ.get("GITHUB_EVENT_NAME"),
    "server_url": os.environ.get("GITHUB_SERVER_URL", "https://github.com"),
    "api_url": os.environ.get("GITHUB_API_URL", "https://api.github.com"),
    "graphql_url": os.environ.get("GITHUB_GRAPHQL_URL", "https://api.github.com/graphql"),
}

# For PR events, the event payload contains PR details
if GITHUB_EVENT_PATH:
    pr_data = event_data.get("pull_request", {})
    pr_context = {
        "number": pr_data.get("number"),
        "title": pr_data.get("title"),
        "body": pr_data.get("body"),
        "user": pr_data.get("user", {}).get("login"),
        "base_ref": pr_data.get("base", {}).get("ref"),
        "base_sha": pr_data.get("base", {}).get("sha"),
        "head_ref": pr_data.get("head", {}).get("ref"),
        "head_sha": pr_data.get("head", {}).get("sha"),
        "changed_files": pr_data.get("changed_files"),
        "additions": pr_data.get("additions"),
        "deletions": pr_data.get("deletions"),
    }
```

---

## 7. Security Best Practices

### 7.1 Token Permissions (Least Privilege)

Always declare the **minimum required permissions** at the workflow or job level:

```yaml
# Workflow-level permissions
permissions:
  contents: read          # Read repo contents
  pull-requests: write    # Post comments/reviews
  issues: write           # Post issue comments (if using issue_comment trigger)

# Job-level permissions (override workflow-level)
jobs:
  review:
    permissions:
      contents: read
      pull-requests: write
    runs-on: ubuntu-latest
    steps:
      # ...
```

**Permission Reference for AI Review Agents:**

| Permission | Level | Why Needed |
|------------|-------|------------|
| `contents` | `read` | Checkout code, read files |
| `pull-requests` | `write` | Post review comments, PR comments |
| `issues` | `write` | Post comments on issue-triggered workflows |
| `actions` | `read` | Read workflow artifacts (if needed) |
| `id-token` | `write` | Only if using OIDC for cloud auth |

### 7.2 Avoiding Secret Exposure in Logs

**NEVER echo secrets directly:**

```yaml
# BAD - Secret will be masked but still risky
- run: echo "${{ secrets.OPENAI_API_KEY }}"

# GOOD - Pass via environment
- run: python scripts/review.py
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

**GitHub automatically masks secrets** in logs, but only if:
1. They are stored in GitHub Secrets (not hardcoded)
2. They are referenced via `${{ secrets.XXX }}`

**Additional protections:**

```yaml
- name: Run review with secret
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  run: |
    # Prevent command echoing
    set +x
    python scripts/review.py
```

### 7.3 Handling Secrets in Python

```python
import os

# Read from environment (never hardcode)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# Validate
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")

# When logging, never print secrets
print(f"API key configured: {'yes' if OPENAI_API_KEY else 'no'}")
print(f"API key length: {len(OPENAI_API_KEY)}")  # Safe: only length, not value
```

### 7.4 Using OIDC for Cloud Authentication (Optional)

If your AI agent needs to access cloud resources (e.g., AWS Bedrock, Azure OpenAI), use OIDC instead of long-lived credentials:

```yaml
permissions:
  id-token: write    # Required for OIDC
  contents: read

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # AWS OIDC authentication
      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-actions-ai-review
          aws-region: us-east-1

      # Now you can use AWS CLI/SDK without storing secrets
      - name: Run review with AWS Bedrock
        run: python scripts/review_bedrock.py
```

### 7.5 Security Checklist

- [ ] Set `permissions:` explicitly at workflow or job level
- [ ] Use `secrets.GITHUB_TOKEN` (auto-generated, scoped to repo)
- [ ] Store API keys in GitHub Secrets, never in code
- [ ] Pin third-party actions to specific commit SHAs or versions
- [ ] Use `pull_request` trigger (not `pull_request_target`) for untrusted forks
- [ ] For fork PRs, use `pull_request` trigger (runs in fork context, no write access)
- [ ] For trusted repos, `pull_request_target` can be used with caution
- [ ] Review third-party actions before use
- [ ] Enable branch protection rules requiring review before merge

### 7.6 Handling Untrusted Fork PRs

```yaml
# For public repos with fork contributions:
# Use pull_request trigger (safer, runs in fork context)
# The GITHUB_TOKEN has read-only permissions for forks

on:
  pull_request:
    types: [opened, synchronize]

permissions:
  contents: read
  pull-requests: read    # Read-only for forks

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run read-only review
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          # This can read but NOT post comments
          python scripts/review_readonly.py

# If you need to post comments on fork PRs, use a two-workflow pattern:
# Workflow 1 (pull_request): Generates review output as artifact
# Workflow 2 (workflow_run): Reads artifact and posts comment (has write access)
```

---

## 8. Handling Large PRs

### 8.1 GitHub Limits Reference

| Limit | Value | Notes |
|-------|-------|-------|
| Max file size | 100 MiB | Cannot exceed |
| Warning file size | 50 MiB | Warning but allowed |
| Recommended repo size | < 1 GB | For optimal performance |
| Critical repo size | > 5 GB | GitHub may contact you |
| Workflow timeout | 6 hours (default) | Up to 72 hours configurable |
| Job timeout | 6 hours (default) | Per-job limit |
| API rate limit | 1,000 requests/hour | For GITHUB_TOKEN |
| PR diff max size | ~100,000 lines | API may truncate |

### 8.2 File Count and Size Limits in Workflow

```yaml
jobs:
  review:
    runs-on: ubuntu-latest
    timeout-minutes: 30  # Set a reasonable timeout
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Check PR size
        id: size-check
        run: |
          MAX_FILES=50
          MAX_LINES=5000
          MAX_DIFF_SIZE=50000  # 50KB

          CHANGED_FILES=$(git diff --name-only origin/main...HEAD)
          FILE_COUNT=$(echo "$CHANGED_FILES" | wc -l)
          TOTAL_LINES=$(git diff --stat origin/main...HEAD | tail -1 | awk '{print $4}')
          DIFF_SIZE=$(git diff origin/main...HEAD | wc -c)

          echo "file_count=$FILE_COUNT" >> $GITHUB_OUTPUT
          echo "total_lines=$TOTAL_LINES" >> $GITHUB_OUTPUT
          echo "diff_size=$DIFF_SIZE" >> $GITHUB_OUTPUT

          # Determine if we should skip
          if [ "$FILE_COUNT" -gt "$MAX_FILES" ]; then
            echo "skip_reason=Too many files ($FILE_COUNT > $MAX_FILES)" >> $GITHUB_OUTPUT
            echo "should_skip=true" >> $GITHUB_OUTPUT
          elif [ "$TOTAL_LINES" -gt "$MAX_LINES" ]; then
            echo "skip_reason=Too many lines changed ($TOTAL_LINES > $MAX_LINES)" >> $GITHUB_OUTPUT
            echo "should_skip=true" >> $GITHUB_OUTPUT
          elif [ "$DIFF_SIZE" -gt "$MAX_DIFF_SIZE" ]; then
            echo "skip_reason=Diff too large ($DIFF_SIZE > $MAX_DIFF_SIZE bytes)" >> $GITHUB_OUTPUT
            echo "should_skip=true" >> $GITHUB_OUTPUT
          else
            echo "should_skip=false" >> $GITHUB_OUTPUT
          fi

      - name: Skip large PRs
        if: steps.size-check.outputs.should_skip == 'true'
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          python scripts/post_comment.py \
            --message "## AI Review Skipped\n\n${{ steps.size-check.outputs.skip_reason }}\n\nPlease consider breaking this PR into smaller changes."

      - name: Run review
        if: steps.size-check.outputs.should_skip == 'false'
        run: python scripts/ai_review.py
```

### 8.3 Chunked Review for Large PRs

```yaml
jobs:
  review:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Get changed files
        id: files
        run: |
          git diff --name-only origin/main...HEAD > changed_files.txt
          CHANGED_COUNT=$(wc -l < changed_files.txt)
          echo "count=$CHANGED_COUNT" >> $GITHUB_OUTPUT

      - name: Review in chunks
        if: steps.files.outputs.count != '0'
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
          REPO: ${{ github.repository }}
        run: |
          # Review files in batches of 10
          BATCH_SIZE=10
          TOTAL_FILES=$(wc -l < changed_files.txt)
          BATCHES=$(( (TOTAL_FILES + BATCH_SIZE - 1) / BATCH_SIZE ))

          for i in $(seq 0 $((BATCHES - 1))); do
            START=$((i * BATCH_SIZE + 1))
            END=$((START + BATCH_SIZE - 1))
            BATCH_FILES=$(sed -n "${START},${END}p" changed_files.txt | tr '\n' ',')
            
            echo "Reviewing batch $((i + 1))/$BATCHES: files $START-$END"
            
            python scripts/ai_review.py \
              --pr-number "$PR_NUMBER" \
              --repo "$REPO" \
              --files "$BATCH_FILES" \
              --batch "$((i + 1))" \
              --total-batches "$BATCHES"
          done
```

### 8.4 Filtering Files by Type/Size

```yaml
- name: Filter reviewable files
  id: filter
  run: |
    # Only review source code files
    git diff --name-only origin/main...HEAD | \
      grep -E '\.(py|js|ts|jsx|tsx|java|go|rb|php|cs|cpp|c|h|swift|kt|rs)$' | \
      grep -v -E '(test|spec|__pycache__|node_modules|vendor)' > reviewable_files.txt

    # Skip files larger than 100KB
    while IFS= read -r file; do
      SIZE=$(git cat-file -s "HEAD:$file" 2>/dev/null || echo 0)
      if [ "$SIZE" -lt 102400 ]; then
        echo "$file" >> filtered_files.txt
      else
        echo "Skipping large file: $file ($SIZE bytes)"
      fi
    done < reviewable_files.txt

    COUNT=$(wc -l < filtered_files.txt)
    echo "count=$COUNT" >> $GITHUB_OUTPUT
```

### 8.5 Timeout Configuration

```yaml
jobs:
  review:
    runs-on: ubuntu-latest
    timeout-minutes: 30  # Fail fast if something hangs
    steps:
      # ...
      - name: Run review with timeout
        timeout-minutes: 20  # Per-step timeout
        run: python scripts/ai_review.py
```

---

## 9. Complete Working Example

### 9.1 Full Workflow File

`.github/workflows/ai-code-review.yml`:

```yaml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
    branches: [main, develop]
  issue_comment:
    types: [created]

permissions:
  contents: read
  pull-requests: write

concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.event.issue.number }}
  cancel-in-progress: true

jobs:
  ai-review:
    name: AI Code Review
    runs-on: ubuntu-latest
    timeout-minutes: 15
    if: |
      (github.event_name == 'pull_request' && !github.event.pull_request.draft) ||
      (github.event_name == 'issue_comment' && github.event.issue.pull_request && contains(github.event.comment.body, '/ai-review'))

    steps:
      # --------------------------------------------------
      # 1. Checkout
      # --------------------------------------------------
      - name: Checkout PR branch
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
          ref: ${{ github.event_name == 'issue_comment' && format('refs/pull/{0}/head', github.event.issue.number) || '' }}

      - name: Fetch base branch
        run: |
          BASE_REF="${{ github.event.pull_request.base.ref || github.event.issue.pull_request.base.ref }}"
          git fetch origin "$BASE_REF":refs/remotes/origin/"$BASE_REF"

      # --------------------------------------------------
      # 2. Setup Python
      # --------------------------------------------------
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
          cache-dependency-path: 'requirements.txt'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      # --------------------------------------------------
      # 3. Analyze PR
      # --------------------------------------------------
      - name: Analyze PR size
        id: analyze
        run: |
          BASE_REF="${{ github.event.pull_request.base.ref || 'main' }}"
          CHANGED_FILES=$(git diff --name-only origin/"$BASE_REF"...HEAD || true)
          FILE_COUNT=$(echo "$CHANGED_FILES" | grep -v '^$' | wc -l)
          TOTAL_LINES=$(git diff --stat origin/"$BASE_REF"...HEAD | tail -1 | awk '{print $4}' || echo 0)
          DIFF_SIZE=$(git diff origin/"$BASE_REF"...HEAD | wc -c || echo 0)

          echo "file_count=$FILE_COUNT" >> $GITHUB_OUTPUT
          echo "total_lines=$TOTAL_LINES" >> $GITHUB_OUTPUT
          echo "diff_size=$DIFF_SIZE" >> $GITHUB_OUTPUT

          # Determine if reviewable
          MAX_FILES=50
          MAX_LINES=5000
          MAX_DIFF_SIZE=50000

          if [ "$FILE_COUNT" -gt "$MAX_FILES" ] || [ "$TOTAL_LINES" -gt "$MAX_LINES" ] || [ "$DIFF_SIZE" -gt "$MAX_DIFF_SIZE" ]; then
            echo "should_review=false" >> $GITHUB_OUTPUT
          else
            echo "should_review=true" >> $GITHUB_OUTPUT
          fi

      # --------------------------------------------------
      # 4. Run AI Review
      # --------------------------------------------------
      - name: Run AI Review
        if: steps.analyze.outputs.should_review == 'true'
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          PR_NUMBER: ${{ github.event.pull_request.number || github.event.issue.number }}
          REPO: ${{ github.repository }}
          BASE_SHA: ${{ github.event.pull_request.base.sha || '' }}
          HEAD_SHA: ${{ github.sha }}
        run: |
          python scripts/ai_review.py \
            --pr-number "$PR_NUMBER" \
            --repo "$REPO" \
            --base-sha "$BASE_SHA" \
            --head-sha "$HEAD_SHA" \
            --mode "${{ github.event_name == 'issue_comment' && 'on-demand' || 'full' }}"

      # --------------------------------------------------
      # 5. Handle oversized PRs
      # --------------------------------------------------
      - name: Post skip message
        if: steps.analyze.outputs.should_review == 'false'
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          PR_NUMBER: ${{ github.event.pull_request.number || github.event.issue.number }}
          REPO: ${{ github.repository }}
        run: |
          python scripts/post_comment.py \
            --pr-number "$PR_NUMBER" \
            --repo "$REPO" \
            --message "## AI Review Skipped\n\nThis PR exceeds review limits (${{ steps.analyze.outputs.file_count }} files, ${{ steps.analyze.outputs.total_lines }} lines). Please consider breaking it into smaller changes."
```

### 9.2 Project Structure

```
.github/
  workflows/
    ai-code-review.yml      # Main workflow
scripts/
  ai_review.py              # Main review agent
  post_comment.py           # Helper to post comments
  utils.py                  # Shared utilities
requirements.txt            # Python dependencies
```

### 9.3 `requirements.txt`

```
PyGithub>=2.1.0
requests>=2.31.0
openai>=1.0.0
anthropic>=0.21.0
python-dotenv>=1.0.0
```

---

## 10. Quick Reference Cheat Sheet

### Workflow Triggers

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
    branches: [main, develop]
  issue_comment:
    types: [created]
```

### Checkout Patterns

```yaml
# Standard PR checkout
- uses: actions/checkout@v4
  with:
    fetch-depth: 0

# Checkout from issue_comment trigger
- uses: actions/checkout@v4
  with:
    ref: refs/pull/${{ github.event.issue.number }}/head
    fetch-depth: 0

# Fetch base branch
- run: git fetch origin ${{ github.event.pull_request.base.ref }} --depth=100
```

### Python Setup

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: '3.11'
    cache: 'pip'
- run: |
    python -m pip install --upgrade pip
    pip install -r requirements.txt
```

### Data Passing

```yaml
# GITHUB_OUTPUT (step to step)
- id: step1
  run: echo "value=123" >> $GITHUB_OUTPUT
- run: echo "${{ steps.step1.outputs.value }}"

# GITHUB_ENV (across steps)
- run: echo "VAR=value" >> $GITHUB_ENV
- run: echo "$VAR"

# Artifacts (job to job)
- uses: actions/upload-artifact@v4
  with:
    name: data
    path: output/
- uses: actions/download-artifact@v4
  with:
    name: data
```

### Security

```yaml
permissions:
  contents: read
  pull-requests: write

env:
  API_KEY: ${{ secrets.API_KEY }}
```

### Large PR Handling

```yaml
timeout-minutes: 15

- run: |
    FILE_COUNT=$(git diff --name-only origin/main...HEAD | wc -l)
    if [ "$FILE_COUNT" -gt 50 ]; then
      echo "PR too large"; exit 0
    fi
```

---

## References

1. GitHub Actions Documentation — [https://docs.github.com/en/actions](https://docs.github.com/en/actions)
2. `actions/checkout` — [https://github.com/actions/checkout](https://github.com/actions/checkout)
3. `actions/setup-python` — [https://github.com/actions/setup-python](https://github.com/actions/setup-python)
4. GitHub Actions Security — [https://docs.github.com/en/actions/security-guides](https://docs.github.com/en/actions/security-guides)
5. PyGithub Library — [https://github.com/PyGithub/PyGithub](https://github.com/PyGithub/PyGithub)
6. GitHub REST API — [https://docs.github.com/en/rest](https://docs.github.com/en/rest)
7. OpenAI API — [https://platform.openai.com/docs](https://platform.openai.com/docs)
8. StepSecurity Best Practices — [https://www.stepsecurity.io/blog/github-actions-secrets-management-best-practices](https://www.stepsecurity.io/blog/github-actions-secrets-management-best-practices)

---

*This reference was compiled for teams building AI-powered code review agents using GitHub Actions. All examples are production-ready and follow current best practices as of 2026.*
