# MAF library catalogue (issue #183)

Audit of the user's single 3ds Max MAF library scene, turned into one `.max` + one FBX + one preview PNG per MAF.
Binaries stay **outside the repo** (`C:/x/t_3e6ff1b3/library/{max,fbx,preview}`, contact sheet
`C:/x/t_3e6ff1b3/library/contact_sheet.png`); PNG/FBX/MAX are Git LFS types and the LFS budget is exhausted.
This folder holds only text: `catalogue.json` (every entry, paths to its files) and `catalogue.md` (table).
Status: technical audit only, not identification (T-MAF-1) and not user acceptance.

## Inputs (read only, worked on copies)

| Input | sha256 before = after |
|---|---|
| `МАФы_Union_ALLin.max` (319.5 MB, 3ds Max scene, metres) | `beeef9d418e81045bbc4933cc74077acd3d9f7a265319ceb9bf0ff0253050109` |
| `МАФЫ_НПМ.blend` (54.8 MB, NPM set, Blender 5.1.2) | `52ef2222b13a7cb4f4c3b728ee27e827cfaeb49499f3e7d7d03a5f7364d661dd` |
| `maf_spec_vedomost_3.xlsx` (MAF specification sheet, copy) | `9b4302c16501636fe4a522f54ff16091244ba0b6f20378763b2706d51f1eb2b3` |

## How it was built

```bash
# pass A: inventory + mesh elements of every object (headless 3ds Max 2026, copy of the scene)
AGR_MAF_SCENE=C:/x/t_3e6ff1b3/src.max AGR_MAF_OUT=C:/x/t_3e6ff1b3/elements.json \
  python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --file tools/library/maf_max_elements_job.py
# plan: one entry per spatial cluster of elements (gap 0.5 m) -> MAF_0001..
uv run python tools/library/maf_catalogue.py plan --elements elements.json --out plan.json --gap 0.5
# pass B: per entry .max (saveNodes) + FBX (selected) + Scanline preview; resumable (skips ok rows)
AGR_MAF_PLAN=plan.json AGR_MAF_LIB=C:/x/t_3e6ff1b3/library \
  python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --file tools/library/maf_max_build_job.py --timeout 3000
# catalogue: + NPM .blend matching, specification dimension candidates, duplicates, overlaps, contact sheet
uv run --with openpyxl python tools/library/maf_catalogue.py catalogue --plan plan.json --built library/built.jsonl \
  --blend blend_inventory.json --spec maf_spec_vedomost_3.xlsx --out-json catalogue.json --out-md catalogue.md \
  --contact-sheet library/contact_sheet.png
```

Rules used: an object whose mesh elements form several clusters farther apart than 0.5 m (Chebyshev gap between
element boxes) is a cluster of several MAF and is split; objects ≤ 12 tris and < 5 mm tall are helper planes;
text/shapes/dummies are non-geometry. Duplicates = equal tris and dims within 1 cm (X/Y swap allowed). NPM matching:
name (prefix `C_`/`crp_` and `.NNN` removed) plus dims within 10 cm, else dims only. Specification candidates are
dimension-only (tolerance 10 cm, user grilling Q8) — candidates, not identification.

`element_first_faces` (needed to rebuild a split) is kept in `plan.json` outside the repo and dropped here.
