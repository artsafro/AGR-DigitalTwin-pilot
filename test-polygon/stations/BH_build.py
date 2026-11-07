"""new-case: polygon station objects of #1024 branch BH (handoff.export, handoff.import, handoff.verify,
handoff.restore_materials; base 1.1).

build_scene.py calls make(obj, rt) -> node for every BH.json object with `"builder": "BH_build"`; obj['extra']:
{"size": [w, l, h], "at": [x, y, z], "twin": bool} - a Box in metres (scenes frag_bh_*). `twin: true` also makes a
second Box with the same name 3 m away (not a catalogue object): the FAIL object of handoff.export, finding
duplicate_name (the return from Blender is matched by name). Same node kind as U_build.py. The builder writes the user
property buffer and the layer after make(), so roles / layers set here would not survive.
"""




def make(obj, rt):
    ex = obj.get('extra') or {}
    w, l, h = ex['size']
    x, y, z = ex.get('at', (0.0, 0.0, 0.0))
    node = rt.Box(name=obj['name'], width=w, length=l, height=h, mapcoords=True)
    node.pos = rt.Point3(x, y, z)
    if ex.get('twin'):
        twin = rt.Box(name=obj['name'], width=w, length=l, height=h, mapcoords=True)
        twin.pos = rt.Point3(x, y + 3.0, z)
    return node
