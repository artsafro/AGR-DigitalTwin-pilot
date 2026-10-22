"""Export an unchanged copied Max scene for colour-only UV processing.

new-case: native source FBX bridge preserves source mesh, UVs and collision hulls.
"""
import json
import os
from pathlib import Path
import pymxs

rt = pymxs.runtime
out = Path(os.environ['TEC26_BUILD'])
assert not out.exists(), f'new version required: {out}'
out.mkdir(parents=True)
print('APP', rt.maxVersion(), 'DOCUMENT', rt.maxFilePath, rt.maxFileName, 'UNITS', rt.units.SystemType)
assert str(rt.units.SystemType) == 'meters'
mesh = rt.getNodeByName('Tuba')
assert mesh != rt.undefined
cols = sorted([n for n in rt.objects if str(n.name).startswith('Col_')], key=lambda n: str(n.name))
assert len(cols) == 60
rt.execute('''fn sourceUvBounds n = (
 local result=#(); for id in #(1,2,3,5,6,7) do (
 local lo=[1e9,1e9,1e9]; local hi=[-1e9,-1e9,-1e9]; local span=[0,0,0]; local nf=0
 for i=1 to polyop.getNumFaces n where polyop.getFaceMatID n i == id do (
 nf+=1; local fl=[1e9,1e9,1e9]; local fh=[-1e9,-1e9,-1e9]
 for v in polyop.getMapFace n 1 i do (local p=polyop.getMapVert n 1 v
 for k=1 to 3 do (lo[k]=amin lo[k] p[k]; hi[k]=amax hi[k] p[k]; fl[k]=amin fl[k] p[k]; fh[k]=amax fh[k] p[k]))
 for k=1 to 3 do span[k]=amax span[k] (fh[k]-fl[k]))
 append result #(id,nf,lo,hi,span)); result)
''')
print('UV_BY_ID', rt.sourceUvBounds(mesh))
rt.select(rt.Array(mesh, *cols))
for k,v in [('Animation',False),('Cameras',False),('Lights',False),('EmbedTextures',False),('ASCII',False),('FileVersion','FBX201400'),('UpAxis','Z'),('SmoothingGroups',True),('Triangulate',False)]:
 rt.FBXExporterSetParam(k,v)
path=out/'source.fbx'
assert rt.exportFile(str(path),rt.Name('noPrompt'),selectedOnly=True,using=rt.FBXEXP)
assert path.stat().st_size>1000
print('SOURCE_EXPORTED',path,path.stat().st_size)
