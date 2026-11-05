# FNO registry `fno_codes_utf8.csv` — provenance

Owner decision: Artem, 05.11.2026 (team audit T04, open question 2, issue #908): the registry may be moved into
AGR Tools / the pilot as data.

| Field | Value |
|---|---|
| File | `standards/data/fno_codes_utf8.csv` (byte-exact copy, `-text` in `.gitattributes`) |
| SHA256 | `397e75e3ff1cb231359686d065cd4ebcd93ff8f789deaadefe8d4155594dff31` |
| Size | 43 075 bytes, UTF-8 with BOM, CRLF, `;`-separated, 471 lines (3 header lines) |
| Content | Classifier of functional-purpose types of capital construction objects (ФНО ОКС): groups `XXX`, subgroups `XXX XXX`, types `XXX XXX XXX` with their names |
| Primary source | SINTEZ AGR Checker 1.6.1 (Blender extension, SINTEZ.SPACE, manifest `license = SPDX:GPL-3.0-or-later`), `documents/fno_codes_utf8.csv`; the customer-side acceptance checker. Installed copy on Artem's laptop (`%APPDATA%/Blender Foundation/Blender/5.1/extensions/user_default/sintez_agr_checker/documents/`, dated 28.10.2026) has the same SHA256 |
| Route into the team | `AGR_Checker.zip` (team script, GeoAGR-private `sources/team-scripts/telegram/AGR_Checker.zip`, sha256 `0c1e5f7454bf9aa5183e5e9d1893f6b801b3f0123638278cbb97651748693e4d`), `AGR_Checker/data/fno_codes_utf8.csv` — same SHA256; its `fno_registry.py` names the source «реестр из открытого аддона Sintez AGR Checker» |
| Copied | 05.11.2026, from the AGR_Checker.zip copy; SHA256 verified against the SINTEZ 1.6.1 copy |
| Rights note | The table reproduces an official classifier (a normative list of codes and names), not program code. It ships inside a GPL-3.0-or-later package; this repository is private. Re-check before any public redistribution |

## How it is used

`src/twinqa/fno.py` reads the table (rows 4+; columns 1-6 = group name/code, subgroup name/code, type name/code)
into `{code: name}` for all three levels. `src/twinqa/geojson.py` (V011, used by `tools/qa/validate_package.py`
and AGR Tools `qa.package` / `qa.geojson`) applies it to OKS GeoJSON only, as SINTEZ 1.6.1 `hp_checks.py` does:

- `FNO_code not in registry` — fail: a 3/6/9-digit code that is not in the table;
- `FNO_name vs registry` — fail: the name differs from the table entry of that code (spaces ignored, case kept);
- no finding otherwise (the V011 `schema` pass covers it); an unreadable registry gives `FNO registry` not_run,
  never a pass. Ground GeoJSON is not checked against the registry (PKG-21).

## Updating

Replace the file only with a newer customer-checker copy, update the SHA256 here and `twinqa.fno.REGISTRY_SHA256`
(the unit test compares them), and record the source version and date.
