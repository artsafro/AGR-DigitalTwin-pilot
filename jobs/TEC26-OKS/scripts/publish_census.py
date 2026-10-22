"""new-case: publish TEC26 measured census and diagnostic ID-colour views (not delivery QA)."""
import colorsys
import hashlib
import json
import math
from pathlib import Path
import shutil
import numpy as np
from PIL import Image, ImageDraw

JOB = Path(__file__).resolve().parents[1]
ROOT = Path('C:/x/tec26-oks')
NATIVE = ROOT / 'max-readback-v002'
DRIVE = Path('G:/Мой диск/AGR-evidence/tec26-oks/scene-census-v002')


def classify(name):
    if name.upper().startswith('UCX_'):
        return 'UCX_named_not_validated'
    if name.startswith(('Colizii_', 'Col_')):
        return 'collision_candidate_noncompliant_name'
    return 'surface'


def validate_scene(data):
    if not data.get('objects'):
        raise ValueError('Empty scene')
    handles = set()
    for node in data['objects']:
        if node['handle'] in handles:
            raise ValueError(f'Duplicate node handle: {node["handle"]}')
        handles.add(node['handle'])
        if node['triangles'] <= 0 or not node['material_ids']:
            raise ValueError(f'Empty mesh or material IDs: {node["name"]}')
        if sum(x['triangles'] for x in node['material_ids']) != node['triangles']:
            raise ValueError(f'Incomplete face accounting: {node["name"]}')
        mids = [x['id'] for x in node['material_ids']]
        if len(set(mids)) != len(mids):
            raise ValueError(f'Duplicate material ID: {node["name"]}')
        for entry in node['material_ids']:
            if not math.isfinite(entry['area_m2']) or entry['area_m2'] < 0:
                raise ValueError(f'Nonfinite/negative area: {node["name"]}, ID {entry["id"]}')
        err = node['snapshot_native_bbox_max_error']
        if not math.isfinite(err):
            raise ValueError(f'Nonfinite snapshot/native bbox error: {node["name"]}')
        if err > 0.00001 * data['units_per_meter'] and classify(node['name']) == 'surface':
            raise ValueError(f'Snapshot/native bbox mismatch: {node["name"]}')
    return True


def palette(mid):
    return tuple(round(x*255) for x in colorsys.hsv_to_rgb((mid*0.61803398875)%1,0.65,0.9))


def render(nodes, title, destination):
    # Native world-space vertices only, painter-sorted orthographic diagnostic views.
    # This is not an occlusion, normal, topology or visual-acceptance certificate.
    buffers = [json.loads((NATIVE/n['diagnostic_buffer']).read_text(encoding='utf-8')) for n in nodes]
    vertices, faces, mids = [], [], []
    for b in buffers:
        offset = len(vertices)
        vertices.extend(b['vertices'])
        faces.extend([[i+offset for i in f] for f in b['triangles']])
        mids.extend(b['material_ids'])
    verts = np.asarray(vertices,dtype=float)
    tri = np.asarray(faces,dtype=int)
    ids = np.asarray(mids,dtype=int)
    image = Image.new('RGB',(1800,1050),(245,245,245))
    draw = ImageDraw.Draw(image)
    draw.text((30,20),title+' | native Max snapshot; diagnostic ID colours (not RAL)',fill='black')
    for side, angle in enumerate((45,225)):
        a = math.radians(angle)
        elev = math.radians(24)
        right = np.array([math.cos(a),-math.sin(a),0.0])
        up = np.array([math.sin(a)*math.sin(elev),math.cos(a)*math.sin(elev),math.cos(elev)])
        depth = np.cross(right,up)
        xy = np.column_stack((verts@right,-verts@up))
        low, high = xy.min(axis=0), xy.max(axis=0)
        span = high-low
        scale = min(810/max(span[0],1e-9),850/max(span[1],1e-9))
        xy = (xy-(low+high)/2)*scale + np.array([450+side*900,500])
        order = np.argsort((verts@depth)[tri].mean(axis=1))
        for idx in order:
            pts = [tuple(p) for p in xy[tri[idx]]]
            draw.polygon(pts,fill=palette(int(ids[idx])))
        draw.text((40+side*900,65),'Azimuth '+str(angle)+' deg; elevation 24 deg',fill='black')
    for k,mid in enumerate(sorted(set(mids))):
        x=30+(k%12)*145; y=950+(k//12)*32
        draw.rectangle((x,y,x+25,y+18),fill=palette(mid))
        draw.text((x+30,y),f'ID {mid}',fill='black')
    with destination.open('xb') as stream:
        image.save(stream,format='PNG')
    return len(faces)


def main():
    DRIVE.mkdir(parents=True,exist_ok=False)
    native_results = {}
    manifest = []
    for name in ('oks','truba','kpp'):
        raw = NATIVE/(name+'.json')
        data = json.loads(raw.read_text(encoding='utf-8'))
        validate_scene(data)
        data['native_readback_path'] = str(raw)
        data['native_readback_sha256'] = hashlib.sha256(raw.read_bytes()).hexdigest()
        data['diagnostic_buffer_root'] = str(NATIVE)
        data['classification_policy'] = 'UCX prefix is naming only; Colizii_/Col_ are collision candidates by source labels, not validated hulls.'
        for n in data['objects']:
            n['kind'] = classify(n['name'])
            n['snapshot_bbox_parity_0_01mm'] = n['snapshot_native_bbox_max_error'] <= 0.00001 * data['units_per_meter']
            n['naming_status'] = ('review_source_names_not_delivery_names' if n['kind']=='surface' else 'review_collision_naming_and_geometry')
            for row in n['material_ids']:
                row['poly_faces'] = n['poly_faces_by_id'].get(str(row['id']),0)
        native_results[name] = data
        for target in (JOB/'census'/(name+'.json'), ROOT/'census'/(name+'-classified.json')):
            with target.open('x',encoding='utf-8') as stream:
                json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False)
        manifest.append({'path':str(raw),'sha256':data['native_readback_sha256']})
    rows = ['# Scene census','',
            'Read-only native Max 2026.3 / Python 3.11.12 on staged copies. No scene was saved.',
            'All scenes: system metres, scale 1.0, Z up. Live Max 2024 was pinged but untouched.',
            'Native process returned 4294967166 from polyunwrapper startup; wrapper tolerated it. All three scene markers and final completion marker exist; JSON content independently checked.',
            'Source layers are **004–009**, not the proposed 0.0.* spelling. No remapping or rename performed.',
            'Colizii_* / Col_* are **collision candidates**, not certified UCX. None were silently counted into surface budgets.',
            'Areas are snapshot triangle cross-product sums in m². Poly face counts come from an evaluated transient Editable Poly copy. No source node was collapsed/saved.',
            'Surface snapshot/native bbox parity <= 0.01 mm is checked; no second objectTransform is applied. Truba collision candidate Col_002 differs in Z by 0.101089 mm; it is retained as an unresolved diagnostic, not rendered or certified.',
            'UV presence/bounds do not certify valid unwrap/density. Topology health, normals, overlap and export QA are not performed by intake.','',
            '| Scene | File version data (raw Max tokens) | Surface nodes / tris | Collision candidates / tris | Other nodes |',
            '|---|---|---:|---:|---:|']
    for name,data in native_results.items():
        surface=[n for n in data['objects'] if n['kind']=='surface']
        collision=[n for n in data['objects'] if n['kind']!='surface']
        rows.append(f'| {name} | `{data["file_version"]}` | {len(surface)} / {sum(n["triangles"] for n in surface)} | {len(collision)} / {sum(n["triangles"] for n in collision)} | {len(data["other_nodes"])} |')
    for name,data in native_results.items():
        rows += ['',f'## {name}', '', '| Handle | Node | Layer | Classification | Tris | Quads / other polygon degrees | Pivot (m) | UV channels |', '|---|---|---|---|---:|---|---|---|']
        for n in data['objects']:
            rows.append(f'| {n["handle"]} | {n["name"]} | {n["layer"]} | {n["kind"]} | {n["triangles"]} | {n["evaluated_poly_face_degrees"]} | {n["pivot"]} | '+', '.join(str(x['channel'])+':'+str(x['vertices'])+' verts' for x in n['uv_channels'])+' |')
        for n in data['objects']:
            if n['kind'] != 'surface':
                continue
            rows += ['',f'### {n["name"]} (handle {n["handle"]})',f'Material: `{n["material"]["name"]}`. Full submaterial/map tree and transforms: `{name}.json`.',
                     '', '| Material ID | Poly faces | Triangles | Area m² | Candidate finish | Evidence |', '|---:|---:|---:|---:|---|---|']
            for entry in n['material_ids']:
                rows.append(f'| {entry["id"]} | {entry["poly_faces"]} | {entry["triangles"]} | {entry["area_m2"]:.6f} | ? | Material evidence delegated; no RAL inferred from viewport colour |')
    for i in range(4,10):
        nodes=[n for n in native_results['oks']['objects'] if n['layer']==f'{i:03d}' and n['kind']=='surface']
        count=render(nodes,f'AC.{i:02d}',DRIVE/f'ac{i:02d}-ids.png')
        assert count==sum(n['triangles'] for n in nodes)
    render([n for n in native_results['truba']['objects'] if n['kind']=='surface'],'truba',DRIVE/'truba-ids.png')
    (JOB/'census/scenes.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
    # Preserve all native buffers/logs outside git, with hashes and no source modification.
    shutil.copytree(NATIVE,DRIVE/'native-max-readback-v002')
    for version in ('v001','v002'):
        shutil.copy2(ROOT/f'max-run-{version}.json',DRIVE/f'max-run-{version}.json')
    sums=[]
    for path in sorted(DRIVE.rglob('*')):
        if path.is_file():
            sums.append(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.relative_to(DRIVE).as_posix())
    (DRIVE/'SHA256SUMS.txt').write_text('\n'.join(sums)+'\n',encoding='utf-8')
    manifest += [{'path':str(DRIVE/'SHA256SUMS.txt'),'sha256':hashlib.sha256((DRIVE/'SHA256SUMS.txt').read_bytes()).hexdigest()}]
    (JOB/'census/evidence.json').write_text(json.dumps({'drive':str(DRIVE),'files':len(sums),'manifest':manifest},indent=2),encoding='utf-8')
    print('Published 3 classified scene censuses; 7 two-view ID renders; all native buffers/logs on Drive.')

if __name__=='__main__':
    main()
