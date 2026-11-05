"""new-case: AGR Tools 0.9 (#979) QA 0.9 (address, normals, SINTEZ, procedural objects), 3ds Max side. Stub of branch 0; owned by branch C (improve/issue-979-qa).

runtime.edits_090 calls `<function>(ctx, mode, nodes, preview)` for `qa_address` (qa.address), `qa_normals` (qa.normals), `qa_sintez` (qa.sintez), `qa_procedural_objects` (qa.procedural_objects);
while the function is absent the dispatcher reports `status: not_implemented` (issue #979).
ctx: agr (runtime globals), core (qa9_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Import pymxs inside functions so this file loads under plain pytest.
"""
