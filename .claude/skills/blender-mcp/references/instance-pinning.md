# Blender instance pinning and review-window lifecycle (#1541)

Use this procedure before every MCP call. Port 9877 being occupied by Blender is
not proof that the intended scene is connected. Never ask the user to save just
to make another window's in-memory edits visible: saving does not change which
process owns a socket. No add-on or persistent preference changes are needed.

## Inventory and expected-file gate

1. State the expected absolute path and, if already known, expected PID and
   creation time. Run this read-only PowerShell inventory from the terminal:

   ```powershell
   $ErrorActionPreference = 'Stop'
   $blenders = @(Get-CimInstance Win32_Process -Filter "Name='blender.exe'")
   $listeners = @(Get-NetTCPConnection -State Listen |
       Where-Object { $_.LocalPort -eq 9877 })
   $owners = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
   $blenders | ForEach-Object {
       $p = Get-Process -Id $_.ProcessId -ErrorAction Stop
       [pscustomobject]@{
           PID = $_.ProcessId; Created = $_.CreationDate
           Title = $p.MainWindowTitle; LaunchHint = $_.CommandLine
           Owns9877 = ($owners -contains $_.ProcessId)
       }
   } | ConvertTo-Json -Depth 3
   $listeners | Select-Object LocalAddress,LocalPort,OwningProcess |
       ConvertTo-Json -Depth 3
   ```

   Keep the output in task evidence, including every Blender PID, displayed
   open-file title and command line. A title or launch hint is **not proof** of
   the current open file: File > Open can change it without changing arguments;
   a title can show only a basename. Label non-owner current paths `unknown`
   unless separately identified through that instance's bridge/native UI.
   Empty lists, command errors, multiple owner PIDs, a non-Blender owner or an
   unavailable pinned PID all mean REFUSE. Require exactly one owner PID for
   9877, and retain its creation time; never silently choose the newest window.
   An owner different from the pinned PID/birth means REFUSE, even if both
   processes have opened the same file. Do not automatically repin on restart.
   Example: PID 11 has `A.blend`, PID 22 has `B.blend`, 9877 belongs to 22,
   expected is `A.blend`: REFUSE, not a read from 11 and not a request to save.
2. Identity-only exception: call `get_blendfile_summary_path_info` on the
   configured 127.0.0.1:9877 route, not a CLI-launched substitute. This is the
   only bootstrap read allowed before the expected-file gate passes. Require
   outer success and inner `status="ok"`; record the returned full path and
   saved/dirty state beside the owner PID. Re-run the inventory immediately
   afterwards; require the same owner PID and creation time. If the response is
   empty, partial, unsupported, unsaved (blank path), failed or ambiguous,
   REFUSE all scene/object reads. Do not infer a file from a stale response.
3. Compare the returned full current path to the expected absolute path using
   filesystem identity (`Path(actual).samefile(expected)` in Python, only when
   both paths exist); do not use a same basename, substring or launch argument
   match. Missing/inaccessible paths or comparison errors mean REFUSE. A
   different file means REFUSE even if the expected file is open in another
   Blender. Report `expected=<path>; actual=<path>; owner=<PID>; REFUSE`.
   A hardlink/junction alias of the same file is acceptable, not a second scene.
4. Only then read scene/datablock/object data. Recheck path-info and the OS
   owner after the read; discard data if either changed. Repeat the gate for
   every call, after a file switch, reconnect, restart or timeout; no cached
   receipt authorizes a later call. If identity changes repeatedly, stop live
   reads and use a headless versioned copy instead of racing the user's UI.
   This is an agent procedure, not an atomic transport lock: it cannot prove
   absence of an intervening switch restored between checks. Never claim that
   a historical PID/path receipt pins later requests.

## Review windows: no bridge, no window accumulation

- Separate the one MCP work instance from windows opened only for user review.
  Launch each review copy **without the MCP bridge**, using session-local
  factory preferences and disabled file autoexec (not merely `--offline-mode`):

  ```bash
  "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --factory-startup --disable-autoexec "<absolute-versioned-review-copy.blend>"
  ```

  Use terminal `background=true`. These flags avoid saved add-on autostart and
  file startup scripts; do not enable extensions, use `--online-mode`, or save
  preferences in this review window. Verify the new review PID owns no 9877
  listener and the previous work owner is unchanged. A failed launch or new
  listener is not a valid isolated review: stop and diagnose your own process.
- Record the native PID, creation time, exact review path and task that launched
  it. Before opening a newer review, close only your own superseded review
  windows; never user-owned or merely same-named processes. Recheck PID birth,
  title/file and dirty state in the native UI before closing. If user edits are
  dirty or state cannot be established, do not force termination: preserve the
  window, ask about those edits, and stop accumulating review windows.
- Close normally in the UI (or `taskkill /PID <own pid>` for a confirmed clean
  own review); never by image name. Confirm that exact process exited, then
  inventory 9877 again. Do not close the work instance while using its bridge.

## Regression boundary

The card permits a skill step instead of a check helper. This procedure uses
that option because only the live typed path-info response knows the current
file; OS launch arguments are insufficient. Pytest locks the procedure/order,
review flags and failure/cleanup requirements. It is not a mocked-process test
of runtime enforcement. Preserve a real two-process inventory as evidence;
never label synthetic process lists as live or claim automatic enforcement.
