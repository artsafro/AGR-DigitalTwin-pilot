"""new-case: hash-verified, no-clobber TEC26 intake source staging (not a shared adapter)."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path('C:/Users/artsafro/Desktop/!3D viz/Dima_Andrew/2_kotelnya')
DEST = Path('C:/x/tec26-oks/sources-v001')

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def main():
    files = list((ROOT / 'Vlad_OKS').rglob('*')) + list((ROOT / 'maps_kpp').rglob('*'))
    files += [ROOT / 'KPP1_VPM_NPM_quads_v002.max']
    pd = ROOT / 'ИД/ТЭЦ-26 для передачи АГР/Актуальная ПД'
    files += [p for p in pd.rglob('*') if p.is_file() and
              (any(f'АС.{i:02d}' in str(p) for i in range(4, 10)) or
               p.suffix.lower() == '.docm' or 'Текстовая часть' in str(p))]
    files = sorted({p for p in files if p.is_file()})
    assert files and not DEST.exists(), 'Missing sources or destination already exists'
    DEST.mkdir(parents=True, exist_ok=False)
    rows = []
    for src in files:
        rel = src.relative_to(ROOT)
        out = DEST / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        before = src.stat()
        sha = digest(src)
        with src.open('rb') as inp, out.open('xb') as target:
            shutil.copyfileobj(inp, target)
        assert digest(out) == sha == digest(src), f'Hash changed: {src}'
        assert src.stat().st_mtime_ns == before.st_mtime_ns, f'Source changed: {src}'
        rows.append(dict(source=str(src), copy=str(out), relative=rel.as_posix(),
                         sha256=sha, bytes=before.st_size, mtime_ns=before.st_mtime_ns))
    report = Path(__file__).resolve().parents[1] / 'census/sources.json'
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open('x', encoding='utf-8') as stream:
        json.dump(rows, stream, ensure_ascii=False, indent=2)
    with (DEST.parent / 'SHA256SUMS.txt').open('x', encoding='utf-8') as stream:
        stream.write(''.join(r['sha256'] + '  sources-v001/' + r['relative'] + '\n' for r in rows))
    print(f'Copied and hash verified {len(rows)} files; {sum(r["bytes"] for r in rows)} bytes')

if __name__ == '__main__':
    main()
