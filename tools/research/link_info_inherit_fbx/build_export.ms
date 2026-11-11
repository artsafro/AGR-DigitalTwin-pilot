-- SYNTHETIC test scene for backlog Q10 (Link Info «Inherit» -> FBX). Not a real object.
-- Pattern: new-case (standalone synthetic Link Info/FBX experiment).
-- Run only headless: 3dsmaxbatch.exe build_export.ms   (outputs outside the repo)
-- Writes <Q10_OUT>raw.fbx, baked.fbx, *.max and max_raw.json / max_baked.json (world transforms and world vertices).
Q10_OUT = @"C:\x\link-info-test-2026-11\"
makeDir Q10_OUT all:true

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
    local t = n.transform
    local e = (t.rotationpart as eulerAngles)
    "{\"name\":\"" + n.name + "\",\"parent\":" + (if n.parent == undefined then "null" else ("\"" + n.parent.name + "\"")) + \
    ",\"inherit\":" + (bitsStr (getInheritanceFlags n)) + ",\"transform\":" + (tmStr t) + \
    ",\"pos\":" + (f3 t.translationpart) + ",\"euler_deg\":" + (f3 [e.x, e.y, e.z]) + ",\"scale\":" + (f3 t.scalepart) + \
    ",\"world_verts\":" + (worldVerts n) + "}"
)
fn dumpScene nodes path extra = (
    local f = createFile path
    format "{%,\"nodes\":[" extra to:f
    for i = 1 to nodes.count do (format "%" (nodeJson nodes[i]) to:f; if i < nodes.count do format "," to:f)
    format "]}\n" to:f
    close f
)
fn exportFbx path = (
    FBXExporterSetParam "ResetExport"
    FBXExporterSetParam "FileVersion" "FBX201400"
    FBXExporterSetParam "ASCII" false
    FBXExporterSetParam "Animation" false
    FBXExporterSetParam "ConvertUnit" "m"
    FBXExporterSetParam "UpAxis" "Y"
    FBXExporterSetParam "Triangulate" false
    FBXExporterSetParam "EmbedTextures" false
    FBXExporterSetParam "Cameras" false
    FBXExporterSetParam "Lights" false
    exportFile path #noPrompt using:FBXEXP
)

resetMaxFile #noPrompt
units.SystemType = #meters
units.SystemScale = 1.0
units.DisplayType = #metric
units.MetricType = #meters
pluginManager.loadClass FBXEXP

P  = Box name:"P_synthetic"  length:2.0 width:3.0 height:4.0 pos:[0,0,0]
C1 = Box name:"C1_inherit_all" length:1.0 width:1.5 height:2.0 pos:[5,0,0]
C2 = Box name:"C2_no_rot"      length:1.0 width:1.5 height:2.0 pos:[0,5,0]
C3 = Box name:"C3_no_scale"    length:1.0 width:1.5 height:2.0 pos:[5,5,0]
C4 = Box name:"C4_no_posX"     length:1.0 width:1.5 height:2.0 pos:[-5,2,1]
kids = #(C1, C2, C3, C4)
for c in kids do c.parent = P
-- bits 1-3 move XYZ, 4-6 rotate XYZ, 7-9 scale XYZ (Hierarchy > Link Info > Inherit)
setInheritanceFlags C2 #{1,2,3,7,8,9} keepPos:false
setInheritanceFlags C3 #{1,2,3,4,5,6} keepPos:false
setInheritanceFlags C4 #{2,3,4,5,6,7,8,9} keepPos:false
-- parent transform AFTER linking: non-uniform scale, 30 deg about Z, translate
P.transform = (scaleMatrix [2.0, 1.0, 0.5]) * (rotateZMatrix 30.0) * (transMatrix [10.0, 20.0, 3.0])

allNodes = #(P, C1, C2, C3, C4)
saveMaxFile (Q10_OUT + "raw.max") quiet:true
exportFbx (Q10_OUT + "raw.fbx")
fbxVer = FBXExporterGetParam "FileVersion"
dumpScene allNodes (Q10_OUT + "max_raw.json") ("\"variant\":\"raw\",\"max_version\":\"" + ((maxVersion())[1] as string) + "/" + ((maxVersion())[8] as string) + "\",\"product\":\"" + (getFileVersion (getDir #maxroot + "3dsmax.exe")) + "\",\"fbx_file_version\":\"" + (fbxVer as string) + "\",\"fbx_plugin\":\"" + (try (FBXExporterGetParam "FBXExporterVersion" as string) catch "?") + "\",\"system_units\":\"" + (units.SystemType as string) + "\"")

-- bake: keep the world transform, unlink, inherit all, Reset XForm, collapse
for c in kids do (
    local tm = c.transform
    c.parent = undefined
    setInheritanceFlags c #all keepPos:true
    c.transform = tm
    ResetXForm c
    collapseStack c
)
saveMaxFile (Q10_OUT + "baked.max") quiet:true
exportFbx (Q10_OUT + "baked.fbx")
dumpScene allNodes (Q10_OUT + "max_baked.json") "\"variant\":\"baked\""
format "DONE build_export\n"
