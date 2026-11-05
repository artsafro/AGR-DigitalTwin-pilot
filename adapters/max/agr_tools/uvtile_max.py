"""new-case: AGR Tools 0.9 (#979) UV tiles (MatID -> UDIM, UDIM tiles and slots), 3ds Max side. Stub of branch 0; owned by branch B (improve/issue-979-tex-udim-atlas).

runtime.edits_090 calls `<function>(ctx, mode, nodes, preview)` for `udim_matid_unwrap` (udim.matid_unwrap), `udim_slots` (udim.slots);
while the function is absent the dispatcher reports `status: not_implemented` (issue #979).
ctx: agr (runtime globals), core (uvtile_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Import pymxs inside functions so this file loads under plain pytest.
"""
