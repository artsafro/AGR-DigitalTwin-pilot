"""#1359: event storm + context map generator (drift / existence) and the jobs/ duplicate guard."""
import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
import duplicate_guard as guard  # noqa: E402
import mini_yaml  # noqa: E402
import route_map  # noqa: E402

YAMLS = [ROOT / route_map.EVENTS, ROOT / route_map.CONTEXTS]


# ---------------------------------------------------------------- generator: drift, references, labels
def test_committed_files_equal_generator_output():
    _, _, files = route_map.render(ROOT)
    assert len(files) == 4
    for rel, text in files.items():
        assert (ROOT / rel).read_bytes() == text.encode("utf-8"), f"{rel} drifted; rerun route_map.py"


def test_generator_is_deterministic_and_ids_unique():
    a = route_map.render(ROOT)[2]
    b = route_map.render(ROOT)[2]
    assert a == b
    for rel, text in a.items():
        if rel.suffix == ".excalidraw":
            ids = [e["id"] for e in json.loads(text)["elements"]]
            assert len(ids) == len(set(ids))


def test_every_named_command_d_row_path_and_function_exists():
    events, contexts, _ = route_map.render(ROOT)
    assert route_map.verify_references(ROOT, events, contexts) == []


def test_check_cli_passes_on_repo(capsys):
    assert route_map.main(["--check"]) == 0


def test_every_drawn_label_is_russian():
    for rel in ("npm-oks-route.excalidraw", "contexts.excalidraw"):
        doc = json.loads((ROOT / "docs/architecture" / rel).read_text(encoding="utf-8"))
        texts = [e["text"] for e in doc["elements"] if e["type"] == "text"]
        assert texts
        bad = [t for t in texts if not route_map.CYRILLIC.search(t)]
        assert bad == [], f"{rel}: labels without Russian text: {bad}"


def test_route_covers_the_issue_stages_and_hotspots():
    events = mini_yaml.load(ROOT / route_map.EVENTS)
    assert [s["id"] for s in events["stages"]] == [
        "sources", "parts", "gate1", "model", "uv", "export", "readback", "validate", "sintez", "delivered"]
    assert {"agent", "artem", "checker"} == {a["id"] for a in events["actors"]}
    assert {"parapet-roof-seam", "windows", "udim", "package"} <= {h["id"] for h in events["hotspots"]}
    contexts = mini_yaml.load(ROOT / route_map.CONTEXTS)
    assert len(contexts["contexts"]) == 5


@pytest.mark.parametrize("command,ok", [
    ("agr inspect", True), ("agr validate", True), ("agr vpm-to-npm", True), ("agr package-vpm", True),
    ("dt derive atlas", True), ("dt qa xview", True), ("dt spec compare", True), ("dt inspect", True),
    ("agr unwrap-atlas", False), ("agr ucx", False), ("agr", False), ("dt derive nonsense", False),
    ("dt nonsense", False), ("python tools/x.py", False), ("dt qa xview extra", False), ("", False),
])
def test_command_exists(command, ok):
    assert route_map.command_exists(command) is ok


def _loaded():
    return mini_yaml.load(YAMLS[0]), mini_yaml.load(YAMLS[1])


@pytest.mark.parametrize("mutate,needle", [
    (lambda e, c: e["stages"][0]["commands"].append("agr brick-seams"), "agr brick-seams"),
    (lambda e, c: e["stages"][0]["rules"].append("D999"), "D999"),
    (lambda e, c: e["stages"][0]["rules"].append("D24"), "D24 "),
    (lambda e, c: e["hotspots"][0]["evidence"].append("jobs/KPP1/nope.md"), "jobs/KPP1/nope.md"),
    (lambda e, c: c["contexts"][0]["functions"].append({"name": "no_such_fn", "contract": "х"}), "no_such_fn"),
    (lambda e, c: c["contexts"][0].update(owner="src/dt_ai/ops/nope.py"), "nope.py"),
    (lambda e, c: c["contexts"][0]["duplicates"][0].update(at="jobs/KPP1/scripts/seal.py:1"), "does not contain"),
    (lambda e, c: c["contexts"][0]["duplicates"][0].update(at="jobs/KPP1/scripts/seal.py:99999"), "past the end"),
    (lambda e, c: c["contexts"][0]["duplicates"][0].update(at="jobs/KPP1/scripts/gone.py:3"), "does not exist"),
    (lambda e, c: c["contexts"][0]["duplicates"][0].update(at="src/dt_ai/ops/operations.py:44",
                                                           match="def run_operation("), "owner itself"),
])
def test_unknown_reference_is_reported(mutate, needle):
    events, contexts = _loaded()
    mutate(events, contexts)
    problems = route_map.verify_references(ROOT, events, contexts)
    assert any(needle in p for p in problems), problems


@pytest.mark.parametrize("mutate,needle", [
    (lambda e, c: e["stages"][0].update(event_ru="Sources received"), "no Russian"),
    (lambda e, c: e["stages"][0].update(actor="robot"), "unknown actor"),
    (lambda e, c: e["stages"][0].update(context="nowhere"), "unknown context"),
    (lambda e, c: e["stages"][1].update(id="sources"), "duplicate stage"),
    (lambda e, c: e["hotspots"][0].update(stage="nowhere"), "unknown stage"),
    (lambda e, c: e["stages"][0].pop("rules"), "'rules'"),
    (lambda e, c: e["stages"][0].update(commands=[]), "'commands'"),
    (lambda e, c: c["relations"][0].update(to="nowhere"), "unknown context"),
    (lambda e, c: c["contexts"][0]["duplicates"][0].update(at="jobs/x.py"), "path.py:line"),
    (lambda e, c: c["contexts"][0]["duplicates"][0].update(issue="1359"), "#<number>"),
    (lambda e, c: c["contexts"][0]["duplicates"][0].pop("ru"), "'ru'"),
    (lambda e, c: c["shared_kernel"]["duplicates"][0].update(rule="nope"), "unknown rule"),
    (lambda e, c: c["contexts"][1].update(id="body"), "duplicate context"),
])
def test_schema_errors_name_the_key(mutate, needle):
    events, contexts = _loaded()
    mutate(events, contexts)
    with pytest.raises(route_map.SchemaError, match=needle.replace("(", r"\(").replace("'", "'")):
        route_map.check_schema(events, contexts)


def _tmp_arch(tmp_path):
    shutil.copytree(ROOT / "docs/architecture", tmp_path / "docs/architecture")
    shutil.copy2(ROOT / "docs/decisions.md", tmp_path / "docs/decisions.md")
    return tmp_path


def test_check_without_decisions_is_an_error_not_a_pass(tmp_path):
    root = _tmp_arch(tmp_path)
    (root / "docs/decisions.md").unlink()
    assert route_map.main(["--root", str(root), "--check"]) == 2


def test_check_detects_hand_edited_drift(tmp_path, capsys):
    root = _tmp_arch(tmp_path)
    target = root / "docs/architecture/contexts.excalidraw"
    target.write_bytes(target.read_bytes().replace("Корпус".encode(), "Кopпус".encode(), 1))
    assert route_map.main(["--root", str(root), "--check"]) == 1
    assert "drift: docs/architecture/contexts.excalidraw" in capsys.readouterr().out


def test_check_detects_missing_output(tmp_path, capsys):
    root = _tmp_arch(tmp_path)
    (root / "docs/architecture/npm-oks-route.svg").unlink()
    assert route_map.main(["--root", str(root), "--check"]) == 1
    assert "drift: docs/architecture/npm-oks-route.svg" in capsys.readouterr().out


def test_write_mode_is_idempotent_and_leaves_no_partial(tmp_path):
    root = _tmp_arch(tmp_path)
    before = {p.name: p.read_bytes() for p in (root / "docs/architecture").iterdir()}
    assert route_map.main(["--root", str(root)]) == 0
    after = {p.name: p.read_bytes() for p in (root / "docs/architecture").iterdir()}
    assert before == after


def test_output_that_is_an_input_is_refused(tmp_path, monkeypatch):
    root = _tmp_arch(tmp_path)
    alias = root / "docs/architecture/contexts.svg"
    alias.write_bytes((root / route_map.CONTEXTS).read_bytes())
    before = alias.read_bytes()
    monkeypatch.setattr(route_map, "CONTEXTS", Path("docs/architecture/contexts.svg"))
    assert route_map.main(["--root", str(root)]) == 2
    assert alias.read_bytes() == before
    assert not list((root / "docs/architecture").glob("*.partial"))


def test_malformed_yaml_exits_2_and_writes_nothing(tmp_path):
    root = _tmp_arch(tmp_path)
    (root / route_map.EVENTS).write_text("stages: [a, b]\n", encoding="utf-8")
    before = (root / "docs/architecture/npm-oks-route.excalidraw").read_bytes()
    assert route_map.main(["--root", str(root)]) == 2
    assert (root / "docs/architecture/npm-oks-route.excalidraw").read_bytes() == before


# ---------------------------------------------------------------- mini_yaml
@pytest.mark.parametrize("path", YAMLS, ids=lambda p: p.name)
def test_mini_yaml_matches_pyyaml_on_the_sources(path):
    text = path.read_text(encoding="utf-8")
    assert mini_yaml.loads(text) == yaml.safe_load(text)


@pytest.mark.parametrize("text", [
    "", "# only a comment\n", "a: [1, 2]\n", "a: {b: 1}\n", "a: yes\n", "a: null\n", "a: 1.5\n", "a: .inf\n",
    "a: x # comment\n", "a: 1\na: 2\n", "a:\tb\n", "a: &x 1\n", "a: |\n  t\n", "a:\n", "- a\nb: 1\n",
    "a: 'x'\n", "a: b: c\n", "a: \"open\n", "---\na: 1\n", "a:\n  - x\n   - y\n", "a: \n", "a: -x\n",
])
def test_mini_yaml_fails_closed(text):
    with pytest.raises(mini_yaml.MiniYamlError):
        mini_yaml.loads(text)


def test_mini_yaml_generated_documents_match_pyyaml():
    import random
    rng = random.Random(1359)
    words = ["альфа", "beta", "D271", "agr inspect", "path/to/x.py:12", "#1337", "a -> b", "Ёж"]

    def gen(depth):
        if depth == 0 or rng.random() < 0.3:
            return rng.choice(words + [rng.randint(-50, 5000)])
        if rng.random() < 0.5:
            return [gen(depth - 1) for _ in range(rng.randint(1, 3))]
        return {f"k{i}": gen(depth - 1) for i in range(rng.randint(1, 3))}

    def dump(v, ind):
        pad = " " * ind
        if isinstance(v, dict):
            out = []
            for k, x in v.items():
                out.append(f"{pad}{k}:" + ("\n" + dump(x, ind + 2) if isinstance(x, (dict, list)) else " " + sc(x)))
            return "\n".join(out)
        out = []
        for x in v:
            if isinstance(x, dict):
                body = dump(x, ind + 2).split("\n")
                body[0] = pad + "- " + body[0].lstrip()
                out.append("\n".join(body))
            elif isinstance(x, list):
                out.append(f"{pad}- " + json.dumps("nested", ensure_ascii=False))
            else:
                out.append(f"{pad}- {sc(x)}")
        return "\n".join(out)

    def sc(x):
        return str(x) if isinstance(x, int) else json.dumps(x, ensure_ascii=False)

    n = 0
    for _ in range(300):
        doc = {"root": gen(4)}
        text = dump(doc, 0) + "\n"
        assert mini_yaml.loads(text) == yaml.safe_load(text), text
        n += 1
    assert n == 300


# ---------------------------------------------------------------- duplicate guard
def test_guard_green_on_repo_with_allowlist(capsys):
    assert guard.main([]) == 0, capsys.readouterr().out


def test_allowlist_rows_carry_an_issue_and_name_only_known_rules():
    allowed = guard.allowlist(mini_yaml.load(ROOT / route_map.CONTEXTS))
    assert {r for r, _ in allowed} == set(guard.RULES)
    assert all(issue.startswith("#") for issue in allowed.values())
    jobs = [k for k in allowed if k[1].startswith("jobs/")]
    assert len([k for k in jobs if k[0] == "delivery-zip"]) == 14
    assert len([k for k in jobs if k[0] == "udim-tile"]) == 30


UDIM_COPIES = [
    "tile = 1001 + u + 10 * v\n",
    "tile = 10 * v + u + 1001\n",
    "tile = int(1001 + np.floor(a) + 10 * np.floor(b))\n",
    "t = by[1001 + tu + v * 10]\n",
    "du = (tile - 1001) % 10\n",
    "dv = (tile - 1001) // 10\n",
    "du, dv = divmod(tile - 1001, 10)\n",
    "i = udim - 1001\nx = (i % 10, i // 10)\n",
]
ZIP_COPIES = [
    "import zipfile\nwith zipfile.ZipFile(p, 'w') as z: pass\n",
    "import zipfile\nwith zipfile.ZipFile(p, \"x\", zipfile.ZIP_DEFLATED) as z: pass\n",
    "from zipfile import ZipFile\nZipFile(p, mode='a')\n",
    "import zipfile\nmode = 'w'\nzipfile.ZipFile(p, mode)\n",
]
NOT_COPIES = [
    "x = 1001 + u\n", "y = 10 * v + 5\n", "z = tile - 1001\n", "w = (tile - 1000) % 10\n",
    "import zipfile\nzipfile.ZipFile(p)\n", "import zipfile\nzipfile.ZipFile(p, 'r')\n",
    "import zipfile\nzipfile.ZipFile(p, mode='r')\n", "s = '1001 + u + 10 * v'\n",
]


def _guard_root(tmp_path, files, rows=""):
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    (tmp_path / "jobs").mkdir(exist_ok=True)
    ctx = tmp_path / "contexts.yaml"
    ctx.write_text("contexts:\n  - id: x\n    duplicates:\n" + rows if rows else "contexts:\n  - id: x\n",
                   encoding="utf-8")
    return ["--root", str(tmp_path), "--contexts", str(ctx)]


@pytest.mark.parametrize("code", UDIM_COPIES + ZIP_COPIES)
def test_guard_red_on_synthetic_job_local_copy(tmp_path, code, capsys):
    args = _guard_root(tmp_path, {"jobs/NEWJOB/scripts/copy.py": code})
    assert guard.main(args) == 1
    assert "NEW COPY" in capsys.readouterr().out


@pytest.mark.parametrize("code", NOT_COPIES)
def test_guard_ignores_non_copies(tmp_path, code):
    assert guard.main(_guard_root(tmp_path, {"jobs/NEWJOB/scripts/ok.py": code})) == 0


def test_guard_red_on_synthetic_copy_inside_the_real_repo_tree(tmp_path, capsys):
    """Copy the real jobs/ tree, add one new job-local copy: the real allowlist no longer passes."""
    def only_py(directory, names):
        return [n for n in names if not (Path(directory) / n).is_dir() and not n.endswith(".py")]

    for top in ("jobs", "adapters", "tools", "src"):
        shutil.copytree(ROOT / top, tmp_path / top, ignore=only_py)
    args = ["--root", str(tmp_path), "--contexts", str(ROOT / route_map.CONTEXTS)]
    assert guard.main(args) == 0
    (tmp_path / "jobs/KPP1/scripts/new_udim.py").write_text("t = 1001 + u + 10 * v\n", encoding="utf-8")
    assert guard.main(args) == 1
    assert "NEW COPY [udim-tile] jobs/KPP1/scripts/new_udim.py:1" in capsys.readouterr().out


def test_guard_allowlisted_copy_passes_and_stale_row_fails(tmp_path, capsys):
    row = '      - at: "jobs/J/a.py:1"\n        rule: udim-tile\n        issue: "#1337"\n'
    assert guard.main(_guard_root(tmp_path, {"jobs/J/a.py": UDIM_COPIES[0]}, row)) == 0
    assert guard.main(_guard_root(tmp_path, {"jobs/J/a.py": "x = 1\n"}, row)) == 1
    assert "STALE ALLOWLIST [udim-tile] jobs/J/a.py:1" in capsys.readouterr().out


def test_guard_moved_line_is_new_and_stale(tmp_path, capsys):
    row = '      - at: "jobs/J/a.py:1"\n        rule: udim-tile\n        issue: "#1337"\n'
    assert guard.main(_guard_root(tmp_path, {"jobs/J/a.py": "\n" + UDIM_COPIES[0]}, row)) == 1
    out = capsys.readouterr().out
    assert "NEW COPY [udim-tile] jobs/J/a.py:2" in out and "STALE ALLOWLIST [udim-tile] jobs/J/a.py:1" in out


@pytest.mark.parametrize("row", [
    '      - at: "jobs/J/a.py:1"\n        rule: udim-tile\n',                       # no issue
    '      - at: "jobs/J/a.py:1"\n        rule: udim-tile\n        issue: "1337"\n',  # not an issue ref
    '      - at: "jobs/J/a.py:1"\n        rule: nope\n        issue: "#1"\n',         # unknown rule
    '      - at: "jobs/J/a.py:1"\n        rule: udim-tile\n        issue: "#1"\n'
    '      - at: "jobs/J/a.py:1"\n        rule: udim-tile\n        issue: "#1"\n',    # duplicated row
])
def test_guard_bad_allowlist_is_an_error(tmp_path, row):
    assert guard.main(_guard_root(tmp_path, {"jobs/J/a.py": UDIM_COPIES[0]}, row)) == 2


def test_guard_unparsable_job_file_is_an_error_naming_it(tmp_path, capsys):
    assert guard.main(_guard_root(tmp_path, {"jobs/J/broken.py": "def (:\n"})) == 2
    assert "jobs/J/broken.py" in capsys.readouterr().err


def test_guard_missing_jobs_or_empty_contexts_is_an_error(tmp_path):
    ctx = tmp_path / "contexts.yaml"
    ctx.write_text("contexts:\n  - id: x\n", encoding="utf-8")
    assert guard.main(["--root", str(tmp_path), "--contexts", str(ctx)]) == 2       # no jobs/
    (tmp_path / "jobs").mkdir()
    ctx.write_text("", encoding="utf-8")
    assert guard.main(["--root", str(tmp_path), "--contexts", str(ctx)]) == 2       # empty YAML


def test_guard_fresh_process_cli():
    import subprocess
    r = subprocess.run([sys.executable, str(ROOT / "tools/architecture/duplicate_guard.py")],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
