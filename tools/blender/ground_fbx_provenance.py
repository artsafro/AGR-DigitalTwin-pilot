"""new-case: byte-bound Ground placement transfer at Blender FBX producer boundaries.

The existing Ground build writes a path-bound placement receipt and a separate
byte-bound export record. For legacy placement verify the recorded offset against
the hash-bound source mesh via the existing derivation record. New placement
receipts also carry the FBX digest. Neither form certifies a survey datum.
"""
import hashlib
import json
import math
import os
import re
from pathlib import Path

from adapters.max.agr_tools import export_meta

PLACEMENT = '.placement.json'
EXPORT = '.export_meta.json'
CRS_LABELS = {'MSK-77', 'SYNTHETIC_LOCAL', 'DWG WCS metres; CRS unspecified by user, no transform'}
RELATION = 'mesh_xyz = msk77_xyz - origin_msk77_xyz'
# Readback noise allowance, not a production placement or modelling tolerance.
FRAME_EPS = 0.0001
GROUND_NAME = re.compile(r'SM_([A-Za-z0-9]+(?:_[A-Za-z0-9]+)*_Ground)')


def sidecar(fbx, suffix):
    return fbx.with_name(fbx.name + suffix)


def refuse_outputs(inputs, outputs):
    resolved = {Path(path).resolve() for path in inputs}
    for path in outputs:
        if os.path.lexists(path) or path.resolve() in resolved:
            raise ValueError(f'refuse overwrite or input alias: {path}')
        resolved.add(path.resolve())


def publish(pairs):
    """Publish staged same-volume files without overwriting even a late arrival.

    Publish the FBX last. On failure remove only links created by this attempt.
    """
    linked = []
    try:
        for staged, dest in pairs:
            os.link(staged, dest)
            linked.append((staged, dest))
    except OSError:
        for staged, dest in reversed(linked):
            try:
                if os.path.samefile(staged, dest):
                    dest.unlink()
            except FileNotFoundError:
                pass
        raise


def require_finished(result, operation):
    if result != {'FINISHED'}:
        raise ValueError(f'{operation} did not finish: {result!r}')


def _finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def _xyz(xyz):
    return isinstance(xyz, list) and len(xyz) == 3 and all(_finite(x) for x in xyz)


def _close(left, right):
    return len(left) == len(right) and all(abs(a - b) < FRAME_EPS for a, b in zip(left, right))


def render_top(meshes):
    points = (float((obj.matrix_world @ v.co)[2]) for obj in meshes for v in obj.data.vertices)
    top = None
    for z in points:
        if not math.isfinite(z):
            return 'unknown'
        top = z if top is None else max(top, z)
    return 'unknown' if top is None else top


def ground_object(meshes):
    objects = [obj for obj in meshes if GROUND_NAME.fullmatch(obj.name)]
    return objects[0] if len(objects) == 1 else None


def _frame(obj):
    world = obj.matrix_world
    transform = tuple(float(x) for row in world for x in row)
    location = tuple(float(x) for x in obj.location)
    # Retain vertex multiplicity. Conservative lexicographic pairing may decline a
    # reordered near-tie; it cannot certify a pair that exceeds the readback bound.
    points = sorted(tuple(float(x) for x in world @ v.co) for v in obj.data.vertices)
    if (len(transform) != 16 or len(location) != 3 or not all(map(_finite, transform + location))
            or not points or not all(len(point) == 3 and all(map(_finite, point)) for point in points)):
        raise ValueError('Ground frame has empty or non-finite evidence')
    return transform, location, points


def _load_snapshot(path):
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def _json(raw):
    return json.loads(raw, object_pairs_hook=export_meta.unique_object)


class GroundEvidence:
    def __init__(self, source):
        self.source = source
        self.digest = export_meta._sha256(source)
        self.paths = [sidecar(source, EXPORT), sidecar(source, PLACEMENT)]
        self.snapshots = [_load_snapshot(p) for p in self.paths]
        self.legacy = None
        self.meta = None
        if self.snapshots[0] is not None:
            try:
                meta = export_meta.validate_meta(_json(self.snapshots[0]))
                if meta.get('exported_sha256', {}).get(source.name) == self.digest:
                    self.meta = meta
            except (ValueError, OverflowError):
                pass  # Historical/malformed export records are not evidence for this FBX.

    def assert_unchanged(self):
        if (export_meta._sha256(self.source) != self.digest
                or [_load_snapshot(p) for p in self.paths] != self.snapshots):
            raise ValueError(f'Ground source FBX or sidecars changed during export: {self.source}')
        if self.legacy is not None:
            derivation, raw, master, digest = self.legacy
            if _load_snapshot(derivation) != raw or export_meta._sha256(master) != digest:
                raise ValueError(f'legacy Ground derivation or master changed during export: {self.source}')

    def _verify_legacy_origin(self, origin):
        from adapters.max.agr_tools import build_manifest

        path = self.source.with_name(build_manifest.derivation_filename(self.source))
        try:
            raw = path.read_bytes()
            derivation = build_manifest.check_derivation(_json(raw))
            if (derivation.get('role') != 'ground'
                    or derivation['artifacts'].get(self.source.name, {}).get('sha256') != self.digest):
                raise ValueError('does not bind this Ground FBX')
        except (OSError, ValueError, TypeError) as exc:
            raise ValueError(f'legacy placement derivation unavailable or invalid: {exc}') from exc

        try:
            master = Path(derivation['master_path'])
            digest = derivation['master_sha256']
            mesh = master.read_bytes()
            if hashlib.sha256(mesh).hexdigest() != digest:
                raise ValueError('SHA-256 differs from derivation')
            verts = _json(mesh)['verts']
            if not isinstance(verts, list) or not verts or not all(map(_xyz, verts)):
                raise ValueError('no finite source vertices')
        except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
            raise ValueError(f'legacy Ground master unavailable or invalid: {exc}') from exc
        xs, ys, _ = zip(*verts)
        # Exact replay of the Ground build's XY bounds centre, not a new datum.
        if origin != [(min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, 0.0]:
            raise ValueError('legacy placement origin differs from the verified Ground master')
        self.legacy = path, raw, master, digest

    def capture(self, ground, top):
        """Placement and measured input frame, or an explicit reason to omit them."""
        if ground is None:
            return None, 'no unique Ground mesh'
        if self.meta is None:
            return None, 'missing, invalid or stale export record'
        if self.meta['address'] != ground.name[3:]:
            return None, 'export record does not identify the Ground mesh'
        raw = self.snapshots[1]
        if raw is None:
            return None, 'missing placement receipt'
        try:
            place = _json(raw)
            keys = {'fbx', 'crs', 'origin_msk77_xyz', RELATION, 'object_location'}
            if not isinstance(place, dict) or set(place) not in (keys, keys | {'fbx_sha256'}):
                raise ValueError('unsupported placement fields')
            if not isinstance(place['fbx'], str) or Path(place['fbx']).resolve() != self.source.resolve():
                raise ValueError('placement receipt names another FBX')
            if 'fbx_sha256' in place and place['fbx_sha256'] != self.digest:
                raise ValueError('stale placement FBX digest')
            if (place['crs'] not in CRS_LABELS or place[RELATION] is not True
                    or not _xyz(place['origin_msk77_xyz']) or not _xyz(place['object_location'])):
                raise ValueError('unsupported or non-finite placement')
            measured = _frame(ground)
            if not _close(place['object_location'], measured[1]) or not _close(place['object_location'], measured[0][3:12:4]):
                raise ValueError('placement pivot differs from the imported Ground')
            if not _finite(top) or not _finite(self.meta['h_otn_model_max_z_m']) or not _close([top], [self.meta['h_otn_model_max_z_m']]):
                raise ValueError('recorded render top differs from the imported FBX')
            if 'fbx_sha256' not in place:
                self._verify_legacy_origin(place['origin_msk77_xyz'])
            return (ground.name, place, measured), None
        except (ValueError, TypeError, OSError, OverflowError) as exc:
            return None, str(exc)

    def readback_placement(self, capture, staged, out, bpy):
        candidate, reason = capture
        bpy.ops.wm.read_factory_settings(use_empty=True)
        require_finished(bpy.ops.import_scene.fbx(filepath=str(staged)), 'Ground FBX readback')
        meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.name.upper().startswith('UCX')]
        top = render_top(meshes)
        if candidate is None:
            return reason, top
        name, place, frame = candidate
        ground = ground_object(meshes)
        if ground is None or ground.name != name:
            return 'output does not identify the same Ground mesh', top
        transform, location, points = _frame(ground)
        if (not _close(transform, frame[0]) or not _close(location, frame[1])
                or len(points) != len(frame[2]) or not all(_close(a, b) for a, b in zip(points, frame[2]))):
            return 'output Ground frame differs from the input', top
        placement = dict(place, fbx=str(out.resolve()), fbx_sha256=export_meta._sha256(staged))
        with sidecar(staged, PLACEMENT).open('x', encoding='utf-8') as fh:
            json.dump(placement, fh, indent=2, allow_nan=False)
        return None, top

    def check_binder_profile(self, profile, out, plan):
        if profile not in export_meta.DELIVERY_PROFILES:
            raise ValueError(f'binding plan requires explicit profile npm or vpm, got {profile!r}')
        chosen, why = export_meta.resolve_export_profile(profile, out, legacy_default=None, source=str(plan))
        upstream = (self.meta or {}).get('profile')
        if self.explicit_profile and upstream != chosen:
            raise ValueError(f'binding profile {chosen!r} contradicts explicit input export profile {upstream!r}')
        return chosen, why

    @property
    def explicit_profile(self):
        return ': explicit exporter profile argument' in (self.meta or {}).get('provenance', {}).get('profile', '')

    def inherited_profile(self, name):
        if self.meta and self.meta['address'] == name and self.meta.get('profile') in export_meta.DELIVERY_PROFILES:
            why = self.meta.get('provenance', {}).get('profile', 'recorded input profile; explicitness unknown')
            return self.meta['profile'], f'inherited from {self.paths[0]}: {why}'
        return 'unknown', 'unknown; no verified Ground input profile'

    def supplied_thumbnail(self, plan, supplied):
        if not isinstance(supplied, str) or not supplied.strip() or supplied == 'unknown':
            raise ValueError('thumbnail must name an explicitly supplied file for the new output')
        path = (plan.parent / supplied).resolve()
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f'supplied thumbnail is missing or empty: {path}')
        prior = (self.meta or {}).get('thumbnail', 'unknown')
        prior = self.source.parent / prior
        if prior.is_file() and prior.samefile(path):
            raise ValueError(f'supplied thumbnail aliases the input FBX preview: {path}')
        if path.samefile(self.source) or path.samefile(plan):
            raise ValueError(f'supplied thumbnail aliases a non-image input: {path}')
        return path
