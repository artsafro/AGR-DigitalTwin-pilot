"""Read-only audit of Gate 1 proposal evidence; does not read scoring keys."""

import hashlib
import json
from pathlib import Path
import statistics
import subprocess

from dt_ai.core.models import PartsList
from pydantic import ValidationError

ROOT = Path('C:/x/trainer/runs')
IDS = ('kpp1-v004', 'g22-k2-stage1', '63a-stage1')
NAMES = {'parts.json', 'partslist.json'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(wt, *args):
    return subprocess.check_output(['git', '-C', str(wt), *args], timeout=15)


def candidates(root):
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError(f'Missing or aliased evidence root: {root}')
    return sorted(p for p in root.rglob('*.json') if p.name.lower() in NAMES)


def probe(directory):
    wt = directory / 'wt'
    tracked = set(git(wt, 'ls-files', '--full-name', '-z', '--', 'jobs').decode().split('\0'))
    head = git(wt, 'rev-parse', 'HEAD').decode().strip()
    committed = set(git(wt, 'ls-tree', '-r', '--name-only', '-z', head, '--', 'jobs').decode().split('\0'))
    paths = candidates(directory / 'built') + [
        p for p in candidates(wt / 'jobs') if p.relative_to(wt).as_posix() not in tracked | committed
    ]
    row = {'worktree_head': head, 'files': {}, 'proposals': []}
    for name in ('last.txt', 'run.json'):
        row['files'][name] = digest((directory / name).read_bytes())
    for path in paths:
        data = path.read_bytes()
        proposal = {'path': path.relative_to(directory).as_posix(), 'file_sha256': digest(data)}
        try:
            proposal['approval_sha256'] = PartsList.model_validate_json(data).approval_sha256()
        except ValidationError as exc:
            proposal['invalid'] = sorted({error['type'] for error in exc.errors()})
        row['proposals'].append(proposal)
    return row


def main():
    series = []
    reference = None
    for _ in range(3):
        rows = {key: probe(ROOT / f'{key}-codex-20261124') for key in IDS}
        if reference is not None and rows != reference:
            raise RuntimeError('Evidence drift between readbacks')
        reference = rows
        series.append(sum(any('approval_sha256' in p for p in row['proposals']) for row in rows.values()))
    print(json.dumps({'rows': reference, 'series': series, 'median': statistics.median(series),
                      'spread': max(series) - min(series), 'held_out': 'not_measured'}, indent=2))


if __name__ == '__main__':
    main()
