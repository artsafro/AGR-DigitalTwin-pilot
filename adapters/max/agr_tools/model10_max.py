"""new-case: AGR Tools 1.0 (#1024) Quick Attach by material (Keep split by default) / move apart: To = final gap, 3ds Max side. Stub of branch 0; owned by branch G (improve/issue-1024-body).

runtime.edits_100 calls `<function>(ctx, mode, nodes, preview)` for `model_attach_by_material` (model.attach_by_material), `model_move_apart` (model.move_apart);
while the function is absent the dispatcher reports `status: not_implemented` (issue #1024).
ctx: agr (runtime globals), core (model10_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, user props, one undo record).
Import pymxs inside functions so this file loads under plain pytest.
"""
