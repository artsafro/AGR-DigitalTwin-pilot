"""new-case: Before/After visual evidence pair rendered with one camera from two scene versions (#1360, [D286]).

Renders the baseline (Before) and the changed version (After) of an FBX or .blend
in one isolated headless Blender process (``dt_ai.core.blender_runner.run_blender``)
with the same camera, render engine and style, then writes a labelled side-by-side
PNG, a manifest and ``SHA256SUMS.txt`` into a NEW directory outside every git work
tree (Drive evidence: ``G:/Мой диск/AGR-evidence/<issue>-<topic>/``).

Fail closed (exit 2, nothing written, inputs untouched): missing/empty/unsupported
or identical inputs, an output that exists or resolves into a git work tree or onto
an input, a non-finite camera request, cameras that differ between the two renders
(``--camera-mode named`` with two different cameras), inputs that change during the
run. The renders are evidence, not visual acceptance.

    uv run python tools/review/before_after.py --before <v1.fbx> --after <v2.fbx> \
        --output "G:/Мой диск/AGR-evidence/1360-before-after/kpp1-roof-seam" \
        --label-before "welded (before #1352)" --label-after "separate plate (#1352)"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))
from dt_ai.core.blender_runner import run_blender  # noqa: E402

BLENDER_SCRIPT = Path(__file__).resolve().parent / 'before_after_blender.py'
SUFFIXES = {'.fbx', '.blend'}
MODES = {'fit', 'named'}
STYLES = {'solid', 'wire', 'material', 'texture'}
CAMERA_FLOATS = ('lens', 'ortho_scale', 'sensor_width', 'sensor_height', 'shift_x', 'shift_y',
                 'clip_start', 'clip_end')
# 'projection' = camera.calc_matrix_camera(depsgraph, x, y, scale_x, scale_y) flattened: the effective
# projection, so any parameter that changes the image (incl. ones not listed above) is a mismatch.
CAMERA_KEYS = {'type', 'matrix_world', 'projection', 'sensor_fit', 'resolution', 'pixel_aspect',
               *CAMERA_FLOATS}
RENDER_KEYS = {'engine', 'style', 'view_transform', 'look', 'exposure', 'gamma', 'use_curve_mapping',
               'use_white_balance', 'emulation',
               'display_device', 'world_color', 'world_use_nodes', 'background_type',
               'background_color', 'thickness', 'use_border', 'use_multiview',
               'image_views_format', 'workbench'}
TOLERANCE = 1e-6


class BeforeAfterError(Exception):
    """Refusal: nothing was written and the inputs are unchanged."""


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'camera {name} is not a finite number: {value!r}')
    return float(value)


def _vector(camera, key, size):
    value = camera[key]
    if not isinstance(value, (list, tuple)) or len(value) != size:
        raise ValueError(f'camera {key} must have {size} numbers: {value!r}')
    return [_finite(v, key) for v in value]


def _normal(camera):
    if not isinstance(camera, dict):
        raise ValueError(f'camera record is not an object: {camera!r}')
    keys = set(camera)
    if keys != CAMERA_KEYS:
        raise ValueError(f'camera keys missing {sorted(CAMERA_KEYS - keys)} unknown {sorted(keys - CAMERA_KEYS)}')
    if camera['type'] not in {'ORTHO', 'PERSP'}:
        raise ValueError(f"camera type unsupported: {camera['type']!r}")
    if not isinstance(camera['sensor_fit'], str):
        raise ValueError(f"camera sensor_fit is not a string: {camera['sensor_fit']!r}")
    out = {key: _finite(camera[key], key) for key in CAMERA_FLOATS}
    out.update(type=camera['type'], sensor_fit=camera['sensor_fit'],
               matrix_world=_vector(camera, 'matrix_world', 16), projection=_vector(camera, 'projection', 16),
               resolution=_vector(camera, 'resolution', 2), pixel_aspect=_vector(camera, 'pixel_aspect', 2))
    return out


def _close(a, b):
    if isinstance(a, list):
        return all(_close(x, y) for x, y in zip(a, b))
    if isinstance(a, float):
        return abs(a - b) <= TOLERANCE * max(1.0, abs(a), abs(b))
    return a == b


def compare_cameras(before, after):
    """Return the camera keys that differ (sorted); raise ValueError on a partial or non-finite record."""
    a, b = _normal(before), _normal(after)
    return sorted(key for key in CAMERA_KEYS if not _close(a[key], b[key]))


def compare_render_state(before, after):
    """Require complete finite state; return exact differing keys (no wire-width tolerance)."""
    for state in (before, after):
        if not isinstance(state, dict):
            raise ValueError('render record must be an object')
        keys = set(state)
        if keys != RENDER_KEYS:
            raise ValueError(f'render keys missing {sorted(RENDER_KEYS - keys)} unknown {sorted(keys - RENDER_KEYS)}')
        for key, allowed in (('engine', {'BLENDER_WORKBENCH'}), ('style', STYLES),
                             ('emulation', {'AUTO', 'OFF'}),
                             ('image_views_format', {'INDIVIDUAL', 'STEREO_3D'}),
                             ('background_type', {'WORLD', 'VIEWPORT', 'THEME'})):
            if not isinstance(state[key], str) or state[key] not in allowed:
                raise ValueError(f'render {key} unsupported: {state[key]!r}')
        for key in ('view_transform', 'look', 'display_device'):
            if not isinstance(state[key], str) or not state[key].strip():
                raise ValueError(f'render {key} must be a nonempty string')
        for key in ('world_use_nodes', 'use_curve_mapping', 'use_white_balance',
                    'use_border', 'use_multiview'):
            if not isinstance(state[key], bool):
                raise ValueError(f'render {key} must be a boolean')
        if not isinstance(state['workbench'], dict):
            raise ValueError('render workbench must be an object')
        for key in ('exposure', 'gamma'):
            _finite(state[key], f'render.{key}')
        if state['gamma'] <= 0:
            raise ValueError('render gamma must be positive')
        for key in ('world_color', 'background_color'):
            _vector(state, key, 3)
        if state['style'] == 'wire':
            if _finite(state['thickness'], 'render.thickness') <= 0:
                raise ValueError('render thickness must be positive for wire')
        elif state['thickness'] is not None:
            raise ValueError('render thickness must be null for non-wire style')
    return sorted(k for k in RENDER_KEYS if before[k] != after[k])


def validate_request(spec):
    """Validate the camera/render request sent to Blender; return a normalised copy."""
    allowed = {'mode', 'name', 'azimuth_deg', 'elevation_deg', 'margin', 'resolution', 'style'}
    unknown = set(spec) - allowed
    if unknown:
        raise ValueError(f'unknown request keys: {sorted(unknown)}')
    mode = spec.get('mode')
    if mode not in MODES:
        raise ValueError(f'camera mode must be one of {sorted(MODES)}: {mode!r}')
    out = {'mode': mode, 'style': spec.get('style', 'wire'), 'resolution': spec.get('resolution', [1600, 1000])}
    if out['style'] not in STYLES:
        raise ValueError(f"style must be one of {sorted(STYLES)}: {out['style']!r}")
    resolution = out['resolution']
    if (not isinstance(resolution, (list, tuple)) or len(resolution) != 2
            or not all(isinstance(v, int) and not isinstance(v, bool) and 16 <= v <= 8192 for v in resolution)):
        raise ValueError(f'resolution must be two integers in 16..8192: {resolution!r}')
    out['resolution'] = list(resolution)
    if mode == 'named':
        name = spec.get('name')
        if not isinstance(name, str) or not name.strip():
            raise ValueError('camera mode named needs a camera name present in both scenes')
        out['name'] = name
        return out
    for key, default, low, high in (('azimuth_deg', 45.0, -360.0, 360.0), ('elevation_deg', 35.0, -89.0, 89.0)):
        value = spec.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
                or not low <= value <= high:
            raise ValueError(f'{key} must be a finite number in [{low}, {high}]: {value!r}')
        out[key] = float(value)
    margin = spec.get('margin', 1.1)
    if isinstance(margin, bool) or not isinstance(margin, (int, float)) or not math.isfinite(margin) \
            or not 1.0 <= margin <= 4.0:
        raise ValueError(f'margin must be a finite number in [1, 4]: {margin!r}')
    out['margin'] = float(margin)
    return out


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def _inside_git(path):
    for parent in (path, *path.parents):
        if (parent / '.git').exists():
            return parent
    return None


def check_paths(before, after, output):
    """Resolve and validate the inputs and the new output directory; raise BeforeAfterError."""
    resolved = []
    for role, raw in (('before', before), ('after', after)):
        path = Path(raw).resolve()
        if not path.is_file():
            raise BeforeAfterError(f'{role} input is not a file: {raw}')
        if path.suffix.lower() not in SUFFIXES:
            raise BeforeAfterError(f'{role} input must be .fbx or .blend: {raw}')
        if path.stat().st_size == 0:
            raise BeforeAfterError(f'{role} input is empty: {raw}')
        resolved.append(path)
    a, b = resolved
    if a == b or os.path.samefile(a, b):
        raise BeforeAfterError(f'before and after are the same file: {a}')
    digests = sha256(a), sha256(b)
    if digests[0] == digests[1]:
        raise BeforeAfterError(f'before and after have identical content (sha256 {digests[0]}): no visible change')
    out = Path(output).resolve()
    partial = out.with_name(out.name + '.partial')
    for candidate in (out, partial):
        if candidate.exists():
            raise BeforeAfterError(f'output already exists (never overwritten): {candidate}')
        if candidate in (a, b) or a.is_relative_to(candidate) or b.is_relative_to(candidate):
            raise BeforeAfterError(f'output resolves onto an input: {candidate}')
    repo = _inside_git(out.parent if not out.exists() else out)
    if repo is not None:
        raise BeforeAfterError(f'output is inside the git work tree {repo}; evidence goes to Drive, not git')
    return a, b, out, partial, digests


def _resolution(text):
    try:
        width, height = (int(v) for v in text.lower().split('x'))
    except ValueError:
        raise argparse.ArgumentTypeError(f'resolution must be WIDTHxHEIGHT: {text!r}') from None
    return [width, height]


def parser():
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('--before', required=True, help='baseline FBX/.blend (real, never a mockup)')
    p.add_argument('--after', required=True, help='changed FBX/.blend')
    p.add_argument('--output', required=True, help='NEW directory outside git (Drive evidence)')
    p.add_argument('--label-before', required=True, help='baseline version, e.g. "main 9d7753e1 welded"')
    p.add_argument('--label-after', required=True, help='changed version, e.g. "PR #1352 separate plate"')
    p.add_argument('--camera-mode', choices=sorted(MODES), default='fit',
                   help='fit: one orthographic camera fitted to the union of both scenes; '
                        'named: a camera object of this name in BOTH scenes (must be identical)')
    p.add_argument('--camera-name', help='camera object name for --camera-mode named')
    p.add_argument('--azimuth', type=float, default=45.0, help='fit view azimuth, degrees')
    p.add_argument('--elevation', type=float, default=35.0, help='fit view elevation, degrees (-89..89)')
    p.add_argument('--margin', type=float, default=1.1, help='fit margin around the union bbox (1..4)')
    p.add_argument('--style', choices=sorted(STYLES), default='wire',
                   help='workbench style: solid, wire (solid + edges), material, texture')
    p.add_argument('--resolution', type=_resolution, default=[1600, 1000], help='WIDTHxHEIGHT')
    p.add_argument('--blender', help='Blender executable (default: TWINQA_BLENDER or pinned 5.1)')
    p.add_argument('--timeout', type=float, default=1800)
    return p


def compose(before_png, after_png, labels, target):
    from PIL import Image, ImageDraw, ImageFont
    left, right = Image.open(before_png).convert('RGB'), Image.open(after_png).convert('RGB')
    if left.size != right.size:
        raise BeforeAfterError(f'render sizes differ: {left.size} vs {right.size}')
    band = max(28, left.height // 18)
    try:
        font = ImageFont.truetype('arial.ttf', int(band * 0.6))
    except OSError:
        font = ImageFont.load_default()
    pair = Image.new('RGB', (left.width * 2 + 8, left.height + band), 'white')
    draw = ImageDraw.Draw(pair)
    for index, (image, text, colour) in enumerate(((left, labels[0], (150, 30, 30)),
                                                  (right, labels[1], (20, 110, 40)))):
        x = index * (left.width + 8)
        pair.paste(image, (x, band))
        draw.text((x + 8, band * 0.15), text, fill=colour, font=font)
    pair.save(target)


def run(args):
    labels = [args.label_before.strip(), args.label_after.strip()]
    if not all(labels):
        raise BeforeAfterError('both --label-before and --label-after must name the version')
    try:
        request = validate_request({k: v for k, v in dict(
            mode=args.camera_mode, name=args.camera_name, azimuth_deg=args.azimuth,
            elevation_deg=args.elevation, margin=args.margin, resolution=args.resolution,
            style=args.style).items() if v is not None})
    except ValueError as exc:
        raise BeforeAfterError(str(exc)) from None
    before, after, output, partial, digests = check_paths(args.before, args.after, args.output)
    created = [d for d in (partial.parent, *partial.parent.parents) if not d.exists()]
    partial.mkdir(parents=True)
    try:
        config = dict(before=str(before), after=str(after), output_dir=str(partial), request=request)
        config_path = partial / 'config.json'
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')
        record = run_blender(BLENDER_SCRIPT, [config_path], executable=args.blender,
                             output_json=partial / 'render-evidence.json',
                             outputs=[partial / 'before.png', partial / 'after.png'],
                             timeout=args.timeout, log_path=partial / 'blender.log')
        try:
            differ = compare_cameras(record['before']['camera'], record['after']['camera'])
            render_differ = compare_render_state(record['before']['render'], record['after']['render'])
        except (KeyError, TypeError, ValueError) as exc:
            raise BeforeAfterError(f'render evidence incomplete: {exc}') from None
        if differ or render_differ:
            raise BeforeAfterError(f'mismatched cameras/render state between Before and After: {differ + render_differ}')
        if (sha256(before), sha256(after)) != digests:
            raise BeforeAfterError('an input changed during the run; rerun on stable inputs')
        texts = [f'BEFORE: {labels[0]} | {before.name} sha256 {digests[0][:12]}',
                 f'AFTER: {labels[1]} | {after.name} sha256 {digests[1][:12]}']
        compose(partial / 'before.png', partial / 'after.png', texts, partial / 'before-after.png')
        manifest = {
            'scope': 'Before/After visual evidence (D286); no acceptance implied',
            'synthetic': False,
            'before': {'label': labels[0], 'path': str(before), 'sha256': digests[0], 'render': 'before.png'},
            'after': {'label': labels[1], 'path': str(after), 'sha256': digests[1], 'render': 'after.png'},
            'pair': 'before-after.png', 'request': request, 'same_camera': True,
            'camera': record['before']['camera'], 'render': record['before']['render'],
        }
        (partial / 'before-after.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                                                   encoding='utf-8')
        sums = [f'{sha256(p)}  {p.name}' for p in sorted(partial.iterdir()) if p.is_file()]
        # LF only: Path.write_text would emit CRLF on Windows and break `sha256sum -c`.
        (partial / 'SHA256SUMS.txt').write_bytes(('\n'.join(sums) + '\n').encode('utf-8'))
        if output.exists():
            raise BeforeAfterError(f'output appeared during the run (never overwritten): {output}')
        partial.rename(output)
    except BaseException:
        shutil.rmtree(partial, ignore_errors=True)
        for directory in created:  # innermost first; only the empty parents this run created
            try:
                directory.rmdir()
            except OSError:
                break
        raise
    return output


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        output = run(args)
    except BeforeAfterError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    except Exception as exc:  # Blender launch/process failures: the partial dir is already removed
        print(f'ERROR: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 2
    print(json.dumps({'status': 'written', 'output': str(output),
                      'pair': str(output / 'before-after.png')}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
