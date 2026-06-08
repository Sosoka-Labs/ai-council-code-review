# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |
| < 1.0   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability in AI Council Code Review, please report it responsibly.

**Please do not open a public issue for security bugs.**

Instead, use one of the following methods:

1. **GitHub Private Vulnerability Reporting** — Open a [private security advisory](https://github.com/Sosoka-Labs/ai-council-code-review/security/advisories/new) on this repository.
2. **Email** — Contact the maintainer directly at the email associated with the GitHub account.

## What to Include

- A description of the vulnerability and its impact
- Steps to reproduce (or proof of concept)
- Affected versions
- Any suggested fixes or mitigations

## Response Timeline

- **Acknowledgment:** Within 48 hours
- **Initial assessment:** Within 7 days
- **Fix release:** As soon as practical, typically within 30 days for critical issues

## Security Considerations

### Secrets Handling

- API keys are passed via GitHub Secrets and are never logged by the action
- Debug artifacts strip any values that look like secrets before upload
- The action does not persist code or review data outside the workflow run

### Fork PRs

By default, AI Council **skips commenting on pull requests from forks** (`comment_on_forks: false`). This is because `GITHUB_TOKEN` on fork PRs is read-only and cannot post reviews.

### Known Limitations

- AI Council does not scan for secrets in the code it reviews; it is a code review tool, not a secrets scanner
- LLM providers may see code diffs as part of the review process; users should review their provider's data handling policies
