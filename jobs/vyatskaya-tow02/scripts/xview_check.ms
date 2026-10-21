-- TOW02: import the joined quad FBX into an empty scene and run every xView checker on it (3ds Max 2024).
-- Engine gap: EG6. User request 2026-10-21: attach all Lego pieces, run xView, list the errors before NPM.
-- Usage: 3dsmax.exe -U MAXScript xview_check.ms   (reads TOW02_XVIEW_FBX and TOW02_XVIEW_OUT from the environment)
-- xView only computes from a UI context (a startup script works; calls through the MCP bridge return 'Not applicable').
-- Writes <out>/xview_report.jsonl, one line per checker, flushed as it goes (Overlapping Faces is slow on 35k faces):
-- name, return type, count, xView text, seconds, up to 30 sample world positions, or the error.
(
  local fbx = systemTools.getEnvVariable "TOW02_XVIEW_FBX"
  local outp = systemTools.getEnvVariable "TOW02_XVIEW_OUT"
  local logf = outp + "/xview_report.jsonl"
  fn emit logf line = (local fs = openFile logf mode:"a"; format "%\n" line to:fs; close fs)
  fn p3 p = "[" + (p.x as string) + "," + (p.y as string) + "," + (p.z as string) + "]"
  deleteFile logf
  resetMaxFile #noPrompt
  FBXImporterSetParam "ResetImport"
  FBXImporterSetParam "Mode" #create
  FBXImporterSetParam "ConvertUnit" "m"
  FBXImporterSetParam "SmoothingGroups" true
  FBXImporterSetParam "Animation" false
  importFile fbx #noPrompt using:FBXIMP
  local node = getNodeByName "SM_Vyatskaya_Vl_47_49_013_Main"
  if classof node != Editable_Poly then convertToPoly node
  select node
  max modify mode
  emit logf ("{\"node\":\"" + node.name + "\",\"faces\":" + (polyop.getNumFaces node) as string + ",\"verts\":" + (polyop.getNumVerts node) as string + "}")
  local order = #(1, 3, 4, 5, 6, 7, 8, 9, 10, 2)  -- Overlapping Faces last: slowest
  for i in order do (
    local name = xViewChecker.getCheckerName i
    try (
      local t0 = timeStamp()
      xViewChecker.activeIndex = i
      xViewChecker.on = true
      xViewChecker.runCheck currentTime
      local rv = xViewChecker.getCurrentReturnVal()
      local cnt = xViewChecker.getCurrentOutputCount()
      local txt = substituteString (xViewChecker.getCurrentString()) "\"" "'"
      local secs = (timeStamp() - t0) / 1000.0
      local pts = ""
      if cnt > 0 and rv != #Failed then (
        try (
          xViewChecker.selectResults currentTime
          local sel = case rv of (
            #Vertices: polyop.getVertSelection node
            #Edges: polyop.getEdgeSelection node
            #Faces: polyop.getFaceSelection node
          )
          local k = 0
          for e in sel while k < 30 do (
            local p = case rv of (
              #Vertices: polyop.getVert node e
              #Edges: (local ev = polyop.getEdgeVerts node e; ((polyop.getVert node ev[1]) + (polyop.getVert node ev[2])) / 2)
              #Faces: polyop.getFaceCenter node e
            )
            pts += (if k > 0 then "," else "") + (p3 p)
            k += 1
          )
        ) catch (pts = "\"samples failed: " + (substituteString (getCurrentException()) "\"" "'") + "\"")
      )
      emit logf ("{\"name\":\"" + name + "\",\"type\":\"" + rv as string + "\",\"count\":" + cnt as string + ",\"text\":\"" + txt + "\",\"seconds\":" + secs as string + ",\"samples\":[" + pts + "]}")
    ) catch (
      emit logf ("{\"name\":\"" + name + "\",\"error\":\"" + (substituteString (getCurrentException()) "\"" "'") + "\"}")
    )
  )
  xViewChecker.on = false
  emit logf "{\"done\":true}"
)
