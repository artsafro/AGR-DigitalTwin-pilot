"""#1618 body-modelling research: deliverable structure and the read-only census scripts. new-case: research doc guard.

Acceptance table (issue #1618):
- Russian research doc with sources (links) and etalon measurements            -> test_doc_russian_sources_and_measurements
- rule list mapped to skeleton stage + skill + #1616 component (table)          -> test_mapping_table_covers_every_rule
- skeleton body stage links the doc (link only), skill section in both copies   -> test_skeleton_and_skill_link_the_rules
- Russian one-page summary for Artem                                            -> test_summary_is_russian_one_page
- census scripts: measured numbers, fail-closed on empty / output == input      -> test_band_census_*, test_analyze_grid_*
"""
import importlib.util
import json
import re
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/research/body-modelling.md"
SUMMARY = ROOT / "docs/research/body-modelling-summary-ru.md"
SCRIPTS = ROOT / "docs/research/body-modelling-1618"
RULES = [f"BM-{i:02d}" for i in range(1, 15)]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cyr_share(text):
    letters = re.findall(r"[A-Za-zА-Яа-яЁё]", re.sub(r"`[^`]*`|\([^)]*\)|https?://\S+", "", text))
    return sum(1 for c in letters if re.match(r"[А-Яа-яЁё]", c)) / max(len(letters), 1)


def test_doc_russian_sources_and_measurements():
    text = DOC.read_text(encoding="utf-8")
    head = text.split("\n## ", 1)[0]
    assert text.startswith("# ") and _cyr_share(head) > 0.8
    sources = text.split("## 1. Источники", 1)[1].split("\n## ", 1)[0]
    links = set(re.findall(r"\]\((https?://[^)]+)\)", sources))
    assert len(links) >= 10, links
    measured = text.split("## 2. Эталон G22", 1)[1].split("\n## ", 1)[0]
    for number in ("148 186", "97,6 %", "96,1 %", "98,2 %", "957"):
        assert number in measured, number
    assert "G:/Мой диск/AGR-evidence/1618-body-training/" in text


def test_mapping_table_covers_every_rule():
    text = DOC.read_text(encoding="utf-8")
    rules = text.split("## 5. Правила", 1)[1].split("\n## ", 1)[0]
    assert re.findall(r"^- \*\*(BM-\d\d)\.", rules, re.M) == RULES
    table = text.split("## 6. Таблица соответствия", 1)[1].split("\n## ", 1)[0]
    rows = [r for r in table.splitlines() if r.startswith("| BM-")]
    assert [r.split()[1] for r in rows] == RULES
    stages = set(json.loads((ROOT / "docs/agents/skeletons.json").read_text(encoding="utf-8"))["stages"])
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        assert len(cells) == 6, row
        named = set(re.findall(r"`([a-z-]+)`", cells[1]))
        assert named and named <= stages, (row, named - stages)
        assert cells[2] and cells[3] and cells[4] and cells[5], row
    components = " ".join(r.split("|")[4] for r in rows)
    for comp in ("quad share", "slivers", "n-gons", "inset elements vs body",
                 "welds across element boundaries", "max face side"):
        assert comp in components, comp


def test_skeleton_and_skill_link_the_rules():
    sk = (ROOT / "docs/agents/SKELETONS.md").read_text(encoding="utf-8")
    body_rows = [r for r in sk.splitlines() if re.match(r"^\| \d+ \| `body`", r)]
    assert len(body_rows) == 2
    for row in body_rows:
        assert "(../research/body-modelling.md#5-правила)" in row
    copies = [(ROOT / p).read_bytes() for p in (".agents/skills/scenario/SKILL.md", ".claude/skills/scenario/SKILL.md")]
    assert copies[0] == copies[1]
    skill = copies[0].decode("utf-8")
    section = skill.split("### Body stage: clean body grid (#1618)", 1)[1].split("\n## ", 1)[0]
    assert "../../../docs/research/body-modelling.md" in section
    assert (ROOT / ".agents/skills/scenario" / "../../../docs/research/body-modelling.md").resolve() == DOC.resolve()


def test_summary_is_russian_one_page():
    text = SUMMARY.read_text(encoding="utf-8")
    assert _cyr_share(text) > 0.85
    assert len(text.splitlines()) <= 60
    assert "1618-body-training/g22_etalon_wire_sheet.png" in text


def test_artem_answers_replace_proposals():
    text = DOC.read_text(encoding="utf-8")
    summary = SUMMARY.read_text(encoding="utf-8")
    assert "## 8. Принятые решения" in text
    assert "стойки — обычно\n  текстура" not in text
    assert "рельеф, панели, стойки — обычно текстура" not in summary
    assert "**Стойки — геометрия по умолчанию**" in text
    assert "**геометрия по умолчанию**" in summary
    assert "[D336]" in text and "[D336]" in summary
    for doc in (text, summary):
        assert "[D337]" in doc and "[D338]" in doc
        assert "WARN-only (OBSERVE)" in doc and "первую неделю" in doc
        assert "Нужно твоё решение" not in doc
    for path in (".agents/skills/scenario/SKILL.md", ".claude/skills/scenario/SKILL.md"):
        skill = (ROOT / path).read_text(encoding="utf-8")
        assert "[D337]" in skill and "[D338]" in skill
        assert "quads >= 95 %" in skill and "slivers <= 0.5 %" in skill
        assert "until Artem confirms" not in skill


def test_main_split_and_new_decision_rows_survive():
    sk = (ROOT / "docs/agents/SKELETONS.md").read_text(encoding="utf-8")
    for row in sk.splitlines():
        if re.match(r"^\| \d+ \| `body`", row):
            assert "[D336]" in row and "body-modelling.md#5-правила" in row
    decisions = (ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    rows = [r for r in decisions.splitlines() if re.match(r"^\| D33[678] \|", r)]
    assert [r.split("|")[1].strip() for r in rows] == ["D336", "D337", "D338"]
    for row in rows[1:]:
        assert "2026-11-17" in row and "comment 6938656989" in row
    assert "2 cm" in rows[1] and "texture step" in rows[1]
    assert "quads >= 95 %" in rows[2] and "slivers <= 0.5 %" in rows[2]
    assert "WARN-only (OBSERVE)" in rows[2] and "first week" in rows[2]
    domain = (ROOT / "docs/domain/areas/body.md").read_text(encoding="utf-8")
    assert "[D337]" in domain and "[D338]" in domain


def _fixture(tmp_path, faces, verts):
    """Synthetic dump: rejoined faces == exported faces (no UV needed by the census)."""
    verts = np.asarray(verts, float)
    tris = [f for f in faces if len(f) == 3] or [[0, 1, 2]]
    p = tmp_path / "fx.npz"
    np.savez(p, verts=verts, jverts=verts, jn=np.array([len(f) for f in faces]),
             ji=np.array([i for f in faces for i in f]), fn=np.array([3] * len(tris)),
             fi=np.array([i for f in tris for i in f]), mats=np.zeros(len(tris), int),
             jmats=np.zeros(len(faces), int), uvn=np.zeros(0, int), uvf=np.zeros((0, 2)), names=np.array(["m"]))
    return p


def _wall(nx=4, nz=6, step=1.0, h=3.0):
    """A flat wall in XZ (normal -Y) 4 m wide, z from 0 to nz*h/..., quads only."""
    verts, idx = [], {}
    zs = [i * 1.5 for i in range(nz + 1)]
    for i in range(nx + 1):
        for j, z in enumerate(zs):
            idx[i, j] = len(verts)
            verts.append((i * step, 0.0, z))
    faces = [[idx[i, j], idx[i + 1, j], idx[i + 1, j + 1], idx[i, j + 1]] for i in range(nx) for j in range(nz)]
    return verts, faces


def test_band_census_counts_quads_slivers_and_near_duplicates(tmp_path):
    bc = _load("band_census")
    verts, faces = _wall(nx=4, nz=12)  # 18 m high: ground / typical / top bands
    # near-duplicate vertical 1 cm right of x=2 on the typical band: split one quad column into a sliver strip
    base = len(verts)
    verts += [(2.01, 0.0, 9.0), (2.01, 0.0, 10.5)]
    faces.append([base, base + 1, 13 * 2 + 7])  # sliver triangle (x=2.01 -> x=2 at z=10.5)
    p = _fixture(tmp_path, faces, verts)
    rep = bc.census(str(p), 0.0)
    ft = rep["bands"]["facade/typical"]
    assert ft["tris"] == 1 and ft["slivers"] == 1
    assert rep["bands"]["facade/ground"]["tris"] == 0
    assert rep["main_planes"]["ny"]["near_duplicate_lt_3cm"] == 1


def test_band_census_fail_closed(tmp_path):
    bc = _load("band_census")
    empty = _fixture(tmp_path, [], [(0, 0, 0)])
    with pytest.raises(SystemExit):
        bc.census(str(empty), 0.0)
    verts, faces = _wall()
    p = _fixture(tmp_path, faces, verts)
    before = p.read_bytes()
    with pytest.raises(SystemExit):
        bc.main([str(p), "--out", str(p)])
    with pytest.raises(SystemExit):
        bc.main([str(p), "--out", str(tmp_path / "x.npz")])
    assert p.read_bytes() == before and not (tmp_path / "x.npz").exists()


def test_analyze_grid_quad_share_and_levels(tmp_path):
    ag = _load("analyze_grid")
    verts, faces = _wall(nx=4, nz=6)
    d = tmp_path / "dump"
    d.mkdir()
    p = _fixture(d, faces, verts)
    res = ag.analyse(str(p))
    assert res["quads"] == 24 and res["residual_tris"] == 0 and res["ngons"] == 0 and res["quad_share"] == 1.0
    assert len(res["z_levels_1pct"]) == 7 and res["components"] == 1
    with pytest.raises(SystemExit):
        ag.analyse(str(_fixture(tmp_path, [], [(0, 0, 0)])))
