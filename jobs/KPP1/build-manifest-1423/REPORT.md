# KPP1 #1423 — build manifest: a roof edit in a master copy makes the stale NPM/VPM set refused

## Кратко (RU)

- Мастер A — копия quad-мастера KPP1 `SM_Kpp_1.quad-v002.fbx` (#1372, sha `7a95e9ca…`). NPM `0000_Kpp_1_01.fbx`
  получен из него в #1372 (`run-quad-v002-r6b`, `agr vpm-to-npm`). Ground v004 из #1416 вписан в систему R1 мостом
  #1371 (`jobs/KPP1/delivered-1371/mapping.json`); его запись производства тоже называет мастер этой сборки. VPM —
  экспорт меша мастера (Main, MainGlass, 4 UCX) в Blender + PNG/GeoJSON v008.
- **Базовая сборка (A):** `agr build-manifest build` прочитал каждый FBX из ZIP (владелец экспорта FBX): размеры,
  положения частей, материалы, UV, привязка UCX к видимому мешу (`UCX_SM_Kpp_1_Main_001..004 -> SM_Kpp_1_Main`).
  `agr validate`: V001 «build manifest» — **pass** для NPM и VPM; одинаковый мастер у обоих пакетов.
- **Правка крыши в копии мастера (B):** 912 верхних граней крыши (z = 8.65 м) `SM_Kpp_1_Main` подняты на 0.30 м.
  - NPM и VPM, собранные из A, с `--master B` — **fail `manifest_master_stale`**, exit 1.
  - VPM FBX переэкспортирован из B, а PNG/GeoJSON и NPM остались от A — **fail `manifest_master_mismatch`**
    (артефакты называют разные ревизии мастера), exit 1.
  - `qa.package` над NPM(A) + VPM(B) — **`manifest_cross_master`** для обоих пакетов.
- Это тестовая копия: исходные файлы не изменялись; пакеты не являются поставкой. Итог доставки KPP1 не меняется
  (открытые строки #1416 остаются).

## Run

```bash
export DT_BLENDER="C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"
uv run python jobs/KPP1/build-manifest-1423/prove_stale_1423.py C:/x/ev_t_63caf81f/kpp1-r3
# a second run on the same folder -> FileExistsError, nothing written
```

`kpp1-r1` was a first run whose VPM export joined all meshes into one (not the master's structure); `r2` keeps the
master meshes; `r3` is the same run with the shared Blender runner and the package_core ZIP owner (duplicate guard). All three gave the same verdicts.

## Evidence

`G:/Мой диск/AGR-evidence/1423-kpp1-build-manifest/r3/` + `SHA256SUMS.txt` (sha `7775d97d…`, 121 files: r2 and r3; copy:
[evidence-SHA256SUMS.txt](evidence-SHA256SUMS.txt)). Summary of every verdict: [proof-r3.json](proof-r3.json),
checked by `tests/jobs/test_kpp1_build_manifest_1423.py`.

| Step | Package | Master given | V001 build manifest | exit |
|---|---|---|---|---|
| A | `pkg-A/0000_Kpp_1.zip` | A | pass | 2 (other stages not_run/review) |
| A | `pkg-A/SM_Kpp_1.zip` | A | pass | 1 (other VPM stages of this test copy) |
| A vs B | `pkg-A/0000_Kpp_1.zip` | B | fail `manifest_master_stale` | 1 |
| A vs B | `pkg-A/SM_Kpp_1.zip` | B | fail `manifest_master_stale` | 1 |
| B | `pkg-B/SM_Kpp_1.zip` (FBX from B, textures from A) | B | fail `manifest_master_mismatch` | 1 |
| B | `pkg-B/0000_Kpp_1.zip` (stale copy) | B | fail `manifest_master_stale` | 1 |
| B | NPM(A) + VPM(B) via `package_core.cross_masters` | — | `manifest_cross_master` ×2 | — |
