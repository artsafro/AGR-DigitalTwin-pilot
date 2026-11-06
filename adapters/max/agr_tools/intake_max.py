"""new-case: AGR Tools 1.0 (#1024) source intake: units, axes, origin, 3ds Max side. Stub of branch 0; owned by branch F (improve/issue-1024-passport).

runtime.edits_100 calls `<function>(ctx, mode, nodes, preview)` for `source_intake` (source.intake);
while the function is absent the dispatcher reports `status: not_implemented` (issue #1024).
ctx: agr (runtime globals), core (intake_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, user props, one undo record).
Import pymxs inside functions so this file loads under plain pytest.
"""
