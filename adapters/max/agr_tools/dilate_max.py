"""AGR Tools 1.0 (#1024), owned by branch N (improve/issue-1024-vpm-maps): map padding, 3ds Max side (tex.dilate, mode `file`).

runtime.edits_100 calls `tex_dilate(ctx, mode, nodes, preview)`.
ctx: agr (runtime globals), core (dilate_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, user props, one undo record).
The scene is read only (bitmaps and UV of the selected objects); the padded PNG copies go to a NEW folder.
Import pymxs inside functions so this file loads under plain pytest.
"""
import importlib.util
import os
import sys


def _rt():
    from pymxs import runtime
    return runtime


def _sibling(name, file):
    mod = sys.modules.get(name)
    if mod is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file)
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return mod


def _read(path):
    try:
        with open(path, 'rb') as f:
            return f.read()
    except OSError:
        return None


def _tile_faces(faces, udim):
    """UV faces (u, v) of tile `udim` moved into 0..1, for the faces whose centre lies in that tile."""
    n = int(udim) - 1001
    du, dv = n % 10, n // 10
    out = []
    for f in faces:
        cu = sum(p[0] for p in f) / len(f)
        cv = sum(p[1] for p in f) / len(f)
        if du <= cu < du + 1 and dv <= cv < dv + 1:
            out.append([(p[0] - du, p[1] - dv) for p in f])
    return out


def _sources(nodes):
    """Files and UV faces of the selected objects (their material bitmaps) when options.files is absent."""
    tm = _sibling('agr_tools_tex_max', 'tex_max.py')
    tc = _sibling('agr_tools_tex_core', 'tex_core.py')
    src = list(nodes) if nodes is not None else list(_rt().selection)
    if not src:
        raise ValueError('nothing selected: select objects with maps or give options.files (empty input is an error)')
    files, uv, owners = [], {}, {}
    for item, n in zip(tm.scene_bitmaps(tc, src), src):
        faces = None
        for r in item['rows']:
            if r['path'] not in files:
                files.append(r['path'])
            owner = [item['handle'], item['node']]
            if owner not in owners.setdefault(os.path.basename(r['path']), []):
                owners[os.path.basename(r['path'])].append(owner)
            if r['udim']:
                if faces is None:
                    faces = tm._uv_faces(n, 1)
                uv.setdefault(os.path.basename(r['path']), []).extend(_tile_faces(faces, r['udim']))
    return files, uv, owners


def tex_dilate(ctx, mode, nodes, preview):
    core, edit = ctx.core, ctx.edit
    if mode == 'preview':
        o = dict(ctx.options)
        if o.get('files') is None and o.get('folder') is None:
            o['files'], o['uv_faces'], o['owners'] = _sources(nodes)
        opts = core.dilate_options(o)
        rows = core.dilate_plan(opts, _read)
        return core.dilate_report(edit, 'preview', opts, rows, edit.fingerprint(core.dilate_state(rows, opts)))
    plan = preview['plan']
    opts = plan['options']
    rows = core.dilate_plan(opts, _read)       # re-planned from the preview options: the hash proves nothing moved
    edit.require_current(preview, core.dilate_state(rows, opts))
    written = core.write_padded(edit, rows)
    return core.dilate_report(edit, 'apply', opts, rows, None, written)
