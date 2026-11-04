-- Readback of a built PZU scene: stats to <out>.txt, top-down and oblique renders to <out>_top.png / <out>_persp.png.
-- Set AGR_IN and AGR_OUT (forward slashes) before fileIn, or edit the two lines below.
global AGR_IN, AGR_OUT, AGR_FOCUS
(
	loadMaxFile AGR_IN quiet:true useFileUnits:true
	local fs = createFile (AGR_OUT + ".txt")
	format "file %\nunits % %\n" AGR_IN units.SystemType units.SystemScale to:fs
	for o in objects do (
		local bb = nodeGetBoundingBox o (matrix3 1)
		format "node % class % pos % bbmin % bbmax %\n" o.name (classof o) o.pos bb[1] bb[2] to:fs
		if classof o == Editable_Poly then (
			local ids = #()
			for f = 1 to polyop.getNumFaces o do appendIfUnique ids (polyop.getFaceMatID o f)
			sort ids
			format "  faces % verts % openEdges % matIDs % mat %\n" (polyop.getNumFaces o) (polyop.getNumVerts o) ((polyop.getOpenEdges o).numberSet) ids o.material to:fs
		)
		if superclassof o == shape then (
			local m = snapshotAsMesh o renderMesh:true
			local zmin = 1e9, zmax = -1e9
			for i = 1 to m.numverts do (local z = (getVert m i).z; if z < zmin do zmin = z; if z > zmax do zmax = z)
			format "  splines % renderable % rect % len % wid % renderMeshFaces % zmin % zmax %\n" (numSplines o) o.render_renderable o.render_rectangular o.render_length o.render_width m.numfaces zmin zmax to:fs
			delete m
		)
	)
	close fs
	-- renders (a short Corona preview when the scene uses Corona; nothing here is saved back)
	try (renderers.current.progressive_passLimit = 6; renderers.current.progressive_timeLimit = 60000) catch ()
	useEnvironmentMap = false; backgroundColor = (color 230 230 230)  -- flat light for the check only
	local g = getNodeByName "PZU_Ground"
	local bb = nodeGetBoundingBox g (matrix3 1)
	local c = (bb[1] + bb[2]) / 2
	local span = amax #(bb[2].x - bb[1].x, bb[2].y - bb[1].y)
	local cam = Freecamera name:"AGR_TopCam" orthoProjection:true fov:60
	cam.position = [c.x, c.y, 100]
	cam.fov = 2 * atan (span * 0.55 / 100)
	render camera:cam outputwidth:2000 outputheight:2000 outputfile:(AGR_OUT + "_top.png") vfb:false quiet:true
	local cam2 = Targetcamera name:"AGR_PerspCam" fov:40 target:(Targetobject pos:c)
	cam2.position = c + [-span * 0.3, -span * 0.6, span * 0.35]
	render camera:cam2 outputwidth:2000 outputheight:1300 outputfile:(AGR_OUT + "_persp.png") vfb:false quiet:true
	if AGR_FOCUS != undefined do (  -- close-up of one point, e.g. a painted circle
		local cam3 = Targetcamera name:"AGR_FocusCam" fov:40 target:(Targetobject pos:AGR_FOCUS)
		cam3.position = AGR_FOCUS + [-2.5, -6, 4]
		render camera:cam3 outputwidth:1600 outputheight:1000 outputfile:(AGR_OUT + "_focus.png") vfb:false quiet:true
	)
	resetMaxFile #noPrompt
)
