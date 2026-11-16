"""Skeleton guard (#1546): a job configures its scenario skeleton and plugs in a few hooks, it never re-implements a stage.

Pattern: n/a | new-case: AST job-contract guard over docs/agents/skeletons.json (scenario -> stages -> owners).

Contract ([D324], [D325]; human view docs/agents/SKELETONS.md):
- `jobs/<ID>/skeleton.json` = {"scenario": <cell of docs/scenarios/scenarios.json>, "config": {<key of the cell's
  config_keys>: ...}, "hooks": [{"script": "hooks/<name>", "stage": <stage of the cell>, "point": before|after|gap}]}.
- Every script of the job (suffixes of job_contract.script_suffixes) lives in `hooks/` and is listed once in `hooks`;
  at most job_contract.max_hooks hooks (5 passes, 6 fails). `gap` is allowed only on a stage without a shared
  implementation (gap != null); a stage that has one is called, never replaced.
- A Python hook re-implements a stage when it defines (def/class, any depth) one of the stage's `entry_defs` (names
  the stage owners define) or holds a copy that a duplicate_guard rule of the stage's `dup_rules` flags. The shared
  cores (`shared`, e.g. the Blender runner) are checked for every job.
Which job folders are checked (`check_repo`): every jobs/<ID>/ with a skeleton.json; a folder with scripts and no
skeleton.json fails unless it is a delivered job (`finished_jobs` of docs/architecture/contexts.yaml: historical,
[D327]) or in LEGACY_JOBS (folders that existed at #1546; they opt in by adding skeleton.json). `_template` is skipped.
Every problem names the file and the stage. Usage: python tools/architecture/skeleton_guard.py [--root REPO]
[--job jobs/ID]; exit 0 clean, 1 violations, 2 unreadable input (bad JSON, unknown scenario, syntax error).
"""
import argparse
import ast
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import duplicate_guard  # noqa: E402
    import mini_yaml  # noqa: E402
else:
    from . import duplicate_guard, mini_yaml

SKELETONS = "docs/agents/skeletons.json"
# Job folders that existed when the contract started (#1546); they keep their scripts until they opt in.
LEGACY_JOBS = frozenset({
    "4bk-k3", "4bk-k3-course-grid-1326", "butovskaya-sosh1000", "COD-20207", "elv-tc-vpm", "garibaldi22",
    "kasatkino-ground", "KERNEL-SYNTHETIC", "maf-atlas-512", "master-topology-1420", "OBJ03",
    "ogorodnyj-proezd-zu4-3", "ORCH-OBR22-NPM", "silikatniy-uvk-pzu-viz", "silikatny-maf-viz", "SYNTH-001",
    "vyatskaya-tow02",
})


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


def check_job(root, job_dir, skeletons):
    """Problems of one job folder that has a skeleton.json (ConfigError for unreadable input)."""
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
    for i, h in enumerate(hooks):
        if not isinstance(h, dict) or set(h) != {"script", "stage", "point"}:
            raise ConfigError(f"{rel_job}: hooks[{i}] needs exactly script, stage, point")
        script, sid, point = str(h["script"]), h["stage"], h["point"]
        if sid not in spec["stages"]:
            raise ConfigError(f"{rel_job}: hooks[{i}] stage {sid!r} is not a stage of {cell} ({spec['stages']})")
        if point not in contract["points"]:
            raise ConfigError(f"{rel_job}: hooks[{i}] point {point!r} unknown ({contract['points']})")
        path = (job_dir / script).resolve()
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
        rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
        if path.resolve() not in listed:
            where = "outside hooks/" if not path.resolve().is_relative_to(hooks_root) else "not listed in hooks"
            problems.append(f"{rel}: script {where}; a job holds skeleton.json + listed hooks only [D324]")
        if path.suffix.lower() == ".py":
            problems.extend(stage_problems(path.read_bytes(), rel, guarded))
    return problems


def check_repo(root, skeletons=None, finished=None):
    """Problems of every job folder under root/jobs (see module docstring for which ones)."""
    root = Path(root)
    skeletons = skeletons or load_skeletons(root)
    if finished is None:
        contexts = mini_yaml.load(root / "docs/architecture/contexts.yaml")
        finished = {Path(j).name for j in duplicate_guard.finished_jobs(root, contexts)}
    suffixes = set(skeletons["job_contract"]["script_suffixes"])
    problems = []
    jobs = root / "jobs"
    if not jobs.is_dir():
        raise ConfigError(f"{jobs}: missing")
    for job_dir in sorted(p for p in jobs.iterdir() if p.is_dir()):
        name = job_dir.name
        if name == "_template":
            continue
        if (job_dir / skeletons["job_contract"]["config"]).is_file():
            problems.extend(check_job(root, job_dir, skeletons))
        elif name not in finished and name not in LEGACY_JOBS and _scripts(job_dir, suffixes):
            problems.append(f"jobs/{name}: has scripts but no {skeletons['job_contract']['config']}; configure the "
                            "scenario skeleton and put small scripts in hooks/ (docs/agents/SKELETONS.md) [D324]")
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
