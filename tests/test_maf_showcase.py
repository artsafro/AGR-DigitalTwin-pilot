"""new-case: MAF showcase scene (#487): layout, spec text, fail-closed inputs, readback, per-item pending lines."""
import copy
import json
import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

from test_review_publish import FakeAdapter, _load, _publish, review  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
SET = ROOT / "jobs" / "VATUTINO-SITE" / "maf" / "site-maf-set.json"
CONFIG = ROOT / "jobs" / "VATUTINO-SITE" / "maf" / "site-maf-showcase.config.json"


@pytest.fixture(scope="module")
def sc():
    sys.path.insert(0, str(ROOT / "tools" / "review"))
    return _load("maf_showcase")


@pytest.fixture()
def data():
    return (json.loads(SET.read_text(encoding="utf-8")), json.loads(CONFIG.read_text(encoding="utf-8")))


def _readback(layout):
    objs = []
    for s in layout["slots"]:
        for prof, prefix in (("npm", "NPM__"), ("vpm", "VPM__")):
            objs.append(dict(name=f"{prefix}{s['set_id']}_GroundEl", kind="mesh", tris=s[prof]["triangles"],
                             size=list(s[prof]["size"]), text=""))
        objs.append(dict(name=f"TXT_{s['set_id']}", kind="text", tris=0, size=[1, 0, 1], text="\n".join(s["lines"])))
    for r in layout["rows"]:
        objs.append(dict(name=f"ROW_{r['group']}", kind="text", tris=0, size=[1, 0, 1], text=r["label"]))
    return dict(ok=True, units="meters", scale=1.0, version=28000, objects=objs)


def test_plan_real_set_has_13_pairs_text_and_rows(sc, data):
    report, config = data
    layout = sc.plan(report, config, check_hashes=False)
    ids = [p["set_id"] for p in report["positions"]]
    assert sorted(s["set_id"] for s in layout["slots"]) == sorted(ids) and len(ids) == 13
    assert [r["group"] for r in layout["rows"]] == list(sc.GROUPS)
    assert sum(r["count"] for r in layout["rows"]) == 13
    assert next(r for r in layout["rows"] if r["group"] == "lighting")["count"] == 0
    fbx = [s[p]["fbx"] for s in layout["slots"] for p in ("npm", "vpm")]
    assert len(set(fbx)) == 26
    by = {p["set_id"]: p for p in report["positions"]}
    for s in layout["slots"]:
        pos, text = by[s["set_id"]], "\n".join(s["lines"])
        for needle in (s["set_id"], pos["schedule"], pos["name"], pos["catalogue_id"],
                       f"{pos['npm']['triangles']} / {pos['vpm']['triangles']}", "Спецификация L/W/H", "Замер NPM L/W/H"):
            assert needle in text, (s["set_id"], needle)
    review_ids = sorted(s["set_id"] for s in layout["slots"] if s["review"])
    assert review_ids == ["VAT_MAF_T3510_28", "VAT_MAF_T3510_32"]
    t28 = next(s for s in layout["slots"] if s["set_id"].endswith("_28"))["lines"]
    assert "!! REVIEW" in t28[0] and any("D094" in line for line in t28) and any("исключение" in line for line in t28)
    assert all(s["lines"][0].endswith("pass") for s in layout["slots"] if not s["review"])


@pytest.mark.parametrize("case", ["unmapped", "extra", "unknown_group", "duplicate", "empty", "nan_size",
                                  "inf_tris", "zero_tris", "bad_exception", "extra_exception", "dup_fbx"])
def test_plan_fails_closed(sc, data, case):
    report, config = copy.deepcopy(data[0]), copy.deepcopy(data[1])
    if case == "unmapped":
        del config["groups"]["VAT_MAF_T3510_09"]
        match = "VAT_MAF_T3510_09"
    elif case == "extra":
        config["groups"]["VAT_MAF_X"] = "kids"
        match = "VAT_MAF_X"
    elif case == "unknown_group":
        config["groups"]["VAT_MAF_T3510_09"] = "roof"
        match = "roof"
    elif case == "duplicate":
        report["positions"].append(copy.deepcopy(report["positions"][0]))
        match = "duplicate"
    elif case == "empty":
        report["positions"] = []
        match = "no positions"
    elif case == "nan_size":
        report["positions"][3]["vpm"]["measured_size_m"][1] = math.nan
        match = "VAT_MAF_T3510_09"
    elif case == "inf_tris":
        report["positions"][3]["npm"]["triangles"] = math.inf
        match = "VAT_MAF_T3510_09"
    elif case == "zero_tris":
        report["positions"][3]["npm"]["triangles"] = 0
        match = "VAT_MAF_T3510_09"
    elif case == "bad_exception":
        config["user_exceptions"]["VAT_MAF_T3510_28"] = []
        match = "VAT_MAF_T3510_28"
    elif case == "extra_exception":
        config["user_exceptions"]["VAT_MAF_Y"] = "x"
        match = "VAT_MAF_Y"
    else:
        report["positions"][1]["vpm"]["fbx"] = report["positions"][0]["npm"]["fbx"]
        match = "used twice"
    with pytest.raises(sc.ShowcaseError, match=match):
        sc.plan(report, config, check_hashes=False)


def test_plan_rejects_missing_or_changed_fbx(sc, data, tmp_path):
    report, config = copy.deepcopy(data[0]), data[1]
    for pos in report["positions"]:
        for prof in ("npm", "vpm"):
            path = tmp_path / prof / f"{pos['set_id']}.fbx"
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(f"{prof}{pos['set_id']}".encode())
            pos[prof]["fbx"] = path.as_posix()
            pos[prof]["sha256"] = sc.sha256(path)
    assert len(sc.plan(report, config)["slots"]) == 13
    Path(report["positions"][5]["vpm"]["fbx"]).write_bytes(b"changed")
    with pytest.raises(sc.ShowcaseError, match="VAT_MAF_T3510_12 vpm: SHA256"):
        sc.plan(report, config)
    Path(report["positions"][5]["vpm"]["fbx"]).unlink()
    with pytest.raises(sc.ShowcaseError, match="missing FBX"):
        sc.plan(report, config)


def test_layout_probe_random_groupings_never_overlap_or_drop(sc, data):
    """Probe: seed 487, 200 random groupings/orders: every id once, no x overlap in a row, rows apart."""
    report, config = data
    rng = random.Random(487)
    for _ in range(200):
        rep = copy.deepcopy(report)
        rng.shuffle(rep["positions"])
        cfg = dict(config, groups={k: rng.choice(sc.GROUPS) for k in config["groups"]})
        layout = sc.plan(rep, cfg, check_hashes=False)
        assert sorted(s["set_id"] for s in layout["slots"]) == sorted(cfg["groups"])
        for row in layout["rows"]:
            slots = sorted((s for s in layout["slots"] if s["group"] == row["group"]), key=lambda s: s["npm_x"])
            assert len(slots) == row["count"]
            for s in slots:
                assert s["y"] == row["y"]
                assert s["npm_x"] + s["npm"]["size"][0] < s["vpm_x"] < s["vpm_x"] + s["vpm"]["size"][0] < s["text_x"]
            for a, b in zip(slots, slots[1:]):
                assert a["text_x"] + max(map(len, a["lines"])) * sc.CHAR_W < b["npm_x"]
        for a, b in zip(layout["rows"], layout["rows"][1:]):
            depth = max([1.0] + [s[p]["size"][1] for s in layout["slots"] if s["group"] == a["group"]
                                 for p in ("npm", "vpm")])
            assert b["y"] - a["y"] >= depth + sc.ROW_GAP - 1e-9


def test_build_script_escapes_and_counts(sc, data):
    report, config = copy.deepcopy(data[0]), data[1]
    report["positions"][0]["name"] = 'Скамья "Тест" C:\\path'
    layout = sc.plan(report, config, check_hashes=False)
    ms = sc.build_script(layout, Path("C:/x/o/s.max"), Path("C:/x/o/r.png"), Path("C:/x/o/b.json"), Path("C:/x/o"))
    assert ms.count("placeFbx \"") == 26 and ms.count('"TXT_') == 13 and ms.count('"ROW_') == 5
    assert 'Скамья \\"Тест\\" C:\\\\path' in ms
    for token in ("@SLOTS@", "@ROWS@", "@OUT@", "@RENDER@", "@REPORT@", "@ROWCAMS@", "@CX@", "@DIST@"):
        assert token not in ms


def test_readback_counts_and_fail_closed(sc, data):
    layout = sc.plan(*data, check_hashes=False)
    good = _readback(layout)
    assert sc.check_readback(good, layout) == dict(meshes=26, texts=13, row_labels=5,
                                                     triangles=sum(s[p]["triangles"] for s in layout["slots"]
                                                                   for p in ("npm", "vpm")))
    mutations = {
        "ok false": lambda r: r.update(ok=False),
        "units": lambda r: r.update(units="centimeters"),
        "scale 1000": lambda r: r["objects"][0]["size"].__setitem__(0, r["objects"][0]["size"][0] * 1000),
        "at threshold+": lambda r: r["objects"][0]["size"].__setitem__(2, r["objects"][0]["size"][2] + 0.0021),
        "tris": lambda r: r["objects"][1].update(tris=r["objects"][1]["tris"] - 1),
        "missing mesh": lambda r: r["objects"].pop(0),
        "missing text": lambda r: r["objects"].pop(2),
        "text differs": lambda r: r["objects"][2].update(text="x"),
        "extra node": lambda r: r["objects"].append(dict(name="Box001", kind="other", tris=0, size=[0, 0, 0], text="")),
        "extra mesh": lambda r: r["objects"].append(dict(name="NPM__VAT_MAF_T3510_01_copy", kind="mesh", tris=1,
                                                         size=[1, 1, 1], text="")),
        "duplicate name": lambda r: r["objects"].append(dict(r["objects"][0])),
        "missing row": lambda r: r["objects"].pop(),
    }
    for name, mutate in mutations.items():
        bad = copy.deepcopy(good)
        mutate(bad)
        with pytest.raises(sc.ShowcaseError):
            sc.check_readback(bad, layout)
        assert name


def test_output_folder_overlap_rejected(sc, tmp_path):
    fbx = tmp_path / "v005-set" / "npm" / "a.fbx"
    fbx.parent.mkdir(parents=True)
    fbx.write_bytes(b"x")
    for out in (fbx, fbx.parent, fbx.parent / "sub", tmp_path / "v005-set" / "npm" / "..", tmp_path):
        with pytest.raises(sc.ShowcaseError, match="overlaps"):
            sc.check_output(out, [fbx])
    sc.check_output(tmp_path / "showcase" / "v001", [fbx])


def test_cli_fresh_process_refuses_existing_or_input_folder(tmp_path):
    script = ROOT / "tools" / "review" / "maf_showcase.py"
    existing = tmp_path / "exists"
    existing.mkdir()
    base = [sys.executable, str(script), "--set", str(SET), "--config", str(CONFIG), "--plan-only", "--out"]
    data = json.loads(SET.read_text(encoding="utf-8"))
    if not Path(data["positions"][0]["npm"]["fbx"]).is_file():
        pytest.skip("v005-set files are outside git and absent on this machine")
    for out, needle in ((existing, "exists"), (Path(data["positions"][0]["npm"]["fbx"]).parent, "overlaps"),
                        (Path(data["out_dir"]) / "showcase", "overlaps")):
        proc = subprocess.run(base + [str(out)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert proc.returncode == 1 and needle in proc.stderr, proc.stderr
    assert sorted(p.name for p in existing.iterdir()) == []


# --- pending.json: one verdict line per item (#487) ---------------------------------------------

def test_publish_items_one_pending_line_per_set_id(review, tmp_path):
    ids = [f"VAT_MAF_T3510_{n:02d}" for n in (1, 2, 7, 9, 11, 12, 16, 26, 27, 28, 29, 31, 32)]
    assert _publish(review, tmp_path, FakeAdapter(), task="487", slug="maf-vatutino-showcase", items=ids) == 0
    rows = json.loads((tmp_path / "review" / "pending.json").read_text(encoding="utf-8"))
    assert [r["item"] for r in rows] == ids and {r["task"] for r in rows} == {"#487"}
    assert len({r["path"] for r in rows}) == 1
    review.verdict(task="487", status="ok", note="принято", review_root=tmp_path / "review", item=ids[0])
    review.verdict(task="487", status="changes", note="переделать", review_root=tmp_path / "review", item=ids[9])
    rows = json.loads((tmp_path / "review" / "pending.json").read_text(encoding="utf-8"))
    assert [r.get("status") for r in rows] == ["ok"] + [None] * 8 + ["changes"] + [None] * 3
    before = (tmp_path / "review" / "pending.json").read_bytes()
    for bad in ("VAT_MAF_T3510_99", "", "a b", "../x"):
        with pytest.raises(review.ReviewError):
            review.verdict(task="487", status="ok", note="x", review_root=tmp_path / "review", item=bad)
    assert (tmp_path / "review" / "pending.json").read_bytes() == before


@pytest.mark.parametrize("items", [[], ["A", "A"], ["ok", "bad id"], "VAT_MAF_T3510_01", [None], ["x" * 65]])
def test_publish_bad_items_write_nothing(review, tmp_path, items):
    with pytest.raises(review.ReviewError):
        _publish(review, tmp_path, FakeAdapter(), task="487", slug="maf-vatutino-showcase", items=items)
    assert not (tmp_path / "review").exists() or not any((tmp_path / "review").rglob("*"))


def test_publish_without_items_keeps_one_line(review, tmp_path):
    assert _publish(review, tmp_path, FakeAdapter()) == 0
    rows = json.loads((tmp_path / "review" / "pending.json").read_text(encoding="utf-8"))
    assert len(rows) == 1 and "item" not in rows[0]
    review.verdict(task="348", status="ok", note="x", review_root=tmp_path / "review")
    assert json.loads((tmp_path / "review" / "pending.json").read_text(encoding="utf-8"))[0]["status"] == "ok"
