"""new-case: polygon station objects of #1024 branch U (agent.request, agent.accept).

build_scene.py calls make(obj, rt) -> node for every U.json object with `"builder": "U_build"`; obj['extra']:
{"size": [w, l, h], "at": [x, y, z]} - a Box in metres (scenes frag_u_*). The builder then writes the user property
buffer and the layer (`own_layer`): the FAIL object of agent.request lies in a layer AGENT_old (unaccepted agent work,
finding in_agent_layer). Roles set here would be overwritten by the builder (native job 20261106-050456-708506f3).
"""


def make(obj, rt):
    ex = obj.get('extra') or {}
    w, l, h = ex['size']
    node = rt.Box(name=obj['name'], width=w, length=l, height=h, mapcoords=True)
    node.pos = rt.Point3(*ex.get('at', (0.0, 0.0, 0.0)))
    return node
