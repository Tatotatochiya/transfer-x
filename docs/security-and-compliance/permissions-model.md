---
title: "Permissions Model — Risk Posture"
last_updated: 2026-07-03
status: Draft
owner: "TODO — assign a Security Owner"
---

# Permissions Model — Risk Posture

## Purpose

Describes what is and isn't protected in TransferX today from a confidentiality/access standpoint — the risk-facing view. For how authentication and authorization are technically implemented, see [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md); this document doesn't repeat that mechanism, only assesses it.

## Scope

In scope: confidentiality boundaries between parties (e.g. clubs, agents, players), and known gaps.
Out of scope: implementation mechanism (see [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md)).

## Table of Contents

- [Confidentiality boundaries](#confidentiality-boundaries)
- [Known gaps](#known-gaps)
- [Related documents](#related-documents)

## Confidentiality boundaries

> **TODO:** Document, per entity, who should and shouldn't be able to see it — e.g. a selling club's reserve price should be visible only to that club; a deal's medical check should be visible only to its participants. State the intended boundary here; verify it holds in the code as part of any security review rather than assuming this document is currently accurate.

## Known gaps

> **TODO:** Track known permission gaps here as they're identified (e.g. via security review or audit), each with a link to its corresponding backlog ticket. Do not let this list silently go stale — if a ticket closes, remove or update the entry.

## Related documents

- [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md) — the technical mechanism
- [`data-privacy-and-legal.md`](./data-privacy-and-legal.md) — the legal dimension of data exposure
- [`../product/personas.md`](../product/personas.md) — the parties whose confidentiality this document protects
