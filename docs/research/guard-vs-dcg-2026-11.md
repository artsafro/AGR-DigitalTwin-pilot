# Guard vs destructive_command_guard (2026-11-10)

Plan step 1.2 (`docs/plans/telegram-findings-rollout.md`). Source: GitHub
`Dicklesworthstone/destructive_command_guard` at `acbe0665` (2026-11-08), read only: pack docs
`docs/packs/{core,strict_git,system,careful_company_running_windows}.md` and `src/packs/windows/filesystem.rs`.
Ours: `.claude/hooks/guard.py` `SHELL_RULES`. Policy kept: every match asks (dcg denies); no existing rule changed.

Action: **port** = new rule + test in `tests/test_guard_permissions.py` (`DCG_PORTED_ASK` / `DCG_PORTED_ALLOW`);
**have** = already covered; **skip** = reason given.

| Pattern / command class | dcg | ours before | Action |
|---|---|---|---|
| `git push` force / mirror / delete / refspec | deny (strict: any force) | asks on every `git push` | have |
| `git reset --hard` | deny | ask | have |
| `git reset --merge` | deny | — | port |
| `git clean -f` (dry run allowed) | deny | asks on every `git clean` | have (stricter) |
| `git branch -D` / force delete | deny | ask | have |
| `git branch -d` (safe delete) | deny | allowed on purpose (#1027) | skip: deliberate |
| `git checkout .` / `git restore .` | deny | ask | have |
| `git checkout -- <path>`, `git restore <path>` | deny | — | skip: per-path recovery is a documented workflow (`docs/ARCHIVE.md`) |
| `git checkout -f`, `git switch -f / --discard-changes` | deny | — | port |
| `git read-tree --reset` | deny | — | port |
| `git rm -f` | deny | — (`git rm -r` already asks) | port |
| filter-branch / filter-repo / rebase / `update-ref -d` / `lfs migrate` | deny | ask | have |
| `git reflog expire / delete`, `git gc --prune` | deny | — | port |
| `git stash drop / clear` | deny | — | port (stash stack is shared by all worktrees) |
| `git lfs prune / uninstall` | deny | — | port (repo uses LFS, 16 patterns) |
| `git worktree remove` | deny (strict) | — | port `--force` only; plain remove refuses a dirty tree |
| `git show ref:path > path`, alias / dynamic-token analysis | deny | — | skip: needs a shell parser |
| `git commit --amend`, `cherry-pick`, `add -A`, push to main | deny (strict) | — | skip: normal workflow; push already asks |
| `rm -rf` (flags first) | deny | ask | have |
| `rm -f -r`, `rm --recursive`, `rm x -r` | deny | — | port |
| PowerShell aliases `ri/del/erase/rmdir/rd -Recurse`, `Remove-Item -r / -Re` | deny | only `Remove-Item -Rec(urse)` | port |
| cmd `rd /s` | deny | ask | have |
| cmd `del /s`, `erase /s` | deny | — | port |
| `[IO.Directory]::Delete`, `DirectoryInfo.Delete($true)` | deny | — | port |
| `find -delete`, `robocopy /MIR` | deny | ask | have |
| `unlink`, `truncate`, `shred`, `dd of=`, `tar --remove-files`, `mv`/`cp`-then-delete | deny | — | skip: POSIX tools rarely used here; single-file deletes are not asked by our policy |
| redirects / `tee` into `.git/`, credential files, login scripts | deny | — | skip: needs a shell parser; open item below |
| `Clear-Content` | deny | — | skip: consistent with `Set-Content` / `>` overwrites not being asked |
| `Clear-RecycleBin` | deny | — | port |
| `format X:`, `Format-Volume`, `Clear-Disk`, shadow-copy delete (vssadmin / wmic / Win32_ShadowCopy) | deny | — | port |
| Defender / firewall / BitLocker / event-log tampering | deny | — | port as "security settings change" |
| `Set-ExecutionPolicy`, `reg add/delete`, `setx` | deny | ask | have |
| `powershell -EncodedCommand`, download piped into `iex` / `sh` | deny | — | port |
| agent hook config tamper (`.claude/settings.json`, hooks) | deny | — | skip: would ask on every harness PR; open item below |
| `gh gist create` | deny | — | port |
| `gh release upload`, `secret set`, other HTTP / email / tunnel / scp egress | deny | — | skip: outside this guard's scope; GitHub writes already gated by push / PR merge |
| fork bomb, Linux disk tools (`mkfs`, `fdisk`, `mdadm`, ...) | deny | — | skip: not on this Windows host |

Counts (rows): 17 ported as 14 new rules, 10 already covered, 10 skipped.
Tests: 57 ask commands x 2 protocols + 30 safe neighbours.

Open items:
- Pre-existing false positive: `git stash push ...` asks as "git push publishes to a remote" (not changed here).
- Writes into `.git/` and agent hook configuration are not guarded; both need a shell parser or a
  file-tool rule with an exception for harness branches.
