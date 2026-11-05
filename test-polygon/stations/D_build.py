"""new-case: polygon builder of branch D (#979): light nodes for the light.check stations.

`make(obj, rt) -> node` is called by build/build_scene.py for objects with `builder: "D_build"`. The light class
and the unit system come from `extra`: {"light": "Omnilight" | "freeSpot" | "targetSpot" | "Free_Light" |
"Directionallight" | "Skylight", "units": "meters" | "centimeters"}. `pos` is in METRES; in a centimetre scene the
node is placed at pos x 100 system units, so the same physics is checked in both unit systems.
"""

SCALE = {'meters': 1.0, 'centimeters': 100.0}


def make(obj, rt):
    extra = obj.get('extra') or {}
    units = extra.get('units', 'meters')
    if units not in SCALE:
        raise ValueError('D_build: unknown units ' + repr(units))
    if str(rt.units.SystemType).lower() != units:
        rt.units.SystemType = rt.Name(units)
        rt.units.SystemScale = 1.0
    cls = extra.get('light')
    maker = {'Omnilight': rt.Omnilight, 'freeSpot': rt.freeSpot, 'targetSpot': rt.targetSpot,
             'Free_Light': rt.Free_Light, 'Directionallight': rt.Directionallight, 'Skylight': rt.Skylight}.get(cls)
    if maker is None:
        raise ValueError('D_build: unknown light class ' + repr(cls))
    node = maker(name=obj['name'])
    k = SCALE[units]
    node.pos = rt.Point3(*(float(v) * k for v in obj['pos']))
    return node
