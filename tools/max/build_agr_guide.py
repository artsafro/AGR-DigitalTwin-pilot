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

    return {'GUIDE.md': roadmap.guide_md(suite, model.VERSION) + stages_md(suite, roadmap, model),
            'flow.svg': roadmap.flow_svg(suite, model.VERSION, colour)}


def wip_note(model):
    """Release 1.0.0 (#1024 R): which stage buttons are still wip (branch Q, deferred to 1.1.0)."""
    wip = [a for a in model.ACTIONS_100 if a.wip]
    if not wip:
        return ''
    return ' — в 1.0.0 это только {} (ветка Q, выпуск в 1.1.0)'.format(
        ', '.join('`{}`'.format(a.tool) for a in wip))


def stages_md(suite, roadmap, model):
    """The 1.0 stage rail of «Путь» (#1024) as the panel draws it (ui_model.stage_rail): big button, second row."""
    station = {rid: '1.0.{}'.format(i) for i, rid in enumerate(roadmap.stage_buttons(suite), 1)}
    out = ['', '## ' + model.MENU_100, '',
           'На вкладке «Путь» над блоками — ряд больших кнопок этапов (иконка, подпись, статус этапа из паспорта '
           'проекта); под каждой — вторая строка с мелкими кнопками этапа. Кнопка в работе видна, но неактивна: '
           '«{}»{}. Страницы блоков 0–9 не меняются.'.format(model.WIP_TIP, wip_note(model)), '',
           '| Этап | Большая кнопка | Мелкие кнопки (вторая строка) |', '|---|---|---|']

    def name(a):
        return '{} (`{}`, {})'.format(a.label, a.tool, station[a.tool])

    for st in model.stage_rail(suite):
        out.append('| {} | {} | {} |'.format(model.stage_title(st.id, st.label), name(st.big),
                                                '; '.join(name(a) for a in st.small) or '—'))
    return '\n'.join(out) + '\n'


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
