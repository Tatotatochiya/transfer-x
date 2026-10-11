---
title: "Data Privacy & Legal"
last_updated: 2026-10-11
status: Draft
owner: "TODO — assign a Security/Legal Owner"
---

# Data Privacy & Legal

## Purpose

Covers data privacy handling and legal-adjacent technical surface — terms of service, consent tracking, and data subject rights.

## Scope

In scope: privacy policy/ToS status, consent tracking, data retention/erasure.
Out of scope: confidentiality *between platform users* (see [`permissions-model.md`](./permissions-model.md)), business/commercial legal structure (see [`../business/README.md`](../business/README.md)).

## Table of Contents

- [Current state](#current-state)
- [Data subject rights](#data-subject-rights)
- [Related documents](#related-documents)

## Current state

There are no Terms of Service, privacy policy or cookie consent pages in the app (checked 2026-10-11).

> **TODO:** Write the Terms of Service and privacy policy, and decide whether a cookie notice is needed (the app stores sign-in tokens and per-device settings in the browser; it sets no tracking cookies), before a real club signs up.

## Data subject rights

Built on 2026-10-04 (`app/auth/privacy.py`, migration `0096`), under Account settings → Your data.

**Export.** The person's own data:
- account, profile and preferences;
- signed-in devices and notifications;
- their audit events and what they wrote.

Club data (players, deals, finances) belongs to the club and isn't included.

**Closing an account.**
- **Erased:** personal details. The email is replaced and the names cleared, and sessions, push subscriptions and device details are deleted. The account is anonymised and marked closed.
- **Kept:** the records a dispute or audit relies on (audit events, deal comments, negotiation messages, terms versions). They stay attributed to a closed account with no name or email.
- **Refused for:**
  - a club owner, since the club has to be handed over or closed by TransferX;
  - an agent who still holds mandates;
  - TransferX staff, who are closed by another admin.

## Monitoring data

Admin monitoring ([`operations/monitoring-and-observability.md`](../operations/monitoring-and-observability.md)) keeps data that can include personal data from log messages and request context (user ids, request paths). Platform admins only.

| Store | Holds | Kept |
|---|---|---|
| `job_run_logs` | Log lines written during a job run | 30 days |
| `error_events` | Error messages, tracebacks, request method, path, status, request id and user id. Never bodies, headers or query strings | 30 days (newest 20 per issue) |
| `error_issues` | Grouped error titles and counts | 90 days after last seen |
| `job_runs` | Job outcomes and counts | 90 days |
| `request_minutes` | Requests per endpoint per minute: counts and latency, no user data | 14 days |

Slack receives titles and counts only, never tracebacks or event context.

## Related documents

- [`permissions-model.md`](./permissions-model.md) — confidentiality between platform users, as distinct from this document's legal/privacy scope
- [`../business/README.md`](../business/README.md) — business context this legal surface serves
