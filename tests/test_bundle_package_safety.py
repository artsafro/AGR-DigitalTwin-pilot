"""Bundle member safety through the public writer and reader interfaces."""

from itertools import combinations, product
from warnings import catch_warnings, simplefilter
from zipfile import ZipFile, ZipInfo

from dt_ai.publish.bundle import package, read_bundle


UNSAFE_NAMES = [""] + [
    template.format(stem)
    for stem in ("asset", "nested/asset", "mesh.bin")
    for template in ("/{}", "../{}", "{}/../escape", "{}\\escape", "{}:stream")
]
# Probe every NUL position, including leading NUL (an empty ZIP name) and
# trailing NUL (silent truncation), with and without a discarded suffix.
NUL_NAMES = [
    stem[:index] + "\x00" + suffix + stem[index:]
    for stem in ("asset.bin", "nested/mesh.bin")
    for index in range(len(stem) + 1)
    for suffix in ("", "discarded")
]
NUL_MEMBER_SETS = [("000-safe.bin", name) for name in NUL_NAMES] + [
    (stem, stem + "\x00" + suffix)
    for stem in ("asset.bin", "nested/mesh.bin")
    for suffix in ("", "discarded")
] + [("\x00",), ("\x00discarded",)]
CASE_PAIRS = list(combinations(
    ["".join(chars) + ".bin" for chars in product("mM", "aA", "pP")], 2
))


def assert_rejected_without_writing(tmp_path, member_sets):
    failures = []
    for index, members in enumerate(member_sets):
        for existing in (False, True):
            output = tmp_path / f"bundle-{index}-{existing}.zip"
            original = b"Existing output must survive unchanged"
            if existing:
                output.write_bytes(original)
            try:
                package(dict.fromkeys(members, b"payload"), output)
            except ValueError:
                pass
            else:
                failures.append((members, existing, "no ValueError"))
            if existing:
                if output.read_bytes() != original:
                    failures.append((members, existing, "output overwritten"))
            elif output.exists():
                failures.append((members, existing, "output created"))
    assert not failures, failures


def test_package_rejects_unsafe_names_before_touching_output(tmp_path):
    # Include a safe member first: validation must cover the entire input up front.
    assert_rejected_without_writing(
        tmp_path, [("000-safe.bin", name) for name in UNSAFE_NAMES]
    )


def test_package_rejects_nul_before_touching_output(tmp_path):
    assert_rejected_without_writing(tmp_path, NUL_MEMBER_SETS)


def test_package_rejects_generated_case_collisions_before_touching_output(tmp_path):
    assert_rejected_without_writing(tmp_path, CASE_PAIRS)


def test_read_bundle_rejects_unsafe_and_duplicate_members(tmp_path):
    path = tmp_path / "untrusted.zip"
    members_to_check = (
        NUL_MEMBER_SETS
        + [(name,) for name in UNSAFE_NAMES if name]
        + CASE_PAIRS
        + [("same.bin", "same.bin")]
    )
    failures = []
    for members in members_to_check:
        with catch_warnings():
            simplefilter("ignore", UserWarning)  # Deliberately duplicate a ZIP member.
            with ZipFile(path, "w") as archive:
                for name in members:
                    # Assign after construction to preserve raw NUL/backslash bytes.
                    info = ZipInfo("placeholder")
                    info.filename = name
                    archive.writestr(info, b"payload")
        try:
            read_bundle(path)
        except ValueError:
            pass
        else:
            failures.append(members)
    assert not failures, failures


def test_safe_package_round_trips_byte_identically(tmp_path):
    files = {
        "manifest.json": b'{"synthetic": true}',
        "nested/mesh.bin": bytes(range(256)),
        "textures/Map.png": b"\x00\xff\x80\r\n",
        "empty.bin": b"",
        "unicode/café.bin": b"UTF-8 member name",
    }
    output = tmp_path / "new-directory" / "safe.zip"
    package(files, output)
    assert read_bundle(output) == files


def test_empty_package_round_trips(tmp_path):
    output = tmp_path / "empty.zip"
    package({}, output)
    assert read_bundle(output) == {}
