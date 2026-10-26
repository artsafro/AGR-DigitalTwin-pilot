# When to use which lookup method

Decision for this pilot: **keep grep/read as the default; graphify and context7 are not adopted**.
This is an experiment result, not authorization to change worker profiles.

## Neither — current repo rules and job facts

Use **neither additional tool** for routine pilot rule/job lookup. In
[RESULTS — Overall comparison](RESULTS.md#overall-comparison), baseline A answered **20/20 (100%)**
with **12,666.5 median tokens / 7.8265 s**. B and C also reached **20/20**, but used
**20,127.0 (+58.90%)** and **18,635.5 (+47.12%)** median tokens. Neither reaches the
preregistered **>=10% relative accuracy gain OR >=30% token reduction**.

## Graphify — only a separately justified code-graph experiment

Use graphify **when a task genuinely needs code relationships / paths and a new matched benchmark
shows the required gain**; do not enable it by default on the strength of this test. **Not adopted here**:
B's **20/20**, **20,127.0 median tokens**, **11.0615 s** are no accuracy gain and **58.90% more tokens**
than A ([Overall comparison](RESULTS.md#overall-comparison)). Its local graph had
**17,839 nodes / 48,230 edges** but excluded **463 docs / 1 paper / 10 images**
([Token and tool accounting](RESULTS.md#token-and-tool-accounting)). This result cannot justify
using AST-only graphify to find prose decisions, nor disprove a future local semantic-doc approach.
That future approach would need its own privacy decision and benchmark; it is not part of this adoption.

## Context7 — explicit public-API documentation lookup, not a worker default

Use context7 **when a person explicitly needs current public library documentation unavailable in the
repo**, and accepts the extra retrieval cost; this is an ad-hoc source choice, not a measured efficiency
win or a persistent worker setup. **Not adopted here**: the six API questions were **6/6 correct** for
both A and C, with **12,666.5 vs 18,214.5 median tokens**
([Category comparison](RESULTS.md#category-comparison)). Across all 20 questions C used **47.12% more
median tokens**, not the required **30% less** ([Overall comparison](RESULTS.md#overall-comparison)).
Context7's current-documentation answers must not silently substitute another Blender version for 5.0;
the actual resolved library IDs and queries are retained in `results.jsonl`.

## Neither — unapproved private-source upload or unproven generalization

Use **neither hosted retrieval nor a semantic upload** for private drawings / source contents without
separate permission. The benchmark kept all **14 repo/job questions per variant** local; hosted
context7 calls were restricted to the **6 public API questions**, while local graphify skipped the
**463 docs / 1 paper / 10 images** listed in
[RESULTS — Limits](RESULTS.md#limits-and-excluded-attempt) and
[Token and tool accounting](RESULTS.md#token-and-tool-accounting). These **60 single-trial rows**
do not establish behavior for arbitrary APIs, PDF corpora, AC07 or D186, which are not represented in
the frozen main snapshot. Do not turn a ceiling-limited 20/20 into a broad superiority claim.
