# KPP1 L03 plan contour: reproduce

How to rebuild `plan-contours.json` / `plan-account.json` from the customer DWG with two recorded
commands (#1203, KPP1 cold run F3, `jobs/KPP1/cold-run-1172/RUN-LOG.md` G4). The DWG is not in the
repository (rule 57); its path and SHA-256 are in `jobs/KPP1/cold-run-1172/inputs-manifest.json`.
Work only in `C:/x/kpp1/` (or a new versioned folder): both tools refuse to overwrite.

1. DWG -> DXF readback on a copy (AutoCAD 2025 `accoreconsole.exe /i <copy> /s <script>`, script
   `_.DXFOUT <path> _V _2018 16 _.QUIT _Y`). AutoCAD never opens the original; the receipt records the
   source, copy and DXF SHA-256. `--dry-run` prints the plan without AutoCAD.

```
uv run python tools/methods/body/dwg_to_dxf.py "C:/Users/artsafro/Downloads/22Е56-АР2-1002-АС.03-R1_L03_без подписей.dwg" C:/x/kpp1/dxf/L03.dxf C:/x/kpp1/L03.readback.json --workdir C:/x/kpp1
```

2. Extract (one line; the layer map is the committed `layer-map-L03.txt`):

```
uv run python tools/methods/body/plan_from_dxf.py extract C:/x/kpp1/dxf/L03.dxf C:/x/kpp1/plan-contours-v002.json C:/x/kpp1/plan-account-v002.json --map-file jobs/KPP1/cold-run-1172/layer-map-L03.txt --z0 0 --levels 0,3.9,7.909 --contour-source hatch --origin-mm 25884.5,0 --frame-shift-m=-14.655,-5.355
```

The output carries `invocation` (argv, `options_argv` with every map entry expanded, DXF and map-file
SHA-256, tool SHA-256 and git sha); `extract <dxf> <out> <report> *options_argv` re-runs it from the file
alone. `method` names the contour source (`plan wall hatch union ...` for `hatch`).

What the tool does not write and the accepted file carries by hand: `source` (sheet title, frame and
storey notes) and `opening_decision` (pass it with `--opening-decision`). The DXF bytes differ per
readback (header timestamps); the geometry and the entity account do not.

Run 2026-11-11 (#1203): readback `pass`, source = copy SHA-256 `ad1de2b2…4469` (before and after),
DXF 3 355 525 bytes; extract exit 0. Against the accepted `plan-contours.json`: `bands`, `levels_m`,
`method`, `openings`, `origin_mm`, `frame_shift_m`, `params` equal; `coverage` equal on every key the
accepted file has, plus the #1004 overshoot keys (`unaccounted_m2` 0.0) the current tool adds;
`plan-account.json` byte-identical (SHA-256 `72006144…0014`).
