"""new-case: generate docs/agr-tools/GUIDE.md and flow.svg from docs/plans/agr-tools-suite.json (#860).

The same JSON drives the «Путь» tab of the AGR Tools panel (roadmap.py), so the help in Max and in the repo
never diverge. `--check` exits 1 when the committed files differ from a fresh render (CI / tests).

    uv run python tools/max/build_agr_guide.py          # write
    uv run python tools/max/build_agr_guide.py --check  # compare only
"""
import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'adapters/max/agr_tools'
SUITE = ROOT / 'docs/plans/agr-tools-suite.json'
OUT = ROOT / 'docs/agr-tools'
# Light theme of the repo picture: Qt Fusion light palette (window, base, text)
LIGHT = ((239, 239, 239), (255, 255, 255), (0, 0, 0))


def _load(name, mod):
    spec = importlib.util.spec_from_file_location(mod, PACKAGE / name)
    m = importlib.util.module_from_spec(spec)
    sys.modules[mod] = m
    spec.loader.exec_module(m)
    return m


def render():
    roadmap = _load('roadmap.py', 'agr_guide_roadmap')
    model = _load('ui_model.py', 'agr_guide_ui_model')
    suite = roadmap.load_file(SUITE)

    def colour(node):
        return '#{:02x}{:02x}{:02x}'.format(*model.block_accent(node['hue'], *LIGHT))

    return {'GUIDE.md': roadmap.guide_md(suite, model.VERSION),
            'flow.svg': roadmap.flow_svg(suite, model.VERSION, colour)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    files = render()
    stale = []
    for name, text in files.items():
        p = OUT / name
        data = text.encode('utf-8')
        if args.check:
            if not p.is_file() or p.read_bytes().replace(b'\r\n', b'\n') != data:
                stale.append(name)
        else:
            OUT.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
    if stale:
        print('stale (regenerate with tools/max/build_agr_guide.py): ' + ', '.join(stale))
        return 1
    print('ok ' + ', '.join(sorted(files)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
