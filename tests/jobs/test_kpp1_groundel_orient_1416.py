"""#1416 review P1 (#1418): GroundEl winding must pass the FBX readback rule; every fail finding is waived or open."""
import importlib.util
import json
import math
import random
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
JOB = ROOT / "jobs/KPP1/ground-budget-1416"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan = _load("ground_copy_plan", JOB / "ground_copy_plan.py")
maf = _load("maf_surface", ROOT / "src/twinqa/geometry/maf_surface.py")

CUBE_V = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
CUBE_F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]  # outward


def _facts(coords, polys):
    normals = [[(0.0, 0.0, 1.0)] * len(p) for p in polys]
    return maf.surface_facts(coords, polys, normals)


def _random_mesh(rng):
    coords, polys = [], []
    for _ in range(rng.randint(1, 4)):
        s, ox, oy, oz = rng.uniform(0.2, 5), rng.uniform(-50, 50), rng.uniform(-50, 50), rng.uniform(-3, 3)
        split = rng.random() < 0.5  # duplicated vertex records at the same position (readback welds them)
        base = len(coords)
        coords.extend((ox + x * s, oy + y * s, oz + z * s) for x, y, z in CUBE_V)
        for f in CUBE_F:
            f = [base + i for i in f]
            if split and rng.random() < 0.5:
                n = len(coords)
                coords.extend([coords[i] for i in f])
                f = [n, n + 1, n + 2, n + 3]
            if rng.random() < 0.4:
                f = f[::-1]
            if rng.random() < 0.5:  # quad -> two triangles, like the export triangulation
                polys.extend([[f[0], f[1], f[2]], [f[0], f[2], f[3]]])
            else:
                polys.append(list(f))
        if rng.random() < 0.3:  # zero-area face on a cube edge: bmesh sees 3 faces there, the readback 2
            polys.append([base + 0, base + 1, base + 1 if rng.random() < 0.5 else base + 0])
            coords.append(tuple((a + b) / 2 for a, b in zip(coords[base], coords[base + 1])))
            polys.append([base + 0, len(coords) - 1, base + 1])
    if rng.random() < 0.5:  # flat component: only consistent winding is required
        b = len(coords)
        coords.extend([(100, 0, 0), (101, 0, 0), (101, 1, 0), (100, 1, 0), (102, 0, 0), (102, 1, 0)])
        second = [b + 1, b + 4, b + 5, b + 2]
        polys.extend([[b, b + 1, b + 2, b + 3], second[::-1] if rng.random() < 0.5 else second])
    return coords, polys


def test_readback_flips_leave_zero_flipped_and_inconsistent_brute_force():
    rng = random.Random(1416)
    for _ in range(300):
        coords, polys = _random_mesh(rng)
        flips = plan.readback_flips(coords, polys)
        fixed = [p[::-1] if i in flips else p for i, p in enumerate(polys)]
        facts = _facts(coords, fixed)
        assert facts["flipped_faces"] == 0 and facts["inconsistent_edges"] == 0, facts


def test_already_outward_mesh_needs_no_flip_and_zero_area_faces_are_never_flipped():
    polys = [list(f) for f in CUBE_F] + [[0, 1, 1]]
    assert plan.readback_flips(CUBE_V, polys) == set()


def test_non_finite_vertex_fails_closed():
    for bad in (math.nan, math.inf):
        with pytest.raises(plan.PlanError, match="non-finite"):
            plan.readback_flips([(bad, 0, 0)] + CUBE_V[1:], [list(f) for f in CUBE_F])


# D313 waives the customer Ground's own modelling defects (fails of the Ground FBX only); everything else that
# is not "pass" - including R1 rows with the same finding name - must be listed in REPORT.md "## Open items"
GROUND = "0000_Kpp_1_Ground.fbx"
D313_WAIVED = {("V003", "ground skirt depth", GROUND, "fail"), ("V004", "topology defects", GROUND, "fail"),
               ("V004", "co-directional clearance", GROUND, "fail")}


def _audit_fixture(monkeypatch, tmp_path, findings, report):
    """Exercise the real package audit with synthetic files, never customer assets."""
    (tmp_path / "package-npm-findings.json").write_text(
        json.dumps({"findings": findings}), encoding="utf-8")
    (tmp_path / "REPORT.md").write_text(report, encoding="utf-8")
    monkeypatch.setitem(globals(), "JOB", tmp_path)
    test_every_non_pass_finding_of_the_current_npm_package_is_waived_or_open()


def test_r1_topology_fail_is_not_covered_by_ground_prose(monkeypatch, tmp_path):
    data = json.loads((JOB / "package-npm-findings.json").read_text(encoding="utf-8"))
    report = (JOB / "REPORT.md").read_text(encoding="utf-8")
    next(f for f in data["findings"] if f["name"] == "topology defects"
         and f["evidence"] == "0000_Kpp_1_01.fbx")["status"] = "fail"
    with pytest.raises(AssertionError, match="topology defects"):
        _audit_fixture(monkeypatch, tmp_path, data["findings"], report)


def _synthetic_rows(*rows):
    return [*rows, {"stage": "V004", "name": "MAF flipped normals", "evidence": GROUND, "status": "pass"}]


def test_ground_waivers_do_not_need_open_item_prose(monkeypatch, tmp_path):
    rows = [{"stage": stage, "name": name, "evidence": evidence, "status": status}
            for stage, name, evidence, status in sorted(D313_WAIVED)]
    _audit_fixture(monkeypatch, tmp_path, _synthetic_rows(*rows), "## Open items\n")


@pytest.mark.parametrize("text", [
    "V004 topology defects", "intro V004 topology defects", "* V004 topology defects",
    "\n## History\n- V004 topology defects", "- V004 topology defects extra",
])
def test_non_bullet_or_later_section_is_not_an_open_item(monkeypatch, tmp_path, text):
    row = {"stage": "V004", "name": "topology defects", "evidence": "0000_Kpp_1_01.fbx", "status": "fail"}
    with pytest.raises(AssertionError, match="topology defects"):
        _audit_fixture(monkeypatch, tmp_path, _synthetic_rows(row), "## Open items\n" + text)


def test_explicit_open_item_bullet_covers_non_pass(monkeypatch, tmp_path):
    row = {"stage": "V004", "name": "topology defects", "evidence": "0000_Kpp_1_01.fbx", "status": "fail"}
    _audit_fixture(monkeypatch, tmp_path, _synthetic_rows(row),
                   "## Open items\n- V004 topology defects — fail — 0000_Kpp_1_01.fbx\n")


@pytest.mark.parametrize("rows", [[], [{"stage": "V004", "name": "topology defects", "status": "fail"}]])
def test_empty_or_missing_evidence_fails_closed(monkeypatch, tmp_path, rows):
    with pytest.raises((AssertionError, KeyError)):
        _audit_fixture(monkeypatch, tmp_path, rows, "## Open items\n- V004 topology defects\n")


def test_waiver_key_matrix(monkeypatch, tmp_path):
    # Independent literal oracle: only these three Ground fail identities are waived.
    cases = [("V003", "ground skirt depth"), ("V004", "topology defects"),
             ("V004", "co-directional clearance")]
    for stage, name in cases:
        for target in (GROUND, "0000_Kpp_1_01.fbx", "other.fbx", ""):
            for status in ("fail", "review", "not_run", "unsupported", "", math.nan, math.inf):
                row = {"stage": stage, "name": name, "evidence": target, "status": status}
                for rows in (_synthetic_rows(row, row), list(reversed(_synthetic_rows(row)))):
                    if target == GROUND and status == "fail":
                        _audit_fixture(monkeypatch, tmp_path, rows, "## Open items\n")
                    else:
                        with pytest.raises(AssertionError, match=name):
                            _audit_fixture(monkeypatch, tmp_path, rows, "## Open items\n")


def test_every_non_pass_finding_of_the_current_npm_package_is_waived_or_open():
    data = json.loads((JOB / "package-npm-findings.json").read_text(encoding="utf-8"))
    report = (JOB / "REPORT.md").read_text(encoding="utf-8")
    open_block = report.split("## Open items", 1)[1].split("\n## ", 1)[0]
    open_bullets = "\n".join(line for line in open_block.splitlines() if line.startswith("- "))
    assert data["findings"], "empty findings list is not a pass"
    seen = set()
    for f in data["findings"]:
        key = (f["stage"], f["name"], f["evidence"], f["status"])
        seen.add(key[:2])
        if f["status"] == "pass":
            continue
        assert key in D313_WAIVED or re.search(
            rf"^- {re.escape(f['stage'])}\b[^\n]*{re.escape(f['name'])}(?= —|$)",
            open_bullets, re.MULTILINE), key
    assert ("V004", "MAF flipped normals") in seen
    maf_row = next(f for f in data["findings"] if f["name"] == "MAF flipped normals")
    assert maf_row["status"] != "fail", maf_row
