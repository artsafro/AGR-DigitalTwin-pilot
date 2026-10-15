"""Package L1 documentation regression; no package compliance is asserted (#156)."""
from pathlib import Path
import re

import pytest

from test_area_requirement_sheet import contract, find_gap_lines

ROOT = Path(__file__).resolve().parents[1]
SHEET = ROOT / "docs/domain/areas/package.md"
IDS = [f"PKG-{n:02d}" for n in range(1, 26)]

# Issue #156 scope (roadmap §7.8 T-PKG-1): sources and numbers transcribed from the rendered pages.
REQUIRED = {
    "PKG-01": ("reg p.6 §1.1", "[D015]", "<= 1 GB (1024 MiB, binary)"),
    "PKG-02": ("reg p.26 §1.1", "[D015]", "OKS ZIP <= 500 MB (500 MiB)", "Ground ZIP <= 1 GB (1024 MiB)"),
    "PKG-03": ("reg p.6 §1.2", "reg p.7 §1.6", "2-21 FBX", "up to 20 OKS FBX"),
    "PKG-04": ("reg p.26 §1.2", "3-2100 PNG", "optional lighting FBX"),
    "PKG-05": ("reg p.26 §1.3-1.4", "free-standing OKS"),
    "PKG-06": ("reg p.6 §1.4", "<= 40 geometry objects", "<= 20 objects (max 40 texture sets)",
               "<= 20 objects (no texture sets)"),
    "PKG-07": ("reg p.6-7 §1.5", "<= 22 texture sets", "Ground (<= 20 sets", "GroundEl (1 set)", "Flora (1 set)"),
    "PKG-08": ("reg p.7 §2.1-2.4", "<= 20 FBX", "`_01`..`_20`", "continuous"),
    "PKG-09": ("reg p.4 §1.1", "reg p.24 §1.1", "FBX 7.4 (FBX 2014), binary"),
    "PKG-10": ("reg p.4 §2.1", "reg p.24 §2.1", "1 unit = 1 m", "scale 1:1"),
    "PKG-11": ("reg p.6 §1.3", "reg p.28 §3.1-3.2", "single default layer", "lights removed"),
    "PKG-12": ("reg p.33 §10.4.1", "[D017]", "`SM_<Address>_Light.fbx`"),
    "PKG-13": ("reg p.11 §10.1-10.3.2", "reg p.33 §10.1-10.4.1", "[D019]", "four-digit territorial code",
               "`SM_Address_Ground_Light`"),
    "PKG-14": ("reg p.34-35 §10.4.5-10.4.6", "`Address_Spot_001..250`", "`Address_Omni_001..250`",
               "`Address_Ground_Root`"),
    "PKG-15": ("reg p.37 §15.2", "<= 250 lights per lighting FBX"),
    "PKG-16": ("reg p.37 §15.3-15.4", "reg p.38 §15.6-15.7", "omni point lights and conical spot lights",
               "only colour and intensity"),
    "PKG-17": ("reg p.38 §15.5", "omni 5 m, spot 1.5 m"),
    "PKG-18": ("reg p.38 §15.8-15.9", "one root helper empty"),
    "PKG-19": ("reg p.26 §2.1", "reg p.27 §2.5", "reg p.28 §2.7", "UTF-8"),
    "PKG-20": ("reg p.51-53", "`ObjectFeature`", "`Point`"),
    "PKG-21": ("reg p.27 §2.6", "[D011]", "3, 6 or 9 digits", "`act_AGR` may be empty", "never invent"),
    "PKG-22": ("reg p.53-54 table 1 rows 2-17", "<= 50 characters", "`FNO_name` <= 255", "<= 4 decimals",
               "<= 2 decimals"),
    "PKG-23": ("reg p.54 table 1 row 19", "256x256 JPG"),
    "PKG-24": ("reg p.55 table 1 row 21", "MSK-77", "3 decimals", "maximum offset 50 cm"),
    "PKG-25": ("reg p.55 table 1 rows 22-22.5", "[D016]", "`M_Address_MainGlass_1`..`_7`", "`color_RGB` 0-255",
               "`transparency` 0-1 (0 fully transparent)", "`refraction` 1-3", "`roughness` 0-1",
               "`metallicity` 0-1"),
}
QUOTES = (("PKG-01", 6), ("PKG-02", 26), ("PKG-03", 6), ("PKG-04", 26), ("PKG-14", 34),
          ("PKG-15", 37), ("PKG-17", 38), ("PKG-24", 55))
STAGES = [f"V{n:03d}" for n in range(1, 18)]


def slug(heading: str) -> str:
    """GitHub heading anchor."""
    text = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return text.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    return {slug(m.group(1)) for m in re.finditer(r"^#{1,6}\s+(.+)$", path.read_text(encoding="utf-8"), re.M)}


def sheet_text():
    assert SHEET.is_file(), "Issue #156 requires docs/domain/areas/package.md"
    return SHEET.read_text(encoding="utf-8")


def package_contract(text, evidence_paths=()):
    rows = contract(text)
    ids = [row[0].split()[0] for row in rows]
    assert ids == IDS, ids
    indexed = dict(zip(ids, rows))
    for key, tokens in REQUIRED.items():
        row = " | ".join(indexed[key])
        for token in tokens:
            assert token in row, (key, token)
    for key in [f"PKG-{n}" for n in range(14, 26)]:
        assert indexed[key][2].startswith("n/a"), (key, "NPM has no lights / GeoJSON")
    for target, anchor in re.findall(r"\]\(((?:[^()#]|\([^()]*\))+)(?:#([^)]*))?\)", text):
        path = (SHEET.parent / target).resolve()
        assert path.exists(), target
        if anchor and path.suffix == ".md":
            assert anchor in anchors(path), (target, anchor)
    for key, page in QUOTES:
        assert re.search(rf"^- \*\*{key}, reg p\.{page} .*«.+»", text, re.M), (key, page)
    section = text.split("## Validator map V001-V017", 1)[1].split("\n## ", 1)[0]
    for stage in STAGES:
        assert len(re.findall(rf"^- \*\*{stage}\*\*", section, re.M)) == 1, stage
    gaps = {gid for _, gid, _ in find_gap_lines(text)}
    assert gaps == {row[0].split()[0] for row in rows if row[5] == "none"}
    assert f"Rows with `none` (**{len(gaps)}**)" in text
    assert f"**{len(rows)} requirement rows.**" in text
    assert not re.search(r"\]\([^)]*\.png\)", text, re.IGNORECASE)
    assert not any(Path(p).suffix.lower() == ".png" for p in evidence_paths)
    return rows


def test_package_requirement_sheet():
    rows = package_contract(sheet_text(), [p.name for p in SHEET.parent.rglob("*")])
    print(f"package.md: {len(rows)} rows")


def test_package_generated_scope_and_number_probes():
    text = sheet_text()
    count = 0
    for key, tokens in REQUIRED.items():
        row = next(line for line in text.splitlines() if line.startswith(f"| {key} "))
        for token in tokens:
            with pytest.raises(AssertionError):
                package_contract(text.replace(row, row.replace(token, "OMITTED")))
            count += 1
            # Off-by-one on every digit run of a transcribed number.
            for match in re.finditer(r"\d+", token):
                bumped = token[:match.start()] + str(int(match.group()) + 1) + token[match.end():]
                with pytest.raises(AssertionError):
                    package_contract(text.replace(row, row.replace(token, bumped)))
                count += 1
    print(f"package scope/number mutations: {count}/{count} rejected")
    assert count > 100


def test_package_generated_map_quote_gap_and_png_probes():
    text = sheet_text()
    package_contract(text)
    lines, count = text.splitlines(), 0
    for i, line in enumerate(lines):
        if re.match(r"^- \*\*(V\d{3}|PKG-\d\d)(\*\*|,|:)", line):
            with pytest.raises(AssertionError):
                package_contract("\n".join(lines[:i] + lines[i + 1:]) + "\n")
            count += 1
    for bad in ("[r](../x.png)", "[r](../X.PNG)", "[r](C:/x/l1-evidence/package/p06.Png)"):
        with pytest.raises(AssertionError):
            package_contract(text + f"\n{bad}\n")
        count += 1
    with pytest.raises(AssertionError):
        package_contract(text, ["p06.png"])
    with pytest.raises(AssertionError):
        package_contract(text.replace("#npm-appendix-1", "#npm-appendix-9", 1))
    count += 2
    print(f"package map/quote/gap/png mutations: {count}/{count} rejected")
    assert count >= 17 + 8 + 9 + 5
