"""new-case: AGR Tools panel Max backend selection behaviour (#861) against a fake pymxs runtime.

Row click selects the finding's components (vertices / faces) when the id type is known, else the object;
scope "вся сцена" never leaves the user's selection replaced. SYNTHETIC scene: fake nodes, no 3ds Max.
"""
import importlib.util
import random
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'

FACE_CODES = ('udim_id', 'empty_id', 'empty_slot', 'missing_material')


class Node:
    def __init__(self, handle, nv=8, nf=6, poly=True, modifiers=()):
        self.handle, self.nv, self.nf = handle, nv, nf
        self.baseObject = 'Editable_Poly' if poly else 'Editable_mesh'
        self.modifiers = list(modifiers)
        self.valid = True
        self.vsel, self.fsel = None, None


class FakeRt:
    Editable_Poly = 'Editable_Poly'

    def __init__(self, nodes, geometry=None):
        self.nodes = {n.handle: n for n in nodes}
        self.objects = list(nodes)
        self.geometry = list(geometry if geometry is not None else nodes)
        self.selection = []
        self.subObjectLevel = 0
        self.calls = []
        rt = self

        class Polyop:
            @staticmethod
            def getNumVerts(n):
                return n.nv

            @staticmethod
            def getNumFaces(n):
                return n.nf

            @staticmethod
            def setVertSelection(n, ids):
                rt.calls.append(('vsel', n.handle, list(ids)))
                n.vsel = list(ids)

            @staticmethod
            def setFaceSelection(n, ids):
                rt.calls.append(('fsel', n.handle, list(ids)))
                n.fsel = list(ids)
        self.polyop = Polyop

    def select(self, x):
        self.selection = list(x) if isinstance(x, (list, tuple)) else [x]

    def clearSelection(self):
        self.selection = []

    def getAnimByHandle(self, h):
        return self.nodes.get(h)

    def isValidNode(self, n):
        return n is not None and n.valid

    def classOf(self, obj):
        return obj

    def Name(self, s):
        return s

    def setCommandPanelTaskMode(self, mode):
        self.calls.append(('mode', mode))

    def redrawViews(self):
        pass


@pytest.fixture
def ui(monkeypatch):
    spec = importlib.util.spec_from_file_location('agr_tools_ui_model', PKG / 'ui_model.py')
    model = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, 'agr_tools_ui_model', model)
    spec.loader.exec_module(model)
    pymxs = types.ModuleType('pymxs')
    pymxs.runtime = None
    qt = types.ModuleType('agr_tools_ui_qt')
    qt.QtGui = qt.QtWidgets = None
    qt.max_icon = qt.max_main_window = lambda *a: None
    monkeypatch.setitem(sys.modules, 'pymxs', pymxs)
    monkeypatch.setitem(sys.modules, 'agr_tools_ui_qt', qt)
    spec = importlib.util.spec_from_file_location('agr_tools_ui_max_test', PKG / 'ui_max.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def make(nodes, geometry=None, agr=None):
        rt = FakeRt(nodes, geometry)
        mod.rt = rt
        return mod.MaxBackend(agr or types.SimpleNamespace(), ''), rt, model
    return make


def _row(model, node, check, code, ids):
    return model.Row(node.handle if node else None, 'n', check, False, code, '', tuple(ids))


# ---- row click -------------------------------------------------------------------------------------------
def test_row_click_selects_vertices_of_overlap_vertices(ui):
    n = Node(7, nv=10)
    be, rt, m = ui([n])
    assert be.select_row(_row(m, n, 'xview', 'overlap_vertices', (2, 5))) == 'vertex'
    assert rt.selection == [n] and n.vsel == [2, 5] and n.fsel is None and rt.subObjectLevel == 1
    assert ('mode', 'modify') in rt.calls


@pytest.mark.parametrize('check,code', [('xview', 'overlap_faces')] + [('matid', c) for c in FACE_CODES])
def test_row_click_selects_faces_of_face_findings(ui, check, code):
    n = Node(7, nf=6)
    be, rt, m = ui([n])
    assert be.select_row(_row(m, n, check, code, (1, 6))) == 'face'
    assert rt.selection == [n] and n.fsel == [1, 6] and n.vsel is None and rt.subObjectLevel == 4


@pytest.mark.parametrize('case', ['unknown_code', 'export_check', 'modifier', 'not_poly', 'ok_row', 'empty',
                                  'zero', 'too_big', 'negative', 'bool', 'float', 'nan', 'str', 'exact_plus_one'])
def test_row_click_falls_back_to_object_only(ui, case):
    n = Node(7, nv=4, nf=3, poly=case != 'not_poly', modifiers=['TurboSmooth'] if case == 'modifier' else ())
    be, rt, m = ui([n])
    check, code, ids = 'xview', 'overlap_faces', (1, 2)
    check, code, ids = {
        'unknown_code': ('names', 'bad_name', (1,)), 'export_check': ('export', 'overlap_faces', (1,)),
        'ok_row': ('xview', 'ok', ()), 'empty': (check, code, ()), 'zero': (check, code, (0, 1)),
        'too_big': (check, code, (1, 4)), 'negative': (check, code, (-1,)), 'bool': (check, code, (True,)),
        'float': (check, code, (1.0,)), 'nan': (check, code, (float('nan'),)), 'str': (check, code, ('1',)),
        'exact_plus_one': ('xview', 'overlap_vertices', (5,)),
    }.get(case, (check, code, ids))
    assert be.select_row(_row(m, n, check, code, ids)) == 'object'
    assert rt.selection == [n] and n.vsel is None and n.fsel is None and rt.subObjectLevel == 0


def test_row_click_at_exact_count_selects(ui):
    n = Node(7, nv=4, nf=3)
    be, rt, m = ui([n])
    assert be.select_row(_row(m, n, 'xview', 'overlap_vertices', (4,))) == 'vertex' and n.vsel == [4]
    assert be.select_row(_row(m, n, 'matid', 'udim_id', (3,))) == 'face' and n.fsel == [3]


def test_row_click_on_missing_node_clears_selection(ui):
    n = Node(7)
    be, rt, m = ui([n])
    rt.selection = [n]
    assert be.select_row(_row(m, None, 'xview', 'overlap_faces', (1,))) is False
    assert rt.selection == [] and rt.calls == []


def test_row_click_probe_components_always_within_node(ui):
    """Generated probe: component selection only with valid 1-based ids of a plain poly node, else object."""
    rng = random.Random(861)
    for _ in range(500):
        n = Node(3, nv=rng.randint(1, 20), nf=rng.randint(1, 20), poly=rng.random() > 0.2,
                 modifiers=['Bend'] if rng.random() < 0.2 else ())
        be, rt, m = ui([n])
        check, code = rng.choice([('xview', 'overlap_vertices'), ('xview', 'overlap_faces'), ('matid', 'empty_id'),
                                  ('export', 'overlap_vertices'), ('names', 'x')])
        ids = tuple(rng.randint(-1, 22) for _ in range(rng.randint(0, 4)))
        got = be.select_row(_row(m, n, check, code, ids))
        count = n.nv if code == 'overlap_vertices' else n.nf
        valid = (check in ('xview', 'matid') and n.baseObject == 'Editable_Poly' and not n.modifiers
                 and ids and all(1 <= i <= count for i in ids))
        assert rt.selection == [n]
        if valid:
            assert got in ('vertex', 'face') and sorted(set(n.vsel or n.fsel)) == sorted(set(ids))
        else:
            assert got == 'object' and n.vsel is None and n.fsel is None


# ---- scope "вся сцена" -----------------------------------------------------------------------------------
def _agr(rt, seen, raise_for=()):
    def run(tool):
        seen.append((tool, list(rt.selection)))
        if tool in raise_for:
            raise RuntimeError('boom')
        return {'tool': tool}
    return types.SimpleNamespace(CHECKS_070=('census',), EDITS_080={'model.triangulate': 1},
                                 ui=run, edit_ui=run, remember=lambda r: None)


@pytest.mark.parametrize('tool,scope', [('cleanup', 'geometry'), ('census', 'objects'),
                                        ('model.triangulate', 'geometry')])
def test_scope_all_restores_user_selection(ui, tool, scope, capsys):
    a, b, c = Node(1), Node(2), Node(3)
    be, rt, _ = ui([a, b, c], geometry=[a, b])
    seen = []
    be.agr = _agr(rt, seen)
    rt.selection = [c]
    be.run_tool(tool, True)
    assert seen == [(tool, getattr(rt, scope))]  # the tool saw the whole scope
    assert rt.selection == [c]  # ... and the user's selection is back


def test_scope_all_restores_on_error_and_drops_deleted_nodes(ui):
    a, b = Node(1), Node(2)
    be, rt, _ = ui([a, b])
    seen = []
    be.agr = _agr(rt, seen, raise_for=('cleanup',))
    rt.selection = [a, b]
    b.valid = False
    with pytest.raises(RuntimeError):
        be.run_tool('cleanup', True)
    assert rt.selection == [a]


def test_scope_all_restores_empty_selection(ui):
    a = Node(1)
    be, rt, _ = ui([a])
    be.agr = _agr(rt, [])
    be.run_tool('cleanup', True)
    assert rt.selection == []


def test_scope_selection_never_touches_selection(ui):
    a, b = Node(1), Node(2)
    be, rt, _ = ui([a, b])
    seen = []
    be.agr = _agr(rt, seen)
    rt.selection = [b]
    be.run_tool('cleanup', False)
    assert seen == [('cleanup', [b])] and rt.selection == [b]


def test_scope_all_probe_selection_unchanged(ui):
    """Generated probe: after any scope-all run the selection equals the user's still-valid selection."""
    rng = random.Random(8610)
    for _ in range(300):
        nodes = [Node(i) for i in range(1, rng.randint(1, 8) + 1)]
        be, rt, _ = ui(nodes, geometry=[n for n in nodes if rng.random() < 0.7])
        tool = rng.choice(['cleanup', 'census', 'model.triangulate'])
        fails = rng.random() < 0.3
        be.agr = _agr(rt, [], raise_for=(tool,) if fails else ())
        rt.selection = [n for n in nodes if rng.random() < 0.5]
        before = list(rt.selection)
        for n in nodes:
            n.valid = rng.random() > 0.1
        try:
            be.run_tool(tool, True)
        except RuntimeError:
            assert fails
        assert rt.selection == [n for n in before if n.valid]
