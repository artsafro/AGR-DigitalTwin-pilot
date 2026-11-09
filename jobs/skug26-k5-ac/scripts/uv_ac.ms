-- K5 conditioner screens: UV channel 1 onto the 4 islands of T_K5_*_AC.1004 (texel 1300 px/m).
-- Each element = front (largest face) + 2 sides. Front: u along the viewer's right (outside view),
-- mirrored for elements whose source hole field sits on the other side. Side: u = 0 at the edge
-- shared with the front. v = height above the face's lowest vertex. Islands: #(w_m, h_m, x_px, y_px)
-- with a bottom-left pixel origin; see make_ac_tex.py. Note: MAXScript names are case-insensitive
-- (n == N, i == I) - keep loop and normal names distinct from the constants.
fn gUVAC o isl islS mirr =
(
	local T = 1300.0; local SZ = 4096.0
	local nf = polyop.getNumFaces o
	local corners = 0
	for f = 1 to nf do corners += (polyop.getFaceDeg o f)
	polyop.setNumMapVerts o 1 corners keep:false
	local mv = 0; local done = #{}; local k = 0
	for f = 1 to nf where not done[f] do
	(
		local el = polyop.getElementsUsingFace o #{f}
		done += el; k += 1
		local fl = el as array
		local fr = fl[1]
		for ff in fl where (polyop.getFaceArea o ff) > (polyop.getFaceArea o fr) do fr = ff
		local frV = polyop.getFaceVerts o fr
		local nrm = polyop.getFaceNormal o fr
		local rt = normalize (cross (-nrm) [0,0,1])
		local isM = (findItem mirr k) > 0
		for ff in fl do
		(
			local vs = polyop.getFaceVerts o ff
			local ps = for v in vs collect (polyop.getVert o v)
			local zmin = amin (for p in ps collect p.z)
			local us = #(); local isA = isl
			if ff == fr then
			(
				local ds = for p in ps collect (dot p rt)
				local dmin = amin ds; local dmax = amax ds
				us = for d in ds collect (if isM then (dmax - d) else (d - dmin))
			)
			else
			(
				isA = islS
				local sh = for v in vs where (findItem frV v) > 0 collect (polyop.getVert o v)
				local e0 = sh[1]
				local c = [0,0,0]; for p in ps do c += p; c /= ps.count
				local hd = c - e0; hd.z = 0; hd = normalize hd
				us = for p in ps collect (dot (p - e0) hd)
			)
			local ids = #()
			for j = 1 to vs.count do
			(
				mv += 1
				polyop.setMapVert o 1 mv [(isA[3] + us[j]*T)/SZ + 3.0, (isA[4] + (ps[j].z - zmin)*T)/SZ, 0]
				append ids mv
			)
			polyop.setMapFace o 1 ff ids
		)
	)
	k
)

-- Run as done on 2026-11-05 (element order = Object005 face order; mirrored list from phase.py):
-- gUVAC $Object005 #(1.2,1.944,32,32) #(0.685,1.944,1656,32) #(43,...,82,105,106,107,108)
-- gUVAC $Object004 #(1.903,0.58,32,2623) #(0.685,0.58,2570,2623) #()
