# When to use a parametric-part tool

Rules below cite the rows in `RESULTS.md`. They do not change the MAF catalogue or the roof library.

1. Compare modelling time with `build_s`, and quote the Max session separately. On the bench build row, SolidCraft is 0.005197 s, Blender 0.0239359 s, Max 0.0722662 s. The Max process that produced all four Max meshes was 37.2 s; that is startup plus the four `build_s` values, not the bench build itself.

2. Accept a row only when FBX readback is ok: finite vertices, a non-empty triangle list, zero xView pairs at 2 mm and zero xView contact faces at 5 mm, and a finite dimension error. The six build rows and the three bench parameter rows all meet that. A SolidCraft `solid.box` fallback for the bench at 1900 mm did not (4 vertex pairs) and is not a result row.

3. Treat dimension error under 0.00005 mm on these rows as FBX numeric residue, not a modelling miss. SolidCraft's ASCII readback is 0 mm on the bench and on the aerator box. Max and Blender are 4.76837158203125e-05 mm on the bench and 1.430511474609375e-05 mm on the aerator revolve.

4. Do not treat the SolidCraft aerator row as the same part as the Max/Blender aerator. SolidCraft is a 12-triangle box of the 390 × 390 × 324 mm spec. Max and Blender are the 192-triangle stepped revolve. The shared number is the bbox error, not the shape. Use the bench rows (40 triangles vs 36, same silhouette, same bbox) when comparing the three tools.

5. A parameter change is usable when topology stays valid and the new bbox error stays at the same residue. The three bench rows (length +100 mm) do: SolidCraft 0.0013164 s, Blender 0.0050702 s, Max 0.0244939 s, all topology valid, triangle count unchanged, error 0 or 2.86102294921875e-05 mm.

6. SolidCraft is not marked "not adopted" on this sample. The bench build is faster than both Max (0.0722662 s) and Blender (0.0239359 s), and its dimension error (0 mm) is smaller than both (4.76837158203125e-05 mm). The same is true of the bench parameter row. That is the card's bar. It is not a production adoption: one run of two parts, the aerator comparison is a box against a revolve (rule 4), and `solid.box` can emit vertices that fail the 2 mm xView check (the discarded 1900 mm box). Library meshes stay on the Max/Blender recipe until a second sample repeats the bench result on a part that is not a bbox primitive.
