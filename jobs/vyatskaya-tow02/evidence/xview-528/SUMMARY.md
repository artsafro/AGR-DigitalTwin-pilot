# xView runner #528: native 3ds Max 2024 evidence (measured 2026-10-24)

Run: `python dcc_batch.py max --version 2024 --file tools/qa/xview_dump.ms` (3dsmaxbatch, shared lock) on COPIES
under C:/x/xview-528/in/. XVIEW_OUT=<run dir>, jobs.txt with a nonce. The user's interactive Max was not touched.
`xview_parity.py --check-run` exit 0 for both runs. hashes_*.txt are committed in the same dir
(`hashes_before.txt`, `hashes_after_src.txt`, `hashes_after_copies.txt`). PowerShell comparison of (hash, name)
on 2026-11-02: the two source rows in `hashes_after_src.txt` match the same names in `hashes_before.txt` (2/2:
export-v005 FBX `ff8994dc4b7c…` and `sceene.max` `d4e209269c98…`). The two copy rows also listed in
`hashes_before.txt` (`in/v005.fbx`, `in/sceene013.max`) match `hashes_after_copies.txt` (2/2, same two hashes).
`hashes_before.txt` has those two extra copy rows, so the full before set is not the same set as after_src.

| job | input | node | faces | vertices | acceptance |
|---|---|---|---|---|---|
| v005_plain | export-v005 FBX | SM_..._013_Main | 185 | 0 | 185 faces: ok |
| 013_plain | sceene.max copy | SM_..._013_Main | 0 | 10 | faces 0 / vertices 10: ok |
| 013_weld | same | same | 0 | 0 | faces 0 / vertices 0: ok |
| 013_weldpoly | same | same | 0 | 10 | weld then Poly: vertices 10: ok |

Historical (superseded 2026-10-24): the first native run failed check_run because the dump wrote `"type":"vertices"`
(MAXScript name printing) while check_run requires `#Vertices` / `#Faces`. The fixed script's measured rows above pass.
