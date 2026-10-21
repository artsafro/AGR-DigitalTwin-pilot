-- TOW02 review (#514): xView Overlapping Faces 5 mm / Overlapping Vertices 2 mm on several models, full face lists.
-- Engine gap: EG6 (no xView-grade overlap check in the engine; 3ds Max xView is the overlap truth).
-- Usage: 3dsmax.exe -U MAXScript xview_review.ms   (reads TOW02_XV_OUT; <out>/jobs.txt has lines label|path|node[|weld])
-- path is .fbx (imported into a reset scene) or .max (loaded, never saved). node empty = largest mesh in the scene.
-- weld: convert to Editable Mesh, weld at 2 mm, check the mesh (the user's pre-export step); weldpoly: same, then
-- back to poly before the checks. Welded count is reported as weldedVerts.
-- Paths must be ASCII: Max 2024 misreads a cp1251/UTF-8 jobs.txt, so copy files with Cyrillic paths first.
-- Tolerances go through units.decodeValue, so they stay 5 mm / 2 mm whatever the system unit is.
-- Writes <out>/<label>.json per model: units, scene objects, node counts, counts and every flagged face/vertex.
(
  local outp = systemTools.getEnvVariable "TOW02_XV_OUT"
  fn p3 p = "[" + (p.x as string) + "," + (p.y as string) + "," + (p.z as string) + "]"
  fn q s = "\"" + (substituteString (substituteString (s as string) "\\" "/") "\"" "'") + "\""
  fn faceCount o = (try (getPolygonCount o)[1] catch 0)
  -- Editable Mesh and Editable Poly read through their own APIs, so a welded mesh is checked without a poly round trip
  fn isMesh node = classof node == Editable_mesh
  fn faceSel node = if isMesh node then getFaceSelection node else polyop.getFaceSelection node
  fn vertSel node = if isMesh node then getVertSelection node else polyop.getVertSelection node
  fn faceRow node f = (
    local mid = if isMesh node then getFaceMatID node f else polyop.getFaceMatID node f
    local ar = if isMesh node then meshop.getFaceArea node #{f} else polyop.getFaceArea node f
    local c = if isMesh node then meshop.getFaceCenter node f else polyop.getFaceCenter node f
    "[" + f as string + "," + mid as string + "," + ar as string + "," + (p3 c) + "]"
  )
  fn vertPos node v = if isMesh node then getVert node v else polyop.getVert node v
  fn runChecker node idx = (
    local t0 = timeStamp()
    xViewChecker.activeIndex = idx
    xViewChecker.on = true
    xViewChecker.runCheck currentTime
    local rv = xViewChecker.getCurrentReturnVal()
    local cnt = xViewChecker.getCurrentOutputCount()
    local items = ""
    if cnt > 0 and rv != #Failed then (
      xViewChecker.selectResults currentTime
      local k = 0
      if rv == #Faces then (
        for f in (faceSel node) do (items += (if k > 0 then "," else "") + (faceRow node f); k += 1)
      ) else if rv == #Vertices then (
        for v in (vertSel node) do (
          items += (if k > 0 then "," else "") + "[" + v as string + "," + (p3 (vertPos node v)) + "]"
          k += 1
        )
      )
    )
    xViewChecker.on = false
    "{\"name\":" + (q (xViewChecker.getCheckerName idx)) + ",\"type\":" + (q rv) + ",\"count\":" + cnt as string + \
      ",\"text\":" + (q (xViewChecker.getCurrentString())) + ",\"seconds\":" + ((timeStamp() - t0) / 1000.0) as string + \
      ",\"items\":[" + items + "]}"
  )
  local jf = openFile (outp + "/jobs.txt")
  local jobs = #()
  while not eof jf do (local l = readLine jf; if l != "" then append jobs (filterString l "|" splitEmptyTokens:true))
  close jf
  for j in jobs do (
    local label = j[1], path = j[2], want = (if j.count > 2 then j[3] else "")
    local res = outp + "/" + label + ".json"
    deleteFile res
    try (
      resetMaxFile #noPrompt
      if matchPattern path pattern:"*.max" then loadMaxFile path quiet:true useFileUnits:true
      else (
        FBXImporterSetParam "ResetImport"
        FBXImporterSetParam "Mode" #create
        FBXImporterSetParam "ConvertUnit" "m"
        FBXImporterSetParam "SmoothingGroups" true
        FBXImporterSetParam "Animation" false
        importFile path #noPrompt using:FBXIMP
      )
      local geo = for o in geometry where superclassof o == GeometryClass collect o
      local node = if want != "" then getNodeByName want else undefined
      if node == undefined then (local best = 0; for o in geo do (local n = faceCount o; if n > best then (best = n; node = o)))
      local scn = ""
      for o in geo do scn += (if scn != "" then "," else "") + "[" + (q o.name) + "," + (q (classof o)) + "," + (faceCount o) as string + "]"
      local srcClass = classof node
      local welded = -1
      local mode = if j.count > 3 then j[4] else ""
      if mode == "weld" or mode == "weldpoly" then (
        -- the user's pre-export step: Editable Mesh, weld all vertices at 2 mm (in memory only). "weld" checks the
        -- mesh as is; "weldpoly" converts back to poly first, which splits non-manifold vertices again (user, 2026-10-21)
        convertToMesh node
        local nv0 = node.numverts
        meshop.weldVertsByThreshold node #{1..nv0} (units.decodeValue "2mm")
        update node
        welded = nv0 - node.numverts
      )
      if mode != "weld" and classof node != Editable_Poly then convertToPoly node
      clearSelection(); select node
      max modify mode
      OverlappingFaces.tolerance = units.decodeValue "5mm"
      OverlappingVertices.tolerance = units.decodeValue "2mm"
      local tris = 0, ngons = 0
      local nf = if isMesh node then node.numfaces else polyop.getNumFaces node
      if isMesh node then tris = nf
      else for f = 1 to nf do (local d = polyop.getFaceDeg node f; if d == 3 then tris += 1 else if d > 4 then ngons += 1)
      local vi = 0, fi = 0
      for i = 1 to xViewChecker.getNumCheckers() do (
        local nm = xViewChecker.getCheckerName i
        if nm == "Overlapping Vertices" then vi = i
        if nm == "Overlapping Faces" then fi = i
      )
      local fs = createFile res
      format "{\"label\":%,\"path\":%,\"units\":%,\"systemScale\":%,\"tolFaces\":%,\"tolVerts\":%,\"scene\":[%],\n" \
        (q label) (q path) (q units.systemType) units.systemScale OverlappingFaces.tolerance OverlappingVertices.tolerance scn to:fs
      format "\"node\":%,\"sourceClass\":%,\"weldedVerts\":%,\"faces\":%,\"verts\":%,\"tris\":%,\"ngons\":%,\"bbox\":[%,%],\n" \
        (q node.name) (q srcClass) welded nf (if isMesh node then node.numverts else polyop.getNumVerts node) tris ngons \
        (p3 node.min) (p3 node.max) to:fs
      flush fs
      format "\"verticesCheck\":%,\n" (runChecker node vi) to:fs
      flush fs
      format "\"facesCheck\":%}\n" (runChecker node fi) to:fs
      close fs
    ) catch (
      local fs = createFile res
      format "{\"label\":%,\"path\":%,\"error\":%}\n" (q label) (q path) (q (getCurrentException())) to:fs
      close fs
    )
  )
  close (createFile (outp + "/done.txt"))
  quitMax #noPrompt
)
