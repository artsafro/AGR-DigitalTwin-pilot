"""new-case: AGR Tools 1.0 (#1024) plug colours check, 3ds Max side. Stub of branch 0; owned by branch L (improve/issue-1024-materials).

runtime.edits_100 calls `tex_plug_colour(ctx, mode, nodes, preview)` for tex.plug_colour (plan mode `read`:
preview only, READ_100). ctx: agr (runtime globals), core (plugcolour_core), edit (edit_core), emax (edit_max),
options (dict of the preview), host (host_max.MaxHost). Import pymxs inside functions so this file loads under pytest.

Input: options.paths (files) or options.folder (its image files, not recursive), else the bitmaps of the selected
objects' materials (tex_max._scene_maps, the shared 0.8 enumerator, material records only). Files are read as bytes
(gamma 1.0): PNG/TGA by the core, JPG/BMP/TIF through .NET System.Drawing -> PNG -> tex_core (no Max bitmap slot,
so no gamma 2.2 darkening, no modal dialogs). Nothing is written or changed.
"""
import os
import shutil
import tempfile

IMAGE_EXTS = ('.png', '.tga', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')


def _rt():
    from pymxs import runtime
    return runtime


def _read(path):
    if not path or not os.path.isfile(path):
        return None
    with open(path, 'rb') as f:
        return f.read()


def _dotnet(core):
    def decode(path):
        rt = _rt()
        tmp = tempfile.mkdtemp(prefix='agr_plug_')
        try:
            bmp = rt.dotNetObject('System.Drawing.Bitmap', path)
            try:
                png = os.path.join(tmp, 'decoded.png')
                bmp.Save(png, rt.dotNetClass('System.Drawing.Imaging.ImageFormat').Png)
            finally:
                bmp.Dispose()
            with open(png, 'rb') as f:
                img, _ = core.tex_core().decode_png(f.read())
            return img
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return decode


def _node_maps(ctx, nodes):
    """{node handle: (name, [paths])} of the selected objects' material bitmaps."""
    texmax = ctx.agr._load_core('tex_max.py', 'agr_tools_tex_max')
    texcore = ctx.agr._load_core('tex_core.py', 'agr_tools_tex_core')
    records, _ = texmax._scene_maps(texcore, nodes)
    out = {}
    for n in nodes:
        out[int(ctx.emax.handle(n))] = (str(n.name), [])
    for r in records:
        if r.get('source') != 'material':
            continue
        for owner in r['owners']:
            h = owner.get('handle')
            if h in out and r['path'] not in out[h][1]:
                out[h][1].append(r['path'])
    return out


def tex_plug_colour(ctx, mode, nodes, preview):
    core, edit = ctx.core, ctx.edit
    if mode != 'preview':
        raise ValueError('tex.plug_colour is read-only: there is no apply')
    opts = core.options({k: v for k, v in ctx.options.items() if k in core.DEFAULTS})
    other = _dotnet(core)
    paths = list(ctx.options.get('paths') or ())
    folder = ctx.options.get('folder')
    if folder:
        paths += sorted(os.path.join(folder, f) for f in os.listdir(folder)
                        if os.path.splitext(f)[1].lower() in IMAGE_EXTS)
    entries, rows, ambiguous = [], [], []
    if paths:
        for p in paths:
            row = core.analyse_file(p, _read, other, opts)
            rows.append(row)
            f = core.finding_of(row)
            if f:
                ambiguous.append('{}: {}'.format(*f))
    else:
        maps = _node_maps(ctx, list(nodes or ()))
        if not maps:
            raise ValueError('tex.plug_colour: empty input (select objects or give options.paths / folder)')
        for handle, (name, files) in maps.items():
            found = []
            if not files:
                found.append(edit.finding('plug_no_map', [], 'no bitmap in the material'))
            for p in files:
                row = core.analyse_file(p, _read, other, opts)
                row['owner'] = name
                rows.append(row)
                f = core.finding_of(row)
                if f:
                    found.append(edit.finding(f[0], [], f[1]))
            entries.append(edit.entry(handle, name, found))
    if not rows and not entries:
        raise ValueError('tex.plug_colour: no files to read')
    state = {'files': [[r['file'], r.get('sha256')] for r in rows], 'options': opts}
    return core.report(edit, entries, rows, ambiguous, edit.fingerprint(state), opts)
