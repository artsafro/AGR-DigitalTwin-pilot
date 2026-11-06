"""new-case: 3ds Max host of the D108 gate (agr_gate.GateHost) on pymxs, branch U (#1024 К4). Runs INSIDE Max.

Thin: every decision is in agr_gate.py. Units: metres <-> system units by units.SystemType/SystemScale (never
units.decodeValue). Handles are node handles (maxOps.getNodeByHandle), as ObjRef. The transaction is theHold:
Begin -> Accept(label) gives ONE undo record; Cancel restores what was held, including nodes created inside it.
An object's state for the hashes: class, transform, mesh (vertex positions rounded to 1e-6 system units, faces,
material IDs), material name, parent, hidden flag and the user property buffer. No MAXScript globals are created.
"""
import hashlib
import json

_UNITS = {'millimeters': 0.001, 'centimeters': 0.01, 'meters': 1.0, 'kilometers': 1000.0, 'inches': 0.0254,
          'feet': 0.3048, 'miles': 1609.344}


def _rt():
    from pymxs import runtime
    return runtime


def m_per_unit(rt=None):
    rt = rt or _rt()
    kind = str(rt.units.SystemType).lower().lstrip('#')
    if kind not in _UNITS:
        raise ValueError('unsupported units.SystemType ' + kind)
    return _UNITS[kind] * float(rt.units.SystemScale)


class MaxGateHost:
    """agr_gate host on the open Max scene."""

    def __init__(self, rt=None):
        self.rt = rt or _rt()
        self._saved, self._created, self._faces = {}, [], {}
        self.nested = False

    # -- reading -----------------------------------------------------------------------------------------------------
    def doc(self):
        rt = self.rt
        import os
        name = str(rt.maxFileName)
        return os.path.join(str(rt.maxFilePath), name) if name else 'untitled'

    def m_per_unit(self):
        return m_per_unit(self.rt)

    def node(self, handle):
        n = self.rt.maxOps.getNodeByHandle(int(handle))
        if n is None or not self.rt.isValidNode(n):
            raise ValueError('unknown node handle ' + str(handle))
        return n

    def _mesh_digest(self, n):
        rt = self.rt
        if not rt.canConvertTo(n, rt.TriMeshGeometry):
            return None
        m = rt.snapshotAsMesh(n)
        try:
            h = hashlib.sha256()
            nv, nf = int(m.numverts), int(m.numfaces)
            h.update('{} {}|'.format(nv, nf).encode())
            for i in range(1, nv + 1):
                p = rt.getVert(m, i)
                h.update('{:.6f},{:.6f},{:.6f};'.format(float(p.x), float(p.y), float(p.z)).encode())
            for i in range(1, nf + 1):
                f = rt.getFace(m, i)
                h.update('{},{},{},{};'.format(int(f.x), int(f.y), int(f.z), int(rt.getFaceMatID(m, i))).encode())
            return h.hexdigest()
        finally:
            rt.delete(m)

    def _state(self, n):
        rt = self.rt
        tm = n.transform
        rows = [tm.row1, tm.row2, tm.row3, tm.row4]
        parent = n.parent
        mat = n.material
        return {'class': str(rt.classOf(n)),
                'tm': [[round(float(c), 6) for c in (r.x, r.y, r.z)] for r in rows],
                'mesh': self._mesh_digest(n),
                'material': None if mat is None else str(mat.name),
                'parent': None if parent is None else int(parent.inode.handle),
                'hidden': bool(n.isHidden),
                'props': str(rt.getUserPropBuffer(n))}

    def objects(self):
        return [{'handle': int(n.inode.handle), 'name': str(n.name), 'layer': str(n.layer.name),
                 'state': self._state(n)} for n in self.rt.objects]

    def props(self, handle):
        rt = self.rt
        n = self.node(handle)
        out = {}
        for key in ('agr_role', 'agr_opening', 'agr_window_type', 'agr_agent_source', 'agr_agent_op',
                    'agr_agent_request', 'agr_agent_preview'):
            v = rt.getUserProp(n, key)
            if v is not None:
                out[key] = str(v)
        return out

    def mesh(self, handle):
        """{'verts': [[x, y, z]] metres world, 'tris': [[i, j, k]] 0-based, 'mat_ids': [...]} of a node."""
        rt = self.rt
        n = self.node(handle)
        k = self.m_per_unit()
        m = rt.snapshotAsMesh(n)
        try:
            verts = [[float(c) * k for c in (p.x, p.y, p.z)]
                     for p in (rt.getVert(m, i) for i in range(1, int(m.numverts) + 1))]
            tris, ids = [], []
            for i in range(1, int(m.numfaces) + 1):
                f = rt.getFace(m, i)
                tris.append([int(f.x) - 1, int(f.y) - 1, int(f.z) - 1])
                ids.append(int(rt.getFaceMatID(m, i)))
        finally:
            rt.delete(m)
        return {'verts': verts, 'tris': tris, 'mat_ids': ids}

    def selection(self):
        return [int(n.inode.handle) for n in self.rt.selection]

    def restore_selection(self, handles):
        rt = self.rt
        live = []
        for h in handles:
            n = rt.maxOps.getNodeByHandle(int(h))
            if n is not None and rt.isValidNode(n):
                live.append(n)
        rt.clearSelection()
        if live:
            rt.select(live)

    # -- writing (inside begin/accept|cancel) ----------------------------------------------------------------------
    def ensure_layer(self, name):
        rt = self.rt
        layer = rt.LayerManager.getLayerFromName(name)
        if layer is None:
            layer = rt.LayerManager.newLayerFromName(name)
        return layer

    def _put(self, node, layer, props):
        self.ensure_layer(layer).addNode(node)
        for key, value in sorted((props or {}).items()):
            self.rt.setUserProp(node, key, str(value))
        h = int(node.inode.handle)
        self._created.append(h)
        return h

    def create_mesh(self, layer, name, verts_m, tris, props):
        rt = self.rt
        k = self.m_per_unit()
        verts = rt.Array(*[rt.Point3(v[0] / k, v[1] / k, v[2] / k) for v in verts_m])
        faces = rt.Array(*[rt.Point3(int(t[0]) + 1, int(t[1]) + 1, int(t[2]) + 1) for t in tris])
        node = rt.mesh(name=name, vertices=verts, faces=faces)
        rt.update(node)
        return self._put(node, layer, props)

    def create_point(self, layer, name, pos_m, props):
        rt = self.rt
        k = self.m_per_unit()
        node = rt.Point(name=name, pos=rt.Point3(pos_m[0] / k, pos_m[1] / k, pos_m[2] / k), size=0.2 / k)
        return self._put(node, layer, props)

    def set_prop(self, handle, key, value):
        n = self.node(handle)
        self._saved.setdefault(int(handle), str(self.rt.getUserPropBuffer(n)))  # compensation for cancel()
        self.rt.setUserProp(n, key, str(value))

    def set_face_ids(self, handle, faces, mat_id):
        rt = self.rt
        n = self.node(handle)
        if not rt.isKindOf(n, rt.Editable_Mesh):
            raise ValueError('set_face_ids needs an Editable_Mesh in the agent layer: ' + str(n.name))
        old = self._faces.setdefault(int(handle), {})
        for f in faces:
            old.setdefault(int(f), int(rt.getFaceMatID(n, int(f) + 1)))
            rt.setFaceMatID(n, int(f) + 1, int(mat_id))
        rt.update(n)

    def move_to_layer(self, handle, layer):
        self.ensure_layer(layer).addNode(self.node(handle))

    def hide(self, handle):
        self.node(handle).isHidden = True

    def begin(self):
        """Open the transaction. Not holding (GUI Max between commands): theHold.Begin -> Accept(label) is ONE undo
        record, Cancel restores. Already holding (batch Max runs the script inside a hold, native job
        20261106-045917-c65df697): theHold.Cancel would also restore the caller's earlier work (it moved and
        un-created objects of the script), so a nested transaction never calls Begin/Cancel: its rollback is the
        explicit compensation below and its changes merge into the open hold. The gate proves either way."""
        rt = self.rt
        self.nested = bool(rt.theHold.Holding())
        self._saved, self._created, self._faces = {}, [], {}
        if not self.nested:
            rt.theHold.Begin()

    def accept(self, label):
        if not self.nested:
            self.rt.theHold.Accept(label)

    def cancel(self):
        """theHold.Cancel (not nested), then the explicit compensation of this transaction's own actions: created
        nodes deleted, user property buffers and face material IDs put back."""
        rt = self.rt
        if not self.nested:
            rt.theHold.Cancel()
        for h in reversed(self._created):
            n = rt.maxOps.getNodeByHandle(h)
            if n is not None and rt.isValidNode(n):
                rt.delete(n)
        for h, buf in sorted(self._saved.items()):
            n = rt.maxOps.getNodeByHandle(h)
            if n is not None and rt.isValidNode(n) and str(rt.getUserPropBuffer(n)) != buf:
                rt.setUserPropBuffer(n, buf)
        for h, ids in sorted(self._faces.items()):
            n = rt.maxOps.getNodeByHandle(h)
            if n is not None and rt.isValidNode(n):
                for f, mid in sorted(ids.items()):
                    rt.setFaceMatID(n, f + 1, mid)
                rt.update(n)
        self._saved, self._created, self._faces = {}, [], {}


def dumps(value):
    return json.dumps(value, sort_keys=True, allow_nan=False)
