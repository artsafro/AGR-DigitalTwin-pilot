# Blender startup crash evidence — t_b205c8e1

Two crashes at the same address; no third Blender attempt.

## Attempt 1 — v1 source, before environment repair

```text
Error   : EXCEPTION_ACCESS_VIOLATION
Address : 0x00007FF6FCE42509
Module  : blender.exe
Thread  : 000bfd90
Blender 5.1.2 (hash ec6e62d40fa9 built 2026-05-19 01:37:34)
Writing: C:\Users\artsafro\AppData\Local\Temp\blender.crash.txt
```

Exit 11. Repaired command environment: TEMP/TMP/TMPDIR under the worktree,
`--threads 1 --disable-autoexec`; factory preflight passed. The next v1
structure extraction succeeded (exit 0).

## Attempt 2 — in-scope revised lightning-rod FBX, repaired environment

```text
Error   : EXCEPTION_ACCESS_VIOLATION
Address : 0x00007FF6FCE42509
Module  : blender.exe
Thread  : 000c8408
Blender 5.1.2 (hash ec6e62d40fa9 built 2026-05-19 01:37:34)
Writing: C:\Users\artsafro\agr-pilot\AGR-DigitalTwin\.worktrees\t_b205c8e1\tmp\dcc-temp\blender.crash.txt
```

Exit 11. `remaining-structure-runs.json` pins the attempted source and elapsed
time. Stopped under the two-same-cause-failures rule; no further DCC retries.
