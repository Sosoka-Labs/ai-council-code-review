# Dogfood Test Files

This directory contains deliberately bad code used to test the AI Council Code Review pipeline.

These files are **not** part of the production codebase. They exist solely so we can open pull requests that modify them and verify that the AI agents correctly identify security issues, quality problems, and architectural concerns.

**Do not use this code in production.**

## Files

- `test_security_issues.py` — Contains fake hardcoded secrets, SQL injection, unsafe deserialization, and command injection vulnerabilities. The AWS key `AKIAIOSFODNN7EXAMPLE` is [AWS's official example access key](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html) and is not a real credential.
