# sources - variants (stub)

Clean input for the other classes. Status: **stub** - planned variants, nothing measured yet. Each entry gets idea, tool, inputs,
steps, script path and limits when it is built ([README](../README.md)); benchmarks: kpp1 (Revit), ac08 (DWG), tow02 (supplied FBX).

1. Revit -> FBX (RevitBridge `agr_export_fbx`), groups + sidecars.
2. DWG -> model (AutoCAD core console extract, `src/dt_ai/cad`).
3. Supplied-FBX repair (Blender: units, transforms, weld, normals, material slots).
