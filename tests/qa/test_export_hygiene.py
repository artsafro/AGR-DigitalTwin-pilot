"""Pre-export hygiene check (#547): custom attributes, UDP, map channel 1 name, channels 2+.

Fixtures are synthetic scene dumps (no 3ds Max run); they mimic what
ClearCustomAttributesAndObjProp_010.ms reads: CA lists per owner, the UDP buffer
(map channel names live there as `MapChannel:N = name`) and the supported map channels.
"""
import copy
import itertools
import json
import random
import subprocess
import sys

import pytest

from twinqa.export_hygiene import (
    CHECK_NAMES, InputError, hygiene_findings, load_scene, main, parse_udp, repair_plan,
)


def clean(name="Box001"):
    return {"name": name, "custom_attributes": {"base": [], "node": [], "modifiers": [], "materials": []},
            "user_props": "MapChannel:1 = UV\r\n", "map_channels": [1]}


def by_name(findings):
    return {f.name: f for f in findings}


def statuses(findings):
    return {f.name: f.status for f in findings}


# --- one finding per defect, a clean object passes -------------------------------------------

def test_clean_object_passes_every_check():
    found = hygiene_findings([clean()], "scene.json")
    assert [f.name for f in found] == list(CHECK_NAMES)
    assert set(statuses(found).values()) == {"pass"}


@pytest.mark.parametrize("owner", ["base", "node", "modifiers", "materials"])
def test_custom_attribute_on_any_owner_is_a_finding(owner):
    obj = clean()
    obj["custom_attributes"][owner] = ["AGR_Data"]
    f = by_name(hygiene_findings([obj], "s"))["no custom attributes"]
    assert f.status == "fail"
    assert f"Box001.{owner}: AGR_Data" in f.observed
    assert f.data["objects"] == {"Box001": {owner: ["AGR_Data"]}}


def test_user_defined_property_is_a_finding_but_map_channel_lines_are_not():
    obj = clean()
    obj["user_props"] = "MapChannel:1 = UV\r\nfloor = 3\r\n\r\n"
    found = by_name(hygiene_findings([obj], "s"))
    assert found["no user-defined properties"].status == "fail"
    assert found["no user-defined properties"].data["objects"] == {"Box001": ["floor = 3"]}
    assert found["map channel 1 named UV"].status == "pass"


@pytest.mark.parametrize("udp, expect", [
    ("", "unnamed (Max default '1:map')"),
    ("MapChannel:1 = map\r\n", "'map'"),
    ("MapChannel:1 = uv\r\n", "'uv'"),
    ("MapChannel:1 = UVChannel_1\r\n", "'UVChannel_1'"),
])
def test_map_channel_1_not_named_uv_is_a_finding(udp, expect):
    obj = clean()
    obj["user_props"] = udp
    f = by_name(hygiene_findings([obj], "s"))["map channel 1 named UV"]
    assert f.status == "fail"
    assert f"Box001: {expect}" in f.observed


def test_missing_map_channel_1_is_a_finding():
    obj = clean()
    obj["map_channels"] = [2]
    f = by_name(hygiene_findings([obj], "s"))["map channel 1 named UV"]
    assert f.status == "fail" and "Box001: map channel 1 missing" in f.observed


def test_conflicting_channel_1_names_are_a_finding():
    obj = clean()
    obj["user_props"] = "MapChannel:1 = UV\r\nMapChannel:1 = map\r\n"
    f = by_name(hygiene_findings([obj], "s"))["map channel 1 named UV"]
    assert f.status == "fail" and "ambiguous" in f.observed


def test_channels_2_plus_are_listed():
    a, b = clean("A"), clean("B")
    a["map_channels"] = [1, 2, 5]
    a["user_props"] += "MapChannel:2 = lightmap\r\n"
    b["user_props"] += "MapChannel:3 = orphan\r\n"  # name without a channel: listed too
    f = by_name(hygiene_findings([a, b], "s"))["no map channels 2+"]
    assert f.status == "fail"
    assert f.data["objects"] == {"A": {"channels": [2, 5], "names": {"2": "lightmap"}},
                                 "B": {"channels": [], "names": {"3": "orphan"}}}
    assert "A: channels [2, 5]" in f.observed and "B: orphan names {3: 'orphan'}" in f.observed


def test_parse_udp_follows_max_pattern():
    names, other = parse_udp("MapChannel:1 = UV\nMapChannel:x = y\n  MapChannel:2=  light  \nfoo\n")
    assert names == {1: ["UV"], 2: ["light"]}
    assert other == ["MapChannel:x = y", "foo"]


# --- the check never deletes data -----------------------------------------------------------

def test_check_and_repair_plan_do_not_mutate_input():
    obj = clean()
    obj["custom_attributes"]["base"] = ["X"]
    obj["user_props"] = "a=1\r\nMapChannel:1 = map\r\n"
    obj["map_channels"] = [1, 2]
    before = copy.deepcopy(obj)
    hygiene_findings([obj], "s")
    plan = repair_plan([obj])
    assert obj == before
    cleaned = plan["objects"][0]["cleaned"]
    assert hygiene_findings([cleaned], "s") and set(statuses(hygiene_findings([cleaned], "s")).values()) == {"pass"}
    assert plan["objects"][0]["actions"] == [
        {"action": "remove_custom_attributes", "owner": "base", "names": ["X"]},
        {"action": "clear_user_defined_lines", "lines": ["a=1"]},
        {"action": "delete_map_channels", "channels": [2], "names": {}},
        {"action": "rename_map_channel_1", "from": "map", "to": "UV"},
    ]


def test_repair_plan_reports_missing_channel_1_as_unrepairable():
    obj = clean()
    obj["map_channels"] = []
    obj["user_props"] = ""
    entry = repair_plan([obj])["objects"][0]
    assert entry["unrepairable"] == ["map channel 1 missing: no UV to rename"]
    assert by_name(hygiene_findings([entry["cleaned"]], "s"))["map channel 1 named UV"].status == "fail"


# --- fail-closed input -----------------------------------------------------------------------

@pytest.mark.parametrize("objects, needle", [
    ([], "no objects"),
    ("x", "list"),
    ([1], "object #0"),
    ([{k: v for k, v in clean().items() if k != "user_props"}], "user_props"),
    ([{k: v for k, v in clean().items() if k != "map_channels"}], "map_channels"),
    ([{k: v for k, v in clean().items() if k != "custom_attributes"}], "custom_attributes"),
    ([{**clean(), "name": ""}], "name"),
    ([{**clean(), "extra": 1}], "extra"),
    ([{**clean(), "custom_attributes": {"base": [], "node": [], "modifiers": []}}], "materials"),
    ([{**clean(), "custom_attributes": {"base": [], "node": [], "modifiers": [], "materials": [], "layer": []}}], "layer"),
    ([{**clean(), "custom_attributes": {"base": "X", "node": [], "modifiers": [], "materials": []}}], "base"),
    ([{**clean(), "user_props": None}], "user_props"),
    ([{**clean(), "map_channels": [1, 1]}], "duplicate"),
    ([{**clean(), "map_channels": [0]}], "0"),
    ([{**clean(), "map_channels": [-1]}], "-1"),
    ([{**clean(), "map_channels": [1.0]}], "1.0"),
    ([{**clean(), "map_channels": [True]}], "True"),
    ([{**clean(), "map_channels": [float("nan")]}], "nan"),
    ([{**clean(), "map_channels": [100]}], "100"),
    ([clean("A"), clean("A")], "duplicate object name 'A'"),
])
def test_bad_input_is_an_error_naming_it(objects, needle):
    with pytest.raises(InputError, match=None) as err:
        hygiene_findings(objects, "s")
    assert needle in str(err.value)


def test_max_channel_99_is_accepted():
    obj = clean()
    obj["map_channels"] = [1, 99]
    assert by_name(hygiene_findings([obj], "s"))["no map channels 2+"].status == "fail"


# --- invariant probes ------------------------------------------------------------------------

def _random_object(rng, i):
    obj = clean(f"O{i}")
    for owner in obj["custom_attributes"]:
        if rng.random() < 0.2:
            obj["custom_attributes"][owner] = [f"CA{rng.randint(0, 9)}"]
    lines = []
    if rng.random() < 0.3:
        lines.append(f"prop{rng.randint(0, 9)} = {rng.randint(0, 9)}")
    name = rng.choice(["UV", "UV", "map", "uv", None])
    if name is not None:
        lines.append(f"MapChannel:1 = {name}")
    if rng.random() < 0.2:
        lines.append(f"MapChannel:{rng.randint(2, 4)} = extra")
    rng.shuffle(lines)
    obj["user_props"] = "\r\n".join(lines)
    obj["map_channels"] = sorted(set(([1] if rng.random() < 0.9 else []) + rng.sample(range(2, 6), rng.randint(0, 2))))
    return obj


def test_probe_every_defective_object_named_and_repair_cleans_every_repairable_one():
    rng = random.Random(547)
    for _ in range(300):
        objs = [_random_object(rng, i) for i in range(rng.randint(1, 4))]
        before = copy.deepcopy(objs)
        found = hygiene_findings(objs, "s")
        assert objs == before
        flagged = set(itertools.chain.from_iterable(f.data["objects"] for f in found))
        for f in found:
            assert (f.status == "pass") == (not f.data["objects"])
        plan = repair_plan(objs)
        assert objs == before
        assert [e["name"] for e in plan["objects"]] == [o["name"] for o in objs]
        for entry in plan["objects"]:
            assert bool(entry["actions"] or entry["unrepairable"]) == (entry["name"] in flagged)
            if not entry["unrepairable"]:
                assert set(statuses(hygiene_findings([entry["cleaned"]], "s")).values()) == {"pass"}


# --- CLI: repair off by default, never writes over inputs ------------------------------------

def _dump(tmp_path, objects):
    p = tmp_path / "scene.json"
    p.write_text(json.dumps({"objects": objects}), encoding="utf-8")
    return p


def test_cli_check_only_by_default(tmp_path, capsys):
    obj = clean()
    obj["map_channels"] = [1, 2]
    scene = _dump(tmp_path, [obj])
    before = scene.read_bytes()
    report = tmp_path / "report.json"
    assert main([str(scene), "--report", str(report)]) == 1
    assert scene.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["report.json", "scene.json"]
    data = json.loads(report.read_text(encoding="utf-8"))
    assert {f["name"]: f["status"] for f in data["findings"]}["no map channels 2+"] == "fail"


def test_cli_clean_scene_exits_zero(tmp_path):
    assert main([str(_dump(tmp_path, [clean()]))]) == 0


def test_cli_repair_switch_writes_plan_to_new_path(tmp_path):
    obj = clean()
    obj["user_props"] = "x=1"
    scene = _dump(tmp_path, [obj])
    out = tmp_path / "plan.json"
    assert main([str(scene), "--repair-out", str(out)]) == 1
    plan = json.loads(out.read_text(encoding="utf-8"))
    assert plan["source"] == str(scene)
    assert not list(tmp_path.glob("*.partial"))


@pytest.mark.parametrize("alias", ["same", "dot", "report"])
def test_cli_output_aliasing_an_input_or_report_exits_nonzero_and_writes_nothing(tmp_path, alias):
    scene = _dump(tmp_path, [clean()])
    before = scene.read_bytes()
    report = tmp_path / "report.json"
    out = {"same": scene, "dot": tmp_path / "." / "scene.json", "report": report}[alias]
    argv = [str(scene), "--repair-out", str(out)]
    if alias == "report":
        argv += ["--report", str(report)]
    assert main(argv) == 2
    assert scene.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["scene.json"]


def test_cli_report_aliasing_input_exits_nonzero(tmp_path):
    scene = _dump(tmp_path, [clean()])
    before = scene.read_bytes()
    assert main([str(scene), "--report", str(scene)]) == 2
    assert scene.read_bytes() == before


@pytest.mark.parametrize("text", ["", "{}", "[]", '{"objects": []}', "not json", '{"objects": [], "x": 1}'])
def test_cli_bad_scene_exits_2(tmp_path, text):
    p = tmp_path / "scene.json"
    p.write_text(text, encoding="utf-8")
    assert main([str(p)]) == 2


def test_load_scene_missing_file_is_input_error(tmp_path):
    with pytest.raises(InputError):
        load_scene(tmp_path / "nope.json")


def test_cli_fresh_process(tmp_path):
    scene = _dump(tmp_path, [clean()])
    r = subprocess.run([sys.executable, "-m", "twinqa.export_hygiene", str(scene)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "pass" in r.stdout


def test_rule_text_cites_team_script_as_origin():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    for rel in ("docs/domain/export-import.md", "docs/domain/areas/uv-atlas.md", "src/twinqa/export_hygiene.py"):
        text = (root / rel).read_text(encoding="utf-8")
        assert "ClearCustomAttributesAndObjProp_010.ms" in text, rel
        assert rel.endswith(".py") or "export_hygiene" in text, rel
