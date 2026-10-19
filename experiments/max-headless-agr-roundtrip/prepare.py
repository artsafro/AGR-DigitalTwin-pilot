"""Copy fixture inputs and time the unchanged engine (no DCC)."""
import hashlib
import json
import shutil
import statistics
import time
from pathlib import Path

from dt_ai.geometry.from_spec import BuildInputs, build
from dt_ai.spec.model import Spec

ROOT = Path(__file__).resolve().parents[2]
SCRATCH = Path('C:/Users/artsafro/.hermes/profiles/dt-experimenter-codex/cache/scratch/agr-exp-t_69ee7ca0')
NATIVE = SCRATCH / 'agr-3dsmax-t_69ee7ca0'
BENCHES = ['bench-b01-box', 'bench-b02-corner-niche']


def main():
    NATIVE.mkdir(parents=True, exist_ok=True)
    rows = []
    for bench in BENCHES:
        dest = SCRATCH / bench
        dest.mkdir(exist_ok=True)
        for name in ['spec.json', 'object.json', 'etalon.json', 'tolerances.json']:
            shutil.copy2(ROOT / 'benchmark' / bench / name, dest / name)
        manifest = json.loads((dest / 'etalon.json').read_text())
        src = Path('C:/Users/artsafro/AGR-DigitalTwin/data/benchmark') / bench / 'etalon.fbx'
        shutil.copy2(src, dest / 'etalon.fbx')
        sha = hashlib.sha256((dest / 'etalon.fbx').read_bytes()).hexdigest()
        assert sha == manifest['files']['etalon.fbx']['sha256']
        spec = Spec.model_validate_json((dest / 'spec.json').read_text())
        inputs = BuildInputs.from_object(json.loads((dest / 'object.json').read_text()))
        times = []
        for _ in range(3):
            t = time.perf_counter()
            dump = build(spec, inputs)
            times.append(time.perf_counter() - t)
        (dest / 'engine.json').write_text(json.dumps(dump), encoding='utf-8')
        rows.append({'bench': bench, 'sha256': sha, 'build_seconds': times,
                     'median_seconds': statistics.median(times),
                     'vertices': sum(len(m['vertices']) for m in dump['meshes']),
                     'triangles': sum(len(m['triangles']) for m in dump['meshes'])})
    (ROOT / 'experiments/max-headless-agr-roundtrip/baseline-engine.json').write_text(json.dumps(rows, indent=2))
    print(json.dumps(rows, indent=2))


if __name__ == '__main__':
    main()
