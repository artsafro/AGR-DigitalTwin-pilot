"""new-case: seal this research's external evidence into a NEW Drive directory.

Customer binaries never enter git. This is intentionally a one-card prototype.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--dest', type=Path, required=True)
    p.add_argument('--receipt', type=Path, required=True)
    a = p.parse_args()
    root, dest = a.root.resolve(), a.dest.resolve()
    if root == dest or root in dest.parents or dest in root.parents or a.receipt.exists():
        raise ValueError('nested/aliased evidence or existing receipt')
    for inventory in root.glob('*-inventory.json'):
        data = json.loads(inventory.read_text(encoding='utf-8'))
        if sha(data['source']) != data['sha256'] or sha(data['copy']) != data['sha256']:
            raise ValueError(f'input changed: {inventory}')
    shutil.copytree(root, dest)  # refuses an existing target
    files = sorted(p for p in dest.rglob('*') if p.is_file())
    lines = []
    for output in files:
        relative = output.relative_to(dest)
        digest = sha(output)
        if sha(root / relative) != digest:
            raise ValueError(f'copy mismatch: {relative}')
        lines.append(f'{digest}  {relative.as_posix()}\n')
    manifest = dest / 'SHA256SUMS.txt'
    with manifest.open('x', encoding='utf-8', newline='\n') as stream:
        stream.writelines(lines)
    receipt = {'status': 'sealed_copy_verified', 'directory': str(dest),
               'manifest': str(manifest), 'manifest_sha256': sha(manifest),
               'members_excluding_manifest': len(files),
               'bytes_excluding_manifest': sum(x.stat().st_size for x in files)}
    with a.receipt.open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
    print(json.dumps(receipt,ensure_ascii=False))


if __name__ == '__main__':
    main()
