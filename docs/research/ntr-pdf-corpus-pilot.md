# NTR PDF corpus pilot — company-folder reference draft (#1275)

## Decision and outcome

**Conditional GO** for a source-referenced text-first search catalogue, in small batches.
**NO-GO** for a blind whole-corpus vision run or automatic window/MAF/Flora library approval.
Materials, window-family candidates, MAF, planting and standards below are a **draft**,
not a delivery model, approved substitution list or independently scored extraction.

Artem chose NTR on 2026-11-12; the 2026-11-13 continuation excludes cached input
from the 2,000,000-token pilot limit and authorizes at most 300,000 further new
input+output tokens [D267]. The ten explicit card paths take precedence over the
inventory's older 213-page proposal. #1254 is not required for these lists.
Staropetrovskiy is list-only: modelling #425 remains parked [D267].

## Inputs, reading boundary and reproducibility

All 10 PDFs / 261 physical pages were text-scanned in place, read-only. Full hashes,
exact original paths, per-page text-byte counts and timings are in
[ntr-pdf-corpus-pilot.json](ntr-pdf-corpus-pilot.json). Source hashes matched before
and after extraction and again at receipt sealing, 10/10. No PDF was copied or committed.
Page refs below are **one-based physical PDF pages**, not printed sheet numbers:
A10 p11 is printed sheet 5; A10 p16 is printed sheet 6 and contains an older
compensation-plan inset. This does not establish the inset as current planting authority.

The existing `src/dt_ai/album/schedules.py` PyMuPDF loader read every text page;
`export_schedules` ran on selected candidate pages using PyMuPDF/pdfplumber 0.11.10.
Commands (from the worktree after `uv sync`):

```bash
uv run --extra pdf-review python tmp/explore_ntr.py
for a in A01 A02 A04 A05 A07 A10; do
  uv run --extra pdf-review --with pdfplumber==0.11.10 python tmp/ntr_tables.py "$a" || break
done
```

These exact one-off scripts and inputs are sealed with the extracted text, table
CSVs/JSONs and derived PNGs at `G:/Мой диск/AGR-evidence/1275-ntr-pdf-corpus/`.
Only small receipts are in git. `SHA256SUMS.txt` and its digest in the JSON bind the
external members; this verifies the mounted Drive copy, not remote cloud-sync completion.
Do not blindly rerun the historical scripts into existing outputs; use fresh directories.

Native image review in attempt 1 covered A06/A08 contact sheets and A08 p12–14.
No additional image-tool calls were used during continuation; shared agent-model
usage for analysis and report writing is measured below. Text layer presence
is NOT schedule completeness: **A08 p12–14 have zero text but visible finish legends**.
Every page was text-scanned; not every image or drawing region was semantically checked.

## Per-album reading, confidence and measured local cost

H = coherent direct source text; M = column/visual draft; U = unknown/not recovered.
These are review priorities, not calibrated probabilities. No independent expert labels
exist. All local extraction calls use **0 new / 0 cached model tokens**. Both columns
below explicitly include the unavailable **shared analysis** portion: NM = not measured,
not zero. The agent compared several albums in the same model turns, so neither new
nor cached session tokens can honestly be assigned to individual albums. No usage API
was exposed by the native image tool. Per-album model latency and USD are also NM.

| ID / project | Pages | Read / confidence | Text bytes | Extract s | Tables / s | New tokens local + shared | Cached tokens local + shared |
|---|---:|---|---:|---:|---|---|---|
| A01 / 14_Skolkovo | 4 | Facades p1–2; lightning p3–4; H/M interleaved columns | 96647 | 1.284 | 11 / 1.974 | 0 + NM | 0 + NM |
| A02 / 22_COD | 5 | Lighting schedule p5 H; other facade notes partly outlined U | 8480 | 0.066 | 1 / 0.366 | 0 + NM | 0 + NM |
| A03 / 29_Donskoy | 4 | Facade alternatives; no typed window/material schedule recovered U | 4209 | 0.126 | not run | 0 + NM | 0 + NM |
| A04 / 33_Staropetrovskiy | 142 | MAF p73–75 H; planting p109,112–115 H/M; contradictions retained | 1624756 | 3.147 | 7 / 1.827 | 0 + NM | 0 + NM |
| A05 / 3_PPT_4 | 11 | MAF product cards p5–10 H/M; zero grid tables, not zero products | 97309 | 0.161 | 0 / 0.653 | 0 + NM | 0 + NM |
| A06 / EcoBunino | 18 | 18-page text scan + contact sheet; imagery; schedule absence unproven U | 42451 | 0.046 | not run | 0 + NM | 0 + NM |
| A07 / 14_Skolkovo | 26 | Finish legends p15–16 H; p13 unfinished placeholders excluded | 82235 | 0.281 | 1 / 1.031 | 0 + NM | 0 + NM |
| A08 / 3_PPT_4 | 32 | Visual finish legends p12–14 M; zero text on those pages | 31888 | 1.207 | not run | 0 + NM | 0 + NM |
| A09 / 14_Skolkovo | 3 | Lighting/network pages H/M; not a window schedule | 144214 | 0.197 | not run | 0 + NM | 0 + NM |
| A10 / 14_Skolkovo | 16 | Paving/planting p11 H; compensation inset p16 H/M, authority unknown | 392004 | 0.874 | 6 / 52.936 | 0 + NM | 0 + NM |

Local extraction total: **7.390 s**;
table calls: **58.788 s** for
26 candidate tables. A10 completed: 6 tables,
52.936 s (not the unobserved status in the earlier partial note). These times include
source hashing/text or table work respectively, not dependency install, rendering,
agent reasoning or manual review. All table exports retain row_type_review, unit_review,
region_binding, ground_truth and approval gates. Grid detections are not accepted rows.

## Reference entries


Physical PDF pages, one-based. H = directly readable coherent text; M = multi-column
or visual draft requiring a second check. Neither means independent expert accuracy.
Russian names below are source quotations, not translated identifiers.

### Finishes and window candidates

| Item | Source | Evidence / status |
|---|---|---|
| Aluminium smooth matte panels RAL 7015 | A01 p1; A07 p15, Ф.1 | H; repeated Skolkovo project, not independent company-wide recurrence |
| Perforated aluminium cassettes RAL 7004 | A01 p1; A07 p15, Ф.2 | H |
| Plinth: plaster over steel mesh + porcelain cladding RAL 7015 | A01 p1; A07 p15, Ф.4 | H; no image texture asset extracted |
| Aluminium lamellas RAL 6018 | A01 p1 | H |
| Double-chamber curtain wall, clear glass, profile RAL 7015 | A01 p1 | H; family candidate only, no window block mark/size schedule |
| Single-chamber curtain wall with stemalite, profile RAL 7015 | A01 p1 | H; keep separate from next version |
| Ф.5.1 tinted double-chamber curtain wall, profile RAL 7004 | A07 p15 | H; **differs from A01**, no version authority selected |
| Ф.5.2 stemalite double-chamber curtain wall, profile RAL 7004, stemalite RAL 7015 | A07 p15 | H; not silently merged with A01 |
| Ф.5.3 ventilation-grille curtain-wall infill, profile/grille RAL 7004 | A07 p15 | H; not a transparent window |
| Painted pebble-textured SFTK, grain 2 mm; RAL 5014 / 5001 | A08 p12 | M; native image, legend rows 1/2 |
| Scratched steel composite panels RAL 1014 / 1002 | A08 p12 | M; native image, rows 3/4 |
| Painted pebble-textured SFTK, grain 2 mm; RAL 6034 / 5009 / 1014 / 1002 | A08 p13 | M; native image, rows 1–4 |
| Painted pebble-textured SFTK, grain 2 mm; RAL 6033 / 6004 / 1014 / 1002 | A08 p14 | M; native image, rows 1–4 |
| Clinker brick, horizontal laying, RAL 5014; glazed facing brick, vertical laying, RAL 5001 | A08 p12–13 | M; native image, ground-floor rows 5/6; dimensions await ROI check |
| Glazed facing brick, horizontal/vertical laying, RAL 6026 | A08 p14 | M; native image, rows 5/6 |
| INTILED LACE RGBW Custom, silicone, 16x15 mm, total length 5505 m, quantity 1 | A02 p5 | H; quantity is not length; source requires final approval |
| Asphalt paving; curb БР 100.30.15; concrete B15/B22.5, crushed stone M600, sand | A10 p11 | H; construction layers, not ready texture maps |

No marked window-block schedule was recovered in the inspected text/schedule regions; raster negatives remain unknown. Facade families are **candidates**,
not dimensioned reusable library geometry. A07 p13 “Наименование” placeholders must not
become products. No material or window authority conflict is resolved by this draft.

### MAF lists only (no modelling, #425 remains parked)

A04 p73: QBP-011 bench; TID180B/TID80 benches; TID50 stool; TID50T table;
ЛГДП-59 rotating chair; MNT290 bench; PG80516930 Berlin bin; Superkrug 4 table.
A04 p74: Yo chairs with/without arms; 40020 Bar stool; LOB280/LOB240 Orbit bench-tables;
VT120 Valet ashtray; Drop chair.
A04 p75: Drop pouf; POL225/POL425 planter sets; РП 008 Corten tree grille;
.СКМ 157 Hitech chair; ВП 029 Monochrome bike rack; SM100 Mielon bollards.
Names/articles are text-derived candidates (H for reading; not approved supplier substitutions).

A05 p5: Gloria bench 10020, Gloria seat 10022, Box bin 9007, Vozdukh bike rack 8010,
Alegra tree grille 6001-1.
A05 p6: Orion pergola 40171.1, double swings 18244, Pyramid tower 18621,
climber type 20 18434, Zhuravl swings 18203.
A05 p7: Landau table 13010, Krug pergola 40080, Penek benches 10045-5/10045-6,
Duga radial bench 40002.
A05 p8: repeated 18434 and 18244; islands platform/slide 18046, balance rocker 18953,
sandbox 18000. Repeats are not additional unique product types.
A05 p9: Antey 23019.1, double parallel bars 23048.1, Atlant 23015.1, double monkey bars 23050.1.
A05 p10: Apollon Extra 23080, obstacle course 23043.1, sports complex 23040.1,
Partiya tennis table 3003-3. Source position labels repeat; article + page is safer than position alone.

### Flora lists only

A04 p112: Pinus sylvestris; Ulmus × hollandica 'Lobel'; Amelanchier lamarckii;
Acer campestre 'Elsrijk'; source-spelled Acer saccarinum 'Laciniatum Viery';
Acer freemanii 'Autumn Blaze'; Tilia cordata 'Rancho'; Alnus glutinosa 'Imperialis'
(with Russian alternative buckthorn in same row); Amelanchier canadensis / Malus hybrida
'Evereste'; Hydrangea paniculata 'Kyushu'/'Little Lime'; Cornus alba 'Ivory Halo'/'Red Gnome';
Cornus stolonifera 'Flaviramea'; source-spelled Mahonia aquifolim; Ribes alpinum 'Schmidt';
Symphoricarpos chenaultii 'Hancock'; Spiraea betulifolia, vanhouttei/cinerea, japonica 'Albiflora';
source-spelled Parthenocissus quinquefolia. Preserve alternatives/spelling; no taxonomy correction.

A04 p113: groundcover types include Spiraea betulifolia, Mahonia, Geranium macrorrhizum
'Spessart', Bergenia, Cornus 'Ivory Halo', Nepeta 'Snowflake', Sesleria autumnalis,
Spiraea japonica 'Goldflame', Calamagrostis 'Overdam'.
A04 p114–115: sun/shade/planter mixes and perennial summary include Anemone, Bergenia,
Milium, Waldsteinia, Calamagrostis, Geranium, Darmera, Ajuga, Nepeta, Sanguisorba,
Alchemilla, Carex, Sedum, Sesleria, Tellima, Equisetum and Brunnera (all provisional).
A04 p115 second table row 7 pairs Russian Darmera with Latin Bergenia: **unresolved source
mismatch**, not an instruction to select one. A04 p109 lists Poa pratensis, Festuca rubra,
Agrostis capillaris, Trifolium repens; percentage ranges are not a normalized recipe.

A10 p11: seeded soil 1910 m² and rolled lawn on slopes 909 m².
A10 p16: Norway spruce h=5 m, 10 pcs; European lime h=5 m, 15 pcs; root ball d=1.25 m.
Do not replace these project-specific planting choices with A04's explicitly non-rolled lawn.

### Referenced standards / repeated solutions

A10 p8/p11: GOST 6665-91 (curb). A10 p11: GOST 9128-2013 (asphalt),
26633-2015 (concrete), 8267-93 (crushed stone), 8736-2014 (sand);
TU 5718-003-04000633-2006 also appears. These are **document citations**, not a claim
that the editions remain current. No independently verified standard-series catalogue yet.

Additional **verbatim standard citations**, not extra Staropetrovskiy modelling work:
A04 p36 mentions GOST 8736 (sand) and GOST 31424 (crushing screenings); no edition
is safely bound to either in the extracted columns. A04 p37 cites GOST 17608-2017
and GOST 8736-2014; the source also has the suspicious joined string
`8736-93-01м`, retained as an unnormalized citation candidate rather than a valid
edition. A04 p38 cites GOST 6665-91 (curb) and GOST 26633-91 (concrete), an older
edition than A10's 26633-2015. These are document references, not current-law advice.
A whole-text regex audit generated false joins such as `ГОСТ 105 МПа` on A04 p36
and `ГОСТ 8267-93 - 0` on A10 p11: discarded as pressure/layer-thickness spillover,
not added as standard IDs. This audit used already-extracted text, not new PDF copies
or production work; graphic-only standard citations remain unknown.

Repeated Skolkovo finish palette (A01 p1–2 / A07 p15–16), metal/wood outdoor furnishings
(A04 p73–75 / A05 p5–10) and lawn/asphalt context (A07 p12 / A10 p11) are useful
retrieval hypotheses, not proof of NTR-wide standardized design. The NTR directory groups
multiple issuers: A02 explicitly credits The Light; A05 DOMO; A08 BQ. A company-folder
reference must not attribute all design authorship to NTR.


### Additional directly recovered facade candidates

| Item / source mark | Page refs | Confidence / use |
|---|---|---|
| Acoustic louvre screen, source-spelled AIRO-SOUBD or analogue, RAL 7004, Ф.3 | A07 p15–16 | H reading; no supplier or geometry approval |
| Powder-coated metal door, RAL 7004, Ф.8 | A07 p15–16 | H family only; no opening dimensions |
| Stainless-steel canopy with transparent tempered triplex, Ф.7 | A07 p15–16 | H; not a window block |
| Metal facade flashings/profiles RAL 7015, Ф.10; porch railing RAL 7015, Ф.6 | A07 p15–16 | H; not extracted texture files |

### Planting detail retained rather than normalized away

A04 p113 Type 1: Spiraea betulifolia, source-spelled Mahonia aquifolim,
Geranium macrorrhizum 'Spessart', Bergenia crassifolia. Type 2: Spiraea betulifolia,
Cornus alba 'Ivory Halo', Geranium 'Spessart', Nepeta × faassenii 'Snowflake',
Sesleria autumnalis. Type 3: Mahonia aquifolim, Spiraea japonica 'Goldflame',
Nepeta 'Snowflake', Calamagrostis acutiflora 'Overdam', Bergenia cordifolia.
Bergenia names differ even within this schedule; do not collapse the source records.

A04 p114 sun mixes 1–3: манжетка мягкая, очиток гибридный 'Eline', кровохлёбка
тонколистная 'Alba', сеслерия осенняя, герань 'Spessart', вейник 'Overdam',
котовник 'Snowflake'; narcissus поэтический var. Recurvus among sun mixes 1/2.
Shade mixes 1–4: бадан, анемона гибридная, герань 'Spessart', вальдштейния
тройчатая, бор развесистый, живучка ползучая, дармера, хвощ зимующий,
теллима, осока морроу, бруннера сибирская. Planter mixes 1/2: гейхера гибридная
with будра плющелистная / осока морроу respectively. All are source mix membership,
not interchangeable single-species library records or fixed density recipes.

A04 p115 main summary gives Anemone × hybrida, Bergenia crassifolia, Milium effusum,
Waldsteinia ternata, Calamagrostis acutiflora (Russian name 'Overdam'), Geranium
macrorrhizum 'Spessart', Darmera peltata, Ajuga reptans, Nepeta faassenii 'Snowflake',
Sanguisorba tenuifolia 'Alba', Alchemilla mollis, Carex morrowii, Sedum x hybridum
'Eline', Sesleria autumnalis, Tellima grandiflora, Equisetum hyemale, Brunnera sibirica.
The lawn-grid summary row 7 instead prints Darmera / Bergenia crassifolia together:
retain both original cells and flag identity unknown, never repair by choosing one.

## Negative results, drops and unresolved authority

- No dimensioned marked window-block schedule was recovered. Facade glazing is a
  family search seed only, not an export-ready window library; sizes, opening pattern,
  sill and authoritative revision remain unknown. No invented types for A03/A06/A09.
- A07 p13 placeholder `Наименование` rows excluded as unfilled. A05 repeated article
  18434/18244 on p6/p8 and repeated position labels are not separate new product types.
- No texture image assets or measured PBR maps were extracted: surface words/RALs
  are references to finishes, not approved texture replacements.
- The cited GOST editions are verbatim document references, not checked current law.
  No confidently identified standard-series catalogue number was recovered in the
  inspected schedule regions; graphic-only regions remain unverified.
- A01/A07 glazing differences are kept as revision alternatives; A04 botanical name
  disagreements and A10 old inset remain unresolved source records. Research may
  catalogue contradictions without selecting authority; production would require Artem.
- Remaining pages are retained in the external text/page ledger, not silently dropped;
  overview scan is not semantic coverage. No axes, quantities, areas or MAF geometry
  are certified. No changes to #425, Flora library, skills or pipeline code.

## Measured session cost and extrapolation

Snapshot timestamp: `1794533218.967688` Unix seconds; exact counters/session IDs
are in the JSON. Attempt 1 ended: 129,300 new input +
10,041 output = **139,341 new**;
**1,991,552 cached**. Continuation at sealing:
**142,582 new / 1,176,064 cached**.
Combined observed lower bound: **281,923 new / 3,167,616 cached**, or
**1,080.2 new + 12,136.5 cached tokens per pilot page**.
This is the real text-first **whole-session** rate, not isolated PDF or vision billing.
Includes project intake/repeated context, table interpretation and report assembly;
not final test/publication delta. Final delta is reported in the PR, not silently
relabelled as measured in this immutable snapshot. Reasoning counters are disclosed
but not added again to output; runtime does not establish their disjointness.

Both sessions report `cost_status=included`, `actual_cost_usd=null`: currency cost is
**not measured** under subscription auth. Cached input still consumes resources and
must be reported, but is excluded from the authorized new-token ceiling [D267].
No per-album model figures can be recovered from these aggregate session counters;
a future batch must isolate album calls to obtain them, rather than allocate by pages
and present that estimate as measured. This is an instrumentation limitation of this
pilot, explicitly included in the go/no-go decision.

The entire authorized completion ceiling is **439,341 new tokens** = 139,341 from
attempt 1 + 300,000 continuation [D267], or **1,683.3 new/page**.
It is below 2M and the card's 11,766,924-token all-vision comparator. That historical
comparator includes context/cache differently, so the reduction is a planning budget
comparison, **not a like-for-like bill saving or accuracy comparison**.

Inventory is hash-deduplicated: 645 readable unique albums / 10119 pages;
NTR 18 / 269; remaining NTR 8 pages, other companies 9850.
141 unreadable source files (120 stream errors, 21 placeholders) are outside this
readable-corpus estimate and require separate recovery, not fabricated page totals.

| Scope | Pages | At observed new/page (lower-bound scenario) | At authorized pilot ceiling/page (planning scenario) |
|---|---:|---:|---:|
| NTR total | 269 | 290,564 | 452,807 |
| NTR not in this pilot | 8 | 8,641 | 13,466 |
| Full readable corpus, including NTR | 10119 | 10,930,187 | 17,033,301 |
| Remaining readable corpus after this pilot | 9858 | 10,648,264 | 16,593,960 |

These extrapolations are scenarios, NOT an authorization or measured upper bound for
other companies: the pilot is selected, same-project repeats inflate reuse, A04
supplies most schedule content, and scan-heavy albums may cost much more. At the
snapshot cache rate the full readable corpus would add approximately
**122,808,836 cached tokens**, separately from new tokens.
Local extraction extrapolation: 286.5 s
for 10119 pages, excluding table extraction, rendering, cloud IO, installs and
semantic review. Whole-session/inference time is not an extraction-time forecast.
Attempt 1 elapsed 971.6 s; continuation elapsed
at snapshot 619.2 s. These are shared
wall times; parallel local work and the overnight blocked interval are not inference.

## Recommendation for Artem

1. **Conditional GO**: finish NTR's remaining 8 inventory pages as a separately
   authorized batch, then try one different issuer before approving a full-corpus run.
   Reuse finish/product names for retrieval; do not generate geometry from this draft.
2. Batch at most **2 albums or 40 physical pages**, whichever comes first; split long
   albums (especially A04) by source page ranges. Use **100,000 new input+output tokens
   per batch**, retain a **30,000-token reserve** and start no inference call if its
   bounded worst-case would consume that reserve. Cached usage has a separate ledger.
   If no pre-call usage bound exists, stop before vision and ask; native unmetered
   image calls cannot enforce a hard spend limit. These are proposed future caps,
   not permission to spend them or exceed the remaining continuation authorization.
3. Text first, then render only unanswered schedule ROIs. Require isolated per-album
   new/cache/wall-time receipts and a small independent row check before expanding.
   Exclude duplicate hashes; preserve version alternatives and unresolved identities.
4. **NO-GO** for blind full-page vision, automatic window catalogue publication,
   supplier substitutions, taxonomy repairs or confidence percentages without labels.
   Success here is a searchable **draft reference**, not proof of complete semantic
   extraction. The reference is useful already; full-corpus execution is not begun.

## Batch 2 (#1303): B01 Avtozavodskaya planting, B02 Buhvostova school facade

Artem 2026-11-13 accepted recommendation 2 for one weekend batch: at most 2 albums / 40 pages, 100,000 new
tokens + 30,000 reserve, cached input not counted [D267]. After the first 10 albums the #1274
inventory has only **8 unique NTR albums of 1 page each** (8 pages). Selection (best extension of the
reference above; two new projects, neither in A01–A10):

- **B01** `18_Avtozavodskaya/LSR_Благо_озеленение.pdf`, 1 page, sha256 `0bac184a…97bf58be`: paving
  build-ups + planting legend (planting / site finishes).
- **B02** `5_1Buhvostova_School/002 - 10.04.2026 - Фасады/Схема фасада в осях 1-17.pdf`, 1 page,
  sha256 `1450b887…7184c7f2f0be`: facade finish legend **and a window/glazing legend**.

Not selected (reasons, not drops): the three other Buhvostova elevations (А-П, П-А, 17-1) share the
same folder, author and inventory text size (3.2–3.5k chars), so they likely repeat B02's legend
(unverified) and are the next batch's cheapest cross-check; `3_PPT_4/покрытия.pdf`
(366 text chars) and `11_Skladochnaya/Благо.pdf` (180 chars, PDF title says facade-texture concept) are
near text-less and would need image ROIs; `14_Skolkovo/.../Page 11 from 004_ЦОД02…pdf` is by its file
name an extract of A10's source (A10 p11), different hash, content not compared — likely overlap.

Method as in #1275: read-only PyMuPDF text, hashes before/after (2/2 unchanged), then a unique-line digest
in native line order (the `sort=True` dump is 142 kB / 117 kB of padding around 2,010 / 3,362 unique text
characters). Table extraction not run (text legends read directly), no rendering, no image calls. Scripts, text, digests
and usage snapshots: `G:/Мой диск/AGR-evidence/1303-ntr-pdf-batch2/` + `SHA256SUMS.txt`
(digest in the JSON `batch2` block). Page refs are one-based physical pages; both albums are p1.

### Batch 2 reference entries

| Item (source wording) | Source | Evidence / status |
|---|---|---|
| ТИП 1.1 paths, concrete paving slab 100 mm, on ground | B01 p1 | H type title; layer stack M (columns shared by types) |
| ТИП 1.2 fire-truck access, concrete slab 100 mm; concrete with road mesh 100 mm, crushed stone 200 mm, sand 300 mm | B01 p1 | H titles/layers; layer-to-type binding M |
| ТИП 1.3 / 1.4 paths / fire access **over the roof slab** (stylobate): slab 100 mm, dry sand-cement mix ≥30 mm, unloading RC slab B15 ≥100 mm, ГеоСтандарт 500 separation, TMD 10120 6040T drainage membrane, «Сейфити ЭПП 4 мм» 2 layers, CPR M150 screed 50 mm, expanded-clay concrete D800 slope ≥1.5%, XPS per project, «Сейфити ЭПП 3 кг» vapour barrier, RC slab | B01 p1 | H wording; M binding; the first roof-podium build-up in the reference |
| ТИП 2.1 paths, concrete slab 60 mm | B01 p1 | H |
| ТИП 2.2 rubber-crumb surfacing for children's and sports grounds, polymer surface ≥20 mm on RC slab B15 ≥120 mm | B01 p1 | H; surface, not MAF |
| ТИП 2.3 blind area (отмостка) of gravel 60 mm on «Сейфити Керамик ЭКП 4,5 мм» | B01 p1 | H/M |
| Planting legend: береза декоративная (+ separate line «Жакмана»), боярышник сливолистный, дерен белый, боярышник сливолистный **в кадке**, самшит **в кадке**, шалфей, щучка дернистая | B01 p1 | H names; «Жакмана» binding to the birch line M; Russian only, **no Latin names, quantities or sizes** |
| Panels «GRAVIS» galvanized steel 1.2 mm (or analogue), flat, matte brown-red RAL 3022; also radial variant | B02 p1 | H; mark Ф-1…Ф-9 binding M |
| Same panels, light-grey metallic RAL 9006; dark-grey metallic RAL 7021 | B02 p1 | H |
| Decorative element with 3D geometric pattern RAL 9006; plaster RAL 9006 / RAL 7021; granite plinth slab RAL 7021; concrete mosaic panels 500x700 mm (НГ) | B02 p1 | H |
| **Window block**: aluminium profile, dark grey RAL 7021; clear double-chamber IGU | B02 p1 «ЗАПОЛНЕНИЕ ОКОН И ВИТРАЖЕЙ» | H; family only — no block marks/sizes/opening scheme |
| Stick curtain wall Alutech ALT F50 (or analogue), RAL 7021, glass Larta/AGC (or analogue); **structural/semi-structural** variant | B02 p1 | H; first named profile system in the reference |
| Single-chamber IGU with painted glass in the curtain wall RAL 7021; sandwich panel in curtain/window system RAL 7021 | B02 p1 | H; opaque infill, not transparent window |
| Vent grilles RAL 7021; roof railing steel RAL 5000; roof mesh fence posts RAL 7021 / mesh RAL 9010 | B02 p1 | H |
| Noise screen: steel frame RAL 7021 with steel lamellas «Renson» (or analogue) | B02 p1 | H; marked Ц-1/Ц-2 region M |
| Navigation plates 1300x325 mm (lit) and 600x400 mm, blue background / white text | B02 p1 | H; signage, not MAF modelling |
| Levels +21,150 (height limit), +9,750, +7,250, ±0.000; abs. 139,740 etc. | B02 p1 | M: text positions only, not bound to axes |

B02 credits ООО «ам Атриум» as designer and carries a Mosgosexpertiza conclusion number and
«МАТЕРИАЛ ПРОВЕРЕН»: like A02/A05/A08 it is not NTR authorship. Legend marks (Ф-1…Ф-9, С-1…С-3,
ОГ-1…ОГ-4, Ц-1/Ц-2) are separate text lines from the descriptions; mark→description pairing needs one
ROI render and is **unknown** here.

### What batch 2 added that A01–A10 did not

1. A **window-block legend** («Оконный блок…», double-chamber IGU) and a **named curtain-wall system**
   (Alutech ALT F50, Larta/AGC, structural variant) — A01/A07 had only unnamed curtain-wall families.
   Still no dimensioned window-block schedule.
2. New RALs: 3022, 9006, 7021, 5000, 9010; «GRAVIS» steel panels; granite plinth; mosaic concrete panels.
3. A roof-podium (stylobate) paving build-up with named membranes (Сейфити, TMD, ГеоСтандарт) and
   rubber-crumb play/sport surfacing — A10 p11 had asphalt on ground only.
4. Tub-grown shrubs (боярышник, самшит; A04 had perennial planter mixes only) and species absent from
   A04/A10 lists (береза декоративная, боярышник сливолистный, шалфей, щучка дернистая). «дерен белый»
   may be A04's Cornus alba, but Russian/Latin names are not matched here (no taxonomy repair).
No new MAF products and no new GOST citations (none in the text layer of either album).

### Batch 2 negative results and unknowns

- B01: no Latin names, counts, sizes or areas; the 1:500 schemes are graphic. B02: no window marks,
  sizes, counts or opening types. Neither album has a GOST citation in text.
- Mark→description pairing (B02) and layer→type pairing (B01) are layout-dependent: M, not H.
- RAL 7021 in B02 vs RAL 7004/7015 in A01/A07 are different projects, not a conflict.

### Batch 2 cost ledger (session counters, `cost_status=estimated`, USD not measured)

New = input + cache-write + output; cached = cache-read, reported but outside the cap [D267].
Snapshots of this worker session (exact values in the JSON `batch2.usage_snapshots`); a window is
snapshot-to-snapshot and lags by one API call, so B01 includes issuing B02's extraction call.

| Window | New tokens | Cached tokens | Local extract s |
|---|---:|---:|---:|
| Intake: card, AGENTS, this report, inventory, plan (before B01) | 49,484 | 550,775 | – |
| **B01** extraction + reading | **11,993** | 340,071 | 0.463 |
| **B02** extraction + reading | **3,694** | 73,668 | 0.153 |
| Albums total | 15,687 | 413,739 | 0.616 |

Report/test/PR work after the B02 snapshot and the final session total are reported in the PR.
The 100,000 cap was never approached during album reading, so no stop-and-ask was triggered;
the 30,000 reserve was untouched. Per-album cost is **7,844 new per page** — higher than the
#1275 1,080/page because a 1-page album pays the full read-and-interpret overhead.

### Go/no-go for the next batch

**GO**, text-first, one batch: the remaining 6 NTR one-page albums (6 pages). Expected new tokens
≈ 4,000–12,000 per album from this ledger, i.e. well under 100,000 including intake; the three
Buhvostova sibling elevations should be read together (same legend → cheap cross-check of B02).
`покрытия.pdf` and `Благо.pdf` (11_Skladochnaya) need **one ROI render each** — ask before that.
After that NTR is exhausted; the next step is one batch of a different issuer (recommendation 1).
**NO-GO** unchanged for whole-page vision and library publication.
