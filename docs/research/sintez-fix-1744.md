# SINTEZ #1744 — замечания на доступных пакетах и точечные правки

**Кратко.** На доступной выборке чаще всего встречаются замечания к подписи,
комплектности НПМ и GeoJSON, а не к развёртке. Для правок выделена [отдельная
ячейка](../agents/SKELETONS-stages.md#sintez-fix): только по явной просьбе Артёма, только
на копиях. Исчезнувшее замечание не доказывает сохранение швов.

## Frequency table — partial census, not prevalence across all deliveries

The Russian datasets are under `G:/Мой диск/AGR-evidence/1744/census-v002/`:
`пакеты.csv` records original and copy paths and SHA-256; `отчёты.csv` links each
profile/round to its source; `замечания.csv` records checker message counts (not
face counts); `частота.csv` ranks by distinct projects with a finding × distinct
observed package rounds with that finding per profile. Byte-identical reruns of
one package in the same project/profile do not increase the rank. Pass and
unmeasured entries do not count as findings. The independent Staropetrovskiy
customer baseline is retained but excluded from ranking; ELV is an explicit
accepted-package control, not an additional repair round. Counts are reliable
within the listed reports only; targeted reruns and incomplete histories bias
cross-project ranks. The missing PSU275 primaries and unmeasured Vatutino NPM
are **unknown, not zero**. The source snapshots are under `C:/x/sintez-fix/`
with `SHA256SUMS`.

| Место | Профиль / код | Замечание | Объекты × пакет-раунды | Источники | Правка до → после |
|---:|---|---|---:|---|---|
| 1 | ВПМ 2.1.1 | Размер ZIP / УКЭП | 5 × 20 = 100 | Элеваторная, Старопетровский v001–v007, КПП1 v001–v004, ТЭЦ26 AC08, Ватутино v007 | Не подтверждена: нет подлинной пары ZIP ВПМ + УКЭП и прогона с сохранением `.sig`. |
| 2–4 | ВПМ 2.2.1 | Структура и синтаксис | 3 × 12 = 36 | КПП1 v001–v004, ТЭЦ26 AC08, Ватутино v007 | Измерена на контрольной копии Элеваторной: обрезанный GeoJSON `fail` → `pass`; FBX и карты не изменились. |
| 2–4 | НПМ 2.1.1 | Размер ZIP / УКЭП | 3 × 12 = 36 | Старопетровский до v014 / v014 / v015, КПП1 v001 / v002 / v004, ТЭЦ26 AC08 | Не подтверждена: нет подлинной пары ZIP НПМ + УКЭП и прогона с сохранением `.sig`. |
| 2–4 | НПМ 2.1.2 | 2–21 FBX в ZIP | 3 × 12 = 36 | Старопетровский до v014 / v014 / v015, КПП1 v001 / v002 / v004, ТЭЦ26 AC08 | Не подтверждена: нет одобренного недостающего FBX того же участка и ревизии. |
| 5 | ВПМ 2.2.6 | Заполнение полей | 2 × 11 = 22 | Старопетровский v001–v007, КПП1 v001–v004 | Измерена на контрольной копии Элеваторной: пустое `FNO_name` `fail` → `pass`; FBX и карты не изменились. |

## Recipes and boundaries

1. **VPM 2.1.1**: split size from signature. For size, recompress losslessly
   through the package owner and compare every payload member; if still too big,
   stop before modifying maps or topology. For signature, route the exact final
   ZIP to the authorized signer. Never create a dummy `.sig`. The checker wrapper
   copies ZIPs only, so the signature recommendation on isolated copies is not
   evidence of the actual signature status at delivery.
2. **VPM 2.2.1**: preserve FBX and map member bytes, correct only the specific
   syntax issue in the proved project GeoJSON, then run `agr validate` and
   `agr checker`. Vatutino v007 is missing the whole file; it needs a source for
   this export's placement, not an empty template. KPP1's FNO and the material
   recommendation under the same code must be assessed separately.
3. **NPM 2.1.1**: same size/signing route, NPM limit and exact NPM archive. Don't
   reuse a signature over different bytes or treat the VPM result as NPM coverage.
4. **NPM 2.1.2**: use `agr package-npm` with the approved Ground and OKS members
   from the same site/revision in the same coordinate frame. Verify unchanged
   FBX SHA-256 (embedded maps included). The one-FBX diagnostics are not complete
   deliveries. No unrelated or doubled FBX to get a count of two.
5. **VPM 2.2.6**: correct individual fields from project sources. Never fill
   FNO, area or height by guess. A real Staropetrovskiy test replacing `ZU_area=0`
   with an empty string preserved all FBX/PNG bytes but promoted this recommendation
   to an error; the naive recipe is rejected. The authoritative area is needed.

For the commonly observed geometry classes, not substitutes for ranks 1–5:
`master-qa` localizes topology changes before touching the export, `vpm-uv`
localizes collapsed, mirrored or cross-tile loops, and #1732 measures the exact
triangles. Fix only evidenced loops/faces through the existing owner. For texel,
adjustment of scale or texture pixels changes the physical result and requires
separate approval; don't repack the full facade. Compare indexed drift and map
bindings, and list changed/unmatched faces instead of treating them as preserved.

## Evidence status

ELV: fresh SINTEZ 1.6.1 at Blender 5.1.2, 66 pass / 1 review (signature) /
53 not measured / 0 fail. Acceptance by the customer is not a signed-ZIP
or all-checks-pass conclusion. Two deliberately seeded ELV controls (truncated
GeoJSON, missing FNO name) each went from fail to pass at the target rule after
restoring source metadata. All 98 non-GeoJSON members were byte-identical in
each pair. This proves the narrow metadata recipes, not repair of historical
KPP1/AC08 findings. Six unrelated checks were not measured in the restored ELV
run versus the earlier ELV baseline; no whole-checklist verdict is claimed.
For Staropetrovskiy, the prior v002→v003 tile
and opaque-mirroring repairs, v004→v005 opacity mirroring and v006→v007
unwrapped-triangle change remain historical checker pairs. See the before/after
sheet for the independent hash and drift measurements. These historical packages
are not production repair authorization. Three ranked rows (both signature
rows and the NPM composition row) still lack a valid measured fix on the
available copies. They need signed reference inputs/readback and the approved
same-revision missing FBX, respectively.
