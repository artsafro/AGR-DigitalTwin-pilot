# H168 — finish partition on the same wall candidates as the glazing stack (OBSERVE)

## Кратко для Артёма

**Не внедрять автоматическую привязку. H168 опровергнута.** На ТЦ «Среда» добавление признака отделки к признаку
остекления подняло число совпадений **по стороне здания** с 2/7 до 3/7 полных видов, но не помогло ни одному
из двух непривязанных реальных фрагментов. Два зеркально отражённых фрагмента получили уверенные ответы на
неверную сторону. Более того, единственное новое совпадение на полном виде получило балл 1,0 из-за деления
на почти нулевую энтропию: в зоне сравнения был только один цвет. Три свежих прогона совпали.

Для будущего листа `view<->face map sheet`: указывать отдельно сторону и физическую стену. Если оси, ключевой
план или название вида не подтверждают стену, показывать двух кандидатов и причину отказа, **не переносить
выноски отделки**. Оценку по цветовым зонам пока использовать только для диагностики. Сокольники не открывались:
конкретные два фрагмента STOP 04 этим прогоном не решены.

## Frozen contract (before implementation and scoring)

**Question.** #167 had 2/7 correct full views (both east I-A) and 1/3 correct real fragments (D–G), with no wrong sides. The glass cue had almost no evidence on opaque views. #149's finish partitions recovered 6/7 full views against four whole-side candidates, but produced a wrong opposite-side answer on a mirror. Can the same cue rescue opaque views when competing against physical wall candidates, without interpreting the other cue's silence as contradictory evidence?

**Arms (one new candidate, no search).** A = unchanged #167 C166 (glass NCC, length veto, rhythm veto). Calculate D using the frozen #149 R1b scoring functions (0.20 m grid; ±0.60 m horizontal slack and ±3 rows around top alignment; 30% overlap; score ≥0.30 and margin ≥0.10 across all *wall IDs*, including walls on the same side). Use #149's PDF fill extraction and metric crop on the exact ten #167 native boxes with no titles or side labels. Map visible Revit types by ray casting through the same per-wall orthographic depth slab, orientation, horizontal margins, Z band and hidden-object set as #167. Do not rerender whole-side candidates or use a supervised wall prior. F returns the sole non-null wall ID, agrees if both match exactly, and abstains on different IDs even if their azimuths match. Empty and horizontal mirror inputs mutate **both** drawing channels. No thresholds or candidate criteria change after the first pair.

**Frozen independent fixture and scope.** ELV TC Sreda: #145 hash-bound PDF/FBX and its axis/footprint oracle, reused by #167 (`b59d6e2213fff0d6f89f97e9140dd2965019f4ee`). All 7 full views and all 3 real fragments, including the top-cut p20, with the same 34 wall candidates (candidate parity enforced through the #167 body digest). ELV shares development provenance with both cues: this is a within-project ablation, not external validation. Scoring is **side-level** against the independent oracle, not physical plane/bay ground truth; exact wall-ID agreement is a veto, not proof of a correct plane. Silikatny's raster/OBJ pair does not carry the vector fills + Revit type labels used here; no transfer or fallback claim about it. G22/KPP1/AC08/OBR22/Vatutino, alternate source modalities, package quality (user-accepted versus user-rejected), Sokolniki/STOP 04 and finish transfer are not measured. #2001 is OPEN; do not open Sokolniki sources or keys. #2074 already owns D transfer to Olimpijsky FOK, #2075/#2080 the H153 witness-count fix, #2062 disagreement between earlier whole-side line scorers; none are part of this round. Atlas/form/trainer work remains parked.

**Metric and acceptance.** Primary: correct side assignments / seven full views (abstentions count as not correct); also report answered accuracy, abstain rate and integer correct/wrong/abstain for full and fragments separately. Confirm H168 iff F reaches ≥4/7 clean full views (≥2 net gains vs A), retains A's correctly answered clean rows at exact wall ID (including `p18 I-A`), has zero clean wrong on all ten views, and rejects all blanks plus has zero confident-wrong on exercised mirrors. Mirrors keep the native source wall/side as identity (abstain is permitted), and are never pooled with clean. Positive witness: a clean opaque view `p19 A-I` (A abstains) must be recovered correctly via D, not via leakage from A; accepted/retention control `p18 I-A` must retain A's exact ID and report whether D independently answers there. Rejected/confounder witness: the mirrored `p19 10-1`, which D at side level assigned to its opposite in #149, must not get a wrong side in F. Top-cut p20 reported separately, no waiver for wrong. Per state record changed cells by channel, no-op injections `not_exercised`, and whether both cues, sole D, or conflict actually determine the result. This is not an approval to ship; even confirmation requires an independent album with physical wall truth and a blind #2001 transfer when unlocked.

**Parity, budget and replay.** Three fresh pairs, shared FBX import but new Blender workbench render + type rays and fresh PDF reads each pair; not receipt rescoring. A's complete decoded payload must reproduce the canonical SHA-256 `04f67ea689a0cb763bd9df3b01e7b38cd1b9dd65b4555ff1441e072db7948921`; each audited F body must be byte-identical over the series. No report-based tuning. Budget 2100 s elapsed, one variant (one budget-setting first pair and two confirmations, no new candidate; estimate remaining as 1.15× first pair per outstanding pair, stop inconclusive if it cannot fit; hard process deadline). Report individual wall times, median and paired-run spread; experiment elapsed and verdict are separate.

```
git fetch origin research/autoresearch-standing-161 research/autoresearch-standing-162 research/autoresearch-standing-163 research/autoresearch-standing-165 research/autoresearch-standing-166 research/autoresearch-standing-167
uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-wall-fusion/run.py tmp/ar168-NEW
```

Preflight Git object pins, `uv.lock`, Python dependency versions and SHA-256 for PDF/FBX/Blender; postflight rehash native inputs. Pin measured local files in the recorded head and receipt. Replay limited to a host with the #145 named-folder input bytes and Blender 4.4 (or hash-identical copies). No source/delivery writes, no protected Sokolniki data, no other cards' file edits, no model save, no check weakening/deselection, no production code.

## Result

**Hypothesis: refuted. Run status: finished. Adoption: not ready. Review: OBSERVE evidence only, no PR.**
Contract `f55531a0009aef2ca2e5353bd8ae0aee07a42261`, measured runner `f42e840fc50b1e7067e729f4041b2143ddb56d77`.
Three fresh pairs: 345.415 / 338.143 / 313.859 s; median 338.143 s, spread 31.556 s, elapsed 999.735 s.
Pair 1 left room for both confirmations under the frozen 1.15× rule. A reproduced the exact #167 digest every time;
F payload digest was `9355a8c728aa40305caaf1b9a74046b283d2aeabc98aabfc52cc5bbdcef6c3a7` in all three pairs.
All 34 wall label maps had hits. PDF, FBX and Blender bytes were unchanged on postflight.

| Cohort | A: #167 glass stack | D: #149 on physical wall candidates | F: union |
|---|---:|---:|---:|
| Clean native full (7) | 2 / 0 / 5 | 1 / 0 / 6 | 3 / 0 / 4 |
| Clean native fragments (3, includes top-cut p20) | 1 / 0 / 2 | 0 / 0 / 3 | 1 / 0 / 2 |
| Injected mirrors, full (7) | 2 / 0 / 5 | 1 / 0 / 6 | 3 / 0 / 4 |
| Injected mirrors, fragments (3) | 1 / 0 / 2 | 0 / 2 / 1 | 1 / 2 / 0 |
| Injected blanks (10) | 0 / 0 / 10 | 0 / 0 / 10 | 0 / 0 / 10 |

Cells give correct / wrong / abstain. Full primary accuracy was 2/7 → 3/7; among answers it was 2/2 → 3/3,
with abstention 5/7 → 4/7. For clean fragments the answer accuracy and abstention were unchanged (1/1, 2/3).
All blank and mirror rows changed at least one channel; `p21 1-12` did not exercise the glass channel, but did
exercise the finish channel. Changed cells by state and channel are in the receipt. No native row exercised the
exact-ID agreement or conflict branch (both channels never answered together); those branches were unit-tested,
not measured on native inputs. The A `p18 I-A` positive retention control kept `W08`, but D abstained there.
The known #149 mirror witness `p19 10-1` did abstain. This did not prevent the two new wrong mirrors below.

| Witness | Frozen outcome | Actual |
|---|---|---|
| Opaque `p19 A-I` | D rescues a correct side | Abstain: 0.396 vs 0.335, below margin 0.10 |
| Slanted `p19 6-1` | Graded as an ordinary full view | D selects `W16`, correct azimuth 90, physical wall ID ungraded |
| Mirror `p24 frag 8-9` | No wrong side | `W16` at 0.810, azimuth 90 instead of 270 |
| Mirror top-cut `p20 frag 9-10` | No wrong side | `W12` at 1.000, azimuth 90 instead of 270 |

**Post-hoc mechanism, not a candidate replay.** The pair-1 support diagnostic reproduced all five inspected saved
scores at 9 decimal places and inspected the corresponding winning offsets. For the clean `6-1` match (17,939
overlapping cells, 96.3% of filled cells) and the wrong top-cut mirror (88 cells, 33.0%), the **overlap contains
exactly one view label**. Its true entropy is zero, but summing floating-point joint probabilities yielded
`H(V) = 1.1102230246251564e-16` in both cases; the `hv <= 0` guard did not fire and the quotient scored 1.0.
Thus the one new correct side is not sound evidence for a finish partition. The wrong `8-9` mirror had five
view labels and 5,204 overlapping cells (91.8%); rejecting constant partitions alone cannot explain that error,
and a generic higher overlap floor is not a substitute for handedness evidence. No revised scorer was measured.

**Next measurements (not implemented):** (1) reject one-label support explicitly in D and compare exact
multi-label score parity on real accepted controls and the two observed degenerate witnesses; (2) acquire an
independent labelled physical-wall/fragment pair on the named calibration projects, and verify handedness with
source plan/section corroboration, not with the finish score; (3) blind STOP 04 transfer only after #2001 closes.

## Evidence and checks

- [Bound receipt](autoresearch-view-face-wall-fusion/receipt.json), SHA-256
  `602e6c2347c70303ca9a1b8e98e871987bafb0fad570fb4169c88c78f94c85cd`.
- `G:/Мой диск/AGR-evidence/168-view-face-wall-fusion/` contains the mounted readback of the three native pairs,
  wall-type maps, wall renders, run and guard logs, and the diagnostic `ar168-support.py` +
  `ar168-support-entropy.json`. `SHA256SUMS.txt` covers 124 files, manifest SHA-256
  `e82a82807a4f45ac9aa75c9e5f2dc7940b73ace7cf5000dab809834187f3bc02`. Cloud sync was not verified.
- Replay is limited to the pinned Blender build and access to the named folder; the existing
  `G:/Мой диск/AGR-evidence/145-view-face-elv/run1/elv.pdf` and `elv.fbx` also matched the exact native input
  hashes. The primary runner uses the named inputs in the pinned fixture. The actual series wrapped the replay
  command in `timeout 2100s`, using output directory `tmp/ar168-R1`.
- Affected tests: `env -u PYTEST_ADDOPTS uv run --offline --locked --extra pdf-review pytest -q -p no:cacheprovider docs/research/autoresearch-view-face-wall-fusion/test_run.py docs/research/autoresearch-view-face-material/test_score.py` — 16 passed.
- `env -u PYTEST_ADDOPTS bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — GREEN, 572 passed.
- Full suite: deferred to merge batch (rule 68).
