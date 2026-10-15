"""Adversarial archive admission without editor or runtime substitutes."""
import hashlib
import os
import stat
import struct
import zipfile

import pytest

from scripts.verification.editor_workbench import archive


def make_zip(tmp_path, members):
    path = tmp_path / "input.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as package:
        for name, data in members:
            package.writestr(name, data)
    return path


def extract(path, destination, **pins):
    raw = path.read_bytes()
    return archive.extract_verified(path, destination, **{
        "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw), **pins,
    })


def test_exact_inventory_preserves_raw_bytes_and_notices(tmp_path):
    files = {"VSCodium.exe": b"\x00\xff\r\n", "bin/codium.cmd": b"@echo off\r\n",
             "resources/app/LICENSE.txt": b"License\r\n", "empty": b""}
    path = make_zip(tmp_path, [("resources/", b""), *files.items()])
    destination = tmp_path / "unpacked"
    inventory = extract(path, destination)
    assert inventory == {name: {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}
                         for name, raw in sorted(files.items())}
    assert {str(p.relative_to(destination)).replace(os.sep, "/"): p.read_bytes()
            for p in destination.rglob("*") if p.is_file()} == files


@pytest.mark.parametrize("name", [
    "../escape", "/absolute", "a/../escape", "a/./file", "a//file", "a\\file",
    "C:/file", "a:stream", "NUL.txt", "con", "aux.dat", "LPT9", "COM¹.log", "CONOUT$",
    "CON .txt", "tail.", "tail ", "a\x01b", "a\x7fb", "a\u202eb", "a?b", "a//",
], ids=["dotdot", "absolute", "nested-dotdot", "dot", "empty-part", "backslash",
        "drive", "ads", "nul", "con", "aux", "lpt", "superscript-device", "console-device", "device-space",
        "trailing-dot", "trailing-space", "control", "del", "format-control", "wildcard", "double-slash"])
def test_unsafe_spellings_refuse_before_destination_exists(tmp_path, name):
    path = make_zip(tmp_path, [("valid-first", b"valid"), (name, b"bad")])
    destination = tmp_path / "unpacked"
    with pytest.raises(ValueError):
        extract(path, destination)
    assert not destination.exists()


def test_original_nul_suffix_is_not_silently_truncated(tmp_path):
    path = make_zip(tmp_path, [("nulXsuffix", b"bad")])
    path.write_bytes(path.read_bytes().replace(b"nulXsuffix", b"nul\0suffix"))
    with pytest.raises(ValueError):
        extract(path, tmp_path / "unpacked")
    assert not (tmp_path / "unpacked").exists()


def test_explicit_directory_can_follow_its_implicit_parent(tmp_path):
    path = make_zip(tmp_path, [("directory/file", b"bytes"), ("directory/", b"")])
    assert extract(path, tmp_path / "unpacked") == {
        "directory/file": {"sha256": hashlib.sha256(b"bytes").hexdigest(), "size_bytes": 5},
    }


@pytest.mark.parametrize("members", [
    [("File", b"a"), ("file", b"b")], [("a", b"a"), ("a/b", b"b")],
    [("a/b", b"b"), ("a", b"a")], [("a/", b""), ("a", b"a")],
    [("a/b", b"b"), ("A/c", b"c")], [("a/", b""), ("A/", b"")],
], ids=["case-file", "file-parent", "implicit-directory", "explicit-directory", "case-parent", "case-directory"])
def test_duplicate_and_shadow_paths_refuse_all_extraction(tmp_path, members):
    path = make_zip(tmp_path, members)
    with pytest.raises(ValueError):
        extract(path, tmp_path / "unpacked")
    assert not (tmp_path / "unpacked").exists()


@pytest.mark.parametrize("mode,dos,name,data", [
    (stat.S_IFLNK | 0o777, 0, "link", b"../outside"),
    (stat.S_IFIFO | 0o600, 0, "fifo", b""),
    (stat.S_IFSOCK | 0o600, 0, "socket", b""),
    (stat.S_IFREG | 0o600, 0x400, "reparse", b""),
    (stat.S_IFREG | 0o600, 0x08, "volume", b""),
    (stat.S_IFREG | 0o600, 0x40, "device", b""),
    (stat.S_IFREG | 0o600, 0x10, "directory-bit", b""),
    (stat.S_IFDIR | 0o700, 0, "directory-without-slash", b""),
    (stat.S_IFREG | 0o600, 0, "regular/", b""),
    (stat.S_IFDIR | 0o700, 0x10, "directory/", b"payload"),
], ids=["symlink", "fifo", "socket", "reparse", "volume", "device", "dos-directory", "unix-directory", "regular-slash", "directory-payload"])
def test_nonregular_or_inconsistent_entries_are_rejected(tmp_path, mode, dos, name, data):
    info = zipfile.ZipInfo(name)
    info.create_system = 3
    info.external_attr = (mode << 16) | dos
    path = make_zip(tmp_path, [(info, data)])
    with pytest.raises(ValueError):
        extract(path, tmp_path / "unpacked")
    assert not (tmp_path / "unpacked").exists()


def test_encrypted_metadata_is_rejected_before_extraction(tmp_path):
    path = make_zip(tmp_path, [("encrypted", b"secret")])
    raw = bytearray(path.read_bytes())
    for signature, offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        position = raw.index(signature) + offset
        struct.pack_into("<H", raw, position, struct.unpack_from("<H", raw, position)[0] | 1)
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        extract(path, tmp_path / "unpacked")
    assert not (tmp_path / "unpacked").exists()


@pytest.mark.parametrize("pin", [{"sha256": "0" * 64}, {"size_bytes": 1}], ids=["hash", "size"])
def test_pin_mismatch_creates_nothing(tmp_path, pin):
    path = make_zip(tmp_path, [("file", b"payload")])
    with pytest.raises(ValueError):
        extract(path, tmp_path / "unpacked", **pin)
    assert not (tmp_path / "unpacked").exists()


@pytest.mark.parametrize("limit,value,members", [
    ("MAX_ENTRIES", 1, [("a", b""), ("b", b"")]),
    ("MAX_MEMBER_BYTES", 2, [("a", b"abc")]),
    ("MAX_TOTAL_BYTES", 3, [("a", b"ab"), ("b", b"cd")]),
], ids=["entries", "member-bytes", "total-bytes"])
def test_bounds_are_applied_before_creation(tmp_path, monkeypatch, limit, value, members):
    path = make_zip(tmp_path, members)
    monkeypatch.setattr(archive, limit, value)
    with pytest.raises(ValueError):
        extract(path, tmp_path / "unpacked")
    assert not (tmp_path / "unpacked").exists()


def test_short_actual_stream_is_not_reported_as_declared_size(tmp_path):
    path = make_zip(tmp_path, [("file", b"abc")])
    raw = bytearray(path.read_bytes())
    struct.pack_into("<I", raw, raw.index(b"PK\x01\x02") + 24, 4)
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="stream size"):
        extract(path, tmp_path / "unpacked")


def test_corrupt_payload_never_returns_inventory(tmp_path):
    path = tmp_path / "input.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as package:
        package.writestr("file", b"abc")
    raw = bytearray(path.read_bytes())
    offset = raw.index(b"PK\x03\x04") + 30 + len("file")
    raw[offset] ^= 0xFF
    path.write_bytes(raw)
    with pytest.raises((zipfile.BadZipFile, RuntimeError, OSError)):
        extract(path, tmp_path / "unpacked")


def test_existing_destination_is_untouched(tmp_path):
    path = make_zip(tmp_path, [("file", b"payload")])
    destination = tmp_path / "unpacked"
    destination.mkdir()
    (destination / "keep").write_bytes(b"untouched")
    with pytest.raises(FileExistsError):
        extract(path, destination)
    assert list(destination.iterdir()) == [destination / "keep"]
    assert (destination / "keep").read_bytes() == b"untouched"


def test_symlink_destination_ancestor_is_refused(tmp_path):
    path = make_zip(tmp_path, [("file", b"payload")])
    target, link = tmp_path / "target", tmp_path / "link"
    target.mkdir()
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Creating directory symlinks is unavailable")
    with pytest.raises(ValueError):
        extract(path, link / "unpacked")
    assert not (target / "unpacked").exists()
