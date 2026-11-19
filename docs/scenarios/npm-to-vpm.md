# Existing NPM -> VPM conversion workflow

**Кратко:** без таблицы сначала восстанавливаем provisional ID из ячеек атласа;
неоднозначные материалы не угадываем. Затем проверяем вместимость UDIM до записи.
Неразрешённый вход даёт diagnostic/blocked, не сертификат VPM.

## Read first

- `docs/domain/areas/derivation.md` (DER-04/10/11/12).
- `docs/domain/areas/uv-atlas.md` (UV-06/09/10/11/12/13).
- `docs/agents/SKELETONS.md`, `npm-to-vpm`; `docs/agents/skeletons.json`.
- Existing `docs/experiments/npm.to_vpm.md`, `adapters/max/agr_tools/npm2vpm_core.py`.

## Contract

Name the immutable source version/hashes, atlas and units, output copy, presence of
`npm_table.json`, explicit material mapping (if known) and allowed cleanup. Layout
IDs are numbered by cells, not semantic/library approval. Never infer glass/window
semantics from colour. This workflow crosses `oks-npm` -> `oks-vpm`; it is selected
explicitly in the job config, not by changing profile routing of ordinary jobs.

## Route

One `skeleton.json`, no parallel job chain. `npm-ids` -> `npm-udim-fit` ->
`npm-to-vpm` -> `readback` (including xView) -> `checker` -> `package-vpm` -> `validate`.
Standard before/after stage hooks remain available; no gap replacement.

With table: validate it, use `npm.to_vpm` table mode; no recovered IDs replace its
provenance. Without table: `agr npm-ids SOURCE NEW_OUT --profile facade`, then
regions mode. `npm2vpm_core.plan` is the read-only planning option when a native
conversion is not yet safe. Each ID gets area, extent after region_uv, required
extent at the target density, texel bounds and straddle diagnostics. Non-fit stops
before VPM writes and requires explicit user policy. An answered seam policy is
not authority to ignore unassigned faces, crop mixed materials or delete faces.

## Proof and current limit

G22: `jobs/G22/npm2vpm-1630/RESULT.md`. Numbered atlas/model sheets, per-face
assignment, exact unresolved lists, source drops and native-copy readback stay in
external evidence. A blocking finding with an owned follow-up is an allowed
outcome for issue #1630, not a certified VPM package. Downstream stages stay
not_run until a valid conversion exists. VPM geometry refinement belongs to
#1618/#1619; library mapping and Max UI are separate work.
