"""Task-local substitution and unchanged pytest inventory capture."""
import json
import os
from pathlib import Path
from candidate import install

NODES = []
OUTCOMES = []


def pytest_configure(config):
    install(os.environ['HYP359_MODE'])


def pytest_collection_modifyitems(items):
    NODES.extend(item.nodeid for item in items)


def pytest_runtest_logreport(report):
    if report.when == 'call' or report.failed or report.skipped:
        OUTCOMES.append([report.nodeid, report.when, report.outcome])


def pytest_sessionfinish(session, exitstatus):
    Path(os.environ['HYP359_REPORT']).write_text(json.dumps({
        'nodes': NODES, 'outcomes': OUTCOMES, 'exitstatus': int(exitstatus),
    }, indent=2) + '\n', encoding='utf-8')
