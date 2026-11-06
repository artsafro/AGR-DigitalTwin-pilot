"""new-case: AGR Tools 1.0 (#1024) UCX stairs, 3ds Max side. Stub of branch 0; owned by branch T (improve/issue-1024-deliver-small).

runtime.edits_100 calls `<function>(ctx, mode, nodes, preview)` for `ucx_stairs` (ucx.stairs);
while the function is absent the dispatcher reports `status: not_implemented` (issue #1024).
ctx: agr (runtime globals), core (ucxstairs_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, user props, one undo record).
Import pymxs inside functions so this file loads under plain pytest.
"""
