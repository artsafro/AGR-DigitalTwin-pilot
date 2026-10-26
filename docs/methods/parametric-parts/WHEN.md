# When to use a parametric-part tool

Rules below cite the rows in `RESULTS.md`. They do not change the MAF catalogue or the roof library.

1. Time every tool on one boundary: build + FBX export. SolidCraft does not export FBX, so its boundary also includes OBJ export and the OBJ→FBX conversion. The parameter-change rows use that same boundary (the edit, then export, and the conversion when the tool needs it). Quote the Max session separately. The session that wrote the four Max meshes was 35.6 s. That is startup plus the four `build_s` values, not a bench build.

2. Accept a row only when FBX readback is ok: a Model connected to Geometry, finite vertices, a closed polygon list, zero xView pairs at 2 mm and zero xView contact faces at 5 mm, a finite dimension error, and a fresh DCC import with at least one object and the same triangle count. The twelve rows meet that. A file Max imports as zero objects is not a row, even when a parser can see a vertex array.

3. Treat dimension error under 0.00005 mm on these rows as FBX numeric residue, not a modelling miss. Every build and parameter row is inside that band. No tool is ahead on dimension error.

4. Compare the aerator rows as the same part. Flange radius 0.195 m, pipe radius 0.05 m, cap radius 0.09 m, heights 0.064 / 0.110 / 0.150 m. SolidCraft is 188 triangles, Max and Blender 192. The difference is triangulation of the same stepped solid. The bench rows are the same silhouette (40 triangles vs 36) inside the catalogue box.

5. A parameter change is usable when topology stays valid, the triangle count stays the same, and the new bbox error stays at the residue. All six parameter rows do.

6. Adoption: not adopted. On the bench build, SolidCraft is 0.8411376000149176 s, Blender 0.022990999976173043 s, Max 0.062177599989809096 s. On the aerator build, SolidCraft is 1.072084499988705 s, Blender 0.005639799986965954 s, Max 0.04162400000495836 s. The parameter rows have the same order. SolidCraft does not beat Max or Blender on time, and the dimension errors are the same residue. The earlier speed claim used a timer that stopped before export.
