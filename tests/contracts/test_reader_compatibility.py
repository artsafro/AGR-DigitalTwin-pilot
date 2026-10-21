"""Characterize the compatibility boundaries of the two public JSON/YAML readers.

new-case: independent JSON/YAML reader encoding, nonfinite and merge compatibility.

AGR reader = ``dt_ai.core.io``; QA reader = ``twinqa.io``. Every test pins the
CURRENT observed behaviour of one reader against a literal expected value or error.
No test uses the other reader's output as its expected value (oracle). Legacy
returns (e.g. AGR accepting UTF-16/32 BOM bytes or nonfinite YAML floats) are
recorded as observations, not as approval of a universal encoding / merge /
numeric policy. JSON exponent-overflow caller exposure is deliberately out of
scope here and owned by the separate research item.
"""

import json
import math

import pytest

from dt_ai.core.io import read_json as agr_read_json
from dt_ai.core.io import read_yaml as agr_read_yaml
from twinqa.io import read_json as qa_read_json
from twinqa.io import read_yaml as qa_read_yaml


def _write_yaml(tmp_path, name, raw_bytes):
    path = tmp_path / name
    path.write_bytes(raw_bytes)
    return path


# --- JSON encoding family -------------------------------------------------

UTF8_BYTES = b'{"outer": {"s": "ok", "n": 1.25, "items": [1, 2, 3]}}'
UTF8_STR = '{"outer": {"s": "ok", "n": 1.25, "items": [1, 2, 3]}}'
UTF8_EXPECTED = {"outer": {"s": "ok", "n": 1.25, "items": [1, 2, 3]}}

UTF16LE_BOM = b'\xff\xfe{\x00"\x00n\x00"\x00:\x001\x00}\x00'
UTF32LE_BOM = (b'\xff\xfe\x00\x00{\x00\x00\x00"\x00\x00\x00n\x00\x00\x00'
               b'"\x00\x00\x00:\x00\x00\x001\x00\x00\x00}\x00\x00\x00')
UTF8_BOM_BYTES = b'\xef\xbb\xbf{"n":1}'
BOM_STR = '\ufeff{"n":1}'


@pytest.mark.parametrize("raw", [UTF8_BYTES, UTF8_STR], ids=["bytes", "string"])
def test_json_utf8_nested_finite_agr(raw):
    assert agr_read_json(raw) == UTF8_EXPECTED


@pytest.mark.parametrize("raw", [UTF8_BYTES, UTF8_STR], ids=["bytes", "string"])
def test_json_utf8_nested_finite_qa(raw):
    assert qa_read_json(raw) == UTF8_EXPECTED


def test_json_utf16le_bom_bytes_agr():
    assert agr_read_json(UTF16LE_BOM) == {"n": 1}


def test_json_utf16le_bom_bytes_qa():
    with pytest.raises(UnicodeDecodeError):
        qa_read_json(UTF16LE_BOM)


def test_json_utf32le_bom_bytes_agr():
    assert agr_read_json(UTF32LE_BOM) == {"n": 1}


def test_json_utf32le_bom_bytes_qa():
    with pytest.raises(UnicodeDecodeError):
        qa_read_json(UTF32LE_BOM)


def test_json_utf8_byte_bom_agr():
    assert agr_read_json(UTF8_BOM_BYTES) == {"n": 1}


def test_json_utf8_byte_bom_qa():
    with pytest.raises(json.JSONDecodeError, match="BOM"):
        qa_read_json(UTF8_BOM_BYTES)


def test_json_bom_string_agr():
    with pytest.raises(json.JSONDecodeError):
        agr_read_json(BOM_STR)


def test_json_bom_string_qa():
    with pytest.raises(json.JSONDecodeError):
        qa_read_json(BOM_STR)


# --- YAML nonfinite family -------------------------------------------------

YAML_INF = b"n: .inf\n"
YAML_EXP_OVERFLOW = b"n: 1.0e+400\n"
YAML_INT_EXP = b"n: 1e400\n"


def test_yaml_inf_agr(tmp_path):
    value = agr_read_yaml(_write_yaml(tmp_path, "inf.yaml", YAML_INF))["n"]
    assert math.isinf(value) and value > 0


def test_yaml_inf_qa(tmp_path):
    with pytest.raises(ValueError, match="Nonfinite value in YAML"):
        qa_read_yaml(_write_yaml(tmp_path, "inf.yaml", YAML_INF))


def test_yaml_exponent_overflow_agr(tmp_path):
    value = agr_read_yaml(_write_yaml(tmp_path, "exp.yaml", YAML_EXP_OVERFLOW))["n"]
    assert math.isinf(value) and value > 0


def test_yaml_exponent_overflow_qa(tmp_path):
    with pytest.raises(ValueError, match="Nonfinite value in YAML"):
        qa_read_yaml(_write_yaml(tmp_path, "exp.yaml", YAML_EXP_OVERFLOW))


@pytest.mark.parametrize("reader", [agr_read_yaml, qa_read_yaml], ids=["agr", "qa"])
def test_yaml_int_exponent_is_literal_string(tmp_path, reader):
    assert reader(_write_yaml(tmp_path, "str.yaml", YAML_INT_EXP)) == {"n": "1e400"}


# --- YAML/JSON duplicate and merge family ----------------------------------

JSON_NESTED_DUP = '{"outer": {"a": 1, "a": 2}}'
YAML_NESTED_DUP = b"outer:\n  a: 1\n  a: 2\n"
YAML_MERGE_OVERRIDE = b"base: &b {a: 1}\nobj:\n  <<: *b\n  a: 2\n"
YAML_MERGE_NO_OVERLAP = b"base: &b {a: 1}\nobj:\n  <<: *b\n  c: 2\n"


def test_json_nested_duplicate_agr():
    with pytest.raises(ValueError, match="Duplicate key: a"):
        agr_read_json(JSON_NESTED_DUP)


def test_json_nested_duplicate_qa():
    with pytest.raises(ValueError, match="Duplicate key: a"):
        qa_read_json(JSON_NESTED_DUP)


def test_yaml_nested_duplicate_agr(tmp_path):
    with pytest.raises(ValueError, match="Duplicate key: a"):
        agr_read_yaml(_write_yaml(tmp_path, "dup.yaml", YAML_NESTED_DUP))


def test_yaml_nested_duplicate_qa(tmp_path):
    with pytest.raises(ValueError, match="Duplicate key: a"):
        qa_read_yaml(_write_yaml(tmp_path, "dup.yaml", YAML_NESTED_DUP))


def test_yaml_merge_override_agr(tmp_path):
    with pytest.raises(ValueError, match="Duplicate key: a"):
        agr_read_yaml(_write_yaml(tmp_path, "merge.yaml", YAML_MERGE_OVERRIDE))


def test_yaml_merge_override_qa(tmp_path):
    with pytest.raises(ValueError, match="Duplicate key: a"):
        qa_read_yaml(_write_yaml(tmp_path, "merge.yaml", YAML_MERGE_OVERRIDE))


@pytest.mark.parametrize("reader", [agr_read_yaml, qa_read_yaml], ids=["agr", "qa"])
def test_yaml_merge_without_overlap(tmp_path, reader):
    assert reader(_write_yaml(tmp_path, "merge_ok.yaml", YAML_MERGE_NO_OVERLAP)) == {
        "base": {"a": 1},
        "obj": {"a": 1, "c": 2},
    }
