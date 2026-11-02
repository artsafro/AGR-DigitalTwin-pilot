# MAF atlas (512)

Builds one shared texture for NPM GroundEl (МАФ).

## Pattern / scope

Per [docs/agents/REVIEW_CHECKLIST.md](../../docs/agents/REVIEW_CHECKLIST.md) Q1, this tool is an explicit new-case: shared NPM GroundEl atlas packing with buddy allocator and patterned growth, not a registered/proven pattern (registry [docs/domain/patterns/INDEX.md](../../docs/domain/patterns/INDEX.md)).

The tool does not assign UVs on a mesh. Ground and Flora atlases are out of scope.

## Normative references vs algorithm choices

Normative requirements from [docs/domain/uv-textures.md](../../docs/domain/uv-textures.md):
- reg p.10 §5.12: GroundEl uses one texture set for all elements, <= 512×512 px.
- reg p.9 §5.4: Padding >= 8 px between neighbouring islands with unique images.
- reg p.9 §5.1: Textures delivered as PNG (embedded in FBX).
- reg p.9 §5.5: Alpha channel forbidden in NPM textures.

Algorithm choices (implementation design, not regulation):
- Quadtree buddy allocator for power-of-two square slots (largest slots placed first).
- Patterned growth strategy: doubling the smallest patterned slot iteratively to utilize leftover atlas area.
- Content rect insetting by `padding_px / 2` with border pixel duplication to avoid bilinear bleed, and RGB (128, 128, 128) neutral background.

## Input

JSON file:

```json
{
  "atlas_size": 512,
  "padding_px": 8,
  "materials": [
    {"name": "post", "kind": "solid", "color": "RAL 9005", "size": 128},
    {"name": "plaster", "kind": "solid", "color": "#E8E4DA"},
    {"name": "paving", "kind": "patterned", "texture": "paving.png", "size": 128}
  ]
}
```

`atlas_size` and `padding_px` are optional (defaults 512 and 8). If `atlas_size` is present it must be exactly 512. `padding_px` must be an even integer ≥ 8 and smaller than the smallest slot.

Each material:

| Field | Required | Meaning |
|---|---|---|
| `name` | yes | Unique. Latin letters, digits, `_`, `-` only. |
| `kind` | yes | `solid` or `patterned`. |
| `color` | solids | `#RRGGBB` or `RAL 9005` / `RAL9005`. Unknown RAL codes must be replaced with a hex value. |
| `texture` | patterned | PNG (or any Pillow image). Relative paths are resolved from the JSON file's folder. |
| `size` | no | Solid: 64 (default) or 128. Patterned: minimum slot, power of two, at least 128 (default 128). |

RAL Classic values in `ral_classic.json` are screen approximations, not measured paint matches.
`7047` is `#D0D0D0`. This reuses the project's recorded display approximation from #320, not an official or spectrophotometric RAL match or new visual approval.

## Packing

Every material gets a square power-of-two slot. A quadtree buddy allocator places the largest slots first (equal sizes keep input order). Solids stay at 64 or 128. After the minimum layout fits, patterned slots grow: repeatedly double the currently smallest patterned slot when the new set still fits in the atlas. A slot never grows past `atlas_size`.

Inside each slot the content rect is inset by `padding_px / 2` on every side, so neighbouring content is at least `padding_px` apart. Solids fill the whole slot, including that gutter. Patterned images are resized with Lanczos into the content rect, then edge pixels are repeated out to the slot border so bilinear sampling does not pick up a neighbour. Unused pixels are RGB (128, 128, 128).

`padding_px` must be an even integer ≥ 8 and smaller than the smallest slot.

If the minimum area exceeds the atlas, the tool stops and reports the overflow in 64×64 cells and what to shrink: solids requested at 128 (dropping to 64 frees 3 cells), patterned slots above 128 (halve them), or otherwise which materials to remove or merge (for example solids that share a colour).

## Outputs

- PNG: RGB, 512 × 512.
- JSON: `atlas_size` (512), `padding_px`, `v_origin` = `"bottom"`, and per material `kind`, `slot_px` `[x, y, size, size]`, `content_px` `[cx, cy, cw, ch]` (top-left origin), and `uv` `[u0, v0, u1, v1]`.

The two output paths must name different files. Neither may be the material-list JSON or a patterned source texture, including after `..` is collapsed and, on Windows, a case-only difference. `--force` replaces a previous atlas or UV file; it does not allow those inputs to be overwritten.

V is 0 at the bottom of the image (FBX / Blender / 3ds Max).

## CLI

```text
uv run python tools/materials/atlas_maf.py materials.json --out-png atlas.png --out-json atlas.json
```

Add `--force` to replace an existing output. On success the process prints one summary line and exits 0. On a bad list, a list that does not fit, an `atlas_size` other than 512, a `padding_px` below 8, a refused overwrite, or an output path that aliases the other output or an input, it prints `error: ...` to stderr and exits 2. A rejected run does not create the output files or their missing parent directories.

## Limits

- One atlas, always 512×512. `padding_px` is an even integer ≥ 8.
- The list must fit by minimum area. The error names the materials to shrink; it does not drop them automatically.
- Patterned sources are resampled. The tool does not preserve their pixel size or generate mip maps.
- UV rectangles are written to JSON only. They are not applied to a model.

## Ground recipes (Vatutino)

Seeded Pillow/numpy diffuse maps for the twelve Ground slots ([D117]), no external image inputs.
CurbGarden and Stairs use the same provisional provenance rules as the other slots.

```text
uv run python tools/materials/ground_recipes.py deliver --version v003 --address Vatutino --out C:/x/vatutino-ground-textures/v003
```

NPM: 2048 at 30 px/m, repeat 68.266667 m; VPM: 4096 at 1024 px/m, repeat 4 m.
Density source: #295 / merged PR #308 (`5eb945a`), v014 FBX; the binding tool measures
exported per-face density again rather than trusting the recipe's nominal value.
`nominal_tile_mm` is the sourced 100x300 mm face, `joint_mm` is a **provisional, user review**
5 mm physical joint, shared by both profiles. No artificial widened joints or pixel-scale overrides.
An integer tile count closes a periodic supertile with <=1% per-axis physical scale error, as authorized
by Artem on card t_47240e52 (2026-10-19). Manifest `physical_layout` records the nominal and actual face,
joint, counts, floating pixel periods and signed scale errors for each tile slot/profile. Pixel-area
integration averages subpixel joints; NPM cannot resolve every grain or joint independently.
`fraction_mm` drives Gravel pitch; subpixel grains become a periodic aggregate. Other unsourced
colours/cells remain explicit provisional review defaults in JSON and on the contact sheet.

Only `C:/x/vatutino-ground-textures/vNNN` (001..999), matching `--version`, is permitted. v003 is the
delivery that adds CurbGarden and Stairs; v001 and v002 remain untouched. Nonempty folders, repository paths,
input aliases, malformed versions, incompatible physical scales and pixel-period overrides are refused.
Maps and the contact sheet are computed/validated before output creation. Use a new version, never overwrite.
PNG bytes are RGB uint8 with an sRGB chunk. Diffuse recipes are not a complete material/FBX delivery;
manual colour/appearance review and subsequent Ground binding remain separate gates.

## Ground binding (#340)

`bind_ground_textures.py plan` reads `--npm-readback`, `--vpm-readback`, `--manifest`,
`--textures` and writes `--out` JSON. `bind` additionally requires `--npm-fbx` and
`--vpm-fbx`; its output root is `C:/x/vatutino-ground-textured/v001` and must be empty.
The v003 manifest supplies the filename/hash table; no map is selected by judgement.
Wrong names, missing/hash-mismatched maps, wrong dimensions/UDIM tiles, duplicate or
incomplete inventories and input/output aliases fail before export. Existing output
versions and v001/v002 source textures are never overwritten.

The companion Blender 5.1.2 headless script works on copies. Separate clean imports
compare ordered vertices, UVs, topology, imported face material IDs and raw FBX
`LayerElementMaterial`, then read every Base Color socket with `fbx_readback.py`.
Materialless UCX in the final #295 VPM is preserved and checked separately, not bound
or included in relief density. Skirt density is reported but exempt from the relief
band (GND-03/08). A failed export/readback removes its partial FBX.

Actual commands, source/output hashes, all-slot tables and pending delivery gates:
[`ground-textures.md`](../../jobs/VATUTINO-SITE/ground-textures.md). Technical binding
verification is not visual acceptance, SINTEZ acceptance or delivery-package approval.

## NPM atlas from a UDIM mesh (#546)

`npm_atlas_udim.py` collapses a VPM-shaped UDIM / Multi-Sub mesh into one NPM atlas. It re-implements the logic of
the team script `VPM_to_NPM.ms` (latest of 2 versions, 706 lines, Drive `AGR-evidence/Scripts from Telegram/`; audit
`docs/research/team-scripts-audit.md`). No MAXScript is copied. The data is synthetic in the tests.

```text
uv run python tools/materials/npm_atlas_udim.py ground.obj --out-dir out/npm-v001 [--size 1024] [--mode oks] [--overlay uv.png]
```

Input: OBJ + MTL, one `usemtl` per material (= Multi/Sub ID = one UDIM tile); `map_Kd` may hold `<UDIM>`; a material
with only `Kd` is a flat plug; optional `map_d` is a grey opacity map; `d` (or `1 - Tr`) multiplies the opacity.
The MTL reader is fail-closed: any map option (`-s`, `-o`, `-clamp`, ...), any other map (`map_Ks`, `bump`, `norm`,
...), PBR or unknown directive, a non-neutral `Ke` / `Tf`, `d` outside 0..1 or `d` disagreeing with `Tr` is an
error naming the material and directive (exit 2, nothing written). `Ka`, `Ks`, `Ns`, `Ni`, `illum`, neutral `Ke` /
`Tf` and a `Kd` tint under `map_Kd` (3ds Max convention: the map replaces `Kd`) are listed per material in the
report `ignored_mtl` with the reason. FBX is refused (export OBJ first); in Python,
pass a `UdimMesh` + `MaterialSource` map to `pack()`. Output (new files; an existing file or a path that resolves to
an input is an error, exit 2, nothing written): `<base>_d.png` RGB, `<base>_o.png` L (only if some material is
transparent), `<base>.obj` / `<base>.mtl` (same vertices and faces, one material, remapped UV), `<base>_report.json`.
A measured failure (padding, UV outside the cell, Ground texel outside 10-40 px/m) exits 1 and writes nothing; after
writing, the files are read back and measured again.

### Algorithm notes (script line ranges)

| Step | `VPM_to_NPM.ms` | Pilot implementation |
|---|---|---|
| Defaults: atlas 2048, target 35 px/m, plug 12.5 px/m, band 10..40, pad 6, plug <= 512 px, plug cell 16 | 30-38 | same defaults except pad: `--padding` default and minimum 8 (`island_padding_px_min`) |
| Per ID: UV bbox, per-face texel `sqrt(uv area / geo area) x W`, UV vertices shared by two IDs counted | 109-149 | `analyze()`: directional metric instead of the area one - per fan triangle the singular values of the metre -> pixel Jacobian (px per linear metre along the least / most stretched direction); a shared UV vertex is an error naming both materials |
| Tile of the ID = floor of the bbox centre | 165-166 | same; an island that crosses its tile border is an error (script: tile wrap) |
| Plug test: no bitmap or `W <= 512` | 167 | pilot rule: only a one-colour map (or `Kd` only) is a plug; a small patterned map stays a texture cell |
| Ground scale `k = clamp(T / median, 10 x 1.03 / min, 40 x 0.97 / max)`; spread too wide -> geometric mean + warning | 194-205 | same clamp on directional bounds (`10 x 1.03 / min sigma_min`, `40 x 0.97 / max sigma_max`, median of `sqrt(sigma_min sigma_max)`); spread or anisotropy too wide is an error naming the material (no warning-and-continue) |
| Crop rect = bbox + `ceil(pad / k) + 1` source px of tile continuation; cell = crop x k, rounded | 207-230 | cell = island x k + 2 x (pad + 1) px, crop is the exact inverse (uniform `k`, no rounding stretch); tile-wrapped source |
| Shelf pack, plugs first, then by height | 233-264 | shelf pack of all cells by height, name as tie-break |
| Ground: lower T by x0.96 from 35 until it fits (stop at 10 x 1.05); OKS: scale 1 or bisect 24 steps | 266-308 | same search; no fit is an error naming the materials |
| Crop + halving downscale (bicubic) | 331-369 | Lanczos `resize` with a fractional box |
| Diffuse without alpha; opacity = alpha as grey, written only if some map has alpha | 413-445 | RGB PNG; L PNG `_o` only if a material has alpha < 255 or a `map_d` |
| UV: one affine per ID (shift + scale) | 451-481 | same; textured faces keep shared UV vertices |
| Ground plugs: each polygon scaled about its centre to the plug texel | 482-527 | each Ground plug face is laid flat in its own plane at exactly the plug texel in every direction (flat colour: the source UV shape carries nothing); own UV vertices; OKS plugs fit a 16 px interior |
| Verify texel per polygon and UV outside 0..1 | 533-562 | `measure()` / `readback()`: directional min / max per material, plus UV inside its cell, padding to the cell edge, island gap, read back from the written files |
| Copy `<name>_NPM`, one material, all IDs -> 1 | 582-626 | new OBJ + MTL with one material; the source files are never written |

### Where the pilot differs from the script

- Padding: script 6 px (`:35`); pilot >= 8 px from every island to its cell edge (reg p.9 §5.4), so two islands are
  >= 16 px apart.
- Plugs: script `W <= 512` (`:12`, `:36`, `:167`) shrinks every small map to a flat plug. Pilot: a 128x128 one-colour
  placeholder exists only for flat Metallic/Roughness maps (reg p.3-4, conflict #5); this tool writes no MR maps, so a
  diffuse becomes a plug cell only when it is one colour, and a small patterned map keeps its pattern.
- Texel spread that cannot fit 10..40 with one scale, a shared UV vertex, a tile-crossing island and a non-fitting
  pack are errors, not report warnings.
- Texel density: the script's `sqrt(uv area / geo area)` is the geometric mean of the two directions, so a
  0.1 x 10 m quad with a square UV reads 35 px/m while its directions are 350 and 3.5 px/m. The pilot plans and
  verifies the directional extremes (both must be inside 10..40) and refuses such a material; a rotated or tilted
  isotropic mapping still reads exactly 35 / 35.
- MTL: the script reads 3ds Max materials directly; the OBJ path here refuses what it cannot carry (see Input).
