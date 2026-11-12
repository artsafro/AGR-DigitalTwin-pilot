"""new-case: read-only Octopus installation checker CLI regression seam."""

import json
from pathlib import Path
import subprocess
import sys
from xml.sax.saxutils import escape

import pytest


def write_menu(tmp_path, command, *, active="true", extra=""):
    menu = tmp_path / "myscripts.octopus"
    menu.write_text(
        '<OctopusDataWrapper><ButtonDataList><LocalButtonDataList '
        'IsActive="true" ButtonText="MultiSub Dedupe"><buttonActionData>'
        f'<actionDataList active="{active}"><command>{escape(command)}</command>'
        f'</actionDataList>{extra}</buttonActionData></LocalButtonDataList>'
        '</ButtonDataList></OctopusDataWrapper>', encoding="utf-8",
    )
    return menu


@pytest.mark.parametrize("command", [
    '', '  ', '-- comment only', '/* comment only */',
    'fileIn variable', 'fileIn ("a.ms" + "b.ms")', 'fileIn ""',
    'fileIn @"missing.ms"', 'fileIn "NaN"', 'fileIn "inf"',
    'fileIn @"SCRIPT_PATH"; fileIn unknown',
    'fileIn @"SCRIPT_PATH"; fileIn @"SCRIPT_PATH" + suffix',
    'fileIn @"SCRIPT_PATH"; /* unfinished',
])
def test_fail_closed(tmp_path, command):
    script = tmp_path / "exists.ms"
    script.write_text("-- synthetic", encoding="utf-8")
    menu = write_menu(tmp_path, command.replace("SCRIPT_PATH", script.as_posix()))
    result = run_check(menu)
    assert result.returncode == 1, result.stdout
    assert json.loads(result.stdout)["passed"] is False


def test_getdir(tmp_path):
    script = tmp_path / "script.ms"
    script.write_text("-- synthetic", encoding="utf-8")
    menu = write_menu(tmp_path, 'FiLeIn ((getDir #userStartupScripts) + "/script.ms")')
    assert run_check(menu).returncode == 1
    result = run_check(menu, "--max-dir", f"userStartupScripts={tmp_path}")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["buttons"][0]["filein_paths"] == [script.as_posix()]


def test_every_filein(tmp_path):
    first = tmp_path / "first.ms"
    second = tmp_path / "second.ms"
    first.write_text("-- synthetic", encoding="utf-8")
    menu = write_menu(tmp_path, f'fileIn @"{first.as_posix()}"; fileIn @"{second.as_posix()}"')
    result = run_check(menu)
    row = json.loads(result.stdout)["buttons"][0]
    assert result.returncode == 1
    assert row["filein_paths"] == [first.as_posix(), second.as_posix()]
    assert second.as_posix() in str(row["errors"])
    second.write_text("-- synthetic", encoding="utf-8")
    assert run_check(menu).returncode == 0

@pytest.mark.parametrize("xml", [
    '', '<OctopusDataWrapper>', '<other/>', '<OctopusDataWrapper/>',
    '<OctopusDataWrapper><LocalButtonDataList ButtonText="MultiSub Dedupe" IsActive="true"/></OctopusDataWrapper>',
    '<OctopusDataWrapper><other ButtonText="MultiSub Dedupe" IsActive="true"><buttonActionData><actionDataList active="true"><command>print 1</command></actionDataList></buttonActionData></other></OctopusDataWrapper>',
    '<!DOCTYPE OctopusDataWrapper [<!ENTITY cmd "print 1">]><OctopusDataWrapper><LocalButtonDataList ButtonText="MultiSub Dedupe" IsActive="true"><buttonActionData><actionDataList active="true"><command>&cmd;</command></actionDataList></buttonActionData></LocalButtonDataList></OctopusDataWrapper>',
])
def test_bad_xml(tmp_path, xml):
    menu = tmp_path / "bad.octopus"
    menu.write_text(xml, encoding="utf-8")
    assert run_check(menu).returncode == 1


def test_duplicate_commands(tmp_path):
    menu = write_menu(tmp_path, 'print "one"')
    menu.write_text(menu.read_text().replace('</command>', '</command><command>print 2</command>'), encoding="utf-8")
    assert run_check(menu).returncode == 1


def test_duplicates(tmp_path):
    menu = write_menu(tmp_path, 'print "one"')
    assert run_check(menu, LABEL).returncode == 1
    text = menu.read_text()
    start, end = text.index('<LocalButtonDataList'), text.index('</LocalButtonDataList>') + len('</LocalButtonDataList>')
    menu.write_text(text[:end] + text[start:end] + text[end:], encoding="utf-8")
    assert run_check(menu).returncode == 1


def test_reset(tmp_path):
    script = tmp_path / "exists.ms"
    script.write_text("-- synthetic", encoding="utf-8")
    menu = write_menu(tmp_path, f'fileIn @"{script.as_posix()}"')
    assert run_check(menu).returncode == 0
    script.unlink()
    assert run_check(menu).returncode == 1
    script.write_text("-- changed synthetic", encoding="utf-8")
    assert run_check(menu).returncode == 0


def test_read_only(tmp_path):
    script = tmp_path / "a & b.ms"
    script.write_text("-- synthetic", encoding="utf-8")
    alias = tmp_path / "alias.ms"
    alias.hardlink_to(script)
    sentinel = tmp_path / "myscripts.octopus.partial"
    sentinel.write_text("do not overwrite", encoding="utf-8")
    menu = write_menu(tmp_path, f'fileIn @"{alias.as_posix()}"; fileIn @"{script.as_posix()}"')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert run_check(menu).returncode == 0
    assert run_check(menu, '--output', str(menu)).returncode != 0
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_comments_and_strings_are_not_calls(tmp_path):
    menu = write_menu(tmp_path, 'print "fileIn missing"; /* fileIn unknown */\n-- fileIn "missing.ms"\nprint 1')
    result = run_check(menu)
    assert result.returncode == 0
    assert json.loads(result.stdout)["buttons"][0]["filein_paths"] == []


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
