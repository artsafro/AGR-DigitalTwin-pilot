# MAF atlas (512)

Builds one shared texture for NPM GroundEl (МАФ). Regulation: one texture set, at most 512×512 px, and at least 8 px between neighbouring islands that carry different images.

The tool does not assign UVs on a mesh. Ground and Flora atlases are out of scope.

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

`atlas_size` and `padding_px` are optional (defaults 512 and 8).

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

`padding_px` must be an even integer ≥ 0 and smaller than the smallest slot.

If the minimum area exceeds the atlas, the tool stops and reports the overflow in 64×64 cells and what to shrink: solids requested at 128 (dropping to 64 frees 3 cells), patterned slots above 128 (halve them), or otherwise which materials to remove or merge (for example solids that share a colour).

## Outputs

- PNG: RGB, `atlas_size` × `atlas_size`.
- JSON: `atlas_size`, `padding_px`, `v_origin` = `"bottom"`, and per material `kind`, `slot_px` `[x, y, size, size]`, `content_px` `[cx, cy, cw, ch]` (top-left origin), and `uv` `[u0, v0, u1, v1]`.

V is 0 at the bottom of the image (FBX / Blender / 3ds Max).

## CLI

```text
uv run python tools/materials/atlas_maf.py materials.json --out-png atlas.png --out-json atlas.json
```

Add `--force` to replace an existing output. On success the process prints one summary line and exits 0. On a bad list, a list that does not fit, or a refused overwrite, it prints `error: ...` to stderr and exits 2.

## Limits

- One atlas, default 512×512. `atlas_size` may be another power of two ≥ 64; delivery for GroundEl stays at 512.
- The list must fit by minimum area. The error names the materials to shrink; it does not drop them automatically.
- Patterned sources are resampled. The tool does not preserve their pixel size or generate mip maps.
- UV rectangles are written to JSON only. They are not applied to a model.
