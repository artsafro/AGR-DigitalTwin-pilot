# Skolkovo L4 — v012 live Revit host audit

**Incomplete production; passed=false. No accepted geometry, export or PR.**

## Exact next action needed

Please open the copied sibling
`C:/x/l4-skolkovo/01_source/02_pravki_2026-09-15/rvt/СК_ИЦ_ЦОД02_П_АР_Ф.rvt`
in live Revit with MCP, without saving/reloading/changing the current document.
The host's link to that sibling is unloaded (id5921640). The worker will only inspect
it; no save/export/edit/transaction, and FBX remains authority. This is a reference
access request, not a new Gate1, tolerance or geometry-authority question.

## Actual live evidence

Route: locked `C:/Users/artsafro/hermes_kanban/scripts/revit_exec.py` only.
Artem's permission19:58/earlier18:20 applies. Health: addin0.8.40,
mutationMode=direct. Only explicit inspection commands were used; the wrapper's
read-only list also contains view isolation and PDF export, which were NOT used.

Revit2025.2 build25.2.0.38; active document was the exact copied
`СК_ИЦ_ЦОД02_П_АР.rvt`, workshared, METRIC display units, isModified=true before
inspection. No conversion of native coordinates or geometry replacement occurred.
The active view was `{3D - artsafro}`; no view-changing command was issued.
Two persisted later document snapshots are identical. An unchanged isModified
boolean is not a proof of unchanged document contents; it was already true.

Five FBX-label candidate IDs6631253/6640426/6640949/6641475/6677027 each return
HTTP404/not_found in this host. They were never established as native ElementIds;
this does not establish a discrepancy with authoritative FBX. No geometry call
was made against an absent element or an unrelated substitute.

All seven RVT links are unloaded, including П_АР_Ф.rvt and П_АР_Фасад.rvt.
Narrow family inventories: GenericModel26, StructuralFraming19,
SpecialityEquipment8, ElectricalEquipment0, ElectricalFixtures0. These inventories
did not identify target mast/KNS families. Five targeted Family-regex queries also
return count0, returned0, truncated=false, but the English parameter name was not
independently validated in this localized model. These are NOT an exhaustive
absence proof or proof that the sibling contains the target. The sibling is the
next reference candidate explicitly allowed by the original card.

Two broad calls exceeded the wrapper's20000-character print limit and produced
JSONDecodeError (positions19999/19998). Narrow category calls succeeded instead.
The wrapper, token, config and addin were not modified; no raw HTTP bypass.
The broad truncated responses were not used as evidence of complete inventories.

Raw19 persisted responses, errors, limitations and checks are committed in
`evidence-v012/live-reference-audit.json`. Seven evidence consistency checks pass:
explicit read-only commands, no dry-run mutation, five404s, unloaded links,
identical persisted document snapshots, five bounded empty queries, errors not pass.
These are audit checks, not kernel invariants or architectural acceptance.

## Verification and timing

`env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider tests/test_task_to_model.py --basetemp=C:/x/t_b205c8e1/pt-v012`
returned **136 passed in64.34s**, exit0. No production/shared code was changed;
there is no code-fix RED/GREEN claim in this audit-only increment. Historical
v011776 tests and failed geometry remain historical, not newly re-executed results.
Full suite reserved for the complete first-review head via suite_slot.py.
CI: not run (billing lock).

Native reference timing can be recovered from the raw-response file timestamps
in ignored `tmp/skolkovo-v012/`; no invented full-stage duration is added. Existing
measured L5 timings remain in v011. This increment does not complete mast repair.

## Continue after sibling is open

1. Confirm identity/version/units; use read-only family/type/instance inspection.
2. Match native families and placements to FBX, without treating label IDs as proof.
3. If native topology access is supported, inspect side/cap domains; aggregate
   geometry metrics alone cannot reconstruct rings. Do not invent richer tooling.
4. Resume source-bound profile engineering only with usable new reference evidence.
   All prior rejected candidates remain rejected. No threshold weakening.
5. Complete KNS10k,49parts/conditional joints, measured master, versioned
   export/readback/comparison, board-user visual gate, final SINTEZ, suite/receipts/PR.

Canonical Gate1 SHA fca5b23b4e4939ad44f01abde68d8b510b0daad18c5e7bf3072a22e05fcd0d2a,
49parts/147000 allocation/291 conditional joints and authorized primary<=2mm
remain settled; see RESUME-v011.md. Job checklist and canonical proposal were not
edited. No new library/module, binary, LFS or DCC subprocess. Revit stays open
under the user's ownership; the worker neither started nor closed it.
