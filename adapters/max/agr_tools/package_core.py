"""new-case: AGR Tools 0.8 (#908) package logic, stdlib only; owned by branch D (improve/issue-908-package).

Pure logic for `qa.package`, `export.zip`, `export.ground_fbx` and `export.geojson_write`; no pymxs. Reports,
preview hashes and never-overwrite paths come from edit_core.py (passed in as `edit`).

* qa.package — runs the pilot validator `tools/qa/validate_package.py --json` (with `--scene` by default) in the
  project interpreter and turns its stage table into an edit report (read-only: preview only).
* export.zip — member lists from the exact name grammar per address (lab L04: GeoAGR Archivate All picked members
  by substring, mixed addresses and lost `_Light`, GeoAGR.ms:66246-66307); in-process ZIP, new file only, binary
  limits (D015), the validator run on every archive written.
* export.ground_fbx — classification by the geometry suffix grammar (docs/domain/geometry.md:39-44): Ground,
  GroundGlass, GroundEl, GroundElGlass, Flora -> `{code4}_{Address}_Ground.fbx`; OKS `SM_{Address}_{NNN}_*` ->
  `{code4}_{Address}_{NN}.fbx`. The file name comes from the address field, never from the first selected object
  (GeoAGR.ms:66617-66622).
No GeoAGR or team-script code is reproduced (#853).
"""
import json
import os
import re
import subprocess
import zipfile

MIB = 1024 * 1024
# D015 binary units; standards/NPM_STANDARD.yaml archive.max_bytes, VPM_STANDARD.yaml archive.oks/ground_max_bytes
LIMITS = {'npm': 1024 * MIB, 'vpm_oks': 500 * MIB, 'vpm_ground': 1024 * MIB}
ADDRESS = r'[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*'
_ADDRESS = re.compile('^' + ADDRESS + '$')
CODE = re.compile(r'^[0-9]{4}$')
NPM_FBX = re.compile(r'^(?P<code>[0-9]{4})_(?P<address>' + ADDRESS + r')_(?P<part>0[1-9]|1[0-9]|20|Ground)\.fbx$')
VPM_FILE = re.compile(r'^SM_(?P<stem>' + ADDRESS + r')(?P<ext>\.fbx|\.geojson)$')
VPM_TEX = re.compile(r'^T_(?P<stem>' + ADDRESS + r')_(?:Diffuse|ERM|Normal)_[0-9]+\.[0-9]{4}\.png$')
OKS_INDEX = re.compile(r'^(?P<address>' + ADDRESS + r')_(?P<index>[0-9]{3})$')
TRAILING_NUMBER = re.compile(r'^(?P<address>' + ADDRESS + r')_(?P<number>[0-9]+)$')
GROUND_SUFFIXES = ('GroundElGlass', 'GroundGlass', 'GroundEl', 'Ground', 'Flora')  # longest first
OKS_MESH = re.compile(r'^SM_(?P<address>' + ADDRESS + r')_(?P<index>00[1-9]|01[0-9]|020)_(?P<suffix>Main|MainGlass)$')
GROUND_MESH = re.compile(r'^SM_(?P<address>' + ADDRESS + r')_(?P<suffix>GroundElGlass|GroundGlass|GroundEl|Ground|Flora)$')
NEAR_ORIGIN_M = 100.0  # NPM sits in MSK coordinates: a pivot this close to 0,0,0 is a placement error (lab L04)
# FBX settings of the NPM export (lab L04: GeoAGR's are right except Triangulate, GeoAGR.ms:66578-66605)
GROUND_FBX_PARAMS = (('Animation', False), ('Cameras', False), ('Lights', False), ('ASCII', False),
                     ('FileVersion', 'FBX201400'), ('EmbedTextures', True), ('Triangulate', True),
                     ('SmoothingGroups', True), ('SmoothMeshExport', False), ('ConvertUnit', 'm'),
                     ('UpAxis', 'Y'), ('ScaleFactor', 1.0), ('Preserveinstances', False), ('GeomAsBone', False))
TOOLS = ('qa.package', 'export.zip', 'export.ground_fbx', 'export.geojson_write')


# ---- validator (qa.package engine) -------------------------------------------------------------------------
def validator_argv(python, root, target, profile=None, scene=True):
    argv = [str(python), os.path.join(str(root), 'tools', 'qa', 'validate_package.py'), str(target), '--json']
    if profile is not None:
        if profile not in ('npm', 'vpm'):
            raise ValueError('unsupported profile: ' + repr(profile))
        argv += ['--profile', profile]
    if scene:
        argv.append('--scene')
    return argv


def subprocess_runner(argv, timeout=3600):
    """Run the validator; (exit code, stdout text). The validator exits 0/1/2; anything else is an error."""
    proc = subprocess.run(argv, capture_output=True, timeout=timeout)
    out = proc.stdout.decode('utf-8', errors='replace')
    if proc.returncode not in (0, 1, 2) or not out.strip():
        detail = proc.stderr.decode('utf-8', errors='replace')[-2000:]
        raise RuntimeError('validator failed (exit {}): {}'.format(proc.returncode, detail.strip() or 'no output'))
    return proc.returncode, out


def stage_table(validator_json):
    """Compact stage table V001..V017 of one validator report: id, check, gate, status, non-pass findings."""
    rep = json.loads(validator_json) if isinstance(validator_json, str) else validator_json
    if not isinstance(rep, dict) or not isinstance(rep.get('stages'), list) or 'exit_code' not in rep:
        raise ValueError('validator report without stages/exit_code')
    stages = []
    for s in rep['stages']:
        bad = ['{}: {}: {}'.format(f['status'], f['name'], f['observed']) for f in s.get('findings', [])
               if f.get('status') != 'pass']
        stages.append({'id': s['id'], 'check': s['check'], 'gate': s['gate'], 'status': s['status'],
                       'non_pass': bad[:8]})
    return {'target': rep.get('target'), 'profile': rep.get('profile'), 'exit_code': int(rep['exit_code']),
            'stages': stages, 'notes': list(rep.get('notes', []))[:20]}


def validate(target, runner, python, root, profile=None, scene=True):
    code, out = runner(validator_argv(python, root, target, profile, scene))
    table = stage_table(out)
    if table['exit_code'] != code:
        raise RuntimeError('validator exit {} != report exit_code {}'.format(code, table['exit_code']))
    return table


def stage_findings(edit, table):
    """Edit-report findings of one validator table: one per failed stage (review/not_run stay in the table)."""
    out = []
    for s in table['stages']:
        if s['status'] == 'fail':
            detail = s['check'] + ': ' + '; '.join(f for f in s['non_pass'] if f.startswith('fail'))
            out.append(edit.finding(s['id'], (), detail[:1000]))
    return out


def worst_exit(tables):
    codes = {t['exit_code'] for t in tables}
    return 1 if 1 in codes else 2 if 2 in codes else 0


def qa_targets(path):
    """A file is checked as is; a folder means every top-level *.zip in it (sorted)."""
    path = os.fspath(path)
    if os.path.isfile(path):
        return [path]
    if not os.path.isdir(path):
        raise ValueError('qa.package: no such file or folder: ' + path)
    zips = sorted(os.path.join(path, n) for n in os.listdir(path)
                  if n.lower().endswith('.zip') and os.path.isfile(os.path.join(path, n)))
    if not zips:
        raise ValueError('qa.package: no ZIP in ' + path)
    return zips


def _file_state(paths):
    out = []
    for p in paths:
        st = os.stat(p)
        out.append([os.path.basename(p), int(st.st_size), int(st.st_mtime_ns)])
    return out


def qa_package(edit, path, runner, python, root, profile=None, scene=True, options=None):
    """Read-only report: one object per checked file (handle = 1-based ordinal), findings = failed stages."""
    targets = qa_targets(path)
    tables, objects = [], []
    for i, t in enumerate(targets, 1):
        table = validate(t, runner, python, root, profile, scene)
        tables.append(table)
        objects.append(edit.entry(i, os.path.basename(t), stage_findings(edit, table)))
    state = {'path': os.path.abspath(os.fspath(path)), 'files': _file_state(targets)}
    extra = {'options': dict(options or {}), 'scene': bool(scene), 'exit_code': worst_exit(tables),
             'reports': tables}
    return edit.report('qa.package', 'preview', objects=objects, done=[os.path.basename(t) for t in targets],
                       state_hash=edit.fingerprint(state), extra=extra)


# ---- export.zip: member lists by exact grammar ---------------------------------------------------------------
def _vpm_set(stem):
    """VPM set stem (after SM_) -> (address, role, index) with role vpm_oks / vpm_ground, or None (not a set)."""
    if stem.endswith('_Light'):
        return None
    if stem.endswith('_Ground'):
        address = stem[:-len('_Ground')]
        return (address, 'vpm_ground', None) if _ADDRESS.match(address) else None
    m = OKS_INDEX.match(stem)
    if m:
        return m.group('address'), 'vpm_oks', m.group('index')
    return stem, 'vpm_oks', None


def classify_folder(names):
    """Exact-grammar classification of a delivery folder listing.

    Returns {'npm': {(code, address): {'Ground': name, '01': name, ...}},
             'vpm': {stem: {'address', 'role', 'index', 'fbx', 'light', 'geojson', 'png': [...]}},
             'other': [names]}. Each name lands in at most one place."""
    npm, vpm, other, loose = {}, {}, [], []
    for n in sorted(names):
        m = NPM_FBX.match(n)
        if m:
            npm.setdefault((m.group('code'), m.group('address')), {})[m.group('part')] = n
            continue
        m = VPM_FILE.match(n)
        if m and m.group('ext') == '.fbx' and not m.group('stem').endswith('_Light'):
            info = _vpm_set(m.group('stem'))
            if info:
                address, role, index = info
                vpm.setdefault(m.group('stem'), {'address': address, 'role': role, 'index': index, 'fbx': n,
                                                 'light': None, 'geojson': None, 'png': []})
                continue
        loose.append(n)
    for n in loose:
        m = VPM_FILE.match(n)
        t = VPM_TEX.match(n)
        if m and m.group('ext') == '.fbx' and m.group('stem')[:-len('_Light')] in vpm:
            vpm[m.group('stem')[:-len('_Light')]]['light'] = n
        elif m and m.group('ext') == '.geojson' and m.group('stem') in vpm:
            vpm[m.group('stem')]['geojson'] = n
        elif t and t.group('stem') in vpm:
            vpm[t.group('stem')]['png'].append(n)
        else:
            other.append(n)
    return {'npm': npm, 'vpm': vpm, 'other': other}


def delivery_address(cls, address=None):
    """The one address of this run: given, else the unique address that has a Ground FBX (NPM or VPM), else the
    unique address of the VPM OKS sets. Several -> ValueError (mixed addresses are refused, never merged)."""
    if address is not None:
        if not isinstance(address, str) or not _ADDRESS.match(address):
            raise ValueError('invalid address: ' + repr(address))
        return address
    grounds = {a for (_, a), parts in cls['npm'].items() if 'Ground' in parts}
    grounds |= {s['address'] for s in cls['vpm'].values() if s['role'] == 'vpm_ground'}
    if len(grounds) > 1:
        raise ValueError('mixed addresses in one folder: {}; pass options.address'.format(sorted(grounds)))
    if grounds:
        return grounds.pop()
    oks = {s['address'] for s in cls['vpm'].values()}
    if len(oks) == 1:
        return oks.pop()
    raise ValueError('no delivery address: {} candidates; pass options.address'.format(sorted(oks) or 'no'))


def _member_rows(folder, names):
    rows = []
    for n in names:
        st = os.stat(os.path.join(folder, n))
        rows.append({'name': n, 'bytes': int(st.st_size), 'mtime_ns': int(st.st_mtime_ns)})
    return rows


def zip_plan(folder, address=None, limits=None):
    """Archives to write for one address, plus skipped items with reasons. No file is touched."""
    folder = os.path.abspath(os.fspath(folder))
    if not os.path.isdir(folder):
        raise ValueError('export.zip: no such folder: ' + folder)
    limits = dict(LIMITS, **(limits or {}))
    names = [n for n in os.listdir(folder) if os.path.isfile(os.path.join(folder, n))]
    cls = classify_folder(names)
    addr = delivery_address(cls, address)
    archives, skipped = [], []

    codes = sorted(c for (c, a) in cls['npm'] if a == addr)
    for (code, a), parts in sorted(cls['npm'].items()):
        if a != addr:
            skipped += [(n, 'address {} is not the delivery address {}'.format(a, addr)) for n in sorted(parts.values())]
    if len(codes) > 1:
        for code in codes:
            skipped += [(n, 'mixed territory codes {} for {}'.format(codes, addr))
                        for n in sorted(cls['npm'][(code, addr)].values())]
    elif codes:
        code = codes[0]
        parts = cls['npm'][(code, addr)]
        oks = sorted(p for p in parts if p != 'Ground')
        problems = []
        if 'Ground' not in parts:
            problems.append('Ground FBX {}_{}_Ground.fbx missing'.format(code, addr))
        if not oks:
            problems.append('no OKS FBX {}_{}_01.fbx'.format(code, addr))
        elif oks != ['{:02d}'.format(i) for i in range(1, len(oks) + 1)]:
            problems.append('OKS parts not 01..{:02d} without gaps: {}'.format(len(oks), oks))
        members = ([parts['Ground']] if 'Ground' in parts else []) + [parts[p] for p in oks]
        archives.append(_archive('{}_{}.zip'.format(code, addr), 'npm', folder, members, limits['npm'], problems))

    for stem, s in sorted(cls['vpm'].items()):
        own = [s['fbx']] + ([s['light']] if s['light'] else []) + ([s['geojson']] if s['geojson'] else []) + s['png']
        if s['address'] != addr:
            m = TRAILING_NUMBER.match(stem)
            if m and m.group('address') == addr:
                why = 'SM_{} is not SM_{}[_NNN]: the OKS index has 3 digits'.format(stem, addr)
            else:
                why = 'address {} is not the delivery address {}'.format(s['address'], addr)
            skipped += [(n, why) for n in own]
            continue
        problems = []
        if not s['geojson']:
            problems.append('GeoJSON SM_{}.geojson missing'.format(stem))
        if len(s['png']) < 3:
            problems.append('{} PNG T_{}_* (Diffuse, ERM, Normal needed)'.format(len(s['png']), stem))
        archives.append(_archive('SM_{}.zip'.format(stem), s['role'], folder, own, limits[s['role']], problems))
    targets = {a['name'] for a in archives}
    skipped += [(n, 'not in the delivery grammar of {}'.format(addr)) for n in cls['other'] if n not in targets]
    for a in archives:
        if os.path.exists(a['target']):
            a['problems'].append('exists; refusing to overwrite (never update an archive)')
    return {'folder': folder, 'address': addr, 'archives': archives,
            'skipped': [{'item': n, 'reason': r} for n, r in sorted(skipped)]}


def _archive(name, role, folder, members, limit, problems):
    rows = _member_rows(folder, members)
    total = sum(r['bytes'] for r in rows)
    return {'name': name, 'role': role, 'target': os.path.join(folder, name), 'members': rows,
            'bytes_in': total, 'limit': int(limit), 'problems': list(problems)}


def size_status(n, limit):
    """`<=` binary limit: the limit itself passes, limit + 1 fails (D015, lab L04)."""
    return 'pass' if int(n) <= int(limit) else 'fail'


def zip_preview(edit, folder, address=None, limits=None, options=None):
    plan = zip_plan(folder, address, limits)
    objects = [edit.entry(i, a['name'], [edit.finding('archive', (), p) for p in a['problems']])
               for i, a in enumerate(plan['archives'], 1)]
    state = {'plan': plan}
    extra = {'options': dict(options or {}), 'folder': plan['folder'], 'address': plan['address'],
             'archives': plan['archives']}
    done = [a['name'] for a in plan['archives'] if not a['problems']]
    skipped = [edit.skipped(a['name'], '; '.join(a['problems'])) for a in plan['archives'] if a['problems']]
    skipped += [edit.skipped(s['item'], s['reason']) for s in plan['skipped']]
    return edit.report('export.zip', 'preview', objects=objects, done=done, skipped_=skipped,
                       state_hash=edit.fingerprint(state), extra=extra)


def _write_zip(folder, archive, edit):
    """New ZIP via an exclusive `.partial` beside the target, then a no-clobber link; no temp file is left."""
    target = edit.new_path(archive['target'])  # refuses an existing archive (never update)
    partial = target + '.partial'
    try:
        with open(partial, 'xb') as fh:
            with zipfile.ZipFile(fh, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as z:
                for m in archive['members']:
                    z.write(os.path.join(folder, m['name']), arcname=m['name'])
        size = os.path.getsize(partial)
        if size_status(size, archive['limit']) != 'pass':
            return None, size
        try:
            os.link(partial, target)  # fails if the target appeared meanwhile: no clobber
        except OSError:
            if os.path.exists(target):
                raise
            os.rename(partial, target)
        return target, size
    finally:
        if os.path.exists(partial):
            os.unlink(partial)


def zip_apply(edit, preview, validate_fn=None, limits=None):
    """Write the archives of the unaltered, still current preview; run the validator on each one written."""
    plan = preview['plan']
    current = zip_plan(plan['folder'], plan['options'].get('address'), limits)
    edit.require_current(preview, {'plan': current})
    objects, done, skipped, reports = [], [], [], []
    for i, a in enumerate(current['archives'], 1):
        if a['problems']:
            skipped.append(edit.skipped(a['name'], '; '.join(a['problems'])))
            objects.append(edit.entry(i, a['name'], [edit.finding('archive', (), p) for p in a['problems']]))
            continue
        target, size = _write_zip(current['folder'], a, edit)
        findings = []
        if target is None:
            findings.append(edit.finding('size', (), '{} B > {} B (binary limit, D015); not written'.format(
                size, a['limit'])))
            skipped.append(edit.skipped(a['name'], 'over the size limit; not written'))
        else:
            done.append(a['name'])
            if validate_fn is not None:
                table = validate_fn(target)
                reports.append(table)
                findings += stage_findings(edit, table)
        objects.append(edit.entry(i, a['name'], findings))
    skipped += [edit.skipped(s['item'], s['reason']) for s in current['skipped']]
    extra = {'folder': current['folder'], 'address': current['address'], 'reports': reports,
             'exit_code': worst_exit(reports) if reports else None}
    return edit.report('export.zip', 'apply', objects=objects, done=done, skipped_=skipped, extra=extra)


# ---- export.ground_fbx: NPM FBX split by the suffix grammar --------------------------------------------------
def classify_mesh(name):
    """('ground', address, suffix) | ('oks', address, NNN) | None. Suffix grammar of docs/domain/geometry.md:39-44;
    Flora belongs to the Ground file (D097), unlike GeoAGR's lowercase 'ground' substring test (GeoAGR.ms:66611)."""
    m = GROUND_MESH.match(name)
    if m:
        return 'ground', m.group('address'), m.group('suffix')
    m = OKS_MESH.match(name)
    if m:
        return 'oks', m.group('address'), m.group('index')
    return None


def ground_plan(nodes, code, address=None, folder=None, exists=os.path.exists):
    """FBX files of one NPM delivery from node facts; no file is touched.

    nodes: [{'handle', 'name', 'geometry': bool, 'material': class name or None, 'pivot_m': distance of the pivot
    to 0,0,0 in metres, 'hidden': bool}]. Returns {'files': [{'name', 'role', 'nodes', 'handles', 'target'}],
    'findings': {handle: [(code, detail)]}, 'skipped': [(name, reason)], 'address', 'code'}.
    Mixed addresses raise (never merged); the file name comes from the address field, not from a selected object."""
    if not isinstance(code, str) or not CODE.match(code):
        raise ValueError('territory code must be 4 digits (options.code or AGR_CODE): ' + repr(code))
    findings, skipped, groups, addresses = {}, [], {'ground': [], 'oks': {}}, set()
    for n in sorted(nodes, key=lambda x: x['name']):
        h, name = n['handle'], n['name']
        if name.startswith('UCX_'):
            skipped.append((name, 'UCX is not exported to NPM'))
            continue
        cls = classify_mesh(name)
        if cls is None:
            skipped.append((name, 'not SM_{Address}_{Ground|GroundGlass|GroundEl|GroundElGlass|Flora} '
                                  'or SM_{Address}_{001..020}_{Main|MainGlass}'))
            continue
        role, addr, key = cls
        if address is not None and addr != address:
            skipped.append((name, 'address {} is not the delivery address {}'.format(addr, address)))
            continue
        addresses.add(addr)
        bad = []
        if not n.get('geometry'):
            bad.append(('not_geometry', 'not a geometry object'))
        if n.get('hidden'):
            bad.append(('hidden', 'hidden: unhide it yourself (the tool never unhides)'))
        if n.get('material') not in (None, 'Standardmaterial', 'StandardMaterial', 'Standard'):
            bad.append(('material', 'material {} is not Standard'.format(n.get('material'))))
        pivot = n.get('pivot_m')
        if not isinstance(pivot, (int, float)) or pivot <= NEAR_ORIGIN_M:
            bad.append(('placement', 'pivot {} m from 0,0,0: NPM needs MSK coordinates (> {} m)'.format(
                pivot, NEAR_ORIGIN_M)))
        if bad:
            findings[h] = bad
        if role == 'ground':
            groups['ground'].append(n)
        else:
            groups['oks'].setdefault(key, []).append(n)
    if len(addresses) > 1:
        raise ValueError('mixed addresses {}: pass options.address'.format(sorted(addresses)))
    if not addresses:
        raise ValueError('no Ground or OKS mesh in the NPM grammar among the nodes')
    addr = addresses.pop()
    files = []
    if groups['ground']:
        files.append(('{}_{}_Ground.fbx'.format(code, addr), 'ground', groups['ground']))
    oks = sorted(groups['oks'])
    if len(oks) > 20:
        raise ValueError('more than 20 OKS ({}): NPM allows parts 01..20'.format(len(oks)))
    for i, index in enumerate(oks, 1):
        files.append(('{}_{}_{:02d}.fbx'.format(code, addr, i), 'oks', groups['oks'][index]))
    out = []
    for name, role, group in files:
        target = os.path.join(folder, name) if folder else name
        out.append({'name': name, 'role': role, 'nodes': sorted(n['name'] for n in group),
                    'handles': sorted(int(n['handle']) for n in group), 'target': target,
                    'exists': bool(folder) and exists(target)})
    return {'files': out, 'findings': findings, 'skipped': skipped, 'address': addr, 'code': code}


def ground_report(edit, mode, plan, nodes, state=None, done=(), extra_findings=None, extra=None):
    """Edit report of the NPM FBX split: one object per node (guards), skipped nodes/files, done files."""
    objects = []
    for n in sorted(nodes, key=lambda x: int(x['handle'])):
        items = [edit.finding(c, (), d) for c, d in plan['findings'].get(n['handle'], [])]
        items += [edit.finding(c, (), d) for c, d in (extra_findings or {}).get(n['name'], [])]
        objects.append(edit.entry(n['handle'], n['name'], items))
    skipped = [edit.skipped(n, r) for n, r in plan['skipped']]
    skipped += [edit.skipped(f['name'], 'exists; refusing to overwrite') for f in plan['files'] if f['exists']]
    ambiguous = []
    if mode == 'preview':
        done = [f['name'] for f in plan['files'] if not f['exists']]
    info = {'address': plan['address'], 'code': plan['code'],
            'files': [{k: f[k] for k in ('name', 'role', 'nodes', 'target')} for f in plan['files']]}
    info.update(extra or {})
    return edit.report('export.ground_fbx', mode, objects=objects, done=list(done), skipped_=skipped,
                       ambiguous=ambiguous, state_hash=None if mode == 'apply' else edit.fingerprint(state),
                       extra=info)

# ---- export.geojson_write: the VPM GeoJSON passport -----------------------------------------------------------
# GeoAGR Create/Save/Load (GeoAGR.ms:64642-64644) are disabled buttons without any handler: nothing to port.
PROPERTY_KEYS = ('address', 'okrug', 'rajon', 'name', 'developer', 'designer', 'cadNum', 'FNO_code', 'FNO_name',
                 'ZU_area', 'h_relief', 'h_otn', 'h_abs', 's_obsh', 's_naz', 's_podz', 'spp_gns', 'act_AGR',
                 'imageBase64', 'other')  # standards/VPM_STANDARD.yaml geojson.properties_keys
OKS_MAY_BE_EMPTY = ('other', 'act_AGR')
GROUND_NULLABLE = ('FNO_name', 'FNO_code', 'h_otn', 'h_abs', 's_obsh', 's_naz', 's_podz', 'spp_gns', 'other')
VPM_MESH = re.compile(r'^SM_(?P<address>' + ADDRESS + r')_(?P<suffix>Main|MainGlass|GroundElGlass|GroundGlass|'
                      r'GroundEl|Ground|Flora)$')
GLASS_SUFFIXES = ('MainGlass', 'GroundGlass', 'GroundElGlass')
COORD_DECIMALS = 3


def jpeg_size(data):
    """(width, height) of a baseline/progressive JPEG from its SOF marker, stdlib only; ValueError otherwise."""
    if not isinstance(data, (bytes, bytearray)) or data[:2] != b'\xff\xd8':
        raise ValueError('not a JPEG (no SOI marker)')
    i = 2
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            raise ValueError('broken JPEG marker at byte {}'.format(i))
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        length = int.from_bytes(data[i + 2:i + 4], 'big')
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            if i + 9 > len(data):
                break
            return int.from_bytes(data[i + 7:i + 9], 'big'), int.from_bytes(data[i + 5:i + 7], 'big')
        i += 2 + length
    raise ValueError('JPEG without a frame header')


def preview_image(data):
    """(base64 text, findings) of the 256x256 JPG preview (reg p.54); the tool never resizes (GeoAGR shelled out to
    ImageMagick `magick`, GeoAGR.ms:64859)."""
    import base64
    try:
        size = jpeg_size(data)
    except ValueError as exc:
        return None, [('image', 'preview: {} (a 256x256 JPG is needed)'.format(exc))]
    if size != (256, 256):
        return None, [('image', 'preview is {}x{}; a 256x256 JPG is needed'.format(*size))]
    return base64.b64encode(bytes(data)).decode('ascii'), []


def geojson_stem(names):
    """(stem, ground, address, glass mesh names) from the VPM mesh names: OKS `SM_{A}_Main*` -> SM_{A},
    Ground family -> SM_{A}_Ground. One address and one role per GeoJSON; anything else raises."""
    roles, addresses, glass, other = set(), set(), [], []
    for n in names:
        m = VPM_MESH.match(n)
        if not m:
            if not n.startswith('UCX_'):
                other.append(n)
            continue
        addresses.add(m.group('address'))
        roles.add('oks' if m.group('suffix').startswith('Main') else 'ground')
        if m.group('suffix') in GLASS_SUFFIXES:
            glass.append(n)
    if len(addresses) != 1:
        raise ValueError('one address per GeoJSON, got {}'.format(sorted(addresses) or 'none'))
    if len(roles) != 1:
        raise ValueError('OKS and Ground meshes together: one GeoJSON per OKS / per Ground (select one set)')
    address, ground = addresses.pop(), roles.pop() == 'ground'
    return ('SM_{}_Ground'.format(address) if ground else 'SM_{}'.format(address)), ground, address, sorted(glass)


def pivot_coordinates(pivot_report):
    """MSK-77 insertion point [x, y] (3 decimals) from the export.pivot_place preview (branch A): its common pivot
    `plan.pivot_value` = [centre X, centre Y, floor]. A stub/failed preview is an error, never a guessed point."""
    import math
    if not isinstance(pivot_report, dict) or pivot_report.get('status') == 'not_implemented':
        raise ValueError('export.pivot_place is not implemented yet (#908 branch A): the GeoJSON point needs its pivot')
    plan = pivot_report.get('plan') or {}
    value = plan.get('pivot_value')
    if pivot_report.get('status') != 'pass' or not isinstance(value, list) or len(value) != 3:
        raise ValueError('export.pivot_place preview without a pivot: {}'.format(pivot_report.get('status')))
    x, y = float(value[0]), float(value[1])
    if not (math.isfinite(x) and math.isfinite(y)):
        raise ValueError('non-finite pivot')
    return [round(x, COORD_DECIMALS), round(y, COORD_DECIMALS)], plan.get('floor')


def glasses_entry(materials):
    """`Glasses`: [] without glass, else ONE object keyed by glass material name (conflict #13). Values come from the
    glass material (diffuse colour, opacity, IOR, glossiness); identical glass is one material."""
    if not materials:
        return []
    out = {}
    for m in sorted(materials, key=lambda x: x['name']):
        rgb = [int(round(max(0.0, min(255.0, float(c))))) for c in m['diffuse']]
        out[m['name']] = {'color_RGB': {'Red': rgb[0], 'Green': rgb[1], 'Blue': rgb[2]},
                          'transparency': round(max(0.0, min(100.0, float(m['opacity']))) / 100.0, 3),
                          'refraction': round(max(1.0, min(3.0, float(m.get('ior') or 1.5))), 3),
                          'roughness': round(1.0 - max(0.0, min(100.0, float(m.get('glossiness', 0.0)))) / 100.0, 3),
                          'metallicity': 0.0}
    return [out]


def property_findings(properties, ground):
    """Missing/empty mandatory values are findings (never invented); unknown keys are an error."""
    if not isinstance(properties, dict):
        raise ValueError('options.properties must be an object of the App.3 keys')
    unknown = sorted(set(properties) - set(PROPERTY_KEYS))
    if unknown or 'imageBase64' in properties:
        raise ValueError('unknown or reserved property keys: {}'.format(unknown or ['imageBase64']))
    may_be_empty = GROUND_NULLABLE if ground else OKS_MAY_BE_EMPTY
    out = []
    for key in PROPERTY_KEYS:
        if key == 'imageBase64':
            continue
        value = properties.get(key)
        if value in (None, '') and key not in may_be_empty:
            out.append(('property', '{} is empty: a mandatory value (ask the customer, never invent it)'.format(key)))
        elif isinstance(value, float) and value != value:
            out.append(('property', key + ' is NaN'))
    return out


def geojson_document(properties, image_b64, coordinates, glasses, ground):
    """The UTF-8 bytes of the passport: FeatureCollection / ObjectFeature / Point, exact App.3 key order."""
    may_be_empty = GROUND_NULLABLE if ground else OKS_MAY_BE_EMPTY
    props = {}
    for key in PROPERTY_KEYS:
        if key == 'imageBase64':
            props[key] = image_b64 or ''
        else:
            value = properties.get(key)
            props[key] = '' if value is None and key in may_be_empty else value
    doc = {'type': 'FeatureCollection', 'features': [{'type': 'ObjectFeature', 'properties': props,
           'geometry': {'type': 'Point', 'coordinates': list(coordinates)}, 'Glasses': glasses}]}
    return json.dumps(doc, ensure_ascii=False, indent=1, allow_nan=False).encode('utf-8')


def geojson_plan(names, properties, image_bytes, pivot_report, glass_materials, folder, exists=os.path.exists):
    stem, ground, address, glass_meshes = geojson_stem(names)
    findings = property_findings(properties, ground)
    if image_bytes is None:
        image_b64, more = None, [('image', 'no preview: options.image must name a 256x256 JPG')]
    else:
        image_b64, more = preview_image(image_bytes)
    findings += more
    coords, floor = pivot_coordinates(pivot_report)
    if glass_meshes and not glass_materials:
        findings.append(('glass', 'glass meshes {} without a material'.format(glass_meshes)))
    glasses = glasses_entry(glass_materials)
    target = os.path.join(folder, stem + '.geojson')
    data = geojson_document(properties, image_b64, coords, glasses, ground)
    return {'stem': stem, 'ground': ground, 'address': address, 'target': target, 'exists': exists(target),
            'coordinates': coords, 'floor': floor, 'glass_meshes': glass_meshes,
            'glass_materials': sorted(m['name'] for m in glass_materials), 'findings': findings, 'data': data}