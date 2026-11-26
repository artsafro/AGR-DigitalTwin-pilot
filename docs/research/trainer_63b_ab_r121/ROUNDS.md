# Round log, #121: 63B SKELETONS-first A/B

Head: `origin/main` 8531433d1f1a1e4860ce156fd29d7e0b20bf5903. Evidence dir: `C:/x/ev_t_cc06dd03/`. It is copied to
`G:/Мой диск/AGR-evidence/121-trainer-63b-ab/` together with `SHA256SUMS.txt`.

| round | what | result |
|---|---|---|
| 0 | Preflight on the bank copy where only `practice_ready` was changed (`bank_63b_admit_r0.json`, sha256 `e686dc75…`) | **fail**: 31 files of the scrubbed practice tree still point to the accepted versions or to the unscrubbed repo. `1619-body-training` appears in 2 files (`docs/research/autoresearch-trainer-tower-id.md`, `docs/research/body-training-1619/README.md`), `POLY63-B` in 10, `agr-pilot/AGR-DigitalTwin` in 20, `C:/x/trainer/runs` in 2. The positive trigger witness works: the scan fires on the current bank. The official 63B entry is **not isolated** as is. |
| 1 | Repair: the 31 files are added to the 63B `hidden_repo_paths`, in the copy only (`bank_63b_admit_r1.json`, sha256 `30fec481…`, 35 paths) | **pass**: 3865 files scanned, 71 scrubbed, 0 left, 0 hits in the prompt |
| 2 | A/B run: OLD = empty, NEW = `AGENTS.md` sha256 `fe83e898…` | see below |
