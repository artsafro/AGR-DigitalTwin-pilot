"""Methods-only Ground builder build that skips the Ground gate and lists the failed gates (#733, Artem 2026-11-02 (b)).

Pattern: new-case: methods-only (never a delivery) builder variant; gate bypass recorded, row marked, table marked.
"""
from __future__ import annotations

import json
import types

import pytest

from tests.methods.test_ground_terrain import ground_cli, ground_rb, plane
from tests.methods.test_methods_catalog import TOOLS, _load, last_row, rmd, rv

mo = _load("methods_ground_builder_mo", TOOLS / "ground" / "builder_methods_only.py")


def fake_builder(gates: dict, *, rc_when_failed=1, call_gates=True):
    """Stand-in for jobs/VATUTINO-SITE/build_ground.py: main() calls the module-global acceptance_gates, writes the
    masters only when nothing failed (fail closed), always writes ground_report.json."""
    mod = types.ModuleType("fake_build_ground")

    def acceptance_gates(rep, exceptions=None):
        return json.loads(json.dumps(gates))

    def main(argv):
        from pathlib import Path

        out = Path(argv[argv.index("--out") + 1])
        out.mkdir(parents=True, exist_ok=True)
        g = mod.acceptance_gates({}, None) if call_gates else {}
        failed = [k for k, v in g.items() if not v["pass"]]
        if not failed:
            (out / "ground_master_vpm.json").write_text("{}", encoding="utf-8")
        (out / "ground_report.json").write_text(json.dumps({"gates": g, "seconds": 1.0}), encoding="utf-8")
        return rc_when_failed if failed else 0

    mod.acceptance_gates, mod.main = acceptance_gates, main
    return mod


GATES = {"normal_gap_max_20mm": {"pass": False, "value": 0.031}, "density_vpm": {"pass": False, "value": 3},
         "coverage": {"pass": True, "value": 1.0}}


def test_methods_only_writes_the_mesh_and_restores_the_real_gates(tmp_path):
    out = tmp_path / "b"
    assert mo.run(fake_builder(GATES), ["in.json", "--out", str(out)]) == 0
    assert (out / "ground_master_vpm.json").is_file()
    rep = json.loads((out / "ground_report.json").read_text(encoding="utf-8"))
    assert rep["gates"] == GATES  # the report keeps the real verdicts, never the forced passes
    assert rep["methods_only"] == {"delivery": False, "gates_skipped": True,
                                   "failed_gates": ["density_vpm", "normal_gap_max_20mm"],
                                   "decision": mo.DECISION}


def test_methods_only_on_a_passing_build_lists_no_failed_gate(tmp_path):
    ok = {"coverage": {"pass": True}}
    assert mo.run(fake_builder(ok), ["in.json", "--out", str(tmp_path / "b")]) == 0
    rep = json.loads((tmp_path / "b" / "ground_report.json").read_text(encoding="utf-8"))
    assert rep["methods_only"]["failed_gates"] == [] and rep["methods_only"]["delivery"] is False


def test_methods_only_fails_closed_when_the_gates_never_ran(tmp_path):
    assert mo.run(fake_builder(GATES, call_gates=False), ["in.json", "--out", str(tmp_path / "b")]) == 1
    rep = json.loads((tmp_path / "b" / "ground_report.json").read_text(encoding="utf-8"))
    assert "methods_only" not in rep


def test_methods_only_patch_is_undone_after_the_run(tmp_path):
    mod = fake_builder(GATES)
    orig = mod.acceptance_gates
    mo.run(mod, ["in.json", "--out", str(tmp_path / "b")])
    assert mod.acceptance_gates is orig


def test_methods_only_propagates_a_refusal_of_the_builder(tmp_path):
    mod = fake_builder(GATES)
    mod.main = lambda argv: 2  # build_ground.py refused before any write
    assert mo.run(mod, ["in.json", "--out", str(tmp_path / "b")]) == 2
    assert not (tmp_path / "b").exists()


def test_variant_driver_knows_the_methods_only_builder():
    drv = _load("methods_ground_build_mo", TOOLS / "ground" / "build_variant.py")
    assert "builder-methods-only" in drv.VARIANTS


MO = {"delivery": False, "gates_skipped": True, "failed_gates": ["normal_gap_max_20mm"], "decision": "x"}


def _cli(tmp_path, variant, methods_only):
    rep = {"ok": True, "wall_time_s": 2.5, "input": {"kind": "adapter-v4"}}
    if methods_only is not None:
        rep["methods_only"] = methods_only
    args = ground_cli(tmp_path, ground_rb(*plane()), report=rep)
    args[args.index("--variant") + 1] = variant
    return args


def test_run_variant_copies_the_methods_only_block_and_results_md_marks_it(tmp_path):
    assert rv.main(_cli(tmp_path, "builder-methods-only-2m", MO)) == 0
    row = last_row(tmp_path / "results.jsonl")
    assert row["methods_only"] == MO
    md = rmd.render(rmd.read_rows(tmp_path / "results.jsonl"), "ground-terrain")
    assert "builder-methods-only-2m [METHODS-ONLY, not a delivery]" in md
    assert "- R1: Ground gate skipped, failed gates: normal_gap_max_20mm" in md


@pytest.mark.parametrize("variant,block", [
    ("builder-methods-only-2m", {**MO, "delivery": True}),
    ("builder-methods-only-2m", {**MO, "delivery": None}),
    ("builder-methods-only-2m", {**MO, "gates_skipped": False}),
    ("builder-methods-only-2m", {**MO, "failed_gates": "normal_gap_max_20mm"}),
    ("builder-methods-only-2m", {**MO, "failed_gates": [""]}),
    ("builder-methods-only-2m", {**MO, "failed_gates": [1]}),
    ("builder-methods-only-2m", {**MO, "failed_gates": ["a", "a"]}),
    ("builder-methods-only-2m", ["not", "a", "dict"]),
    ("builder-methods-only-2m", None),  # methods-only name without the block
    ("builder-2m", MO),  # block without the methods-only name: the table would hide it
])
def test_run_variant_refuses_a_bad_or_hidden_methods_only_block(tmp_path, variant, block):
    assert rv.main(_cli(tmp_path, variant, block)) == 4
    assert not (tmp_path / "results.jsonl").exists()


def test_results_md_refuses_a_methods_only_row_claiming_delivery():
    row = {"row": "R1", "benchmark": "b", "variant": "builder-methods-only-2m", "methods_only": {**MO, "delivery": True}}
    with pytest.raises(ValueError, match="delivery"):
        rmd.render([row], "ground-terrain")
