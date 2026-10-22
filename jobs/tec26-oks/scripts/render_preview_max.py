"""Depth-correct scanline previews of the named truba scene.

Opens the already saved max (not the source copy). Hides UCX and the NPM
duplicate, draws a bar on z=0, and renders a clay view plus finish-colour views.
Does not save.

Usage: dcc_batch.py max --file render_preview_max.py --scene <truba_named.max>

new-case: depth-correct scanline renders with UCX hidden and a z=0 reference line.
"""
from __future__ import annotations

import os

import pymxs

rt = pymxs.runtime

OUT = os.environ.get("TEC26_RENDERS", r"C:/x/tec26-oks/renders")

HELPERS = r"""
fn agrProbe = (
    local s = ""
    try (s += "scan=" + ((classof (Default_Scanline_Renderer())) as string) + " ") catch (s += "scan-missing ")
    try (s += "tcam=" + ((classof (Targetcamera())) as string) + " ") catch (s += "tcam-missing ")
    try (s += "fcam=" + ((classof (Freecamera())) as string) + " ") catch (s += "fcam-missing ")
    try (s += "tdir=" + ((classof (Target_Direct())) as string) + " ") catch (s += "tdir-missing ")
    try (s += "omni=" + ((classof (Omnilight())) as string) + " ") catch (s += "omni-missing ")
    s
)
fn agrUseScanline = (
    renderers.current = Default_Scanline_Renderer()
    classof renderers.current as string
)
fn agrHide name = (
    local n = getNodeByName name
    if n != undefined do (
        n.isHidden = true
        n.renderable = false
    )
    n != undefined
)
fn agrHidePrefix prefix = (
    local c = 0
    for n in objects where (matchPattern n.name pattern:(prefix + "*")) do (
        n.isHidden = true
        n.renderable = false
        c += 1
    )
    c
)
fn agrZeroBar = (
    local b = Box length:0.12 width:80 height:0.08 name:"ZERO_000"
    b.pos = [-23, 0, 0]
    local lo = in coordsys world b.min
    local hi = in coordsys world b.max
    b.pos.z = b.pos.z - ((lo.z + hi.z) / 2.0)
    local m = Standardmaterial()
    m.name = "M_Zero_000"
    m.diffuse = color 220 30 30
    m.twoSided = true
    b.material = m
    local z0 = in coordsys world b.min.z
    local z1 = in coordsys world b.max.z
    #(z0, z1)
)
fn agrAim name px py pz tx ty tz = (
    local tgt = Targetobject name:(name + "_tgt") pos:[tx,ty,tz]
    local cam = Targetcamera name:name pos:[px,py,pz] fov:50 target:tgt
    cam.nearclip = 0.05
    cam.farclip = 5000
    cam
)
fn agrExposure = (
    backgroundColor = color 210 214 218
    ambientColor = color 60 60 60
    useEnvironmentMap = false
)
fn agrKeyLight px py pz = (
    local lamp = Omnilight name:"Key_Preview" pos:[px,py,pz] multiplier:1.3
    local fill = Omnilight name:"Fill_Preview" pos:[px-90,py+160,pz-30] multiplier:0.45
    lamp
)
fn agrShot cam path = (
    render camera:cam outputfile:path outputSize:[1280,960] vfb:off progressbar:false
    doesFileExist path
)
"""


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    rt.execute(HELPERS)
    print("PROBE", rt.agrProbe())
    rt.execute("for c in cameras do delete c\nfor L in lights do delete L\n")
    print("RENDERER", rt.agrUseScanline())
    hidden_ucx = int(rt.agrHidePrefix("UCX_"))
    hidden_npm = bool(rt.agrHide("SM_Truba_1_003_Main"))
    print("HIDDEN", hidden_ucx, hidden_npm)
    zero = list(rt.agrZeroBar())
    print("ZERO_Z", float(zero[0]), float(zero[1]))
    mesh = rt.getNodeByName("SM_Truba_1_Main")
    if mesh == rt.undefined:
        raise RuntimeError("SM_Truba_1_Main missing")
    lo = rt.execute("in coordsys world $SM_Truba_1_Main.min")
    hi = rt.execute("in coordsys world $SM_Truba_1_Main.max")
    centre = (
        (float(lo.x) + float(hi.x)) / 2,
        (float(lo.y) + float(hi.y)) / 2,
        (float(lo.z) + float(hi.z)) / 2,
    )
    cam_34 = rt.agrAim("Cam_34", centre[0] + 70, centre[1] - 90, centre[2] + 45, *centre)
    cam_side = rt.agrAim("Cam_side", centre[0] + 10, centre[1] - 120, centre[2] + 5, *centre)
    print("LIGHT", rt.agrKeyLight(centre[0] + 40, centre[1] - 60, centre[2] + 70))
    kept = mesh.material
    rt.agrExposure()
    clay = rt.Standardmaterial()
    clay.name = "M_Preview_Clay"
    clay.diffuse = rt.Color(190, 190, 190)
    clay.twoSided = True
    mesh.material = clay
    shaded = os.path.join(OUT, "truba_shaded.png").replace("\\", "/")
    finishes = os.path.join(OUT, "truba_finishes.png").replace("\\", "/")
    base = os.path.join(OUT, "truba_finishes_base.png").replace("\\", "/")
    print("SHADED", bool(rt.agrShot(cam_34, shaded)))
    mesh.material = kept
    if rt.isProperty(kept, "numsubs"):
        count = int(kept.numsubs)
        for index in range(count):
            sub = kept.materialList[index]
            if sub == rt.undefined:
                continue
            try:
                sub.twoSided = True
            except Exception as exc:
                print("TWOSIDE", exc)
            for prop in ("glossinessMapEnable", "specularLevelMapEnable", "bumpMapEnable"):
                try:
                    setattr(sub, prop, False)
                except Exception as exc:
                    print("MAP_OFF", prop, exc)
    print("FINISHES", bool(rt.agrShot(cam_34, finishes)))
    print("BASE", bool(rt.agrShot(cam_side, base)))
    for path in (shaded, finishes, base):
        print("FILE", path, os.path.getsize(path) if os.path.isfile(path) else 0)
    print("RENDER_OK")


main()
