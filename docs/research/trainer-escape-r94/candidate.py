"""Experimental E94 path extraction; never executes the input command."""
import re

import audit

HARNESS = 'C:/x/t_e4cd663a/trainer/.venv/Scripts/python.exe'
WRAPPER = re.compile(
    rf'''^(?:"[^"\r\n]*/powershell\.exe"|powershell\.exe)[ \t]+-Command[ \t]+["']'''
    rf'''(?P<exe>{re.escape(HARNESS)})[ \t]+-c(?=[ \t])''',
    re.IGNORECASE,
)
# Capture the E93 implementation before the paired runner selects an arm.
BASE_PATHS = audit.paths


def candidate_paths(cmd, wt):
    paths = BASE_PATHS(cmd, wt)
    text = audit.prepare(cmd)
    wrapper = WRAPPER.match(text)
    if wrapper:
        # E93 lists absolute drive matches first, in source order. Do not
        # rewrite the input or suppress paths later in the same script.
        index = sum(m.start() < wrapper.start('exe') for m in audit.DRIVE.finditer(text))
        paths[index] = audit.norm(wrapper.group('exe'))
    return paths
