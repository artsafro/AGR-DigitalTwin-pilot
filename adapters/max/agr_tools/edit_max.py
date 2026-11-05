"""new-case: AGR Tools 0.8 edit contract, 3ds Max side (#908): pymxs helpers shared by branches A–D.

* `export_copies()` — deep copies of the working nodes under a new name (and optionally a layer); the
  working objects are never touched. Materials are copied so a copy edit cannot reach the original.
* `session(label)` — ONE undo record per run (`pymxs.undo(True, label)`) plus selection save/restore; an error
  inside the record is re-raised after it (pymxs.undo swallows it in Max 2024).
* `snapshot()` — before/after fingerprint for tests and for `edit_core.require_current`: names, transforms,
  mesh hash (vertices, faces, material IDs) per node, in handle order.

pymxs is imported lazily so this file loads under plain pytest (the logic is in edit_core.py).
"""
import contextlib
import hashlib
import struct

COPY_SUFFIX = '_AGR_export_'
EXPORT_LAYER = 'AGR_export'


def _rt():
    from pymxs import runtime
    return runtime


def handle(n):
    return int(_rt().getHandleByAnim(n))


# ---- selection + undo ---------------------------------------------------------------------------------
@contextlib.contextmanager
def keep_selection():
    """Restore the user's selection after the run (only nodes still valid)."""
    rt = _rt()
    before = list(rt.selection)
    try:
        yield before
    finally:
        rt.clearSelection()
        alive = [n for n in before if rt.isValidNode(n)]
        if alive:
            rt.select(alive)


@contextlib.contextmanager
def undo_record(label):
    """Exactly one undo record for everything inside (one Ctrl+Z removes the whole run).

    Measured (job 20261105-011438-a488a8fd, Max 2024 batch, #908 branch C): an exception inside
    `pymxs.undo(True, ...)` does not leave the `with` block, so a failed apply would carry on as a success.
    The error is caught inside the record and re-raised after the record is closed."""
    import pymxs
    failed = []
    with pymxs.undo(True, 'AGR Tools: ' + str(label)):
        try:
            yield
        except BaseException as exc:  # noqa: BLE001 - re-raised below, outside the undo context
            failed.append(exc)
    if failed:
        raise failed[0]


@contextlib.contextmanager
def session(label):
    with keep_selection() as before, undo_record(label):
        yield before


# ---- export copies ------------------------------------------------------------------------------------
def _layer(name):
    rt = _rt()
    layer = rt.LayerManager.getLayerFromName(name)
    if layer is None or layer == rt.undefined:
        layer = rt.LayerManager.newLayerFromName(name)
    return layer


def export_copies(nodes, suffix=COPY_SUFFIX, layer=None):
    """[(original, copy)] with unique names `<name><suffix>NN`; originals untouched. All or nothing."""
    rt = _rt()
    pairs = []
    target = _layer(layer) if layer else None
    try:
        for n in nodes:
            c = rt.copy(n)
            pairs.append((n, c))
            c.name = rt.uniqueName(str(n.name) + suffix)
            if n.material is not None:
                c.material = rt.copy(n.material)
            if target is not None:
                target.addNode(c)
    except Exception:
        copies = [c for _, c in pairs if rt.isValidNode(c)]
        if copies:
            rt.delete(copies)
        raise
    return pairs


# ---- before/after snapshot ----------------------------------------------------------------------------
def _matrix(tm):
    return [round(float(v), 9) for row in (tm.row1, tm.row2, tm.row3, tm.row4) for v in (row.x, row.y, row.z)]


def mesh_hash(n):
    """sha256 over vertex positions (float64), face vertex indices and material IDs of the evaluated mesh."""
    rt = _rt()
    mesh = rt.snapshotAsMesh(n)
    h = hashlib.sha256()
    nv, nf = int(mesh.numverts), int(mesh.numfaces)
    h.update(struct.pack('<II', nv, nf))
    for i in range(1, nv + 1):
        p = rt.getVert(mesh, i)
        h.update(struct.pack('<ddd', float(p.x), float(p.y), float(p.z)))
    for i in range(1, nf + 1):
        f = rt.getFace(mesh, i)
        h.update(struct.pack('<iiii', int(f.x), int(f.y), int(f.z), int(rt.getFaceMatID(mesh, i))))
    return h.hexdigest()


def snapshot(nodes):
    """[{handle, name, transform, mesh}] sorted by handle; JSON-ready for edit_core.fingerprint."""
    rt = _rt()
    out = []
    for n in nodes:
        if not rt.isValidNode(n):
            raise ValueError('invalid node in snapshot')
        geo = bool(rt.canConvertTo(n, rt.TriMeshGeometry))
        out.append({'handle': handle(n), 'name': str(n.name), 'transform': _matrix(n.transform),
                    'mesh': mesh_hash(n) if geo else None})
    return sorted(out, key=lambda x: x['handle'])
