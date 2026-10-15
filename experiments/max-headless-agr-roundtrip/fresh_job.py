"""Fresh Max process verification of existing-tool and experimental FBX/OBJ files."""
import json
import runpy
import time
from pathlib import Path
import pymxs

rt = pymxs.runtime
HERE = Path(__file__).resolve().parent
# Import definitions only: native_job is deliberately not imported (it executes).
namespace = {}
source = (HERE / 'native_job.py').read_text()
exec(source[:source.index('\ntry:\n    main()')], namespace)
dump, clear = namespace['dump'], namespace['clear']
BASE, OUT = namespace['BASE'], namespace['OUT']
assert not len(rt.objects) and not str(rt.maxFileName)
rt.units.SystemType = rt.Name('meters')
rt.units.SystemScale = 1.0
VERIFY = OUT / next('readback-set-' + str(i) for i in range(100) if not (OUT / ('readback-set-' + str(i))).exists())
VERIFY.mkdir()
rows = []
try:
    files = list(OUT.glob('existing-r*/max-roundtrip.fbx')) + list(OUT.glob('batched-*/max-roundtrip.fbx'))
    files += [OUT / (bench + '-r0.' + fmt) for bench in namespace['BENCHES'] for fmt in ['fbx', 'obj']]
    for index, path in enumerate(files):
        t = time.perf_counter()
        assert rt.importFile(str(path), rt.Name('noPrompt'), using=rt.FBXIMP if path.suffix == '.fbx' else rt.ObjImp)
        data = dump()
        target = VERIFY / ('fresh-' + str(index) + '.json')
        with target.open('x', encoding='utf-8') as f:
            json.dump(data, f)
        rows.append({'path': str(path), 'dump': str(target), 'seconds': time.perf_counter()-t})
        clear()
finally:
    clear()
with (VERIFY / 'fresh-results.json').open('x') as f:
    json.dump(rows, f, indent=2)
print('AGR_FRESH_READBACK', len(rows), 'objects', len(rt.objects))
