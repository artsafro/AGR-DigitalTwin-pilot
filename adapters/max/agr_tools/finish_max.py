"""new-case: AGR Tools 0.9 (#979) finish map by legend, 3ds Max side. Stub of branch 0; owned by branch B (improve/issue-979-tex-udim-atlas).

runtime.edits_090 calls `<function>(ctx, mode, nodes, preview)` for `tex_finish_map` (tex.finish_map);
while the function is absent the dispatcher reports `status: not_implemented` (issue #979).
ctx: agr (runtime globals), core (finish_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Import pymxs inside functions so this file loads under plain pytest.
"""
