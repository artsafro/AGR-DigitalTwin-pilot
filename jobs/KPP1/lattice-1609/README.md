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
