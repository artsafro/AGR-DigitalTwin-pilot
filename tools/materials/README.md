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

Seeded Pillow/numpy diffuse maps for the ten Ground slots ([D117]), no external image inputs.

```text
uv run python tools/materials/ground_recipes.py deliver --version v002 --address Vatutino --out C:/x/vatutino-ground-textures/v002
```

NPM: 2048 at 30 px/m, repeat 68.266667 m; VPM: 4096 at 1024 px/m, repeat 4 m.
Density source: PR #308 `ground-build-v006.md`, still unmerged; recheck after #295 merges.
`nominal_tile_mm` is the sourced 100x300 mm face, `joint_mm` is a **provisional, user review**
5 mm physical joint, shared by both profiles. No artificial widened joints or pixel-scale overrides.
An integer tile count closes a periodic supertile with <=1% per-axis physical scale error, as authorized
by Artem on card t_47240e52 (2026-10-19). Manifest `physical_layout` records the nominal and actual face,
joint, counts, floating pixel periods and signed scale errors for each tile slot/profile. Pixel-area
integration averages subpixel joints; NPM cannot resolve every grain or joint independently.
`fraction_mm` drives Gravel pitch; subpixel grains become a periodic aggregate. Other unsourced
colours/cells remain explicit provisional review defaults in JSON and on the contact sheet.

Only `C:/x/vatutino-ground-textures/vNNN` (001..999), matching `--version`, is permitted. v002 is the
corrected delivery authorized on the card; v001 remains untouched. Nonempty folders, repository paths,
input aliases, malformed versions, incompatible physical scales and pixel-period overrides are refused.
Maps and the contact sheet are computed/validated before output creation. Use a new version, never overwrite.
PNG bytes are RGB uint8 with an sRGB chunk. Diffuse recipes are not a complete material/FBX delivery;
manual colour/appearance review and subsequent Ground binding remain separate gates.
