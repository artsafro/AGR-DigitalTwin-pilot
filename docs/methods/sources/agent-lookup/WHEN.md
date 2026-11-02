# When to use which lookup method

Decision for this pilot: **keep grep/read as default; graphify, context7 and xerj are not adopted**.
This experiment does not authorize persistent worker setup.

## Neither — current repo rules and job facts

Use **neither additional retrieval backend** for routine pilot lookup. In
[RESULTS — Overall comparison](RESULTS.md#overall-comparison), A scored **20/20 (100%)** with
**12,666.5 median tokens / 7.8265 s**. B and C also scored 20/20 but used **58.90%** and **47.12%**
more median tokens. D scored **19 correct + 1 partly (95%)** and used **225.76% more** tokens.
None meets the frozen **>=10% accuracy gain OR >=30% median-token reduction** rule.

## Graphify — only a separately justified code-graph experiment

Use graphify **when code relationships/path traversal are the actual task and a matched new benchmark
shows the required gain**; do not enable it by default from this result. **Not adopted here**:
B's **20/20**, **20,127.0 median tokens / 11.0615 s** are no accuracy gain and **58.90% more tokens**
than A ([Overall comparison](RESULTS.md#overall-comparison)). Its **17,839 nodes / 48,230 edges**
exclude **463 docs / 1 paper / 10 images** ([Local index/setup coverage](RESULTS.md#local-indexsetup-coverage)).
AST-only results cannot justify prose-decision lookup or disprove a future local semantic-doc approach.

## Context7 — explicit public-API documentation lookup, not a default

Use context7 **when a person explicitly needs current public documentation unavailable in the repo**,
accepting retrieval overhead; that is an ad-hoc source choice, not an efficiency win or profile setup.
**Not adopted here**: A and C each scored **6/6 API answers**, at **12,666.5 vs 18,214.5 median tokens**
([Category comparison](RESULTS.md#category-comparison)). Overall C used **47.12% more** median tokens,
not the required **30% less** ([Overall comparison](RESULTS.md#overall-comparison)). Its **8 calls across
4/6 API questions** do not prove full library coverage ([Limits](RESULTS.md#limits-and-excluded-attempt)).
Verify library/version IDs; current docs must not silently replace Blender 5.0 documentation.

## Xerj — a local code-and-doc corpus, only after task-specific validation

Use xerj **when local code-and-document search is needed and a matched benchmark demonstrates a gain**,
not as a default based on vendor claims. **Not adopted here**: D scored **19/20 fully correct (95%)**,
**41,262.0 median tokens / 11.0370 s**, **225.76% more tokens** than A
([Overall comparison](RESULTS.md#overall-comparison)). Its **48,415 records / 99 datasets** include
local documents, unlike AST-only B ([Local index/setup coverage](RESULTS.md#local-indexsetup-coverage)).
That broader coverage did not yield a gain on these 20 questions. D Q19 omitted `selectedOnly=True`;
its incomplete export call must not be treated as production-ready ([Error analysis](RESULTS.md#error-analysis)).
The vendor's 2.7x output-token / 94% first-file claims are different metrics; our all-token answer
benchmark does not directly confirm or refute those percentages ([Limits](RESULTS.md#limits-and-excluded-attempt)).

## Neither — private-source upload or unproven generalization

Use **neither hosted retrieval nor semantic upload** for private drawings/source without permission.
All **14 repo/job questions per variant** stayed local, while hosted C calls were restricted to public
API queries. B excluded **463 docs / 1 paper / 10 images**; D reported **2 named junk files** rather
than hiding drops ([Local index/setup coverage](RESULTS.md#local-indexsetup-coverage),
[Limits](RESULTS.md#limits-and-excluded-attempt)). These **80 single-trial rows**, with D added as a
later block, do not establish behavior for arbitrary APIs, PDF collections, AC07 or D186. Do not turn
baseline's ceiling-limited 20/20 into a broad superiority claim.
