"""new-case: delivery set consistency (#1423): build manifest beside every package, stdlib only (Max + agent CLI).

One delivery ZIP `<stem>.zip` gets one separate file `<stem>.build.json` (export_meta.validate_meta rejects unknown
keys, so the manifest never goes into export_meta; AI Council 2026-11-15). It names:

* the build id and the master revision: SHA-256 of the master file + git commit of the builder;
* every zipped artifact (VPM/NPM FBX, Light FBX, textures, UCX, GeoJSON) with its SHA-256, the master revision it was
  DERIVED from (a derivation record written at export time, `derivation_record`), and its stable part ids (mesh names
  read back from the exported file);
* the coordinate transform used (e.g. the #1371 bridge file with its SHA-256);
* the checks with their report file hash and the hashes of the files each check ran on.

`manifest_findings` is the refusal logic used by tools/qa/validate_package.py (stage V001 "build manifest") and so by
package_core.qa_package / `agr validate`: artifacts naming different master revisions, a master that changed after
the build, report/subject hashes that do not match the zipped files, and a required check that did not run, did not
finish or did not pass (skipped = not ready) are `fail`; a package without a manifest is `not_run` (never pass).

Masters per role (#1525, [D328], refined by #1555 [D333, D332]): package_core owns the Ground-family vocabulary.
Ground/Glass -> ground; GroundEl/Glass -> groundel; Flora -> flora; other members -> oks. File grouping remains Ground.
Schema v2 keeps one master per role; v3 adds `sources` to a role entry when there are independent dependencies and
binds each artifact to source_id + master_name + master_sha256 (#1589). V3 requires explicit stable producer ids,
refuses multiple hashes of one id and unused declarations. Legacy v1/v2 records do not acquire inferred ids.
Repeat --master role=path for independent sources, not revisions
of one source. Optional component `dependencies` bind a combined FBX's parts to their own role/source hashes. Every
read-back part of a different role needs a dependency; the bound report's part inventory cannot be silently dropped.
Schema v1/v2 remain readable; legacy records without ids retain v2 only in single-source builds.
Stale revisions and false roles remain refusals.

FBX export owner (#1423 point 2): the readback of the exported files that go into the package is
`readback_summary` over tools/blender/fbx_readback.py (dimensions, part positions, materials, UV, UCX-to-visual name
binding); its report is the required check `fbx_readback`.
"""
import datetime
import hashlib
import json
import math
import os
import re
import zipfile

SCHEMA = 'agr.build_manifest/2'
SCHEMA_MULTI = 'agr.build_manifest/3'  # [D332]: several independent sources within one role
SCHEMA_V1 = 'agr.build_manifest/1'
ROLES = ('oks', 'ground', 'groundel', 'flora')  # [D333]: independent provenance roles
DERIVATION_SCHEMA = 'agr.derivation/1'
READBACK_SCHEMA = 'agr.fbx_readback/1'
SUFFIX = '.build.json'
READBACK_SUFFIX = '.readback.json'
REQUIRED_CHECKS = ('fbx_readback',)
EXPORT_OWNER = 'tools/derive/build_manifest.py build (export owner readback, #1423)'
KINDS = ('npm_fbx', 'vpm_fbx', 'light_fbx', 'ucx_fbx', 'texture', 'geojson')
SHA = re.compile(r'^[0-9a-f]{64}$')
COMMIT = re.compile(r'^(?:[0-9a-f]{7,40}|unknown)$')
TOP_KEYS_V1 = {'schema', 'build_id', 'created_utc', 'package', 'master', 'transform', 'artifacts', 'checks'}
TOP_KEYS = TOP_KEYS_V1 - {'master'} | {'masters'}
MASTER_KEYS = {'name', 'sha256', 'builder_commit'}
TRANSFORM_KEYS = {'name', 'file', 'sha256'}
ARTIFACT_KEYS_V1 = {'name', 'kind', 'sha256', 'derived_sha256', 'master_sha256', 'parts'}
ARTIFACT_KEYS = ARTIFACT_KEYS_V1 | {'role'}
CHECK_KEYS = {'id', 'owner', 'required', 'status', 'finished', 'report', 'report_sha256', 'subjects'}
DERIVATION_KEYS = {'schema', 'master_name', 'master_sha256', 'builder_commit', 'artifacts', 'master_path', 'role', 'dependencies', 'source_id'}
# master_path: #1505 export-time records; role: #1525 records; older records lack them (role then follows the name)
DERIVATION_REQUIRED = DERIVATION_KEYS - {'master_path', 'role', 'dependencies', 'source_id'}
DEPENDENCY_KEYS = {'role', 'master_name', 'master_sha256', 'parts', 'source_id'}
DERIVATION_SUFFIX = '.derivation.json'
DERIVATION_STORE = 'derivation'  # <export root>/derivation/: beside the exported folder, never inside a package folder
ATLAS_MASTER_KEYS = {'name', 'sha256', 'udims'}
UCX = re.compile(r'^UCX_(?P<rest>.+)$')


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def manifest_path(package_zip):
    """`<dir>/<stem>.build.json` beside `<dir>/<stem>.zip`."""
    package_zip = os.fspath(package_zip)
    if not package_zip.lower().endswith('.zip'):
        raise ValueError('build manifest: package must be a .zip: ' + package_zip)
    return package_zip[:-4] + SUFFIX


def readback_path(package_zip):
    return manifest_path(package_zip)[:-len(SUFFIX)] + READBACK_SUFFIX


def kind_of(name):
    """Artifact kind by the delivery name grammar; an unknown member is an error naming it (never a default)."""
    low = name.lower()
    if low.endswith('.fbx'):
        stem = name[:-4]
        if stem.startswith('UCX_'):
            return 'ucx_fbx'
        if stem.endswith('_Light'):
            return 'light_fbx'
        return 'vpm_fbx' if stem.startswith('SM_') else 'npm_fbx'
    if low.endswith('.png'):
        return 'texture'
    if low.endswith('.geojson'):
        return 'geojson'
    raise ValueError('build manifest: no artifact kind for member ' + repr(name))


def role_of(name):
    """Provenance role from the packaging grammar owner [D333], also in embedded Max installs."""
    try:
        from .package_core import role_of as classify_role
    except ImportError:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'agr_package_role', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'package_core.py'))
        if spec is None or spec.loader is None:
            raise ImportError('package_core role classifier unavailable')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        classify_role = module.role_of
    return classify_role(name)


def _role(value, where):
    if value not in ROLES:
        raise ValueError('{} role {!r} unsupported (roles: {})'.format(where, value, ', '.join(ROLES)))
    return value


def master_args(values):
    """`--master` -> one path or {role: path | [independent paths]} [D332]. Repeated identical paths,
    unknown roles, empty paths, keyed mixed with unkeyed and missing masters are errors."""
    values = [os.fspath(v) for v in values or ()]
    if not values:
        raise ValueError('no --master given')
    keyed, plain = {}, []
    for v in values:
        role, sep, path = v.partition('=')
        if sep and re.fullmatch(r'[A-Za-z_]+', role):
            _role(role, '--master ' + v)
            if not path.strip():
                raise ValueError('--master {}: empty path'.format(v))
            if role in keyed:
                previous = keyed[role] if isinstance(keyed[role], list) else [keyed[role]]
                if path in previous:
                    raise ValueError('--master role {} path given twice'.format(role))
                keyed[role] = previous + [path]
            else:
                keyed[role] = path
        else:
            plain.append(v)
    if keyed and plain:
        raise ValueError('--master: do not mix role=path with an unkeyed path {}'.format(plain))
    if len(plain) > 1:
        raise ValueError('--master given twice without a role: {}; use role=path'.format(plain))
    return plain[0] if plain else keyed


def strict_json(data):
    """JSON object with duplicate keys refused; NaN/Infinity refused."""
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise ValueError('duplicate JSON key ' + repr(k))
            out[k] = v
        return out

    def bad_constant(name):
        raise ValueError('non-finite JSON number ' + name)
    text = data.decode('utf-8') if isinstance(data, bytes) else data
    return json.loads(text, object_pairs_hook=pairs, parse_constant=bad_constant)


def _keys(obj, allowed, where, required=None):
    if not isinstance(obj, dict):
        raise ValueError(where + ' must be an object')
    extra = set(obj) - set(allowed)
    if extra:
        raise ValueError('{} unknown keys: {}'.format(where, sorted(extra)))
    missing = set(allowed if required is None else required) - set(obj)
    if missing:
        raise ValueError('{} missing keys: {}'.format(where, sorted(missing)))


def _sha(value, where):
    if not isinstance(value, str) or not SHA.match(value):
        raise ValueError(where + ' must be a lowercase SHA-256 hex')
    return value


def zip_members(package_zip):
    """{member name: sha256} of a flat delivery ZIP; nested/duplicate names are refused."""
    out = {}
    with zipfile.ZipFile(package_zip) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if '/' in name or '\\' in name:
                raise ValueError('build manifest: nested member ' + repr(name))
            if name.casefold() in {n.casefold() for n in out}:
                raise ValueError('build manifest: duplicated member ' + repr(name))
            out[name] = sha256_bytes(z.read(info))
    if not out:
        raise ValueError('build manifest: empty package ' + os.fspath(package_zip))
    return out


# ---- derivation records: written by the exporter at export time ---------------------------------------------
def derivation_record(artifacts, master, builder_commit, master_sha256=None, role=None, dependencies=None, source_id=None):
    """Record of which master revision the exported `artifacts` (paths) were derived from, hashed NOW (export time).

    master_sha256: the master hash the exporter read BEFORE it opened the master (#1505); a different hash now means
    the master changed during the export and is refused (`master_changed_during_export`), nothing is recorded.
    A later master edit leaves this record behind: the build manifest then names two revisions and is refused.
    role ([D328]): the package role of the artifacts ('oks' | 'ground'); None takes it from the artifact names and
    refuses artifacts of different roles in one record (one record = one master = one role)."""
    if not artifacts:
        raise ValueError('derivation: no artifact')
    if role is None:
        roles = sorted({role_of(os.fspath(p)) for p in artifacts})
        if len(roles) != 1:
            raise ValueError('derivation: artifacts of different roles {} in one record; one master per role '
                             '[D328]'.format(roles))
        role = roles[0]
    _role(role, 'derivation')
    if not COMMIT.match(str(builder_commit)):
        raise ValueError('derivation: builder_commit must be a git sha or unknown')
    if master_sha256 is not None:
        _sha(master_sha256, 'derivation expected master_sha256')
    master = os.fspath(master)
    if not os.path.isfile(master):
        raise ValueError('derivation: no master file ' + master)
    if not os.path.getsize(master):
        raise ValueError('derivation: empty master file ' + master)
    now = sha256_file(master)
    if master_sha256 is not None and now != master_sha256:
        raise ValueError('master_changed_during_export: master {} was {} when the export started, now {}'.format(
            os.path.basename(master), master_sha256[:12], now[:12]))
    rec = {}
    for path in artifacts:
        path = os.fspath(path)
        name = os.path.basename(path)
        if os.path.normcase(os.path.realpath(path)) == os.path.normcase(os.path.realpath(master)):
            raise ValueError('derivation: artifact is the master itself: ' + name)
        if name in rec:
            raise ValueError('derivation: duplicated artifact name ' + name)
        if not os.path.isfile(path) or not os.path.getsize(path):
            raise ValueError('derivation: empty or missing artifact ' + path)
        rec[name] = {'kind': kind_of(name), 'sha256': sha256_file(path)}
    record = {'schema': DERIVATION_SCHEMA, 'master_name': os.path.basename(master), 'master_sha256': now,
            'master_path': os.path.abspath(master), 'builder_commit': str(builder_commit), 'artifacts': rec,
            'role': role}
    if source_id is not None:
        record['source_id'] = _source_id(source_id)
    if dependencies is not None:
        if not isinstance(dependencies, list) or not dependencies:
            raise ValueError('derivation dependencies must be a non-empty list')
        rows = []
        for dep in dependencies:
            _keys(dep, {'role', 'master', 'master_sha256', 'parts', 'source_id'}, 'export dependency',
                  required={'role', 'master', 'master_sha256', 'parts'})
            path = os.fspath(dep['master'])
            if any(os.path.samefile(path, artifact) for artifact in artifacts):
                raise ValueError('derivation: dependency is the artifact itself: ' + path)
            if not os.path.getsize(path):
                raise ValueError('derivation: empty dependency ' + path)
            _sha(dep['master_sha256'], 'dependency expected master_sha256')
            if sha256_file(path) != dep['master_sha256']:
                raise ValueError('master_changed_during_export: dependency ' + path)
            rows.append({'role': dep['role'], 'master_name': os.path.basename(path),
                         'master_sha256': dep['master_sha256'], 'parts': dep['parts']})
            if 'source_id' in dep:
                rows[-1]['source_id'] = _source_id(dep['source_id'])
        check_dependencies(rows)
        record['dependencies'] = rows
    return record


def _source_id(value):
    """Opaque stable producer identity, never inferred from a revision's file name or hash."""
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError('source_id must be a non-empty string without surrounding whitespace')
    return value


def check_dependencies(rows):
    """Component-level provenance in a combined Ground FBX [D333]; no default role or unbound part."""
    if not isinstance(rows, list) or not rows:
        raise ValueError('dependencies must be a non-empty list')
    seen = set()
    for dep in rows:
        _keys(dep, DEPENDENCY_KEYS, 'dependency', required=DEPENDENCY_KEYS - {'source_id'})
        if 'source_id' in dep:
            _source_id(dep['source_id'])
        _role(dep['role'], 'dependency')
        _sha(dep['master_sha256'], 'dependency master_sha256')
        if not isinstance(dep['master_name'], str) or not dep['master_name'].strip():
            raise ValueError('dependency master_name required')
        parts = dep['parts']
        if not isinstance(parts, list) or not parts or not all(isinstance(p, str) and p for p in parts):
            raise ValueError('dependency parts must be a non-empty list of names')
        if len(parts) != len(set(parts)):
            raise ValueError('dependency part given twice')
        for part in parts:
            if role_of(part) != dep['role']:
                raise ValueError('dependency role disagrees with part ' + part)
        identity = (dep['role'], dep['master_name'], tuple(sorted(parts)))
        if identity in seen:
            raise ValueError('dependency given twice: ' + dep['master_name'])
        seen.add(identity)


def derivation_store(export_dir):
    """Export-time record store of one export: `<parent of the exported folder>/derivation/` (#1505).

    Outside the exported folder on purpose: package_vpm zips every file of its package folder."""
    return os.path.join(os.path.dirname(os.path.abspath(os.fspath(export_dir))), DERIVATION_STORE)


def check_component_coverage(artifact):
    """Bind component dependencies to the actual exported part inventory [D333, D332]."""
    covered = {p for d in artifact.get('dependencies', []) for p in d['parts']}
    for dep in artifact.get('dependencies', []):
        if not set(dep['parts']) <= set(artifact['parts']):
            raise ValueError('dependency names unread part in ' + artifact['name'])
    for part in artifact['parts']:
        if role_of(part) != artifact['role'] and part not in covered:
            raise ValueError('no dependency record for part ' + part + ' in ' + artifact['name'])


def derivation_filename(artifact):
    """Bound the record/partial basename even when a regulatory PNG name already uses 254 characters."""
    name = os.path.basename(os.fspath(artifact))
    if len((name + DERIVATION_SUFFIX + '.partial').encode('utf-8')) > 255:
        name = sha256_bytes(name.encode('utf-8'))
    return name + DERIVATION_SUFFIX


def write_export_derivation(artifacts, master, store_dir, builder_commit='unknown', master_sha256=None, inputs=(),
                            role=None, dependencies=None, source_id=None):
    """Exporter hook (#1505): write `<store>/<first artifact>.derivation.json` (new file, never replaced).

    Every refusal (no artifact, master changed during the export, existing record, record aliasing an input, unknown
    role) happens before the store folder or the record is created."""
    artifacts = [os.fspath(p) for p in artifacts]
    rec = derivation_record(artifacts, master, builder_commit, master_sha256, role, dependencies, source_id)
    inputs = list(inputs) + [os.fspath(d['master']) for d in dependencies or []]
    store_dir = os.fspath(store_dir)
    path = os.path.join(store_dir, derivation_filename(artifacts[0]))
    taken = {os.path.normcase(os.path.realpath(p)) for p in list(artifacts) + [os.fspath(master)] + list(inputs)}
    for p in (path, path + '.partial'):
        if os.path.normcase(os.path.realpath(p)) in taken:
            raise ValueError('output {} is an input'.format(p))
        if os.path.lexists(p):
            raise FileExistsError('refusing to overwrite: ' + p)
    os.makedirs(store_dir, exist_ok=True)
    return write_new(path, dumps(rec), list(artifacts) + [os.fspath(master)] + list(inputs))


def derivation_files(paths):
    """`--derivation` operands: a record file as is, a store folder -> its `*.derivation.json` in name order."""
    out = []
    for p in paths:
        p = os.fspath(p)
        if os.path.isdir(p):
            found = sorted(n for n in os.listdir(p) if n.endswith(DERIVATION_SUFFIX))
            if not found:
                raise ValueError('derivation store {} has no derivation record'.format(p))
            out += [os.path.join(p, n) for n in found]
        else:
            out.append(p)
    return out


def git_commit(root):
    """HEAD of the repository at `root`, or 'unknown' (never a guess)."""
    import subprocess
    try:
        r = subprocess.run(['git', '-C', os.fspath(root), 'rev-parse', 'HEAD'], capture_output=True, text=True,
                           timeout=30)
    except (OSError, subprocess.SubprocessError):
        return 'unknown'
    sha = r.stdout.strip()
    return sha if r.returncode == 0 and COMMIT.match(sha) else 'unknown'


# ---- NPM atlas bound to the master (#1505) ------------------------------------------------------------------
class AtlasBindingError(ValueError):
    """Atlas refused for this master; `reason` is atlas_unbound | atlas_master_mismatch | atlas_udim_mismatch."""

    def __init__(self, reason, detail):
        self.reason = reason
        super().__init__('{}: {}'.format(reason, detail))


def _atlas_udims(finishes):
    if not isinstance(finishes, dict) or not finishes:
        raise AtlasBindingError('atlas_udim_mismatch', 'atlas has no finish region')
    udims = []
    for name, region in finishes.items():
        udim = region.get('udim') if isinstance(region, dict) else None
        if type(udim) is not int:
            raise AtlasBindingError('atlas_udim_mismatch', 'finish {} has no integer UDIM'.format(name))
        udims.append(udim)
    return sorted(udims)


def atlas_master_binding(master, finishes):
    """`npm_atlas.json` key `master`: the master file name, its SHA-256 and the UDIM tiles the atlas maps."""
    master = os.fspath(master)
    if not os.path.isfile(master) or not os.path.getsize(master):
        raise ValueError('atlas: empty or missing master ' + master)
    return {'name': os.path.basename(master), 'sha256': sha256_file(master), 'udims': _atlas_udims(finishes)}


def check_atlas_master(atlas, master_sha256):
    """The atlas binding when it names exactly this master revision and the atlas's own UDIM set; else
    AtlasBindingError with a named reason. A missing/malformed binding is `atlas_unbound`, never a pass."""
    _sha(master_sha256, 'current master sha256')
    if not isinstance(atlas, dict):
        raise AtlasBindingError('atlas_unbound', 'npm_atlas.json is not an object')
    b = atlas.get('master')
    if not isinstance(b, dict) or set(b) != ATLAS_MASTER_KEYS or not isinstance(b.get('sha256'), str) \
            or not SHA.match(b['sha256']):
        raise AtlasBindingError('atlas_unbound', 'npm_atlas.json has no master binding {name, sha256, udims}; '
                                'regenerate the atlas with --master')
    if b['sha256'] != master_sha256:
        raise AtlasBindingError('atlas_master_mismatch', 'atlas bound to master {} sha256 {}, current master {}'.format(
            b['name'], b['sha256'][:12], master_sha256[:12]))
    want = _atlas_udims(atlas.get('finishes'))
    got = b['udims']
    if not isinstance(got, list) or any(type(u) is not int for u in got) or got != want:
        raise AtlasBindingError('atlas_udim_mismatch', 'binding udims {!r} != atlas finish udims {}'.format(got, want))
    return b


def check_derivation(rec):
    _keys(rec, DERIVATION_KEYS, 'derivation', DERIVATION_REQUIRED)
    if 'source_id' in rec:
        _source_id(rec['source_id'])
    if 'master_path' in rec and (not isinstance(rec['master_path'], str) or not rec['master_path'].strip()):
        raise ValueError('derivation master_path must be a non-empty path')
    if rec['schema'] != DERIVATION_SCHEMA:
        raise ValueError('derivation schema {!r} != {!r}'.format(rec['schema'], DERIVATION_SCHEMA))
    if 'role' in rec:
        _role(rec['role'], 'derivation')
    if 'dependencies' in rec:
        check_dependencies(rec['dependencies'])
    _sha(rec['master_sha256'], 'derivation master_sha256')
    if not isinstance(rec['artifacts'], dict) or not rec['artifacts']:
        raise ValueError('derivation artifacts must be a non-empty object')
    for name, a in rec['artifacts'].items():
        _keys(a, {'kind', 'sha256'}, 'derivation artifact ' + name)
        _sha(a['sha256'], 'derivation artifact {} sha256'.format(name))
        if a['kind'] != kind_of(name):
            raise ValueError('derivation artifact {} kind {!r} != {!r}'.format(name, a['kind'], kind_of(name)))
    return rec


# ---- export owner readback ----------------------------------------------------------------------------------
def ucx_binding(names):
    """{UCX mesh: visual mesh or None}: `UCX_<Visual>` or `UCX_<Visual>_NN` must name a render mesh of the same file."""
    visual = {n for n in names if not UCX.match(n)}
    out = {}
    for n in sorted(names):
        m = UCX.match(n)
        if not m:
            continue
        rest = m.group('rest')
        stripped = re.sub(r'_[0-9]+$', '', rest)
        out[n] = rest if rest in visual else stripped if stripped in visual else None
    return out


def _vec3(value):
    """[x, y, z] of exactly 3 finite real numbers (bool refused), else None (#1434: fail closed)."""
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in value):
        return None
    return [float(v) for v in value]


def readback_summary(name, data_sha256, rb):
    """Export owner readback of one exported FBX: dimensions, part positions, materials, UV, UCX binding + status.

    `rb` is the tools/blender/fbx_readback.py report of exactly the zipped bytes (`data_sha256`)."""
    problems = []
    meshes = []
    if not isinstance(rb, dict) or rb.get('readback_ok') is not True:
        problems.append('readback not ok')
    for m in (rb or {}).get('meshes', []) if isinstance(rb, dict) else []:
        bounds = m.get('bounds_m')
        lo, hi = bounds if isinstance(bounds, (list, tuple)) and len(bounds) == 2 else (None, None)
        lo, hi = _vec3(lo), _vec3(hi)
        dims = None if lo is None or hi is None else [round(b - a, 6) for a, b in zip(lo, hi)]
        loc = _vec3(m.get('location'))
        row = {'name': m.get('name'), 'dimensions_m': dims,
               'location': None if loc is None else [round(v, 6) for v in loc],
               'materials': list(m.get('materials', [])), 'uv_channels': m.get('uv_channels'),
               'triangles': m.get('triangles')}
        meshes.append(row)
        if not UCX.match(str(row['name'])):
            if not row['materials'] or None in row['materials']:
                problems.append('{}: empty material slot'.format(row['name']))
            if not row['uv_channels']:
                problems.append('{}: no UV channel'.format(row['name']))
        if dims is None or not all(math.isfinite(d) for d in dims):
            problems.append('{}: dimensions not read (bounds_m must be 2 x 3 finite numbers)'.format(row['name']))
        if loc is None:
            problems.append('{}: location not read (must be 3 finite numbers)'.format(row['name']))
    if not meshes:
        problems.append('no mesh read back')
    binding = ucx_binding([m['name'] for m in meshes])
    problems += ['{}: no visual mesh of that name'.format(u) for u, v in sorted(binding.items()) if v is None]
    return {'name': name, 'sha256': data_sha256, 'blender': (rb or {}).get('blender') if isinstance(rb, dict) else None,
            'meshes': meshes, 'ucx_binding': binding, 'problems': problems,
            'status': 'fail' if problems else 'pass'}


def readback_report(package_zip, summaries):
    """Readback report of every FBX member: status pass only when every FBX was read back and passed."""
    members = zip_members(package_zip)
    fbx = sorted(n for n in members if n.lower().endswith('.fbx'))
    got = {s['name']: s for s in summaries}
    missing = [n for n in fbx if n not in got]
    stale = [n for n in fbx if n in got and got[n]['sha256'] != members[n]]
    status = 'pass' if fbx and not missing and not stale and all(got[n]['status'] == 'pass' for n in fbx) else 'fail'
    return {'schema': READBACK_SCHEMA, 'owner': EXPORT_OWNER, 'package': os.path.basename(os.fspath(package_zip)),
            'status': status, 'finished': not missing, 'missing': missing, 'stale': stale,
            'files': [got[n] for n in fbx if n in got]}


# ---- manifest ---------------------------------------------------------------------------------------------
def _masters_by_role(masters, roles):
    """One path for a one-role package, or {role: path | [independent paths]} [D332]."""
    if isinstance(masters, dict):
        out = {_role(r, 'build manifest master'): p for r, p in masters.items()}
    elif len(roles) == 1:
        out = {next(iter(roles)): os.fspath(masters)}
    else:
        raise ValueError('build manifest: package has roles {}: give one master per role (--master role=path, '
                         '[D328])'.format(sorted(roles)))
    missing = sorted(set(roles) - set(out))
    if missing:
        raise ValueError('build manifest: no master for role(s) {} (--master role=path)'.format(missing))
    unused = sorted(set(out) - set(roles))
    if unused:
        raise ValueError('build manifest: master given for role(s) {} but the package has no such member'.format(
            unused))
    for r, p in out.items():
        paths = p if isinstance(p, list) else [p]
        if not paths:
            raise ValueError('build manifest: empty sources for ' + r)
        names, identities = set(), set()
        for path in paths:
            path = os.fspath(path)
            name = os.path.basename(path).casefold()
            identity = os.path.normcase(os.path.realpath(path))
            if not os.path.isfile(path) or not os.path.getsize(path):
                raise ValueError('build manifest: no {} master file {}'.format(r, path))
            alias = any(os.path.isfile(other) and os.path.samefile(path, other) for other in paths if other != path)
            if name in names or identity in identities or alias:
                raise ValueError('build manifest: source given twice for {}: {}'.format(r, path))
            names.add(name)
            identities.add(identity)
    return out


def source_entries(entry):
    """All independent source descriptors for a role; v1/v2 retain their single-source layout."""
    return entry.get('sources', [entry])


def master_hashes(master):
    """Hash CLI/API paths without dropping a repeated role's independent sources [D332]."""
    if isinstance(master, dict):
        return {r: [sha256_file(p) for p in paths] if isinstance(paths, list) else sha256_file(paths)
                for r, paths in master.items()}
    return sha256_file(master) if master is not None else None


def make_manifest(package_zip, master, builder_commit, derivations, transform, readback=None, readback_file=None,
                  build_id=None, now=None):
    """Manifest dict of one package. Every member needs a derivation record (an unrecorded member is an error naming
    it); the master revision named by each record is kept as is, so a stale artifact shows up as a mismatch.

    master: {role: path} ([D328]: OKS from its .blend, Ground from its own source) or one path for a one-role
    package. A record whose role disagrees with the member name grammar is refused naming the member."""
    package_zip = os.fspath(package_zip)
    if not COMMIT.match(str(builder_commit)):
        raise ValueError('build manifest: builder_commit must be a git sha or unknown')
    members = zip_members(package_zip)
    by_name = {}
    for rec in derivations:
        check_derivation(rec)
        for name, a in rec['artifacts'].items():
            role = rec.get('role', role_of(name))
            if name in members and role != role_of(name):
                raise ValueError('build manifest: derivation record of {} names role {!r} but the member is a {!r} '
                                 'artifact by name; each part keeps its own master [D328]'.format(
                                     name, role, role_of(name)))
            if name in by_name and by_name[name][0] != rec['master_sha256']:
                raise ValueError('build manifest: two derivation records for {} name different masters'.format(name))
            row = (rec['master_sha256'], a['sha256'], role, rec.get('dependencies'), rec['master_name'], rec.get('source_id'))
            if name in by_name and by_name[name] != row:
                raise ValueError('build manifest: conflicting derivation records for ' + name)
            by_name[name] = row
    unrecorded = sorted(set(members) - set(by_name))
    if unrecorded:
        raise ValueError('build manifest: no derivation record for member(s) {}'.format(unrecorded))
    roles = {by_name[n][2] for n in members}
    roles.update(d['role'] for n in members for d in by_name[n][3] or [])
    masters = _masters_by_role(master, roles)
    parts = {}
    if readback is not None:
        parts = {f['name']: sorted(m['name'] for m in f['meshes']) for f in readback['files']}
    artifacts = [{'name': n, 'kind': kind_of(n), 'role': by_name[n][2], 'sha256': members[n],
                  'derived_sha256': by_name[n][1], 'master_sha256': by_name[n][0], 'parts': parts.get(n, [])}
                 for n in sorted(members)]
    for artifact in artifacts:
        deps = by_name[artifact['name']][3]
        if deps is not None:
            artifact['dependencies'] = deps
        if readback is not None:
            check_component_coverage(artifact)
    checks = []
    if readback is not None:
        checks.append({'id': 'fbx_readback', 'owner': readback['owner'], 'required': True,
                       'status': readback['status'], 'finished': bool(readback['finished']),
                       'report': os.path.basename(readback_file) if readback_file else None,
                       'report_sha256': sha256_file(readback_file) if readback_file else None,
                       'subjects': {f['name']: f['sha256'] for f in readback['files']}})
    entries = {}
    for r, paths in sorted(masters.items()):
        paths = paths if isinstance(paths, list) else [paths]
        sources = [{'name': os.path.basename(p), 'sha256': sha256_file(p), 'builder_commit': str(builder_commit)}
                   for p in paths]
        entries[r] = dict(sources[0])
        if len(sources) > 1:
            entries[r]['sources'] = sources
    # Even a legacy-compatible output must not erase an explicitly declared revision conflict.
    revisions = {}
    for artifact in artifacts:
        digest, _, _, deps, _, sid = by_name[artifact['name']]
        for identity, sha in [(sid, digest)] + [(d.get('source_id'), d['master_sha256']) for d in deps or []]:
            if identity is not None:
                if identity in revisions and revisions[identity] != sha:
                    raise ValueError('two revisions of source_id ' + identity)
                revisions[identity] = sha
    multi = any('sources' in e for e in entries.values()) or any('dependencies' in a for a in artifacts)
    # Partial migration must not make a legacy single-source role require an invented id.
    # Fully identified packages opt into v3; genuinely multi-source packages always require it.
    multi = multi or all(by_name[a['name']][5] is not None for a in artifacts)
    if multi:
        for artifact in artifacts:
            artifact['master_name'] = by_name[artifact['name']][4]
            artifact['source_id'] = by_name[artifact['name']][5]
        bindings = [b for a in artifacts for b in [a] + a.get('dependencies', [])]
        used_names = {(b['role'], b['master_name']) for b in bindings}
        unused = [(r, s['name']) for r, e in entries.items() for s in source_entries(e)
                  if (r, s['name']) not in used_names]
        if unused:
            raise ValueError('unused declared source(s): ' + repr(unused))
        for artifact in artifacts:
            for binding in [artifact] + artifact.get('dependencies', []):
                try:
                    _source_id(binding.get('source_id'))
                except ValueError as exc:
                    raise ValueError('{}: {}'.format(artifact['name'], exc)) from exc
        for r, entry in entries.items():
            for source in source_entries(entry):
                used = [b for b in bindings if b['role'] == r and b['master_name'] == source['name']]
                ids = {_source_id(b.get('source_id')) for b in used}
                if len(ids) != 1:
                    raise ValueError('conflicting source_id for ' + source['name'])
                source['source_id'] = next(iter(ids))
            if 'sources' in entry:
                entry['source_id'] = entry['sources'][0]['source_id']
        check_source_bindings(entries, artifacts)
    first = entries['oks' if 'oks' in entries else sorted(entries)[0]]['sha256']
    now = now or datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    stem = os.path.basename(package_zip)[:-4]
    return {'schema': SCHEMA_MULTI if multi else SCHEMA,
            'build_id': build_id or '{}-{}-{}'.format(stem, now, first[:8]),
            'created_utc': now,
            'package': {'name': os.path.basename(package_zip), 'sha256': sha256_file(package_zip)},
            'masters': entries,
            'transform': transform, 'artifacts': artifacts, 'checks': checks}


def transform_entry(name, path=None):
    if not isinstance(name, str) or not name.strip():
        raise ValueError('build manifest: transform name required (e.g. identity, 1371-bridge)')
    if path is None:
        return {'name': name, 'file': None, 'sha256': None}
    return {'name': name, 'file': os.path.basename(os.fspath(path)), 'sha256': sha256_file(path)}


def write_new(path, data, inputs=()):
    """Exclusive write via `<path>.partial`; refuses an existing file or an alias of an input; leaves no temp."""
    path = os.fspath(path)
    partial = path + '.partial'
    taken = {os.path.normcase(os.path.realpath(os.fspath(p))) for p in inputs}
    for p in (path, partial):
        if os.path.normcase(os.path.realpath(p)) in taken:
            raise ValueError('output {} is an input'.format(p))
        if os.path.lexists(p):
            raise FileExistsError('refusing to overwrite: ' + p)
    with open(partial, 'xb') as fh:
        fh.write(data)
    try:
        os.link(partial, path)
    finally:
        os.unlink(partial)
    return path


def dumps(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False) + '\n').encode('utf-8')


# ---- refusal logic ------------------------------------------------------------------------------------------
def check_source_bindings(entries, artifacts):
    """V3: explicit producer identities, one revision per id, and no unused declared source."""
    revisions, declared, used = {}, set(), set()
    def bind(source_id, digest):
        source_id = _source_id(source_id)
        if source_id in revisions and revisions[source_id] != digest:
            raise ValueError('two revisions of source_id ' + source_id)
        revisions[source_id] = digest
        return source_id
    for role, entry in entries.items():
        for source in source_entries(entry):
            sid = bind(source.get('source_id'), source['sha256'])
            declared.add((role, sid, source['name'], source['sha256']))
    for artifact in artifacts:
        for row in [artifact] + artifact.get('dependencies', []):
            sid = bind(row.get('source_id'), row['master_sha256'])
            key = (row['role'], sid, row['master_name'], row['master_sha256'])
            if key not in declared:
                raise ValueError('undeclared source_id {} ({})'.format(sid, row['master_name']))
            used.add(key)
    unused = sorted(declared - used)
    if unused:
        raise ValueError('unused declared source(s): ' + repr(unused))


def parse_manifest(data):
    """Strict read of a build manifest. v2 ([D328]) `masters` by role; v1 (one `master`) is normalized to v2: that one
    master stands for every role present and each artifact gets its role from its name."""
    m = strict_json(data)
    v1 = isinstance(m, dict) and m.get('schema') == SCHEMA_V1
    _keys(m, TOP_KEYS_V1 if v1 else TOP_KEYS, 'manifest')
    if m['schema'] not in (SCHEMA, SCHEMA_V1, SCHEMA_MULTI):
        raise ValueError('manifest schema {!r} != {!r}'.format(m['schema'], SCHEMA))
    if not isinstance(m['build_id'], str) or not m['build_id']:
        raise ValueError('manifest build_id must be a non-empty string')
    _keys(m['package'], {'name', 'sha256'}, 'manifest package')
    _sha(m['package']['sha256'], 'manifest package sha256')
    if not isinstance(m['artifacts'], list) or not m['artifacts']:
        raise ValueError('manifest artifacts must be a non-empty list')
    if v1:
        _keys(m['master'], MASTER_KEYS, 'manifest master')
        for a in m['artifacts']:
            _keys(a, ARTIFACT_KEYS_V1, 'manifest artifact')
            a['role'] = role_of(a['name'])
        m['masters'] = {r: dict(m['master']) for r in sorted({a['role'] for a in m['artifacts']})}
        del m['master']
        m['schema'] = SCHEMA
    if not isinstance(m['masters'], dict) or not m['masters']:
        raise ValueError('manifest masters must be a non-empty object keyed by role')
    for r, e in m['masters'].items():
        _role(r, 'manifest masters')
        source_keys = MASTER_KEYS | ({'source_id'} if m['schema'] == SCHEMA_MULTI else set())
        _keys(e, source_keys | ({'sources'} if m['schema'] == SCHEMA_MULTI else set()),
              'manifest masters ' + r, required=source_keys)
        sources = source_entries(e)
        if not isinstance(sources, list) or not sources:
            raise ValueError('manifest sources must be a non-empty list: ' + r)
        names = set()
        for source in sources:
            _keys(source, source_keys, 'manifest source ' + r)
            if not isinstance(source['name'], str) or not source['name'].strip():
                raise ValueError('manifest source name required: ' + r)
            if source['name'].casefold() in names:
                raise ValueError('manifest source given twice: ' + source['name'])
            names.add(source['name'].casefold())
            _sha(source['sha256'], 'manifest masters {} sha256'.format(r))
            if not COMMIT.match(str(source['builder_commit'])):
                raise ValueError('manifest masters {} builder_commit must be a git sha or unknown'.format(r))
        if 'sources' in e and {k: e[k] for k in source_keys} != sources[0]:
            raise ValueError('manifest primary source differs from sources[0]: ' + r)
    _keys(m['transform'], TRANSFORM_KEYS, 'manifest transform')
    if not isinstance(m['transform']['name'], str) or not m['transform']['name'].strip():
        raise ValueError('manifest transform name required')
    if (m['transform']['file'] is None) != (m['transform']['sha256'] is None):
        raise ValueError('manifest transform file and sha256 go together')
    if m['transform']['sha256'] is not None:
        _sha(m['transform']['sha256'], 'manifest transform sha256')
    seen = set()
    for a in m['artifacts']:
        multi = m['schema'] == SCHEMA_MULTI
        _keys(a, ARTIFACT_KEYS | ({'dependencies', 'master_name', 'source_id'} if multi else set()),
              'manifest artifact', required=ARTIFACT_KEYS | ({'master_name', 'source_id'} if multi else set()))
        if multi and (not isinstance(a['master_name'], str) or not a['master_name'].strip()):
            raise ValueError('manifest artifact master_name required')
        if 'dependencies' in a:
            check_dependencies(a['dependencies'])
        if a['name'] in seen:
            raise ValueError('manifest artifact listed twice: ' + str(a['name']))
        seen.add(a['name'])
        _role(a['role'], 'manifest artifact {}'.format(a['name']))
        if a['role'] != role_of(str(a['name'])):  # [D328]: the role follows the delivery name grammar
            raise ValueError('manifest artifact {} role {!r} != {!r} by name'.format(
                a['name'], a['role'], role_of(str(a['name']))))
        for k in ('sha256', 'derived_sha256', 'master_sha256'):
            _sha(a[k], 'manifest artifact {} {}'.format(a['name'], k))
        if a['kind'] not in KINDS:
            raise ValueError('manifest artifact {} kind {!r} unsupported'.format(a['name'], a['kind']))
        want = kind_of(str(a['name']))  # #1434 P3: kind follows the delivery name grammar
        if a['kind'] != want:
            raise ValueError('manifest artifact {} kind {!r} != {!r}'.format(a['name'], a['kind'], want))
        if not isinstance(a['parts'], list) or not all(isinstance(p, str) for p in a['parts']):
            raise ValueError('manifest artifact {} parts must be a list of names'.format(a['name']))
    roles = {a['role'] for a in m['artifacts']}
    roles.update(d['role'] for a in m['artifacts'] for d in a.get('dependencies', []))
    for a in m['artifacts'] if m['schema'] == SCHEMA_MULTI else []:
        check_component_coverage(a)
    if set(m['masters']) != roles:
        raise ValueError('manifest masters {} != artifact roles {} (one master per role present)'.format(
            sorted(m['masters']), sorted(roles)))
    if m['schema'] == SCHEMA_MULTI:
        check_source_bindings(m['masters'], m['artifacts'])
    if not isinstance(m['checks'], list):
        raise ValueError('manifest checks must be a list')
    ids = set()
    for c in m['checks']:
        _keys(c, CHECK_KEYS, 'manifest check')
        if c['id'] in ids:
            raise ValueError('manifest check listed twice: ' + str(c['id']))
        ids.add(c['id'])
        if not isinstance(c['subjects'], dict):
            raise ValueError('manifest check {} subjects must be an object'.format(c['id']))
    return m


def report_disagreements(path, check, members, fbx, artifacts=None):
    """#1434: what the check report says vs the manifest check entry and the zipped bytes; [] = they agree.

    A hash-matching report proves only that the file was not edited after the build, not that it says pass."""
    try:
        with open(path, 'rb') as fh:
            rep = strict_json(fh.read())
    except (OSError, ValueError, TypeError, UnicodeDecodeError) as exc:
        return ['unreadable: {}'.format(str(exc)[:300])]
    if not isinstance(rep, dict):
        return ['unreadable: not a JSON object']
    out = []
    if rep.get('schema') != READBACK_SCHEMA:
        out.append('schema {!r} != {!r}'.format(rep.get('schema'), READBACK_SCHEMA))
    if rep.get('status') != check['status']:
        out.append('status {!r} != manifest {!r}'.format(rep.get('status'), check['status']))
    if rep.get('finished') is not check['finished']:
        out.append('finished {!r} != manifest {!r}'.format(rep.get('finished'), check['finished']))
    files = rep.get('files')
    if not isinstance(files, list) or not all(isinstance(f, dict) for f in files):
        return out + ['files must be a list of objects']
    got = {}
    for f in files:
        if f.get('name') in got:
            out.append('files list {!r} twice'.format(f.get('name')))
        got[f.get('name')] = f
        if artifacts is not None and f.get('name') in artifacts:
            meshes = f.get('meshes')
            if not isinstance(meshes, list) or not all(isinstance(x, dict) and isinstance(x.get('name'), str) for x in meshes):
                out.append('readback mesh inventory missing: ' + str(f.get('name')))
            elif sorted(x['name'] for x in meshes) != sorted(artifacts[f['name']]['parts']):
                out.append('readback parts differ from manifest: ' + str(f['name']))
    sha = {n: f.get('sha256') for n, f in got.items()}
    subj = check['subjects']
    differ = sorted(str(n) for n in set(sha) | set(subj) if sha.get(n) != subj.get(n))
    if differ:
        out.append('files[].sha256 differ from the manifest subjects: {}'.format(differ))
    off = sorted(n for n in fbx if sha.get(n) != members.get(n))
    if off:
        out.append('files[].sha256 differ from the zipped bytes or are missing: {}'.format(off))
    if check['status'] == 'pass':
        bad = sorted(str(n) for n, f in got.items() if f.get('status') != 'pass')
        if bad:
            out.append('file status not pass while the report passes: {}'.format(bad))
    return out


def manifest_findings(manifest_bytes, members, package_name, package_sha256=None, master_sha256=None,
                      report_dir=None):
    """[(status, code, detail)] of one package against its manifest; empty `members` is refused.

    members: {zipped member name: sha256}; master_sha256: hash of the master file given now (stale check);
    report_dir: folder where check reports are read (beside the ZIP)."""
    if manifest_bytes is None:
        return [('not_run', 'manifest_missing', 'no build manifest {} beside the package: delivery set consistency '
                 'not proven (agr build-manifest build)'.format(package_name[:-4] + SUFFIX))]
    try:
        m = parse_manifest(manifest_bytes)
    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        return [('fail', 'manifest_unreadable', str(exc)[:900])]
    out = []
    if not members:
        return [('fail', 'manifest_hash_mismatch', 'package has no member to compare')]
    if m['package']['name'] != package_name:
        out.append(('fail', 'manifest_package', 'manifest names {!r}, package is {!r}'.format(
            m['package']['name'], package_name)))
    if package_sha256 is not None and m['package']['sha256'] != package_sha256:
        out.append(('fail', 'manifest_package', 'package sha256 {} != manifest {}'.format(
            package_sha256[:12], m['package']['sha256'][:12])))
    arts = {a['name']: a for a in m['artifacts']}
    unlisted = sorted(set(members) - set(arts))
    absent = sorted(set(arts) - set(members))
    if unlisted:
        out.append(('fail', 'manifest_member_unlisted', 'zipped but not in the manifest: {}'.format(unlisted)))
    if absent:
        out.append(('fail', 'manifest_member_missing', 'in the manifest but not zipped: {}'.format(absent)))
    bad = sorted(n for n in set(members) & set(arts) if arts[n]['sha256'] != members[n])
    if bad:
        out.append(('fail', 'manifest_hash_mismatch', 'zipped bytes differ from the manifest: {}'.format(bad)))
    changed = sorted(n for n, a in arts.items() if a['derived_sha256'] != a['sha256'])
    if changed:
        out.append(('fail', 'manifest_derived_changed', 'artifact changed after its export record: {}'.format(changed)))
    masters = {r: {s['sha256'] for s in source_entries(e)} for r, e in m['masters'].items()}
    current = master_sha256
    if isinstance(current, str):
        # one unkeyed master: valid for a one-role manifest only; else no role is checked (never a guess)
        current = {next(iter(masters)): current} if len(masters) == 1 else {}
    elif current is None:
        current = {}
    revisions = {}
    for n, a in sorted(arts.items()):
        source_ids = {(s['name'], s['sha256']) for s in source_entries(m['masters'][a['role']])}
        if a['master_sha256'] not in masters[a['role']] or ('master_name' in a and
                (a['master_name'], a['master_sha256']) not in source_ids):
            revisions.setdefault((a['role'], a['master_sha256']), []).append(n)
        for dep in a.get('dependencies', []):
            dep_ids = {(s['name'], s['sha256']) for s in source_entries(m['masters'][dep['role']])}
            if (dep['master_name'], dep['master_sha256']) not in dep_ids:
                revisions.setdefault((dep['role'], dep['master_sha256']), []).append(n + ':' + ','.join(dep['parts']))
    if revisions:
        detail = '; '.join('role {}: {} derived from master {} (build {} master {})'.format(
            r, ns, s[:12], r, sorted(masters[r])) for (r, s), ns in sorted(revisions.items()))
        out.append(('fail', 'manifest_master_mismatch', 'artifacts name different master revisions: ' + detail))
    foreign = sorted(str(r) for r in current if r not in masters)
    if foreign:
        out.append(('fail', 'manifest_master_role', 'master given for role(s) {} but the package has only {} '
                    '[D328]'.format(foreign, sorted(masters))))
    unchecked = sorted(r for r in masters if r not in current)
    if unchecked:
        # no master given -> the stale check did not run; never pass without it (#1423 r1 P1)
        out.append(('not_run', 'manifest_master_unchecked', 'manifest_master_unchecked: master not given for role(s) '
                    '{}, the build master was not compared with the current master (agr validate --master '
                    'role=path)'.format(', '.join('{} {}'.format(r, sorted(masters[r])) for r in unchecked))))
    for r in sorted(masters):
        hashes = current.get(r)
        hashes = hashes if isinstance(hashes, list) else [hashes]
        if r in current and (set(hashes) != masters[r] or len(hashes) != len(source_entries(m['masters'][r]))):
            out.append(('fail', 'manifest_master_stale', 'role {} master now {} != build master {}: rebuild every '
                        '{} artifact'.format(r, str(current[r]), sorted(masters[r]), r)))
    checks = {c['id']: c for c in m['checks']}
    fbx = sorted(n for n in members if n.lower().endswith('.fbx'))
    for cid in REQUIRED_CHECKS:
        c = checks.get(cid)
        if c is None:
            out.append(('fail', 'manifest_check_not_ready', 'required check {} did not run'.format(cid)))
            continue
        if c['required'] is not True or c['finished'] is not True or c['status'] != 'pass':
            out.append(('fail', 'manifest_check_not_ready', 'required check {}: status {!r}, finished {!r}, '
                        'required {!r} (skipped = not ready)'.format(cid, c['status'], c['finished'], c['required'])))
        subj = c['subjects'] if isinstance(c['subjects'], dict) else {}
        uncovered = [n for n in fbx if n not in subj]
        wrong = sorted(n for n in subj if members.get(n) != subj[n])
        if uncovered or wrong:
            out.append(('fail', 'manifest_report_hash', 'check {} ran on other files: uncovered {}, hash/name differs '
                        '{}'.format(cid, uncovered, wrong)))
        if c['report'] is None or c['report_sha256'] is None:
            out.append(('fail', 'manifest_report_hash', 'check {} has no report file'.format(cid)))
        elif report_dir is not None:
            path = os.path.join(report_dir, os.path.basename(str(c['report'])))
            if not os.path.isfile(path):
                out.append(('fail', 'manifest_report_hash', 'check {} report {} missing'.format(cid, c['report'])))
            elif sha256_file(path) != c['report_sha256']:
                out.append(('fail', 'manifest_report_hash', 'check {} report {} changed after the build'.format(
                    cid, c['report'])))
            else:
                out += [('fail', 'manifest_report_hash', 'check {} report {}: {}'.format(cid, c['report'], p))
                        for p in report_disagreements(path, c, members, fbx, arts if m['schema'] == SCHEMA_MULTI else None)]
    for cid, c in sorted(checks.items()):
        if cid not in REQUIRED_CHECKS and c['required'] is True and (c['status'] != 'pass' or c['finished'] is not True):
            out.append(('fail', 'manifest_check_not_ready', 'required check {}: status {!r}, finished {!r}'.format(
                cid, c['status'], c['finished'])))
    if not out:
        out.append(('pass', 'manifest_ok', 'build {}: {} artifacts from masters {} (builder {}), transform {}'.format(
            m['build_id'], len(arts), ', '.join('{} {}'.format(r, sorted(s)) for r, s in sorted(masters.items())),
            sorted({e['builder_commit'] for e in m['masters'].values()}), m['transform']['name'])))
    return out


def manifest_masters(path):
    """{role: source fingerprint}; v3 fingerprints include EVERY source's name/hash in sorted order [D332]."""
    try:
        with open(path, 'rb') as fh:
            return {r: e['sha256'] if 'sources' not in e else sha256_bytes(dumps(sorted(
                (s['name'], s['sha256']) for s in source_entries(e))))
                for r, e in parse_manifest(fh.read())['masters'].items()}
    except (OSError, ValueError, TypeError, UnicodeDecodeError):
        return None
