# texturing-by-drawings - variants (stub)

UV and textures from the drawings, then UDIM -> atlas. Status: **stub** - planned variants, nothing measured yet. Each entry gets idea, tool, inputs,
steps, script path and limits when it is built ([README](../README.md)); benchmarks: kpp1, ac08 (reference renders for SSIM), tow02, vatutino-ground.

1. Unique unwrap per facade (UDIM tiles from the drawing sheets), then bake to atlas.
2. Trim sheet: shared strips (plaster, brick, trims) mapped by face class.
3. Procedural joints: tile / panel joints generated from the drawing grid, baked.
