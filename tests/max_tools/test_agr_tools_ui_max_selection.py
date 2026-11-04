"""new-case: MaxBackend selection behaviour of the AGR Tools 0.6.0 panel with a fake pymxs runtime (#861).

No live 3ds Max: `pymxs`, `agr_tools_ui_model` and `agr_tools_ui_qt` are fake modules injected into
sys.modules for the import of ui_max.py only (monkeypatch restores them after each test).

Id base: finding ids are 1-based Max sub-object indices. runtime.xview / runtime.matid enumerate
`range(1, polyop.getNum{Verts,Faces}(copy) + 1)` on an Editable_Poly copy of the node, so they map 1:1
onto polyop.setVertSelection / polyop.setFaceSelection of an Editable_Poly base object; no +/-1 shift.
"""
import importlib.util
import sys
import types
from collections import namedtuple
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[2] / 'adapters/max/agr_tools'
Row = namedtuple('Row', 'handle name check ok code detail ids')


class Node:
    def __init__(self, name, handle, cls='Editable_Poly', verts=10, faces=12):
        self.name, self.handle, self.cls = name, handle, cls
        self.verts, self.faces = verts, faces
        self.baseObject = self
        self.alive = True


class FakePolyop:
    def __init__(self, rt):
        self.rt = rt

    def getNumVerts(self, n):
        return n.verts

    def getNumFaces(self, n):
        return n.faces

    def setVertSelection(self, n, ids):
        self.rt.calls.append(('vert', n.name, set(ids)))

    def setFaceSelection(self, n, ids):
        self.rt.calls.append(('face', n.name, set(ids)))


class FakeRuntime:
    Editable_Poly = 'Editable_Poly'
    Editable_Mesh = 'Editable_Mesh'

    def __init__(self, nodes):
        self.nodes = {n.handle: n for n in nodes}
        self.selection = []
        self.calls = []
        self.polyop = FakePolyop(self)
        self.subObjectLevel = 0
        self.undefined = object()

    @property
    def geometry(self):
        return [n for n in self.nodes.values() if n.alive]

    def select(self, what):
        self.selection = list(what) if isinstance(what, (list, tuple)) else [what]

    def clearSelection(self):
        self.selection = []

    def getAnimByHandle(self, h):
        return self.nodes.get(h)

    def isValidNode(self, n):
        return n is not None and n.alive

    def classOf(self, obj):
        return obj.cls

    def setCommandPanelTaskMode(self, mode):
        self.calls.append(('panel', mode))

    def Name(self, s):
        return s


@pytest.fixture
def scene(monkeypatch):
    a, b = Node('A', 101), Node('B', 102)
    rt = FakeRuntime([a, b])
    pymxs = types.ModuleType('pymxs')
    pymxs.runtime = rt
    qt = types.ModuleType('agr_tools_ui_qt')
    qt.QtGui = qt.QtWidgets = None
    qt.max_icon = qt.max_main_window = lambda *a: None
    monkeypatch.setitem(sys.modules, 'pymxs', pymxs)
    monkeypatch.setitem(sys.modules, 'agr_tools_ui_model', types.ModuleType('agr_tools_ui_model'))
    monkeypatch.setitem(sys.modules, 'agr_tools_ui_qt', qt)
    spec = importlib.util.spec_from_file_location('agr_tools_ui_max_t861', PKG / 'ui_max.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rt.select([b])  # the user's selection

    class Agr:
        seen = None

        def ui(self, tool):
            Agr.seen = list(rt.selection)
            rt.select([a])  # runtime._report selects the failed nodes
            if tool == 'boom':
                raise ValueError('tool failed')
            return {'tool': tool}

    return types.SimpleNamespace(rt=rt, a=a, b=b, agr=Agr, backend=mod.MaxBackend(Agr(), 'C:/icons'))


def test_scope_all_restores_user_selection(scene):
    assert scene.backend.run_tool('cleanup', True) == {'tool': 'cleanup'}
    assert scene.agr.seen == [scene.a, scene.b]  # the tool saw the whole scene
    assert scene.rt.selection == [scene.b]


def test_scope_all_restores_selection_when_tool_raises(scene):
    with pytest.raises(ValueError):
        scene.backend.run_tool('boom', True)
    assert scene.rt.selection == [scene.b]


def test_scope_all_drops_nodes_deleted_by_the_tool(scene):
    scene.b.alive = False
    scene.backend.run_tool('cleanup', True)
    assert scene.rt.selection == []


def test_selection_scope_keeps_tool_result_selection(scene):
    scene.backend.run_tool('cleanup', False)
    assert scene.agr.seen == [scene.b]
    assert scene.rt.selection == [scene.a]  # unchanged behaviour: failed nodes selected


@pytest.mark.parametrize('check,code,kind,level', [
    ('xview', 'overlap_faces', 'face', 4), ('matid', 'udim_id', 'face', 4),
    ('matid', 'empty_slot', 'face', 4), ('xview', 'overlap_vertices', 'vert', 1)])
def test_row_selects_finding_components(scene, check, code, kind, level):
    assert scene.backend.select_row(Row(101, 'A', check, False, code, '', (7, 3, 3))) is True
    assert scene.rt.selection == [scene.a]
    assert (kind, 'A', {3, 7}) in scene.rt.calls
    assert scene.rt.subObjectLevel == level


@pytest.mark.parametrize('row', [
    Row(101, 'A', 'names', False, 'unknown_code', '', (3, 7)),   # unknown id type
    Row(101, 'A', 'export', False, 'overlap_faces', '', (1,)),   # export ids: not proven polyop indices
    Row(101, 'A', 'xview', False, 'overlap_faces', '', ()),      # no ids
    Row(101, 'A', 'xview', False, 'overlap_faces', '', (0, 3)),  # 0 is outside the 1-based range
    Row(101, 'A', 'xview', False, 'overlap_faces', '', (3, 13)),  # A has 12 faces
])
def test_row_without_mappable_ids_selects_node_only(scene, row):
    assert scene.backend.select_row(row) is True
    assert scene.rt.selection == [scene.a]
    assert scene.rt.calls == []
    assert scene.rt.subObjectLevel == 0


def test_row_on_editable_mesh_selects_node_only(scene):
    scene.a.cls = 'Editable_Mesh'  # poly-copy face indices do not map onto mesh triangles
    scene.backend.select_row(Row(101, 'A', 'xview', False, 'overlap_faces', '', (3, 7)))
    assert scene.rt.selection == [scene.a]
    assert scene.rt.calls == []


@pytest.mark.parametrize('handle', [999, None])
def test_row_with_missing_node_keeps_selection(scene, handle):
    assert scene.backend.select_row(Row(handle, 'gone', 'xview', False, 'overlap_faces', '', (3,))) is False
    assert scene.rt.selection == [scene.b]
    assert scene.rt.calls == []
