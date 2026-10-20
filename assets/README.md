# Asset store (#350)

Fixed workstation store: **`C:/x/assets`**. Google Drive is the mirror; Dropbox is rejected.
Only JSON, schema, documentation and code go into Git. Never add binaries to Git/LFS.
`--root` overrides the workstation root for isolated tests or another disk.

## Inventory and provenance

`manifest.json` covers MAF union/NPM sources and specification, Flora **v003**, Win_Typical
**v001**, and Vatutino Ground **v014** (NPM, intermediate VPM and final VPM+UCX).
Every SHA-256 and byte size was measured from the existing `recorded_path` on 2026-10-20;
the six previously published digests matched. `recorded_path` is provenance, NOT an
automatically trusted copy source. `source` cites repository metadata and is required and nonblank [D151].
`licence` is optional. All licences are unknown (`null`); a documented source does
not grant redistribution rights. MAF versions remain `null`: upstream records do not
name a release. Do not invent one or interpret the inventory as delivery acceptance.

Copy the recorded source files, read-only, into the corresponding `local_path` beneath
the store before syncing. This tool does not move/delete sources or automatically import
arbitrary `recorded_path` values. Missing files or a different hash exit nonzero before
any backend writes; it will not silently repair a bad local copy. Checksum and positive
integer byte size are mandatory, non-null verification evidence in both schema and runtime.
A partial entry rejects the entire batch before backend/report writes, even alongside valid
entries. The checked-in initial inventory has all eight checksums and sizes populated.

## Offline first

```bash
uv run python tools/assets/sync.py
uv run python tools/assets/sync.py --root C:/x/assets --out tmp/assets-report.json
```

Both commands are **dry-run**: no copy, report file, login or remote command. JSON goes
to stdout. An unpopulated store exits 1 with `missing_file`; a populated matching store
exits 0 with `status=match`, `credentials=absent`, `drive_link=pending`.
`--apply --out tmp/assets-report.json` writes a local report without requiring Google.
The manifest is never rewritten: review report links and update `drive_link` explicitly.
Report destinations may not alias the manifest, any local asset (including hardlinks
and absent paths), or any planned mirror destination. Path traversal is rejected.

## One-time user setup (not performed by the agent)

Choose either method and tell the board which was authorised. No credentials are stored
in Git. No Google client is installed by this PR and no cloud upload was exercised here.

### rclone

Install the current stable rclone from <https://rclone.org/downloads/>. Run `rclone config`
and create a Google Drive remote (for example `gdrive`). Authorise it in your browser.

```bash
export AGR_RCLONE_REMOTE='gdrive:AGR-assets'
uv run python tools/assets/sync.py --backend rclone
uv run python tools/assets/sync.py --backend rclone --apply --out tmp/assets-rclone.json
```

Apply first queries `rclone backend features` (read-only). Local backend roots participate
in the same alias/containment preflight as desktop folders, including missing targets and
hardlinks. Opaque wrapped/overlay backends or unavailable filesystem identity fail before
copying; use a direct Google Drive remote or a direct LOCAL remote for synthetic tests.
Dry-run does not query backend features or invoke rclone.

Apply uses `rclone copyto --ignore-existing --checksum` for each verified local file,
then verifies remote size and MD5 via `rclone lsjson --stat --hash --hash-type MD5`.
A different existing remote file is left unchanged and reported as an error; nothing is
deleted. Its file ID is used for an authenticated Drive URL;
the tool never invokes `rclone link` or changes sharing permissions. Missing IDs stay
`pending`. Copy errors are nonzero;
a batch is not transactional (earlier successful uploads can remain). Re-run safely.
No executable/remote configuration means offline validation, not a login prompt.

### Google Drive for desktop

Install from <https://www.google.com/drive/download/> and sign in once. Prefer an explicit
existing folder inside **My Drive**; the tool cannot prove that a generic directory is
actually managed by Drive. No G: drive is assumed to exist.

```bash
uv run python tools/assets/sync.py --backend drive-desktop --drive-root 'G:/My Drive/AGR-assets'
uv run python tools/assets/sync.py --backend drive-desktop --drive-root 'G:/My Drive/AGR-assets' --apply --out tmp/assets-desktop.json
```

Apply copies new files and reads each copy back to check SHA-256; matching targets are
idempotent and differing targets are rejected. The Drive folder must be separate from
the local store. Desktop upload completion and share-link creation remain user checks:
a filesystem copy is NOT proof of cloud publication. Desktop links stay `pending` unless
a valid link was already recorded in the manifest. Without a mounted/configured folder,
local validation still works with pending links. Dry-run never invokes either backend.
