"""Import-order probes run in fresh interpreters, never conftest's module cache."""
import itertools
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULES = ("dt_ai.parts.model", "dt_ai.core.models")


def run_fresh(code):
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("order", list(itertools.permutations(MODULES)))
def test_parts_import_order(order):
    run_fresh(f"""
import importlib
import hashlib
import json
import typing
for name in {order!r}:
    importlib.import_module(name)
from dt_ai.core import models
from dt_ai.parts import model as parts
assert models.SCHEMAS['PartsList'] is parts.PartsList
assert models.Approval is parts.Approval
assert models.SourceRef is parts.SourceRef
assert models.Name is parts.Name
assert parts.PartsList.model_fields['sources'].annotation == list[models.SourceRef]
assert models.Approval in typing.get_args(parts.PartsList.model_fields['gate1'].annotation)
assert set(models.SCHEMAS) == {{
    'AdapterReport', 'BuildJob', 'IntakeSources', 'IntakeSpecDraft',
    'MasterBuilding', 'MaterialRegistry', 'PartsList', 'Placement',
    'ProjectManifest', 'Spec', 'ValidationReport', 'WindowType',
}}
schemas = {{k: v.model_json_schema() for k, v in models.SCHEMAS.items()}}
# Strict snapshot includes #138 decision-ID annotations in three Spec descriptions;
# provenance extraction and import order must preserve those annotations too; RoofStructure.thickness_m (#91).
# IntakeSources also includes the source-specific opening-waiver question (#650).
# Approval.ref (#1205), SourceRef.kind drawing/sheet (#1206), PartsList D tier,
# allocated-budget description and Approval.parts_sha256 (#1309); optional parts-local
# finish_sheets/finish_refs and their definitions (#1366). Shared SourceRef is unchanged.
assert hashlib.sha256(json.dumps(schemas, sort_keys=True).encode()).hexdigest() == (
    'ec0d1aae220d69a6cd4b8090c2177c24198ea3234a9e0c209df8d7295ed572f8'
)
""")


def test_provenance_is_leaf_and_reexports_are_identical():
    run_fresh("""
import sys
from dt_ai.core import provenance
assert not any(name.startswith(('dt_ai.parts', 'dt_ai.spec', 'dt_ai.intake')) for name in sys.modules)
from dt_ai.core import models
for name in ('Contract', 'SourceRef', 'Approval', 'Finite', 'Hash', 'Name'):
    assert getattr(models, name) is getattr(provenance, name), name
""")
