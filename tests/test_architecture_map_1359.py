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
    assert len(files) == 8  # NPM, VPM (#1383), Ground (#1383) routes + context map, .excalidraw + .svg each
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
    (lambda e, c: c["shared_kernel"]["duplicates"][0].update(at="jobs/KPP1/scripts/vpm_uv.py:151"),
     "path.py::function"),
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
    assert {k[0] for k in allowed} == set(guard.RULES)
    assert all(issue.startswith("#") for issue in allowed.values())
    jobs = [k for k in allowed if k[1].startswith("jobs/")]
    assert len([k for k in jobs if k[0] == "delivery-zip"]) == 15
    assert len([k for k in jobs if k[0] == "udim-tile"]) == 32   # #1387: one row per copy (same line may hold 2)
    # #1387: rows are keyed by file + function (+ hash), never by a bare line number
    assert all(qual and ":" not in path for _, path, qual, _ in allowed)


def test_kpp1_package_copies_owned_by_the_packaging_issue():
    """#1387: the KPP1 package-1278 builder and the place_package writers point at #1377 (packaging owner)."""
    allowed = guard.allowlist(mini_yaml.load(ROOT / route_map.CONTEXTS))
    kpp1 = {k: v for k, v in allowed.items()
            if k[1] in ("jobs/KPP1/package-1278/build_package.py", "jobs/KPP1/site-1255/place_package.py")}
    assert {(k[1], k[2]) for k in kpp1} == {("jobs/KPP1/package-1278/build_package.py", "repair_artifacts"),
                                            ("jobs/KPP1/site-1255/place_package.py", "<module>")}
    assert len(kpp1) == 3 and set(kpp1.values()) == {"#1377"}


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


# r1 review (PR #1368): named integer constants hid the formula from the guard.
NAMED_CONST_COPIES = [
    # (b) module-level FIRST=1001 then the forward formula
    "FIRST = 1001\ndef t(u, v):\n    return FIRST + int(u) + 10 * int(v)\n",
    # (c) U=10, offset by the literal, modulo by the name
    "U = 10\ndef o(t):\n    k = t - 1001\n    return k % U\n",
    # function-level constants, annotated assignment, both names
    "def t(u, v):\n    F: int = 1001\n    W = 10\n    return F + u + W * v\n",
    "def o(t):\n    F = 1001\n    W = 10\n    return divmod(t - F, W)\n",
    "B = 1001\nW = 10\ndef o(t):\n    return (t - B) // W\n",
    # owner function names re-defined in a job, whatever the body
    "def udim_tile(u, v):\n    return lookup(u, v)\n",
    "class X:\n    def tile_origin(self, t):\n        return table[t]\n",
    "def face_tile(uvs):\n    pass\n",
    "def udim_of_cell(cu, cv):\n    pass\n",
]
NAMED_CONST_NOT_COPIES = [
    "FIRST = 1000\nx = FIRST + u + 10 * v\n",
    "U = 9\nk = t - 1001\ny = k % U\n",
    "FIRST = '1001'\nx = FIRST + u + 10 * v\n",
    "def udim_tile_report(rows):\n    pass\n",
    "udim_tile = owner.udim_tile\n",
]


def test_guard_red_on_verbatim_copy_of_the_owner(tmp_path, capsys):
    """(a) The owner module itself copied into a job must be a NEW COPY."""
    owner = (ROOT / guard.RULES["udim-tile"]).read_text(encoding="utf-8")
    args = _guard_root(tmp_path, {"jobs/NEWJOB/scripts/udimtile_core.py": owner})
    assert guard.main(args) == 1
    out = capsys.readouterr().out
    assert "NEW COPY" in out and "udim-tile" in out
    # every owned function line is found, not only one of them
    hits = guard.scan(tmp_path)
    assert len([h for h in hits if h[0] == "udim-tile"]) >= 4


@pytest.mark.parametrize("code", NAMED_CONST_COPIES)
def test_guard_red_on_named_constant_copy(tmp_path, code, capsys):
    args = _guard_root(tmp_path, {"jobs/NEWJOB/scripts/copy.py": code})
    assert guard.main(args) == 1
    assert "NEW COPY" in capsys.readouterr().out


@pytest.mark.parametrize("code", NAMED_CONST_NOT_COPIES)
def test_guard_named_constant_non_copies_pass(tmp_path, code):
    assert guard.main(_guard_root(tmp_path, {"jobs/NEWJOB/scripts/ok.py": code})) == 0


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


def _row(at, rule="udim-tile", issue="#1337", digest=None):
    row = f'      - at: "{at}"\n        rule: {rule}\n' + (f'        issue: "{issue}"\n' if issue else "")
    return row + (f'        hash: "{digest}"\n' if digest else "")


FN = "def f(u, v):\n    return 1001 + u + 10 * v\n"


def test_guard_allowlisted_copy_passes_and_stale_row_fails(tmp_path, capsys):
    row = _row("jobs/J/a.py::f")
    assert guard.main(_guard_root(tmp_path, {"jobs/J/a.py": FN}, row)) == 0
    assert guard.main(_guard_root(tmp_path, {"jobs/J/a.py": "def f():\n    return 1\n"}, row)) == 1
    assert "STALE ALLOWLIST [udim-tile] jobs/J/a.py::f" in capsys.readouterr().out


@pytest.mark.parametrize("prefix,body_prefix", [
    ("\n", ""), ("# c\n" * 40, ""), ("import os\n\n\ndef g():\n    pass\n\n\n", ""),
    ("", "    x = 1\n    y = 2\n"), ("\n" * 7, "    # moved\n" * 13),
])
def test_guard_line_shift_inside_the_same_function_stays_green(tmp_path, prefix, body_prefix, capsys):
    """#1387: lines inserted above or inside an allowlisted function move the copy; it is neither NEW nor STALE."""
    code = prefix + "def f(u, v):\n" + body_prefix + "    return 1001 + u + 10 * v\n"
    for digest in (None, guard.scan_text(FN)[0].digest):
        args = _guard_root(tmp_path, {"jobs/J/a.py": code}, _row("jobs/J/a.py::f", digest=digest))
        assert guard.main(args) == 0, capsys.readouterr().out


def test_guard_new_copy_in_another_function_is_red(tmp_path, capsys):
    code = FN + "\n\ndef g(u, v):\n    return 1001 + u + 10 * v\n"
    assert guard.main(_guard_root(tmp_path, {"jobs/J/a.py": code}, _row("jobs/J/a.py::f"))) == 1
    out = capsys.readouterr().out
    assert "NEW COPY [udim-tile] jobs/J/a.py:6 in g" in out and "STALE" not in out


def test_guard_copy_moved_into_another_function_is_new_and_stale(tmp_path, capsys):
    code = "def g(u, v):\n    return 1001 + u + 10 * v\n"
    assert guard.main(_guard_root(tmp_path, {"jobs/J/a.py": code}, _row("jobs/J/a.py::f"))) == 1
    out = capsys.readouterr().out
    assert "NEW COPY [udim-tile] jobs/J/a.py:2 in g" in out and "STALE ALLOWLIST [udim-tile] jobs/J/a.py::f" in out


def test_guard_hash_row_pins_one_copy_inside_the_function(tmp_path, capsys):
    digest = guard.scan_text(FN)[0].digest
    second = FN + "    du = (t - 1001) % 10\n"
    assert guard.main(_guard_root(tmp_path, {"jobs/J/a.py": second}, _row("jobs/J/a.py::f", digest=digest))) == 1
    assert "NEW COPY [udim-tile] jobs/J/a.py:3 in f" in capsys.readouterr().out      # 2nd copy, other hash
    assert guard.main(_guard_root(tmp_path, {"jobs/J/a.py": second}, _row("jobs/J/a.py::f"))) == 0  # no hash
    assert guard.main(_guard_root(tmp_path, {"jobs/J/a.py": FN}, _row("jobs/J/a.py::f", digest="0" * 10))) == 1
    out = capsys.readouterr().out
    assert "NEW COPY [udim-tile] jobs/J/a.py:2 in f" in out and "STALE ALLOWLIST [udim-tile] jobs/J/a.py::f" in out


@pytest.mark.parametrize("code,qual", [
    ("tile = 1001 + u + 10 * v\n", "<module>"),
    ("class X:\n    def tile_origin(self, t):\n        return table[t]\n", "X.tile_origin"),
    ("def outer():\n    def inner(u, v):\n        return 1001 + u + 10 * v\n", "outer.inner"),
    ("class X:\n    K = 1001 + u + 10 * v\n", "X"),
    ("async def f(u, v):\n    return 1001 + u + 10 * v\n", "f"),
    ("def f(u, v, t=1001 + u + 10 * v):\n    pass\n", "<module>"),   # a default runs in the enclosing scope
])
def test_guard_qualname_of_each_finding(code, qual):
    assert [h.qualname for h in guard.scan_text(code)] == [qual]


@pytest.mark.parametrize("row", [
    _row("jobs/J/a.py::f", issue=""),                                    # no issue
    _row("jobs/J/a.py::f", issue="1337"),                                # not an issue ref
    _row("jobs/J/a.py::f", rule="nope", issue="#1"),                     # unknown rule
    _row("jobs/J/a.py::f") + _row("jobs/J/a.py::f"),                     # duplicated row
    _row("jobs/J/a.py::f") + _row("jobs/J/a.py::f", digest="abcdef0123"),  # fn row overlaps a hash row
    _row("jobs/J/a.py:2"),                                               # #1387: a bare line is not a key
    _row("jobs/J/a.py"),                                                 # no function
    _row("jobs/J/a.py::"),                                               # empty function
    _row("jobs/J/a.py::f", digest="nothex!"),                            # malformed hash
    _row("jobs/J/a.py::f", digest="abcdef012"),                          # 9 hex: one short
    _row("jobs/J/a.py::f", digest="abcdef01234"),                        # 11 hex: one long
    _row("jobs/J/a.py::f", digest="ABCDEF0123"),                         # upper case
    _row("jobs/J/a.py::f g"),                                            # not a qualname
])
def test_guard_bad_allowlist_is_an_error(tmp_path, row, capsys):
    assert guard.main(_guard_root(tmp_path, {"jobs/J/a.py": FN}, row)) == 2
    assert "jobs/J/a.py" in capsys.readouterr().err


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
