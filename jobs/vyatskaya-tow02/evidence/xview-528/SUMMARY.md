# xView runner #528: native 3ds Max 2024 startup evidence (measured 2026-10-24)

Run: `python dcc_batch.py max --version 2024 --file tools/qa/xview_dump.ms` (3dsmaxbatch, shared lock) on COPIES
under C:/x/xview-528/in/. XVIEW_OUT=<run dir>, jobs.txt with a nonce. The user's interactive Max was not touched.
`xview_parity.py --check-run` exit 0 for both runs. Source SHA-256 before == after (hashes_*.txt); the copies equal the sources.

| job | input | node | faces | vertices | acceptance |
|---|---|---|---|---|---|
| v005_plain | export-v005 FBX | SM_..._013_Main | 185 | 0 | 185 faces: ok |
| 013_plain | sceene.max copy | SM_..._013_Main | 0 | 10 | faces 0 / vertices 10: ok |
| 013_weld | same | same | 0 | 0 | faces 0 / vertices 0: ok |
| 013_weldpoly | same | same | 0 | 10 | weld then Poly: vertices 10: ok |

Bug found by the native run and fixed in this PR: the dump wrote `"type":"vertices"` (MAXScript name printing),
check_run requires `#Vertices` / `#Faces`; the first native run failed check_run, the fixed script passes.
