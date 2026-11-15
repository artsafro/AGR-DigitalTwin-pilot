"""new-case: #1380 synthetic Blender bmesh parity and cut-policy probes; no scene/file mutation.

Run through dt_ai.core.blender_runner, passing NEW report.json and frozen old vpm_uv.py.
"""
import importlib.util
import json
import math
import sys
from pathlib import Path

import bpy
import bmesh

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/blender'))
import vpm_uv as owner

args = sys.argv[sys.argv.index('--') + 1:]
output, old_source = map(Path, args)
specmod = importlib.util.spec_from_file_location('uv_before_1380', old_source)
old = importlib.util.module_from_spec(specmod)
specmod.loader.exec_module(old)
assert bpy.app.version[:2] == (5, 1), bpy.app.version_string
initial = (bpy.data.filepath, len(bpy.data.objects), bpy.context.scene.unit_settings.system)
checks = 0


def mesh(length=1.0):
    bm = bmesh.new()
    verts = [bm.verts.new(p) for p in [(0.1, 0.1, 0), (length + 0.1, 0.1, 0),
                                    (length + 0.1, 1.1, 0), (0.1, 1.1, 0)]]
    layer = bm.faces.layers.int.new('finish')
    face = bm.faces.new(verts)
    face[layer] = 0
    bm.normal_update()
    return bm


def packed(mod, spec, glass=False):
    bm = mesh()
    try:
        qa = mod.pack_uv(bm, ['finish'], spec, glass=glass)
        layer = bm.loops.layers.uv['UVMap']
        uv = [[tuple(l[layer].uv) for l in face.loops] for face in bm.faces]
        return qa, uv, mod.density_qa(bm, ['finish'], spec)
    finally:
        bm.free()


for kind in ('full', 'placeholder'):
    for tile in (1001, 1002, 1011, 1100):
        for shifted in (False, True):
            spec = {'size_full': 4096, 'size_placeholder': 256, 'pad_m': 0.04,
                    'finishes': {'finish': {'kind': kind, 'udim': tile, 'S': 4.096,
                                            'P': [0.3, 0.3], 'shift': [shifted, shifted]}},
                    'glass': {'udim': 1001}}
            assert packed(owner, spec) == packed(old, spec)
            assert packed(owner, spec, True) == packed(old, spec, True)
            checks += 2

# Independent literal limits and counts, including exact boundary, just below and above.
for size, bound in ((2048, 1.96875), (4096, 3.9375)):
    spec = {'size_full': size, 'pad_m': 0.04, 'finishes': {'finish': {'kind': 'placeholder', 'udim': 1001}}}
    for length, count in ((bound - 0.001, 1), (bound, 1), (bound + 0.001, 2), (8.0, math.ceil(8.0 / bound))):
        bm = owner.texel_cut(mesh(length), ['finish'], spec)
        try:
            assert len(bm.faces) == count, (size, length, len(bm.faces), count)
            assert all(len(f.verts) == 4 for f in bm.faces)
            assert max(e.calc_length() for e in bm.edges) <= bound + 1e-6
            checks += 1
        finally:
            bm.free()

# Invalid finish inputs must reject before creating the output UV layer.
import copy
base = {'size_full': 4096, 'size_placeholder': 256, 'pad_m': 0.04,
        'finishes': {'finish': {'kind': 'full', 'udim': 1001, 'S': 4.096,
                                'P': [0.3, 0.3], 'shift': [True, True]}}}
for field, value in (('kind', 'unsupported'), ('P', [float('nan'), 0.3]), ('udim', 1000)):
    spec = copy.deepcopy(base)
    spec['finishes']['finish'][field] = value
    bm = mesh()
    try:
        try:
            owner.pack_uv(bm, ['finish'], spec)
        except ValueError:
            assert bm.loops.layers.uv.get('UVMap') is None
            checks += 1
        else:
            raise AssertionError(('invalid finish accepted', field))
    finally:
        bm.free()

assert initial == (bpy.data.filepath, len(bpy.data.objects), bpy.context.scene.unit_settings.system)
with output.open('x', encoding='utf-8') as stream:
    json.dump({'synthetic': True, 'blender': bpy.app.version_string, 'mode': 'headless',
               'checks_passed': checks, 'checks_failed': 0, 'scene_unchanged': True}, stream)
print('UV_COMPACTION_1380', checks, 'passed')
