"""new-case: AGR Tools 1.0 (#1024) windows by opening markers, 3ds Max side. Stub of branch 0; owned by branch J (improve/issue-1024-windows).

runtime.edits_100 calls `<function>(ctx, mode, nodes, preview)` for `win_place` (win.place);
while the function is absent the dispatcher reports `status: not_implemented` (issue #1024).
ctx: agr (runtime globals), core (winplace_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, user props, one undo record).
Import pymxs inside functions so this file loads under plain pytest.
"""
