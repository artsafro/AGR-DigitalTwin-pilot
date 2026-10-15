import pytest
from dt_ai.cli.main import parser


def _extract_from_source_entry(help_text: str) -> str:
    lines = help_text.splitlines()
    entry: list[str] = []
    indent: int | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if entry:
                break
            continue
        curr_indent = len(line) - len(line.lstrip())
        if indent is None:
            if stripped.split(None, 1)[0] in ("from-source", "from-source:"):
                indent = curr_indent
                entry.append(stripped)
        else:
            if curr_indent > indent:
                entry.append(stripped)
            else:
                break
    return " ".join(entry)


@pytest.mark.parametrize("args", [["--help"], ["from-source", "--help"]])
def test_from_source_help_warns_experimental(capsys, args):
    p = parser()
    with pytest.raises(SystemExit) as exc_info:
        p.parse_args(args)
    assert exc_info.value.code == 0

    out = capsys.readouterr().out
    target_text = _extract_from_source_entry(out) if args == ["--help"] else out
    assert target_text, "from-source entry not found in top-level help"

    normalized = " ".join(target_text.lower().split())
    assert "experimental" in normalized
    assert "not for production" in normalized
