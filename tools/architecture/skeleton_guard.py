"""Skeleton guard (#1546): a job configures its scenario skeleton and plugs in a few hooks, it never re-implements a stage.

Pattern: n/a | new-case: AST job-contract guard over docs/agents/skeletons.json (scenario -> stages -> owners).

Contract ([D324], [D325]; human view docs/agents/SKELETONS.md):
- `jobs/<ID>/skeleton.json` = {"scenario": <cell of docs/scenarios/scenarios.json>, "config": {<key of the cell's
  config_keys>: ...}, "hooks": [{"script": "hooks/<name>", "stage": <stage of the cell>, "point": before|after|gap}]}.
- Every script of the job (suffixes of job_contract.script_suffixes) lives in `hooks/` and is listed once in `hooks`,
  except the guard-owned exact paths in IMPORTED_LIBRARIES (documented in SKELETONS.md, #1591). These imported
  libraries cannot be registered as hooks and remain subject to syntax, stage and duplicate checks;
  at most job_contract.max_hooks hooks (5 passes, 6 fails). `gap` is allowed only on a stage without a shared
  implementation (gap != null); a stage that has one is called, never replaced.
- A Python hook re-implements a stage when it defines (def/class, any depth) one of the stage's `entry_defs` (names
  the stage owners define) or holds a copy that a duplicate_guard rule of the stage's `dup_rules` flags. The shared
  cores (`shared`, e.g. the Blender runner) are checked for every job.
Which scripts are checked (`check_repo`): every folder at any depth under jobs/ with a skeleton.json is a job and is
checked by `check_job` (sub-jobs like jobs/KPP1/<task>-<issue>/ included; a nested skeleton.json folder is its own
job). Every other script under jobs/ fails unless its path is in the frozen baseline of the #1546 cut
(docs/agents/job_scripts_baseline.txt: legacy and historical scripts, [D327]); legacy means a listed path, never a
whole job folder. Non-script template files (jobs/_template/job.yaml and README.md) need no config;
scripts and skeleton.json files are checked normally, including in any `_template` folder.
Every problem names the file and the stage. Usage: python tools/architecture/skeleton_guard.py [--root REPO]
[--job jobs/ID]; exit 0 clean, 1 violations, 2 unreadable input (bad JSON, unknown scenario, syntax error,
missing/invalid baseline).
"""
import argparse
import ast
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import duplicate_guard  # noqa: E402
else:
    from . import duplicate_guard

SKELETONS = "docs/agents/skeletons.json"

# Guard-owned, exact-path library exemptions (#1591), NOT additions to the frozen D327 baseline.
# Imported by historical build_quad_master.py after building, not run by master-qa.
# Keep the existing import path; only hook-list membership is exempt, never stage/copy checks.
IMPORTED_LIBRARIES = {
    "jobs/KPP1/quad-1372/provenance-1563/hooks/quad_provenance.py",
}


class ConfigError(ValueError):
    """Unreadable or inconsistent input (exit 2)."""


def load_skeletons(root):
    path = Path(root) / SKELETONS
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"{SKELETONS}: cannot read ({exc})") from None
    for cell, spec in data["cells"].items():
        for sid in spec["stages"]:
            if sid not in data["stages"]:
                raise ConfigError(f"{SKELETONS}: cell {cell} names unknown stage {sid!r}")
    return data


_PLACEHOLDER_REASONS = {"todo", "tbd", "?", "-", "...", "n/a", "na", "none"}


def modelling_split_problems(text, skeletons):
    """Problems of the job report's `Modelling split [D336]:` line (#1613, OKS `body` stage `modelling_split`).

    Exactly one line; `plinth=` one of the per-project choices; `inset=` and `texture=` comma lists of known parts,
    disjoint, at least one part named; `reason=` last, non-empty and not a placeholder. Fail-closed: [] only for that.
    """
    split = skeletons["stages"]["body"]["modelling_split"]
    head = split["report_line"].split(":", 1)[0] + ":"
    lines = [ln.strip().lstrip("-* ").strip() for ln in str(text or "").splitlines()]
    lines = [ln[len(head):] for ln in lines if ln.startswith(head)]
    if not lines:
        return [f"job report: no `{head}` line (the per-project split and its reason) [D336]"]
    if len(lines) > 1:
        return [f"job report: more than one `{head}` line ({len(lines)}) [D336]"]
    body, problems = lines[0], []
    fields, sep, reason = body.partition("reason=")
    if not sep:
        problems.append(f"`{head}` missing `reason=` (last field) [D336]")
    elif not reason.strip() or reason.strip().lower() in _PLACEHOLDER_REASONS or reason.strip().startswith("<"):
        problems.append(f"`{head}` reason is empty or a placeholder: {reason.strip()!r} [D336]")
    seen = {}
    for field in (f.strip() for f in fields.split(";")):
        if not field:
            continue
        key, eq, value = field.partition("=")
        key = key.strip()
        if not eq or key not in ("plinth", "inset", "texture"):
            problems.append(f"`{head}` unknown field {field!r} (known: plinth, inset, texture, reason)")
        elif key in seen:
            problems.append(f"`{head}` field {key}= given twice")
        else:
            seen[key] = value.strip()
    for key in ("plinth", "inset", "texture"):
        if key not in seen:
            problems.append(f"`{head}` missing `{key}=` [D336]")
    choices = split["per_project"]["plinth"]
    if "plinth" in seen and seen["plinth"] not in choices:
        problems.append(f"`{head}` plinth={seen['plinth']!r} is not one of {choices}")
    known = set(split["inset"]) | set(split["texture"])
    sides = {}
    for key in ("inset", "texture"):
        parts = [p.strip() for p in seen.get(key, "").split(",") if p.strip()]
        for part in parts:
            if part not in known:
                problems.append(f"`{head}` {key}: unknown part {part!r} (known: {sorted(known)})")
        sides[key] = set(parts)
        if len(parts) != len(sides[key]):
            problems.append(f"`{head}` {key}: a part is named twice: {parts}")
    both = sorted(sides["inset"] & sides["texture"])
    if both:
        problems.append(f"`{head}` parts named both inset and texture: {both}")
    if "inset" in seen and "texture" in seen and not (sides["inset"] | sides["texture"]):
        problems.append(f"`{head}` names no part on either side")
    return problems


def _scripts(job_dir, suffixes):
    return sorted(p for p in Path(job_dir).rglob("*") if p.is_file() and p.suffix.lower() in suffixes)


def _defined_names(tree):
    return {n.name: n.lineno for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def stage_problems(source, rel, guarded):
    """Problems of one Python hook text: defined entry names and duplicate_guard copies of the guarded stages.

    guarded = [(stage id, stage spec)]; SyntaxError raises ConfigError naming the file."""
    try:
        tree = ast.parse(source, filename=rel)
    except SyntaxError as exc:
        raise ConfigError(f"{rel}: cannot parse ({exc.msg}, line {exc.lineno})") from None
    names = _defined_names(tree)
    copies = duplicate_guard.scan_text(source, rel)
    out, flagged = [], set()
    for sid, spec in guarded:
        how = spec.get("calls") or ", ".join(spec.get("owners") or []) or "its building blocks"
        for name in spec.get("entry_defs", []):
            if name in names:
                flagged.add(names[name])
                out.append(f"{rel}:{names[name]}: defines {name!r} = re-implements stage {sid} ({spec['ru']}); "
                           f"call {how} instead [D325]")
        for f in copies:
            if f.rule in spec.get("dup_rules", []) and f.line not in flagged:  # one finding per copy
                out.append(f"{rel}:{f.line}: {f.rule} copy in {f.qualname} = re-implements stage {sid}; "
                           f"call {how} instead [D325]")
    return out


def check_job(root, job_dir, skeletons, nested=()):
    """Problems of one job folder that has a skeleton.json (ConfigError for unreadable input); scripts of the
    `nested` sub-job folders (their own skeleton.json) are left to their own check."""
    root, job_dir = Path(root), Path(job_dir)
    contract = skeletons["job_contract"]
    rel_job = job_dir.relative_to(root).as_posix() if job_dir.is_relative_to(root) else str(job_dir)
    cfg_path = job_dir / contract["config"]
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"{rel_job}/{contract['config']}: cannot read ({exc})") from None
    if not isinstance(cfg, dict) or not cfg:
        raise ConfigError(f"{rel_job}/{contract['config']}: must be a non-empty object")
    unknown = sorted(set(cfg) - {"scenario", "config", "hooks"})
    if unknown:
        raise ConfigError(f"{rel_job}/{contract['config']}: unknown keys {unknown}")
    cell = cfg.get("scenario")
    if not isinstance(cell, str) or cell not in skeletons["cells"]:
        raise ConfigError(f"{rel_job}: scenario {cell!r} is not a cell of {SKELETONS}")
    spec = skeletons["cells"][cell]
    config = cfg.get("config", {})
    if not isinstance(config, dict):
        raise ConfigError(f"{rel_job}: config must be an object")
    bad_keys = sorted(set(config) - set(spec["config_keys"]))
    if bad_keys:
        raise ConfigError(f"{rel_job}: config keys {bad_keys} are not read by the {cell} skeleton "
                          f"(known: {spec['config_keys']})")
    hooks = cfg.get("hooks", [])
    if not isinstance(hooks, list):
        raise ConfigError(f"{rel_job}: hooks must be a list")
    problems, listed = [], {}
    hooks_root = (job_dir / contract["hooks_dir"]).resolve()
    library_paths = {(root / rel).resolve() for rel in IMPORTED_LIBRARIES}
    for i, h in enumerate(hooks):
        if not isinstance(h, dict) or set(h) != {"script", "stage", "point"}:
            raise ConfigError(f"{rel_job}: hooks[{i}] needs exactly script, stage, point")
        script, sid, point = str(h["script"]), h["stage"], h["point"]
        if sid not in spec["stages"]:
            raise ConfigError(f"{rel_job}: hooks[{i}] stage {sid!r} is not a stage of {cell} ({spec['stages']})")
        if point not in contract["points"]:
            raise ConfigError(f"{rel_job}: hooks[{i}] point {point!r} unknown ({contract['points']})")
        path = (job_dir / script).resolve()
        if path in library_paths:
            problems.append(f"{rel_job}: hooks[{i}] {script} is an imported library, not a runnable stage hook "
                            "(docs/agents/SKELETONS.md#imported-library-exemptions)")
        if not path.is_relative_to(hooks_root):
            problems.append(f"{rel_job}: hooks[{i}] {script} is not inside {contract['hooks_dir']}/")
        elif not path.is_file():
            problems.append(f"{rel_job}: hooks[{i}] {script} does not exist")
        if path in listed:
            problems.append(f"{rel_job}: hooks[{i}] {script} listed twice (also hooks[{listed[path]}])")
        listed.setdefault(path, i)
        if point == "gap" and skeletons["stages"][sid]["gap"] is None:
            problems.append(f"{rel_job}: hooks[{i}] {script} replaces stage {sid}, which has a shared "
                            f"implementation ({skeletons['stages'][sid]['calls']}); use before/after [D325]")
    if len(hooks) > contract["max_hooks"]:
        problems.append(f"{rel_job}: {len(hooks)} hooks > {contract['max_hooks']} = a parallel pipeline, "
                        "not a few small scripts [D324]")
    guarded = [(s["id"], s) for s in skeletons["shared"]] + \
        [(sid, skeletons["stages"][sid]) for sid in spec["stages"]]
    for path in _scripts(job_dir, set(contract["script_suffixes"])):
        if any(path.is_relative_to(d) for d in nested if d.is_relative_to(job_dir)):
            continue   # a sub-job with its own skeleton.json is checked on its own
        rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
        if path.resolve() not in listed and rel not in IMPORTED_LIBRARIES:
            where = "outside hooks/" if not path.resolve().is_relative_to(hooks_root) else "not listed in hooks"
            problems.append(f"{rel}: script {where}; a job holds skeleton.json + listed hooks only [D324]")
        if path.suffix.lower() == ".py":
            problems.extend(stage_problems(path.read_bytes(), rel, guarded))
    return problems


def check_repo(root, skeletons=None, baseline=None):
    """Problems of every job script under root/jobs (see module docstring for which ones)."""
    root = Path(root)
    skeletons = skeletons or load_skeletons(root)
    baseline = duplicate_guard.load_job_baseline(root) if baseline is None else baseline
    contract = skeletons["job_contract"]
    jobs = root / "jobs"
    if not jobs.is_dir():
        raise ConfigError(f"{jobs}: missing")
    configured = sorted(p.parent for p in jobs.rglob(contract["config"]) if p.is_file())
    problems = []
    for job_dir in configured:   # any depth: jobs/<ID>/ and sub-jobs like jobs/KPP1/<task>-<issue>/
        problems.extend(check_job(root, job_dir, skeletons, nested=[d for d in configured if d != job_dir]))
    for path in _scripts(jobs, set(contract["script_suffixes"])):
        rel = path.relative_to(root).as_posix()
        if rel in baseline or any(path.is_relative_to(d) for d in configured):
            continue
        problems.append(f"{rel}: script outside a skeleton.json folder and not in the frozen #1546 baseline "
                        f"({duplicate_guard.JOB_BASELINE}); configure the scenario skeleton and put small scripts "
                        "in hooks/ (docs/agents/SKELETONS.md) [D324]")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description="Skeleton guard (#1546): jobs configure skeletons, never rebuild stages")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--job", default=None, help="check one job folder (relative to --root) that has skeleton.json")
    args = ap.parse_args(argv)
    try:
        skeletons = load_skeletons(args.root)
        if args.job:
            job_dir = args.root / args.job
            if not (job_dir / skeletons["job_contract"]["config"]).is_file():
                raise ConfigError(f"{args.job}: no {skeletons['job_contract']['config']}")
            problems = check_job(args.root, job_dir, skeletons)
        else:
            problems = check_repo(args.root, skeletons)
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for p in problems:
        print(f"SKELETON {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
