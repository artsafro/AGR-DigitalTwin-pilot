"""new-case: synthetic 3ds Max scene for the K4 agent-simulation eval and the branch U pytest (no Max, no pymxs).

`FakeScene` implements the agr_gate host (max_side/agr_gate.py): objects with handle / name / layer / user props /
mesh in metres, a selection, layers, and a transaction with Begin / Accept(label) / Cancel and an undo stack, so
"one undo record" and "rollback restores the hashes" are observable. `bad_action` lets a test make an action touch an
object outside the agent layer (the simulated misbehaving agent of acceptance К4).
Synthetic data only.
"""
import copy


def box(lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    v = [[x, y, z] for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    quads = ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5))
    return {'verts': v, 'tris': [list(t) for a, b, c, d in quads for t in ((a, b, c), (a, c, d))]}


class FakeScene:
    def __init__(self, doc='untitled'):
        self._doc = doc
        self.objs = {}
        self.layers = {'0'}
        self.sel = []
        self.next = 100
        self.undo_stack = []
        self._held = None
        self.bad_action = None  # callable(scene) run inside the next transaction (simulated outside write)

    # -- building ---------------------------------------------------------------------------------------------------
    def add(self, name, layer='0', mesh=None, props=None, pos=None):
        self.next += 1
        h = self.next
        self.layers.add(layer)
        self.objs[h] = {'name': name, 'layer': layer, 'mesh': copy.deepcopy(mesh), 'props': dict(props or {}),
                        'pos': list(pos or [0, 0, 0]), 'hidden': False}
        return h

    # -- agr_gate host ------------------------------------------------------------------------------------------------
    def doc(self):
        return self._doc

    def m_per_unit(self):
        return 1.0

    def objects(self):
        out = []
        for h, o in sorted(self.objs.items()):
            out.append({'handle': h, 'name': o['name'], 'layer': o['layer'],
                        'state': {'mesh': o['mesh'], 'props': sorted(o['props'].items()), 'pos': o['pos'],
                                  'hidden': o['hidden']}})
        return out

    def props(self, handle):
        return dict(self.objs[int(handle)]['props'])

    def mesh(self, handle):
        m = self.objs[int(handle)]['mesh']
        if m is None:
            raise ValueError('not a mesh')
        return copy.deepcopy(m)

    def selection(self):
        return list(self.sel)

    def restore_selection(self, handles):
        self.sel = [h for h in handles if h in self.objs]

    def ensure_layer(self, name):
        self.layers.add(name)

    def create_mesh(self, layer, name, verts, tris, props):
        self.sel = []  # a careless host would change the selection; the gate restores it
        return self.add(name, layer, {'verts': [list(v) for v in verts], 'tris': [list(t) for t in tris]}, props)

    def create_point(self, layer, name, pos, props):
        return self.add(name, layer, None, props, pos)

    def set_prop(self, handle, key, value):
        self.objs[int(handle)]['props'][key] = str(value)

    def set_face_ids(self, handle, faces, mat_id):
        o = self.objs[int(handle)]
        ids = o['props'].setdefault('_mat_ids', '')
        o['props']['_mat_ids'] = ids + '{}:{};'.format(mat_id, ','.join(str(f) for f in faces))

    def move_to_layer(self, handle, layer):
        self.layers.add(layer)
        self.objs[int(handle)]['layer'] = layer

    def hide(self, handle):
        self.objs[int(handle)]['hidden'] = True

    def begin(self):
        if self._held is not None:
            raise RuntimeError('already holding')
        self._held = (copy.deepcopy(self.objs), self.next)
        if self.bad_action is not None:
            act, self.bad_action = self.bad_action, None
            act(self)

    def accept(self, label):
        before, _n = self._held
        self.undo_stack.append((label, before))
        self._held = None

    def cancel(self):
        self.objs, self.next = self._held
        self._held = None

    def undo(self):
        """`max undo`: back to the state before the last accepted record."""
        label, before = self.undo_stack.pop()
        self.objs = before
        return label
