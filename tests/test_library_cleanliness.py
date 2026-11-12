"""new-case: unified library cleanliness contracts, independent of delivery certification."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / 'tools/library/check_library.py'


def test_empty_catalogue_fails_closed(tmp_path):
    path = tmp_path / 'catalogue.json'
    path.write_text(json.dumps({'schema': 'agr-library/1', 'library': 'windows', 'assets': []}))
    result = subprocess.run([sys.executable, str(CHECKER), str(path), '--root', str(tmp_path)],
                            capture_output=True, text=True)
    assert result.returncode == 1, result.stderr
    assert 'assets' in result.stdout


def checker():
    spec = importlib.util.spec_from_file_location('library_checker_test', CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
