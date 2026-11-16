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

Masters per role (#1525, [D328]): each part of a package keeps its own master. The role of a member follows the delivery
name grammar (`role_of`: a `Ground` name token -> `ground`, else `oks`); OKS artifacts are derived from the OKS master
(.blend), Ground artifacts from their own source (e.g. the ground mesh JSON of tools/blender/ground_json_to_fbx.py).
Schema v2 keeps `masters` keyed by role; two revisions of ONE role are refused, different masters of different roles
are not. A record whose role disagrees with the member name is refused naming the member (no false provenance).
Schema v1 manifests (one `master`) are still read: that one master stands for every role.

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
SCHEMA_V1 = 'agr.build_manifest/1'
ROLES = ('oks', 'ground')  # [D328]: one master per role
GROUND_TOKEN = re.compile(r'(?:^|_)Ground(?:_|$)')
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
DERIVATION_KEYS = {'schema', 'master_name', 'master_sha256', 'builder_commit', 'artifacts', 'master_path', 'role'}
# master_path: #1505 export-time records; role: #1525 records; older records lack them (role then follows the name)
DERIVATION_REQUIRED = DERIVATION_KEYS - {'master_path', 'role'}
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
    """Package role of a member by the delivery name grammar ([D328]): a `Ground` token in the stem -> 'ground'
    (`<NNNN>_<A>_Ground.fbx`, `SM_<A>_Ground.fbx`, `SM_<A>_Ground_Light.fbx`), else 'oks'."""
    stem = os.path.splitext(os.path.basename(str(name)))[0]
    return 'ground' if GROUND_TOKEN.search(stem) else 'oks'


def _role(value, where):
    if value not in ROLES:
        raise ValueError('{} role {!r} unsupported (roles: {})'.format(where, value, ', '.join(ROLES)))
    return value


def master_args(values):
    """`--master` operands -> one path (legacy, unkeyed) or {role: path} (`role=path`, [D328]); errors name the
    operand: unknown role, a role given twice, an empty path, keyed mixed with unkeyed, no master."""
    values = [os.fspath(v) for v in values or ()]
    if not values:
        raise ValueError('no --master given')
    keyed, plain = {}, []
    for v in values:
        role, sep, path = v.partition('=')
        if sep and re.fullmatch(r'[A-Za-z_]+', role):
            _role(role, '--master ' + v)
            if role in keyed:
                raise ValueError('--master role {} given twice'.format(role))
            if not path.strip():
                raise ValueError('--master {}: empty path'.format(v))
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
def derivation_record(artifacts, master, builder_commit, master_sha256=None, role=None):
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
    return {'schema': DERIVATION_SCHEMA, 'master_name': os.path.basename(master), 'master_sha256': now,
            'master_path': os.path.abspath(master), 'builder_commit': str(builder_commit), 'artifacts': rec,
            'role': role}


def derivation_store(export_dir):
    """Export-time record store of one export: `<parent of the exported folder>/derivation/` (#1505).

    Outside the exported folder on purpose: package_vpm zips every file of its package folder."""
    return os.path.join(os.path.dirname(os.path.abspath(os.fspath(export_dir))), DERIVATION_STORE)


def write_export_derivation(artifacts, master, store_dir, builder_commit='unknown', master_sha256=None, inputs=(),
                            role=None):
    """Exporter hook (#1505): write `<store>/<first artifact>.derivation.json` (new file, never replaced).

    Every refusal (no artifact, master changed during the export, existing record, record aliasing an input, unknown
    role) happens before the store folder or the record is created."""
    artifacts = [os.fspath(p) for p in artifacts]
    rec = derivation_record(artifacts, master, builder_commit, master_sha256, role)
    store_dir = os.fspath(store_dir)
    path = os.path.join(store_dir, os.path.basename(artifacts[0]) + DERIVATION_SUFFIX)
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
    if 'master_path' in rec and (not isinstance(rec['master_path'], str) or not rec['master_path'].strip()):
        raise ValueError('derivation master_path must be a non-empty path')
    if rec['schema'] != DERIVATION_SCHEMA:
        raise ValueError('derivation schema {!r} != {!r}'.format(rec['schema'], DERIVATION_SCHEMA))
    if 'role' in rec:
        _role(rec['role'], 'derivation')
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
    """make_manifest `masters`: one path (legacy; valid only for a one-role package) or {role: path} ([D328])."""
    if isinstance(masters, dict):
        out = {_role(r, 'build manifest master'): os.fspath(p) for r, p in masters.items()}
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
        if not os.path.isfile(p):
            raise ValueError('build manifest: no {} master file {}'.format(r, p))
    return out


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
            by_name[name] = (rec['master_sha256'], a['sha256'], role)
    unrecorded = sorted(set(members) - set(by_name))
    if unrecorded:
        raise ValueError('build manifest: no derivation record for member(s) {}'.format(unrecorded))
    masters = _masters_by_role(master, {by_name[n][2] for n in members})
    parts = {}
    if readback is not None:
        parts = {f['name']: sorted(m['name'] for m in f['meshes']) for f in readback['files']}
    artifacts = [{'name': n, 'kind': kind_of(n), 'role': by_name[n][2], 'sha256': members[n],
                  'derived_sha256': by_name[n][1], 'master_sha256': by_name[n][0], 'parts': parts.get(n, [])}
                 for n in sorted(members)]
    checks = []
    if readback is not None:
        checks.append({'id': 'fbx_readback', 'owner': readback['owner'], 'required': True,
                       'status': readback['status'], 'finished': bool(readback['finished']),
                       'report': os.path.basename(readback_file) if readback_file else None,
                       'report_sha256': sha256_file(readback_file) if readback_file else None,
                       'subjects': {f['name']: f['sha256'] for f in readback['files']}})
    entries = {r: {'name': os.path.basename(p), 'sha256': sha256_file(p), 'builder_commit': str(builder_commit)}
               for r, p in sorted(masters.items())}
    first = entries['oks' if 'oks' in entries else sorted(entries)[0]]['sha256']
    now = now or datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    stem = os.path.basename(package_zip)[:-4]
    return {'schema': SCHEMA,
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
def parse_manifest(data):
    """Strict read of a build manifest. v2 ([D328]) `masters` by role; v1 (one `master`) is normalized to v2: that one
    master stands for every role present and each artifact gets its role from its name."""
    m = strict_json(data)
    v1 = isinstance(m, dict) and m.get('schema') == SCHEMA_V1
    _keys(m, TOP_KEYS_V1 if v1 else TOP_KEYS, 'manifest')
    if m['schema'] not in (SCHEMA, SCHEMA_V1):
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
        _keys(e, MASTER_KEYS, 'manifest masters ' + r)
        _sha(e['sha256'], 'manifest masters {} sha256'.format(r))
        if not COMMIT.match(str(e['builder_commit'])):
            raise ValueError('manifest masters {} builder_commit must be a git sha or unknown'.format(r))
    _keys(m['transform'], TRANSFORM_KEYS, 'manifest transform')
    if not isinstance(m['transform']['name'], str) or not m['transform']['name'].strip():
        raise ValueError('manifest transform name required')
    if (m['transform']['file'] is None) != (m['transform']['sha256'] is None):
        raise ValueError('manifest transform file and sha256 go together')
    if m['transform']['sha256'] is not None:
        _sha(m['transform']['sha256'], 'manifest transform sha256')
    seen = set()
    for a in m['artifacts']:
        _keys(a, ARTIFACT_KEYS, 'manifest artifact')
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
    if set(m['masters']) != roles:
        raise ValueError('manifest masters {} != artifact roles {} (one master per role present)'.format(
            sorted(m['masters']), sorted(roles)))
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


def report_disagreements(path, check, members, fbx):
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
    masters = {r: e['sha256'] for r, e in m['masters'].items()}
    current = master_sha256
    if isinstance(current, str):
        # one unkeyed master: valid for a one-role manifest only; else no role is checked (never a guess)
        current = {next(iter(masters)): current} if len(masters) == 1 else {}
    elif current is None:
        current = {}
    revisions = {}
    for n, a in sorted(arts.items()):
        if a['master_sha256'] != masters[a['role']]:
            revisions.setdefault((a['role'], a['master_sha256']), []).append(n)
    if revisions:
        detail = '; '.join('role {}: {} derived from master {} (build {} master {})'.format(
            r, ns, s[:12], r, masters[r][:12]) for (r, s), ns in sorted(revisions.items()))
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
                    'role=path)'.format(', '.join('{} {}'.format(r, masters[r][:12]) for r in unchecked))))
    for r in sorted(masters):
        if r in current and current[r] != masters[r]:
            out.append(('fail', 'manifest_master_stale', 'role {} master now {} != build master {}: rebuild every '
                        '{} artifact'.format(r, str(current[r])[:12], masters[r][:12], r)))
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
                        for p in report_disagreements(path, c, members, fbx)]
    for cid, c in sorted(checks.items()):
        if cid not in REQUIRED_CHECKS and c['required'] is True and (c['status'] != 'pass' or c['finished'] is not True):
            out.append(('fail', 'manifest_check_not_ready', 'required check {}: status {!r}, finished {!r}'.format(
                cid, c['status'], c['finished'])))
    if not out:
        out.append(('pass', 'manifest_ok', 'build {}: {} artifacts from masters {} (builder {}), transform {}'.format(
            m['build_id'], len(arts), ', '.join('{} {}'.format(r, s[:12]) for r, s in sorted(masters.items())),
            sorted({e['builder_commit'] for e in m['masters'].values()}), m['transform']['name'])))
    return out


def manifest_masters(path):
    """{role: master sha256} named by a manifest file, or None when it is unreadable/absent (cross-package check)."""
    try:
        with open(path, 'rb') as fh:
            return {r: e['sha256'] for r, e in parse_manifest(fh.read())['masters'].items()}
    except (OSError, ValueError, TypeError, UnicodeDecodeError):
        return None
