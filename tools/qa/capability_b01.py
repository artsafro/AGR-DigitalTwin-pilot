"""new-case: isolated fresh-agent B01 capability session lifecycle.

The launcher writes only a new external run directory and git worktree metadata.
It never edits benchmark/ or jobs/. Child writes there are detected and fail the run.
Native event streams are retained verbatim, not relabelled as Claude transcripts.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
import re

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from twinqa.evals.runner import run as eval_run  # noqa: E402


def git(repo, *args):
    return subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True,
                          encoding='utf-8', check=True, timeout=60).stdout.strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(repo):
    return {str(p.relative_to(repo)): sha(p) for folder in ('benchmark', 'jobs')
            for p in (repo / folder).rglob('*') if p.is_file()}


def evaluation_inventory(repo, paths=()):
    # Snapshot every tracked input, not just today's known checker filenames.
    # Retain the original paths even if the child removes them from the index.
    tracked = set(git(repo, 'ls-files', '-z').split('\0')) - {''}
    return {name: sha(repo / name) if (repo / name).is_file() else None
            for name in tracked.union(paths)}


def executable(argv):
    found = shutil.which(argv[0])
    if not found:
        raise ValueError(f'agent executable not found: {argv[0]}')
    if found.lower().endswith(('.cmd', '.bat')):
        return ['cmd.exe', '/d', '/c', found, *argv[1:]]
    return [found, *argv[1:]]


def agent_command(agent, model=None):
    if agent == 'codex':
        return ['codex', '--no-daemon', 'exec', '--ephemeral', '--ignore-user-config', '--json',
                '--enable', 'skip_host_skill_discovery', '--disable', 'memories', '--disable', 'plugins',
                *(['-c', 'windows.sandbox="elevated"'] if os.name == 'nt' else []),
                '--sandbox', 'workspace-write', '--add-dir', '{run}',
                *(['--model', model] if model else []), '{prompt}']
    if agent == 'claude':
        return ['claude', '-p', '--output-format', 'stream-json', '--verbose',
                *(['--model', model] if model else []), '{prompt}']
    raise ValueError('deepseek requires --command-json with the installed CLI argv; no assumed CLI protocol')


def stop(process):
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                       capture_output=True, timeout=30, check=False)
    else:
        import signal
        os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=30)


def validate_ticket(ticket):
    if not isinstance(ticket, dict):
        raise ValueError('ticket must be an object')
    if (type(ticket.get('number')) is not int or ticket['number'] <= 0
            or ticket.get('state') != 'CLOSED'
            or any(not isinstance(ticket.get(k), str) or not ticket[k].strip() for k in ('title', 'body'))):
        raise ValueError('ticket needs positive number, CLOSED state and nonempty title/body')
    labels = ticket.get('labels')
    if not isinstance(labels, list) or any(not isinstance(v, dict) or not isinstance(v.get('name'), str) for v in labels):
        raise ValueError('ticket needs label objects')
    names = [v['name'] for v in labels]
    if len(names) != len(set(names)) or 'ready-for-agent' not in names or not set(names) & {'documentation', 'test', 'tests'}:
        raise ValueError('ticket must be ready-for-agent documentation/test with unique labels')


def fetch_ticket(number, repo):
    if number <= 0:
        raise ValueError('ticket number must be positive')
    raw = subprocess.run(['gh', 'issue', 'view', str(number), '--repo', 'artsafro/AGR-DigitalTwin-pilot',
                          '--json', 'number,state,title,body,labels,url'], cwd=repo, check=True,
                         capture_output=True, text=True, encoding='utf-8', timeout=60).stdout
    from twinqa.evals.capability import unique_object
    value = json.loads(raw, object_pairs_hook=unique_object)
    validate_ticket(value)
    if value['number'] != number:
        raise ValueError('ticket number mismatch')
    return value


def launch(repo, run_dir, etalon=None, *, ticket=None, agent='codex', command=None, model=None,
           expected_sha=None, ref='main', timeout=1800, codex_home=None,
           isolation='private context; OS sandbox'):
    repo, run_dir = (Path(p).resolve() for p in (repo, run_dir))
    if ticket is not None:
        validate_ticket(ticket)
    elif etalon is None:
        raise ValueError('give --etalon or --ticket')
    etalon = Path(etalon).resolve() if etalon is not None else None
    if agent not in ('codex', 'claude', 'deepseek'):
        raise ValueError(f'unsupported agent: {agent}')
    if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be positive and finite')
    if run_dir.exists():
        raise ValueError('run directory exists; use a new run')
    # No deletion or output can overlap the source repository or etalon tree,
    # including absent descendants and junction-resolved aliases.
    if (run_dir.is_relative_to(repo) or repo.is_relative_to(run_dir)
            or (etalon is not None and (run_dir.is_relative_to(etalon.parent) or etalon.is_relative_to(run_dir)))):
        raise ValueError('run directory overlaps input')
    if codex_home is not None:
        codex_home = Path(codex_home).resolve()
        if (codex_home.is_relative_to(run_dir) or run_dir.is_relative_to(codex_home)
                or not codex_home.is_dir()):
            raise ValueError('prepared Codex home must exist and not overlap the run directory')
    if ticket is None and not etalon.is_file():
        raise ValueError(f'missing local B01 etalon: {etalon}')
    if ticket is None:
        expected_sha = expected_sha or json.loads(
            (repo / 'benchmark/bench-b01-box/etalon.json').read_text(encoding='utf-8'))['files']['etalon.fbx']['sha256']
        if sha(etalon) != expected_sha:
            raise ValueError('B01 etalon SHA256 mismatch')
    common = Path(git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir')).resolve().parent
    if run_dir.is_relative_to(common) or common.is_relative_to(run_dir):
        raise ValueError('run directory overlaps main checkout input')
    commit = git(repo, 'rev-parse', '--verify', f'{ref}^{{commit}}')
    template = command if command is not None else agent_command(agent, model)
    if not isinstance(template, list) or not template or any(not isinstance(x, str) or not x for x in template):
        raise ValueError('command must be a nonempty JSON array of nonempty strings')
    # Validate executable before allocating any output.
    executable(template)
    run_dir.mkdir(parents=True, exist_ok=False)
    worktree, output = run_dir / 'worktree', run_dir / 'benchmark'
    prompt = (f'Build bench-b01-box green from this repository alone. Start with the root files and '
              f'follow repository instructions; no prior chat context is available. '
              f'The read-only local etalon FBX is {etalon.as_posix() if etalon else "unused"}. '
              f'Write the benchmark runner outputs to {output.as_posix()}. '
              'Do not modify benchmark/ or jobs/, commit, push, open a PR or run the full test suite. '
              'Do not edit checkers, tolerances or specs to make a check pass. Report failures honestly.')
    branch = f'harness/capability-ticket-{ticket["number"]}-{uuid.uuid4().hex[:12]}' if ticket else None
    if ticket:
        prompt = (f'Fresh closed-ticket replay #{ticket["number"]}: {ticket["title"]}\n{ticket["body"]}\n'
                  f'Start with root files and follow repository instructions. No prior chat context. '
                  f'Your pre-approved branch is {branch}; do not rename it. '
                  f'Produce a committed PR-ready solution and write the PR body to {(run_dir / "pr-body.md").as_posix()}. '
                  'The body must follow the review checklist, Author receipts and all ten Agent trace fields. '
                  'Do not push, open a real PR, call GitHub, run the full test suite, modify benchmark/, jobs/, '
                  'standards/, hooks, evaluation code or policy documents. Focused tests are allowed. '
                  'Record unavailable telemetry as not measured. This historical ticket is intentionally closed; '
                  'solve it against this checkout without looking up its known answer. Publication is forbidden, '
                  'not an approval question. Do not use another checkout or its venv. Stop honestly on failures.')
        (run_dir / 'ticket.json').write_text(json.dumps(ticket, indent=2), encoding='utf-8')
    values = {'prompt': prompt, 'run': run_dir.as_posix(), 'output': output.as_posix(),
              'worktree': worktree.as_posix(), 'etalon': etalon.as_posix() if etalon else '',
              'body': (run_dir / 'pr-body.md').as_posix()}

    argv = []
    for arg in template:
        for name, value in values.items():
            arg = arg.replace('{' + name + '}', value)
        argv.append(arg)
    version = subprocess.run(executable([template[0], '--version']), capture_output=True,
                             text=True, encoding='utf-8', errors='replace', timeout=30, check=False)
    result = {'schema': 1, 'agent': agent, 'model': model, 'commit': commit, 'ref': ref,
              'agent_version': version.stdout.strip() or version.stderr.strip(),
              'command': argv, 'etalon_sha256': expected_sha, 'passed': False, 'cleanup': False,
              'isolation': isolation}
    (run_dir / 'prompt.txt').write_text(prompt, encoding='utf-8')
    started = time.monotonic()
    created = False
    try:
        git(repo, 'worktree', 'add', '--detach', str(worktree), commit)
        created = True
        if ticket:
            git(worktree, 'checkout', '-b', branch)
        before = inventory(worktree)
        evaluation_before = evaluation_inventory(worktree)
        if ticket:
            evaluation_before = {k: v for k, v in evaluation_before.items()
                                 if k.startswith(('benchmark/', 'jobs/', 'standards/', 'evals/', 'tools/hooks/', 'tools/git-hooks/', 'src/twinqa/evals/'))
                                 or k in ('AGENTS.md', 'CLAUDE.md', 'docs/decisions.md')}
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(('HERMES_', 'CLAUDE', 'CODEX_THREAD', 'CODEX_SESSION'))}
        # No inherited editable installation or task workspace location.
        env.pop('VIRTUAL_ENV', None)
        env.pop('PYTHONPATH', None)
        inherited_venv = os.environ.get('VIRTUAL_ENV')
        if inherited_venv:
            env['PATH'] = os.pathsep.join(p for p in env.get('PATH', '').split(os.pathsep)
                                         if not Path(p).resolve().is_relative_to(Path(inherited_venv).resolve()))
        if agent == 'codex' and codex_home is not None:
            env['CODEX_HOME'] = str(Path(codex_home).resolve())
        elif agent == 'codex':
            # Only authentication is inherited, never user AGENTS.md, plugins,
            # sessions, memory or config. Credentials are removed in finally.
            home = run_dir / 'agent-home'
            home.mkdir()
            auth = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'auth.json'
            if auth.is_file():
                shutil.copyfile(auth, home / 'auth.json')
                (home / 'auth.json').chmod(0o600)
            env['CODEX_HOME'] = str(home)
        if ticket:
            # Defense against accidental publication, not an OS security boundary [D159].
            env.update(GIT_CONFIG_COUNT='2', GIT_CONFIG_KEY_0='remote.origin.pushurl',
                       GIT_CONFIG_VALUE_0='disabled-publication://eval',
                       GIT_CONFIG_KEY_1='protocol.allow', GIT_CONFIG_VALUE_1='never',
                       GH_HOST='publication-disabled.invalid', GH_PROMPT_DISABLED='1')
        with (run_dir / 'transcript.jsonl').open('wb') as stdout, (run_dir / 'stderr.log').open('wb') as stderr:
            process = subprocess.Popen(executable(argv), cwd=worktree, env=env, stdout=stdout, stderr=stderr,
                                       stdin=subprocess.DEVNULL, start_new_session=(os.name != 'nt'))
            try:
                result['session_exit'] = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                stop(process)
                result.update(session_exit=124, error='session timeout')
        evaluation_after = evaluation_inventory(worktree, evaluation_before)
        if ticket:
            evaluation_after = {k: evaluation_after.get(k) for k in evaluation_before}
        changed = sorted(name for name in evaluation_before.keys() | evaluation_after.keys()
                         if evaluation_before.get(name) != evaluation_after.get(name))
        result['changed_evaluation_inputs'] = changed
        result['protected_inputs_unchanged'] = (not changed and inventory(worktree) == before
                                                and (etalon is None or sha(etalon) == expected_sha))
        result['head_unchanged'] = git(worktree, 'rev-parse', 'HEAD') == commit
        if ticket:
            actual_branch = git(worktree, 'branch', '--show-current')
            (run_dir / 'branch.txt').write_text(actual_branch, encoding='utf-8')
            (run_dir / 'local.diff').write_text(git(worktree, 'diff', '--binary', commit), encoding='utf-8')
            result.update(branch=actual_branch, ticket=ticket['number'],
                          solution_commit=git(worktree, 'rev-parse', 'HEAD'),
                          committed=not git(worktree, 'status', '--porcelain', '--untracked-files=all'))
        _, bench, _ = eval_run(ROOT / 'evals', task='capability-ticket' if ticket else 'capability-b01', main=run_dir,
                                branch='capability', output=run_dir / 'evals-capability', cwd=repo)

        # Feed native Codex events to the existing procedural graders unchanged;
        # their Claude-only parser reports unsupported records as not measured.
        # Claude stream-json is not a full session transcript, so it is not routed
        # through the Claude evidence glob (that could create vacuous passes).
        if agent == 'codex':
            transcripts = run_dir / 'logs/transcripts'
            transcripts.mkdir(parents=True)
            shutil.copyfile(run_dir / 'transcript.jsonl',
                            transcripts / f'capability-prnone-{uuid.uuid4()}.jsonl')
        _, procedural, _ = eval_run(ROOT / 'evals', suite='regression', main=run_dir,
                                     branch='capability', output=run_dir / 'evals-procedural', cwd=repo)
        result.update(benchmark={k: bench[k] for k in ('passed', 'failed', 'not_measured')},
                      procedural={k: procedural[k] for k in ('passed', 'failed', 'not_measured')},
                      procedural_reason='no Claude transcript; native CLI stdout retained, unsupported by procedural graders')
        if changed:
            # Raw reports remain available for diagnosis, never accepted as evidence
            # after their evaluation inputs changed (even with unchanged HEAD).
            result['benchmark_reported'] = result['benchmark']
            result['benchmark'] = {'passed': 0, 'failed': 1, 'not_measured': 0}
            result['error'] = 'evaluation inputs changed: ' + ', '.join(changed)
        if ticket:
            result['local_pr'] = result.pop('benchmark')
        result['passed'] = (result['session_exit'] == 0 and bench['exit_code'] == 0
                            and procedural['exit_code'] == 0 and result['protected_inputs_unchanged']
                            and (result['committed'] and result['solution_commit'] != commit if ticket else result['head_unchanged']))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result.update(error=f'{type(exc).__name__}: {exc}', passed=False)
    finally:
        cleanup_errors = []
        home = run_dir / 'agent-home'
        for target in (home, worktree if created else None):
            if target is not None and target.exists():
                try:
                    shutil.rmtree(target)
                except OSError as exc:
                    cleanup_errors.append(f'{target.name}: {exc}')
        if created and not worktree.exists():
            try:
                git(repo, 'worktree', 'remove', str(worktree))
            except subprocess.SubprocessError as exc:
                cleanup_errors.append(f'worktree registration: {exc}')
        if ticket and created:
            try:
                git(repo, 'branch', '-D', branch)
            except subprocess.SubprocessError as exc:
                cleanup_errors.append(f'branch cleanup: {exc}')
        result['cleanup'] = not cleanup_errors and not worktree.exists() and not home.exists()
        if not result['cleanup']:
            result.update(passed=False, cleanup_errors=cleanup_errors)
        result['elapsed_seconds'] = round(time.monotonic() - started, 3)
        (run_dir / 'reference.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--run-dir', type=Path, required=True)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--etalon', type=Path)
    inputs.add_argument('--ticket', type=int, help='Closed pilot ready-for-agent documentation/test issue')
    parser.add_argument('--agent', choices=('codex', 'claude', 'deepseek'), default='codex')
    parser.add_argument('--model')
    parser.add_argument('--codex-home', type=Path, help='Operator-prepared context; never copied or deleted')
    parser.add_argument('--isolation', default='private context; OS sandbox')
    parser.add_argument('--command-json', help='Explicit argv array; placeholders: {prompt}, {output}, {run}, {worktree}, {etalon}')
    parser.add_argument('--ref', default='main')
    parser.add_argument('--timeout', type=float, default=1800)
    args = parser.parse_args(argv)
    try:
        ticket = fetch_ticket(args.ticket, args.repo) if args.ticket is not None else None
        result = launch(args.repo, args.run_dir, args.etalon, ticket=ticket, agent=args.agent, model=args.model,
                        command=json.loads(args.command_json) if args.command_json else None,
                        ref=args.ref, timeout=args.timeout, codex_home=args.codex_home,
                        isolation=args.isolation)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f'capability-b01: {exc}', file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
