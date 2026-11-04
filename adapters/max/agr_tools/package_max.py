"""new-case: AGR Tools 0.8 (#908) package, 3ds Max side. Stub of branch 0; owned by branch D (improve/issue-908-package).

runtime.edits_080 calls `<function>(ctx, mode, nodes, preview)` for `qa_package` (qa.package), `export_zip` (export.zip), `export_ground_fbx` (export.ground_fbx), `export_geojson_write` (export.geojson_write);
while the function is absent the dispatcher reports `status: not_implemented`.
ctx: agr (runtime globals), core (package_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Import pymxs inside functions so this file loads under plain pytest.
"""
