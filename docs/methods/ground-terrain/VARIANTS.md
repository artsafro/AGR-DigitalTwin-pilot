# ground-terrain - variants (stub)

Ground surface: relief, paving, kerbs, layered surface. Status: **stub** - planned variants, nothing measured yet. Each entry gets idea, tool, inputs,
steps, script path and limits when it is built ([README](../README.md)); benchmarks: vatutino-ground.

1. Our Ground builder (jobs/VATUTINO-SITE/build_ground.py, method C layers).
2. External mesher (constrained Delaunay on the plan, then height projection).
3. Blender geometry nodes: grid + projection onto the relief.
