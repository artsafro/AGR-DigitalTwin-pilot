---
name: Task
about: A code, harness or documentation task an agent can take - Requirement, Specification, Context
title: ""
labels: needs-triage
---

<!--
Triage applies `ready-for-agent` only when `py -3 tools/check_ready_gate.py --issue <N>` passes:
every field below holds text and Acceptance has at least one checkbox item. "None" is a valid answer.
An agent's first step is to restate Specification and Context in its plan; it stops on an empty field
(docs/agents/WORKFLOW.md, "Recitation"). Comments like this one are removed before the check.
-->

## Requirement

<!-- The user's wording, verbatim (quote it), who asked and when; the profile (NPM-OKS, VPM-OKS, ...)
when the task touches a model. Do not paraphrase here. -->

## Specification

### Acceptance

<!-- Checkable items, one per line, each one a reviewer can verify from the PR. -->

- [ ] 

### Inputs and versions

<!-- Files, commits, sources, tool and model versions the work starts from; "Blocked by: #n". "None" if none. -->

### Out of scope

<!-- What this task does not do, so the agent does not drift into it. "None" if nothing. -->

### Evidence the PR must bring

<!-- Commands with their numbers, files read back, renders, gate outputs the reviewer checks. -->

## Context

<!-- Files and rules to read first: docs/domain/<file>, patterns, decisions [D<n>], cases, the parent spec. -->
