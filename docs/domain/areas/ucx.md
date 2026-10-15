# UCX — cross-cutting collision requirement index

Profiles: **VPM only**; `n/a` in NPM means no UCX requirement, not a failed check.
In scope: OKS Main and Ground surface collision, including target exclusions, hulls,
clearances, names and budget. Out of scope: render geometry, textures, lighting design,
Unreal integration and customer-specific additions to NPM.

Readiness today: OKS **L2-partial**, Ground UCX **L0**, per the
[roadmap §4 and §7.6](../../research/capability-roadmap.md#4-coverage-matrix-upstream-main-ea7ecce).
This sheet adds the L1 requirement index, not a skill, pattern, benchmark or L3 acceptance.
Rows are navigation/check keys, not replacement rule text. `none` means no automatic
check for the complete row today; a manual gate does not count as L2 coverage.
Job-local checks below are static code evidence, not newly executed DCC checks or
shared delivery validation. [Image verification and PR acceptance evidence](ucx-evidence/review.md).

| Requirement | reg page | NPM | VPM | How it is checked | L2 coverage | Detail in |
|---|---|---|---|---|---|---|
| R01 OKS target | reg p.36 §13.2 | n/a | Main: every OKS; existing OKS inside site if present; preserve arches, courtyards and major projections | V016 manual overlay and walkthrough; check target inventory | none | [Collision targets](../geometry.md#collision--ucx-vpm-only-npm-has-none-unless-customer-spec) |
| R02 Ground target | reg p.36 §13.2 | n/a | Ground surface, especially perimeter | Compare collision to approved site surface; Ground has no built case | none | [Collision targets](../geometry.md#collision--ucx-vpm-only-npm-has-none-unless-customer-spec) |
| R03 Excluded targets | reg p.36 §13.2-13.3 | n/a | MAF, lighting, vegetation: none; lighting FBX exempt | Inspect target inventory and lighting FBX separately | none | [Targets](../geometry.md#collision--ucx-vpm-only-npm-has-none-unless-customer-spec), [lighting](../npm-vpm.md#vpm-lighting-fbx-architectural-light-design) |
| R04 Thin-element exception | reg p.36 §13.2 | n/a | Canopies, fences, railings <= 5 cm thick: no UCX | Measure source thickness before applying exception | none | [Collision exceptions](../geometry.md#collision--ucx-vpm-only-npm-has-none-unless-customer-spec) |
| R05 Per-file collision | reg p.36 §13.3 | n/a | Own UCX in each non-lighting geometry FBX | Read back each FBX; V010 has no dedicated missing-UCX detection | none | [V010 implementation limits](../validation.md#implementation-status-inventory-static-audit) |
| R06 Hull geometry | reg p.36 §13.1 | n/a | Convex closed Mesh pieces without holes | KPP1 convex_closed checks convexity and edge closure locally; general V010 shape remains not_run | KPP1 vpm_ucx.py:convex_closed (job-local only) | [Rule](../geometry.md#collision--ucx-vpm-only-npm-has-none-unless-customer-spec), [local check](../../../jobs/KPP1/scripts/vpm_ucx.py) |
| R07 Material slots | reg p.36 §13.1 | n/a | No material slots on UCX | Inspect exported mesh slots; construction without slots is not an independent check | none | [Collision hull contract](../geometry.md#collision--ucx-vpm-only-npm-has-none-unless-customer-spec) |
| R08 Collision names | reg p.34 §4.2 | n/a | UCX_SM_{Address}_{Main\|Ground}_{001..999} | Inspect internal names and indices; V012 does not check internal mesh names | none | [VPM names](../geometry.md#naming---vpm-reg-p33-36), [V012 limits](../validation.md#implementation-status-inventory-static-audit) |
| R09 Mutual intersections | reg p.36 §13.4 | n/a | Pieces must not intersect | KPP1 SAT intersect checks hull pairs; PSU275 checks box pairs; no general V010 geometry check | KPP1 vpm_ucx.py:intersect; PSU275 vpm_ucx.py:clash (job-local only) | [Rule](../geometry.md#collision--ucx-vpm-only-npm-has-none-unless-customer-spec), [KPP1](../../../jobs/KPP1/scripts/vpm_ucx.py), [PSU275](../../../jobs/PSU275/scripts/vpm_ucx.py) |
| R10 Recommended gap | reg p.36 §13.4 | n/a | 0.02-1 cm recommendation, not a blocking minimum | Measure nearest separation separately from overlap; retain recommendation status (C15) | none | [C15](../conflicts.md#a-inside-the-regulation), [ADR-0002 §3](../../agr/decisions/ADR-0002-source-discrepancies.md#3-зазор-ucx--рекомендация) |
| R11 Ground deviation | reg p.36 §13.5 | n/a | <= 10 cm, especially perimeter | V016 manual surface overlay and maximum deviation by target | none | [Shape tolerances](../geometry.md#collision--ucx-vpm-only-npm-has-none-unless-customer-spec) |
| R12 Pedestrian-zone deviation | reg p.36 §13.5 | n/a | <= 30 cm at pedestrian-reachable lower OKS floors, stylobates and bridge/platform approaches | V016 manual height-zone overlay and walkthrough | none | [Shape tolerances](../geometry.md#collision--ucx-vpm-only-npm-has-none-unless-customer-spec), [V016](../validation.md#implementation-status-inventory-static-audit) |
| R13 Other OKS deviation | reg p.36 §13.5 | n/a | <= 1 m elsewhere on OKS | V016 manual overlay outside pedestrian zones | none | [Shape tolerances](../geometry.md#collision--ucx-vpm-only-npm-has-none-unless-customer-spec) |
| R14 Entrance stairs | reg p.36 §13.6 | n/a | Truncated-pyramid collision shape | Inspect stairs against source; job simplifications do not waive this rule | none | [Stair collision](../geometry.md#collision--ucx-vpm-only-npm-has-none-unless-customer-spec) |
| R15 Triangle budget | reg p.36-37 §13.7-13.8; [D012] | n/a | n < 50,000: 15,000; otherwise min(ceil(n * 0.05), 100,000); n excludes UCX | V010 with scene readback, UCX present; C3, decided by the user, overrides historical ADR open status | V010; tests/qa/test_scene.py::test_ucx_budget_is_checker_formula_conflict_3 | [C3 / D012](../conflicts.md#a-inside-the-regulation), [ADR-0002 §2 (historical)](../../agr/decisions/ADR-0002-source-discrepancies.md#2-лимит-ucx--открыто), [implementation](../../../src/twinqa/scene.py) |
| R16 Applied transforms | reg p.29 §3.18 | n/a | Apply/reset transforms including UCX | V004 scene readback checks rotations and scale of all meshes | V004: scene_findings | [Transforms](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted), [implementation limits](../validation.md#implementation-status-inventory-static-audit) |
| R17 UCX pivot exemption | reg p.33 §9.4; [D018] | n/a | Collision pivot placement is free; exempt from shared-pivot check | V013 excludes UCX when checking shared origins | V013; tests/qa/test_scene.py::test_origin_at_zero_and_ucx_exempt_from_shared_pivot | [Pivot decision](../conflicts.md#b-regulation-vs-local-yaml--docs), [test](../../../tests/qa/test_scene.py) |
| R18 Export triangulation | reg p.29 §3.17 | n/a | Triangulated collision meshes in exported FBX | V003 scene readback includes UCX polygon degrees | V003: scene_findings | [Export geometry](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted), [implementation](../../../src/twinqa/scene.py) |

## Current limitations

[Pipeline stage #10](../../pipeline.md) says UCX is “missing”, while
[KPP1](../../../jobs/KPP1/scripts/vpm_ucx.py) and
[PSU275](../../../jobs/PSU275/scripts/vpm_ucx.py) build it. This is job-local capability,
not a shared tool; pipeline.md is deliberately unchanged here. PSU275 explicitly omits
stair collision and fills parapet wells: script existence is not blanket compliance.
V010 checks budget only when UCX is present; its shape/coverage placeholder is not an
implemented validator. No benchmark or Ground UCX case exists in the roadmap snapshot.
C3 is decided by the user [D012]; C15 retains the gap as a recommendation. No new
conflict is introduced or open conflict decided by this sheet.

## L2 gaps

These are follow-up L2 ticket inputs, not newly filed issues. Job-local partial coverage
in R06/R09 still needs shared readback and an etalon benchmark (T-UCX-2 / T-UCX-3).

- R01: Target completeness, arches/courtyards and passage preservation.
- R02: Ground surface target generation and coverage; real case T-UCX-4 waits for surface review.
- R03: Exclusion audit for MAF, vegetation and lighting.
- R04: Thickness-based exception classification.
- R05: Required collision presence per geometry FBX.
- R07: Exported UCX material-slot absence.
- R08: Internal collision name mask and index range.
- R10: Measured advisory gap report, separate from mandatory intersection checks.
- R11: Ground maximum deviation and perimeter coverage.
- R12: Pedestrian-zone classification and maximum deviation.
- R13: Remaining OKS maximum deviation.
- R14: Entrance-stair collision shape.
