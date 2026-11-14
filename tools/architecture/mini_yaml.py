"""Strict stdlib reader for the small block-YAML subset of docs/architecture/*.yaml (#1359).

Pattern: n/a | new-case: stdlib YAML-subset reader so the architecture generator runs without PyYAML.

Supported: block mappings (`key: value`, `key:` + indented block), block sequences (`- value`,
`- key: value` items), whole-line `#` comments, blank lines, scalars: "double-quoted" (JSON escapes),
plain text, plain integers (digits only). Everything else (flow collections, anchors, tags, block scalars,
inline comments, tabs, duplicate keys, plain scalars YAML would read as bool/null/float) raises
MiniYamlError naming the line, so a file this reader accepts reads the same in PyYAML (tested).
"""
import json
import re

_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_\-]*):(?: (.*))?$")
_INT = re.compile(r"^-?[0-9]+$")
_SPECIAL_START = set("[]{}&*!|>'%@`,?:#-\"")
_YAML_WORDS = {"true", "false", "yes", "no", "on", "off", "null", "~", "y", "n"}


class MiniYamlError(ValueError):
    pass


def _scalar(text, lineno):
    if text.startswith('"'):
        if not text.endswith('"') or len(text) < 2:
            raise MiniYamlError(f"line {lineno}: unterminated quoted scalar")
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MiniYamlError(f"line {lineno}: bad quoted scalar: {exc}") from None
        if not isinstance(value, str):
            raise MiniYamlError(f"line {lineno}: quoted scalar is not one string")
        return value
    if not text:
        raise MiniYamlError(f"line {lineno}: empty value")
    if _INT.match(text):
        return int(text)
    if text[0] in _SPECIAL_START or text != text.strip():
        raise MiniYamlError(f"line {lineno}: plain scalar {text!r} must be double-quoted")
    if ": " in text or " #" in text or text.endswith(":") or "\t" in text:
        raise MiniYamlError(f"line {lineno}: plain scalar {text!r} must be double-quoted")
    low = text.lower()
    if low in _YAML_WORDS or re.match(r"^[-+]?(\.[0-9]|[0-9])[0-9_.eE+-]*$", text) or low in {".inf", ".nan"}:
        raise MiniYamlError(f"line {lineno}: plain scalar {text!r} is not a string in YAML; quote it")
    return text


def _lines(text):
    out = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        if "\t" in raw:
            raise MiniYamlError(f"line {lineno}: tab character")
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped in ("---", "..."):
            raise MiniYamlError(f"line {lineno}: document markers are not supported")
        indent = len(raw) - len(raw.lstrip(" "))
        out.append((indent, raw.rstrip(), lineno))
    return out


def loads(text):
    """Parse `text`; return dict/list/str/int. Raises MiniYamlError on anything outside the subset."""
    if text.startswith("\ufeff"):
        raise MiniYamlError("line 1: byte order mark")
    lines = _lines(text)
    if not lines:
        raise MiniYamlError("empty document")
    value, pos = _block(lines, 0, lines[0][0])
    if pos != len(lines):
        raise MiniYamlError(f"line {lines[pos][2]}: unexpected indentation")
    return value


def _block(lines, pos, indent):
    if lines[pos][1].lstrip().startswith("- ") or lines[pos][1].strip() == "-":
        return _seq(lines, pos, indent)
    return _map(lines, pos, indent)


def _child(lines, pos, indent, lineno):
    if pos >= len(lines) or lines[pos][0] <= indent:
        raise MiniYamlError(f"line {lineno}: key without value or nested block")
    return _block(lines, pos, lines[pos][0])


def _map(lines, pos, indent, first=None):
    result = {}
    while pos < len(lines):
        ind, raw, lineno = lines[pos]
        if first is not None:
            ind, body, first = indent, first, None
        else:
            if ind < indent:
                break
            if ind > indent:
                raise MiniYamlError(f"line {lineno}: unexpected indentation")
            body = raw.strip()
        if body.startswith("- "):
            raise MiniYamlError(f"line {lineno}: sequence item inside a mapping")
        m = _KEY.match(body)
        if not m:
            raise MiniYamlError(f"line {lineno}: expected 'key: value'")
        key, rest = m.group(1), m.group(2)
        if key in result:
            raise MiniYamlError(f"line {lineno}: duplicate key {key!r}")
        pos += 1
        if rest is None or rest == "":
            if rest == "":
                raise MiniYamlError(f"line {lineno}: trailing space after ':'")
            result[key], pos = _child(lines, pos, indent, lineno)
        else:
            result[key] = _scalar(rest, lineno)
    return result, pos


def _seq(lines, pos, indent):
    result = []
    while pos < len(lines):
        ind, raw, lineno = lines[pos]
        if ind < indent:
            break
        if ind > indent:
            raise MiniYamlError(f"line {lineno}: unexpected indentation")
        body = raw.strip()
        if body == "-":
            raise MiniYamlError(f"line {lineno}: empty sequence item")
        if not body.startswith("- "):
            break
        item = body[2:]
        if _KEY.match(item):
            value, pos = _map(lines, pos, indent + 2, first=item)
            result.append(value)
        else:
            result.append(_scalar(item, lineno))
            pos += 1
    if pos < len(lines) and lines[pos][0] == indent and not lines[pos][1].strip().startswith("- "):
        raise MiniYamlError(f"line {lines[pos][2]}: mapping key inside a sequence")
    return result, pos


def load(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return loads(fh.read())
