"""new-case: read-only Octopus installation checker CLI regression seam."""

import json
from pathlib import Path
import subprocess
import sys

CHECKER = Path(__file__).resolve().parents[1] / "tools/max/viz/check_octopus_buttons.py"
FIXTURE = Path(__file__).parent / "fixtures/octopus/inactive_clone.octopus"
LABEL = "MultiSub Dedupe"


def run_check(menu, *args):
    return subprocess.run(
        [sys.executable, str(CHECKER), str(menu), LABEL, *args],
        capture_output=True, text=True, encoding="utf-8",
    )


def test_inactive_clone_then_active(tmp_path):
    script = tmp_path / "material tools.ms"
    script.write_text("-- synthetic script, never executed", encoding="utf-8")
    menu = tmp_path / "myscripts.octopus"
    inactive = FIXTURE.read_text(encoding="utf-8").replace("SCRIPT_PATH", script.as_posix())
    menu.write_text(inactive, encoding="utf-8")
    result = run_check(menu)
    assert result.returncode == 1, result.stderr
    row = json.loads(result.stdout)["buttons"][0]
    assert row["found"] is True
    assert row["active"] == "false"
    assert row["command_nonempty"] is True
    assert row["filein_paths"] == [script.as_posix()]
    assert row["filein_paths_exist"] is True
    assert row["passed"] is False
    menu.write_text(inactive.replace('active="false"', 'active="true"', 1), encoding="utf-8")
    result = run_check(menu)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["buttons"][0]["passed"] is True
