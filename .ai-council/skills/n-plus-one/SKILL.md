---
name: n-plus-one
description: >
  Use when reviewing code that touches ORM queries, database access patterns,
  loop-over-collection code, or request handlers in Django, SQLAlchemy, Tortoise,
  or similar ORMs. Covers N+1 detection, eager-loading strategies, and unbounded
  result sets. Apply when files in */models/*, */repositories/*, */dao/*, */queries/*,
  or */views/* appear in the diff.
---

# N+1 Query Detection

Guidance for identifying and fixing N+1 database query patterns in ORM code.

---

## 1. Recognising an N+1

**What to check:** Any loop that accesses a related object or calls `.query()` / `.filter()` / `.get()` / `.objects.all()` inside the loop body on a relationship that was NOT pre-fetched in the initial queryset.

**Django ORM example (N+1):**
```python
# BAD — one query per user to load their orders
users = User.objects.all()          # SELECT * FROM users
for user in users:
    orders = user.orders.all()       # SELECT * FROM orders WHERE user_id=<id>  (×N)
```

**Fix:**
```python
# GOOD — single JOIN
users = User.objects.prefetch_related("orders").all()
for user in users:
    orders = user.orders.all()       # uses cached result, zero extra queries
```

**Why it matters:** On a table with 1 000 rows the N+1 issues 1 001 queries. At 100 ms per query (network round-trip) that is 100 seconds per page load.

---

## 2. SQLAlchemy patterns

**What to check:** Use of `relationship()` attributes accessed inside a loop without `joinedload` or `selectinload` in the session query.

**BAD:**
```python
users = session.query(User).all()
for user in users:
    print(user.address.city)   # lazy-loads address N times
```

**FIX:**
```python
from sqlalchemy.orm import joinedload
users = session.query(User).options(joinedload(User.address)).all()
```

---

## 3. Unbounded result sets

**What to check:** Queries that load every row without `LIMIT` / `.limit()` or pagination — especially on tables expected to grow (users, orders, events, logs).

**What to flag:**
- `.objects.all()` or `.all()` on large tables without pagination in request handlers
- `SELECT * FROM table` without `LIMIT` in raw SQL
- Iterator patterns that materialise the full result into a list

**Fix patterns:** Django `Paginator`, SQLAlchemy `yield_per`, cursor-based pagination, `.limit(N).offset(M)`.

---

## 4. Aggregate queries as loop replacements

**What to check:** Loops that compute statistics by iterating model instances when a single aggregate query would suffice.

```python
# BAD — O(n) queries
total = sum(order.amount for order in Order.objects.filter(user=user))

# GOOD — one SQL aggregate
from django.db.models import Sum
total = Order.objects.filter(user=user).aggregate(Sum("amount"))["amount__sum"] or 0
```

---

## 5. Missing `select_related` for ForeignKey access

**What to check:** Accessing `obj.foreign_key.field` outside a loop (single-object case) without `select_related`, which still causes a lazy query per attribute access in Django.

**Fix:** `User.objects.select_related("profile").get(pk=pk)` pre-fetches with a JOIN.
