"""Internal mesh-name grammar of the NPM/VPM regulation: one module for both profiles.

Pattern: n/a | new-case: internal mesh-name grammar for V012 on the FBX readback (UCX R08, MAF-11)

Grammar (reg = standards/source PDF, one-based pages):
- every name <= ``naming.max_characters`` (254) characters, Latin letters, digits, ``_`` only
  (reg p.11 §10.1-10.2; VPM repeats the ceiling, standards/VPM_STANDARD.yaml ``naming``);
- VPM OKS FBX ``SM_{Address}``: ``SM_{Address}_Main``, ``SM_{Address}_MainGlass`` and collision
  ``UCX_SM_{Address}_Main_{001..999}``; VPM Ground FBX ``SM_{Address}_Ground``:
  ``SM_{Address}_Ground``, ``SM_{Address}_GroundGlass``, ``UCX_SM_{Address}_Ground_{001..999}``
  (reg p.33-34 §4.2);
- NPM OKS FBX ``{code4}_{Address}_{01..20}``: ``SM_{Address}_{001..020}_Main[Glass]``; NPM Ground FBX
  ``{code4}_{Address}_Ground``: ``SM_{Address}_Ground``, ``_GroundGlass``, ``_GroundEl``,
  ``_GroundElGlass``, ``_Flora`` (reg p.11-12 §3.2-3.3);
- NPM has no UCX scheme (customer addendum only), so a UCX name in NPM is ``review``.

The Address is the FBX stem without its profile affixes; when the stem does not follow the FBX
grammar the masks run with any Address and a clean result is ``review``, never ``pass``.
Not checked here: VPM word capitalization (reg p.33 §10.2), material/texture names (MAF-12),
UCX presence (R05) and the light FBX (no mesh mask in the regulation).
"""
from __future__ import annotations

import re
from collections import Counter

from twinqa.report import Finding

NAME_CHARS = re.compile(r"[A-Za-z0-9_]+")
ADDRESS_ANY = "[A-Za-z0-9_]+?"
UCX_INDEX = r"(?:00[1-9]|0[1-9][0-9]|[1-9][0-9]{2})"  # 001..999, exactly three digits
NPM_OKS_NUMBER = r"(?:00[1-9]|01[0-9]|020)"  # 001..020, project-wide OKS number
NPM_FBX_PART = r"(?:0[1-9]|1[0-9]|20)"
GEOMETRY_SUFFIXES = {
    ("vpm", "oks"): ("Main", "MainGlass"),
    ("vpm", "ground"): ("Ground", "GroundGlass"),
    ("npm", "ground"): ("Ground", "GroundGlass", "GroundEl", "GroundElGlass", "Flora"),
}
PAGES = {"npm": [11, 12], "vpm": [33, 34]}
UCX_PAGES = [34]


def address_from_fbx(kind: str, role: str, stem: str) -> str | None:
    """Address encoded in the FBX file stem, or None when the stem does not follow the grammar."""
    if kind == "vpm":
        pattern = r"SM_(?P<a>[A-Za-z0-9_]+?)_Ground" if role == "ground" else r"SM_(?P<a>[A-Za-z0-9_]+)"
    elif role == "ground":
        pattern = r"[0-9]{4}_(?P<a>[A-Za-z0-9_]+?)_Ground"
    else:
        pattern = rf"[0-9]{{4}}_(?P<a>[A-Za-z0-9_]+?)_{NPM_FBX_PART}"
    m = re.fullmatch(pattern, stem)
    return m.group("a") if m else None


def is_ucx(name: str) -> bool:
    """Collision by prefix, case-insensitive as the V010 budget; the exact case is the grammar's job."""
    return name.upper().startswith("UCX_")


def _masks(kind: str, role: str, address: str | None) -> list[re.Pattern]:
    a = re.escape(address) if address else ADDRESS_ANY
    if kind == "npm" and role == "oks":
        return [re.compile(rf"SM_{a}_{NPM_OKS_NUMBER}_(?:Main|MainGlass)")]
    return [re.compile(rf"SM_{a}_{suffix}") for suffix in GEOMETRY_SUFFIXES[(kind, role)]]


def _ucx_mask(role: str, address: str | None) -> re.Pattern:
    a = re.escape(address) if address else ADDRESS_ANY
    return re.compile(rf"UCX_SM_{a}_{'Ground' if role == 'ground' else 'Main'}_{UCX_INDEX}")


def mesh_name_violation(name: str, kind: str, role: str, address: str | None, limit: int) -> str | None:
    """Why ``name`` breaks the grammar of a ``kind``/``role`` FBX with this Address; None if it follows it.
    Address None = not derivable: masks accept any Address."""
    if len(name) > limit:
        return f"{len(name)} characters > {limit}"
    if not NAME_CHARS.fullmatch(name):
        return "characters other than A-Z a-z 0-9 _"
    if is_ucx(name):
        if kind != "vpm":
            return "UCX is not specified for NPM"
        if not _ucx_mask(role, address).fullmatch(name):
            target = "Ground" if role == "ground" else "Main"
            return f"not UCX_SM_{address or '{Address}'}_{target}_001..999"
        return None
    if not any(mask.fullmatch(name) for mask in _masks(kind, role, address)):
        return "no regulation mask matches"
    return None


def mesh_name_findings(names: list[str], kind: str, role: str, fbx_stem: str, limit: int, src: str) -> list[Finding]:
    """V012 findings for the internal mesh names of one FBX readback: 'mesh names' and, when UCX meshes
    exist, 'UCX names'. Light FBX: no findings."""
    if role == "light" or (kind, role) not in (*GEOMETRY_SUFFIXES, ("npm", "oks")):
        return []
    address = address_from_fbx(kind, role, fbx_stem)
    dup = sorted(n for n, c in Counter(names).items() if c > 1)
    out = []
    for label, group, pages in (("mesh names", [n for n in names if not is_ucx(n)], PAGES[kind]),
                                ("UCX names", [n for n in names if is_ucx(n)], UCX_PAGES if kind == "vpm" else PAGES[kind])):
        if label == "UCX names" and not group:
            continue
        bad = {n: mesh_name_violation(n, kind, role, address, limit) for n in group}
        bad = {n: why for n, why in bad.items() if why} | {n: "duplicate name" for n in dup if n in group}
        hard = {n: why for n, why in bad.items() if why != "UCX is not specified for NPM"}
        if hard:
            status = "fail"
        elif bad or address is None:
            status = "review"
        else:
            status = "pass"
        shown = [f"{n}: {why}" for n, why in sorted(bad.items())][:5]
        note = "" if address else f"; Address not derived from {fbx_stem}, masks ran with any Address"
        if label == "UCX names":
            expected = ("UCX_SM_{Address}_" + ("Ground" if role == "ground" else "Main") + "_001..999"
                        if kind == "vpm" else "no UCX scheme in NPM (customer addendum)")
        elif kind == "npm" and role == "oks":
            expected = "SM_{Address}_{001..020}_Main|MainGlass"
        else:
            expected = "SM_{Address}_" + "|".join(GEOMETRY_SUFFIXES[(kind, role)])
        out.append(Finding(label, status, f"{src}: {shown or f'{len(group)} name(s) follow the grammar'}{note}",
                           f"{expected}; <= {limit} characters, A-Z a-z 0-9 _", list(pages), src, []))
    return out
