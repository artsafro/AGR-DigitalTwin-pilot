"""new-case: AGR Tools 1.0 (#1024) NPM -> VPM, 3ds Max side. Stub of branch 0; owned by branch Q (improve/issue-1024-npm-to-vpm).

runtime.edits_100 calls `<function>(ctx, mode, nodes, preview)` for `npm_to_vpm` (npm.to_vpm);
while the function is absent the dispatcher reports `status: not_implemented` (issue #1024).
ctx: agr (runtime globals), core (npm2vpm_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, user props, one undo record).
Import pymxs inside functions so this file loads under plain pytest.
"""
