---
name: example-skill
description: Demonstrates correct SKILL.md structure for testing the skills loader and registry.
metadata:
  author: ai-council
  version: "1.0"
---
# Example Skill

This skill provides guidance for reviewing example patterns in the codebase.

## When to Apply

Apply this skill when reviewing code that involves example or demo patterns,
sample data generation, or test fixture creation.

## Guidelines

- Ensure sample data is clearly labeled as non-production.
- Avoid hardcoded values that look like real credentials.
- Prefer factory functions over inline literals for complex objects.
