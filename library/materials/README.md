# Библиотека материалов ОКС (#1024, ветка L)

- `materials.json` — указатель: `current` → `materials_v001.json`, `version`, `sha256` файла.
- `materials_v001.json` — 41 запись: 40 по аудиту материалов 06.11 (`GeoAGR-private research/materials-audit-1.0`) + 41 `larch_light_oak_boards` [D202].

## Поля записи

- `library_id` — 1..1000, стабильный; `key`, `name_ru`, `class`.
- `ral` — строка или `null`; `rgb_srgb` — экранное приближение из `tools/materials/ral_classic.json`, не измеренный RAL; `rgb_note`.
- `roughness` / `metallic` / `emissive` — байты 0..255 как в MaterialRegistry; у стекла `opacity` 0..1.
- `recipe` — `solid` | `metric_pattern` | `greyscale_mask`; `base_map` — имя серой маски (рецепт `greyscale_mask`).
- `status` — `proposed` | `approved` | `conflict` | `quarantine`.
- `source` — `audit`, `audit_id`, `evidence`; `maf_v005_id` — перекрёстная ссылка на МАФ v005; `questions` — номера вопросов аудита.

Особые случаи: у кирпича (запись 17) `ral = null`, потому что RAL 8023 нет в `ral_classic.json` (Q4);
у записей 4 и 32–34 (RAL 1021) взят `ral_classic` #F6B600, а не цвет КПП (238,201,0) (Q9).

## Правило версий

ID стабильны. Правка = новый `materials_vNNN.json` + новый sha256 в указателе (как MAF v005 / D181); старые версии не переписываются.

## Карты

Лежат на Google Диске `G:\Мой диск\AGR-assets\materials\`; читать только с копии (К5).

## Открытые вопросы

Q1–Q12 в `GeoAGR-private research/materials-audit-1.0/REPORT.md` §5 ждут ответа Артёма. Значения (px/м 1024, модули, шов) — параметры, не константы.
