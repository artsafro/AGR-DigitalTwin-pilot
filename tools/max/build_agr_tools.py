"""new-case: deterministic, exclusively published AGR Tools MZP builder.

The dependency-free hygiene slice is generated from our existing checker by AST;
no team source, third-party package or absolute workstation path is distributed.
"""
import argparse
import ast
import hashlib
import io
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'adapters/max/agr_tools'
HYGIENE = ROOT / 'src/twinqa/export_hygiene.py'
NUDGE = ROOT / 'src/dt_ai/geometry/uv_nudge.py'
TILES = ROOT / 'src/dt_ai/geometry/uv.py'
UCX_AUDIT = ROOT / 'src/twinqa/geometry/ucx_audit.py'
HYGIENE_NAMES = {'ORIGIN', 'UV_NAME', 'CA_OWNERS', 'OBJECT_KEYS', 'MAX_MAP_CHANNEL',
                 '_MAP_LINE', 'InputError', 'parse_udp', '_validate',
                 '_channel1_problem', '_extra_channels', 'repair_plan'}
FILES = ('mzp.run', 'install.ms', 'startup.ms', 'agr_tools.mcr', 'menu.ms', 'runtime.py', 'bootstrap.py',
         'README.md', 'CHANGELOG.md', 'atlas_core.py', 'ucx_core.py', 'texel_core.py', 'export_core.py', 'export_meta.py',
         'master_topology_core.py',
         'checks_core.py', 'checks_max.py', 'ui_model.py', 'ui_qt.py', 'ui_panel.py', 'ui_max.py',
         'suite_core.py', 'suite_max.py', 'roadmap.py',
         # 0.8 (#908): edit contract + stub modules of branches A-D (this list does not change in A-D)
         'edit_core.py', 'edit_max.py', 'geom_core.py', 'geom_max.py', 'tex_core.py', 'tex_max.py',
         'names_core.py', 'names_max.py', 'udim_core.py', 'udim_max.py', 'package_core.py', 'package_max.py',
         'build_manifest.py',  # #1423 delivery set consistency (loaded by package_core)
         # 0.9 (#979): stub modules of branches A-D (this list does not change in A-E3; data/ is collected below)
         'place_core.py', 'place_max.py', 'texqa_core.py', 'texqa_max.py', 'finish_core.py', 'finish_max.py',
         'uvtile_core.py', 'uvtile_max.py', 'flora_atlas_max.py', 'qa9_core.py', 'qa9_max.py', 'facade_core.py',
         'facade_max.py', 'batch_core.py', 'batch_max.py', 'mapsuse_core.py', 'mapsuse_max.py', 'light_core.py',
         'light_max.py',
         'session_core.py',  # shared in_session / same (one copy instead of one per module)
         # 1.0 (#1024): contract, journal, host adapter, stub modules of branches F-U (this list does not
         # change in F-U; SPLIT.md «Ветка 0» p. 5)
         'contract_core.py', 'journal_core.py', 'host_max.py', 'openings_core.py', 'uvlayout_core.py',
         'vpmmaps_core.py', 'passport_core.py', 'passport_max.py', 'intake_core.py', 'intake_max.py',
         'scene10_core.py', 'scene10_max.py', 'body_core.py', 'body_max.py', 'model10_core.py', 'model10_max.py',
         'gridclean_core.py', 'gridclean_max.py', 'glass_core.py', 'glass_max.py', 'windowgen_core.py',
         'windowgen_max.py', 'winplace_core.py', 'winplace_max.py', 'capsule_core.py', 'capsule_max.py',
         'roof_core.py', 'roof_max.py', 'matlib_core.py', 'matlib_max.py', 'tiles_core.py', 'tiles_max.py',
         'plugcolour_core.py', 'plugcolour_max.py', 'vpm_core.py', 'vpm_max.py', 'udim10_core.py', 'udim10_max.py',
         'dilate_core.py', 'dilate_max.py', 'udimplug_core.py', 'udimplug_max.py', 'npm_core.py', 'npm_max.py',
         'facadeatlas_core.py', 'facadeatlas_max.py', 'npm2vpm_core.py', 'npm2vpm_max.py', 'udimview_core.py',
         'udimview_max.py', 'deliver_core.py', 'deliver_max.py', 'ucx10_core.py', 'ucx10_max.py',
         'ucxstairs_core.py', 'ucxstairs_max.py', 'omk_core.py', 'omk_max.py', 'placegeo_core.py', 'placegeo_max.py',
         'agentbridge_core.py', 'agentbridge_max.py',
         # 1.1: Max <-> Blender handoff (branch BH) and the parameter form of the stage buttons
         'handoff_core.py', 'handoff_max.py', 'params_core.py',
         # #1337: the one shared UDIM tile function (loaded by uvlayout_core, twinqa, Blender job scripts)
         'udimtile_core.py',
         # #1044: standalone assets browser and all its dynamic sibling dependencies.
         'assets_core.py', 'assets_max.py', 'assets_ui.py', 'assets_library.py',
         'assets_textures.py', 'assets_launch.ms')
# 0.9 (#979): every file below adapters/max/agr_tools/data/ ships as agr_tools/data/<rel> (owner files of branch C:
# procedural_classes.json, streets/). At most one sub-folder level: install.ms copies data/ and data/<dir>/.
DATA_DIR = 'data'
SUITE_JSON = ROOT / 'docs/plans/agr-tools-suite.json'  # «Путь» source of truth, shipped as agr-tools-suite.json
BUNDLE = 'AGR-Tools.bundle'
ICONS = ROOT / 'tools/max/agr_icons.py'


def _load(path, name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _model():
    return _load(PACKAGE / 'ui_model.py', 'agr_build_ui_model')


def data_files(package=None):
    """Sorted 'data/<rel>' of every file below <package>/data (at most data/<dir>/<file>; deeper is an error)."""
    root = Path(package or PACKAGE) / DATA_DIR
    if not root.is_dir():
        raise ValueError('package data folder missing: ' + str(root))
    out = []
    for p in sorted(root.rglob('*')):
        if p.is_dir():
            continue
        rel = p.relative_to(root.parent).as_posix()
        if rel.count('/') > 2:
            raise ValueError('data file nested deeper than one sub-folder: ' + rel)
        if p.name.startswith('.') or p.suffix in ('.pyc', '.tmp'):
            raise ValueError('stray file in package data: ' + rel)
        out.append(rel)
    return out


def icon_files():
    """Expected files below icons/: {Dark,Light}/AgrIcons/agr_<name>.svg and _24/_30/_36/_48.png."""
    icons = _load(ICONS, 'agr_build_icons')
    out = []
    for theme in icons.THEMES:
        for n in icons.names():
            out.append('{}/AgrIcons/agr_{}.svg'.format(theme, n))
            out += ['{}/AgrIcons/agr_{}_{}.png'.format(theme, n, s) for s in icons.SIZES]
    return out


def hygiene_slice(source=None):
    if source is None:
        source = HYGIENE.read_text(encoding='utf-8')
    nodes = []
    found = set()
    for node in ast.parse(source).body:
        name = getattr(node, 'name', None)
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
        if name in HYGIENE_NAMES:
            nodes.append(node)
            found.add(name)
    if found != HYGIENE_NAMES:
        raise ValueError(f'hygiene source changed: missing {HYGIENE_NAMES - found}')
    header = ('"""Generated from our export_hygiene.py; new-case: stdlib Max hygiene slice.\n'
              f'Source sha256: {hashlib.sha256(source.encode()).hexdigest()}\n"""\n'
              'import copy\nimport re\n')
    return (header + ast.unparse(ast.Module(body=nodes, type_ignores=[])) + '\n').encode('utf-8')


def _function(source, name):
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise ValueError('missing function ' + name)


OWNER_NAMES = ('FIRST_UDIM', 'U_TILES', 'UdimDomainError', 'tile_origin')


class _OwnerCalls(ast.NodeTransformer):
    """`_udimtile.tile_origin` -> `_udimtile_tile_origin` (the inlined owner function)."""

    def visit_Attribute(self, node):
        self.generic_visit(node)
        if isinstance(node.value, ast.Name) and node.value.id == '_udimtile':
            return ast.copy_location(ast.Name(id='_udimtile_' + node.attr, ctx=node.ctx), node)
        return node


def _tile_nodes(tile_source, owner_source):
    """dt_ai tile_origin for the stdlib slice: the owner's tile_origin (#1337) inlined as `_udimtile_tile_origin`
    plus dt_ai's regulated 1001..1100 wrapper, bound to `tile_origin` (#1376: uv.py delegates to the owner)."""
    found = {}
    for node in ast.parse(owner_source).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in OWNER_NAMES:
            found[node.name] = node
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and getattr(node.targets[0], 'id', None) in OWNER_NAMES:
            found[getattr(node.targets[0], 'id')] = node
    if set(found) != set(OWNER_NAMES):
        raise ValueError(f'udimtile_core source changed: missing {sorted(set(OWNER_NAMES) - set(found))}')
    found['tile_origin'].name = '_udimtile_tile_origin'
    wrapper = _OwnerCalls().visit(_function(tile_source, '_regulated_tile_origin'))
    if any(isinstance(n, ast.Name) and n.id == '_udimtile' for n in ast.walk(wrapper)):
        raise ValueError('uv.py _regulated_tile_origin uses _udimtile beyond attribute calls')
    alias = [n for n in ast.parse(tile_source).body if isinstance(n, ast.Assign) and len(n.targets) == 1
             and getattr(n.targets[0], 'id', None) == 'tile_origin'
             and getattr(n.value, 'id', None) == '_regulated_tile_origin']
    if len(alias) != 1:
        raise ValueError('missing function tile_origin (uv.py: tile_origin = _regulated_tile_origin)')
    return [found[name] for name in OWNER_NAMES] + [wrapper, alias[0]]


def nudge_slice(nudge_source=None, tile_source=None, owner_source=None):
    """Stdlib slice of our uv_nudge.py plus tile_origin (via the inlined udimtile_core owner, #1376).
    Team-script names are not shipped."""
    if nudge_source is None:
        nudge_source = NUDGE.read_text(encoding='utf-8')
    if tile_source is None:
        tile_source = TILES.read_text(encoding='utf-8')
    if owner_source is None:
        owner_source = (PACKAGE / 'udimtile_core.py').read_text(encoding='utf-8')
    nudge_source = nudge_source.replace('\r\n', '\n')
    tile_source = tile_source.replace('\r\n', '\n')
    owner_source = owner_source.replace('\r\n', '\n')
    body = []
    for node in ast.parse(nudge_source).body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Expr) and isinstance(getattr(node, 'value', None), ast.Constant):
            continue  # module docstring cites team-script names; the logic below is ours
        body.append(node)
    if not any(isinstance(node, ast.FunctionDef) and node.name == 'nudge_repeating_islands' for node in body):
        raise ValueError('uv_nudge source changed: nudge_repeating_islands missing')
    module = ast.Module(body=[*_tile_nodes(tile_source, owner_source), *body], type_ignores=[])
    ast.fix_missing_locations(module)
    header = ('"""Generated from our uv_nudge.py; new-case: stdlib integer-tile UV nudge slice.\n'
              f'Source sha256: {hashlib.sha256(nudge_source.encode()).hexdigest()}\n"""\n'
              'from __future__ import annotations\nimport math\nimport numbers\n'
              'from dataclasses import dataclass, field\n')
    return (header + ast.unparse(module) + '\n').encode('utf-8')


def audit_slice(source=None):
    """Stdlib copy of our ucx_audit.py. The opening docstring is replaced; the logic is not."""
    if source is None:
        source = UCX_AUDIT.read_text(encoding='utf-8')
    source = source.replace('\r\n', '\n')
    if not source.startswith('"""'):
        raise ValueError('ucx audit source changed: missing docstring')
    end = source.find('\n"""', 3)
    if end < 0:
        raise ValueError('ucx audit source changed: missing docstring')
    body = source[end + 4:].lstrip('\n')
    if not body.startswith('from __future__ import annotations'):
        raise ValueError('ucx audit source changed: future import moved')
    if 'def collision_findings' not in body or 'def name_report' not in body:
        raise ValueError('ucx audit source changed: collision_findings missing')
    header = ('"""Generated from twinqa.geometry.ucx_audit; new-case: stdlib UCX audit slice.\n'
              f'Source sha256: {hashlib.sha256(source.encode()).hexdigest()}\n"""\n')
    return (header + body).encode('utf-8')


def _collect():
    """{archive name below agr_tools/: bytes} plus {input path: bytes} for the change check."""
    entries, inputs = {}, {}
    for name in FILES:
        p = PACKAGE / name
        inputs[p] = p.read_bytes()
        entries[name] = inputs[p].replace(b'\r\n', b'\n')
    for rel in data_files():
        p = PACKAGE / rel
        inputs[p] = p.read_bytes()
        entries[rel] = inputs[p].replace(b'\r\n', b'\n') if p.suffix in ('.json', '.md', '.txt', '.csv') else inputs[p]
    inputs[HYGIENE] = HYGIENE.read_bytes()
    inputs[NUDGE] = NUDGE.read_bytes()
    inputs[TILES] = TILES.read_bytes()
    inputs[UCX_AUDIT] = UCX_AUDIT.read_bytes()
    inputs[SUITE_JSON] = SUITE_JSON.read_bytes()
    entries['agr-tools-suite.json'] = inputs[SUITE_JSON].replace(b'\r\n', b'\n')
    entries['hygiene_core.py'] = hygiene_slice(inputs[HYGIENE].decode('utf-8').replace('\r\n', '\n'))
    entries['uv_nudge_core.py'] = nudge_slice(
        inputs[NUDGE].decode('utf-8').replace('\r\n', '\n'),
        inputs[TILES].decode('utf-8').replace('\r\n', '\n'),
        inputs[PACKAGE / 'udimtile_core.py'].decode('utf-8').replace('\r\n', '\n'))
    entries['ucx_audit_core.py'] = audit_slice(inputs[UCX_AUDIT].decode('utf-8').replace('\r\n', '\n'))
    expected = icon_files()
    for rel, data in icon_entries().items():
        entries['icons/' + rel] = data
    if set('icons/' + r for r in expected) - set(entries):
        raise ValueError('icon set incomplete')
    return entries, inputs


def icon_entries(png_dir=None):
    """{Theme/AgrIcons/file: bytes}. SVG from agr_icons (stdlib). PNG from png_dir / AGR_ICON_PNG_DIR
    (output of `agr_icons.py <dir>`), else rendered in memory with PySide6 (deterministic).
    PNGs are never committed: *.png is LFS-tracked and LFS is not used (COORDINATION rule 57)."""
    import os
    icons = _load(ICONS, 'agr_build_icons')
    png_dir = png_dir or os.environ.get('AGR_ICON_PNG_DIR')
    out = {}
    app = None
    for rel in icon_files():
        theme, _, fname = rel.split('/')
        stem = fname[4:].rsplit('.', 1)[0]
        if rel.endswith('.svg'):
            out[rel] = icons.svg(stem, icons.THEMES[theme]).encode('utf-8')
            continue
        if png_dir:
            p = Path(png_dir) / rel
            if not p.is_file():
                raise ValueError('icon set missing ' + rel)
            data = p.read_bytes()
        else:
            if app is None:
                try:
                    from PySide6 import QtGui
                except ImportError as exc:
                    raise ValueError('PNG icons need PySide6 or AGR_ICON_PNG_DIR') from exc
                app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])
            name, size = stem.rsplit('_', 1)
            data = icons.png_bytes(icons.svg(name, icons.THEMES[theme]), int(size))
        if not data.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('not a PNG: ' + rel)
        out[rel] = data
    if png_dir:
        extra = {p.relative_to(png_dir).as_posix() for p in Path(png_dir).rglob('*.png')} - set(out)
        if extra:
            raise ValueError('icon set extra ' + sorted(extra)[0])
    return out


def _zip(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, content in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    return stream.getvalue()


def _publish(output, data, inputs):
    for path, original in inputs.items():
        if path.read_bytes() != original:
            raise ValueError('input changed during build: ' + str(path))
    # Exclusive creation also refuses aliases/hardlinks to every input and stale outputs.
    with Path(output).open('xb') as f:
        f.write(data)
    return hashlib.sha256(data).hexdigest()


def build(output):
    entries, inputs = _collect()
    files = {('agr_tools/' + k if k not in ('mzp.run', 'install.ms') else k): v for k, v in entries.items()}
    return _publish(output, _zip(files), inputs)


def package_contents(version=None):
    model = _model()
    version = version or model.VERSION
    req = '<RuntimeRequirements OS="Win64" Platform="3ds Max" SeriesMin="2024" SeriesMax="2026" />'

    def comp(desc, entry):
        return ('  <Components Description="{}">\n    {}\n    {}\n  </Components>\n').format(desc, req, entry)
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<ApplicationPackage SchemaVersion="1.0" AutodeskProduct="3ds Max" ProductType="Application" '
            'Name="AGR Tools" Description="AGR-DigitalTwin delivery checks and export for NPM/VPM" '
            'AppVersion="{v}" FriendlyVersion="{v}" Author="AGR-DigitalTwin" '
            'ProductCode="{pc}" UpgradeCode="{uc}">\n'
            '  <CompanyDetails Name="AGR-DigitalTwin" />\n  {req}\n'.format(
                v=version, pc=model.product_code(version), uc=model.UPGRADE_CODE, req=req)
            + comp('macroscripts parts', '<ComponentEntry AppName="AGR Tools macros" Version="{}" '
                   'ModuleName="./Contents/agr_tools/agr_tools.mcr" />'.format(version))
            + comp('post-start-up scripts parts', '<ComponentEntry AppName="AGR Tools startup" Version="{}" '
                   'ModuleName="./Contents/agr_tools/startup.ms" />'.format(version))
            + comp('dark icon paths parts', '<ComponentEntry AppName="AGR Tools dark icons" Version="{}" '
                   'ModuleName="./Contents/agr_tools/icons/Dark" />'.format(version))
            + comp('light icon paths parts', '<ComponentEntry AppName="AGR Tools light icons" Version="{}" '
                   'ModuleName="./Contents/agr_tools/icons/Light" />'.format(version))
            + '</ApplicationPackage>\n')


def build_bundle(output):
    """ZIP with one top folder AGR-Tools.bundle/ (unzip into an ApplicationPlugins folder)."""
    entries, inputs = _collect()
    files = {BUNDLE + '/Contents/agr_tools/' + k: v for k, v in entries.items()
             if k not in ('mzp.run', 'install.ms')}
    files[BUNDLE + '/PackageContents.xml'] = package_contents().encode('utf-8')
    return _publish(output, _zip(files), inputs)


def install_bundle(archive, plugins_dir):
    """Unzip the bundle into plugins_dir; refuses an existing AGR-Tools.bundle. Returns installed files."""
    plugins_dir = Path(plugins_dir)
    target = plugins_dir / BUNDLE
    if target.exists():
        raise FileExistsError('already installed: ' + str(target))
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        for n in names:
            if not n.startswith(BUNDLE + '/') or '..' in Path(n).parts or Path(n).is_absolute():
                raise ValueError('unsafe or foreign archive member: ' + n)
        z.extractall(plugins_dir)
    return sorted(names)


def uninstall_bundle(plugins_dir, ini_files=()):
    """Remove AGR-Tools.bundle and the [AGRTools] section the panel writes into 3dsMax.ini."""
    import shutil
    target = Path(plugins_dir) / BUNDLE
    if not (target / 'PackageContents.xml').is_file():
        raise FileNotFoundError('not an AGR Tools bundle: ' + str(target))
    shutil.rmtree(target)
    removed = []
    for ini in ini_files:
        ini = Path(ini)
        if not ini.is_file():
            continue
        raw = ini.read_bytes()
        enc = 'utf-16' if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-8'
        lines = raw.decode(enc).splitlines(keepends=True)
        out, skip = [], False
        for line in lines:
            head = line.strip()
            if head.startswith('[') and head.endswith(']'):
                skip = head[1:-1].strip().lower() == 'agrtools'
            if not skip:
                out.append(line)
        if len(out) != len(lines):
            ini.write_bytes(''.join(out).encode(enc))
            removed.append(str(ini))
    return removed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--bundle', action='store_true',
                        help='write the Application Plugin Package ZIP (AGR-Tools.bundle/) instead of the MZP')
    args = parser.parse_args()
    digest = build_bundle(args.output) if args.bundle else build(args.output)
    print(f'{digest}  {args.output}')


if __name__ == '__main__':
    main()
