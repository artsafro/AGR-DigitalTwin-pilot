"""new-case: AGR Tools 0.8 (#908) names, 3ds Max side. Stub of branch 0; owned by branch C (improve/issue-908-names).

runtime.edits_080 calls `<function>(ctx, mode, nodes, preview)` for `qa_names_fix` (qa.names_fix), `ucx_rename` (ucx.rename);
while the function is absent the dispatcher reports `status: not_implemented`.
ctx: agr (runtime globals), core (names_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Import pymxs inside functions so this file loads under plain pytest.
"""
