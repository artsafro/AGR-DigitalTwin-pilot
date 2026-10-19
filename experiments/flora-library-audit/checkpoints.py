"""New case #189: hash-checked per-row checkpoints; never trust file presence alone."""
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, payload):
    """Atomic progress replacement, not replacement of an exported asset."""
    path = Path(path)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)


def load_valid(path, entry, source_hash):
    path = Path(path)
    if not path.exists():
        return None
    row = json.loads(path.read_text(encoding='utf-8'))
    if row['id'] != entry['id'] or row['name'] != entry['source_name'] or row['source_sha256'] != source_hash:
        raise ValueError('Checkpoint source/identity mismatch')
    for key, hash_key in [('file', 'sha256'), ('preview', 'preview_sha256')]:
        if sha(row[key]) != row[hash_key]:
            raise ValueError('Checkpoint artifact hash mismatch')
    return row
