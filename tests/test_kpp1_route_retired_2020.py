"""#2020 [D426]: the old KPP1 stage builder build_kpp1.py is retired; the accepted v004 route is lattice-1609."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
import duplicate_guard as guard  # noqa: E402
import mini_yaml  # noqa: E402

BUILD = "jobs/KPP1/scripts/build_kpp1.py"


def test_build_kpp1_has_no_live_entrypoint():
    contexts = mini_yaml.load(ROOT / "docs/architecture/contexts.yaml")
    owners = [e["owner"] for e in contexts.get("entrypoints", [])]
    assert BUILD not in owners
    _, chains = guard.live_chains(ROOT)
    assert BUILD not in chains, chains.get(BUILD)


def test_no_live_kpp1_bypass_rows_or_baseline_keys():
    rows = guard.rows_of(guard.load_maps(ROOT))
    live = [(r.map, r.at) for r in rows if r.rel.startswith("jobs/KPP1/") and r.status == "live-bypass"]
    assert live == []
    build_rows = {r.at: r.status for r in rows if r.rel == BUILD}
    for at in (f"{BUILD}:194", f"{BUILD}:198", f"{BUILD}:327"):
        assert build_rows.get(at) == "historical", (at, build_rows.get(at))
    baseline = guard.LIVE_BYPASS_BASELINE | guard.OWN_DUTY_BASELINE
    assert not [k for k in baseline if k[1].startswith(BUILD)]


def test_bypass_table_has_no_kpp1_row():
    table = guard.bypass_table(guard.rows_of(guard.load_maps(ROOT)))
    assert "jobs/KPP1/" not in table


def test_accepted_lattice_route_is_the_configured_kpp1_body():
    cfg = json.loads((ROOT / "jobs/KPP1/lattice-1609/skeleton.json").read_text(encoding="utf-8"))
    assert cfg["scenario"] == "oks-npm"
    assert {"script": "hooks/kpp1_lattice.py", "stage": "body", "point": "before"} in cfg["hooks"]
