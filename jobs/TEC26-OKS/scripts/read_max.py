"""new-case: TEC26 native Max census on staged copies only; no scene save/export."""
import json
import math
from pathlib import Path
from collections import Counter, defaultdict
from pymxs import runtime as rt

ROOT = Path('C:/x/tec26-oks/sources-v001')
OUT = Path('C:/x/tec26-oks/max-readback-v002')
OUT.mkdir(exist_ok=False)


def vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def material(m, seen=None):
    if m is None:
        return None
    seen = set() if seen is None else seen
    handle = int(rt.getHandleByAnim(m))
    if handle in seen:
        return {'reference_handle': handle}
    seen.add(handle)
    result = {'name': str(m.name), 'class': str(rt.classOf(m)), 'handle': handle}
    maps = []
    for prop in rt.getPropNames(m):
        key = str(prop)
        if any(t in key.lower() for t in ('filename', 'bitmap', 'color', 'mapchannel')):
            try:
                value = rt.getProperty(m, prop)
                if isinstance(value, (str, int, float, bool)):
                    result[key] = value
                elif str(rt.classOf(value)) == 'Color':
                    result[key] = [float(value.r), float(value.g), float(value.b)]
            except Exception:
                pass
    for i in range(1, int(rt.getNumSubTexmaps(m)) + 1):
        child = rt.getSubTexmap(m, i)
        if child is not None:
            maps.append({'slot': i, 'slot_name': str(rt.getSubTexmapSlotName(m, i)), 'map': material(child, seen)})
    result['maps'] = maps
    subs = []
    for i in range(1, (int(rt.getNumSubMtls(m)) if str(rt.superClassOf(m)).lower() == 'material' else 0) + 1):
        entry = {'slot': i, 'material': material(rt.getSubMtl(m, i), seen)}
        if rt.isProperty(m, 'materialIDList'):
            entry['id'] = int(m.materialIDList[i-1])
        subs.append(entry)
    result['submaterials'] = subs
    return result


def inspect_node(n, meter):
    row = {'handle': int(n.handle), 'name': str(n.name), 'layer': str(n.layer.name),
           'class': str(rt.classOf(n)), 'superclass': str(rt.superClassOf(n)),
           'kind': 'UCX' if str(n.name).upper().startswith('UCX_') else 'mesh',
           'position': vec(n.pos), 'pivot': vec(n.pivot), 'scale': vec(n.scale),
           'rotation_quat': [float(n.rotation.x), float(n.rotation.y), float(n.rotation.z), float(n.rotation.w)],
           'bbox_native': [vec(n.min), vec(n.max)], 'material': material(n.material)}
    mesh = rt.snapshotAsMesh(n)
    verts = [vec(rt.getVert(mesh, i)) for i in range(1, int(mesh.numverts)+1)]
    bbox = [[min(v[a] for v in verts) for a in range(3)], [max(v[a] for v in verts) for a in range(3)]] if verts else None
    row['bbox_snapshot'] = bbox
    row['snapshot_native_bbox_max_error'] = max(abs(bbox[k][a]-row['bbox_native'][k][a]) for k in range(2) for a in range(3)) if bbox else None
    faces, ids = [], []
    counts, areas = Counter(), defaultdict(float)
    for i in range(1, int(mesh.numfaces)+1):
        f = rt.getFace(mesh, i)
        indices = [int(f.x)-1, int(f.y)-1, int(f.z)-1]
        mid = int(rt.getFaceMatID(mesh, i))
        p, q, s = [verts[j] for j in indices]
        u = [q[a]-p[a] for a in range(3)]
        v = [s[a]-p[a] for a in range(3)]
        cross = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
        area = math.sqrt(sum(t*t for t in cross)) / (2*meter*meter)
        counts[mid] += 1
        areas[mid] += area
        faces.append(indices)
        ids.append(mid)
    row['vertices'] = len(verts)
    row['triangles'] = len(faces)
    row['material_ids'] = [{'id': k, 'triangles': counts[k], 'area_m2': areas[k]} for k in sorted(counts)]
    uv = []
    for channel in range(0, int(rt.meshop.getNumMaps(mesh))):
        if rt.meshop.getMapSupport(mesh, channel):
            count = int(rt.meshop.getNumMapVerts(mesh, channel))
            item = {'channel': channel, 'vertices': count, 'faces': int(rt.meshop.getNumMapFaces(mesh, channel)), 'exists': count > 0}
            if count:
                coords = [vec(rt.meshop.getMapVert(mesh, channel, i)) for i in range(1,count+1)]
                item['bounds'] = [[min(v[a] for v in coords) for a in range(3)], [max(v[a] for v in coords) for a in range(3)]]
            uv.append(item)
    row['uv_channels'] = uv
    tmp = rt.copy(n)
    try:
        rt.convertToPoly(tmp)
        degrees = Counter(int(rt.polyop.getFaceDeg(tmp,i)) for i in range(1,int(rt.polyop.getNumFaces(tmp))+1))
        row['evaluated_poly_face_degrees'] = dict(degrees)
        pc = Counter(int(rt.polyop.getFaceMatID(tmp,i)) for i in range(1,int(rt.polyop.getNumFaces(tmp))+1))
        row['poly_faces_by_id'] = dict(pc)
    finally:
        rt.delete(tmp)
    # External diagnostic buffers are not a production model or delivery.
    with (OUT / ('geometry-'+str(n.handle)+'.json')).open('x',encoding='utf-8') as f:
        json.dump({'vertices': verts, 'triangles': faces, 'material_ids': ids}, f)
    row['diagnostic_buffer'] = 'geometry-'+str(n.handle)+'.json'
    return row


scenes = [ROOT/'Vlad_OKS/04-09 Geometry Final.max', ROOT/'Vlad_OKS/truba.max', ROOT/'KPP1_VPM_NPM_quads_v002.max']
for index, path in enumerate(scenes):
    assert path.is_file() and path.resolve().is_relative_to(ROOT.resolve())
    rt.resetMaxFile(rt.Name('noPrompt'))
    assert rt.loadMaxFile(str(path), quiet=True), str(path)
    meter = float(rt.units.decodeValue('1m'))
    result = {'source_copy': str(path), 'application_version': list(rt.maxVersion()),
              'file_version': str(rt.getMAXFileVersionData(str(path))),
              'system_unit_type': str(rt.units.SystemType), 'system_unit_scale': float(rt.units.SystemScale),
              'display_unit_type': str(rt.units.DisplayType), 'units_per_meter': meter,
              'up_axis': 'Z', 'objects': [], 'other_nodes': []}
    for n in list(rt.objects):
        if str(rt.superClassOf(n)) == 'GeometryClass':
            result['objects'].append(inspect_node(n,meter))
        else:
            result['other_nodes'].append({'handle':int(n.handle),'name':str(n.name),'class':str(rt.classOf(n)),'layer':str(n.layer.name)})
    with (OUT/['oks.json','truba.json','kpp.json'][index]).open('x',encoding='utf-8') as f:
        json.dump(result,f,ensure_ascii=False,indent=2)
    print('TEC26_SCENE_COMPLETE',path,len(result['objects']))
print('TEC26_MAX_CENSUS_COMPLETE')
