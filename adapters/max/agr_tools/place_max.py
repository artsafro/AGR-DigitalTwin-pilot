"""new-case: AGR Tools 0.9 (#979) place (replace, schedule, drop to Ground, MAF checks, Flora repair), 3ds Max side. Stub of branch 0; owned by branch A (improve/issue-979-place).

runtime.edits_090 calls `<function>(ctx, mode, nodes, preview)` for `place_replace` (place.replace), `place_schedule` (place.schedule), `place_drop_to_ground` (place.drop_to_ground), `place_maf_checks` (place.maf_checks), `place_flora_repair` (place.flora_repair);
while the function is absent the dispatcher reports `status: not_implemented` (issue #979).
ctx: agr (runtime globals), core (place_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Import pymxs inside functions so this file loads under plain pytest.
"""
