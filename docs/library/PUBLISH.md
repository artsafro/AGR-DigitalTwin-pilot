# Library publish — agent-made assets into the AGR library (#1743)

**Кратко.** Агент кладёт в библиотеку то, что намоделил (МАФ, Флора, окна, крышное оборудование [D372]),
одной командой `agr library publish <партия>`: приём копии партии → дубль/вариант/новый → библиотечное имя →
проверка ВПМ и НПМ → неизменяемая версия `vNNN` на Диске + черновик (`draft`) в каталоге git → лист превью
Артёму → пересборка поискового индекса. Черновик сразу виден другим агентам со статусом `draft`; после его «ок»
(`agr library accept`) запись становится `accepted` [D421]. Браузер `assets` в AGR Tools показывает только принятые [D371].

## Where things are [D368]

| What | Where |
|---|---|
| Files (immutable versions) | `G:/Мой диск/AGR-assets/<kind>/<name>/vNNN/` (+ `RECORD.json`, `SHA256SUMS.txt`) |
| Catalogue (agents search this, not folders) | `library/published/catalogue.json`, schema `schemas/library_published.schema.json` |
| Core + CLI | `tools/library/publish.py` (`agr library publish\|accept\|reject\|reindex\|check-job`) |
| Search index (rebuilt on every publish / accept / reject) [D421] | `library/assets/maf_unified.json` |
| Read path | `publish.available()` (accepted + draft); AGR Tools `assets` browser: `assets_core.scan_maf` + `published_gate` (accepted only) |
| Sheets for Artem | `G:/Мой диск/AGR-evidence/<issue>-library-publish/<batch>/sheet.md\|.html` |

Kinds: `maf`, `flora`, `windows`, `roof_equipment`. `materials` is refused (later).

## Commands

```bash
# 1. copy the batch (originals in AGR-assets/_inbox stay read-only), then
agr library publish C:/x/library-publish/inbox/<batch> --kind maf --issue <N> \
    --evidence "G:/Мой диск/AGR-evidence/<N>-library-publish/<batch>" [--identity ids.json] [--blender EXE]
# 2. Artem reads the sheet; on his «ок»
agr library accept <Name>[@vNNN] ... --words "<his words>"            # draft -> accepted
agr library reject <Name>[@vNNN] --words "<his words>"                 # -> rejected + _inbox/<batch>/REJECTED.md
```

Exit: 0 done, 1 a QA failure / refused record, 2 invalid input. `--assets-root` defaults to `G:/Мой диск/AGR-assets`;
`--catalogue` to the git catalogue.

## Stages (skeleton cell `library-publish`, `docs/agents/SKELETONS.md`)

1. `intake` — objects of the batch copy: an A101 archive `<Name>.zip` with `<Name>_high.fbx` (VPM) / `_low.fbx`
   (NPM) and sidecar json, or an object folder with one `*_GroundEl*.fbx` (MAF). A work folder whose code matches an
   archive article is "superseded by archive"; scripts, loose textures (materials later) and other files are drops
   with a reason. Empty batch, unknown kind, two FBX in one folder, an object listed twice → error.
2. `identify` — against `library/assets/maf_unified.json` (A101 + legacy) and other published names by article key:
   `duplicate` (same maker, size within 10 %, `intake_identify.dims_check`) is NOT registered; `variant` (same
   article, other maker or size, or size unknown) and `new` are registered. A previous version of the same library
   name is not a duplicate: publishing again gives `vNNN+1`.
3. `name` [D369] — sidecar identity, else `--identity` JSON `{object: {manufacturer, title_ru, article}}` with a
   source per entry, else `AGR_<kind>_<Name>_<NNN>`. Transliteration and ё=е from `assets_library.translit`.
   A manufacturer without an article or object name is an error. Library names only; delivery names stay per D166.
4. `qa` — each profile's FBX is read back by `tools/blender/fbx_readback.py`; checks: non-empty mesh, triangles,
   0 n-gons, topology measured, a material on every mesh and texture maps on every used material, pivot/seating
   (A101 standard, `library/assets/INTAKE.md` step 5: MAF and roof equipment XY centred ±0.01 m, base at 0 ±0.005 m;
   Flora [D100]: lowest vertex −0.10 ±0.005 m;
   windows: bounds from [0,0,0]), MAF `twinqa.maf_checks.maf_findings` (smoothing, flips). A missing NPM or VPM is a
   failing check. QA failure still registers the draft (Artem sees it); `accept` refuses it unless `--despite-qa`.
5. `register` [D370] — copies the object files into `<kind>/<name>/vNNN.partial/`, checks every copy's SHA-256, writes
   `RECORD.json` + `SHA256SUMS.txt`, renames to `vNNN`. An existing `vNNN` or `vNNN.partial` is never written; an
   assets root overlapping the batch is refused before any write.
6. `sheet` — one new folder per batch (never overwritten): table object / identify / name / version / QA / findings /
   preview, the drop list, `sheet.html` contact view, `SHA256SUMS.txt`, `publish.json`.
7. `index` [D421] — at the end of every `publish`, `accept` and `reject` the search index
   `library/assets/maf_unified.json` is rebuilt (`publish.rebuild_index`): A101 rescanned from
   `G:/Мой диск/AGR-assets/maf/a101` (headless `assets_core.scan_maf`, unchanged zips reuse the scan cache in
   `~/.cache/agr-library-index`) + legacy Union + every `draft` / `accepted` published MAF record
   (`source: published`, `status`, `path: maf/<name>/vNNN`). Drive not reachable: the A101 part is kept, the published
   part is still rebuilt. Commit the rebuilt index with the catalogue. `agr library reindex` rebuilds it by hand.

## Read path [D421]

Agent-made versions are visible to every agent as soon as they are published: `publish.available(catalogue)` returns
`accepted` and `draft` records (accepted first, each with its `status`), and the search index lists them too.
An agent prefers an `accepted` record; it may reuse a `draft` and then writes in its report «использован черновик
`<Name>@vNNN`». Artem's «ок» on reuse (`agr library accept`) turns it into `accepted`. `rejected` is never offered.

The frozen AGR Tools assets browser keeps the [D371] gate: `assets_core.scan_maf` hides every zip under
`<name>/vNNN/` that the catalogue does not list as accepted, every `vNNN.partial`, and all published versions when the
catalogue is missing or unreadable (`report.hidden_unaccepted`); `publish.available(catalogue, drafts=False)` is that
accepted-only list. A101 archives outside the publish layout are unchanged.

## Job close-out guard [D421]

```bash
agr library check-job jobs/<ID> [--outputs <job outputs folder>]   # exit 1 = an unpublished MAF master
```

A MAF master is an object FBX / MAX `<key>_GroundEl*` or `<key>_high|_low`, or an A101 archive with a `_high.fbx`
member, among the `job.yaml` artifacts and the `--outputs` folders; delivery objects `SM_<Address>_...` are not
masters. It has a library entry when a catalogue record (any status) has its SHA-256, its name or its object as
`origin.object`, or an A101 / indexed record has its name. Publish it as a draft before closing the job.
