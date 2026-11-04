"""new-case: AGR Tools 0.8 (#908) geom, 3ds Max side. Stub of branch 0; owned by branch A (improve/issue-908-geom).

runtime.edits_080 calls `<function>(ctx, mode, nodes, preview)` for `model_triangulate` (model.triangulate), `ucx_triangulate` (ucx.triangulate), `export_pivot_place` (export.pivot_place);
while the function is absent the dispatcher reports `status: not_implemented`.
ctx: agr (runtime globals), core (geom_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Import pymxs inside functions so this file loads under plain pytest.
"""
