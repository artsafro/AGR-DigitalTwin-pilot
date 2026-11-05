-- #753: export nodes "АС.08" + "Colizii_044" from a staged COPY of 04-09 Geometry Final.max (no save)
(
	local out = "C:/x/ev_t_b4f6c33a/src/AC08_source_geomfinal.fbx"
	format "SRC file=% units=% scale=%\n" (maxFilePath + maxFileName) units.SystemType units.SystemScale
	local want = #("\u0410\u0421.08", "Colizii_044")
	local sel = #()
	for o in objects do (
		local nm = o.name
		local hit = false
		if (matchPattern nm pattern:"??.08") or nm == "Colizii_044" then hit = true
		if hit then (append sel o; format "SEL name=% class=% faces=% pos=%\n" o.name (classOf o) ((getPolygonCount o)[1]) o.pos)
	)
	format "SELECTED %\n" sel.count
	if sel.count != 2 then (format "ERROR expected 2 nodes\n") else if doesFileExist out then (format "ERROR output exists\n") else (
		select sel
		FBXExporterSetParam "ResetExport"
		FBXExporterSetParam "ConvertUnit" "m"
		FBXExporterSetParam "Triangulate" false
		FBXExporterSetParam "SmoothingGroups" true
		FBXExporterSetParam "Animation" false
		FBXExporterSetParam "Cameras" false
		FBXExporterSetParam "Lights" false
		FBXExporterSetParam "EmbedTextures" false
		local ok = exportFile out #noPrompt selectedOnly:true using:FBXEXP
		format "EXPORT ok=% exists=%\n" ok (doesFileExist out)
	)
)
