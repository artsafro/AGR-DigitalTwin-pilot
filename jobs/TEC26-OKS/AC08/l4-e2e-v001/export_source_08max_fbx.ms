-- #753: export a source FBX COPY from the staged copy of 08.max (no save of any .max)
(
	local out = "C:/x/ev_t_b4f6c33a/src/AC08_source_08max.fbx"
	format "SRC file=% units=% scale=% maxver=%\n" (maxFilePath + maxFileName) units.SystemType units.SystemScale ((maxVersion())[1])
	for o in objects do (
		local nf = -1
		if (canConvertTo o Editable_Mesh) then (try (nf = (getPolygonCount o)[1]) catch ())
		format "NODE name=% class=% faces=% hidden=% layer=% pos=%\n" o.name (classOf o) nf o.isHidden o.layer.name o.pos
	)
	if doesFileExist out then (format "ERROR output exists %\n" out) else (
		FBXExporterSetParam "ResetExport"
		FBXExporterSetParam "ConvertUnit" "m"
		FBXExporterSetParam "Triangulate" false
		FBXExporterSetParam "SmoothingGroups" true
		FBXExporterSetParam "Animation" false
		FBXExporterSetParam "Cameras" false
		FBXExporterSetParam "Lights" false
		FBXExporterSetParam "EmbedTextures" false
		local ok = exportFile out #noPrompt using:FBXEXP
		format "EXPORT ok=% exists=%\n" ok (doesFileExist out)
	)
)
