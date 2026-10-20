"""Fail-closed Flora light-variant evidence and alpha-aware reduction (#347).

Pattern: n/a | new-case: append-only NPM light variants with five-view alpha coverage.
"""
from __future__ import annotations


import copy
import math
import re
from pathlib import Path

POINTS = {105: 38, 204: 325, 103: 29}  # #347 fallback: #296 report not yet merged
REST_TRIANGLES = 41420
VIEWS = ('top', 'front', 'side', 'front45', 'side45')
METHOD = 'alpha-aware source triangle subset'
KEYS = {'material_id', 'object', 'file', 'sha256', 'fbx', 'fbx_sha256', 'triangles',
        'height_m', 'crown_diameter_m', 'method', 'maps', 'silhouettes'}


def number(value, label, minimum=0, maximum=float('inf')):
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or
            not math.isfinite(value) or not minimum <= value <= maximum):
        raise ValueError('invalid ' + label)
    return value


def validate_records(catalogue, document):
    """Validate the complete three-species evidence; return weighted slice triangles."""
    if not isinstance(document, dict) or set(document) != {'schema', 'variants'}:
        raise ValueError('partial light document')
    if document['schema'] != 'flora-npm-light-v1' or not isinstance(document['variants'], list):
        raise ValueError('unsupported light schema')
    rows = {s['material_id']: s for s in catalogue['species']}
    seen = set(); total = REST_TRIANGLES
    for row in document['variants']:
        if not isinstance(row, dict) or set(row) != KEYS:
            raise ValueError('partial light record (including read-back triangles) or unsupported key')
        mid = row['material_id']
        if type(mid) is not int or mid not in POINTS or mid in seen or mid not in rows:
            raise ValueError('unsupported or duplicate material_id')
        seen.add(mid); source = rows[mid]
        if row['object'] != source['objects']['NPM'] + '_light' or row['method'] != METHOD:
            raise ValueError('unsupported object or method')
        if row['maps'] != {k: source['maps'][k] for k in ('diffuse', 'opacity')}:
            raise ValueError('maps changed')
        for key in ('sha256', 'fbx_sha256'):
            if not isinstance(row[key], str) or not re.fullmatch('[0-9a-f]{64}', row[key]):
                raise ValueError('invalid ' + key)
        for key, ext in (('file', '.max'), ('fbx', '.fbx')):
            if not isinstance(row[key], str) or not row[key].startswith('C:/x/flora-light/v001/') or not row[key].endswith(ext) or '..' in row[key].split('/'):
                raise ValueError('unsupported output path')
        tris = row['triangles']
        if type(tris) is not int or tris <= 0:
            raise ValueError('missing or invalid read-back triangles')
        total += POINTS[mid] * tris
        for key in ('height_m', 'crown_diameter_m'):
            number(row[key], key, source[key] * 0.95, source[key] * 1.05)
        metrics = row['silhouettes']
        if not isinstance(metrics, dict) or set(metrics) != set(VIEWS):
            raise ValueError('missing silhouette view')
        for view, metric in metrics.items():
            if not isinstance(metric, dict) or set(metric) != {'iou', 'hausdorff_upper_m'}:
                raise ValueError('partial silhouette metric: ' + view)
            number(metric['iou'], 'silhouette IoU: ' + view, 0.85, 1)
            number(metric['hausdorff_upper_m'], 'silhouette Hausdorff: ' + view,
                   0, 0.1 * min(source['crown_diameter_m'], row['crown_diameter_m']))
    if seen != set(POINTS):
        raise ValueError('exactly three light variants required')
    if total > 70000:
        raise ValueError(f'Flora budget exceeded: {total} > 70000')
    return total


def append_light(catalogue, document, previous):
    """Append only: regeneration and existing light records must be value-identical."""
    def stripped(value):
        result = copy.deepcopy(value)
        for row in result['species']:
            row.pop('npm_light', None)
        return result
    if stripped(catalogue) != stripped(previous):
        raise ValueError('would change existing catalogue key/value')
    validate_records(catalogue, document)
    result = copy.deepcopy(catalogue)
    records = {r['material_id']: r for r in document['variants']}
    old = {s['material_id']: s for s in previous['species']}
    for row in result['species']:
        mid = row['material_id']
        if mid in records:
            if 'npm_light' in old[mid] and old[mid]['npm_light'] != records[mid]:
                raise ValueError('would change existing npm_light key/value')
            row['npm_light'] = copy.deepcopy(records[mid])
    return result


def validate_binding(species, mesh):
    """FBX renumbers a single material to slot 0; retain the stable ID in its material name."""
    import ntpath
    expected = species['objects']['NPM'][:-4] + '_ID' + str(species['material_id'])
    if mesh['materials'] != [expected] or mesh['material_indices'] != [0]:
        raise ValueError('FBX species material identity changed')
    paths = {ntpath.normcase(ntpath.normpath(p)) for p in mesh['images']}
    if paths != {ntpath.normcase(ntpath.normpath(species['maps'][k])) for k in ('diffuse','opacity')}:
        raise ValueError('FBX species maps changed')


def guard_output(output, inputs):
    """Never write into an existing version, an input, or an input's ancestor."""
    dest = Path(output).resolve()
    if dest.exists():
        raise ValueError('output already exists; refuse overwrite: ' + str(dest))
    for source in inputs:
        src = Path(source).resolve()
        if dest == src or dest in src.parents:
            raise ValueError('output resolves to input or its ancestor')


def _arrays(mesh):
    import numpy as np
    v = np.asarray(mesh['vertices'], dtype=float)
    f = np.asarray(mesh['faces'])
    uv = np.asarray(mesh['uv'], dtype=float)
    if (v.ndim != 2 or v.shape[1:] != (3,) or not len(v) or
            f.ndim != 2 or f.shape[1:] != (3,) or not len(f) or
            not np.issubdtype(f.dtype, np.integer) or f.min() < 0 or f.max() >= len(v) or
            uv.shape != (len(f), 3, 2) or not np.isfinite(v).all() or not np.isfinite(uv).all()):
        raise ValueError('empty or invalid mesh/UV evidence')
    return v, f, uv


def _project(vertices, view):
    import numpy as np
    v = vertices.copy()
    if view.endswith('45'):
        c = math.sqrt(0.5)
        v[:, :2] = v[:, :2] @ np.array([[c,c],[-c,c]])
    return v[:, [0,1] if view == 'top' else ([0,2] if view.startswith('front') else [1,2])]


def _pixels(mesh, opacity, view, box, resolution):
    """Nearest-neighbour, 128 cutout; two-sided union, repeated UVs; common world frame."""
    import numpy as np
    v, f, uv = _arrays(mesh)
    lo, hi = box
    extent = hi - lo
    if np.any(extent <= 0) or resolution < 16:
        raise ValueError('empty projection or unsupported resolution')
    p = (_project(v, view) - lo) / extent * (resolution - 5) + 2
    if opacity.ndim != 2 or not opacity.size:
        raise ValueError('empty opacity map')
    result = []
    for face, tex in zip(f, uv):
        a,b,c = p[face]
        low = np.maximum(np.floor(np.minimum(np.minimum(a,b),c)).astype(int), 0)
        high = np.minimum(np.ceil(np.maximum(np.maximum(a,b),c)).astype(int), resolution-1)
        den = (b[1]-c[1])*(a[0]-c[0]) + (c[0]-b[0])*(a[1]-c[1])
        if abs(den) < 1e-12 or np.any(high < low):
            result.append(np.array([], dtype=int)); continue
        x,y = np.meshgrid(np.arange(low[0],high[0]+1)+.5, np.arange(low[1],high[1]+1)+.5)
        u = ((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/den
        w = ((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/den
        coords = u[...,None]*tex[0] + w[...,None]*tex[1] + (1-u-w)[...,None]*tex[2]
        tx = (np.mod(coords[...,0],1)*(opacity.shape[1]-1)).astype(int)
        ty = ((1-np.mod(coords[...,1],1))*(opacity.shape[0]-1)).astype(int)
        good = (u>=-1e-8)&(w>=-1e-8)&(1-u-w>=-1e-8)&(opacity[ty,tx]>=128)
        yy,xx = np.nonzero(good)
        result.append((yy+low[1])*resolution + xx+low[0])
    return result


def select_faces(mesh, opacity, resolution=512, target=.89):
    """Deterministic weighted set cover of original triangles, no invented geometry or UVs."""
    import numpy as np
    number(target, 'coverage target', .85, 1)
    v,f,_ = _arrays(mesh)
    per_face = [[] for _ in f]; areas = []; unions = []; radii = []
    crown = float(np.ptp(v,axis=0)[:2].max())
    for vi, view in enumerate(VIEWS):
        p = _project(v, view); box = (p.min(0), p.max(0))
        pixels = _pixels(mesh, opacity, view, box, resolution)
        union = np.zeros(resolution**2, bool)
        for i, ids in enumerate(pixels):
            per_face[i].append(ids + vi*resolution**2); union[ids] = True
        if not union.any():
            raise ValueError('empty alpha-masked reference: ' + view)
        areas.append(int(union.sum())); unions.append(union)
        diagonal = float(np.linalg.norm((box[1]-box[0])/(resolution-5)))
        radii.append(max(0, int(.06*crown/diagonal)-1))
    pixels = [np.concatenate(p) for p in per_face]
    weights = np.repeat(1/np.array(areas), resolution**2)
    covered = np.zeros(5*resolution**2, bool); chosen = set()
    # Retain faces at all extrema: exact dimensions and the D100 lowest-point/pivot frame.
    for axis in range(3):
        for extreme in (v[:,axis].min(), v[:,axis].max()):
            vertex = int(np.flatnonzero(v[:,axis] == extreme)[0])
            face = int(np.flatnonzero(np.any(f == vertex, axis=1))[0])
            chosen.add(face); covered[pixels[face]] = True
    for _ in f:
        ratios = covered.reshape(5,-1).sum(1)/areas
        if min(ratios) >= target:
            # IoU alone can omit a thin stem. Cover every reference pixel within a
            # conservative 6%-crown raster reach before declaring selection complete.
            far = []
            for vi, radius in enumerate(radii):
                mask = covered.reshape(5,resolution,resolution)[vi].copy()
                for _ in range(radius):
                    pad = np.pad(mask,1)
                    mask = np.logical_or.reduce([pad[y:y+resolution,x:x+resolution] for y in range(3) for x in range(3)])
                far.append(unions[vi] & ~mask.ravel())
            need = np.concatenate(far)
            if not need.any():
                return sorted(chosen)
        else:
            need = np.repeat(ratios < target, resolution**2)
        scores = [-1 if i in chosen else float(weights[p[~covered[p]&need[p]]].sum()) for i,p in enumerate(pixels)]
        best = int(np.argmax(scores))
        if scores[best] <= 0:
            raise ValueError('cannot reach silhouette coverage')
        chosen.add(best); covered[pixels[best]] = True
    raise ValueError('coverage selection exhausted')


def measure(reference, candidate, opacity, resolution=1024, images=None):
    """Five-view alpha IoU and a conservative raster Hausdorff upper bound, in metres.

    Square-pixel dilation reaches a matching opaque pixel in k steps, at distance at most
    k*pixel_diagonal. Add one diagonal for finite sampling. This is an upper bound, not an
    exact continuous-opacity Hausdorff estimate; gate it against the same 10% crown limit.
    """
    import numpy as np
    from PIL import Image
    a,_,_ = _arrays(reference); b,_,_ = _arrays(candidate)
    scores = {}
    for view in VIEWS:
        p = np.concatenate([_project(a, view), _project(b, view)])
        box = (p.min(0), p.max(0)); masks = []
        for mesh in (reference, candidate):
            m = np.zeros(resolution**2, bool)
            for ids in _pixels(mesh, opacity, view, box, resolution):
                m[ids] = True
            masks.append(m.reshape(resolution,resolution))
        ma,mb = masks
        if not ma.any() or not mb.any():
            raise ValueError('empty alpha silhouette: ' + view)
        distance = 0
        for left,right in ((ma,mb),(mb,ma)):
            dilated = right.copy(); steps = 0
            while np.any(left & ~dilated):
                pad = np.pad(dilated,1)
                dilated = np.logical_or.reduce([pad[y:y+resolution,x:x+resolution] for y in range(3) for x in range(3)])
                steps += 1
            distance = max(distance, steps)
        diagonal = float(np.linalg.norm((box[1]-box[0])/(resolution-5)))
        scores[view] = {'iou': float((ma&mb).sum()/(ma|mb).sum()), 'hausdorff_upper_m': (distance+1)*diagonal}
        if images:
            for label,m in zip(('source','light'),masks):
                path = Path(images) / (view+'-'+label+'.png')
                path.parent.mkdir(parents=True,exist_ok=True)
                Image.fromarray(np.flipud(m.astype('uint8')*255)).save(path)
    return scores


def main():
    import argparse
    import json
    parser = argparse.ArgumentParser(description='Check complete Flora light evidence without DCC')
    parser.add_argument('--catalogue', required=True)
    parser.add_argument('--input', required=True)
    args = parser.parse_args()
    try:
        cat = json.loads(Path(args.catalogue).read_text(encoding='utf-8'))
        document = json.loads(Path(args.input).read_text(encoding='utf-8'))
        print('Flora NPM triangles:', validate_records(cat, document))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(1, str(exc)+'\n')


if __name__ == '__main__':
    main()
