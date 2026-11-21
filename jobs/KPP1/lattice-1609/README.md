# KPP1 lattice restart, step 1: line list for W/S/N (#1609)

Artem 2026-11-21 («принимаю рекомендации», docs/research/body-mesh-method.md §6): the body is built only from
the lattice (BM-00). Ground-floor and band lines come from the Revit/DWG openings and zones list, snapped at 10 cm,
never from mesh vertices. A line stays if the cell class changes along it over >= 1.5 m or >= the opening width.
**Step 1 only:** the line list and one ground-floor sheet. The body is built after Artem's «ок».

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
uv run python jobs/KPP1/lattice-1609/line_list.py $C/openings_spec.json $C/walls_ext.objects.json OUT/line_list.json --bands jobs/KPP1/lattice-1609/finish_bands.json
"$B" -b --factory-startup --python docs/research/body-modelling-1618/dump_mesh.py -- kpp1_r1_v003.fbx OUT/dump
"$B" -b --factory-startup --python docs/research/body-modelling-1618/dump_mesh.py -- run-r1-v003/export/fbx/0000_Kpp_1_01.fbx OUT/dumpnpm
uv run python jobs/KPP1/lattice-1609/render_lines.py OUT/line_list.json OUT/dumpnpm/SM_Kpp_1_001_Main.npz OUT/dump/SM_Kpp_1_Main.npz run-r1-v003/atlas/T_Kpp_1_001_Main_d_1.png OUT/kpp1-lattice-lines-ground.png --check OUT/hole_check.json
```
Tests: `tests/jobs/test_kpp1_line_list_1609.py`.

## Step 2: lattice body with closed rings (Artem 2026-11-21: lines accepted; every level a closed ring)

The rule is «луп и ринг должен быть логичный, без прерваний на другой стороне фасада». So facade E is in the line
list now (`FACADES = W, S, N, E`). Its 3 Revit doors add stations, and the E door at z 3.9–6.0 adds 2 global rings.
#1736 core is not on main, so the body is built with the #1742 prototype `proto_lattice.py`. Its new `--lines` input
takes the stations, levels and openings from the list. Every opening cell sits at plane + 0.25 reveal. Every other
cell keeps the R1 v003 depth (clustered at 3 cm, rounded to 1 cm). A cell where R1 has no surface within 3.5 m is
a hole the list lacks (glazed side lights at the entrances), so it is treated as an opening.

- `lattice_input.py`: line list → one ring lattice (perimeter s, S→E→N→W, `--shift` into the R1 frame).
- `lattice_check.py`: per level closed yes/no, per station through yes/no, defects per lattice cell (local signal).
- `render_lattice.py`: unrolled S | E | N | W straight elevations, before/after, rings and cells marked.

Reproduce (outputs `C:/x/ev_1609/s7`, evidence `G:/Мой диск/AGR-evidence/1609-kpp1-lattice-body/step2/`):
```
uv run python jobs/KPP1/lattice-1609/line_list.py $C/openings_spec.json $C/walls_ext.objects.json O/line_list.json --bands jobs/KPP1/lattice-1609/finish_bands.json
uv run python jobs/KPP1/lattice-1609/lattice_input.py O/line_list.json O/lattice_r1.json --shift -14.655 -5.355
"$B" -b --factory-startup --python docs/research/body-mesh-method/proto_lattice.py -- kpp1_r1_v003.fbx O/p6 --objects SM_Kpp_1_Main --lines O/lattice_r1.json --zmin 0 --zmax 8.65
"$B" -b --factory-startup --python docs/research/body-modelling-1618/dump_mesh.py -- O/p6/proto.fbx O/d6
uv run python jobs/KPP1/lattice-1609/lattice_check.py O/d6/SM_Proto_Body.npz O/lattice_r1.json O/qa/check_p6.json
uv run python jobs/KPP1/lattice-1609/render_lattice.py O/lattice_r1.json OUT.png --model LABEL NPZ CHECK.json ...
```
Tests: `tests/jobs/test_kpp1_lattice_body_1609.py`, `tests/jobs/test_kpp1_line_list_1609.py`.
