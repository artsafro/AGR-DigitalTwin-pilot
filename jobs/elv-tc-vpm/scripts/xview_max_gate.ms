-- elv-tc-vpm final overlap gate [D177/D178]: native 3ds Max xView on the delivered FBX.
-- Job-local variant of tools/qa/xview_dump.ms (same checker calls, weld and tolerances), but imports the FBX
-- ONCE and checks every target node in that one scene (Main, MainGlass and each UCX_* separately);
-- xview_dump.ms re-imports per job, which is impractical for ~960 UCX nodes.
-- Run: 3dsmaxbatch (dcc_batch.py max --version 2024 --file <this>) with env
--   ELV_XV_FBX = ASCII path of the FBX copy, ELV_XV_OUT = existing ASCII output dir (no results.json/done.txt yet).
-- Per node: convertToMesh, weld all vertices at units.decodeValue "2mm" (no Poly round trip), then
-- xView Overlapping Vertices (2 mm) and Overlapping Faces (5 mm) on the Editable Mesh.
-- Writes <out>/results.jsonl (one line per node), <out>/summary.json and <out>/done.txt. Never saves the scene.
(
  local fbx = systemTools.getEnvVariable "ELV_XV_FBX"
  local outp = systemTools.getEnvVariable "ELV_XV_OUT"
  local m = 1.0 / (units.decodeValue "1m")   -- system units -> metres
  fn num x = formattedPrint x format:".7g"
  fn p3m p = "[" + (num (p.x * m)) + "," + (num (p.y * m)) + "," + (num (p.z * m)) + "]"
  fn q s = "\"" + (substituteString (substituteString (s as string) "\\" "/") "\"" "'") + "\""
  fn runChecker node idx = (
    xViewChecker.activeIndex = idx
    xViewChecker.on = true
    xViewChecker.runCheck currentTime
    local rv = xViewChecker.getCurrentReturnVal()
    local cnt = xViewChecker.getCurrentOutputCount()
    if rv == #Failed then (xViewChecker.on = false; throw ("checker failed: " + xViewChecker.getCheckerName idx))
    local items = ""
    local k = 0
    if cnt > 0 then (
      xViewChecker.selectResults currentTime
      if rv == #Faces then (
        for f in (getFaceSelection node) do (
          local c = in coordsys world (meshop.getFaceCenter node f node:node)
          local vv = getFace node f
          local vs = ""
          for i = 1 to 3 do vs += (if i > 1 then "," else "") + (p3m (in coordsys world (getVert node vv[i])))
          items += (if k > 0 then "," else "") + "{\"face\":" + (f as string) + ",\"mat\":" + ((getFaceMatID node f) as string) + \
            ",\"area_m2\":" + (num ((meshop.getFaceArea node #{f}) * m * m)) + ",\"center\":" + (p3m c) + ",\"verts\":[" + vs + "]}"
          k += 1
        )
      ) else if rv == #Vertices then (
        for v in (getVertSelection node) do (
          items += (if k > 0 then "," else "") + "{\"vert\":" + (v as string) + ",\"pos\":" + (p3m (in coordsys world (getVert node v))) + "}"
          k += 1
        )
      )
    )
    xViewChecker.on = false
    "{\"type\":" + (q rv) + ",\"count\":" + (cnt as string) + ",\"listed\":" + (k as string) + ",\"text\":" + (q (xViewChecker.getCurrentString())) + ",\"items\":[" + items + "]}"
  )
  local t0 = timeStamp()
  try (
    if fbx == undefined or outp == undefined then throw "ELV_XV_FBX / ELV_XV_OUT not set"
    if doesFileExist (outp + "/done.txt") or doesFileExist (outp + "/results.jsonl") then throw "outputs already exist"
    resetMaxFile #noPrompt
    FBXImporterSetParam "ResetImport"
    FBXImporterSetParam "Mode" #create
    FBXImporterSetParam "ConvertUnit" "m"
    FBXImporterSetParam "SmoothingGroups" true
    FBXImporterSetParam "Animation" false
    importFile fbx #noPrompt using:FBXIMP
    local vi = 0, fi = 0
    for i = 1 to xViewChecker.getNumCheckers() do (
      local nm = xViewChecker.getCheckerName i
      if nm == "Overlapping Vertices" then vi = i
      if nm == "Overlapping Faces" then fi = i
    )
    if vi == 0 or fi == 0 then throw "xView checkers missing"
    OverlappingFaces.tolerance = units.decodeValue "5mm"
    OverlappingVertices.tolerance = units.decodeValue "2mm"
    local targets = #()
    for o in geometry where o.name == "SM_Elevatornaya_1A_Main" do append targets o
    for o in geometry where o.name == "SM_Elevatornaya_1A_MainGlass" do append targets o
    for o in geometry where matchPattern o.name pattern:"UCX_*" do append targets o
    local other = for o in objects where findItem targets o == 0 collect o.name
    local rf = createFile (outp + "/results.jsonl")
    max modify mode
    local nMain = 0, sumV = 0, sumF = 0, hitNodes = 0
    for node in targets do (
      local cls = classof node
      convertToMesh node
      local nv0 = node.numverts
      meshop.weldVertsByThreshold node #{1..nv0} (units.decodeValue "2mm")
      update node
      local nv1 = node.numverts
      clearSelection(); select node
      local vr = runChecker node vi
      local fr = runChecker node fi
      format "{\"node\":%,\"srcClass\":%,\"class\":%,\"faces\":%,\"vertsBefore\":%,\"vertsAfter\":%,\"bboxMin\":%,\"bboxMax\":%,\"verticesCheck\":%,\"facesCheck\":%}\n" \
        (q node.name) (q cls) (q (classof node)) node.numfaces nv0 nv1 (p3m node.min) (p3m node.max) vr fr to:rf
      flush rf
    )
    close rf
    local sf = createFile (outp + "/summary.json")
    format "{\"fbx\":%,\"maxVersion\":%,\"units\":%,\"systemScale\":%,\"metresPerSystemUnit\":%,\"tolFaces_m\":%,\"tolVerts_m\":%,\"targets\":%,\"otherObjects\":%,\"seconds\":%}\n" \
      (q fbx) (q ((maxVersion()) as string)) (q units.systemType) (num units.systemScale) (num m) \
      (num (OverlappingFaces.tolerance * m)) (num (OverlappingVertices.tolerance * m)) targets.count other.count \
      (num ((timeStamp() - t0) / 1000.0)) to:sf
    close sf
    close (createFile (outp + "/done.txt"))
    format "ELV_XV_OK %\n" targets.count
  ) catch (
    local msg = getCurrentException()
    format "ELV_XV_ERROR %\n" msg
    try (local ff = createFile (outp + "/failed.txt"); format "%\n" msg to:ff; close ff) catch ()
  )
  quitMax #noPrompt
)
