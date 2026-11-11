-- SYNTHETIC Q10 test: re-import raw.fbx / baked.fbx in a fresh headless Max and dump world transforms.
-- Pattern: new-case (standalone synthetic Link Info/FBX experiment).
-- Run only headless: 3dsmaxbatch.exe reimport_max.ms   (second reader next to Blender)
Q10_OUT = @"C:\x\link-info-test-2026-11\"

fn fnum v = formattedPrint (v as float) format:".10g"
fn f3 p = "[" + (fnum p.x) + "," + (fnum p.y) + "," + (fnum p.z) + "]"
fn tmStr t = "[" + (f3 t.row1) + "," + (f3 t.row2) + "," + (f3 t.row3) + "," + (f3 t.row4) + "]"
fn bitsStr b = (s = "["; for i = 1 to 9 do (s += (if b[i] then "1" else "0"); if i < 9 do s += ","); s + "]")
fn worldVerts n = (
    local m = snapshotAsMesh n
    local s = "["
    for i = 1 to m.numverts do (s += f3 (getVert m i); if i < m.numverts do s += ",")
    s + "]"
)
fn nodeJson n = (
    "{\"name\":\"" + n.name + "\",\"parent\":" + (if n.parent == undefined then "null" else ("\"" + n.parent.name + "\"")) + \
    ",\"inherit\":" + (bitsStr (getInheritanceFlags n)) + ",\"transform\":" + (tmStr n.transform) + \
    ",\"world_verts\":" + (worldVerts n) + "}"
)
fn importDump variant = (
    resetMaxFile #noPrompt
    units.SystemType = #meters
    units.SystemScale = 1.0
    FBXImporterSetParam "ResetImport"
    FBXImporterSetParam "ConvertUnit" "m"
    FBXImporterSetParam "Animation" false
    importFile (Q10_OUT + variant + ".fbx") #noPrompt using:FBXIMP
    local nodes = for o in geometry collect o
    local f = createFile (Q10_OUT + "maxreimport_" + variant + ".json")
    format "{\"variant\":\"%\",\"nodes\":[" variant to:f
    for i = 1 to nodes.count do (format "%" (nodeJson nodes[i]) to:f; if i < nodes.count do format "," to:f)
    format "]}\n" to:f
    close f
)
pluginManager.loadClass FBXIMP
importDump "raw"
importDump "baked"
format "DONE reimport_max\n"
