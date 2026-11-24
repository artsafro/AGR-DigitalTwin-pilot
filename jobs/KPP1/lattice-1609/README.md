# KPP1 lattice restart, step 1: line list for W/S/N (#1609)

Artem 2026-11-21 («принимаю рекомендации», docs/research/body-mesh-method.md §6): the body is built only from
the lattice (BM-00). Ground-floor and band lines come from the Revit/DWG openings and zones list, snapped at 10 cm,
never from mesh vertices. A line stays if the cell class changes along it over >= 1.5 m or >= the opening width.
**Step 1 only:** the line list and one ground-floor sheet. The body is built after Artem's «ок».

## Skeleton [D324]

`skeleton.json`: cell `oks-npm` (sub-job `vpm/skeleton.json`: `oks-vpm`, no hooks); 5 hooks in `hooks/`, every other
stage is the shared command of `docs/agents/SKELETONS.md`:

| Hook | Stage / point | What |
|---|---|---|
| `kpp1_lattice.py lines / input / check` | `body` before | Revit line list, ring lattice for `proto_lattice.py --lines`, ring/station/cell check |
| `kpp1_elements.py` | `body` after | stdlib kernel of the separate elements (posts, frames, portals, glass, finishes), imported by the assemble hook |
| `kpp1_assemble.py` (`render`, `split`) | `body` after | Blender: body UV/finishes + elements [D336], fixed-camera renders, element-wise split for xView |
| `kpp1_sheets.py lines / lattice / compose` | `verifier` after | review sheets for Artem |
| `kpp1_package.py verify / npm-dir / record-ground` | `package-npm` before | frozen-packet check, NPM package dir + V013 bounds, #1416 Ground derivation record |

Modelling split [D336]: plinth=one_with_body; inset=posts, windows, stained_glass, roof, flashings; texture=panels; reason=KPP1 lattice body (Artem 2026-11-16/21/24): the plinth is a finish band of the lattice body, the corner posts, window frames/surrounds, portals, E annex, roof and glass are separate clean-quad elements never welded into the body, the cassette panels are UDIM texture with a whole-period shift.

## Inputs (read-only)

| Input | sha256 (16) | Role |
|---|---|---|
| Revit census `census-v001/openings_spec.json` (laughing-hawking worktree, `jobs/KPP1/outputs/`) | `fbacbc8246737b37` | window surrounds, doors, portals, screens, grilles per facade (= `openings-1511/PARITY.json`) |
| Revit census `census-v001/walls_ext.objects.json` | `46c328dabf0f5bed` | exterior wall slices = zones (plinth, 0.9 / 2.7 / 7.1 / 8.1 splits), cladding, canopies |
| `finish_bands.json` (this folder) | in git | finishes by height from ИД slides 25-30 + Revit slices; checked on R1 v003 texture |
| R1 v003 `SM_Kpp_1.fbx` (`kpp1_r1_v003.fbx`) | `76a7c97e523d6ac6` | sheet background + hole check only, not a line source |
| R1 v003 NPM export `run-r1-v003/export/fbx/0000_Kpp_1_01.fbx` + atlas `T_Kpp_1_001_Main_d_1.png` | `d4df3ce68471443f` / `daebf173a1a050b2` | textured background (same triangles as R1 v003) |

## Result (`line_list.json`)

- Levels shared by W/S/N (10 of 11): 0 / 0.9 / 1.125 / 2.1 / 2.7 / 3.075 / 4.775 / 6.725 / 7.1 / 8.65.
  The 8.1 split of the stacked Revit walls is dropped: it is texture, because the finish is the same above and below.
- Stations (verticals): W 6, S 23, N 14. These are the corners and the opening edges.
- Moved edges: 1. The S door at u 0.4 moves to the window edge at 0.305 (-95 mm).
- Thin strips < 30 cm on S: 5.315-5.53, 21.33-21.525, 26.6-26.765.
- Not body (separate elements [D336] or texture): portals, the N mullion screen, canopies, entrance cladding and grilles.
- Corner posts: the blue band slice stops 0.11 m before the corner; that gap is the post, a separate element, so the wall runs on to the corner.
- Hole check: all 20 Revit openings are holes in R1 v003, with at most 3 % of each opening on the wall plane (`hole_check.json`).

Evidence: `G:/Мой диск/AGR-evidence/1609-kpp1-lattice-lines/step1/` (`kpp1-lattice-lines-ground.png`/`.jpg`,
`line_list.json`, `hole_check.json`, `SHA256SUMS.txt`).

## Reproduce

```
C=<laughing-hawking>/jobs/KPP1/outputs/census-v001
uv run python jobs/KPP1/lattice-1609/hooks/kpp1_lattice.py lines $C/openings_spec.json $C/walls_ext.objects.json OUT/line_list.json --bands jobs/KPP1/lattice-1609/finish_bands.json
"$B" -b --factory-startup --python docs/research/body-modelling-1618/dump_mesh.py -- kpp1_r1_v003.fbx OUT/dump
"$B" -b --factory-startup --python docs/research/body-modelling-1618/dump_mesh.py -- run-r1-v003/export/fbx/0000_Kpp_1_01.fbx OUT/dumpnpm
uv run python jobs/KPP1/lattice-1609/hooks/kpp1_sheets.py lines OUT/line_list.json OUT/dumpnpm/SM_Kpp_1_001_Main.npz OUT/dump/SM_Kpp_1_Main.npz run-r1-v003/atlas/T_Kpp_1_001_Main_d_1.png OUT/kpp1-lattice-lines-ground.png --check OUT/hole_check.json
```
Tests: `tests/jobs/test_kpp1_line_list_1609.py`.

## Step 2: lattice body with closed rings (Artem 2026-11-21: lines accepted; every level a closed ring)

The rule is «луп и ринг должен быть логичный, без прерваний на другой стороне фасада». So facade E is in the line
list now (`FACADES = W, S, N, E`). Its 3 Revit doors add stations, and the E door at z 3.9–6.0 adds 2 global rings.
#1736 core is not on main, so the body is built with the #1742 prototype `proto_lattice.py`. Its new `--lines` input
takes the stations, levels and openings from the list. Every opening cell sits at plane + 0.25 reveal. Every other
cell keeps the R1 v003 depth (clustered at 3 cm, rounded to 1 cm). A cell where R1 has no surface within 3.5 m is
a hole the list lacks (glazed side lights at the entrances), so it is treated as an opening.

- `kpp1_lattice.py input`: line list → one ring lattice (perimeter s, S→E→N→W, `--shift` into the R1 frame).
- `kpp1_lattice.py check`: per level closed yes/no, per station through yes/no, defects per lattice cell (local signal).
- `kpp1_sheets.py lattice`: unrolled S | E | N | W straight elevations, before/after, rings and cells marked.

Reproduce (outputs `C:/x/ev_1609/s7`, evidence `G:/Мой диск/AGR-evidence/1609-kpp1-lattice-body/step2/`):
```
uv run python jobs/KPP1/lattice-1609/hooks/kpp1_lattice.py lines $C/openings_spec.json $C/walls_ext.objects.json O/line_list.json --bands jobs/KPP1/lattice-1609/finish_bands.json
uv run python jobs/KPP1/lattice-1609/hooks/kpp1_lattice.py input O/line_list.json O/lattice_r1.json --shift -14.655 -5.355
"$B" -b --factory-startup --python docs/research/body-mesh-method/proto_lattice.py -- kpp1_r1_v003.fbx O/p6 --objects SM_Kpp_1_Main --lines O/lattice_r1.json --zmin 0 --zmax 8.65
"$B" -b --factory-startup --python docs/research/body-modelling-1618/dump_mesh.py -- O/p6/proto.fbx O/d6
uv run python jobs/KPP1/lattice-1609/hooks/kpp1_lattice.py check O/d6/SM_Proto_Body.npz O/lattice_r1.json O/qa/check_p6.json
uv run python jobs/KPP1/lattice-1609/hooks/kpp1_sheets.py lattice O/lattice_r1.json OUT.png --model LABEL NPZ CHECK.json ...
```
Tests: `tests/jobs/test_kpp1_lattice_body_1609.py`, `tests/jobs/test_kpp1_line_list_1609.py`.

## Step 3: corner posts as separate elements + UV/materials (Artem 2026-11-21: body accepted)

`kpp1_assemble.py` (Blender) takes the accepted body p6 and the quad-v003 master:
- body faces get the finish of their z band (`kpp1_elements.finish_of_face`: sill up = band below, head down = band
  above), then the shared VPM owner `tools/blender/vpm_uv.py` cuts edge rings for the tile span (no T-junction) and
  packs world-metre UVs into the finish's UDIM tile with a whole-period shift (vpm_textures.json, S 4.096 m);
- the four corner posts are the quad-v003 faces outside the ring, grouped per corner (`kpp1_elements.outside_components`),
  voxelised on their own planes (`kpp1_elements.post_cells`, rays cast outward), voxels inside the ring are body,
  the contact face on the ring plane is not built; each post is its own object `SM_Kpp_1_Main_Post_<corner>` [D336].
  Post finish = v003 UDIM tile in the R1 tile scheme (`r1230/tex/textures.json`: 1005 = Frame_RAL9016).
- the other 25 outside components of v003 (window surrounds, portals, E annex, grilles) are listed in `assemble.json`
  for the package step; nothing is dropped silently.

The modelling split of the job is the one `Modelling split [D336]` line in the skeleton section at the top.

Draft a2 (`C:/x/ev_1609/s8/a2`, evidence `G:/Мой диск/AGR-evidence/1609-kpp1-lattice-posts/step3/` + SHA256SUMS):
body 1134 -> 1244 quads after texel cuts, posts NE 27 / NW 70 / SE 27 / SW 51 quads, 0 tris, 0 n-gons, UV overflow 0,
density 841-1000 px/m; xView NPM-OKS PASS 0/0/0 (all objects); gates63b per element: body 0 open / 0 T / 0 non-manifold,
posts 0 T / 0 non-manifold (their open rim is the contact with the wall); mesh_quality_score 84.6 (p6 83.6, v003 77.3).

```
uv run python jobs/KPP1/scripts/make_textures.py T
"$B" -b --factory-startup --python jobs/KPP1/lattice-1609/hooks/kpp1_assemble.py -- O/p6/proto.fbx SM_Kpp_1.quad-v003.fbx O/a2 T C:/x/kpp1/r1230/tex/textures.json
"$B" -b --factory-startup --python jobs/KPP1/lattice-1609/hooks/kpp1_assemble.py -- render O/a2/master-v004-lattice.blend T O/r2 after
"$B" -b --factory-startup --python jobs/KPP1/lattice-1609/hooks/kpp1_assemble.py -- render SM_Kpp_1.quad-v003.fbx C:/x/kpp1/r1230/tex O/r2 before
uv run python jobs/KPP1/lattice-1609/hooks/kpp1_sheets.py compose O/r2 OUT.png corners|ground TITLE
```
Tests: `tests/jobs/test_kpp1_posts_plan_1609.py`, `tests/jobs/test_kpp1_corner_plan_1609.py`.

## Step 4: package (Artem 2026-11-24: posts accepted, top belt blue [D376])

`kpp1_assemble.py ... package` builds the package master from the same inputs (b19, `C:/x/ev_1609/s9/b19`):
- frames and the E annex: voxel-rebuilt on their own planes (`kpp1_elements.element_plan`, outward ray only, 3 mm snap);
  a frame floating over a lattice opening reaches the 0.11 niche beside it (`kpp1_elements.frame_reach`, V003 decor embed);
- slanted portals, open/flat strips and the roof (the lattice body is an open facade tube, no roof): their v003 quads
  as separate elements, portals clamped 6 mm in front of the body (`kpp1_elements.clamp_outside`, no piercing);
- body faces take the non-band v003 finish at their place (doors, frames, membrane; band finishes never override the
  band scheme [D376]); glass moved in front of the body surface (`kpp1_elements.glass_target`, 0 m² hidden vs 46 m²);
- `master-v004-delivery.blend`: elements joined into SM_Kpp_1_Main as loose parts (export_npm takes one *_Main).

The package stages run as the skeleton commands (section "Skeleton" above, `C:/x/ev_1609/s10/chain12.sh`): derive
(`agr vpm-to-npm`, spec `spec_v004.json`), readback + xView (whole and element-wise [D336] via `kpp1_assemble.py split`),
`kpp1_package.py npm-dir` (OKS + the accepted #1416 Ground copy byte-for-byte, V013 bounds from the fresh readbacks),
`agr package-npm`, `agr build-manifest build` with masters per role [D328]/[D333] (`kpp1_package.py record-ground`
re-records the #1416 Ground derivation) and `agr validate`. VPM `s_podz` stays empty as a delivered-project exception [D377].
Tests: `tests/jobs/test_kpp1_elements_plan_1609.py`.

VPM (sub-job `vpm/skeleton.json`, oks-vpm, no hooks; same delivery master; logs in the evidence folder):
```
"$B" -b --factory-startup --python jobs/KPP1/scripts/export_vpm.py -- PACKET/master-v004-delivery.blend V/pkg
# V/tex = the 24 PNG of the 8 UDIM tiles the master uses (1001 1006 1007 1009 1010 1012 1015 1018), make_textures.py
uv run agr package-vpm V/pkg V/tex --no-geojson --meta V/export_meta.json --deferred-note "GeoJSON deferred [D224]; ..."
uv run agr build-manifest record V/tex/*.png --master V/vpm_textures.json --role oks --source-id Kpp_1.oks.textures --out ...
uv run agr build-manifest build V/SM_Kpp_1.zip --master oks=PACKET/master-v004-delivery.blend --master oks=V/vpm_textures.json \
    --derivation V/derivation V/derivation-tex2 --transform-name "..." --blender "$B"
uv run agr validate V/SM_Kpp_1.zip --profile vpm --scene --json --export-meta V/export_meta.json --master oks=... --master oks=...
uv run agr validate V/SM_Kpp_1.zip --profile vpm --scene --json --export-meta V/export_meta.json --master PACKET/SM_Kpp_1.v004-lattice.fbx   # V003 master quads (DER-03)
```

### Package acceptance disposition (#1817)

Artem accepted the applicable manual gates [D382] on the 2026-11-24 package sheets
(`1609-kpp1-package-v004/draft-b25/sheets`): V015/V017 in NPM; V015/V016/V017 in VPM.
This does not turn an unmeasured automatic finding under V015 into a pass.

| Scope | Accepted disposition [D382] | Raw validation remains |
| --- | --- | --- |
| OKS V003 decor embed | Keep portals N01 (56 mm), N02/S01/S02/S03/S04 (nominal 6 mm) and strips Frame_N06/S05/W03 (116/116/153.6 mm). This is an exception to [D199] for KPP1 v004, not a change to the body or posts. | `review` on the work FBX |
| OKS V004 clearance and duplicates | Keep 0 pairs below 5 mm, 268 in band, 51,781 above 20 mm, and 41 duplicate vertices at NPM loose-part joints [D336]. No weld. | `review` |
| VPM V007 normal | Keep the procedural flat PNGs; the convention is undecidable on the reported sample. This is separate from ELV [D197]. | `review` |
| VPM V012 archive name | Keep `SM_Kpp_1`; the manual address/index review remains open. | `review` |
| NPM Ground V003/V004 | Carry only the [D313] skirt, topology (Flora 150,567 / GroundEl 63,537 / Ground 15,976) and clearance (406 pairs below 5 mm) findings to the byte-identical #1416 `package-v002` Ground FBX. | Three `fail` findings |

For readiness, classify the empty `s_podz` as `accepted_exception` [D377] only for the
delivered KPP1/ELV projects; do not request that field again. V011 is unchanged. The
v004 VPM ZIP contains **no** GeoJSON: V001 is `fail`, V011 is `not_run`, and V013 MSK-77
remains `not_run`. The V010 UCX coverage finding also remains `not_run` [D224]. Ground
footprint/hole coverage, Flora share and dimensions, V006 atlas padding and other
unlisted findings are not waived. The role-master and work-FBX runs are complementary
evidence; neither changes the other's raw findings.

Read-only replay for validation triage/readiness (no DCC and no packaging):

```bash
uv run python tests/jobs/kpp1_acceptance_1817_replay.py 'G:/Мой диск/AGR-evidence/1609-kpp1-package-v004/draft-b25-r1'
```

The replay verifies both ZIPs, the four saved validator reports and the copied Ground
member by SHA-256. It writes only to stdout and emits the original reports alongside
finding-level dispositions. Exit 0 means the overlay was read successfully; all four
original reports retain `passed=false` and their original exit codes. A different or
incomplete evidence bundle is refused; do not transfer these dispositions to a new export.
