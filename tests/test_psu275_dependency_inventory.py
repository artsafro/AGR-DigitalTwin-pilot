"""Static dependency inventory and contract tests between PSU275 and KPP1 scripts.

No bpy imports, job module imports, execution, compile/eval, or DCC.
Static regex extraction for shell targets and AST parsing for Python imports.
"""
import ast
from pathlib import Path
import re
import shutil

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
PSU_SCRIPTS = REPO_ROOT / "jobs" / "PSU275" / "scripts"
KPP_SCRIPTS = REPO_ROOT / "jobs" / "KPP1" / "scripts"

# Pinned actual source inventory:
# 1. Four KPP1 CLI targets invoked via --python in jobs/PSU275/scripts/run_all.sh
EXPECTED_KPP_CLI_TARGETS: tuple[str, ...] = (
    "qa_overlap.py",
    "export_vpm.py",
    "qa_master.py",
    "run_agr_checker.py",
)

# 2. All --python targets in jobs/PSU275/scripts/run_all.sh in order
EXPECTED_ALL_PYTHON_TARGETS: tuple[str, ...] = (
    "vpm_stage5.py",
    "vpm_ucx.py",
    "qa_master_psu275.py",
    "qa_overlap.py",
    "export_vpm.py",
    "qa_master.py",
    "export_npm.py",
    "run_agr_checker.py",
)

EXPECTED_PYTHON_PATHS: tuple[str, ...] = (
    "$J/scripts/vpm_stage5.py",
    "$J/scripts/vpm_ucx.py",
    "$J/scripts/qa_master_psu275.py",
    "$J/../KPP1/scripts/qa_overlap.py",
    "$J/../KPP1/scripts/export_vpm.py",
    "$J/../KPP1/scripts/qa_master.py",
    "$J/scripts/export_npm.py",
    "$J/../KPP1/scripts/run_agr_checker.py",
)

# 3. Four unique imported modules from KPP1 across all PSU275 scripts
EXPECTED_IMPORTED_MODULES: tuple[str, ...] = (
    "export_safety",
    "make_textures",
    "seal",
    "vpm_uv",
)

# 4. Import edges from PSU275 scripts resolving into KPP1 scripts
EXPECTED_IMPORT_EDGES: dict[str, tuple[str, ...]] = {
    "export_npm.py": ("export_safety",),
    "make_npm_atlas.py": ("make_textures",),
    "make_textures_psu275.py": ("make_textures",),
    "vpm_stage5.py": ("seal", "vpm_uv"),
    "vpm_stage5_oks.py": ("seal", "vpm_uv"),
}


def _is_kpp_sys_path_insert(node: ast.AST) -> bool:
    """Recognize supported sys.path.insert calls for KPP1/scripts without expression evaluation.

    Limited static resolver (not a general Python import interpreter):
    Recognizes the currently supported forms:
    1. sys.path.insert(0, os.path.join(HERE, "..", "..", "KPP1", "scripts"))
    2. sys.path.insert(0, str(ROOT / "jobs" / "KPP1" / "scripts"))

    Strictly requires an ast.Call to sys.path.insert with string constants containing
    both 'KPP1' and 'scripts'.
    """
    if not isinstance(node, ast.Call):
        return False

    func = node.func
    if not (
        isinstance(func, ast.Attribute)
        and func.attr == "insert"
        and isinstance(func.value, ast.Attribute)
        and func.value.attr == "path"
        and isinstance(func.value.value, ast.Name)
        and func.value.value.id == "sys"
    ):
        return False

    if len(node.args) < 2:
        return False

    path_arg = node.args[1]
    literals = {
        n.value
        for n in ast.walk(path_arg)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }
    if not ("KPP1" in literals and "scripts" in literals):
        return False

    if isinstance(path_arg, ast.Call):
        call_func = path_arg.func
        # Form 1: os.path.join(...)
        if isinstance(call_func, ast.Attribute) and call_func.attr == "join":
            return True
        # Form 2: str(ROOT / ... / "KPP1" / "scripts")
        if isinstance(call_func, ast.Name) and call_func.id == "str":
            if any(isinstance(sub, ast.BinOp) for sub in ast.walk(path_arg)):
                return True

    return False


def _extract_script_kpp_imports(py_path: Path, kpp_scripts: Path) -> tuple[str, ...]:
    """Parse a single Python script and resolve imports into KPP1 scripts.

    Limited static resolver (not a general Python import interpreter):
    Collects ast.Import aliases and absolute ast.ImportFrom module names.
    Resolves a module only when:
    1. A supported sys.path.insert targeting KPP1/scripts occurs prior to the import.
    2. The module exists as a *.py file in kpp_scripts.
    """
    tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))

    insert_linenos = [
        node.lineno
        for node in ast.walk(tree)
        if _is_kpp_sys_path_insert(node)
    ]
    if not insert_linenos:
        return ()

    min_insert_lineno = min(insert_linenos)
    resolved_modules: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue

        if node.lineno <= min_insert_lineno:
            continue

        if isinstance(node, ast.Import):
            for alias in node.names:
                mod_name = alias.name.split(".")[0]
                target_file = kpp_scripts / f"{mod_name}.py"
                if target_file.is_file():
                    resolved_modules.add(mod_name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                mod_name = node.module.split(".")[0]
                target_file = kpp_scripts / f"{mod_name}.py"
                if target_file.is_file():
                    resolved_modules.add(mod_name)

    return tuple(sorted(resolved_modules))


def _extract_shell_targets(
    run_all_path: Path,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Extract quoted --python targets from non-comment lines of run_all.sh.

    Returns:
        (all_python_targets, all_python_raw_targets, kpp_cli_targets, kpp_cli_raw_targets)
    """
    if not run_all_path.is_file():
        return (), (), (), ()

    all_targets: list[str] = []
    all_raw_targets: list[str] = []
    kpp_targets: list[str] = []
    kpp_raw_targets: list[str] = []

    pattern = re.compile(r'(?:^|\s)--python\s+["\']([^"\']+)["\']')

    for raw_line in run_all_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        for match in pattern.finditer(line):
            raw_path = match.group(1)
            basename = Path(raw_path.replace("\\", "/")).name

            all_raw_targets.append(raw_path)
            all_targets.append(basename)

            path_parts = raw_path.replace("\\", "/").split("/")
            if "KPP1" in path_parts and "scripts" in path_parts:
                kpp_raw_targets.append(raw_path)
                kpp_targets.append(basename)

    return tuple(all_targets), tuple(all_raw_targets), tuple(kpp_targets), tuple(kpp_raw_targets)


def dependency_inventory(psu_scripts: Path, kpp_scripts: Path) -> dict:
    """Extract static dependency inventory for PSU275 scripts against KPP1 scripts.

    Limited static resolver (not a general Python import interpreter):
    - Shell targets: regex-extract quoted `--python` targets from non-comment lines
      in run_all.sh, recording raw path and basename. Targets routing to KPP1 are
      identified by literal KPP1 and scripts routing.
    - Imports: AST parse every PSU275 *.py script, resolving imports to KPP1 only
      when the target exists as a .py in kpp_scripts and the importing script has
      a preceding sys.path.insert call targeting KPP1/scripts (supporting os.path.join
      and Path / forms containing literal 'KPP1' and 'scripts').
    """
    all_targets, all_raw, kpp_targets, kpp_raw = _extract_shell_targets(psu_scripts / "run_all.sh")

    import_edges: dict[str, tuple[str, ...]] = {}
    all_imported_modules: set[str] = set()

    if psu_scripts.is_dir():
        for py_path in sorted(psu_scripts.glob("*.py")):
            mods = _extract_script_kpp_imports(py_path, kpp_scripts)
            if mods:
                import_edges[py_path.name] = mods
                all_imported_modules.update(mods)

    return {
        "all_python_targets": all_targets,
        "all_python_raw_targets": all_raw,
        "kpp_cli_targets": kpp_targets,
        "kpp_cli_raw_targets": kpp_raw,
        "imported_modules": tuple(sorted(all_imported_modules)),
        "import_edges": import_edges,
    }


def assert_dependency_contract(psu_scripts: Path, kpp_scripts: Path) -> dict:
    """Validate dependency contract against extracted inventory."""
    inv = dependency_inventory(psu_scripts, kpp_scripts)

    # 1. KPP1 CLI targets from run_all.sh
    actual_kpp = tuple(inv["kpp_cli_targets"])
    actual_kpp_set = set(actual_kpp)
    expected_kpp_set = set(EXPECTED_KPP_CLI_TARGETS)

    missing_kpp = expected_kpp_set - actual_kpp_set
    assert not missing_kpp, f"Missing required KPP1 CLI target: {', '.join(sorted(missing_kpp))}"

    unapproved_kpp = actual_kpp_set - expected_kpp_set
    assert not unapproved_kpp, f"Unapproved KPP1 CLI target: {', '.join(sorted(unapproved_kpp))}"

    assert actual_kpp == EXPECTED_KPP_CLI_TARGETS, (
        f"KPP1 CLI targets sequence mismatch (order or duplicate): "
        f"expected {EXPECTED_KPP_CLI_TARGETS}, got {actual_kpp}"
    )

    actual_raw = tuple(inv["all_python_raw_targets"])
    assert actual_raw == EXPECTED_PYTHON_PATHS, (
        f"Python CLI target mismatch: "
        f"expected {EXPECTED_PYTHON_PATHS}, got {actual_raw}"
    )

    # 2. Import edges per script (names missing or added target and importing script)
    actual_edges = inv["import_edges"]
    for script, expected_mods in EXPECTED_IMPORT_EDGES.items():
        actual_script_mods = set(actual_edges.get(script, ()))
        missing_script_mods = set(expected_mods) - actual_script_mods
        assert not missing_script_mods, (
            f"Missing required import '{', '.join(sorted(missing_script_mods))}' in {script}"
        )
        unapproved_script_mods = actual_script_mods - set(expected_mods)
        assert not unapproved_script_mods, (
            f"Unapproved import '{', '.join(sorted(unapproved_script_mods))}' in {script}"
        )

    for script, actual_mods in sorted(actual_edges.items()):
        if script not in EXPECTED_IMPORT_EDGES:
            unapproved = set(actual_mods)
            assert not unapproved, f"Unapproved import '{', '.join(sorted(unapproved))}' in {script}"

    # 3. Overall unique imported modules
    actual_imported_set = set(inv["imported_modules"])
    expected_imported_set = set(EXPECTED_IMPORTED_MODULES)
    missing_imported = expected_imported_set - actual_imported_set
    assert not missing_imported, f"Missing required imported module: {', '.join(sorted(missing_imported))}"
    unapproved_imported = actual_imported_set - expected_imported_set
    assert not unapproved_imported, f"Unapproved imported module: {', '.join(sorted(unapproved_imported))}"

    return inv


def copy_job_scripts(tmp_path: Path) -> tuple[Path, Path]:
    """Copy only scripts into tmp_path/jobs/{PSU275,KPP1}/scripts; never outputs or data."""
    psu_dst = tmp_path / "jobs" / "PSU275" / "scripts"
    kpp_dst = tmp_path / "jobs" / "KPP1" / "scripts"
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(PSU_SCRIPTS, psu_dst, ignore=ignore)
    shutil.copytree(KPP_SCRIPTS, kpp_dst, ignore=ignore)
    return psu_dst, kpp_dst


def test_real_source_inventory():
    inv = dependency_inventory(PSU_SCRIPTS, KPP_SCRIPTS)
    assert inv["all_python_targets"] == EXPECTED_ALL_PYTHON_TARGETS
    assert inv["all_python_raw_targets"] == EXPECTED_PYTHON_PATHS
    assert inv["kpp_cli_targets"] == EXPECTED_KPP_CLI_TARGETS
    assert inv["imported_modules"] == EXPECTED_IMPORTED_MODULES
    assert inv["import_edges"] == EXPECTED_IMPORT_EDGES
    assert_dependency_contract(PSU_SCRIPTS, KPP_SCRIPTS)


def test_replaced_export_target_reports_missing_target(tmp_path):
    psu_scripts, kpp_scripts = copy_job_scripts(tmp_path)
    run_all = psu_scripts / "run_all.sh"
    content = run_all.read_text(encoding="utf-8")
    old_call = "$J/../KPP1/scripts/export_vpm.py"
    new_call = "$J/scripts/export_vpm_psu275.py"
    assert old_call in content, f"Expected {old_call} in run_all.sh"
    run_all.write_text(content.replace(old_call, new_call), encoding="utf-8")

    inv = dependency_inventory(psu_scripts, kpp_scripts)
    assert "export_vpm_psu275.py" in inv["all_python_targets"]
    assert "export_vpm.py" not in inv["kpp_cli_targets"]
    with pytest.raises(AssertionError, match=r"(?i)missing.*export_vpm\.py"):
        assert_dependency_contract(psu_scripts, kpp_scripts)


def test_shell_route_change_same_basename_contract_rejects(tmp_path):
    psu_scripts, kpp_scripts = copy_job_scripts(tmp_path)
    run_all = psu_scripts / "run_all.sh"
    content = run_all.read_text(encoding="utf-8")
    old_call = "$J/../KPP1/scripts/export_vpm.py"
    new_call = "$J/scripts/export_vpm.py"
    assert old_call in content, f"Expected {old_call} in run_all.sh"
    run_all.write_text(content.replace(old_call, new_call), encoding="utf-8")

    inv = dependency_inventory(psu_scripts, kpp_scripts)
    assert "export_vpm.py" in inv["all_python_targets"]
    assert "export_vpm.py" not in inv["kpp_cli_targets"]
    with pytest.raises(AssertionError, match=r"(?i)missing.*export_vpm\.py"):
        assert_dependency_contract(psu_scripts, kpp_scripts)


def test_removed_call_reported(tmp_path):
    psu_scripts, kpp_scripts = copy_job_scripts(tmp_path)
    run_all = psu_scripts / "run_all.sh"
    lines = [
        line for line in run_all.read_text(encoding="utf-8").splitlines(keepends=True)
        if "qa_overlap.py" not in line
    ]
    run_all.write_text("".join(lines), encoding="utf-8")

    inv = dependency_inventory(psu_scripts, kpp_scripts)
    assert len(inv["all_python_targets"]) == len(EXPECTED_ALL_PYTHON_TARGETS) - 1
    assert "qa_overlap.py" not in inv["kpp_cli_targets"]
    with pytest.raises(AssertionError, match=r"(?i)missing.*qa_overlap\.py"):
        assert_dependency_contract(psu_scripts, kpp_scripts)


def test_extra_unapproved_import_reported(tmp_path):
    psu_scripts, kpp_scripts = copy_job_scripts(tmp_path)
    synthetic_kpp = kpp_scripts / "qa_overlap_new.py"
    synthetic_kpp.write_text("# synthetic KPP1 module\n", encoding="utf-8")

    target_script = psu_scripts / "export_npm.py"
    original = target_script.read_text(encoding="utf-8")
    target_script.write_text(original + "\nimport qa_overlap_new\n", encoding="utf-8")

    inv = dependency_inventory(psu_scripts, kpp_scripts)
    assert "qa_overlap_new" in inv["imported_modules"]
    assert "qa_overlap_new" in inv["import_edges"].get("export_npm.py", ())
    with pytest.raises(AssertionError, match=r"(?i)unapproved.*qa_overlap_new.*export_npm\.py"):
        assert_dependency_contract(psu_scripts, kpp_scripts)


def test_removed_existing_import_reported(tmp_path):
    psu_scripts, kpp_scripts = copy_job_scripts(tmp_path)
    target_script = psu_scripts / "export_npm.py"
    lines = [
        line for line in target_script.read_text(encoding="utf-8").splitlines(keepends=True)
        if "export_safety" not in line
    ]
    target_script.write_text("".join(lines), encoding="utf-8")

    inv = dependency_inventory(psu_scripts, kpp_scripts)
    assert "export_safety" not in inv["import_edges"].get("export_npm.py", ())
    assert len(inv["imported_modules"]) == len(EXPECTED_IMPORTED_MODULES) - 1
    with pytest.raises(AssertionError, match=r"(?i)missing.*export_safety.*export_npm\.py"):
        assert_dependency_contract(psu_scripts, kpp_scripts)


def test_removed_kpp_sys_path_insert_reports_missing_import(tmp_path):
    psu_scripts, kpp_scripts = copy_job_scripts(tmp_path)
    target_script = psu_scripts / "export_npm.py"
    lines = [
        line for line in target_script.read_text(encoding="utf-8").splitlines(keepends=True)
        if "sys.path.insert" not in line
    ]
    target_script.write_text("".join(lines), encoding="utf-8")

    inv = dependency_inventory(psu_scripts, kpp_scripts)
    assert "export_safety" not in inv["import_edges"].get("export_npm.py", ())
    with pytest.raises(AssertionError, match=r"(?i)missing.*export_safety.*export_npm\.py"):
        assert_dependency_contract(psu_scripts, kpp_scripts)


def test_no_execution_with_raise_sentinel(tmp_path):
    psu_scripts, kpp_scripts = copy_job_scripts(tmp_path)
    target_script = psu_scripts / "vpm_stage5.py"
    original = target_script.read_text(encoding="utf-8")
    sentinel = 'raise RuntimeError("Execution forbidden sentinel")\n'
    target_script.write_text(sentinel + original, encoding="utf-8")

    # Static AST analysis must not execute the module or raise RuntimeError
    inv = dependency_inventory(psu_scripts, kpp_scripts)
    assert "seal" in inv["import_edges"].get("vpm_stage5.py", ())
    assert "vpm_uv" in inv["import_edges"].get("vpm_stage5.py", ())


def test_ast_ignores_comments_and_strings_and_handles_aliases(tmp_path):
    psu_scripts, kpp_scripts = copy_job_scripts(tmp_path)
    # Add dummy files in KPP1 that would trigger false positives if naive string search was used
    for fake in [
        "fake_comment_mod.py",
        "fake_docstring_mod.py",
        "fake_string_mod.py",
        "fake_from_docstring_mod.py",
    ]:
        (kpp_scripts / fake).write_text("# dummy\n", encoding="utf-8")

    sample_script = psu_scripts / "sample_ast_check.py"
    sample_script.write_text(
        'import os, sys\n'
        'HERE = os.path.dirname(os.path.abspath(__file__))\n'
        'sys.path.insert(0, os.path.join(HERE, "..", "..", "KPP1", "scripts"))\n'
        '# import fake_comment_mod\n'
        '"""\n'
        'import fake_docstring_mod\n'
        'from fake_from_docstring_mod import something\n'
        '"""\n'
        'code_str = "import fake_string_mod"\n'
        'import seal as aliased_seal\n'
        'from vpm_uv import load_spec as aliased_spec, pack_uv\n',
        encoding="utf-8",
    )

    inv = dependency_inventory(psu_scripts, kpp_scripts)
    edges = inv["import_edges"].get("sample_ast_check.py", ())
    assert "seal" in edges
    assert "vpm_uv" in edges
    assert "fake_comment_mod" not in edges
    assert "fake_docstring_mod" not in edges
    assert "fake_from_docstring_mod" not in edges
    assert "fake_string_mod" not in edges


def test_malformed_python_source_propagates_syntax_error(tmp_path):
    psu_scripts, kpp_scripts = copy_job_scripts(tmp_path)
    malformed_script = psu_scripts / "malformed_psu.py"
    malformed_script.write_text("def broken_syntax(:\n", encoding="utf-8")

    with pytest.raises(SyntaxError) as exc_info:
        dependency_inventory(psu_scripts, kpp_scripts)
    assert "malformed_psu.py" in (exc_info.value.filename or "") or "malformed_psu.py" in str(exc_info.value)


def test_wrong_root_route_mutation_reports_target_mismatch(tmp_path):
    psu_scripts, kpp_scripts = copy_job_scripts(tmp_path)
    run_all = psu_scripts / "run_all.sh"
    content = run_all.read_text(encoding="utf-8")
    old_call = "$J/../KPP1/scripts/export_vpm.py"
    new_call = "$J/../OTHER/KPP1/scripts/export_vpm.py"
    assert old_call in content, f"Expected {old_call} in run_all.sh"
    run_all.write_text(content.replace(old_call, new_call), encoding="utf-8")

    inv = dependency_inventory(psu_scripts, kpp_scripts)
    assert "export_vpm.py" in inv["kpp_cli_targets"]
    assert new_call in inv["all_python_raw_targets"]
    with pytest.raises(AssertionError, match=r"(?i)target mismatch") as exc_info:
        assert_dependency_contract(psu_scripts, kpp_scripts)
    assert new_call in str(exc_info.value)


def test_duplicate_cli_call_reports_sequence_mismatch(tmp_path):
    psu_scripts, kpp_scripts = copy_job_scripts(tmp_path)
    run_all = psu_scripts / "run_all.sh"
    content = run_all.read_text(encoding="utf-8")
    dup_call = '"$BL" --background --factory-startup --disable-autoexec --python "$J/../KPP1/scripts/qa_overlap.py" -- "$D/overlap.json"\n'
    run_all.write_text(content + "\n" + dup_call, encoding="utf-8")

    inv = dependency_inventory(psu_scripts, kpp_scripts)
    assert inv["kpp_cli_targets"].count("qa_overlap.py") == 2
    with pytest.raises(AssertionError, match=r"(?i)sequence mismatch.*duplicate"):
        assert_dependency_contract(psu_scripts, kpp_scripts)
