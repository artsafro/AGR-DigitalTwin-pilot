"""new-case: AGR Tools 1.0 (#1024) facade strip atlas, 3ds Max side; owned by branch P (improve/issue-1024-npm).

runtime.edits_100 calls `atlas_facade_strip(ctx, mode, nodes, preview)` for `atlas.facade_strip` (copy + file, 1.0.23).
ctx: agr (runtime globals), core (facadeatlas_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost). Import pymxs inside functions so this file loads under plain pytest.

The glue is the one of npm.build (npm_max.run) with one copy per selected object (no attach): preview plans the
strips (facadeatlas_core.plan: D156 run-strip, strips folded by whole periods, unique IDs rigid); apply renders the
atlas from the full-resolution maps, writes it and `strip_table.json` into a NEW folder, then in ONE undo record makes
copies on layer `AGR_facade_strip`, writes channel 1 of each copy, binds one material with the atlas and reads back
texel, cells and the planned UV. Originals and maps are compared before/after; a failure removes copies and files.
"""
TOOL = 'atlas.facade_strip'
LAYER = 'AGR_facade_strip'


def atlas_facade_strip(ctx, mode, nodes, preview):
    nm = ctx.agr._load_core('npm_max.py', 'agr_tools_npm_max_glue')
    return nm.run(ctx, mode, nodes, preview, TOOL, LAYER, False, 'STRIP')
