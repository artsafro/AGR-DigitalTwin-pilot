# Steward note (#2038)

Every AUTOMATIC push to someone else's PR branch or to main — a rework push, a red-main fix, a merge of
main into a PR branch, a merge into main by an automatic lane (`docs/agents/MERGE_POLICY.yaml`, bucket
`auto`) — posts ONE PR comment in this shape right after the push. Without it a human cannot see what the
automation changed or undo it in one command.

```markdown
## Steward note — <rework | red-main fix | main merge | auto-merge> (<profile>, card <t_id>)

**What I changed:** <files or areas, one line each; "merge of origin/main <sha8> into <branch>, conflicts: none | <files>">
**Why:** <the review finding / failing test id / STOP_AUTOMERGE sha / policy rule id + consent>
**Head before -> after:** `<old sha8>` -> `<new sha8>`
**How to revert:** `git revert <sha>` (single commit) | `git revert -m 1 <merge sha>` (merge commit) | the exact commits: `<sha1> <sha2>`
```

Rules:
- One note per push; list every commit the push added (`git log --oneline <old>..<new>`).
- The revert line must be runnable as written; for a merge commit name the parent (`-m 1`).
- Policy merges cite the rule id and consent from the classifier output (`tools/merge_policy.py classify --pr N`).

## Line for the worker card footer (wired by the orchestrator in hermes_kanban, not in this repo)

> After every automatic fix push (rework, red-main fix, main merge) post a PR comment per
> docs/agents/STEWARD_NOTE.md: what I changed / why / how to revert (`git revert <sha>` or the exact commits).
