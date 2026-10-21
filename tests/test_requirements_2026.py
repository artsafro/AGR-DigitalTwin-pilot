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


def test_vendor_empty_title_and_description_are_preserved(tmp_path):
    sources(tmp_path)
    path = tmp_path / "lp_requirements_2026.csv"
    rows = list(csv.reader(path.open(encoding="utf-8-sig", newline=""), delimiter=";"))
    rows[1][3:5] = ["", ""]
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, delimiter=";").writerows(rows)
    output = tmp_path / "out.md"
    result = run(tmp_path, output)
    assert result.returncode == 0, result.stderr
    assert "| 2.1.1 |  |  | 1 | changed |" in output.read_text(encoding="utf-8")


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


@pytest.mark.parametrize("mode", ["empty", "partial", "extra", "duplicate", "flag", "columns"])
def test_bad_csv_fails_without_writing(tmp_path, mode):
    sources(tmp_path)
    path = tmp_path / "lp_requirements_2026.csv"
    rows = list(csv.reader(path.open(encoding="utf-8-sig", newline=""), delimiter=";"))
    if mode == "empty": rows = rows[:1]
    elif mode == "partial": rows[1] = rows[1][:-1]
    elif mode == "extra": rows[1].append("unexpected")
    elif mode == "duplicate": rows.append(rows[1])
    elif mode == "flag": rows[1][-2] = "NaN"
    elif mode == "columns": rows[0][-1] = rows[0][-2]
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, delimiter=";").writerows(rows)
    output = tmp_path / "out.md"
    assert run(tmp_path, output).returncode != 0
    assert not output.exists()


@pytest.mark.parametrize("alias", ["direct", "relative", "hardlink"])
def test_output_cannot_overwrite_source_alias(tmp_path, alias):
    sources(tmp_path)
    source = tmp_path / "lp_requirements_2026.csv"
    before = source.read_bytes()
    output = source
    if alias == "relative": output = tmp_path / "." / source.name
    if alias == "hardlink":
        output = tmp_path / "alias.md"
        output.hardlink_to(source)
    assert run(tmp_path, output).returncode != 0
    assert source.read_bytes() == before


def test_stale_output_check_and_predictable_partial_are_safe(tmp_path):
    sources(tmp_path)
    output = tmp_path / "out.md"
    partial = tmp_path / "out.md.partial"
    partial.write_text("protected", encoding="utf-8")
    assert run(tmp_path, output).returncode == 0
    source = tmp_path / "hp_requirements_2026.csv"
    source.write_bytes(source.read_bytes().replace(b"Full text", b"Changed text"))
    before = output.read_bytes()
    assert run(tmp_path, output, "--check").returncode != 0
    assert output.read_bytes() == before
    assert run(tmp_path, output).returncode == 0
    assert b"Changed text" in output.read_bytes()
    assert partial.read_text() == "protected"


def test_changed_input_during_generation_is_rejected(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("requirements_generator", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sources(tmp_path)
    original = module.read_rows
    def rewrite(data, side):
        rows = original(data, side)
        if side == "hp":
            source = tmp_path / "lp_requirements_2026.csv"
            source.write_bytes(source.read_bytes() + b"\n")
        return rows
    monkeypatch.setattr(module, "read_rows", rewrite)
    output = tmp_path / "out.md"
    with pytest.raises(ValueError, match="source changed"):
        module.generate(tmp_path, output)
    assert not output.exists()
    assert not list(tmp_path.glob("*.partial"))
