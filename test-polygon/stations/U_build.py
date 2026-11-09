"""new-case: polygon station objects of #1024 branch U (agent.request, agent.accept).

build_scene.py calls make(obj, rt) -> node for every U.json object with `"builder": "U_build"`; obj['extra']:
{"size": [w, l, h], "at": [x, y, z], "twin": bool} - a Box in metres (scenes frag_u_*). `twin: true` also makes a
second Box with the same name 3 m away (not a catalogue object): the FAIL object of agent.request, finding
duplicate_name (a common defect of source scenes). The builder writes the user property buffer and the layer after
make(), so roles / layers set here would not survive (native jobs 20261106-050456-708506f3, -050906-50ed5505).
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
