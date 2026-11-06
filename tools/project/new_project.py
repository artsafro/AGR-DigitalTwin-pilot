"""new-case: «завести проект» (contract K1, #1024, branch F): jobs/<ID>/passport.json + PASSPORT.md by the schema.

    python tools/project/new_project.py KPP1 [--root .] [--title T] [--address A] [--source path]
    python tools/project/new_project.py --check jobs/KPP1/passport.json

Create: a NEW folder jobs/<ID>/ (refuses an existing passport or a non-empty folder; never overwrites) with a valid
passport (11 stages todo, metres, Z up, source level C until source.intake) and its PASSPORT.md. The scene is
linked later by the «Паспорт» button (file property agr_passport). Check: exit 1 and the violations for a passport
that breaks schemas/ProjectPassport.schema.json. Logic: adapters/max/agr_tools/passport_core.py (stdlib).
"""
import argparse
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


_CORE = []


def core():
    """passport_core, loaded once (one PassportError class)."""
    if not _CORE:
        spec = importlib.util.spec_from_file_location('agr_tools_passport_core',
                                                      ROOT / 'adapters/max/agr_tools/passport_core.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _CORE.append(mod)
    return _CORE[0]


def create(project_id, root='.', title=None, address=None, source=None):
    """Path of the new passport.json; FileExistsError / PassportError on refusal."""
    pc = core()
    folder = Path(pc.project_dir(str(root), project_id))
    if (folder / pc.PASSPORT_FILE).exists():
        raise FileExistsError('passport exists, open it with the «Паспорт» button: {}'.format(
            folder / pc.PASSPORT_FILE))
    if folder.exists() and any(folder.iterdir()):
        raise FileExistsError('{} exists and is not empty; refusing to create a passport in it'.format(folder))
    passport = pc.new_passport(project_id, source_path=source or 'untitled', title=title, address=address)
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in ((pc.PASSPORT_FILE, pc.dumps(passport)),
                       (pc.MARKDOWN_FILE, pc.markdown(passport).encode('utf-8'))):
        with open(folder / name, 'xb') as f:
            f.write(data)
    return folder / pc.PASSPORT_FILE


def check(path):
    pc = core()
    passport, sha = pc.read(os.fspath(path))
    return passport, sha


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('project_id', nargs='?')
    ap.add_argument('--root', default='.')
    ap.add_argument('--title')
    ap.add_argument('--address')
    ap.add_argument('--source')
    ap.add_argument('--check', metavar='PASSPORT')
    a = ap.parse_args(argv)
    pc = core()
    try:
        if a.check:
            passport, sha = check(a.check)
            print('OK {} {} stages {}'.format(passport['project_id'], sha,
                                              ' '.join('{}:{}'.format(s['id'], s['status'])
                                                       for s in passport['stages'])))
            return 0
        if not a.project_id:
            ap.error('project_id is required (or --check PASSPORT)')
        print(create(a.project_id, a.root, a.title, a.address, a.source))
        return 0
    except (pc.PassportError, FileExistsError) as exc:
        print('ERROR ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
