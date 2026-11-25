# <JOB> — lessons (job-local)

Lessons learned on this job, for the next agent on it. They stay here: no `D<n>` promotion from this file
(the weekly harvest [D326] may propose one to Artem). Form [D411]: every lesson is one `## L<n> <title>` block
with three fields. The evidence is what proves the lesson — the contrast or before/after (an
`agr trainer ab` report, two readbacks, two numbers), not only the issue number.
`tools/qa/lessons_check.py --staged` (pre-commit, warn-only) warns on a new lesson without evidence.

```markdown
## L1 <short title>
- Situation: <what happened, where; the run or stage>
- Lesson: <the rule for the next agent on this job>
- Evidence: <contrast / before-after that proves it: report path, numbers, readbacks>
```

Scope of a harness edit drawn from a lesson: INVARIANT (entry, context, tools) or DOMAIN (OKS / Ground / MAF /
Flora); the two are probed in separate A/B runs (`docs/trainer/ETALONS.md`, "A/B probe").
