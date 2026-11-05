"""FNO registry (classifier of functional purpose of capital construction objects) for V011.

Data: standards/data/fno_codes_utf8.csv, a byte-exact copy of SINTEZ AGR Checker 1.6.1 documents/fno_codes_utf8.csv
(provenance: standards/data/fno_codes.PROVENANCE.md; owner decision 05.11.2026, #908). The comparison follows the
customer checker: digits of FNO_code against the code of its level, FNO_name with all spaces removed, case kept.
Own implementation; no checker code is copied.
"""
import csv
import hashlib
import io
from functools import lru_cache
from pathlib import Path

REGISTRY = Path(__file__).resolve().parents[2] / "standards" / "data" / "fno_codes_utf8.csv"
REGISTRY_SHA256 = "397e75e3ff1cb231359686d065cd4ebcd93ff8f789deaadefe8d4155594dff31"
HEADER_ROWS = 3


@lru_cache(maxsize=4)
def registry(path: Path = REGISTRY) -> dict[str, str]:
    """{code 'XXX[ XXX[ XXX]]': name} for groups, subgroups and types. A missing, changed or malformed file raises."""
    raw = Path(path).read_bytes()
    if path == REGISTRY and hashlib.sha256(raw).hexdigest() != REGISTRY_SHA256:
        raise ValueError(f"FNO registry {path.name}: SHA256 differs from the provenance note")
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), delimiter=";"))
    out: dict[str, str] = {}
    for n, row in enumerate(rows[HEADER_ROWS:], HEADER_ROWS + 1):
        cells = [c.strip() for c in row[:6]] + [""] * (6 - len(row[:6]))
        for name, code in ((cells[0], cells[1]), (cells[2], cells[3]), (cells[4], cells[5])):
            if not (name or code):
                continue
            digits = code.replace(" ", "")
            if not (name and digits.isascii() and digits.isdigit() and len(digits) in (3, 6, 9)):
                raise ValueError(f"FNO registry line {n}: bad pair {name!r} / {code!r}")
            out[_spaced(digits)] = name
    if not out:
        raise ValueError("FNO registry is empty")
    return out


def _spaced(digits: str) -> str:
    return " ".join(digits[i:i + 3] for i in range(0, len(digits), 3))


def _squash(text: str) -> str:
    return "".join(str(text).split())


def check(code, name, path: Path = REGISTRY) -> list[tuple[str, str, str]]:
    """[(finding name, observed, expected)] for an OKS pair; [] = the code exists and the name matches.
    Format errors stay with the V011 format check: a code that is not 3/6/9 ASCII digits returns []."""
    digits = str(code).replace(" ", "") if isinstance(code, str) else ""
    if not (digits.isascii() and digits.isdigit() and len(digits) in (3, 6, 9)):
        return []
    reg = registry(path)
    key = _spaced(digits)
    if key not in reg:
        return [("FNO_code not in registry", repr(code), "a code of the FNO classifier (standards/data/fno_codes_utf8.csv)")]
    if isinstance(name, str) and name.strip() and _squash(name) != _squash(reg[key]):  # absent/empty: own findings
        return [("FNO_name vs registry", f"{code}: {name!r}", f"{reg[key]!r} (FNO classifier, spaces ignored)")]
    return []
