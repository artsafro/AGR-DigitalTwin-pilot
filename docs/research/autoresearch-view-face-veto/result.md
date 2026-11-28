# #147 — OBSERVE round result

**Кратко (RU):** гипотеза H147 **опровергнута** (3 свежих пары, все идентичны, паритет A/B с #146 212/212 в каждой).
Вето несогласия C («отвечать, только если сырой A и поправленный B выбрали один фасад») убрало новые ошибки B на KPP1
(0 ошибок, покрытие KPP1 сохранено: 3 полных, 22 фрагмента) и 12 из 13 ошибок «плотного восточного фасада» ELV, но:
(1) осталась 1 уверенная ошибка на синтетическом фрагменте ELV `p19 A-I partial25@1.0` и 1 на зеркале `p19 10-1` —
там A и B ошибаются **одинаково** (оба смотрят на одни и те же рёбра, ошибки коррелированы); (2) покрытие фрагментов ELV
14 < порога 15. Вывод: согласие двух оценщиков одного признака — фильтр безопасности, но не независимое
доказательство; для шага «карта вид↔фасад» нужен второй, **независимый** признак (контур/рёбра плана, стыки с
возвратными стенами, окна из объектов). Соколники не открывались (#2001 OPEN). Ничего в продакшн не применено.

**Hypothesis: refuted. Adoption: no (OBSERVE).** Series `C:/x/ar147/series2`, status `finished`, 3/3 pairs with
identical `veto.json` hashes, `b_parity` true in every pair (A and B rows equal the published #146 receipt, 212 rows),
measured head `5e09a5ac19b08072dbc41215ab3f00ff3d478b16`, uv.lock `ba1bb998…`.

| Cohort / scope | A: correct / wrong / abstain | B | C (veto) |
| --- | --- | --- | --- |
| ELV full (clean) | 5 / 0 / 2 | 7 / 0 / 0 | 5 / 0 / 2 |
| ELV real fragments (clean) | 1 / 0 / 1 | 1 / 0 / 1 | 1 / 0 / 1 |
| ELV top-cut fragment (clean) | 0 / 0 / 1 | 0 / 0 / 1 | 0 / 0 / 1 |
| ELV synthetic partials (injected) | 15 / 13 / 35 | 37 / 1 / 25 | **14 / 1 / 48** |
| ELV mirror (injected) | 2 / 1 / 4 | 2 / 1 / 4 | **2 / 1 / 4** |
| KPP1 full (clean) | 3 / 0 / 1 | 3 / 1 / 0 | 3 / 0 / 1 |
| KPP1 synthetic partials (injected) | 22 / 0 / 14 | 26 / 1 / 9 | 22 / 0 / 14 |
| KPP1 mirror (injected) | 0 / 0 / 4 | 0 / 0 / 4 | 0 / 0 / 4 |
| AC08 full + partials (clean) | 0 / 0 / 40 | 0 / 0 / 40 | 0 / 0 / 40 |
| AC08 mirror | 0 / 0 / 1, 3 not_exercised | same | same |
| OBR22 full + partials + mirror | 0 / 0 / 44 | 0 / 0 / 44 | 0 / 0 / 44 |

Gate failures: C wrong = 2 (`elv/crop p19 A-I partial25@1.0` -> az 0, `elv/mirror p19 10-1` -> az 270; A and B
agree on both), and ELV crop correct 14 < 15 (lost `p18 I-A partial60@0.0`, where B abstains). Positive witness:
12 of 13 #145 east-attractor crops abstain under C, 1 remains wrong. Trigger on B-only wrong (KPP1 `В-А` full): C
abstains, as frozen. Over all rows 30 cases where A or B was correct are lost to abstention (mostly the 23 ELV crops B
fixed but A missed). Retention on AC08/OBR22: **not measured** (no correct row in either arm); 3 AC08 mirrors are
**not exercised** (zero changed pixels). Not measured: real unlabeled inner-corner transfer, within-face position, G22,
Vatutino, Sokolniki.

Timing: pair 204.416 / 201.698 / 200.938 s (median 201.698, spread 3.478 s), series wall 607.107 s vs ceiling 1500 s.
A first launch (`C:/x/ar147/series1`) crashed in the harness (`KeyError: 'changed_edge_px'` on OBR22 non-mirror rows,
runner bug, fixed in `5e09a5ac`); it is not counted.

Receipt: `docs/research/autoresearch-view-face-veto/receipt.json` (SHA-256
`1569182b4791aa1029085c617364d7c90b2bc497b19aee4750c5fd7f8db337e2`); logs + receipt in
`G:/Мой диск/AGR-evidence/147-view-face-veto/` + `SHA256SUMS.txt`. Replay (pilot host):
`uv run --offline --locked --extra cad --extra pdf-review python docs/research/autoresearch-view-face-veto/run.py C:/x/ar147/<fresh>`.

Recommendation for the shared OKS-trail step 'view<->face map sheet' (measured part): run A and B, answer only on
agreement (0 wrong on all clean rows of four accepted projects in this round), show the top candidates and margins,
and send every disagreement and every **synthetic-partial-sized** view to Artem as a 2-candidate question; agreement
alone is not sufficient for partial views because the two scorers share the edge-density feature. Next measure: an
independent cue (plan footprint edge lengths / return-wall corners at the view edges) whose errors are not correlated
with edge density, scored on the same 212 rows.
