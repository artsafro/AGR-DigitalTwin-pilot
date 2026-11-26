"""docs/agr/ is opened only through docs/agr/INDEX.md, which lists every document there (#120)."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROW = re.compile(r"^\| `([^`]+)` \|([^|]*[^| ][^|]*)\|([^|]*[^| ][^|]*)\|$")
BATCH_5C = {
    "ADAPTER_EXTRACTION.md", "ADAPTER_REPORT.md", "READINESS_REPORT.md", "traceability.html",
    "inventory/INTEGRATION_PLAN.md", "inventory/README.md", "inventory/applications.json",
    "inventory/autocad-menus.json", "inventory/blender-preferences.json", "inventory/catalog.csv",
    "inventory/catalog.html", "inventory/catalog.json", "inventory/coverage.json",
    "inventory/duplicates.json", "inventory/fbx-runtime.json", "inventory/folder-followup-evidence.json",
    "inventory/geoagr-13.63-evidence.json", "inventory/max-runtime.json", "inventory/mcp-registrations.json",
    "inventory/mse-evidence.json", "inventory/packages.json", "inventory/stage-map.json",
    "research/max-workbench/EXPANSION_2026-09-27.md", "research/max-workbench/expanded-inventory.json",
    "research/max-workbench/inventory.json", "research/max-workbench/scan-summary.txt",
}


def test_batch_5c_entries_are_historical_not_production_guidance():
    index = (ROOT / "docs/agr/INDEX.md").read_text(encoding="utf-8")
    rows = {row[1]: row[3].strip() for line in index.splitlines() if (row := ROW.fullmatch(line))}
    historical = {name for name, guidance in rows.items() if guidance.startswith("Historical reference only:")}
    assert BATCH_5C <= historical, sorted(BATCH_5C - historical)
    # Nearby rows did not come from the batch: don't mark an entire index section.
    assert all(name in rows and name not in historical for name in (
        "README.md", "UV_RULES.md", "inventory/NPM_VPM_MAP.md", "research/max-workbench/REVIEW.md",
    ))


def test_index_lists_every_document_once():
    listed = subprocess.run(["git", "ls-files", "docs/agr"], cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8")
    assert listed.returncode == 0, listed.stderr
    tracked = {p.removeprefix("docs/agr/") for p in listed.stdout.splitlines()} - {"INDEX.md"}
    text = (ROOT / "docs/agr/INDEX.md").read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.startswith("| `")]
    rows = [m.group(1) for line in lines if (m := ROW.match(line))]
    assert len(rows) == len(lines), "a row without its two description cells"
    assert len(rows) == len(set(rows)), "a document is listed twice"
    assert set(rows) == tracked
