"""new-case: AGR Tools 0.9 (#979) Flora and GroundEl atlases, 3ds Max side. Stub of branch 0; owned by branch B (improve/issue-979-tex-udim-atlas).

runtime.edits_090 calls `<function>(ctx, mode, nodes, preview)` for `atlas_flora` (atlas.flora), `atlas_groundel` (atlas.groundel);
the core is atlas_core.py (shared with atlas.npm 0.2; in 0.9 edited only by B), runtime.GLUE_090 maps it to this glue.
While the function is absent the dispatcher reports `status: not_implemented` (issue #979).
ctx: agr (runtime globals), core (atlas_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Import pymxs inside functions so this file loads under plain pytest. No C# at runtime (plan row atlas.flora).
"""
