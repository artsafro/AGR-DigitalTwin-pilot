"""new-case: AGR Tools 0.8 (#908) tex, 3ds Max side. Stub of branch 0; owned by branch B (improve/issue-908-tex).

runtime.edits_080 calls `<function>(ctx, mode, nodes, preview)` for `scene_missing_maps` (scene.missing_maps), `tex_format_fix` (tex.format_fix), `tex_placeholders` (tex.placeholders);
while the function is absent the dispatcher reports `status: not_implemented`.
ctx: agr (runtime globals), core (tex_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Import pymxs inside functions so this file loads under plain pytest.
"""
