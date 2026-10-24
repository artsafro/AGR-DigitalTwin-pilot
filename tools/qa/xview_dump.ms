-- Shared 3ds Max xView runner (#528, folds the TOW02 twins into #380).
-- 3dsmax.exe -U MAXScript tools/qa/xview_dump.ms
-- XVIEW_OUT (or TOW02_XV_OUT) is a new directory that already contains jobs.txt.
-- jobs.txt receipt: first non-empty line is #nonce:<id> (8..64 of [A-Za-z0-9_-]).
-- Then one line per model, exactly six fields: label|path|node|mode|material|slot
-- path is .fbx (imported into a reset scene) or .max (loadMaxFile quiet, useFileUnits, never saved).
-- node empty = the largest mesh by polygon count; a name that is not in the scene is an error naming it.
-- mode: plain (default), weld (Editable Mesh + weld all vertices at units.decodeValue "2mm", checks stay
-- on the mesh), weldpoly (same weld, then Editable Poly; that round trip re-splits non-manifold vertices).
-- Face tolerance is units.decodeValue "5mm", so both stay 5 mm / 2 mm in any system unit.
-- A non-ASCII path is copied to XVIEW_TEMP under an ASCII name; SHA-256 of the copy must equal the source.
-- SHA-256 of the opened file is taken before the load and after the checks; a change is an error.
-- xv_preflight runs before any createFile, deleteFile or stage copy. It rejects duplicate labels,
-- '|' and control characters, a non-canonical slot token, and same-file identity (normalized path
-- plus GetFileInformationByHandle) across inputs, <label>.json, jobs.txt, report.jsonl, done.txt,
-- failed.txt, other outputs and the ASCII staging copy. Python is not required: the mirror is
-- tools/qa/xview_parity.py preflight_jobs_txt. A preflight failure exits before any write.
-- Writes <out>/<label>.json: nonce, scene inventory, dropped nodes, counts, every flagged face
-- (Max face id, material id, area, centre) and every flagged vertex (id, position).
-- done.txt is the nonce, written only when every job succeeds. check_run requires that same nonce.
-- Any later failure writes <out>/failed.txt (the reason) and does not leave done.txt.
-- quitMax does not set a process exit code. On failure the script calls
-- System.Environment.Exit 1. The wrapper check_run is the result either way.
-- xView only computes from this startup script, not from the MCP bridge. One Max owner at a time.
(
  local outp = systemTools.getEnvVariable "XVIEW_OUT"
  if outp == undefined or outp == "" do outp = systemTools.getEnvVariable "TOW02_XV_OUT"
  local tempDir = systemTools.getEnvVariable "XVIEW_TEMP"

  fn xv_num x = (
    if x == undefined or x != x then throw "non-finite number"
    formattedPrint x format:".7g"
  )
  fn p3 p = (
    if p == undefined or p.x != p.x or p.y != p.y or p.z != p.z then throw "non-finite coordinate"
    "[" + (xv_num p.x) + "," + (xv_num p.y) + "," + (xv_num p.z) + "]"
  )
  fn q s = "\"" + (substituteString (substituteString (s as string) "\\" "/") "\"" "'") + "\""
  fn faceCount o = (try (getPolygonCount o)[1] catch 0)
  fn isMesh node = classof node == Editable_mesh
  fn faceSel node = if isMesh node then getFaceSelection node else polyop.getFaceSelection node
  fn vertSel node = if isMesh node then getVertSelection node else polyop.getVertSelection node
  fn faceRow node f = (
    local mid = if isMesh node then getFaceMatID node f else polyop.getFaceMatID node f
    local ar = if isMesh node then meshop.getFaceArea node #{f} else polyop.getFaceArea node f
    local c = if isMesh node then meshop.getFaceCenter node f else polyop.getFaceCenter node f
    if ar != ar then throw "non-finite area"
    "[" + (f as string) + "," + (mid as string) + "," + (xv_num ar) + "," + (p3 c) + "]"
  )
  fn vertPos node v = if isMesh node then getVert node v else polyop.getVert node v
  fn xv_abs p = toLower (pathConfig.convertPathToAbsolute (p as string))
  fn xv_same a b = a != undefined and b != undefined and (xv_abs a) == (xv_abs b)
  fn xv_compile_file_id = (
    local ss = stringStream ""
    format "using System;\n" to:ss
    format "using System.IO;\n" to:ss
    format "using System.Runtime.InteropServices;\n" to:ss
    format "public class XvFileId {\n" to:ss
    format "  [StructLayout(LayoutKind.Sequential)] public struct Info {\n" to:ss
    format "    public uint dwFileAttributes;\n" to:ss
    format "    public long ftCreationTime;\n" to:ss
    format "    public long ftLastAccessTime;\n" to:ss
    format "    public long ftLastWriteTime;\n" to:ss
    format "    public uint dwVolumeSerialNumber;\n" to:ss
    format "    public uint nFileSizeHigh;\n" to:ss
    format "    public uint nFileSizeLow;\n" to:ss
    format "    public uint nNumberOfLinks;\n" to:ss
    format "    public uint nFileIndexHigh;\n" to:ss
    format "    public uint nFileIndexLow;\n" to:ss
    format "  }\n" to:ss
    format "  [DllImport(\"kernel32.dll\", SetLastError=true)]\n" to:ss
    format "  static extern bool GetFileInformationByHandle(IntPtr h, out Info info);\n" to:ss
    format "  public static string Id(string path) {\n" to:ss
    format "    if (path == null || path.Length == 0 || !File.Exists(path)) return \"\";\n" to:ss
    format "    FileStream fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);\n" to:ss
    format "    try {\n" to:ss
    format "      Info info;\n" to:ss
    format "      if (!GetFileInformationByHandle(fs.SafeFileHandle.DangerousGetHandle(), out info)) return \"\";\n" to:ss
    format "      return info.dwVolumeSerialNumber.ToString() + \":\" + info.nFileIndexHigh.ToString() + \":\" + info.nFileIndexLow.ToString();\n" to:ss
    format "    } finally { fs.Dispose(); }\n" to:ss
    format "  }\n" to:ss
    format "}\n" to:ss
    local provider = dotNetObject "Microsoft.CSharp.CSharpCodeProvider"
    local param = dotNetObject "System.CodeDom.Compiler.CompilerParameters"
    param.GenerateInMemory = true
    param.ReferencedAssemblies.Add "System.dll"
    local res = provider.CompileAssemblyFromSource param #((ss as string))
    if res.Errors.Count > 0 then throw ("file id compile failed: " + (res.Errors.Item[0].ErrorText as string))
    res.CompiledAssembly.GetType "XvFileId"
  )
  fn xv_file_id typ path = (
    local mi = typ.GetMethod "Id"
    local id = mi.Invoke undefined #(path as string)
    if id == undefined then "" else (id as string)
  )
  fn xv_ident typ a b strict:true = (
    if a == undefined or b == undefined then return false
    if xv_same a b then return true
    if not doesFileExist a or not doesFileExist b then return false
    local ia = ""
    local ib = ""
    try (
      ia = xv_file_id typ a
      ib = xv_file_id typ b
    ) catch (
      ia = ""
    )
    if ia == "" or ib == "" then (
      if strict then throw "file id failed" else return true
    )
    ia == ib
  )
  fn xv_sha256 p = (
    local sha = dotNetObject "System.Security.Cryptography.SHA256Managed"
    local bytes = (dotNetClass "System.IO.File").ReadAllBytes (p as string)
    local hex = (dotNetClass "System.BitConverter").ToString (sha.ComputeHash bytes)
    toLower (substituteString hex "-" "")
  )
  fn xv_non_ascii s = (
    for i = 1 to s.count where (bit.charAsInt s[i]) > 127 do return true
    false
  )
  fn xv_bad_text s what = (
    local t = s as string
    for i = 1 to t.count do (
      local c = bit.charAsInt t[i]
      if c < 32 or c == 124 then throw ("bad field " + what + " '" + t + "'")
    )
    t
  )
  fn xv_nonce_ok s = (
    if s == undefined or s.count < 8 or s.count > 64 then return false
    for i = 1 to s.count do (
      local c = bit.charAsInt s[i]
      local ok = (c >= 48 and c <= 57) or (c >= 65 and c <= 90) or (c >= 97 and c <= 122) or c == 95 or c == 45
      if not ok then return false
    )
    true
  )
  fn xv_slot_ok slotStr = (
    if slotStr == "" then return true
    if slotStr[1] == "0" then return false
    for i = 1 to slotStr.count where (bit.charAsInt slotStr[i]) < 48 or (bit.charAsInt slotStr[i]) > 57 do return false
    true
  )
  fn xv_split s = (
    local parts = #()
    local cur = ""
    for i = 1 to s.count do (
      if s[i] == "|" then (append parts cur; cur = "") else cur += s[i]
    )
    append parts cur
    parts
  )
  fn xv_stage idType path = (
    if not (xv_non_ascii path) then return path
    if tempDir == undefined or tempDir == "" then throw "no ASCII temp dir"
    local dest = (tempDir as string) + "/xv_" + (xv_sha256 path) + (getFilenameType path)
    if xv_ident idType dest path then throw "temp aliases input"
    if xv_non_ascii dest then throw "staged path is not ASCII"
    if not doesFileExist dest then (dotNetClass "System.IO.File").Copy path dest true
    if (xv_sha256 dest) != (xv_sha256 path) then throw "SHA-256 mismatch"
    dest
  )
  fn xv_has_mat node name = (
    if node.material == undefined then return false
    if node.material.name == name then return true
    if classof node.material == Multimaterial then (
      for m in node.material.materialList where m != undefined and m.name == name do return true
    )
    false
  )
  fn xv_read_jobs jobsP = (
    local jf = openFile jobsP
    if jf == undefined then throw "jobs.txt missing"
    local nonce = undefined
    local jobs = #()
    local seenNonce = false
    while not eof jf do (
      local l = readLine jf
      if l != undefined and l != "" do (
        if not seenNonce then (
          seenNonce = true
          if (findString l "#nonce:") != 1 then throw "nonce missing"
          nonce = substring l 8 (l.count - 7)
          if not (xv_nonce_ok nonce) then throw "nonce missing"
        ) else (
          local parts = xv_split l
          if parts.count != 6 then throw ("jobs.txt line field count " + (parts.count as string))
          local names = #("label", "path", "node", "mode", "material", "slot")
          for i = 1 to 6 do xv_bad_text parts[i] names[i]
          append jobs parts
        )
      )
    )
    close jf
    if nonce == undefined then throw "nonce missing"
    if jobs.count == 0 then throw "no inputs"
    #(nonce, jobs)
  )
  fn xv_conflict typ kindA pathA kindB pathB = (
    if not (xv_ident typ pathA pathB) then return false
    if kindA == "input" and kindB == "input" then return false
    if kindA == "temp" and kindB == "temp" then return (xv_abs pathA) != (xv_abs pathB)
    true
  )
  fn xv_preflight idType jobs nonce outp tempDir report doneP failedP jobsP = (
    local kinds = #()
    local paths = #()
    local seen = #()
    for guard in jobs do (
      local label = guard[1]
      local path = guard[2]
      local mode = guard[4]
      local slotStr = guard[6]
      if label == "" or (findString label "\\") != undefined or (findString label "/") != undefined or xv_non_ascii label then
        throw ("unmapped label '" + label + "'")
      if findItem seen (toLower label) > 0 then throw ("duplicate label '" + label + "'")
      append seen (toLower label)
      local ext = toLower (getFilenameType path)
      if ext != ".max" and ext != ".fbx" then throw ("unsupported input '" + (filenameFromPath path) + "'")
      if not doesFileExist path then throw ("input missing: " + path)
      if mode != "" and mode != "plain" and mode != "weld" and mode != "weldpoly" then
        throw ("unmapped mode '" + mode + "'")
      if not (xv_slot_ok slotStr) then throw ("unmapped slot '" + slotStr + "'")
      append kinds "input"
      append paths path
      append kinds "output"
      append paths (outp + "/" + label + ".json")
      if xv_non_ascii path then (
        if tempDir == undefined or tempDir == "" then throw "no ASCII temp dir"
        local dest = (tempDir as string) + "/xv_" + (xv_sha256 path) + ext
        if xv_non_ascii dest then throw "staged path is not ASCII"
        append kinds "temp"
        append paths dest
      )
    )
    append kinds "jobs"; append paths jobsP
    append kinds "report"; append paths report
    append kinds "done"; append paths doneP
    append kinds "failed"; append paths failedP
    local i = 1
    while i <= paths.count do (
      local k = i + 1
      while k <= paths.count do (
        if xv_conflict idType kinds[i] paths[i] kinds[k] paths[k] then throw "output aliases input"
        k += 1
      )
      i += 1
    )
    nonce
  )
  fn runChecker node idx what = (
    if idx < 1 then throw ("unmapped checker '" + what + "'")
    local t0 = timeStamp()
    xViewChecker.activeIndex = idx
    xViewChecker.on = true
    xViewChecker.runCheck currentTime
    local rv = xViewChecker.getCurrentReturnVal()
    local cnt = xViewChecker.getCurrentOutputCount()
    if rv == #Failed then throw ("checker failed: " + what)
    local items = ""
    local k = 0
    if cnt > 0 then (
      xViewChecker.selectResults currentTime
      if rv == #Faces then (
        for f in (faceSel node) do (items += (if k > 0 then "," else "") + (faceRow node f); k += 1)
      ) else if rv == #Vertices then (
        for v in (vertSel node) do (
          items += (if k > 0 then "," else "") + "[" + (v as string) + "," + (p3 (vertPos node v)) + "]"
          k += 1
        )
      ) else throw ("unmapped checker result '" + (rv as string) + "'")
    )
    xViewChecker.on = false
    if k != cnt then throw ("partial " + what + " list")
    "{\"name\":" + (q (xViewChecker.getCheckerName idx)) + ",\"type\":" + (q rv) + ",\"count\":" + (cnt as string) + \
      ",\"text\":" + (q (xViewChecker.getCurrentString())) + ",\"seconds\":" + (xv_num ((timeStamp() - t0) / 1000.0)) + \
      ",\"items\":[" + items + "]}"
  )
  fn xv_exit code = (
    if code != 0 do try ((dotNetClass "System.Environment").Exit code) catch ()
    quitMax #noPrompt
  )
  fn xv_write_failed idType path reason inputs = (
    for p in inputs where xv_ident idType path p strict:false do return false
    local fs = createFile path
    if fs == undefined then return false
    format "%" reason to:fs
    close fs
    true
  )

  local failed = false
  local reason = ""
  local inputPaths = #()
  local ready = false
  local idType = undefined
  try (
  if outp == undefined or outp == "" then throw "XVIEW_OUT is empty"
  local report = outp + "/report.jsonl"
  local doneP = outp + "/done.txt"
  local failedP = outp + "/failed.txt"
  local jobsP = outp + "/jobs.txt"
  local read = xv_read_jobs jobsP
  local nonce = read[1]
  local jobs = read[2]
  idType = xv_compile_file_id()
  xv_preflight idType jobs nonce outp tempDir report doneP failedP jobsP
  ready = true
  if doesFileExist doneP then deleteFile doneP
  if doesFileExist report then deleteFile report
  if doesFileExist failedP then deleteFile failedP
  for j in jobs do append inputPaths j[2]
  local ok = 0
  for j in jobs do (
    local label = j[1]
    local path = j[2]
    local want = j[3]
    local mode = j[4]
    local matName = j[5]
    local slotStr = ""
    if j.count >= 6 then slotStr = j[6] else throw ("jobs.txt line field count " + (j.count as string))
    local res = outp + "/" + label + ".json"
    local openPath = path
    try (
      if label == undefined or label == "" or (findString label "\\") != undefined or (findString label "/") != undefined then
        throw ("unmapped label '" + (label as string) + "'")
      local ext = toLower (getFilenameType path)
      if ext != ".max" and ext != ".fbx" then throw ("unsupported input '" + (filenameFromPath path) + "'")
      if xv_ident idType res path or xv_ident idType report path or xv_ident idType doneP path then throw "output aliases input"
      openPath = xv_stage idType path
      if xv_ident idType res openPath or xv_ident idType report openPath then throw "output aliases input"
      local h0 = xv_sha256 openPath
      local hSrc0 = if openPath != path then xv_sha256 path else h0
      resetMaxFile #noPrompt
      if ext == ".max" then (
        if not (loadMaxFile openPath quiet:true useFileUnits:true) then throw ("load failed: " + openPath)
      ) else (
        FBXImporterSetParam "ResetImport"
        FBXImporterSetParam "Mode" #create
        FBXImporterSetParam "ConvertUnit" "m"
        FBXImporterSetParam "SmoothingGroups" true
        FBXImporterSetParam "Animation" false
        importFile openPath #noPrompt using:FBXIMP
      )
      local seen = #()
      for o in objects do (
        if findItem seen o.name > 0 then throw ("duplicate node '" + o.name + "'")
        append seen o.name
      )
      local geo = for o in geometry where superclassof o == GeometryClass collect o
      local node = undefined
      if want != "" then (
        node = getNodeByName want
        if node == undefined then throw ("unmapped node '" + want + "'")
        if (faceCount node) <= 0 then throw ("node '" + want + "': empty mesh")
      ) else (
        local best = 0
        for o in geo do (local n = faceCount o; if n > best do (best = n; node = o))
        if node == undefined then throw "no mesh"
      )
      if matName != "" and not (xv_has_mat node matName) then throw ("unmapped material '" + matName + "'")
      if slotStr != "" then (
        local id = slotStr as integer
        if classof node.material != Multimaterial or id < 1 or id > node.material.numsubs or node.material.materialList[id] == undefined then
          throw ("unmapped slot '" + slotStr + "'")
      )
      if mode != "" and mode != "plain" and mode != "weld" and mode != "weldpoly" then
        throw ("unmapped mode '" + mode + "'")
      local scn = ""
      for o in geo do scn += (if scn != "" then "," else "") + "[" + (q o.name) + "," + (q (classof o)) + "," + (faceCount o) as string + "]"
      local dropped = ""
      for o in objects where o != node do (
        local why = if superclassof o != GeometryClass then "not a mesh" else (
          if (faceCount o) == 0 then "empty mesh" else "not selected"
        )
        dropped += (if dropped != "" then "," else "") + "{\"name\":" + (q o.name) + ",\"reason\":" + (q why) + "}"
      )
      local srcClass = classof node
      local welded = -1
      if mode == "weld" or mode == "weldpoly" then (
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
      local h1 = xv_sha256 openPath
      local hSrc1 = if openPath != path then xv_sha256 path else h1
      if h0 != h1 or hSrc0 != hSrc1 then throw "input bytes changed"
      if xv_ident idType res openPath or xv_ident idType res path then throw "output aliases input"
      local fs = createFile res
      format "{\"dump_version\":2,\"nonce\":%,\"label\":%,\"path\":%,\"saved\":false,\"sha256_before\":%,\"sha256_after\":%,\"units\":%,\"systemScale\":%,\"tolFaces\":%,\"tolVerts\":%,\"scene\":[%],\"dropped\":[%],\n" \
        (q nonce) (q label) (q path) (q h0) (q h1) (q units.systemType) (xv_num units.systemScale) \
        (xv_num OverlappingFaces.tolerance) (xv_num OverlappingVertices.tolerance) scn dropped to:fs
      format "\"node\":%,\"sourceClass\":%,\"weldedVerts\":%,\"faces\":%,\"verts\":%,\"tris\":%,\"ngons\":%,\"bbox\":[%,%],\n" \
        (q node.name) (q srcClass) welded nf (if isMesh node then node.numverts else polyop.getNumVerts node) tris ngons \
        (p3 node.min) (p3 node.max) to:fs
      flush fs
      format "\"verticesCheck\":%,\n" (runChecker node vi "Overlapping Vertices") to:fs
      flush fs
      format "\"facesCheck\":%}\n" (runChecker node fi "Overlapping Faces") to:fs
      close fs
      local h2 = xv_sha256 openPath
      if h2 != h0 then throw "input bytes changed"
      local rf = openFile report mode:"a"
      format "%\n" ("{\"label\":" + (q label) + ",\"status\":\"ok\"}") to:rf
      close rf
      ok += 1
      format "XVIEW_OK %\n" label
    ) catch (
      local msg = getCurrentException()
      format "XVIEW_ERROR % %\n" label msg
      if reason == "" then reason = (label as string) + ": " + (msg as string) + "\n"
      if res != undefined and idType != undefined and not (xv_ident idType res path strict:false) and not (xv_ident idType res openPath strict:false) then (
        local fs = createFile res
        format "{\"label\":%,\"path\":%,\"error\":%}\n" (q label) (q path) (q msg) to:fs
        close fs
      )
    )
  )
  if ok == jobs.count then (
    local df = createFile doneP
    format "%\n" nonce to:df
    close df
  ) else (
    failed = true
    if reason == "" then reason = "not all jobs ok\n"
    if not (xv_write_failed idType failedP reason inputPaths) then throw "output aliases input"
  )
  ) catch (
    failed = true
    local msg = getCurrentException()
    format "XVIEW_ERROR %\n" msg
    if ready and outp != undefined and outp != "" then (
      if reason == "" then reason = (msg as string)
      xv_write_failed idType (outp + "/failed.txt") (reason + "\n") inputPaths
    )
  )
  if failed then xv_exit 1 else xv_exit 0
)
