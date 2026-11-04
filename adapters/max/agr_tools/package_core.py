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
UCX_MESH = re.compile(r'^UCX_(?P<name>SM_' + ADDRESS + r')_(?P<n>[0-9]{3})$')
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
