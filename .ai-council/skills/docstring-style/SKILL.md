---
name: docstring-style
description: >
  Use when reviewing changes to public Python APIs, modules, or documentation
  files. Covers Google-style docstring conventions, required sections for public
  APIs, common stale-doc patterns, and changelog discipline. Apply when *.py
  files with new/modified public functions or classes appear in the diff, or
  when README.md / CHANGELOG.md / docs/ files change.
---

# Docstring Style & Documentation Quality

Guidance for catching documentation drift and enforcing Google-style docstrings
on public Python APIs.

---

## 1. Required sections for public functions

Every new or modified **public** function (no leading underscore) must have a
docstring with at minimum:

- **One-line summary** — imperative mood, ≤ 79 chars, no period.
- **Args** section — one entry per parameter (skip `self`/`cls`).
- **Returns** section — unless the return type is `None`.
- **Raises** section — whenever the function explicitly raises or re-raises.

```python
# GOOD
def load_user(user_id: int) -> User:
    """Load a user by primary key.

    Args:
        user_id: Database primary key.

    Returns:
        User instance.

    Raises:
        UserNotFoundError: If no user with the given ID exists.
    """
```

---

## 2. Signature vs docstring drift

**What to check:** When a function signature changes (new parameter, changed default, changed return type), verify the docstring Args / Returns sections are updated in the same commit.

**Common stale-doc patterns to flag:**
- Docstring still mentions an old parameter name (renamed in code but not docs).
- Default value described in docstring differs from the actual default in the signature.
- Return type annotation says `list[str]` but docstring says "Returns a dict".

---

## 3. New public classes

New public classes (no leading underscore) require:
- Class-level docstring describing **purpose and usage**, not implementation.
- `__init__` docstring listing constructor parameters unless the class docstring covers them.
- Avoid restating the class name in the docstring ("This class …").

---

## 4. Module-level docstrings

New modules must have a module-level docstring. One or two sentences covering:
- What the module provides.
- Key public names exported.

---

## 5. Changelog gaps

**What to flag:** Any PR that adds a new public API, changes a public function signature, or removes/deprecates functionality without a corresponding entry in `CHANGELOG.md` (or `HISTORY.md` / `CHANGES.md`).

Changelog entries must include the type of change (Added / Changed / Fixed / Deprecated / Removed) and be placed in the `[Unreleased]` section.

---

## 6. Broken code examples

**What to check:** `>>> ` doctest snippets or fenced code blocks in docstrings or README that reference APIs that were renamed or removed in the same PR.

Flag as a medium-severity documentation finding when an example imports a symbol that no longer exists or calls a function with removed arguments.
