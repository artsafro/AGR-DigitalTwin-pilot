"""new-case: visited-node failures of schema_errors on synthetic schemas.

The root-level unevaluatedProperties raise is already pinned in
tests/parts/test_fbx_reader.py (test_schema_validator_rejects_bad_instances).
These tests characterize the same fail-closed raise on nodes the checker
actually visits: a present property, a present item, a local ``#/$defs``
target, and the single branch of an anyOf. Synthetic schemas only.
"""
import copy

import pytest

from dt_ai.parts.readers import fbx as reader

# Keywords the checker rejects. None of these are on the allow-list in schema_errors.
_UNSUPPORTED = {"exclusiveMaximum": 5, "exclusiveMinimum": 0, "multipleOf": 2}


def _call(instance, schema):
    """Run schema_errors and require both arguments to be unchanged."""
    instance_before = copy.deepcopy(instance)
    schema_before = copy.deepcopy(schema)
    try:
        return reader.schema_errors(instance, schema)
    finally:
        assert instance == instance_before
        assert schema == schema_before


def _visited(keywords):
    """Schemas where `keywords` sits on a node the walk actually enters."""
    node = {"type": "integer", **keywords}
    return {
        "property": ({"x": 1}, {"type": "object", "properties": {"x": node}}),
        "items": ([1], {"type": "array", "items": node}),
        "anyOf": (1, {"anyOf": [node]}),
        "ref": (1, {"$ref": "#/$defs/X", "$defs": {"X": node}}),
    }


def test_visited_property_exclusive_minimum_raises():
    instance = {"x": 1}
    schema = {"type": "object", "properties": {"x": {"type": "integer", "exclusiveMinimum": 0}}}
    with pytest.raises(ValueError, match="exclusiveMinimum") as caught:
        _call(instance, schema)
    message = str(caught.value)
    assert message.startswith("schema keywords not supported:")
    assert "expected" not in message
    assert "out of range" not in message


def test_visited_items_multiple_of_raises():
    instance = [1]
    schema = {"type": "array", "items": {"type": "integer", "multipleOf": 2}}
    with pytest.raises(ValueError, match="multipleOf") as caught:
        _call(instance, schema)
    assert str(caught.value).startswith("schema keywords not supported:")


def test_local_ref_target_exclusive_maximum_raises():
    instance = 1
    schema = {"$ref": "#/$defs/X", "$defs": {"X": {"type": "integer", "exclusiveMaximum": 5}}}
    with pytest.raises(ValueError, match="exclusiveMaximum") as caught:
        _call(instance, schema)
    assert str(caught.value).startswith("schema keywords not supported:")


def test_one_branch_anyof_names_the_unsupported_keyword():
    instance = 1
    schema = {"anyOf": [{"type": "integer", "format": "date"}]}
    with pytest.raises(ValueError, match="format") as caught:
        _call(instance, schema)
    assert str(caught.value) == "schema keywords not supported: ['format']"


def test_visited_node_names_both_unsupported_keywords_sorted():
    instance = {"x": 1}
    schema = {"type": "object", "properties": {
        "x": {"type": "integer", "multipleOf": 2, "exclusiveMinimum": 0}}}
    with pytest.raises(ValueError) as caught:
        _call(instance, schema)
    assert str(caught.value) == "schema keywords not supported: ['exclusiveMinimum', 'multipleOf']"


def test_external_ref_raises():
    schema = {"$ref": "https://example.invalid/schema.json"}
    with pytest.raises(ValueError, match="unsupported \\$ref") as caught:
        _call(1, schema)
    assert "unsupported $ref" in str(caught.value)


def test_local_integer_ref_with_minimum_sibling():
    schema = {"$ref": "#/$defs/X", "minimum": 2, "$defs": {"X": {"type": "integer"}}}
    errors = _call(1, schema)
    assert isinstance(errors, list)
    assert errors
    assert any(error.startswith("$:") and "out of range" in error for error in errors)
    assert _call(2, schema) == []


def test_supported_nested_integer_is_an_ordinary_error():
    errors = _call({"x": "bad"}, {"type": "object", "properties": {"x": {"type": "integer"}}})
    assert isinstance(errors, list)
    assert "$.x: expected integer" in errors


def test_probe_visited_unsupported_keyword_never_returns_a_verdict():
    """Every unsupported keyword on a visited node raises; it never returns [] or a list."""
    n = 0
    for keyword, value in _UNSUPPORTED.items():
        for instance, schema in _visited({keyword: value}).values():
            with pytest.raises(ValueError) as caught:
                _call(instance, schema)
            assert str(caught.value) == f"schema keywords not supported: [{keyword!r}]"
            n += 1
    assert n == len(_UNSUPPORTED) * 4


def test_probe_two_unsupported_keywords_are_sorted_on_every_visit():
    """Both names appear once, in sorted order, on every kind of visited node."""
    n = 0
    keywords = list(_UNSUPPORTED)
    for i, left in enumerate(keywords):
        for right in keywords[i + 1:]:
            ordered = sorted((left, right))
            expected = f"schema keywords not supported: {ordered}"
            for instance, schema in _visited({left: _UNSUPPORTED[left], right: _UNSUPPORTED[right]}).values():
                with pytest.raises(ValueError) as caught:
                    _call(instance, schema)
                assert str(caught.value) == expected
                n += 1
    assert n == (len(keywords) * (len(keywords) - 1) // 2) * 4


def test_probe_supported_nested_mismatch_never_raises():
    """A supported nested integer check returns a list naming $.x, and does not raise."""
    bad = ("bad", True, False, 1.5, None, [], {})
    n = 0
    schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
    for value in bad:
        errors = _call({"x": value}, schema)
        assert isinstance(errors, list)
        assert "$.x: expected integer" in errors
        n += 1
    assert n == len(bad)
