"""new-case: AGR Tools 0.9 (#979) batch export, 3ds Max side. Stub of branch 0; owned by branch D (improve/issue-979-export-scene-light).

runtime.edits_090 calls `<function>(ctx, mode, nodes, preview)` for `export_batch` (export.batch);
while the function is absent the dispatcher reports `status: not_implemented` (issue #979).
ctx: agr (runtime globals), core (batch_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Import pymxs inside functions so this file loads under plain pytest.
"""
