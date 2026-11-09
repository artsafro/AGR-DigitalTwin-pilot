"""Write a small ASCII reference FBX and a truncated broken FBX into an output folder.

Binary FBX is not committed. The two text files next to this script are the same bytes
the generator writes, so an agent can see the shape without Max.

    python test-polygon/fbx/make_fbx.py <output dir>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import polygon_core as core

HERE = Path(__file__).resolve().parent


def write(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    ref = folder / 'reference_box.fbx'
    bad = folder / 'broken_truncated.fbx'
    ref.write_text(core.ascii_fbx(), encoding='utf-8')
    bad.write_text('FBX', encoding='utf-8')
    return ref, bad


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) == 2 else str(HERE)
    print(write(target))
