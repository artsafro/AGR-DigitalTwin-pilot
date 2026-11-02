# building-body - variants (stub)

OKS body mesh from the sources (walls, slabs, roof, projections, decor). Status: **stub** - planned variants, nothing measured yet. Each entry gets idea, tool, inputs,
steps, script path and limits when it is built ([README](../README.md)); benchmarks: kpp1, ac08, tow02.

1. Revit export clean-up (Revit -> FBX, then weld / merge / triangulate in Blender bpy): keeps the BIM geometry; needs a Revit model.
2. Our kernel from drawings (`src/dt_ai/parts`, contours + levels): body from DWG plan contours and section heights.
3. 3ds Max / pymxs edit-poly rebuild on a supplied FBX: manual-assisted remodel of a supplied mesh.
4. Blender geometry nodes from level contours: extrude per level, boolean openings.
