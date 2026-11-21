"""new-case: headless .blend writer for the shared R3 railing core."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def main(argv=None):
    from dt_ai.core.blender_runner import BlenderRunError, run_blender

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'adapters/max/agr_tools'))
    from railing_core import PROFILES, REPRESENTATIONS, TYPES, build_railing

    parser = argparse.ArgumentParser(description='Build a new railing inset .blend from a metre spline JSON')
    parser.add_argument('spline', type=Path)
    parser.add_argument('--type', choices=TYPES, required=True)
    parser.add_argument('--profile', choices=PROFILES, default='vpm')
    parser.add_argument('--representation', choices=REPRESENTATIONS, default='geometry')
    parser.add_argument('--out', required=True, type=Path, help='new .blend on a local hardlink-capable filesystem')
    parser.add_argument('--blender')
    args = parser.parse_args(argv)
    try:
        out = args.out.resolve()
        if args.out.is_symlink() or out.exists() or out.suffix.lower() != '.blend':
            raise ValueError('output must be a new .blend; existing and aliased files are refused')
        if args.spline.suffix.lower() != '.json':
            raise ValueError('spline must be a JSON document')
        data = args.spline.read_bytes()
        report = build_railing(json.loads(data, object_pairs_hook=_unique), args.type,
                               args.profile, args.representation)
        report['spline_sha256'] = hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory(prefix='.railing-', dir=out.parent) as workspace:
            spec = Path(workspace) / 'mesh.json'
            staged = Path(workspace) / 'railing.blend'
            spec.write_text(json.dumps(report, allow_nan=False), encoding='utf-8')
            run_blender(Path(__file__).resolve(), ('--write-railing', spec, staged),
                        executable=args.blender, outputs=(staged,), timeout=180)
            if args.spline.read_bytes() != data:
                raise ValueError('spline changed during Blender execution; no output published')
            # Atomic create-if-absent; never replace a racing destination.
            os.link(staged, out)
        print(json.dumps({k: v for k, v in report.items() if k != 'meshes'}, allow_nan=False))
    except (OSError, ValueError, BlenderRunError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    return 0


_COLORS = {'post': (.17, .19, .21), 'top_rail': (.24, .26, .29),
           'glass': (.22, .55, .68), 'infill': (.39, .43, .46)}


def _material(bpy, role, mid):
    material = bpy.data.materials.new(f'{mid:02d}_railing_{role}')
    material['agr_material_id'] = mid
    material.use_nodes = True
    if role != 'opacity':
        color = (*_COLORS[role], 1.)
        material.diffuse_color = color
        shader = material.node_tree.nodes.get('Principled BSDF')
        shader.inputs['Base Color'].default_value = color
        shader.inputs['Metallic'].default_value = .65 if role != 'glass' else 0.
        if role == 'glass':
            shader.inputs['Transmission Weight'].default_value = .92
            shader.inputs['Roughness'].default_value = .12
    return material


def _opacity_material(bpy, member):
    # One tile per bay pattern; the same tile is reused by any chord subdivisions.
    width, height = 256, 128
    diffuse = [0., 0., 0., 1.] * (width * height)
    opacity = diffuse.copy()
    for x0, x1, z0, z1, role in member['mask_rects']:
        i0, i1 = int(x0*width), min(width, max(int(x0*width)+1, round(x1*width)))
        j0, j1 = int(z0*height), min(height, max(int(z0*height)+1, round(z1*height)))
        alpha = .45 if role == 'glass' else 1.
        for j in range(j0, j1):
            sl = slice(4*(j*width+i0), 4*(j*width+i1))
            diffuse[sl] = [*_COLORS[role], 1.] * (i1-i0)
            opacity[sl] = [alpha, alpha, alpha, 1.] * (i1-i0)
    material = _material(bpy, 'opacity', member['material_id'])
    material.use_backface_culling = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    shader = nodes.get('Principled BSDF')
    for suffix, pixels, target in (('_d', diffuse, 'Base Color'), ('_o', opacity, 'Alpha')):
        image = bpy.data.images.new(material.name + suffix, width, height, alpha=False)
        if suffix == '_o':
            image.colorspace_settings.name = 'Non-Color'
        image.pixels.foreach_set(pixels)
        image.pack()
        tex = nodes.new('ShaderNodeTexImage')
        tex.image, tex.extension, tex.interpolation = image, 'EXTEND', 'Closest'
        links.new(tex.outputs['Color'], shader.inputs[target])
    return material


def write_blend(spec, output):
    import bpy

    report = json.loads(Path(spec).read_text(encoding='utf-8'))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.
    materials = {}
    for index, m in enumerate(report.pop('meshes')):
        name = f'Railing_{m["role"]}_{index:05d}'
        mesh = bpy.data.meshes.new(name)
        origin = m['vertices'][0]
        vertices = [tuple(p[i] - origin[i] for i in range(3)) for p in m['vertices']]
        mesh.from_pydata(vertices, [], m['faces'])
        if (mesh.validate() or len(mesh.polygons) != len(m['faces'])
                or len({tuple(v.co) for v in mesh.vertices}) != len(vertices)
                or any(p.area <= 0 for p in mesh.polygons)):
            raise ValueError(f'invalid native mesh: {name}')
        obj = bpy.data.objects.new(name, mesh)
        scene.collection.objects.link(obj)
        obj.location = origin
        mid = m['material_id']
        obj['agr_material_id'] = mid
        if m['role'] == 'opacity':
            key = tuple(tuple(round(x, 8) if isinstance(x, float) else x for x in r) for r in m['mask_rects'])
            if key not in materials:
                materials[key] = _opacity_material(bpy, m)
            mesh.materials.append(materials[key])
            a, b = m['u_limits']
            uv = mesh.uv_layers.new(name='RailingMask')
            for loop, xy in zip(mesh.polygons[0].loop_indices, ((a, 0.), (b, 0.), (b, 1.), (a, 1.))):
                uv.uv[loop].vector = xy
        else:
            if mid not in materials:
                materials[mid] = _material(bpy, m['role'], mid)
            mesh.materials.append(materials[mid])
    scene['agr_railing'] = json.dumps(report, allow_nan=False)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))


if __name__ == '__main__':
    marker = '--write-railing'
    if '--' in sys.argv and sys.argv[sys.argv.index('--')+1:][:1] == [marker]:
        write_blend(*sys.argv[-2:])
    else:
        raise SystemExit(main())
