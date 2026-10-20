# PartsList: stdlib schema checker versus JSON Schema

## Summary

`schema_errors` in `src/dt_ai/parts/readers/fbx.py` agrees with jsonschema **4.26.0** `Draft202012Validator` on **103 of 110** frozen synthetic instances. All **7** disagreements are `schema_errors` reject and jsonschema accept. Five are integral floats (`48.0`, `12.0`, `0.0`, `1.0`, `-0.0`) on `type: integer`: the checker requires a Python `int`, while Draft 2020-12 treats a zero fractional part as an integer. Two are non-JSON `numbers.Number` values (`Decimal`, `complex`) in a `type: number` region. Bool versus integer, fractional floats, required and extra fields, enums, patterns, lengths, `minItems`/`maxItems`, numeric bounds, `null`/`anyOf`, and `const` matched. The current `schemas/PartsList.schema.json` uses only keywords the checker implements (`Draft202012Validator.check_schema` passed). Adding `exclusiveMinimum`, `unevaluatedProperties`, or `$schema` raises `ValueError` and is not a schema verdict. Pydantic **2.13.5** on the converter path dumps JSON integers, so those seven inputs are not what `run()` feeds the checker. Pydantic also coerces `True` to `1` and rejects cross-field rules that both schema validators accept. Both schema validators accept `NaN`, and CPython `json.loads("NaN")` returns `nan`.

## Findings

Evidence labels: **Verified** means this session ran the command or read the file. **Sourced** means a primary document says it; the page was fetched, and the behaviour was not re-derived from that document's other implementations.

### Dialect actually selected

`schemas/PartsList.schema.json` has no `$schema` keyword (verified by reading the file). **Sourced:** jsonschema uses the schema's `$schema` when it names a known meta-schema; if `$schema` is absent, the default validator is the latest released draft ([jsonschema validating](https://python-jsonschema.readthedocs.io/en/stable/validate/)). **Verified:** `jsonschema.validators.validator_for` on this file returned `Draft202012Validator`, meta-schema `https://json-schema.org/draft/2020-12/schema`, package version **4.26.0** (`importlib.metadata.version("jsonschema")`). `Validator.check_schema(schema)` completed without error. Runtime was CPython **3.14.7** via `uv run --with jsonschema`. Pydantic in that environment was **2.13.5**.

The keyword set walked from the schema (`$defs`, `$ref`, `additionalProperties`, `anyOf`, `const`, `default`, `description`, `enum`, `items`, `maxItems`, `maxLength`, `maximum`, `minItems`, `minLength`, `minimum`, `pattern`, `properties`, `required`, `title`, `type`) is exactly the set `schema_errors` allows plus its annotation set. No keyword in the current file takes the `ValueError` path. `additionalProperties` appears only as `false`. The only `$ref` form is `#/$defs/...`. The only `$ref` sibling in the file is `description` on the root `triangle_budget`, which is an annotation, so draft-04 "ignore siblings of `$ref`" versus draft 2020-12 "evaluate siblings" does not change any instance in this schema.

### Corpus and verdicts

The corpus was fixed before the comparison loop. Every instance is synthetic.

- `valid_fixture`: `reader.convert(scene_a(), synthetic=True).model_dump_json()` parsed again with `json.loads`. `scene_a` is the same four-object synthetic scene as `tests/parts/test_fbx_reader.py` (Wall, slab, and two column instances). Part ids were `Column`, `Column_001`, `Slab_Roof`, `Wall_North`. `triangle_budget.npm` was Python `int` `48`.
- `valid_extended`: that object plus one legal embed joint (`Wall_North`/`Slab_Roof`, depth `0.015`), one question, a synthetic `gate1` approval, and `sources[0].region = [0.0, 0.0, 1.0, 1.0]`.
- Every other row is one mutation of one of those two objects. Constraints outside the schema (for example `uniqueItems`, `format`, `multipleOf`) were not invented as corpus rows.

Accept/reject only. An exception is not a reject. The 110-row run produced **0** exceptions. **24** rows were accept/accept, **79** were reject/reject, **7** were reject/accept, **0** were accept/reject.

| id | class | schema_errors | jsonschema 4.26.0 Draft 2020-12 |
|---|---|---|---|
| valid_fixture | valid | accept | accept |
| valid_extended | valid_optional_filled | accept | accept |
| drop_root_synthetic | required_root | reject | reject |
| drop_root_parts | required_root | reject | reject |
| drop_root_sources | required_root | reject | reject |
| drop_root_budget | required_root | reject | reject |
| drop_part_id | required_part | reject | reject |
| drop_part_sources | required_part | reject | reject |
| drop_part_budget | required_part | reject | reject |
| drop_part_source_kind | required_nested_source | reject | reject |
| drop_part_source_reference | required_nested_source | reject | reject |
| drop_budget_npm | required_budget | reject | reject |
| drop_joint_parts | required_joint | reject | reject |
| drop_joint_extra_edges | required_joint | reject | reject |
| drop_question_text | required_question | reject | reject |
| drop_approval_actor | required_approval | reject | reject |
| drop_source_reference | required_source_ref | reject | reject |
| extra_root | additional_root | reject | reject |
| extra_part | additional_part | reject | reject |
| extra_part_source | additional_nested_source | reject | reject |
| extra_budget | additional_budget | reject | reject |
| extra_joint | additional_joint | reject | reject |
| extra_source_ref | additional_source_ref | reject | reject |
| extra_question | additional_question | reject | reject |
| extra_approval | additional_approval | reject | reject |
| bool_total_npm | bool_as_integer | reject | reject |
| bool_part_vpm | bool_as_integer | reject | reject |
| bool_extra_edges | bool_as_integer | reject | reject |
| bool_page | bool_as_integer | reject | reject |
| float_total_npm_48 | integral_float_integer | reject | accept |
| float_part_npm_12 | integral_float_integer | reject | accept |
| float_extra_edges_0 | integral_float_integer | reject | accept |
| float_page_1 | integral_float_integer | reject | accept |
| negzero_npm | integral_float_integer | reject | accept |
| float_npm_48_5 | fractional_float_integer | reject | reject |
| float_page_1_5 | fractional_float_integer | reject | reject |
| gate1_null | anyof_null | accept | accept |
| legend_null | anyof_null | accept | accept |
| embed_null_on_extended | anyof_null | accept | accept |
| page_null | anyof_null | accept | accept |
| region_null | anyof_null | accept | accept |
| sha_null | anyof_null | accept | accept |
| build_as_null | anyof_null | accept | accept |
| gate1_wrong_type | anyof_reject | reject | reject |
| legend_empty | anyof_minlength | reject | reject |
| answer_empty | anyof_minlength | reject | reject |
| sha_short | anyof_pattern | reject | reject |
| build_as_box | anyof_enum_ok | accept | accept |
| build_as_bad | enum | reject | reject |
| tier_bad | enum | reject | reject |
| part_class_bad | enum | reject | reject |
| operation_bad | enum | reject | reject |
| status_bad | enum | reject | reject |
| joint_decision_bad | enum | reject | reject |
| part_source_kind_bad | enum_nested_source | reject | reject |
| audience_bad | enum | reject | reject |
| source_kind_bad | enum | reject | reject |
| scope_bad | enum | reject | reject |
| id_bad | pattern_id | reject | reject |
| part_id_bad | pattern_id | reject | reject |
| id_empty | pattern_id | reject | reject |
| id_len_120 | length_boundary | accept | accept |
| id_len_121 | length_boundary | reject | reject |
| part_id_len_121 | length_boundary | reject | reject |
| joint_part_id_bad | pattern_id | reject | reject |
| date_ok | pattern_date | accept | accept |
| date_unpadded | pattern_date | reject | reject |
| date_unicode_digits | pattern_unicode_digit | accept | accept |
| sha_upper | pattern_sha | reject | reject |
| reference_empty | minlength_nested_source | reject | reject |
| reason_empty | minlength | reject | reject |
| actor_empty | minlength | reject | reject |
| parts_empty | minitems | reject | reject |
| root_sources_empty | minitems | reject | reject |
| part_sources_empty | minitems_nested_source | reject | reject |
| joint_parts_one | minitems | reject | reject |
| joint_parts_three | maxitems | reject | reject |
| region_three | minitems | reject | reject |
| region_five | maxitems | reject | reject |
| region_four_ints | number_accepts_int | accept | accept |
| npm_neg | numeric_minimum | reject | reject |
| npm_zero_part | numeric_minimum | accept | accept |
| extra_edges_neg | numeric_minimum | reject | reject |
| embed_low | numeric_bounds | reject | reject |
| embed_min | numeric_bounds | accept | accept |
| embed_max | numeric_bounds | accept | accept |
| embed_high | numeric_bounds | reject | reject |
| embed_int_zero | number_rejects_out_of_range_int | reject | reject |
| page_zero | numeric_bounds | reject | reject |
| page_one | numeric_bounds | accept | accept |
| page_max | numeric_bounds | accept | accept |
| page_over | numeric_bounds | reject | reject |
| const_bad | const | reject | reject |
| const_ok | const | accept | accept |
| omit_status | annotation_default_not_applied | accept | accept |
| omit_schema_version | const_not_required | accept | accept |
| synthetic_string | type | reject | reject |
| parts_object | type | reject | reject |
| object_id_number | type | reject | reject |
| parts_null | type | reject | reject |
| region_string_item | nested_source_item_type | reject | reject |
| region_bool_item | bool_as_number | reject | reject |
| embed_bool | bool_as_number | reject | reject |
| embed_nan | nonfinite_number | accept | accept |
| embed_inf | nonfinite_number | reject | reject |
| region_nan | nonfinite_number | accept | accept |
| region_decimal | decimal_number | reject | accept |
| region_complex | complex_number | reject | accept |
| npm_decimal_integral | decimal_integer | reject | reject |
| parts_tuple | tuple_not_array | reject | reject |

`embed_min` / `embed_max` use Python floats `0.01` and `0.02`. Both checkers use those same IEEE values, and both accept the inclusive bounds. That is parity, not a proof that the decimal literals are exact.

`date_unicode_digits` is the synthetic date `२०२४-०१-०१` (Devanagari digits). Both checkers accept it. See pattern semantics below. It is not counted as a checker disagreement.

`omit_status` and `omit_schema_version` are accept/accept because `default` is an annotation and `schema_version` is not in `required`. Neither checker fills defaults.

### Integer and number semantics

**Sourced:** JSON Schema 2020-12 validation, section 6.1.1: `integer` "matches any number with a zero fractional part" ([spec](https://json-schema.org/draft/2020-12/json-schema-validation#section-6.1.1)). **Sourced:** jsonschema's Draft 4 integer check is "Python `int` and not `bool`"; from Draft 6 onward, including Draft 2020-12, a float whose `is_integer()` is true also counts ([`jsonschema._types`](https://python-jsonschema.readthedocs.io/en/stable/_modules/jsonschema/_types/), [referencing note](https://python-jsonschema.readthedocs.io/en/v4.18.6/referencing/)). **Sourced:** the `number` type checker accepts `numbers.Number`, explicitly including `int`, `float`, `decimal.Decimal`, and `complex` ([jsonschema validating](https://python-jsonschema.readthedocs.io/en/stable/validate/)).

**Verified** on 4.26.0, schema `{"type": "integer"}`:

| value | schema_errors | Draft202012Validator | Draft4Validator |
|---|---|---|---|
| `48` | accept | accept | accept |
| `48.0` | reject | accept | reject |
| `-0.0` | reject | accept | not run |
| `48.5` | reject | reject | not run |
| `True` / `False` | reject | reject | `True` reject |
| `Decimal("48")` | reject | reject | not run |
| `float("nan")` | reject | reject | not run |

`_type_ok` (`fbx.py` lines 300-305) is the Draft 4 integer rule: `isinstance(value, int) and not isinstance(value, bool)`. The PartsList file is otherwise a 2020-12-shaped schema (`$defs`, `const`, `anyOf`) with no `$schema` marker, and `validator_for` therefore applies the 2020-12 integer rule. The five `integral_float_integer` rows are that gap on real PartsList locations: total `npm`, part `npm`, joint `extra_edges`, and `page` inside `anyOf`. `json.loads("48.0")` is a Python `float` (verified), so a hand-written JSON document can produce them. `Decimal("48")` as an integer agrees (both reject). `Decimal` and `complex` disagree only where the schema says `number` (the region items).

Separate from the 110, on bare `{"type": "number"}` both checkers accepted `nan`, `inf`, and `-inf` (verified). Inside PartsList, `embed_inf` is reject/reject because `maximum` is `0.02`. `embed_nan` and `region_nan` are accept/accept: a NaN comparison does not fail `minimum`/`maximum` in `schema_errors` (`nan < bound` and `nan > bound` are both false), and the region items have no numeric bounds. jsonschema 4.26 accepts those non-finite floats as numbers too.

### Pattern semantics

**Sourced:** `pattern` should be an ECMA-262 regular expression and is not implicitly anchored ([JSON Schema validation 6.3.3](https://json-schema.org/draft/2020-12/json-schema-validation#section-6.3.3)). **Sourced:** jsonschema does not implement ECMA-262; `pattern` uses Python regular expressions ([jsonschema validating](https://python-jsonschema.readthedocs.io/en/stable/validate/)). **Sourced:** Python `re` `\d` matches Unicode category Nd unless `re.ASCII` is set ([Python `re`](https://docs.python.org/3/library/re.html)). **Verified:** `schema_errors` calls `re.search` (`fbx.py` line 335) with no ASCII flag. Every `pattern` in this schema is already anchored with `^` and `$`, so search versus fullmatch does not split the two checkers. ASCII id, sha256, and date cases agreed. The Devanagari date agreed as well: both accept it. An ECMA-262 engine was not run, so this note does not claim an ECMA verdict for that string. It does say the two Python checkers share Python's `\d`.

`minLength` / `maxLength` agreed, including id length 120 accept and 121 reject. **Sourced:** JSON Schema defines string length as the RFC 8259 character count ([validation 6.3.2](https://json-schema.org/draft/2020-12/json-schema-validation#section-6.3.2)). These checkers both use Python `len` on `str`. No supplementary-plane case was in the corpus.

### Unsupported keywords are not verdicts

**Verified**, separate from the 110:

| schema change | instance | schema_errors | Draft202012Validator |
|---|---|---|---|
| root `unevaluatedProperties: false` on PartsList | valid fixture (`npm` 48) | `ValueError: schema keywords not supported: ['unevaluatedProperties']` | accept (the fixture has no unevaluated properties, so the keyword does not fail it) |
| `exclusiveMinimum: 0` on `TriangleBudget.npm` | valid fixture (`npm` 48) | `ValueError: schema keywords not supported: ['exclusiveMinimum']` | accept (`48 > 0`) |
| `{"type":"integer","exclusiveMinimum":0}` | `0` | `ValueError` | reject |
| same | `1` | not run | accept |
| `{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"integer"}` | `1` | `ValueError: schema keywords not supported: ['$schema']` | not run |

The checker fails closed when it sees a keyword outside its set. That raise happens even when the reference validator would still accept the instance. It is not an accept, and it was not entered in the 103/7 counts. Vocabulary present in Draft 2020-12 and absent from this checker includes, from the probes and from the allow-list in `schema_errors`: `$schema`, `exclusiveMinimum`, `exclusiveMaximum`, `multipleOf`, `unevaluatedProperties`, and the other keywords not listed in the allow-list (`allOf`, `oneOf`, `not`, `if`/`then`/`else`, `format`, `patternProperties`, `prefixItems`, `contains`, `uniqueItems`, and property-count keywords). None of those appear in the current PartsList schema.

### What Pydantic hides

`run()` (`fbx.py` lines 382-386) builds a `PartsList`, dumps it with `model_dump_json()`, parses that JSON, calls `PartsList.model_validate` on the dump, then `schema_errors` on the same dump. The dump's budgets are JSON integers (verified on the fixture: `int` 48). The seven disagreements are therefore not inputs to the converter's schema check.

**Verified** coercion on the raw dict, before any dump:

- `PartsList.model_validate` of the fixture with both total budgets set to `48.0` succeeds. The following dump has `npm` as `int` 48, and `schema_errors` on that dump accepts. The integral-float disagreement disappears if validation-and-dump happens first.
- `TriangleBudget.model_validate({"npm": True, "vpm": 0}).model_dump()` is `{"npm": 1, "vpm": 0}` with `npm` type `int`. `True` becomes `1`. On the full fixture, setting only the total `npm` to `True` raises `ValidationError` because part budgets sum to 48 against total 1, which is the sum rule after coercion, not a boolean type error. `schema_errors` and jsonschema both reject `True` on that field. Pydantic-first does not.
- `TriangleBudget.model_validate({"npm": float("nan"), "vpm": 0})` raises `ValidationError`. `Strict` sets `allow_inf_nan=False` (`model.py` line 29). Both schema validators still accept `embed_nan` and `region_nan`. **Verified:** `json.loads("NaN")` returns `nan` under this CPython, so a Python JSON load of a non-RFC `NaN` token can reach the schema checkers without passing through the model.

Cross-field rules live on the model and are absent from the schema. **Verified** on synthetic mutations: both schema validators accept, `PartsList.model_validate` rejects.

| input | model message (first error) |
|---|---|
| duplicate part id | part ids must be unique |
| `status="confirmed"`, `gate1` null | confirmed needs the gate 1 approval of the user |
| total `npm` 0 while parts still sum to 48 | npm: part budgets add up to 48, over the total 0 |
| `operation="primitive"` with `build_as` null | build_as is required by the primitive operation and only by it |
| `operation="library_replace"` with `library_ref` null | library_ref is required by library_replace and only by it |
| `mesh="../out.fbx"` | mesh must be a relative path inside the job |
| joint `decision="weld"` while `embed_depth_m` is `0.015` | embed_depth_m is required by embed and only by it |

`embed_null_on_extended` is accept/accept in the schema table. The same `Joint.decision_fields` validator (`model.py` lines 76-80) rejects embed without a depth; that exact null row was not passed to `model_validate` in this session. The weld-with-depth row above was.

`docs/domain/validation.md` is the delivery-package checker inventory. It does not define PartsList keyword parity. No delivery V-code was treated as a result of this comparison.

## How it applies to this repository

- `src/dt_ai/parts/readers/fbx.py`: `_type_ok` (lines 300-305), the keyword allow-list and `ValueError` (lines 308-316), `re.search` (line 335), numeric comparisons that do not exclude NaN (lines 337-339), and `run()` order model dump then `schema_errors` (lines 383-386).
- `schemas/PartsList.schema.json`: the schema under test. No `$schema`. Integer budgets, `page`, and `extra_edges` are `type: integer`. Region items and embed depth are `type: number`. Patterns are anchored.
- `src/dt_ai/parts/model.py`: `allow_inf_nan=False`, operation/joint/list validators that the schema does not express (lines 29, 54-64, 76-80, 103-126).
- `tests/parts/test_fbx_reader.py`: `test_schema_validator_rejects_bad_instances` (lines 271-280) already checks extra field, missing `parts`, bad id, bad tier, negative budget, empty `parts`, and `ValueError` on `unevaluatedProperties`. It does not include an integral float, `NaN`, or a cross-field case.
- Converter output checked by `run()` stays on the agreeing subset, because the dump uses Python `int` for budgets.

## Proposed next tasks

1. **Match Draft 2020-12 integer on finite integral floats** — Change `_type_ok("integer")` so a finite float with `is_integer()` true is an integer, leaving `True`, `False`, `48.5`, and non-finite floats rejected. Do not add a jsonschema dependency. Input: the synthetic scene_a dump with `triangle_budget.npm = 48.0` → `schema_errors` returns `[]` and `Draft202012Validator.is_valid` is true. Input: `48.5` → both reject. Input: `True` → both reject. The converter dump stays `int` 48, so `run()` output does not change. Value: the only JSON-text disagreement with the reference validator closes. Effort **S**.

2. **Keep model-only rules visible beside the schema checker** — Add assertions, in the existing parts reader tests, that schema acceptance is not PartsList acceptance. Input: synthetic fixture with `status="confirmed"` and `gate1` null → `schema_errors` is `[]`, `Draft202012Validator.is_valid` is true, and `PartsList.model_validate` raises `ValidationError` containing `confirmed needs the gate 1 approval`. Input: the same fixture with two parts sharing one id → both schema validators accept, and `model_validate` raises `ValidationError` containing `part ids must be unique`. Value: a later reader of `schema_errors` cannot treat an empty list as gate 1. Effort **S**.

## Open questions for the user

- Should `integer` in this checker stay "Python `int` and not `bool`" (today, and Draft 4), or follow Draft 2020-12 and accept a finite zero-fraction float? This note does not switch it.
- Should non-finite floats be rejected in `_type_ok` even though jsonschema 4.26 accepts them as `number`? Both checkers accept `NaN` today; Pydantic already rejects it.
- Should the model-only rules (unique ids, budget sum, operation fields, confirmed versus `gate1`, relative `mesh`) be copied into `PartsList.schema.json`? Both validators currently accept those instances.
- Adopting jsonschema as a project dependency is a separate decision. This comparison used a transient `uv run --with jsonschema` install and did not edit `pyproject` or the lockfile.

## Reproduction

Transient install, from the repository root. Synthetic scene only. The import of `dt_ai.core.models` first avoids the `PartsList` cycle in `core/models.py`.

```python
import json
import dt_ai.core.models  # noqa: F401
from importlib.metadata import version
from jsonschema.validators import Draft4Validator, validator_for
from dt_ai.parts.readers import fbx as reader

schema = json.loads(open("schemas/PartsList.schema.json", encoding="utf-8").read())
Validator = validator_for(schema)
print(version("jsonschema"), Validator.__name__, schema.get("$schema"))

def obj(name, bbox):
    return {"name": name, "type": "MESH", "parent": None, "collections": [],
            "mesh": name + "_mesh", "material_slots": ["M0"],
            "face_material_counts": {"0": 6}, "triangle_material_counts": {"0": 12},
            "triangles": 12, "polygons": 6, "bbox": {"min": list(bbox[0]), "max": list(bbox[1])},
            "connected_components": 1}

facts = {"format": "fbx_structure/1",
         "source": {"name": "model.fbx", "path": "C:/x/model.fbx", "sha256": "a" * 64, "bytes": 10},
         "blender": "5.1.2", "units": {"system": "METRIC", "scale_length": 1.0, "length_unit": "METERS"},
         "sections": "not_in_fbx", "contact_tolerance_m": 0.002,
         "objects": [obj("Wall_North", ((0, 0, 0), (1, 1, 1)))],
         "components": [], "contacts": []}
data = json.loads(reader.convert(facts, synthetic=True).model_dump_json())
data["triangle_budget"]["npm"] = 48.0
print("schema_errors", reader.schema_errors(data, schema)[:1])
print("draft2020", Validator(schema).is_valid(data))
print("draft4_bare", Draft4Validator({"type": "integer"}).is_valid(48.0))
try:
    reader.schema_errors(data, {**schema, "unevaluatedProperties": False})
except ValueError as exc:
    print(type(exc).__name__, exc)
```

Expected with the current checker and jsonschema 4.26.0: `schema_errors` reports `expected integer`; Draft 2020-12 `is_valid` is true; Draft 4 `is_valid(48.0)` is false; `unevaluatedProperties` raises `ValueError`.

## Sources

- **Verified:** the 110-row comparison, the unsupported-keyword probes, the Pydantic coercion and cross-field probes, `json.loads("48.0")` and `json.loads("NaN")`, and the file bytes below. No test suite, no DCC, no schema edit.
- **Branch ref** `docs/research-parts-schema-checker-parity`: `c2c90074c29433e09fe925e2885a361560c88088`, read from `.git/refs/heads/docs/research-parts-schema-checker-parity`. Those four paths were unmodified relative to that ref at the start of this work.
- **Content SHA-256 of the files executed against:**
  - `src/dt_ai/parts/readers/fbx.py` `292f132a63bdd4fcf16c90d0bbf2540f4351dde8e6664b52eb1f43719d6b5030`
  - `schemas/PartsList.schema.json` `6530a652d22b6a857c4a5735529c5685b4471f84368918bbcd994634b3c99f42`
  - `src/dt_ai/parts/model.py` `d17c8d69705c4c44636f8d2fe1722cde034218757683fbf43ed2d098ea9709e6`
  - `tests/parts/test_fbx_reader.py` `2762887d2d3253b0b9585a79c6a1da5f97651b8ab027be3934e0951dcbac5462`
- **Sourced:** [JSON Schema 2020-12 validation](https://json-schema.org/draft/2020-12/json-schema-validation) (integer, pattern, minLength); [jsonschema validation](https://python-jsonschema.readthedocs.io/en/stable/validate/) (`$schema` default, `numbers.Number`, Python `pattern`); [jsonschema `_types`](https://python-jsonschema.readthedocs.io/en/stable/_modules/jsonschema/_types/); [Python `re`](https://docs.python.org/3/library/re.html) (`\d` and Nd).
