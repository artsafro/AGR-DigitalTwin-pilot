"""new-case: AGR Tools 1.0 (#1024) glass planes, 3ds Max side. owned by branch H (improve/issue-1024-grid-glass).

runtime.edits_100 calls `model_glass_planes(ctx, mode, nodes, preview)` for model.glass_planes (plan mode `copy`).
ctx: agr (runtime globals), core (glass_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, user props, one undo record). pymxs is imported inside functions.

Preview reads each glass node as data (gridclean_max.read_poly: no scene change) and runs glass_core.planes. Apply makes
ONE export copy per node (layer AGR_export, one undo record, selection restored), rebuilds it from the planes, marks
it `agr_role = glass` (contract_core К1; the glass is a separate mesh with its own UDIM numbering from 1001, owner
answer В9 06.11.2026) and reads it back: every face a quad, MatIDs kept. The working object is never touched.
"""
import importlib.util
import os

TOOL = 'model.glass_planes'
SUFFIX = '_AGR_glass_'
EXPORT_LAYER = 'AGR_export'
_GRID = None


def grid():
    """gridclean_max (read / rebuild helpers of the same owner), loaded once by path."""
    global _GRID
    if _GRID is None:
        here = os.path.dirname(os.path.abspath(__file__))
        spec = importlib.util.spec_from_file_location('agr_tools_gridclean_max_for_glass',
                                                      os.path.join(here, 'gridclean_max.py'))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _GRID = mod
    return _GRID


def _rt():
    from pymxs import runtime
    return runtime


def model_glass_planes(ctx, mode, nodes, preview):
    """Glass to planes on export copies: one quad per flat window, a quad per bend segment, corners on one edge."""
    edit, emax, core = ctx.edit, ctx.emax, ctx.core
    g = grid()
    k = float(ctx.host.m_per_unit())
    if mode == 'preview':
        opts = core.options(ctx.options)
        nodes = g.targets(nodes)
        rows, objects, done, skipped, ambiguous, work = [], [], [], [], [], []
        for n in nodes:
            name = str(n.name)
            if not g.convertible(n):
                skipped.append(edit.skipped(name, 'not a geometry object that converts to Editable Poly'))
                continue
            mesh, _, _ = g.read_poly(n, k)
            if not mesh['faces']:
                skipped.append(edit.skipped(name, 'no polygons'))
                continue
            res = core.planes(mesh, opts)
            work.append(n)
            objects.append(edit.entry(g.node_handle(n), name,
                                      [edit.finding(code, (), detail) for code, detail in res['findings']]))
            ambiguous.extend('{}: {}'.format(name, a) for a in res['ambiguous'])
            c = res['counts']
            rows.append({'handle': g.node_handle(n), 'name': name, 'counts': c,
                         'glass_from_frame_m': res['glass_from_frame_m'],
                         'udim_tiles': core.udim_tiles(res['mesh'])})
            done.append('{}: {} faces -> {} ({} quads), frame {} / thin {} dropped, {} stack(s) to one plane, '
                        '{} corner(s)'.format(name, c['faces_before'], c['faces_after'], c['quads'], c['frame_faces'],
                                              c['thin_faces'], c['stacks_collapsed'], c['slivers'] + c['stitched']))
        st = g.state(emax, work, opts)
        return edit.report(TOOL, 'preview', objects=objects, done=done, skipped_=skipped, ambiguous=ambiguous,
                           state_hash=edit.fingerprint(st),
                           extra={'handles': [r['handle'] for r in rows], 'rows': rows, 'options': opts,
                                  'layer': EXPORT_LAYER, 'm_per_unit': k})
    opts = preview['plan']['options']
    nodes = g.from_preview(preview)
    edit.require_current(preview, g.state(emax, nodes, opts))
    rt = _rt()
    host = ctx.host
    objects, done, copies = [], [], []
    with emax.session(TOOL):
        pairs = emax.export_copies(nodes, suffix=SUFFIX, layer=EXPORT_LAYER)
        for (n, c), row in zip(pairs, preview['plan']['rows']):
            rt.convertTo(c, rt.Editable_Poly)
            mesh, _, _ = g.read_poly(c, k)
            res = core.planes(mesh, opts)
            findings = []
            bad = g.rebuild(c, res['mesh'], k)
            if bad:
                findings.append(edit.finding('rebuild_failed', (), '{} polygon(s) not created'.format(bad)))
            host.set_role(host.refs([c])[0], 'glass')
            back, _, _ = g.read_poly(c, k)
            sizes = sorted({len(f['v']) for f in back['faces']})
            if sizes != [4]:
                findings.append(edit.finding('glass_not_quad', (), 'face sizes {} on the copy'.format(sizes)))
            mats_before = sorted({f['mat'] for f in res['mesh']['faces']})
            mats_after = sorted({f['mat'] for f in back['faces']})
            if mats_before != mats_after:
                findings.append(edit.finding('mat_ids', (), '{} -> {}'.format(mats_before, mats_after)))
            if bool(back['uv']) != bool(res['mesh']['uv']):
                findings.append(edit.finding('uv_lost', (), 'map channel 1 on the copy: {}'.format(back['uv'])))
            objects.append(edit.entry(g.node_handle(c), str(c.name), findings))
            done.append('{} -> {}: {} faces -> {} quads'.format(row['name'], str(c.name), res['counts']['faces_before'],
                                                                len(back['faces'])) if not findings else
                        '{} -> {}: see findings'.format(row['name'], str(c.name)))
            copies.append({'source': row['name'], 'copy': str(c.name), 'handle': g.node_handle(c),
                           'faces': len(back['faces']), 'udim_tiles': core.udim_tiles(back)})
    return edit.report(TOOL, 'apply', objects=objects, done=done, skipped_=preview['plan']['skipped'],
                       ambiguous=list(preview['plan']['ambiguous']),
                       extra={'copies': copies, 'layer': EXPORT_LAYER, 'options': opts})
