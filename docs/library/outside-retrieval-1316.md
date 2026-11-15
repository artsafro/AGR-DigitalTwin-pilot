# Outside-agent retrieval receipt — #1316

## Current result (2026-11-13, A101-native route)

The earlier blocked probes below are retained as history, **not current completion
claims**. After the operator clarified A101-native extraction, four exact native
source variants were published as new v002 candidates (Tilia high/low; Acer Royal
Red high/low). Original RGBA, geometry and UVs are unchanged. RGB and alpha are
separated losslessly, not white-keyed or regenerated. Independent unauthenticated
readback matched **13/13 files**: the A101 MAX and four RGBA/RGB/alpha triplets.
Exact IDs, sizes and hashes: `library/flora/a101-native-v002.json`.

The portable three-asset selection is now
[`library/outside-retrieval-v001.json`](../../library/outside-retrieval-v001.json):

| Selection | Version SHA-256 | Boundary |
|---|---|---|
| MAF_0002 / TBO_konteyner | `ea43c19ac9d77ec240a79eea7f73db442025efa7dd05f06a3adc8ca71bf9c0be` | One source FBX, 137264 bytes; native Blender 5.1.2 readback: one mesh, 1420 polygons, **no external images** |
| Tilia cordata / A101 lipa_t1_h550_low v002 | `a95cdd49b7a4e0dd8b495e8947165a2f62cf21301440d17e4e6927dde57c4480` | Exact object in FLORIO_221.max + original RGBA + v002 RGB/alpha; object 866 triangles |
| Material 40 interior diffuse placeholder v001 | `7838298711c57ade49821a0e371c88d41f2804ae30983c9c25e514c2feb47320` | Published 565-byte diffuse placeholder map, not a complete VPM texture triplet |

The initial MAF_0001 probe exposed an unembedded image reference:
`1_Diffuse_1.1001_e5pokwfjvgc7.png`; Blender also warned about an unsupported Max
material link. That FBX alone is **not** a complete textured asset. Rather than
invent a missing dependency or call it a pass, the final documented selection uses
MAF_0002, whose source `fbx_materials.json` row lists no textures and whose fresh
Blender import confirms no external images. The original raw failure is retained.
MAF hashes are newly measured content pins, not inherited publisher release hashes.

### Real visual loop and answer

3ds Max 2026.3 (28.3.0.30732), headless, shared `dcc_batch.py` session lock,
centimeters, private copy of `FLORIO_221.max`. Read-only inventory preceded preview.
The A101 low/high Tilia objects have 866/1786 triangles, not the unrelated frozen
v003 catalogue's 357/830. Native material filenames select the matching RGBA variant.
A native scanline preview of the **original low geometry/UV/RGBA** was rendered and
visually read back: fully framed tree and visible cutout foliage on a neutral background.
Channel-split equivalence was checked byte-for-byte with Pillow; it is not a new
render of rebound v003 geometry and not complete profile/delivery QA.

- Version: `a95cdd49b7a4e0dd8b495e8947165a2f62cf21301440d17e4e6927dde57c4480`.
- Preview: `G:/Мой диск/AGR-evidence/1316-outside-retrieval/v002/tilia-source-low-v002.png`.
- Preview SHA-256: `8ceed9e2cca249b8565cff32f7ca3d7c89e5d855eb11e86d7d69f9bfbb295b64`.
- `hermes -p default send --to telegram:<configured-owner> --file tmp/telegram-request-1316.txt --json`
  returned success, message **4696**, mirrored=true; transport JSON was read back.
- Exact question: `принимаешь эту версию? Ответ: принять / отклонить + причина.`
- Artem's reply **4697**, replying to that message: **`Да, липа норм`**.
  The gateway mirror and explicit operator hash-bound relay corroborate the answer.
- Stored in `library/flora/visual-verdict-1316.json`, `maps.json`'s exact hash-keyed
  version and `a101-native-v002.json`: **approved for that version only**.
  Other Tilia versions are not approved by that reply.

The subsequent operator request to include Acer was also executed. Native text
`Text_klen_t7_h550` identifies **Acer platanoides Royal Red**. Preserve that cultivar:
Ginnala/Tataricum-labelled atlases are not substituted. `klen_t7_h550_low` has 826
triangles; its unchanged source preview has sparse reddish foliage (shown as is).
Separate request **4701** was sent, success/mirrored result read back:
`77ff8536585ee0a1ebf06d739d164881b7e9741b81bc309ef30f4585c74dfea3`.
Preview/logs/hashes: `G:/Мой диск/AGR-evidence/1316-outside-retrieval/acer-v002/`.
`visual-verdict-acer-1316.json` records **pending**, `answer=null`; no Tilia approval
is transferred. Accept/reject + reason is the only outstanding owner action for it.
It is **not** approval to substitute Royal Red into #1315's planting schedule.

### Portable current maps versus immutable previous releases

All 124 legacy C:/x slot paths in current `maps.json` move to the documented
AGR-assets route. **62 original v001 pairs are still unavailable** there, so their
current status is `missing`, with the exact historical approval words retained.
The three newer Drive-backed map entries are unchanged. This is an availability
correction, not broad texture regeneration, deletion, botanical cleanup or revocation
of historical approvals. New A101 candidates are nested by hash, never silently used
on unrelated `Tilia_cordata_*` or `Acer_platanoides_*` geometry.

The first ordinary catalogue rebuild correctly refused with `ValueError: maps changed`
from the existing immutable npm-light guard (affected run: **5 failed / 81 passed**).
That failure is retained, not relabelled green. Repair: preserve the exact original
map-input snapshot as `maps-v003-snapshot.json` (canonical LF SHA-256
`a20972b8bd7e94240416d7c70035d107be71c4f58789159dbc5b069bdb67afd6`).
The frozen catalogue/light release and pinned Vatutino route-A sheet reproduce from
that snapshot, not today's changed route/availability selection. No guard is weakened,
no light-map path is rewritten inside old native evidence, and no geometry is rebound.
A new regression still requires current-map input to refuse that frozen rebuild.
Old snapshot C:/x paths are **historical provenance**, not offered downloads.

### Reproduce a cold three-asset download

Clone this PR branch into an **unused directory** (later use the merged commit),
then read only `library/README.md` -> `library/outside-retrieval-v001.json`.
No desktop Drive mount, C:/x, auth, cookies, local caches or prior download root is needed.
From that clone run the following stdlib snippet with an unused destination:

```python
import hashlib, json, re, urllib.request
from pathlib import Path, PureWindowsPath
manifest = json.loads(Path('library/outside-retrieval-v001.json').read_text(encoding='utf-8'))
if manifest['schema'] != 'outside-retrieval-selection-v1':
    raise SystemExit('Unsupported manifest schema')
if set(manifest) != {'schema', 'shared_root', 'scope', 'assets'}:
    raise SystemExit('Unexpected manifest fields')
if not isinstance(manifest['assets'], list) or len(manifest['assets']) != 3:
    raise SystemExit('Expected three asset selections')
if [len(a['files']) for a in manifest['assets']] != [1, 4, 1]:
    raise SystemExit('Expected file counts [1, 4, 1]')
seen = set()
for asset in manifest['assets']:
    if set(asset) != {'asset', 'version_sha256', 'authority', 'boundary', 'files'}:
        raise SystemExit('Unexpected asset fields')
    if not re.fullmatch('[0-9a-f]{64}', asset['version_sha256']):
        raise SystemExit('Invalid asset version SHA-256')
    for record in asset['files']:
        if not {'path', 'download_url', 'sha256', 'bytes'} <= set(record) <= {'name', 'path', 'download_url', 'sha256', 'bytes'}:
            raise SystemExit(f'Invalid file fields: {set(record)}')
        if type(record['bytes']) is not int or record['bytes'] <= 0:
            raise SystemExit(f"Invalid byte count: {record['path']}")
        if not re.fullmatch('[0-9a-f]{64}', record['sha256']):
            raise SystemExit(f"Invalid SHA-256: {record['path']}")
        if not record['download_url'].startswith('https://drive.usercontent.google.com/download?id='):
            raise SystemExit(f"Unsupported download URL: {record['path']}")
        relative = Path(record['path'])
        if not relative.parts or relative.is_absolute() or PureWindowsPath(record['path']).drive or '..' in relative.parts:
            raise SystemExit(f"Unsafe path: {record['path']}")
        key = relative.as_posix().casefold()
        if key in seen:
            raise SystemExit(f"Duplicate path: {record['path']}")
        seen.add(key)
# Validate the complete fixed selection before creating any output.
root = Path('cold-download-v001')
root.mkdir(exist_ok=False)
for asset in manifest['assets']:
    for record in asset['files']:
        relative = Path(record['path'])
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(record['download_url'], timeout=120) as response:
            data = response.read()
        assert len(data) == record['bytes'], record['path']
        assert hashlib.sha256(data).hexdigest() == record['sha256'], record['path']
        with target.open('xb') as handle:
            handle.write(data)
        print(record['sha256'], len(data), record['path'])
```

This is a receipt/reproduction snippet for a reviewed fixed manifest, not a general
untrusted-manifest downloader or a certified material/geometry pipeline. Hash/size
checks fail on permission HTML, truncated or changed bytes. Existing destinations
refuse rather than clobber; do not re-use source/export/report directories as output.

### Measured fresh-clone execution

`git clone --depth 1 --single-branch --branch improve/issue-1316-outside-agent-asset-retrieval-by-manifes
https://github.com/artsafro/AGR-DigitalTwin-pilot.git tmp/outside-final-clone` returned 0;
HEAD was `8b322798c1272e242ecf0cf5c50403d20052e887`. The original Python fence at
that commit was extracted from the clone's receipt and executed by stdlib Python with that clone as
cwd, an unused `cold-download-v001`, no credentials/mount reads and no reused bytes.
**Exit 0; 3/3 asset selections, 6/6 payload hashes and sizes matched**:

```text
ea43c19ac9d77ec240a79eea7f73db442025efa7dd05f06a3adc8ca71bf9c0be 137264 maf/union_v001/fbx/MAF_0002_TBO_konteyner.fbx
c9edd5f318e6e2bcbd18170040b0f6faf31d870c61d0ac9363a281518ca2676b 25011570 flora/a101/FLORIO_221.max
ca3122dbfd910a70cbbccb9cca42779efecdc4b1a2bdc4f166172dbf1dcb01fe 2343623 flora/v003/maps/tilia-cordata/lipa_t1_h550_low/diffuse-v002.png
21fff75057b85b94cb847b8508f30ae9a555af1038f9414b5ea220d26f991525 2819435 flora/v003/maps/tilia-cordata/lipa_t1_h550_low/lipa_t1_h550_low.png
1489d9c48a0c89fe0f30b294ad05501d63992b959277f4d1ca5a2892a33b967b 211735 flora/v003/maps/tilia-cordata/lipa_t1_h550_low/opacity-v002.png
7838298711c57ade49821a0e371c88d41f2804ae30983c9c25e514c2feb47320 565 materials/placeholders/v001/interior_d_256.png
```

Initial command extraction failed from shell backtick expansion **before any download**;
using `chr(96)*3` in the launcher repaired quoting without changing the documented snippet.
Affected verification before the main merge: **297 passed, 1 deselected** (eight files).
The RED route regression was committed first in `e99c693b`, after 1 expected assertion
failure on c5db1251's deleted C:/x path. A second tests-first commit, `dd6b7067`,
exposed 9/9 malformed-manifest cases creating an output directory before refusal
(or, for empty input, returning success). The documented snippet now preflights the
whole fixed selection before writes: empty/partial/unsupported input, NaN/inf/zero
sizes, duplicated case-insensitive paths, traversal and absolute paths reject.
An input/output hardlink witness also rejects without modifying either path.
Post-main-merge verification of the eight affected files: **308 passed, 1 deselected**.
Source preservation after native previews: **5/5** hashes unchanged (A101 MAX and
four original RGBA files). Retrieval/native/transport/probe logs are sealed with
SHA256SUMS and readback at `G:/Мой диск/AGR-evidence/1316-outside-retrieval/verification-v003/`
(13 retained text receipts, in addition to the versioned preview directories).
The portability probe used a separate stdlib process and fresh network clone on this
workstation; it is not a claim that a second hosted agent or another physical PC ran it.
The old catalogue's tests are not disabled: they still reconstruct the complete
unchanged release from its exact snapshot, and current-map rebinding still rejects.
Full-suite evidence belongs to the final PR receipt, not to a fabricated pre-run claim here.

## Historical first probe — boundary


Run from card `t_9199048b`, branch
`improve/issue-1316-outside-agent-asset-retrieval-by-manifes`.
Fresh network clone of pilot `main`:
`2a42807f27b1fe6004e648a81e5de753700f04d4`.
No binary was read from `C:/x`, a local asset cache, or a previous worktree.
No credentials, cookies, rclone configuration or Drive desktop mount were used for
retrieval. A later read-only mount existence check corroborated a missing dependency;
that check is **not** outside-agent retrieval evidence.

**Result: three payloads downloaded; complete three-asset retrieval NOT established.**
Flora geometry is retrievable, but its declared approved texture dependencies are not
published on the documented route. Native preview and notification have not run;
there is no visual verdict request and no implied acceptance. This is not a completed
readiness increment, a botanical identity check, or a delivery QA result.

## Documented route and discovery

Start with `library/README.md` and `assets/README.md`, then
`assets/manifest.json`. The latter supplies the shared folder URL:

<https://drive.google.com/drive/folders/1zKszwxFRWH0DnrXYiFR7SN3bH9Iph2d6>

Follow its folder names in the public Drive UI, not the `recorded_path` field.
The root and the listed child folders returned HTTP 200 without authentication.
File IDs below were discovered by following that folder tree; they are exact
retrieval pointers for this receipt, not a new library catalogue or new releases.
Drive IDs alone are not integrity/version guarantees: compare the downloaded bytes
with SHA-256 and size before opening a copy in a DCC.

| Selection | Path inside shared AGR-assets | File ID | Bytes | SHA-256 |
|---|---|---|---:|---|
| MAF `MAF_0001`, source `TS_001` | `maf/union_v001/fbx/MAF_0001_TS_001.fbx` | `1sWsv1F2nefAlVaANINL6YSoJJm6Knsyk` | 142000 | `9f23b1122b5b8ecc66cc833765b1bf1cb065601c3d3bee1fccae9c344902fa08` |
| Flora `Tilia cordata`, material ID 101, library container v003 | `flora/v003/flora-library-v003.max` | `12rcEFUWNXkYNxRNQvc79x8Athg3tDqyk` | 2561364 | `9942ae2be37c900c3066d791193eb0470cc08933881d9f72db833d42578dfa74` |
| Material ID 40 `interior`, VPM diffuse placeholder | `materials/placeholders/v001/interior_d_256.png` | `1GrGLyPjxCLkN1jDDAYTTJo1bC6XaKK7B` | 565 | `7838298711c57ade49821a0e371c88d41f2804ae30983c9c25e514c2feb47320` |

Authorities in that clone:

- MAF: `library/maf/catalogue.json`, entry `MAF_0001`. Its absolute
  `fbx_path` names the same basename, but contains no published file hash. The
  SHA-256 above is a **new download measurement**, not a comparison with a
  previously versioned MAF manifest. `union_v001` is a storage folder name;
  `assets/manifest.json` correctly keeps source MAF releases `version=null`.
- Flora: `assets/manifest.json` entry `flora-library` supplies the expected
  container hash and byte count; both matched. `library/flora/catalogue.json`
  selects `Tilia_cordata_NPM` / `Tilia_cordata_VPM` inside it. These are catalogue
  selectors, not a fresh native confirmation that those objects were opened.
- Material: `library/materials/maps_v002.json`, row with that exact `path`,
  supplies the expected hash and 565 bytes; both matched. This is one map of
  material 40, not a claim to retrieve a complete VPM texture triplet or shader.

## Executed retrieval commands

Run in a new private workspace. The original probe used `tmp/outside-clone` and
`tmp/outside-downloads` in this card's worktree. Choose unused destinations;
`curl -o` overwrites an existing target, so do not rerun against retained evidence.

```bash
git clone --depth 1 --branch main --single-branch \
  https://github.com/artsafro/AGR-DigitalTwin-pilot.git tmp/outside-clone
git -C tmp/outside-clone rev-parse HEAD
mkdir -p tmp/outside-downloads
curl -sS -L --fail --max-time 90 -o tmp/outside-downloads/MAF_0001_TS_001.fbx \
  'https://drive.usercontent.google.com/download?id=1sWsv1F2nefAlVaANINL6YSoJJm6Knsyk&export=download'
curl -sS -L --fail --max-time 120 -o tmp/outside-downloads/flora-library-v003.max \
  'https://drive.usercontent.google.com/download?id=12rcEFUWNXkYNxRNQvc79x8Athg3tDqyk&export=download'
curl -L --fail --max-time 90 -o tmp/outside-downloads/interior_d_256.png \
  'https://drive.usercontent.google.com/download?id=1GrGLyPjxCLkN1jDDAYTTJo1bC6XaKK7B&export=download'
sha256sum tmp/outside-downloads/MAF_0001_TS_001.fbx \
  tmp/outside-downloads/flora-library-v003.max \
  tmp/outside-downloads/interior_d_256.png
```

All three downloads exited 0. Hash output is the table above. Python
`Path.stat().st_size` independently measured their byte counts. An HTTP 200
HTML permission/confirmation page would not match these hashes and is not an asset.
No download/upload tool was added, no sharing permissions changed, and no source,
manifest authority, geometry or material assignment was modified.

## Failure that documentation cannot repair

The selected Flora entry declares these approved dependencies:

- `C:/x/flora-library/v001/maps/tilia-cordata/diffuse-v001.png`
- `C:/x/flora-library/v001/maps/tilia-cordata/opacity-v001.png`

`library/flora/README.md` documents that legacy local map root. The newer layout
in `library/materials/README.md` [D239] names `flora/v003/maps/<slug>/`.
Neither is a downloadable pointer to the two original approved Tilia maps.

The public `flora/v003/maps` folder
<https://drive.google.com/drive/folders/1eXoXppB6QzMCm6LFjWS9i_5POS2ByZbv>
listed only `achillea`, `aster-dumosus-island-samoa`, `berberis`, `daisy-white`,
`daisy-yellow`, `lavandula`, `lysimachia`, `miscanthus`, `miscanthus-v2`, `rosa`,
`syringa`, `triticum`, and `telegram-stars-preview-v001.png`. No `tilia-cordata`.
The mounted mirror also had neither file under `flora/v003/maps/tilia-cordata`,
and no diffuse under the legacy `flora/v001/maps/tilia-cordata` path.
Do not substitute the Telegram genus variants or generate replacement maps.
Do not treat downloading the MAX container as a complete textured-species receipt.

## Publication authorized; original bytes still missing (resume 2026-11-13)

Artem authorized publication of the **exact approved** Tilia pair, with SHA-256
and a portable catalogue route, without regeneration or substitution [D275].
This resolves publication permission only; it does not supply or recreate bytes,
record a visual verdict, or approve the model.

Read-only checks on resume:

```bash
python -c "from pathlib import Path; paths=['C:/x/flora-library/v001/maps/tilia-cordata','C:/x/t_6c48bc9d/maps','G:/Мой диск/AGR-assets/flora/v003/maps/tilia-cordata']; [(print(p, Path(p).exists())) for p in paths]"
```

All three paths returned `False`. The original approval-card directory
`C:/x/t_6c48bc9d` contains only six surviving pytest directories, no production
maps or review sheet. The mounted `flora/v003/maps` still contains the twelve
other species directories listed above, not Tilia. Filename searches under
`G:/Мой диск/AGR-assets` for `*tilia*` and under `G:/Мой диск/AGR-evidence`
for `*batch1*` returned no matches. These are bounded location checks, **not**
a claim that no backup exists anywhere. A broad C:/x recursive search timed out;
another encountered access-denied test directories, so neither is exhaustive.
Synthetic pytest `tilia-cordata` files are not approved assets and are excluded.
No hashes or download URLs were invented; no asset files were published.

Next operational prerequisite: restore the two original approved PNGs from their
retained source/backup, with provenance to the batch-1 approval. Permission is
already granted [D275]; do not ask Artem to authorize publication a second time.
Until exact bytes are recovered, keep catalogue/maps unchanged rather than
replace working metadata with an unverified URL. After recovery: publish under
`flora/v003/maps/tilia-cordata`, measure hashes, obtain real download pointers,
verify unauthenticated byte readback and update source `maps.json` plus generated
catalogue. Then perform the remaining native preview/request gates below.

## A101 source inspection (second resume 2026-11-13)

The source location is now resolved by Artem's issue comments:
[#6860499079](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1316#issuecomment-6860499079)
and the Tilia-only correction
[#6860510392](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1316#issuecomment-6860510392).
Both original files exist under
`G:/Мой диск/AGR-assets/flora/a101/TextureFlora/`:

| Source | Bytes | Dimensions / mode | SHA-256 |
|---|---:|---|---|
| `lipa_t1_h550_high.png` | 9351771 | 4096 x 4096 RGBA | `166e210fe8bfea60d54e2577b139b83d46fdedcf8ec4df0eda4fa265a58ab90d` |
| `lipa_t1_h550_low.png` | 2819435 | 2048 x 2048 RGBA | `21fff75057b85b94cb847b8508f30ae9a555af1038f9414b5ea220d26f991525` |

Measured with `uv run python` using `Path.stat().st_size`,
`hashlib.sha256(path.read_bytes()).hexdigest()` and Pillow `Image.open`.
Both images were visually inspected: they contain **branch/foliage sprites and
an adjacent bark strip**, not a single full-height tree on white. High and low
are distinct atlas variants, not diffuse and opacity of one pair. The high image
is 4096 square; the low is 2048 square. These are measured Tilia properties, not
an extrapolation from the other A101 species' 2048-square descriptions.

A bounded repeat search `Path('G:/Мой диск/AGR-assets/flora').rglob('*tilia*')`
returned no matches. `AGR-evidence` root contains `1146-flora-star` but no
`216`, `190` or `1316` directory. A recursive scan across the evidence root
exceeded 180 seconds and is **not** an exhaustive absence proof. No approved
v001 pair was recovered.

The documented public root also exposes `flora/a101` (folder ID
`1HqAepNoDHY9yPJEC4CSn_zMlhShStiOf`), its `FLORIO_221.max`
(file ID `1Kdpp2GX-Rpcmz54EsQF5GzbUjL7m_0kH`) and `TextureFlora`
(folder ID `1lZX97pGFBeGXYjwbtc6SJzFqFNuoKPwK`). The initial public HTML
listing for TextureFlora returns **only 50 entries**, ending at `elka`;
absence of `lipa` in that first page is NOT a missing-file result. Pagination
or an exact-file lookup is still required for unauthenticated source downloads.
Local source inspection/hashes above are not cold retrieval evidence.

### New decision boundary: incompatible recipe, not missing source

The orchestrator's resume comment asks for a new v002 using the documented
batch-1 recipe. The repository's documented recipe
(`docs/pipeline-flora-textures.md`, sections 1-2) instead requires an RGB,
2048-square, full-plant white-background image and derives opacity by white-key
threshold 245. It explicitly rejects RGBA input. A real read-only probe with
`dt_ai.materials.flora.cutout(Image.open(source))` rejected **both** A101
Tilia files with `ValueError: Expected RGB white-background input without alpha`.
Applying that recipe to the
A101 atlases would require changing the image/opacity semantics; taking high/low
as diffuse/opacity would also be incorrect. Neither operation follows Artem's
"exact library bytes ... no regeneration" instruction.

Recommended resolution for the owning orchestrator: explicitly select the
A101-native route, retaining both RGBA sources unchanged and their original UV
layout, with any RGB/alpha channel split recorded as a **new pending version**,
not recovery or approval of v001. Confirm which native A101 Tilia object and
high/low variant that version selects before rebinding the existing v003
`Tilia_cordata_NPM` / `Tilia_cordata_VPM`: their catalogue source is
`FLORA_Union_v1.max`, not `FLORIO_221.max`; compatibility is not established.
Do not create a whole-tree image, regenerate an atlas, inherit v001 approval,
or rewrite every species path to unverified/nonexistent Drive destinations.

Native Max connectivity probe: `python
C:/Users/artsafro/hermes_kanban/scripts/max_exec.py --ping` returned exit 2,
`status=unreachable` on `127.0.0.1:8765`. No DCC scene was opened or modified;
this is not the blocker (agent-owned Blender remains an allowed preview route).
No publication, preview, Telegram notification or verdict record was fabricated.
The remaining gate is the contradictory source/recipe selection, not another
request for publication permission or the same missing-source question.

## Resume gates

1. Provide the two **existing approved** Tilia map files at a downloadable,
   owner-authorized location, with hashes and original-map provenance. Publication
   permission must not be inferred from `licence=null` or another public folder.
2. From a fresh clone/download root, retrieve the species container and dependencies,
   then native-read the exact selected objects on a copy. Check MAF dependencies and
   the selected material's intended asset boundary too; they are not yet native-tested.
3. Choose one complete asset version for the existing visual loop [D104, D119]:
   confirm DCC/version/document/units, open a copy, render to a new versioned evidence
   directory, hash the asset and preview, and read the saved evidence back.
4. Send **one** Telegram-ready notification with asset ID, full version SHA-256,
   preview image/path, and `принимаешь эту версию?` (accept / reject + reason).
   Retain transport evidence; drafting text alone is not sending it.
5. Record request identity, the exact asset and preview hashes, and `pending` with
   `answer=null` until Artem answers. Bind his verbatim answer and message source to
   those same hashes. A changed asset or preview needs a new request, never transfer
   an earlier verdict. Pending is permitted by #1316; a missing request is not pending.

No request record is fabricated here: rendering/sending are not yet performed.
Only after these gates can #1316 be handed to review. No full suite was run for
this partial documentation-only checkpoint; no production code or tests changed.
