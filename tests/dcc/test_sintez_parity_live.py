"""new-case: opt-in real SINTEZ / twinqa comparison on synthetic ZIPs (#432)."""
import os
from pathlib import Path

import pytest
from tools.sintez_parity import fixtures

pytestmark = pytest.mark.dcc


@pytest.mark.parametrize("case", fixtures(), ids=lambda c: c["id"])
def test_live_parity(case, tmp_path):
    from tools.sintez_parity import run_live
    blender = os.environ.get("DT_BLENDER")
    if not blender:
        pytest.skip("set DT_BLENDER explicitly to Blender 5.1.2")
    result = run_live(case, tmp_path / case["id"], blender)
    assert result["vendor"]["status"] in ("pass", "review", "fail")
    assert result["req_num"] == case["req_num"]
    # Any disagreement remains an explicit failed assertion, never an xfail/pass.
    assert result["agreement"], result
