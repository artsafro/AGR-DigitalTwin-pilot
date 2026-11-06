"""new-case: AGR Tools 1.0 (#1024) source class A/B/C / small parts of zavod sources, 3ds Max side. Stub of branch 0; owned by branch F (improve/issue-1024-passport).

runtime.edits_100 calls `<function>(ctx, mode, nodes, preview)` for `scene_source_class` (scene.source_class), `scene_small_parts` (scene.small_parts);
while the function is absent the dispatcher reports `status: not_implemented` (issue #1024).
ctx: agr (runtime globals), core (scene10_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, user props, one undo record).
Import pymxs inside functions so this file loads under plain pytest.
"""
