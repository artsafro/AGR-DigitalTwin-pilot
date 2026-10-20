"""Non-Blender CLI contracts using synthetic inputs in temporary folders."""

import itertools
import json

import pytest
from pypdf import PdfWriter

from dt_ai.cli.main import main


@pytest.fixture
def inputs(tmp_path, job):
    """Copy the labelled synthetic job; never write to repository fixtures."""
    documents = {
        "manifest": job.model_dump(),
        "current": job.registry.model_dump(),
        "proposal": job.registry.model_dump(),
        "object": {"id": "SyntheticCLI", "levels": []},
        "dump": {},
        "modules": {},
    }
    paths = {}
    for name, document in documents.items():
        paths[name] = tmp_path / f"{name}.json"
        paths[name].write_text(json.dumps(document), encoding="utf-8")
    paths["source"] = tmp_path / "synthetic.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(paths["source"])
    paths["output"] = tmp_path / "output"
    return paths


REQUIRED_FLAGS = {
    "inspect": ("manifest",),
    "registry": ("current", "proposal", "output"),
    "index-pdf": ("source", "output"),
    "from-source": ("dump", "modules", "object", "output"),
}


def arguments(command, paths):
    argv = [command, "merge"] if command == "registry" else [command]
    for flag in REQUIRED_FLAGS[command]:
        if flag in paths:
            argv.extend([f"--{flag}", str(paths[flag])])
    return argv


def test_inspect_dispatch(inputs, job, capsys):
    original = inputs["manifest"].read_bytes()
    assert main(arguments("inspect", inputs)) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "project_id": job.project.project_id,
        "synthetic": True,
        "materials": len(job.registry.materials),
        "surfaces": len(job.master.surfaces),
    }
    assert inputs["manifest"].read_bytes() == original


def test_registry_dispatch(inputs, job, capsys):
    assert main(arguments("registry", inputs)) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "Merged; 0 conflicts preserved separately"
    assert captured.err == ""
    assert json.loads(inputs["output"].read_text(encoding="utf-8")) == job.registry.model_dump()
    conflicts = inputs["output"].with_suffix(".conflicts.json")
    assert json.loads(conflicts.read_text(encoding="utf-8")) == []


def test_index_pdf_dispatch(inputs, capsys):
    assert main(arguments("index-pdf", inputs)) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == f"Indexed 1 pages: {inputs['output'] / 'index.json'}"
    assert captured.err == ""
    index = json.loads((inputs["output"] / "index.json").read_text(encoding="utf-8"))
    assert index["source_file"] == "synthetic.pdf"
    assert [page["page"] for page in index["pages"]] == [1]
    assert (inputs["output"] / "page-001.txt").read_text(encoding="utf-8") == ""


INPUT_PATHS = [
    ("inspect", "manifest"),
    ("registry", "current"),
    ("registry", "proposal"),
    ("index-pdf", "source"),
    ("from-source", "object"),
    ("from-source", "dump"),
    ("from-source", "modules"),
]


@pytest.mark.parametrize("command,flag", INPUT_PATHS)
@pytest.mark.parametrize("kind", ["missing", "directory"])
def test_input_path_errors(command, flag, kind, inputs, capsys):
    path = inputs[flag]
    path.unlink()
    if kind == "directory":
        path.mkdir()
    assert main(arguments(command, inputs)) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ERROR:" in captured.err
    assert path.name in captured.err
    assert not inputs["output"].exists()


@pytest.mark.parametrize(
    "command,flag,content,error",
    [
        (command, flag, "{", "Expecting property name")
        for command, flag in INPUT_PATHS if flag != "source"
    ] + [
        (command, flag, content, error)
        for command, flag in INPUT_PATHS if flag != "source"
        for content, error in [
            ("", "Expecting value"),
            ('{"partial":', "Expecting value"),
            ("NaN", "Nonfinite value: NaN"),
            ("Infinity", "Nonfinite value: Infinity"),
            ("-Infinity", "Nonfinite value: -Infinity"),
            ('{"duplicate": 1, "duplicate": 2}', "Duplicate key: duplicate"),
        ]
    ] + [
        (command, flag, content, "validation error")
        for command, flag in INPUT_PATHS if command in ("inspect", "registry")
        for content in ("{}", "null", "[]", '"unsupported"')
    ],
)
def test_invalid_json_inputs(command, flag, content, error, inputs, capsys):
    inputs[flag].write_text(content, encoding="utf-8")
    assert main(arguments(command, inputs)) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ERROR:" in captured.err
    assert error in captured.err
    assert not inputs["output"].exists()


def test_from_source_existing_output_is_rejected(inputs, capsys):
    inputs["output"].mkdir()
    sentinel = inputs["output"] / "keep.txt"
    sentinel.write_text("synthetic existing run", encoding="utf-8")
    assert main(arguments("from-source", inputs)) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "exists; write a new versioned run" in captured.err
    assert list(inputs["output"].iterdir()) == [sentinel]
    assert sentinel.read_text(encoding="utf-8") == "synthetic existing run"


# Exhaust every nonempty subset of required arguments for the scoped commands.
MISSING_FLAGS = [
    (command, missing)
    for command, flags in REQUIRED_FLAGS.items()
    for size in range(1, len(flags) + 1)
    for missing in itertools.combinations(flags, size)
]


@pytest.mark.parametrize("command,missing", MISSING_FLAGS)
def test_required_arguments(command, missing, inputs, capsys):
    paths = {key: value for key, value in inputs.items() if key not in missing}
    with pytest.raises(SystemExit) as exc:
        main(arguments(command, paths))
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "the following arguments are required" in captured.err
    for flag in missing:
        assert f"--{flag}" in captured.err
    assert not inputs["output"].exists()


@pytest.mark.parametrize("command", ["synthetic-unknown-command", "INSPECT", "registry-merge", "inspect-extra"])
def test_unknown_subcommand(command, capsys):
    with pytest.raises(SystemExit) as exc:
        main([command])
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert f"invalid choice: '{command}'" in captured.err


@pytest.mark.parametrize(
    "command,flag",
    [(command, flag) for command, flags in REQUIRED_FLAGS.items() for flag in flags],
)
def test_required_flag_without_value(command, flag, inputs, capsys):
    argv = arguments(command, inputs)
    del argv[argv.index(f"--{flag}") + 1]
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert f"argument --{flag}: expected one argument" in captured.err
    assert not inputs["output"].exists()


@pytest.mark.parametrize("command", REQUIRED_FLAGS)
def test_unsupported_option(command, inputs, capsys):
    with pytest.raises(SystemExit) as exc:
        main(arguments(command, inputs) + ["--synthetic-unsupported"])
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "unrecognized arguments: --synthetic-unsupported" in captured.err
    assert not inputs["output"].exists()


def test_empty_command(capsys):
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "the following arguments are required: command" in captured.err
