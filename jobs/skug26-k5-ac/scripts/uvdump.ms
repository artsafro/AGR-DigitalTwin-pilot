(
	local f = createFile "C:/Users/artsafro/AppData/Local/Temp/claude/cded0b00b78ce72f/bc045341-1087-412b-aaa6-9286e6f45ee2/scratchpad/uv_faces.csv"
	for nm in #("Object004", "Object005") do
	(
		local o = getNodeByName nm
		for fi = 1 to polyop.getNumFaces o do
		(
			local mf = polyop.getMapFace o 1 fi
			format "%,%,%" nm fi (polyop.getFaceMatID o fi) to:f
			for v in mf do (local p = polyop.getMapVert o 1 v; format ",%,%" (formattedPrint p.x format:".7f") (formattedPrint p.y format:".7f") to:f)
			format "\n" to:f
		)
	)
	close f
)
