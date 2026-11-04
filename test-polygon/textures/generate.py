"""Write the synthetic polygon PNGs into an output folder. Nothing is committed as PNG.

    python test-polygon/textures/generate.py <output dir>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import polygon_core as core

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: generate.py <output dir>')
    print(core.generate_outputs(sys.argv[1]))
