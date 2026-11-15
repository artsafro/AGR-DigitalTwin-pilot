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

FBX export owner (#1423 point 2): the readback of the exported files that go into the package is
`readback_summary` over tools/blender/fbx_readback.py (dimensions, part positions, materials, UV, UCX-to-visual name
binding); its report is the required check `fbx_readback`.
"""
import datetime
import hashlib
import json
import os
import re
import zipfile

SCHEMA = 'agr.build_manifest/1'
DERIVATION_SCHEMA = 'agr.derivation/1'
READBACK_SCHEMA = 'agr.fbx_readback/1'
SUFFIX = '.build.json'
READBACK_SUFFIX = '.readback.json'
REQUIRED_CHECKS = ('fbx_readback',)
EXPORT_OWNER = 'tools/derive/build_manifest.py build (export owner readback, #1423)'
KINDS = ('npm_fbx', 'vpm_fbx', 'light_fbx', 'ucx_fbx', 'texture', 'geojson')
SHA = re.compile(r'^[0-9a-f]{64}$')
COMMIT = re.compile(r'^(?:[0-9a-f]{7,40}|unknown)$')
TOP_KEYS = {'schema', 'build_id', 'created_utc', 'package', 'master', 'transform', 'artifacts', 'checks'}
MASTER_KEYS = {'name', 'sha256', 'builder_commit'}
TRANSFORM_KEYS = {'name', 'file', 'sha256'}
ARTIFACT_KEYS = {'name', 'kind', 'sha256', 'derived_sha256', 'master_sha256', 'parts'}
CHECK_KEYS = {'id', 'owner', 'required', 'status', 'finished', 'report', 'report_sha256', 'subjects'}
DERIVATION_KEYS = {'schema', 'master_name', 'master_sha256', 'builder_commit', 'artifacts'}
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
def derivation_record(artifacts, master, builder_commit):
    """Record of which master revision the exported `artifacts` (paths) were derived from, hashed NOW (export time).

    A later master edit leaves this record behind: the build manifest then names two revisions and is refused."""
    if not artifacts:
        raise ValueError('derivation: no artifact')
    if not COMMIT.match(str(builder_commit)):
        raise ValueError('derivation: builder_commit must be a git sha or unknown')
    master = os.fspath(master)
    if not os.path.isfile(master):
        raise ValueError('derivation: no master file ' + master)
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
    return {'schema': DERIVATION_SCHEMA, 'master_name': os.path.basename(master), 'master_sha256': sha256_file(master),
            'builder_commit': str(builder_commit), 'artifacts': rec}


def check_derivation(rec):
    _keys(rec, DERIVATION_KEYS, 'derivation')
    if rec['schema'] != DERIVATION_SCHEMA:
        raise ValueError('derivation schema {!r} != {!r}'.format(rec['schema'], DERIVATION_SCHEMA))
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


def readback_summary(name, data_sha256, rb):
    """Export owner readback of one exported FBX: dimensions, part positions, materials, UV, UCX binding + status.

    `rb` is the tools/blender/fbx_readback.py report of exactly the zipped bytes (`data_sha256`)."""
    problems = []
    meshes = []
    if not isinstance(rb, dict) or rb.get('readback_ok') is not True:
        problems.append('readback not ok')
    for m in (rb or {}).get('meshes', []) if isinstance(rb, dict) else []:
        lo, hi = m.get('bounds_m', [[None] * 3, [None] * 3])
        dims = [None if a is None or b is None else round(b - a, 6) for a, b in zip(lo, hi)]
        row = {'name': m.get('name'), 'dimensions_m': dims, 'location': [round(float(v), 6) for v in m.get('location', [])],
               'materials': list(m.get('materials', [])), 'uv_channels': m.get('uv_channels'),
               'triangles': m.get('triangles')}
        meshes.append(row)
        if not UCX.match(str(row['name'])):
            if not row['materials'] or None in row['materials']:
                problems.append('{}: empty material slot'.format(row['name']))
            if not row['uv_channels']:
                problems.append('{}: no UV channel'.format(row['name']))
        if any(d is None or d != d for d in dims):
            problems.append('{}: dimensions not read'.format(row['name']))
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
def make_manifest(package_zip, master, builder_commit, derivations, transform, readback=None, readback_file=None,
                  build_id=None, now=None):
    """Manifest dict of one package. Every member needs a derivation record (an unrecorded member is an error naming
    it); the master revision named by each record is kept as is, so a stale artifact shows up as a mismatch."""
    package_zip = os.fspath(package_zip)
    master = os.fspath(master)
    if not COMMIT.match(str(builder_commit)):
        raise ValueError('build manifest: builder_commit must be a git sha or unknown')
    members = zip_members(package_zip)
    by_name = {}
    for rec in derivations:
        check_derivation(rec)
        for name, a in rec['artifacts'].items():
            if name in by_name and by_name[name][0] != rec['master_sha256']:
                raise ValueError('build manifest: two derivation records for {} name different masters'.format(name))
            by_name[name] = (rec['master_sha256'], a['sha256'])
    unrecorded = sorted(set(members) - set(by_name))
    if unrecorded:
        raise ValueError('build manifest: no derivation record for member(s) {}'.format(unrecorded))
    parts = {}
    if readback is not None:
        parts = {f['name']: sorted(m['name'] for m in f['meshes']) for f in readback['files']}
    artifacts = [{'name': n, 'kind': kind_of(n), 'sha256': members[n], 'derived_sha256': by_name[n][1],
                  'master_sha256': by_name[n][0], 'parts': parts.get(n, [])} for n in sorted(members)]
    checks = []
    if readback is not None:
        checks.append({'id': 'fbx_readback', 'owner': readback['owner'], 'required': True,
                       'status': readback['status'], 'finished': bool(readback['finished']),
                       'report': os.path.basename(readback_file) if readback_file else None,
                       'report_sha256': sha256_file(readback_file) if readback_file else None,
                       'subjects': {f['name']: f['sha256'] for f in readback['files']}})
    master_sha = sha256_file(master)
    now = now or datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    stem = os.path.basename(package_zip)[:-4]
    return {'schema': SCHEMA,
            'build_id': build_id or '{}-{}-{}'.format(stem, now, master_sha[:8]),
            'created_utc': now,
            'package': {'name': os.path.basename(package_zip), 'sha256': sha256_file(package_zip)},
            'master': {'name': os.path.basename(master), 'sha256': master_sha, 'builder_commit': str(builder_commit)},
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
    m = strict_json(data)
    _keys(m, TOP_KEYS, 'manifest')
    if m['schema'] != SCHEMA:
        raise ValueError('manifest schema {!r} != {!r}'.format(m['schema'], SCHEMA))
    if not isinstance(m['build_id'], str) or not m['build_id']:
        raise ValueError('manifest build_id must be a non-empty string')
    _keys(m['package'], {'name', 'sha256'}, 'manifest package')
    _sha(m['package']['sha256'], 'manifest package sha256')
    _keys(m['master'], MASTER_KEYS, 'manifest master')
    _sha(m['master']['sha256'], 'manifest master sha256')
    if not COMMIT.match(str(m['master']['builder_commit'])):
        raise ValueError('manifest master builder_commit must be a git sha or unknown')
    _keys(m['transform'], TRANSFORM_KEYS, 'manifest transform')
    if not isinstance(m['transform']['name'], str) or not m['transform']['name'].strip():
        raise ValueError('manifest transform name required')
    if (m['transform']['file'] is None) != (m['transform']['sha256'] is None):
        raise ValueError('manifest transform file and sha256 go together')
    if m['transform']['sha256'] is not None:
        _sha(m['transform']['sha256'], 'manifest transform sha256')
    if not isinstance(m['artifacts'], list) or not m['artifacts']:
        raise ValueError('manifest artifacts must be a non-empty list')
    seen = set()
    for a in m['artifacts']:
        _keys(a, ARTIFACT_KEYS, 'manifest artifact')
        if a['name'] in seen:
            raise ValueError('manifest artifact listed twice: ' + str(a['name']))
        seen.add(a['name'])
        for k in ('sha256', 'derived_sha256', 'master_sha256'):
            _sha(a[k], 'manifest artifact {} {}'.format(a['name'], k))
        if a['kind'] not in KINDS:
            raise ValueError('manifest artifact {} kind {!r} unsupported'.format(a['name'], a['kind']))
        if not isinstance(a['parts'], list) or not all(isinstance(p, str) for p in a['parts']):
            raise ValueError('manifest artifact {} parts must be a list of names'.format(a['name']))
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
    master = m['master']['sha256']
    revisions = {}
    for n, a in sorted(arts.items()):
        revisions.setdefault(a['master_sha256'], []).append(n)
    stale = {r: ns for r, ns in revisions.items() if r != master}
    if stale:
        detail = '; '.join('{} derived from master {} (build master {})'.format(ns, r[:12], master[:12])
                           for r, ns in sorted(stale.items()))
        out.append(('fail', 'manifest_master_mismatch', 'artifacts name different master revisions: ' + detail))
    if master_sha256 is None:
        # no master given -> the stale check did not run; never pass without it (#1423 r1 P1)
        out.append(('not_run', 'manifest_master_unchecked', 'manifest_master_unchecked: master not given, the build '
                    'master {} was not compared with the current master (agr validate --master)'.format(master[:12])))
    elif master_sha256 != master:
        out.append(('fail', 'manifest_master_stale', 'master now {} != build master {}: rebuild every artifact'.format(
            master_sha256[:12], master[:12])))
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
    for cid, c in sorted(checks.items()):
        if cid not in REQUIRED_CHECKS and c['required'] is True and (c['status'] != 'pass' or c['finished'] is not True):
            out.append(('fail', 'manifest_check_not_ready', 'required check {}: status {!r}, finished {!r}'.format(
                cid, c['status'], c['finished'])))
    if not out:
        out.append(('pass', 'manifest_ok', 'build {}: {} artifacts from master {} (builder {}), transform {}'.format(
            m['build_id'], len(arts), master[:12], m['master']['builder_commit'], m['transform']['name'])))
    return out


def manifest_master(path):
    """Master sha256 named by a manifest file, or None when it is unreadable/absent (cross-package check)."""
    try:
        with open(path, 'rb') as fh:
            return parse_manifest(fh.read())['master']['sha256']
    except (OSError, ValueError, TypeError, UnicodeDecodeError):
        return None
