"""new-case: polygon station objects of #1024 branch U (agent.request, agent.accept).

build_scene.py calls make(obj, rt) -> node for every U.json object with `"builder": "U_build"`; obj['extra']:
{"size": [w, l, h], "at": [x, y, z], "props": {"agr_role": ...}} - a Box (metres, scenes frag_u_*) with the given
user properties (the role contract К1: `agr_role`, an unknown role is the FAIL object of agent.request).
"""


def make(obj, rt):
    ex = obj.get('extra') or {}
    w, l, h = ex['size']
    node = rt.Box(name=obj['name'], width=w, length=l, height=h, mapcoords=True)
    node.pos = rt.Point3(*ex.get('at', (0.0, 0.0, 0.0)))
    for key, value in sorted((ex.get('props') or {}).items()):
        rt.setUserProp(node, key, str(value))
    return node
