"""#298 copy-only assembly preparation. new-case: job-local placed scene atlas adapter.

Run headless, metres; original #296 scenes and library assets are never saved.
"""
import json
import re
import sys
from pathlib import Path
import bpy
from mathutils import Matrix

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
sys.path.insert(0, str(Path(__file__).resolve().parent))
def load_library(lib):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=lib['fbx'])
    added = set(bpy.data.objects) - before
    meshes = [o for o in added if o.type == 'MESH']
    if len(meshes) != 1:
        raise RuntimeError(f"expected one light mesh: {lib['fbx']}")
    ob = meshes[0]
    loc, rot, scale = ob.matrix_world.decompose()
    ob.data = ob.data.copy()
    ob.data.transform(Matrix.Scale(lib['base_scale'], 4) @ rot.to_matrix().to_4x4() @ Matrix.Diagonal((*scale, 1)))
    ob.matrix_world = Matrix.Identity(4)
    for other in added - {ob}:
        bpy.data.objects.remove(other, do_unlink=True)
    return ob

source, outdir, profile = sys.argv[sys.argv.index('--') + 1:]
from assembly_rules import new_output
out = new_output(source, outdir)
if profile not in ('npm', 'vpm'):
    raise ValueError(f'unsupported profile {profile}')
out.mkdir(parents=True)
copy = out / 'prepared.blend'
if copy.exists():
    raise RuntimeError(f'existing output {copy}')
bpy.ops.wm.open_mainfile(filepath=source)
if bpy.context.scene.unit_settings.scale_length != 1:
    raise RuntimeError('metre units required')
instances = [o for o in bpy.data.objects if o.type == 'MESH' and o.get('library_id')]
record = {'source': source, 'profile': profile, 'replaced': {}, 'maf_materials': {}}
if profile == 'npm':
    light = json.loads((root / 'library/flora/npm-light.json').read_text())
    # The published manifest is keyed by species; retain original instance matrices and base scale.
    entries = light.get('variants', light.get('species', []))
    if isinstance(entries, dict):
        entries = list(entries.values())
    for entry in entries:
        old_id = entry['object'].removesuffix('_light')
        targets = [o for o in instances if o['library_id'] == old_id]
        if not targets:
            raise RuntimeError(f'no placed objects for {old_id}')
        spec = json.loads(Path(source).with_name('spec.json').read_text())
        base = next(x.get('base_scale', 1.0) for x in spec['libraries'] if x['id'] == old_id)
        ob = load_library({'id': old_id, 'fbx': entry['fbx'], 'base_scale': base})
        for target in targets:
            target.data = ob.data
        record['replaced'][old_id] = len(targets)
        bpy.data.objects.remove(ob, do_unlink=True)
flora, materials = [], {}
for ob in instances:
    me = ob.data
    lid = ob['library_id']
    if not lid.startswith('VAT_MAF_'):
        ids = set()
        for m in me.materials:
            match = re.search(r'ID(\d+)', m.name)
            if not match:
                raise RuntimeError(f'unmapped Flora material {m.name}')
            ids.add(int(match.group(1)))
        if len(ids) != 1:
            raise RuntimeError(f'ambiguous species IDs {ob.name}: {ids}')
        species = ids.pop()
        if 'species_id' not in me.attributes:
            me.attributes.new('species_id', 'INT', 'FACE')
        for v in me.attributes['species_id'].data:
            v.value = species
        flora.append({'name': ob.name, 'faces': [{'material_id': species, 'uvs': [list(me.uv_layers.active.data[i].uv) for i in p.loop_indices]} for p in me.polygons]})
    else:
        for m in me.materials:
            if m.name in materials:
                continue
            source_materials = json.loads(Path('C:/x/vatutino-maf/v005-set/atlas/material-list.json').read_text())['materials']
            key = re.sub(r'\.\d+$', '', m.name).removeprefix('MAF_')
            item = next((x for x in source_materials if x['name'] == key), None)
            if item is None:
                raise RuntimeError(f'unmapped MAF material {m.name}')
            materials[m.name] = item
record['maf_materials'] = {name: item['name'] for name, item in materials.items()}
(out / 'flora-placed.json').write_text(json.dumps({'schema': 'flora-placed-v1', 'objects': flora}), encoding='utf-8')
(out / 'maf-materials.json').write_text(Path('C:/x/vatutino-maf/v005-set/atlas/material-list.json').read_text(), encoding='utf-8')
(out / 'prepare.json').write_text(json.dumps(record, indent=1), encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(copy))
print('PREPARED', profile, len(instances), 'instances;', len(materials), 'MAF materials;', record['replaced'])
