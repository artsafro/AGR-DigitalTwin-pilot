"""new-case: AGR Tools 1.0 (#1024) facade strip atlas, 3ds Max side. Stub of branch 0; owned by branch P (improve/issue-1024-npm).

runtime.edits_100 calls `<function>(ctx, mode, nodes, preview)` for `atlas_facade_strip` (atlas.facade_strip);
while the function is absent the dispatcher reports `status: not_implemented` (issue #1024).
ctx: agr (runtime globals), core (facadeatlas_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, user props, one undo record).
Import pymxs inside functions so this file loads under plain pytest.
"""
