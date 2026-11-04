# Research: who creates `UsersartsafroAppDataLocalTemppytest_tmp/` in worktrees (t_c5990e13)

## Summary

- **Producer (verified): the Windows user-level environment variable `PYTEST_ADDOPTS=--basetemp=C:\Users\artsafro\AppData\Local\Temp\pytest_tmp`** (backslashes), inherited by every Hermes worker and every spawned Cursor/Codex shell. Neither a card, a profile SOUL, nor a repo file sets it.
- pytest splits `PYTEST_ADDOPTS` with `shlex` (POSIX mode): `\U`, `\a`, `\A`, `\L`, `\T`, `\p` lose the backslash -> `C:UsersartsafroAppDataLocalTemppytest_tmp`. On Windows `C:name` is relative to the cwd on drive C:, so the basetemp is created inside the worktree you run pytest from.
- Reproduced once (git-bash, `uv run --no-project --with pytest pytest -q`, one trivial `tmp_path` test): backslash value -> `UsersartsafroAppDataLocalTemppytest_tmp/` appears in cwd; the same value with forward slashes -> no dir (`ls` shows only `test_a.py __pycache__`).
- 27 such dirs existed at card time (28 on my re-count, incl. this card's own run), mtimes 2026-10-20 .. 2026-11-04. Provider is not the discriminator: all profiles that ran pytest in a worktree are affected (14 dirs touched by dt-worker-cursor runs, 14 by dt-worker, 2 codex, 1 deepseek, 1 agy; 26 also by dt-reviewer; sets overlap, per-task `task_runs.profile`).
- No branch ever committed one: `git log --all --name-only | grep -c pytest_tmp` -> 0 (only docs mention the name: `docs/HANDOFF.md:28`, `docs/experiments/hyp-748.md`, `docs/research/job-retro-tec26-oks-pr574.md`). It is NOT in `.gitignore` (`git check-ignore` prints nothing), so it shows as untracked and is one `git add -A` away from a commit.
- Fix: stop the source (set the variable with forward slashes) + defensive `.gitignore` line. Not applied here (report only).

## Findings

1. Env of the worker shell (verified, `env`): `PYTEST_ADDOPTS=--basetemp=C:\Users\artsafro\AppData\Local\Temp\pytest_tmp`, `PYTEST_DEBUG_TEMPROOT=C:\Users\artsafro\AppData\Local\Temp\pytest_tmp`, `TMPDIR=/tmp/pytest_tmp`, `TEMP=TMP=/tmp`. PowerShell `GetEnvironmentVariable("PYTEST_ADDOPTS","User")` returns the same backslash value, i.e. it is set at User scope in the registry, not per card. (Where/when it was set is not recorded; no script in `hermes_kanban/scripts`, `hermes_kanban/profiles`, profile configs or repo files contains `PYTEST_ADDOPTS`.)
2. Mechanism (verified by reproduction): backslash value -> mangled dir in cwd; forward-slash value -> none. pytest documents `PYTEST_ADDOPTS` as extra command-line options (https://docs.pytest.org/en/stable/reference/reference.html#envvar-PYTEST_ADDOPTS) - splitting rules are `shlex`, which is why backslashes are eaten (source claim, consistent with the reproduction).
3. Because the explicit `--basetemp=C:/x/<card>` on a card's command line is added after `PYTEST_ADDOPTS`, it wins when passed; the mangled dir appears whenever a worker/Cursor/reviewer runs pytest WITHOUT `--basetemp` (default runs, `uv run pytest -q <file>`, hooks that spawn pytest). Evidence in `~/.cursor/projects/*/agent-transcripts`: e.g. t_08bb3e43 Cursor ran `Remove-Item ...\t_08bb3e43\UsersartsafroAppDataLocalTemppytest_tmp -Recurse -Force; uv run pytest -q ...`; t_670f1a0f log shows hook subprocesses `...\t_670f1a0f\UsersartsafroAppDataLocalTemppytest_tmp\test_explicit_decisions_ask_pi0\.claude\hooks\guard.py` timing out (the mangled dir is also used as tmp_path root of real tests). 14 of 27 worktrees have a matching `~/.cursor/projects/<worktree>` log; 8 of them contain the literal `pytest_tmp` string.
4. Existing mitigation is per-worker folklore: `~/.hermes/profiles/dt-worker/skills/software-development/geoagr-knowledge-catalogue/SKILL.md:36` ("pass `--basetemp=C:/x/<card>` or delete that dir"). It treats the symptom and lives in one profile only.
5. Counts per provider (kanban `agr-pilot` board `task_runs.profile`, read-only): by profile of any run on the card - dt-worker-cursor 14, dt-worker 14, dt-worker-codex 2, dt-worker-deepseek 1, dt-worker-agy 1, dt-reviewer 26. Current `tasks.assignee` is misleading (reviewers inherit the card), so use runs.
6. Git history: 0 commits contain the path in any ref. Untracked only. mtime of a dir = last pytest run without `--basetemp`, not the card creation time.

## How it applies to this repository

- Repo has no setting of its own: `pyproject.toml`/`conftest.py` have no `basetemp`. `.gitignore` has no `/Users*pytest_tmp/` rule.
- AGENTS/worker prompts tell workers to pass `--basetemp=C:/x/<card>`, which works only if remembered on every invocation (hooks and Cursor sub-runs forget it).

## Proposed next tasks

1. **Set `PYTEST_ADDOPTS` with forward slashes (operator, User env)** - change the User variable to `--basetemp=C:/Users/artsafro/AppData/Local/Temp/pytest_tmp` (or unset it; `PYTEST_DEBUG_TEMPROOT` already gives a safe root). Input: new shell, run any test without `--basetemp`; expected: `git status --short` has no `Users*` entry (verified here: forward-slash value leaves cwd clean). Note: concurrent worktrees then share one basetemp, which pytest wipes per run -> prefer unsetting `PYTEST_ADDOPTS` and relying on `PYTEST_DEBUG_TEMPROOT`, or per-card `--basetemp`. Value S. Advances: none honestly named - `Archive: no roadmap link` (check `gh issue list --label roadmap` for a harness-reliability blocker before planning).
2. **`.gitignore`: `/Users*pytest_tmp/`** - before: `git status --short` shows `?? UsersartsafroAppDataLocalTemppytest_tmp/`; after: no line (and `git check-ignore -v` prints the rule). Prevents an accidental commit of test temp dirs. Value S. `Archive: no roadmap link`.
3. **Pre-commit/guard check** (separate card, not here): refuse staging of paths matching `Users*pytest_tmp*`. Value S. `Archive: no roadmap link`.

## Open questions for the user

- Who/what set the User-level `PYTEST_ADDOPTS` (a one-off, a Hermes installer step)? Can it be unset, given parallel worktrees would otherwise share `pytest_tmp`?
- The 27 existing dirs were not deleted (as requested); OK to remove them in a follow-up once nothing uses them?

## Not measured

- When the variable was created; whether a Hermes profile re-injects it at spawn (no hit in profile configs/scripts grepped); the other 13 worktrees' Cursor logs are absent or pruned, so their attribution rests on mtime plus `task_runs` only.
