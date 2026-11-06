"""new-case: AGR Tools 1.0 (#1024) 3ds Max HostAdapter (contract_core.HostAdapter), thin pymxs glue of branch 0.

Gives the 1.0 cores plain data: ObjRef ({host, doc, handle, name}, handle = node handle of maxOps.getNodeByHandle),
world-space meshes in metres (units.SystemScale, never units.decodeValue), user properties and one undo record.
No new MAXScript globals. Import pymxs inside methods so this file loads under plain pytest.
"""
import contextlib
import os


def _rt():
    from pymxs import runtime
    return runtime


def _core():
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location('agr_tools_contract_core', os.path.join(here, 'contract_core.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class MaxHost:
    host = 'max'

    def __init__(self):
        self.contract = _core()

    def doc(self):
        rt = _rt()
        name = str(rt.maxFileName)
        return os.path.join(str(rt.maxFilePath), name) if name else 'untitled'

    def m_per_unit(self):
        return _system_scale_m(_rt())

    def refs(self, nodes):
        doc = self.doc()
        return [self.contract.obj_ref('max', doc, int(n.inode.handle), str(n.name)) for n in nodes]

    def resolve(self, refs):
        rt = _rt()
        out = []
        for ref in refs:
            ref = self.contract.check_ref(ref)
            n = rt.maxOps.getNodeByHandle(ref['handle'])
            if n is None or not rt.isValidNode(n):
                raise ValueError('unknown node handle {} ({})'.format(ref['handle'], ref['name']))
            out.append(n)
        return out

    def selection(self):
        return self.refs(list(_rt().selection))

    def mesh(self, ref):
        rt = _rt()
        node, = self.resolve([ref])
        k = self.m_per_unit()
        m = rt.snapshotAsMesh(node)
        try:
            verts = [[float(c) * k for c in (p.x, p.y, p.z)] for p in
                     (rt.getVert(m, i) for i in range(1, int(m.numverts) + 1))]
            faces, ids = [], []
            for i in range(1, int(m.numfaces) + 1):
                f = rt.getFace(m, i)
                faces.append([int(f.x) - 1, int(f.y) - 1, int(f.z) - 1])
                ids.append(int(rt.getFaceMatID(m, i)))
        finally:
            rt.delete(m)
        return {'verts': verts, 'faces': faces, 'mat_ids': ids, 'ref': ref}

    def get_prop(self, ref, key):
        rt = _rt()
        node, = self.resolve([ref])
        value = rt.getUserProp(node, key)
        return None if value is None else str(value)

    def set_prop(self, ref, key, value):
        rt = _rt()
        node, = self.resolve([ref])
        rt.setUserProp(node, key, str(value))

    @contextlib.contextmanager
    def undo(self, label):
        from pymxs import undo
        with undo(True, label):
            yield


def _system_scale_m(rt):
    """Metres per system unit from units.SystemType / units.SystemScale (IMPL.md: never units.decodeValue)."""
    per = {'millimeters': 0.001, 'centimeters': 0.01, 'meters': 1.0, 'kilometers': 1000.0,
           'inches': 0.0254, 'feet': 0.3048, 'miles': 1609.344}
    kind = str(rt.units.SystemType).lower().lstrip('#')
    if kind not in per:
        raise ValueError('unsupported units.SystemType ' + kind)
    return per[kind] * float(rt.units.SystemScale)
