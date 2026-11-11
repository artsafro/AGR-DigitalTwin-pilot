"""new-case: read-only PDF corpus discovery for issue #1228 (not production)."""
from pathlib import Path
import hashlib
import json
import shutil
import pymupdf

ROOT = Path('C:/x/pdf-album-research/t_5b23c219')
SOURCES = {
    'elv': ('C:/Users/artsafro/Desktop/!3D viz/Dima_Andrew/3_sreda/for_ai', '*.pdf'),
    'tec26': ('C:/Users/artsafro/Desktop/!3D viz/Dima_Andrew/2_kotelnya/ИД', '26.pdf'),
    'cod20207': ('C:/Users/artsafro/Desktop/!3D viz/NTR/22_COD/Исходные данные/001 - Исходные данные/Альбом', '*.pdf'),
}

def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    for name, (folder, pattern) in SOURCES.items():
        paths = list(Path(folder).glob(pattern))
        if len(paths) != 1:
            raise ValueError(f'{name}: expected one PDF, found {paths}')
        src = paths[0]
        dest = ROOT / f'{name}.pdf'
        if dest.exists():
            raise FileExistsError(dest)
        shutil.copy2(src, dest)
        with pymupdf.open(dest) as doc:
            result = {'source': str(src), 'copy': str(dest), 'sha256': hashlib.sha256(dest.read_bytes()).hexdigest(),
                      'bytes': dest.stat().st_size, 'pages': len(doc), 'metadata': doc.metadata,
                      'ocg': doc.get_ocgs(), 'embedded_files': doc.embfile_names(),
                      'index': [{'page': i+1, 'size_pt': list(p.rect), 'text_chars': len(p.get_text()),
                                 'text_preview': p.get_text()[:700]} for i,p in enumerate(doc)]}
        (ROOT / f'{name}-inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False))

if __name__ == '__main__':
    main()
