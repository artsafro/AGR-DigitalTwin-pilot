"""new-case: shared MAXScript job for live and batch visual-review adapters.

Reload the saved scene and compare mesh, UV, materials and transforms.
Review cameras are not added to any delivery FBX.
Source nodes are never deleted or renamed: the review camera and target take the
first free name (Review_Camera, Review_Camera_001, ...), and the saved scene must
reproduce the geometry inventory taken before the camera was added.
"""
import json
from pathlib import Path


def render_preview(rt, path, camera="Review_Camera"):
    """Never substitute synthetic previews for a failed renderer."""
    rt.execute('render camera:(getNodeByName ' + json.dumps(camera) + ') vfb:false outputfile:'
               + json.dumps(str(path).replace(chr(92), '/')))
    if not Path(path).is_file():
        raise RuntimeError("renderer wrote no preview")


def script(config):
    values = {key: json.dumps(Path(config[key]).resolve().as_posix())
              for key in ('source', 'max_out', 'result')}
    render = ''
    if config.get('preview_png'):
        path = json.dumps(Path(config['preview_png']).resolve().as_posix())
        render = ('local bmp = render camera:reviewCam '
                  'outputSize:[640,360] vfb:false outputfile:' + path
                  + '; if bmp == undefined do throw "no rendered bitmap"; close bmp')
    selftest = ''
    if config.get('selftest'):
        selftest = ('resetMaxFile #noPrompt; units.SystemType = #meters; units.SystemScale = 1.0; '
                    'local b = Box length:2 width:2 height:2; b.material = Standardmaterial(); '
                    'if not (exportFile ' + values['source']
                    + ' #noPrompt using:FBXEXP) do throw "test FBX export failed"')
    hold = 'holdMaxFile()' if config.get('live') else ''
    restore = 'fetchMaxFile quiet:true' if config.get('live') else ''
    mode = 'live' if config.get('live') else 'batch'
    return TEMPLATE.replace('@SOURCE@', values['source']).replace('@OUTPUT@', values['max_out']).replace(
        '@REPORT@', values['result']).replace('@RENDER@', render).replace('@SELFTEST@', selftest).replace(
        '@HOLD@', hold).replace('@RESTORE@', restore).replace('@MODE@', mode)


TEMPLATE = r'''(
fn reviewInventory = (
    local rows = #()
    for obj in geometry do (
        local m = snapshotAsMesh obj
        local mat = if obj.material == undefined then "none" else obj.material.name
        append rows #(obj.name, m.numverts, m.numfaces, (getNumTVerts m), mat, obj.transform as string)
    )
    rows as string
)
local source = @SOURCE@
local output = @OUTPUT@
local success = false
local problem = ""
local cameraCount = 0
local materialCount = 0
local meshCount = 0
local inventory = ""
local maxBuild = (maxVersion())[1]
@HOLD@
try (
    @SELFTEST@
    if toLower (getFilenameType source) == ".fbx" then (
        resetMaxFile #noPrompt
        units.SystemType = #meters
        units.SystemScale = 1.0
        FBXImporterSetParam "Mode" "merge"
        if not (importFile source #noPrompt using:FBXIMP) do throw "FBX import failed"
    ) else (
        if not (loadMaxFile source quiet:true useFileUnits:true) do throw "Max load failed"
        local factor = 1.0 / (units.decodeValue "1m")
        if abs (factor - 1.0) > 0.000001 do rescaleWorldUnits factor
        units.SystemType = #meters
        units.SystemScale = 1.0
    )
    if geometry.count == 0 do throw "empty geometry"
    meshCount = geometry.count
    local sourceInventory = reviewInventory()
    local sourceNodes = objects.count
    for obj in geometry where obj.material != undefined do materialCount += 1
    if materialCount == 0 do throw "no materials"
    local lo = [1e30,1e30,1e30]
    local hi = [-1e30,-1e30,-1e30]
    for obj in geometry do (
        local bb = nodeGetBoundingBox obj (matrix3 1)
        for k = 1 to 3 do (lo[k] = amin lo[k] bb[1][k]; hi[k] = amax hi[k] bb[2][k])
    )
    local center = (lo + hi) / 2
    local radius = amax 1.0 ((distance lo hi) / 2)
    local camName = "Review_Camera"
    local targetName = "Review_Target"
    local n = 0
    while (getNodeByName camName) != undefined or (getNodeByName targetName) != undefined do (
        n += 1
        local suffix = "_" + (formattedPrint n format:"03d")
        camName = "Review_Camera" + suffix
        targetName = "Review_Target" + suffix
    )
    local cam = Targetcamera name:camName fov:45
    cam.target = Targetobject name:targetName pos:center
    cam.pos = center + radius * [1.6,-2.2,1.8]
    cameraCount = cameras.count
    if objects.count != sourceNodes + 2 do throw "review camera changed the source node set"
    inventory = reviewInventory()
    if inventory != sourceInventory do throw "review camera changed source geometry"
    if not (saveMaxFile output quiet:true) do throw "Max save failed"
    if not (loadMaxFile output quiet:true useFileUnits:true) do throw "Max readback failed"
    if geometry.count != meshCount do throw "geometry count readback mismatch"
    if objects.count != sourceNodes + 2 do throw "node count readback mismatch"
    if (reviewInventory()) != sourceInventory do throw "mesh/UV/material/transform readback mismatch"
    local reviewCam = getNodeByName camName
    if reviewCam == undefined or (classOf reviewCam) != Targetcamera do throw "review camera lost on readback"
    @RENDER@
    success = true
) catch (problem = getCurrentException())
@RESTORE@
local f = createFile @REPORT@ encoding:#utf8
if success then (
    format "{\"ok\":true,\"version\":\"3ds Max build % (@MODE@)\",\"cameras\":%,\"materials\":%,\"meshes\":%,\"readback\":true}" maxBuild cameraCount materialCount meshCount to:f
) else (
    format "{\"ok\":false,\"error\":\"Max job failed; see listener\"}" to:f
    format "Review failed: %\n" problem
)
close f
success
)
'''
