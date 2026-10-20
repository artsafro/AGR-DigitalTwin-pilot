"""new-case: lossless 2026 CSV Markdown generation and input-preserving CLI rejection."""
import csv
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/generate_requirements_2026.py"
HEAD = ["Номер", "Пункт требований", "Категория", "Наименование краткое (новая редакция)", "Описание (новая редакция)"]


def sources(tmp_path):
    for side in ("lp", "hp"):
        columns = HEAD + (["Авто", "Сравнение с новой редакцией"] if side == "lp" else ["Автоматизировано", "Наименование краткое (старая редакция)"])
        with (tmp_path / f"{side}_requirements_2026.csv").open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(columns)
            writer.writerow(["1", "2.1.1", "Format", "ZIP | scope", "Full text\nsecond line", "1", "изм" if side == "lp" else "Old ZIP"])
    return tmp_path


def run(source, output, *args):
    return subprocess.run([sys.executable, str(SCRIPT), "--source-dir", str(source), "--output", str(output), *args], capture_output=True, text=True, encoding="utf-8")


def test_cli_preserves_full_rows_and_changed_markers(tmp_path):
    output = tmp_path / "requirements.md"
    result = run(sources(tmp_path), output)
    assert result.returncode == 0, result.stderr
    text = output.read_text(encoding="utf-8")
    assert text.count("| 2.1.1 |") == 2
    assert "ZIP &#124; scope" in text and "Full text<br>second line" in text
    assert text.count("| 1 | changed |") == 2
    assert "LP: 1 rows, 1 changed" in result.stdout
    assert "HP: 1 rows, 1 changed" in result.stdout
    assert run(tmp_path, output, "--check").returncode == 0
