"""new-case: AGR Tools 0.9 (#979) facade sheet comparison, 3ds Max side. Stub of branch 0; owned by branch C (improve/issue-979-qa).

runtime.edits_090 calls `<function>(ctx, mode, nodes, preview)` for `qa_facade_compare` (qa.facade_compare);
while the function is absent the dispatcher reports `status: not_implemented` (issue #979).
ctx: agr (runtime globals), core (facade_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Import pymxs inside functions so this file loads under plain pytest.
"""
