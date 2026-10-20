-- xView parity dump for #370 (card t_3013550d). Imports a COPY of an FBX, runs Max's built-in xView
-- checkers OverlappingVertices (2 mm) and OverlappingFaces (5 mm) on every geometry node, writes their
-- result ids (1-based) and the node's vertices (metres) + polygon faces (1-based) to a JSON file.
-- Usage: set global xv_fbx / xv_out before filein.
fn xv_arr a = (
	local s = "["
	for i = 1 to a.count do (if i > 1 do s += ","; s += (a[i] as string))
	s + "]"
)
fn xv_dump fbxPath outPath = (
	resetMaxFile #noPrompt
	units.SystemType = #meters
	importFile fbxPath #noPrompt using:FBXIMP
	local m = 1.0 / (units.decodeValue "1m")      -- system units -> metres
	local tolV = 0.002 / m
	local tolF = 0.005 / m
	local f = createFile outPath
	format "{\"fbx\": \"%\", \"system_type\": \"%\", \"m_per_unit\": %, \"tol_v_units\": %, \"tol_f_units\": %, \"nodes\": [\n" \
		(substituteString fbxPath "\\" "/") units.SystemType m (formattedPrint tolV format:".6f") (formattedPrint tolF format:".6f") to:f
	local first = true
	for n in (geometry as array) where canConvertTo n Editable_Poly do (
		convertToPoly n
		local cls = classof n.baseobject
		OverlappingVertices.tolerance = tolV
		format "XV tolV set % read %
" tolV OverlappingVertices.tolerance
		local rv = #()
		local tv = OverlappingVertices.Check currentTime n &rv
		OverlappingFaces.tolerance = tolF
		local rf = #()
		local tf = OverlappingFaces.Check currentTime n &rf
		format "XV tolF read %
" OverlappingFaces.tolerance
		local p = n
		local nv = polyop.getNumVerts p
		local nf = polyop.getNumFaces p
		if not first do format ",\n" to:f
		first = false
		format "{\"name\": \"%\", \"class\": \"%\", \"verts_type\": \"%\", \"faces_type\": \"%\", \"overlap_vertices\": %, \"overlap_faces\": %, \"num_verts\": %, \"num_faces\": %, \"vertices\": [" \
			n.name cls tv tf (xv_arr (rv as array)) (xv_arr (rf as array)) nv nf to:f
		for i = 1 to nv do (
			local q = (polyop.getVert p i) * m
			if i > 1 do format "," to:f
			format "[%,%,%]" (formattedPrint q.x format:".7f") (formattedPrint q.y format:".7f") (formattedPrint q.z format:".7f") to:f
		)
		format "], \"faces\": [" to:f
		for i = 1 to nf do (
			if i > 1 do format "," to:f
			format "%" (xv_arr (polyop.getFaceVerts p i)) to:f
		)
		format "]}" to:f
		format "XV node=% class=% verts=% faces=% ov=%(%) of=%(%)\n" n.name cls nv nf (rv as array).count tv (rf as array).count tf
	)
	format "]}\n" to:f
	close f
)
xv_dump (getFilenamePath (getSourceFileName()) + "npm\\SM_Vatutino_Ground.fbx") (getFilenamePath (getSourceFileName()) + "npm_poly_xview.json")
xv_dump (getFilenamePath (getSourceFileName()) + "vpm\\SM_Vatutino_Ground.fbx") (getFilenamePath (getSourceFileName()) + "vpm_poly_xview.json")
format "XV done\n"
