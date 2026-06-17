---
name: github-actions-hardening
description: >
  Use when reviewing GitHub Actions workflow files (.github/workflows/*.yml).
  Covers action pinning, permission scoping, injection prevention, secret
  handling, and pull_request_target misuse. Apply any time .github/workflows/*
  files appear in the diff.
---

# GitHub Actions Hardening

Security and correctness guidance for GitHub Actions workflows.

---

## 1. Pin actions to a full commit SHA

**What to check:** Any `uses: owner/action@tag` that is NOT pinned to a full
40-character commit SHA.  Tags (e.g. `@v4`) are mutable — an attacker who
compromises the action repository can push a new commit to the tag and inject
malicious code into your CI.

**Bad:**
```yaml
- uses: actions/checkout@v4
```

**Good:**
```yaml
# actions/checkout v4.2.2
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af68
```

**Why it matters:** This is a supply-chain attack surface that has been exploited in the wild (e.g., `tj-actions/changed-files`, `reviewdog` ecosystem).

---

## 2. Least-privilege `permissions`

**What to check:** Workflows that use the default (implicit) permissions, or that set `permissions: write-all` / `contents: write` at the top level when only a narrower scope is needed.

**Best practice:** Declare `permissions: {}` at the top of every workflow (deny-all default), then grant the minimum per-job:

```yaml
permissions: {}

jobs:
  build:
    permissions:
      contents: read
      pull-requests: write   # only if you need to comment on PRs
```

---

## 3. `pull_request_target` misuse

**What to check:** Workflows triggered by `pull_request_target` that check out the PR's head commit or run code from the PR's branch.  `pull_request_target` runs in the context of the **base** repository with write permissions — running untrusted code from the fork is a critical vulnerability.

**Safe pattern:** Check out the PR head only after explicitly limiting permissions:
```yaml
on:
  pull_request_target:
    types: [labeled]   # only trigger after a maintainer labels

jobs:
  safe:
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@<SHA>
        with:
          ref: ${{ github.event.pull_request.head.sha }}
```

**Unsafe (flag as critical):**
```yaml
on: pull_request_target
jobs:
  build:
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.ref }}
      - run: make build   # runs attacker-controlled code with WRITE token
```

---

## 4. Expression injection in `run` steps

**What to check:** Interpolating `${{ github.event.* }}` or other untrusted context values directly into shell `run:` steps.  An attacker can include shell metacharacters in a PR title, branch name, or commit message to inject commands.

**Bad:**
```yaml
- run: echo "PR title is ${{ github.event.pull_request.title }}"
```

**Good:** Assign to an environment variable first:
```yaml
- name: Echo title
  env:
    TITLE: ${{ github.event.pull_request.title }}
  run: echo "PR title is $TITLE"
```

---

## 5. Secrets in logs

**What to check:** `echo ${{ secrets.MY_SECRET }}`, `run: curl -H "Authorization: $TOKEN"` where `$TOKEN` is set from a secret directly in the command string.

**Fix:** Pass secrets via environment variables (`env:` block), never interpolate them directly into command strings.

---

## 6. Missing `timeout-minutes`

**What to check:** Jobs or steps without an explicit `timeout-minutes` setting.  A hung step will consume runner minutes until the GitHub default timeout (6 hours) is reached.

**Best practice:** Set a reasonable per-job timeout:
```yaml
jobs:
  test:
    timeout-minutes: 20
```
