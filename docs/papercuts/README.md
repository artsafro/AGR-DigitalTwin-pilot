# Papercuts

A papercut is a small snag an agent worked around and kept going: a doc line that sent it the wrong way, a
confusing name, a command that needed a retry or a flag nobody wrote down, a permission prompt that should not
exist, a check that was slow for no reason. Logged one line each, papercuts are the raw material for `/retro`
and `docs/backlog.md`; a single one is cheap to ignore, the same one five times is a task.

## How to log

- One file per branch: `docs/papercuts/<branch name with / replaced by ->.md`, created on the first papercut and
  committed with the branch. Separate files keep parallel branches free of merge conflicts.
- One line per papercut, appended, at the moment it happens:

  ```
  - 2026-11-10 <agent> <where: file, tool, command> — <what slowed you> -> <how you worked around it>
  ```

- Keep working after the line; fixing the snag is a separate task unless it blocks this one.
- Real blockers, user corrections and rejected results are not papercuts: they go to the user and to `/retro`.

## Who reads them

`/retro` (step 2) reads the papercut lines dated in its range, groups repeats and turns a repeated or costly one
into a deduplicated issue. Lines stay in place; this is date filtering only:
overlapping or identical ranges can select the same lines again.
Issue deduplication does not deduplicate incident counts.
