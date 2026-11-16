"""#1613 OKS modelling split [D336]: inset elements, texture-only parts, per-project split reason.

Pattern: n/a | new-case: regression tests of the OKS modelling-split rule wired into the skeleton and docs (#1613).

Acceptance table (PR body) -> tests:
- D336 exists, carries Artem's correction, is cited in SKELETONS.md and the OKS stage docs/skill -> test_d336_*
- the OKS skeleton names inset elements and texture-only parts                               -> test_skeleton_split_*
- the skeleton requires a per-project split reason in the job report (fail-closed check)     -> test_report_line_*
- no master/QA check forces welding inset elements into the body                             -> test_master_check_*
"""
import importlib.util
import itertools
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
import skeleton_guard as sg  # noqa: E402

SK = sg.load_skeletons(ROOT)
OKS_CELLS = ("oks-vpm", "oks-npm")
STAGE_DOCS = ("docs/agents/SKELETONS.md", "docs/scenarios/oks-vpm.md", "routes/npm-oks.md",
              "docs/domain/areas/body.md", "docs/domain/areas/windows.md", ".agents/skills/scenario/SKILL.md")
GOOD = ("Modelling split [D336]: plinth=inset; inset=windows, stained_glass, roof, flashings, posts; "
        "texture=panels; reason=plinth stone has its own texture set, a separate element keeps the body UDIM simple")


def _text(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def _row(did):
    rows = [line for line in _text("docs/decisions.md").splitlines() if line.startswith(f"| {did} |")]
    assert len(rows) == 1, did
    return rows[0]


def test_d336_row_records_the_rule_and_the_correction():
    row = _row("D336")
    for word in ("windows", "stained glass", "roof", "flashings", "posts", "panels", "plinth",
                 "seam", "job report", "[D312]", "weld", "#1613",
                 "Стойки обычно геометрией а панели текстурой со швом"):
        assert word in row, word
    assert "posts and panels by texture" not in row.lower()


@pytest.mark.parametrize("rel", STAGE_DOCS)
def test_d336_cited_in_skeleton_and_oks_stage_docs(rel):
    assert re.search(r"\[D336\]", _text(rel)), rel


def test_d336_is_a_link_not_copied_text():
    """The docs point at the row; Artem's verbatim quote lives only in docs/decisions.md."""
    quote = "Стойки обычно геометрией"
    for rel in STAGE_DOCS:
        assert quote not in _text(rel), rel


def test_skeleton_split_names_inset_and_texture_parts():
    split = SK["stages"]["body"]["modelling_split"]
    assert split["decision"] == "D336"
    assert {"windows", "stained_glass", "roof", "flashings", "posts"} <= set(split["inset"])
    assert set(split["texture"]) == {"panels"}
    assert not set(split["inset"]) & set(split["texture"])
    assert split["per_project"] == {"plinth": ["one_with_body", "inset"]}
    assert split["report_line"].startswith("Modelling split [D336]:")
    for cell in OKS_CELLS:
        assert "body" in SK["cells"][cell]["stages"], cell


def test_skeleton_split_is_listed_in_skeletons_md():
    md = _text("docs/agents/SKELETONS.md")
    section = md.split("## OKS modelling split [D336]", 1)[1].split("\n## ", 1)[0]
    split = SK["stages"]["body"]["modelling_split"]
    for part in split["inset"] + split["texture"] + ["plinth", "Modelling split [D336]:"]:
        assert part in section, part


def test_report_line_good_passes():
    assert sg.modelling_split_problems("# Job report\n\n" + GOOD + "\n", SK) == []


@pytest.mark.parametrize("text,needle", [
    ("", "no `Modelling split [D336]:` line"),
    ("# report without the line\n", "no `Modelling split [D336]:` line"),
    (GOOD + "\n" + GOOD, "more than one"),
    (GOOD.replace("plinth=inset", "plinth=welded"), "plinth"),
    (GOOD.replace("plinth=inset; ", ""), "plinth"),
    (GOOD.split("; reason=")[0], "reason"),
    (GOOD.split("; reason=")[0] + "; reason=   ", "reason"),
    (GOOD.split("; reason=")[0] + "; reason=TODO", "reason"),
    (GOOD.replace("texture=panels", "texture=panels, cornices"), "cornices"),
    (GOOD.replace("inset=windows", "inset=windows, gargoyles"), "gargoyles"),
    (GOOD.replace("texture=panels", "texture=panels, posts"), "both inset and texture"),
    (GOOD.replace("; texture=panels", ""), "texture"),
    (GOOD.replace("inset=windows, stained_glass, roof, flashings, posts; ", ""), "inset"),
    (GOOD.replace("plinth=inset", "plinth=inset; plinth=one_with_body"), "twice"),
    (GOOD.replace("inset=windows", "inset=windows, windows"), "named twice"),
    (GOOD.replace("plinth=inset", "plinth=inset; colour=red"), "unknown field"),
    (GOOD.split("; reason=")[0] + "; reason=<why, for this project>", "placeholder"),
    (None, "no `Modelling split [D336]:` line"),
])
def test_report_line_fails_closed(text, needle):
    problems = sg.modelling_split_problems(text, SK)
    assert problems and any(needle in p for p in problems), (text, problems)


def test_report_line_generated_probe():
    """Every plinth choice x every subset of known parts on either side: pass iff the sides are disjoint."""
    split = SK["stages"]["body"]["modelling_split"]
    parts = split["inset"] + split["texture"]
    checked = 0
    for plinth in split["per_project"]["plinth"]:
        for mask in itertools.product((0, 1, 2), repeat=len(parts)):   # 0 = not named, 1 = inset, 2 = texture
            inset = [p for p, m in zip(parts, mask) if m == 1]
            texture = [p for p, m in zip(parts, mask) if m == 2]
            line = (f"Modelling split [D336]: plinth={plinth}; inset={', '.join(inset)}; "
                    f"texture={', '.join(texture)}; reason=project textures")
            problems = sg.modelling_split_problems(line, SK)
            assert (problems == []) == bool(inset or texture), (line, problems)
            checked += 1
    assert checked == 2 * 3 ** len(parts)


def _master_core():
    path = ROOT / "adapters/max/agr_tools/master_topology_core.py"
    spec = importlib.util.spec_from_file_location("mtc_1613", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_master_check_is_element_wise_and_does_not_need_a_weld():
    """Body + separate inset elements pass per element; the verdict never asks them to be one mesh."""
    core = _master_core()
    objects = [{"name": n, "face_degrees": [4] * 6} for n in
               ("Body", "Window_001", "StainedGlass_001", "Roof", "Flashing_Roof_001", "Flashing_Win_001", "Post_001")]
    report = core.check(objects)
    assert report["status"] == "pass"
    assert [r["name"] for r in report["objects"]] == [o["name"] for o in objects]
    bad = [dict(o) for o in objects]
    bad[1] = {"name": "Window_001", "face_degrees": [4, 5]}
    rows = {r["name"]: r["status"] for r in core.check(bad)["objects"]}
    assert rows.pop("Window_001") == "fail" and set(rows.values()) == {"pass"}


def test_master_check_list_documents_no_forced_weld():
    md = _text("docs/agents/SKELETONS.md")
    section = md.split("## OKS modelling split [D336]", 1)[1].split("\n## ", 1)[0]
    for check in ("tools/qa/master_topology.py", "tools/qa/body_layout.py"):
        assert check in section, check
    assert "no check may require welding" in section
    split = SK["stages"]["body"]["modelling_split"]
    assert split["master_checks"] == "element-wise; no check may require welding inset elements into the body"


def test_skeletons_json_is_valid_json_with_split():
    data = json.loads(_text("docs/agents/skeletons.json"))
    assert "modelling_split" in data["stages"]["body"]
