"""Read exact names from trusted-size malicious ZIP test fixtures, without ZipInfo."""
import struct


def assert_raw_zip_member(blob, expected):
    """Require the actual hostile bytes in both headers before testing a reader."""
    expected = expected.encode("utf-8")
    end = blob.rfind(b"PK\x05\x06")
    assert end >= 0 and len(blob) <= 4 * 1024 * 1024
    cursor = struct.unpack_from("<I", blob, end + 16)[0]
    found = 0
    while cursor < end:
        assert blob[cursor:cursor + 4] == b"PK\x01\x02"
        name_size, extra_size, comment_size = struct.unpack_from("<HHH", blob, cursor + 28)
        name = blob[cursor + 46:cursor + 46 + name_size]
        if name == expected:
            local = struct.unpack_from("<I", blob, cursor + 42)[0]
            assert blob[local:local + 4] == b"PK\x03\x04"
            local_size = struct.unpack_from("<H", blob, local + 26)[0]
            assert blob[local + 30:local + 30 + local_size] == expected
            found += 1
        cursor += 46 + name_size + extra_size + comment_size
    assert cursor == end and found == 1
