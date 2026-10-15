"""Copy approved inputs and measure unchanged engine; never modify references."""
import argparse
import hashlib
import json
import shutil
import statistics
import time
from pathlib import Path
from dt_ai.geometry.from_spec import BuildInputs, build
from dt_ai.spec.model import Spec

ROOT = Path(__file__).resolve().parents[2]
BENCHES = ['bench-b01-box', 'bench-b02-corner-niche']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--fixtures', type=Path, required=True)
    args = p.parse_args()
    args.run.mkdir(parents=True, exist_ok=False)
    rows, sources = [], []
    for bench in BENCHES:
        dest = args.run / bench
        dest.mkdir()
        for name in ['spec.json', 'object.json', 'etalon.json', 'tolerances.json', 'etalon.fbx']:
            source = (args.fixtures if name == 'etalon.fbx' else ROOT / 'benchmark') / bench / name
            digest = sha(source)
            shutil.copy2(source, dest / name)
            assert sha(dest / name) == digest
            sources.append({'source': str(source), 'copy': str(dest / name), 'sha256': digest})
        manifest = json.loads((dest / 'etalon.json').read_text())
        assert sha(dest / 'etalon.fbx') == manifest['files']['etalon.fbx']['sha256']
        spec = Spec.model_validate_json((dest / 'spec.json').read_text())
        inputs = BuildInputs.from_object(json.loads((dest / 'object.json').read_text()))
        times = []
        data = None
        for _ in range(3):
            start = time.perf_counter()
            data = build(spec, inputs)
            times.append(time.perf_counter() - start)
        assert data is not None
        (dest / 'engine.json').write_text(json.dumps(data))
        rows.append({'bench': bench, 'seconds': times, 'median_seconds': statistics.median(times),
                     'vertices': sum(len(m['vertices']) for m in data['meshes']),
                     'triangles': sum(len(m['triangles']) for m in data['meshes'])})
    (args.run / 'inputs.json').write_text(json.dumps({'sources': sources, 'engine': rows}, indent=2))
    print(json.dumps(rows, indent=2))


if __name__ == '__main__':
    main()
