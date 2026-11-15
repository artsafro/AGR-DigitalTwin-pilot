"""new-case: shared course-grid command; synthetic fixtures, no DCC acceptance."""
import json
import subprocess
import sys


def test_brick_seams_help_is_real_shared_command():
    result = subprocess.run([sys.executable, '-m', 'dt_ai.cli.agr', 'brick-seams', '--help'],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert '--config' in result.stdout
    assert '--out' in result.stdout
