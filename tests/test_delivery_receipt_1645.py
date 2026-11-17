"""new-case: delivered ZIP/Max byte identity through existing delivery writers (#1645)."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_review_publish import FakeAdapter, _publish, review  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from adapters.max.agr_tools import package_core as pc
from adapters.max.agr_tools.export_meta import record_export


def cli(*args):
    return subprocess.run([sys.executable, '-m', 'dt_ai.cli.agr', *map(str, args)],
                          cwd=ROOT, capture_output=True, encoding='utf-8')


def assert_receipt(report, target):
    expected = {'file': target.name, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                'size': target.stat().st_size}
    assert report['delivered'] == expected
    line = f'delivered: {target.name} sha256={expected["sha256"]} size={expected["size"]}'
    assert report['summary_ru'].splitlines().count(line) == 1


def test_npm_cli_records_final_zip(tmp_path):
    pkg = tmp_path / 'fbx'
    pkg.mkdir()
    for part in ('01', 'Ground'):
        fbx = pkg / f'0000_Synthetic_{part}.fbx'
        fbx.write_bytes(b'synthetic ' + part.encode())
        record_export(fbx, source='synthetic fixture', top=3.5)
    run = cli('package-npm', pkg)
    assert run.returncode == 0, run.stderr
    report = json.loads((tmp_path / 'package_report.json').read_text(encoding='utf-8'))
    assert_receipt(report, tmp_path / '0000_Synthetic.zip')
