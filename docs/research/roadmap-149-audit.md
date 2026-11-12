# Capability roadmap #149: closure audit (#1260)

## Verdict and boundary

**Close #149 as a superseded planning umbrella after this report is merged, not as
"all capabilities complete".** The L1 sheet wave and first L2 checks landed; the
universal L2/L3 promise did not. Remaining production work belongs to current
AGR Tools, PDF intake, library and per-job issues, not a restart of the 2026-10-15 queue.
This report does not close #149 itself, create issues, approve a model or change a rule.
The merge and the owner's/triage's closure comment remain pending.

Audit baseline: pilot `main` **f1fbe9a49b2167f3840c6ceff36aea9b3837136e**,
2026-11-12. GitHub issue bodies/comments and PR merge metadata were read on that date.
Later edits to issues are not retroactive evidence for this snapshot. `CLOSED` is an
administrative state, not proof of completion; an open PR is not implementation on main.

Sources: [original roadmap](capability-roadmap.md) (PR #114),
[spec #149](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/149), calibration
PRs #138/#142/#143 and all **59 direct sub-issues** returned by GitHub. Tables cover
all **42 T-* candidates**, all **21 spec stories**, the board proposals, original
open questions and later direct children. Repeated §11 recommendations refer to the
same T-* rows; area/tree/coverage prose is reconciled in the area summary below.

Status vocabulary: **done** = the named bounded artifact exists on main;
**partly** = useful implementation/evidence exists but an original acceptance item is
missing; **not started** = the named artifact/run has no main evidence;
**obsolete** = a later named decision or owner instruction replaced that ask.
A done tool is not a passed delivery. Historical results below were read, not rerun.

Evidence pack: `G:/Мой диск/AGR-evidence/1260-roadmap-audit/v001/` contains the audit
CSV sheets, frozen issue/PR metadata, this report and `SHA256SUMS.txt`. No new model,
render or regulation calibration image was produced: existing calibration receipts
were inspected. Customer scenes/FBX were not opened, copied into git or modified.

## Area-level reconciliation of the old coverage matrix (§2–§5)

All eleven L1 **sheets** exist. That does not establish complete L1 procedures in
every area, let alone complete L2 benchmarks/evals or L3 acceptance. Ground textures
and Ground UCX remain targets of cross-cutting sheets, not extra duplicated sheets.

| Original area | Main evidence | What the old level no longer tells us |
|---|---|---|
| OKS BODY | [body sheet](../domain/areas/body.md), B01/B02/B02t, `docs/cases.md` | Accepted bounded cases remain; K01 is not 9/9 and general BODY procedure is not a dedicated skill. |
| Windows / doors | [windows sheet](../domain/areas/windows.md), `library/windows/standard.json`, AGR Tools window generation | Real library and ELV cases supersede "no library"; quarantine/unconfirmed types and no B05 prevent universal L2/L3. |
| Decor | [decor sheet](../domain/areas/decor.md), B03/K02 READMEs | Still no completed independent decor benchmark. OBJ03 failure is not an accepted case. |
| UV / atlas | [UV sheet](../domain/areas/uv-atlas.md), V008/V009, AGR Tools cores | Beyond the old archive-only checks, but the proposed Obr22 benchmark is absent. |
| Textures | [textures sheet](../domain/areas/textures.md), `library/materials/`, AC08 pilot | Libraries/maps/recipes exist; no generic accepted ERM/Normal area certificate. |
| OKS UCX | [UCX sheet](../domain/areas/ucx.md), shared builder, delivered-project analysis | Tool and distance/check coverage landed, not a clean universal etalon or B01/B02t benchmark. |
| Derivation | [derivation sheet](../domain/areas/derivation.md), `tools/derive/`, AGR Tools stages 6–9 | Shared tools exist; an unconditional two-object hash-parity/acceptance claim is unsupported. |
| Export / package | [package sheet](../domain/areas/package.md), `validate_package`, SINTEZ bridge | Checker integration is not official acceptance; metadata/manual gates remain. |
| Ground surface | [Ground sheet](../domain/areas/ground-surface.md), Vatutino v015 | Ground-only L3 case accepted under D193; not approval of the assembled site. |
| Ground textures | Vatutino recipes/binding and V009 | D097/D160 resolve density policy; assembled VPM still has density failures. |
| Ground UCX | Vatutino 727-piece UCX in the site acceptance sheet | No longer L0; advisory gap/coverage evidence remains distinct from final approval. |
| GroundEl / MAF | [MAF sheet](../domain/areas/groundel-maf.md), catalogue, skill, site examples | Technical catalogue is not identification; accepted geometry is not all colour/ID/profile QA. |
| Flora | [Flora sheet](../domain/areas/flora.md), catalogue, skill, atlas tool | Maps were approved; v003 defects/identity gaps remain; D232 selects replacement route A. |

The old L3 label for BODY and new Ground acceptance must not be summed into "the
whole pipeline is L3". §3's user-only acceptance and official-check separation remain
valid. The later L4/L5 terminology in #353 is a different readiness rubric, not a
silent redefinition of these L1/L2/L3 levels.

## Every original ticket candidate (§7 and repeated §11)

Each row has status **on the frozen main**, an owning issue/merged PR where known,
and a concrete witness or explicit missing artifact. Bare # references in this report
mean the **pilot** repository unless marked upstream.

| Candidate | Original ask | Status | PR / issue | Main evidence and remaining limit |
|---|---|---|---|---|
| T-BODY-1 | BODY requirement sheet | done | #130; PR #138 | `docs/domain/areas/body.md`; `tests/test_area_requirement_sheet.py`; later V002/V004 rows updated. |
| T-BODY-2 | Standalone model-body skill, B01 dry run/eval | partly | #351; PR #363/#395; #1201 | `docs/procedure/TASK_TO_MODEL.md`, `docs/scenarios/oks-vpm.md`; no `.agents/skills/model-body/SKILL.md` or its promised B01 eval. D107/D108 replace generator-only production instructions. |
| T-BODY-3 | K01 9/9 or decided remaining conflicts | partly | upstream #9–#11; #1209 / PR #1216 | `benchmark/bench-k01-kpp1/README.md` still records mesh/opening/material failures; KPP1 rerun is not a 9/9 K01 receipt. |
| T-BODY-4 | Multi-height BODY benchmark | not started | upstream #82 (deferred by owner) | No unequal-parapet accepted benchmark; D065 and COORDINATION_RULES 32 retain the missing-real-etalon gate. B02 multi-storey coverage is not this benchmark. |
| T-WIN-1 | Window/door sheet | done | #151; PR #199 | `docs/domain/areas/windows.md`; source/column/gap contract tests. |
| T-WIN-2 | Window library plus modelling skill/procedure | partly | upstream #4; PR #245; #1024; #1259 | `library/windows/window_types.json`, `standard.json`, `adapters/max/agr_tools/windowgen_core.py`; sash readings unconfirmed, six quarantined types in 1.x plan; no dedicated model-windows skill. |
| T-WIN-3 | bench-b05-windows with user etalon | not started | upstream #4; #1259 (current library owner) | `benchmark/` has no `bench-b05-windows`; synthetic window tests are not the requested independent benchmark. |
| T-WIN-4 | KPP1 v007 windows accepted as an area | partly | #1209 / PR #1216; PR #969 (ELV, different object) | `jobs/KPP1/STATE.md` records whole-model ~90% acceptance, not this area gate; newer rerun has blockers. ELV acceptance cannot sign KPP1 windows. |
| T-DEC-1 | Decor sheet | done | #152; PR #206 | `docs/domain/areas/decor.md`, `tests/test_decor_requirement_sheet.py`. |
| T-DEC-2 | K02 decor benchmark | not started | upstream #117 (failed case, not delivery) | `benchmark/bench-k02-decor-fragment/README.md` and `decor-catalog.json` are not a measured green run; no supplied/accepted K02 etalon receipt. |
| T-DEC-3 | B03 decor etalon and first run | not started | upstream #117 | `benchmark/bench-b03-decor/README.md` only; no etalon/run. Do not resurrect OBJ03 without owner approval. |
| T-UV-1 | Cross-target UV/atlas sheet | done | #153; PR #209 | `docs/domain/areas/uv-atlas.md`, target table and contract tests. |
| T-UV-2 | Obr22 bench-uv-01 overlap/density/pixel comparison | not started | #149 candidate; no benchmark issue implementation | No `benchmark/bench-uv-01`; job UV examples are not the stated independent comparison. |
| T-UV-3 | General V009 density with wrong-density fixture | done | PR #1100; #431 (D160) | `src/twinqa/scene.py:_texel_density_findings`, `src/twinqa/uv.py`; `tests/qa/test_decision_checks.py`, `test_texel_metric_divergence.py`. Per-polygon/per-tile VPM checks exist; no claim of all NPM/vegetation semantics. |
| T-TEX-1 | Texture/map sheet | done | #154; PR #210 | `docs/domain/areas/textures.md`, `tests/test_textures_requirement_sheet.py`. |
| T-TEX-2 | Reproduce facades v003 atlas hashes/tolerance | not started | #149 candidate; no benchmark implementation | No named reproducibility benchmark/receipt; Ground recipes and MAF atlas tests test different inputs. |
| T-TEX-3 | KPP1/PSU275 VPM D/ERM/N area acceptance | partly | #1209 / PR #1216; #1106 / PR #1115 | `jobs/KPP1/STATE.md`, `tools/derive/package_vpm.py`; historical maps/packages exist but no separate accepted ERM/Normal area gate; deferrals remain. |
| T-UCX-1 | UCX target/gap/limit sheet | done | #131/#175; PR #142/#186 | `docs/domain/areas/ucx.md`, delivered-project review and updated checks. |
| T-UCX-2 | Shared Main/Ground tool and pipeline inventory fix | done | #166; PR #307/#334 | `src/dt_ai/geometry/ucx_build.py`, `tests/test_ucx_build.py`, `docs/pipeline.md`; one-sided D134 contract. D225 selects canonical cores for future consolidation, not proof that consolidation is finished. |
| T-UCX-3 | bench-ucx-01 B01/B02t user-approved etalon | obsolete | #165 / PR #205; #166 / PR #307 | Owner's 2026-10-15 correction: analyse delivered projects, not imperfect KPP1/PSU275-derived etalons. `docs/research/ucx-etalon-analysis.md` is the replacement evidence; no claim that the literal B01 benchmark landed. |
| T-UCX-4 | GROUND-PROJECTION UCX after v008 review | obsolete | #176; #295/#371/#298; PR #308/#906/#1153 | Original Ground is explicitly not the reference; Vatutino replaces that object. Real Ground UCX exists, but the site sheet retains review statuses; this does not close all UCX L3. |
| T-DER-1 | Master/profile derivation contract sheet | done | #155; PR #212 | `docs/domain/areas/derivation.md`, `tests/test_derivation_requirement_sheet.py`. |
| T-DER-2 | Shared derive pipeline; KPP1/PSU275 reproduction | partly | #1106; PR #1115; #1024 | `tools/derive/{npm_atlas,export_npm,package_vpm,fbx_parity}.py`; public `dt derive atlas/npm/package` and tests exist. Full original two-job hash-for-hash packages are not certified; D225 consolidation remains #1141. |
| T-DER-3 | KPP1 v007 shared-derived user acceptance | partly | #1209 / PR #1216 | `jobs/KPP1/rerun-1209/RUN-LOG.md`: VPM first, NPM derived, readback; both `passed=false`. Newer build is not acceptance of the old v007 claim. |
| T-PKG-1 | Export/package/GeoJSON/lights sheet | done | #156; PR #213 | `docs/domain/areas/package.md`, `tests/test_package_requirement_sheet.py`. |
| T-PKG-2 | PSU275 real GeoJSON and lights validated | partly | #1107 / PR #1123; #1106 / PR #1115; #1024 | `docs/research/geojson-d220-customer-files.md`, `tools/derive/package_vpm.py`, AGR Tools light/package functions. Customer sample analysis and a writer are not a newly validated PSU275 GeoJSON + Light FBX run. |
| T-PKG-3 | SINTEZ/AGR integration as recorded gate | done | #298 / PR #1153; #753 / PR #891 | `jobs/KPP1/scripts/run_agr_checker.py`, `tools/sintez_parity.py`, `tests/qa/test_sintez_parity.py`; `docs/deliveries/vatutino-site-2026-11-09.md` and AC08 report record actual checker failures. Gate exists, official pass does not. |
| T-GND-1 | Ground surface sheet | done | #157; PR #218 | `docs/domain/areas/ground-surface.md`, table contract; later GND-03 corrections #1133/#1224. |
| T-GND-2 | Review old GROUND-PROJECTION v008 / Max import | obsolete | #176; #371 / PR #906 | Owner rejected the old case as a general reference; `docs/cases.md` records Vatutino v015 NPM/VPM acceptance 2026-11-04. D157/D193 define its bounded exceptions. |
| T-GND-3 | Generalise old height-field job into dt ground | partly | #176/#195/#295/#371; PR #232/#299/#308/#906 | `adapters/cad/spozu.py`, `src/dt_ai/geometry/ground_cake.py`, `tools/ground/build_ground_v015.py`; real Vatutino pipeline exists, not the literal old v003 fixture/CLI. |
| T-GND-4 | bench-g01-site two slopes + 30 cm step | not started | #149 candidate; #176 changes practice | No `benchmark/bench-g01-site` user etalon. Ground synthetic tests and Vatutino runs are different evidence. |
| T-GTX-1 | Ground texture target rows and conflict pointer | done | #153/#154/#175; PR #209/#210/#186 | UV/textures sheets contain Ground rows; D097 establishes linear px/m, D160 fixes VPM lower bound. |
| T-GTX-2 | Real Ground texture set at validated density | partly | #319/#340; PR #329/#368; #298 / PR #1153 | `jobs/VATUTINO-SITE/ground-textures.md`; real maps bound/read back. Current assembled site V009 fails; existence of maps is not density acceptance. |
| T-MAF-1 | Every MAF identified by manufacturer/spec with confidence | partly | #183 / PR #208; #182; #425 | `library/maf/README.md` explicitly says technical audit, not identification; 931 entries and dimension candidates do not prove manufacturer/article identity. User supplied 205-row XLSX, so "no paths" is obsolete. |
| T-MAF-2 | MAF sheet | done | #132/#181; PR #143/#233 | `docs/domain/areas/groundel-maf.md`, project practice, table tests. |
| T-MAF-3 | model-maf skill | done | #182; PR #277 | `.agents/skills/model-maf/SKILL.md`, source/spec/atlas/smoothing/placement procedure and documented dry walk. |
| T-MAF-4 | bench-maf-01 three independently identified etalons | partly | #185/#313; PR #238/#320/#493 | `tests/qa/test_maf_surface.py`, `jobs/VATUTINO-SITE/maf/site-maf-set.md`; real set/checks exist, but no literal `benchmark/bench-maf-01` independent three-object etalon run. |
| T-MAF-5 | Ten real-spec MAF verified and user accepted | partly | #313/#349/#425; PR #320/#493/#1093 | `docs/cases.md`: 13 positions accepted as geometry, Verona rows 2–10 accepted as library baseline; colour/profile/site gates are narrower/different. #425 now waits for the owner's MAF session. |
| T-FLO-1 | Flora sheet | done | #158; PR #215 | `docs/domain/areas/flora.md`, source/column/gap contract. |
| T-FLO-2 | Flora library identification against schedules | partly | #189/#216; PR #229/#273 | `library/flora/{catalogue,species-curation}.json`, Vatutino species schedule; unidentified names/15 stand-in gaps and unverified VPM identity explicitly retained. |
| T-FLO-3 | model-flora procedure | done | #188; PR #237 | `.agents/skills/model-flora/SKILL.md`; procedure now library -> placement -> one scene atlas, not atlas-before-placement. |
| T-FLO-4 | bench-flora-01 tree/shrub/hedge verification | partly | #191/#217/#347; PR #239/#310/#362 | Checks and real atlas/light outputs exist; no literal independent `benchmark/bench-flora-01`; D232 changes the next production route. |

## Spec #149: every user story

| Story | Ask | Status | PR / issue | Evidence / boundary |
|---|---|---|---|---|
| US-01 | One sheet per area | done | #130–#158; PR #138/#142/#143/#199/#206/#209/#210/#212/#213/#218/#215 | Eleven files under `docs/domain/areas/`; two cross-cutting targets share sheets. |
| US-02 | Source per requirement | done | #150 / PR #173 | `tests/test_area_requirement_sheet.py` checks citations. |
| US-03 | Numbers read on rendered PDF | done | PR #138/#142/#143 and eight L1 PRs | Calibration evidence sections in sheets and `docs/domain/areas/ucx-evidence/review.md`; historical receipts, not fresh image verification by this audit. |
| US-04 | Point to conflicts, do not decide them | done | #150/#151/#153; PR #173/#199/#209 | Sheets link C23/C35/C36 etc.; only owner decisions resolve them. |
| US-05 | Every row states L2 coverage | done | #150 / PR #173 | Seven-column sheets and contract test. |
| US-06 | List every none row as gap | done | #150 / PR #173 | Same test; text can still be semantically stale, see US-11. |
| US-07 | Remaining eight L1 sheets | done | #151–#158; PR #199/#206/#209/#210/#212/#213/#218/#215 | All eight present; BODY/UCX/MAF calibration already present. |
| US-08 | Ground texture/UCX target rows | done | #153/#154/#131 | `uv-atlas.md`, `textures.md`, `ucx.md`. |
| US-09 | Automatic FBX check for every closed L2 gap | partly | #159–#166/#185/#191; PR #304 | V002/V004/V010/V012 and MAF/Flora checks exist; many none/manual/partial rows remain, not every requirement automated. |
| US-10 | RED/GREEN fixture per new check | done | PR #222/#225/#226/#228/#230/#231/#238/#239 | `tests/qa/test_scene.py`, `test_topology.py`, `test_scene_clearance.py`, `test_maf_surface.py`, `test_scene_flora.py`; bounded first wave, not every future gap. |
| US-11 | Update coverage cell in same PR | partly | PR #222/#225/#226/#228/#230/#231/#1100 | First-wave PRs updated cells; BODY-X, UV-06, TEX-18 and package sheet still say V009 unimplemented despite current scene implementation. Audit flags drift, does not rewrite sheets. |
| US-12 | Shared UCX tool | done | #166 / PR #307/#334 | `src/dt_ai/geometry/ucx_build.py`, target parameter and tests; canonical-core migration remains #1141/D225. |
| US-13 | Delivered-project UCX etalon analysis | done | #165 / PR #205 | `docs/research/ucx-etalon-analysis.md` compares three deliveries and KPP1/PSU275; defects retained rather than blessed. |
| US-14 | Identify MAF library against specifications | partly | #183/#182/#425 | Audit and XLSX supplied; all-object confident identification not achieved. |
| US-15 | Flora library/schedules as etalons | partly | #189/#216/#426/#1146 | Library/maps/schedules exist; defects, botanical/identity gaps and pending route-A visual gate remain. |
| US-16 | SPOZU DWG adapter | done | #194/#195; PR #240/#299 | `adapters/cad/{dwg,spozu}.py`, `configs/vatutino_dom2.yaml`, `tests/test_adapters_cad_spozu.py`; real Vatutino inventory. |
| US-17 | Independent verify board kind | partly | #149; #298/#351 | Acceptance sheets/procedure and separate review roles exist. No proof from this repository of deployed blind `verify` card-kind routing; code review is not blind model verification. Board implementation is outside this worktree. |
| US-18 | Notify ready-for-view, offer Blender any day | partly | #348 / PR #373; #1033; D233/D255 | `tools/review/publish.py`/pending queue exist; no telemetry here proves prompt notifications/offers for every ready result. |
| US-19 | Nightly area-level status page | not started | #149 | `docs/roadmap/status.md` absent. Generated `PROJECT_STATE.md` is a different artifact and contains stale open-PR entries. No claim of a working nightly publisher. |
| US-20 | Balanced providers/cheap docs lanes | obsolete | #149; COORDINATION_RULES 35–41/51/54/55/58/64 and 2026-11-10/11 resume notes | Owner repeatedly changed pause/quota/routing policy; current board config, not a fixed 2026-10-15 Codex/Claude split, owns dispatch. Not measured by this repo audit. |
| US-21 | BODY and MAF step-by-step skills | partly | #182/#351; PR #277/#363 | model-maf exists; BODY uses current scenario/playbook, not the requested standalone skill/eval. |

## Direct-child ledger (all 59, including later extensions)

All were CLOSED when retrieved. The **Status** column below independently assesses
what the ticket delivered; PR references are verified merged except where explicitly
called a replacement issue. Titles are shortened; frozen full bodies/comments are in
the evidence pack. These are direct sub-issues, not a claim to enumerate the entire
transitive GitHub graph.

| Child | Bounded deliverable | Status | PR / issue | Main witness or reason |
|---|---|---|---|---|
| CH-150 | Sheet contract | done | PR #173 | `tests/test_area_requirement_sheet.py`. |
| CH-151 | Windows sheet | done | PR #199 | `docs/domain/areas/windows.md`. |
| CH-152 | Decor sheet | done | PR #206 | `docs/domain/areas/decor.md`. |
| CH-153 | UV sheet | done | PR #209 | `docs/domain/areas/uv-atlas.md`. |
| CH-154 | Textures sheet | done | PR #210 | `docs/domain/areas/textures.md`. |
| CH-155 | Derivation sheet | done | PR #212 | `docs/domain/areas/derivation.md`. |
| CH-156 | Package sheet | done | PR #213 | `docs/domain/areas/package.md`. |
| CH-157 | Ground sheet | done | PR #218 | `docs/domain/areas/ground-surface.md`. |
| CH-158 | Flora sheet | done | PR #215 | `docs/domain/areas/flora.md`. |
| CH-159 | Units / scale | done | PR #222 | `src/twinqa/fbx_header.py`, `tests/qa/test_fbx_units.py`. |
| CH-160 | Topology defects | done | PR #225 | `src/twinqa/geometry/topology.py`, `tests/qa/test_topology.py`. |
| CH-161 | Co-directional clearance | done | PR #226 | `src/twinqa/clearance.py`, `tests/qa/test_scene_clearance.py`. |
| CH-162 | UCX present / no materials | done | PR #228 | V010 in `src/twinqa/scene.py`, `tests/qa/test_scene.py`. |
| CH-163 | UCX / MAF name grammar | done | PR #230 | `src/twinqa/naming.py`, `tests/qa/test_mesh_names.py`. |
| CH-164 | UCX intersections | done | PR #231 | V010 pair checks in `scene.py`; gap diagnostic is distinct from intersection fail. |
| CH-165 | Delivered UCX analysis | done | PR #205 | Research report + measured audit JSON. |
| CH-166 | Shared UCX builder | done | PR #307/#334 | `src/dt_ai/geometry/ucx_build.py`, `tests/test_ucx_build.py`. |
| CH-175 | Ground density / UCX gap decisions | done | PR #186 | D097/D098 in `docs/decisions.md`; D160 later corrects lower bound. |
| CH-176 | Ground skill | done | PR #232 | `.agents/skills/model-ground/SKILL.md`; old Ground case explicitly not reference. |
| CH-180 | MAF size / sinking / hidden-bottom decisions | done | PR #193 | D094–D096; decided C38. |
| CH-181 | MAF project practice | done | PR #233 | MAF sheet and `tests/test_maf_project_practice.py`. |
| CH-182 | MAF skill | done | PR #277 | `.agents/skills/model-maf/SKILL.md`. |
| CH-183 | Per-MAF audit/export catalogue | done | PR #208; follow-up #227 | `library/maf/{catalogue,audit}.json`, README: 931 entries, 927 exact triangle matches; technical exceptions retained, not identification. |
| CH-184 | 512 atlas packer | done | PR #196 | `tools/materials/atlas_maf.py`, `tests/test_atlas_maf.py`. |
| CH-185 | MAF checks | done | PR #238/#304 | `tests/qa/test_maf_surface.py`, V004/size findings; failing real models not silently accepted. |
| CH-187 | Flora tolerances / placement decisions | done | PR #198 | D099–D102 in decision log. |
| CH-188 | Flora skill | done | PR #237 | `.agents/skills/model-flora/SKILL.md`. |
| CH-189 | Flora library audit | done | PR #229 | `experiments/flora-library-audit/`, `docs/experiments/flora-library-audit.md`; availability not geometry identity. |
| CH-190 | Generated/cut-out species maps | done | PR #220 | `docs/cases.md` three-species map approval; owner removed atlas scope to #217. |
| CH-191 | Flora checks | done | PR #239/#304 | `src/twinqa/flora.py`, `tests/qa/test_scene_flora.py`. |
| CH-194 | Vatutino SPOZU inventory | done | PR #240 | `docs/research/spozu-vatutino-inventory.md` and per-DWG inventories. |
| CH-195 | Typed CAD adapter | done | PR #299 | `adapters/cad/spozu.py`, project map, synthetic and opt-in real tests. |
| CH-216 | Consolidated Flora library/maps | done | PR #273 | `library/flora/README.md`: narrowed owner acceptance, identity explicitly unverified and split to #305. Not a whole-library geometry approval. |
| CH-217 | One scene-derived Flora atlas | done | PR #310 | `tools/library/flora_atlas_from_scene.py`, `tests/test_flora_atlas_from_scene.py`; site sheet records actual one-atlas run. |
| CH-292 | Opacity operation and swap planning | done | PR #303/#325 | `src/dt_ai/ops/operations.py`, opacity/invariant tests under `tests/ops/`. |
| CH-294 | First L2 integration batch | done | PR #304 | Integrated scene findings and updated BODY/UCX/MAF/Flora sheets. |
| CH-295 | Vatutino Ground build | partly | PR #308/#906 | Initial PR explicitly partial; v015 Ground later accepted, not all original site/metadata gates. |
| CH-296 | Site placement | done | PR #344 | `jobs/VATUTINO-SITE/placement-report.md`; counts/exclusions reported; placement is not object identity/quality approval. |
| CH-298 | Site assembly / checker / acceptance sheet | partly | PR #1153 | `docs/deliveries/vatutino-site-2026-11-09.md` verdict not passed; metadata/manual/geometry/texture blockers persist. |
| CH-313 | Vatutino MAF set | partly | PR #320/#493 | `jobs/VATUTINO-SITE/maf/site-maf-set.md`; geometry accepted, colour zones/IDs followed separately; not all ten-source-item complete verification. |
| CH-316 | Seeded placement engine | done | PR #323 | `src/dt_ai/placement/engine.py`, `tests/test_placement_engine.py`. |
| CH-317 | Synthetic vector PDF reader | done | PR #321 | `src/dt_ai/album/reader.py`, `tests/test_album_pdf_reader.py`; real album limits owned by #1228/#1233–#1236/#1254. |
| CH-318 | Local CI receipt/manual workflow | done | PR #376 | `tools/ci_receipt.py`, `tests/test_ci_receipt.py`; D222 later changes workflow/runner policy, not local-receipt validity. |
| CH-319 | Ground texture recipes | done | PR #329 | `tools/materials/ground_recipes.py`, `tests/test_ground_recipes.py`. |
| CH-332 | Refresh old PR group | done | PR #266/#260/#280; #337 | Closure comment records remaining #252 transferred to #337; all four PRs now merged. No new modelling capability implied. |
| CH-333 | Context diet | done | PR #335 | `AGENTS.md`, generated `docs/PROJECT_STATE.md`, `tests/test_context_diet.py`. |
| CH-337 | Remaining refreshes | done | PR #252/#260 | Owner cleanup comment 2026-11-02, merged states verified. |
| CH-338 | Contour rebuild operation | done | PR #341 | `src/dt_ai/ops/contour.py`, `tests/ops/test_contour.py`. |
| CH-339 | FBX structure -> parts | done | PR #342 | `src/dt_ai/parts/readers/fbx.py`, related reader tests. |
| CH-340 | Ground texture binding/readback | done | PR #368 | `tools/materials/bind_ground_textures.py`, `tests/test_bind_ground_textures.py`. |
| CH-345 | Quad-dominance invariant | done | PR #354 | `src/dt_ai/ops/inv_quads.py`, `tests/ops/test_inv_quads.py`. |
| CH-346 | Texel-ready invariant | done | PR #356 | `src/dt_ai/ops/inv_texel.py`, `tests/ops/test_inv_texel.py`; v015 exception bounded by D193. |
| CH-347 | Three light Flora variants | done | PR #362 | `library/flora/npm-light.json`, `tests/test_flora_npm_light.py`; variant QA not placement acceptance. |
| CH-348 | Review publication/cleanup | done | PR #373 | `tools/review/{publish,verdict,cleanup}.py`, review tests; D255 removes blanket waits-Max for checks. |
| CH-349 | Separate library showcases | obsolete | #1259/#1257; owner comment 2026-11-12 | Showcases absorbed into each library issue; MAF waits for owner's session. Existing #493 MAF showcase is not three-library completion. |
| CH-350 | Asset manifest / Drive sync | done | PR #372 | `assets/manifest.json`, `tools/assets/sync.py`; unknown Drive links remain pending, no invented licence. |
| CH-351 | Fixed-gate/free-path playbook | done | PR #363/#395 | `docs/procedure/TASK_TO_MODEL.md`, `schemas/JobChecklist.schema.json`, immutable-evidence walk. |
| CH-352 | Immediate roof-equipment library | obsolete | #1257; owner comment 2026-11-12 | Replaced by delivered-project research then library; do not infer roof catalogue from closed ticket. |
| CH-353 | First real building through kernel, Skolkovo triple | partly | #753/#968; PR #891/#1006 | AC08 L4 report is a real but different building: 5/19 applied after relative invariants, 14/17 parity, SINTEZ failures. No completed original Skolkovo revision/timing acceptance. |

## Supersession register: what must not be re-queued literally

| Old statement / affected line | Replacement decision or owner instruction | Current evidence / consequence |
|---|---|---|
| BODY built only from generated spec; add isolated procedures per old engine | D107 (reduce source), D108 (operation menu/invariants), D111 (PartsList); AGR Tools #1024 contract | `TASK_TO_MODEL.md`, `docs/agr-tools/OVERVIEW.md`, `docs/plans/agr-tools-1.x.md`. Missing dedicated skills still count as missing, but should describe current stages, not obsolete generator-only production. |
| Three competing shared UCX/atlas/placement implementations | D225: AGR Tools Max cores canonical; #1141 follows #1105 | T-UCX-2/T-DER-2 already have useful tools; consolidation is open, not done merely because the decision exists. |
| Any step must wait for Artem's Max | D233, D250 and general D255 | Hashed-copy agent-owned Blender 5.1.2+ allowed for modelling/checks; final AGR-Tools-in-Max check still needs Max. No instance was launched in this audit. |
| KPP1/PSU275 UCX are ideal etalons; derive B01 etalon from them | Owner 2026-10-15 correction in #149/#165; one-sided tolerance D134 | Delivered analysis has Skolkovo 215 hulls/0 overlaps, Mashi 139/8 overlaps, A101 0 hulls. Delivered does not mean compliant. |
| Old GROUND-PROJECTION v008 is the reference; smooth away all small steps | Owner Ground grilling as preserved by #176/C37; D157/D193, #371 acceptance | Vatutino v015 replaces the reference, with explicit face-bound texel exceptions. C37 general small-step conflict remains open; this audit does not choose a rule. |
| Ground density unresolved and blocks all textures | D097 linear px/m; D160 lower bound 512; D193 v015-only exception | V009 now implemented, but some sheets retain stale none/unimplemented text. No general density waiver. |
| One <=150k master means every VPM job must stay <=150k | D010 retains general project target, BODY-F hard VPM limit 1M; KPP1-specific D238 budgets | KPP1 R1 approved 145k NPM/960k VPM total budgets and VPM-first derivation; do not extrapolate that local choice to every job or silently alter D010. |
| KPP1 R1 dimensions stay provisional forever | D254 supersedes provisional D249 for R1 | 0.35 parapet, slab 7.700–7.909, levels 3.900/7.909 final for R1; older RUN-LOG wording is historical. Architect changes become R2, not invented approval of delivery. |
| Generic PDF parser means dimensions/materials ready | #1228 / PR #1232 measured research; #1234 owner partial acceptance and #1254 | `pdf-album-pipeline.md`: text recall != geometric binding. PR #1249 accepted partial (levels 43/43 precision, recall 0.443; axes 0/8); #1235/#1236/#1254 remain current work. PDF -> DWG not the default. |
| MAF library before skill never; identify only when PDFs appear | Owner supplied XLSX (#182/#185), #183 audit, #425 session instruction 2026-11-12 | Technical catalogue exists; library-wide identification remains partial. Next MAF-from-PDF work waits for Staropetrovsky ~50-MAF etalon session/retro; do not file duplicates now. |
| Flora skill then build library; atlas from a species list | Owner #216/#217 ordering correction; D232 route A | Library/maps -> place -> one atlas from scene; old v003 repair stays parked while new stars/shells are the chosen route. Map-only approval does not approve geometry. |
| No window library / wait for first type decisions | Upstream #4 supplied Win_Typical; D204 family standard, D221 glass 1001; #1259 | Library exists; template/cleanliness/sash rebuilding is the current ask. No new parallel window-library ticket. |
| Immediate roof library and standalone showcase tickets | Owner 2026-11-12 on #352/#349 | #1257 research then roof library; #1259 shared library format starts with windows. Roof and later MAF reuse it. |
| Fixed night-queue topics/provider balance/nightly status assumption | Repeated owner routing/pause instructions; no `docs/roadmap/status.md` | Do not infer deployment from the proposal. Use current board state; no scheduler change is made here. |
| All check/acceptance gates can pass despite deferred metadata | D125, D220/D223/D224; AGENTS mandatory-gate rule | KPP1 and assembled Vatutino remain `passed=false`; no official pass is created by closing #149. |

## Original decisions (§8), board proposals (§9) and questions (§10)

The original **16 grilling decisions** are reconciled explicitly here; local numbered
items below are not new D-ids and do not allocate decisions.

| Original decision | Disposition | Evidence |
|---|---|---|
| 1 capability not delivery roadmap | retained | This audit distinguishes artifact completion from object acceptance. |
| 2 area tree | retained | Eleven sheets + Ground texture/UCX targets; no extra duplicated sheet required. |
| 3 Unreal/IFC/harness separate | retained | No Unreal/IFC implementation or harness completion claimed by #149 closure. |
| 4 NPM/VPM axis, one master | qualified | Shared derivation exists; KPP1-specific D238 budgets/VPM-first do not rewrite the general D010 target. |
| 5 L1/L2/L3 readiness | retained | Original definitions; no promotion based solely on a merged PR. |
| 6 official AGR pass is separate | retained | KPP1/Vatutino/AC08 reports retain fails/manual gates. |
| 7 reviewed L1 sheets | done as bounded wave | Eleven sheets and calibration/contract tests. |
| 8 parallel L1/L2, L3 dependencies | retained | No new schedule or ownership changes in this audit. |
| 9 old real/synthetic/remodel learning order | retained | Synthetic labelled tests vs real historical job reports; no fake real-object evidence. |
| 10 skill before typed libraries | superseded in ordering | #216/#217 library-first owner correction; #183 technical audit and current #1259 template. |
| 11 MAF identification/external search | retained, incomplete | T-MAF-1 and #425; not all catalogue entries identified. No external image upload in this task. |
| 12 blind verify + owner acceptance | partly realised | D125/playbook/sheets exist; deployed blind card kind not proven (US-17). |
| 13 free DCC choice | refined | D233/D250/D255; canonical AGR Tools and final Max check exception remain. |
| 14 Ground Max-import priority | superseded object/priority | Vatutino v015 accepted #371; old v008 no longer learning reference. |
| 15 pilot source of truth | retained | All audit main evidence is pilot; original upstream links are explicitly disambiguated. |
| 16 per-area map issues / L2 children | partly realised | #149 gained 59 direct children; no per-area-map or universal coverage claim. |

| §9 proposal | Status on main / evidence |
|---|---|
| verify kind | partly: US-17, not proven deployed by a pilot file. |
| Review L1 research | done for named wave: reviewed calibration/remaining-sheet PRs; not a claim about all future board routing. |
| night_queue topics | not measured here: external scheduler, owner routing has changed; no new queue writes. |
| per-area map issues | partly: child issues exist, not one current complete map per area. |
| paths in card inputs | done for MAF/Flora/SPOZU library inputs (#183/#189/#194); hashed external pointers, not customer binaries committed. |

| §10 original question | Answer now / still open |
|---|---|
| 1 Flora schedules exist? | Yes: #149 amendment, #189/#216 and Vatutino species/schedule data; identity gaps remain. |
| 2 MAF naming? | #182/#185 supplied XLSX naming `<Manufacturer>_<ObjectName><Article>_<high\|low>`; technical IDs alone are not manufacturer identity. |
| 3 Ground density unit? | D097 linear px/m; D160 VPM lower bound 512. Resolved, not a new user question. |
| 4 VPM triangle table vs figure? | D010 chooses table hard limits; object-specific budgets/exceptions recorded separately. |
| 5 Which missing etalons first? | UCX delivered analysis done; no evidence of approved B03/K02/B05/G01 etalons. Do not fabricate them or revive OBJ03. |
| 6 Window library? | Supplied, PR #245 then D204; remaining sash/template work #1259 absorbs #246. |
| 7 tool versions/licence/leases/IFC? | D233/D255 and current wrappers refine DCC access; IFC delivery remains outside this roadmap. No fresh licensing/IFC-schema certification here. |

### Repository-number disambiguation

The 2026-10-15 roadmap mixes **upstream** source references (notably #4 window data,
#117 failed OBJ03, harness #118/#119–#134) with **pilot** PR #102 and hypotheses
#83–#107. Its materials-registry pointer `#7` is stale/ambiguous: upstream #7 is
actually "Extractor: openings anchored on holes in the body", not a materials registry.
It is not counted as completed materials work here. The same numbers in pilot often mean unrelated PRs/issues.
Upstream #4 was closed citing pilot PR #245 with follow-up #246; upstream #117 was
closed as unsuccessful/obsolete, never a successful decor benchmark. The upstream
harness spec #118 explicitly excludes the modelling pipeline; its #119–#134 are
context references, not missing production candidates in this audit. Pilot hypotheses
#83/#107 and adoption PR #102 concern matching/IFC rather than a completed area benchmark.
Local named source docs (`3dsmax-scripting.md`, `blender-bpy-automation.md`,
`mcp-dcc-bridges.md`, `ifc-intake-src-contract.md`) are historical tool-input notes,
not new output tickets. Read links in their original repository context.

## Next priorities: proposals only, do not file

These four rows are suggested issue **titles/levels**, not new issues or permission
to start parked work. Existing owners are reused; no duplicate issue was created.

| Proposal | Proposed issue title | Level | Why now | Existing owner / gate |
|---|---|---|---|---|
| NEXT-1 | Windows library: shared clean-asset template, sash evidence and Blender showcase | medium | Turns an existing, partly unconfirmed library into a reusable format for roof/MAF/Flora; directly requested 2026-11-12. | Reuse #1259; absorbs #246/#349; first windows piece accepted before library-wide migration. |
| NEXT-2 | Roof equipment: compare delivered NPM/VPM projects before building a reusable catalogue | medium | Original #352 lacks the evidence needed to pick clean reusable roof assets; research should precede extraction/placement rules. | Reuse #1257; follow #1259 format; Blender hashed copies under D233/D255. |
| NEXT-3 | Substance photo/procedural finishes: two real pilots with physical scale and D/ERM/N parity | medium | Addresses procedural finish generation with measurable quality/time rather than adding unvalidated generic textures. | Reuse #1258 (replaces #792); no assumption that headless/licence capability exists. |
| NEXT-4 | PDF intake: recover block axes/levels and prove independently calibrated dimension binding | hard | #1249 partial acceptance and real-album failures show a source-understanding bottleneck, unlike another synthetic-only parser. | Reuse #1254; coordinate #1235/#1236, do not duplicate their schedule/OCR scope. |

After those, the unfunded gaps include independent UV/decor/window/site benchmarks,
BODY skill/current-route eval, semantic L2-sheet refresh and deployed status/verify
proof. They are **not** additional proposed issues in this task. MAF-from-PDF is not
queued until the owner's Staropetrovsky session/etalon/retro is ready (#425).

## Verification and reproducibility

Exact discovery commands (all read-only except own venv/test outputs):

```bash
git fetch origin
git rev-parse origin/main
gh issue view 149 --repo artsafro/AGR-DigitalTwin-pilot --json title,body,comments,state
gh pr view 114 --repo artsafro/AGR-DigitalTwin-pilot --json title,body,mergedAt,files
gh api repos/artsafro/AGR-DigitalTwin-pilot/issues/149/sub_issues --paginate
gh issue view N --repo artsafro/AGR-DigitalTwin-pilot --json number,title,body,comments,state,closedAt
gh api repos/artsafro/AGR-DigitalTwin-pilot/issues/N/timeline --paginate
gh pr view N --repo artsafro/AGR-DigitalTwin-pilot --json number,title,state,mergedAt,mergeCommit,files
gh issue view 4 --repo artsafro/AGR-DigitalTwin --json number,title,state,body,comments
gh issue view 117 --repo artsafro/AGR-DigitalTwin --json number,title,state,body,comments
uv sync
uv run pytest -q tests/test_roadmap_149_audit.py --tb=short -p no:cacheprovider
```

`N` ranges are frozen in `roadmap-issues.json`/`roadmap-prs.json` in the evidence pack;
PR cross-references were not treated as proof of merge. The focused regression was
written first and failed **5 tests** on the missing report; its tests-first commit
is identified in the PR receipts. It checks exact set/cardinality and populated
status/evidence columns for T-*/US-*/CH-* rows, relative evidence links and 3–5
proposals. These are completeness tests, not an automated truth judge for the audit.
Full-suite, eval and mutation-probe results are attached to the PR's exact head,
not inserted here after the suite (which would change the certified revision).

No new standards, decisions, benchmark etalons or production behavior are introduced.
Open conflicts (including C23/C35/C37) are reported, not resolved. Missing blind
verification, unsigned manual gates and stale sheets remain visible. Once merged,
the suggested #149 closure comment is: "Superseded planning umbrella audited in
`docs/research/roadmap-149-audit.md` (#1260); bounded completed work and residual gaps
are listed there. Closure is not universal L2/L3 or delivery acceptance."
