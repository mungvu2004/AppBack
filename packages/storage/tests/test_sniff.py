import pytest

from packages.storage.sniff import SAFETENSORS_MAX_HEADER, SNIFF_BYTES, Kind, as_kind, sniff

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
PDF = b"%PDF-1.7\n" + b"\x00" * 16
DWG = b"AC1015" + b"\x00" * 16
GLB = b"glTF" + (2).to_bytes(4, "little") + b"\x00" * 16


def _safetensors(header: bytes) -> bytes:
    return len(header).to_bytes(8, "little") + header


@pytest.mark.parametrize(
    ("sample", "expected"),
    [
        (PNG, "png"),
        (JPEG, "jpeg"),
        (PDF, "pdf"),
        (DWG, "dwg"),
        (GLB, "glb"),
        (_safetensors(b'{"__metadata__":{}}'), "safetensors"),
    ],
)
def test_sniff_detects_each_kind(sample: bytes, expected: Kind) -> None:
    assert sniff(sample) == expected


@pytest.mark.parametrize(
    "sample",
    [
        b"",
        b"\x89PNG",
        b"glTF" + (1).to_bytes(4, "little") + b"\x00" * 16,
        (1000).to_bytes(8, "little") + b'{"a":1}',
        (0).to_bytes(8, "little") + b"{",
        (SAFETENSORS_MAX_HEADER + 1).to_bytes(8, "little") + b"{" + b"\x00" * SNIFF_BYTES,
        b"just text, nothing special at all",
    ],
)
def test_sniff_truncated_or_unknown(sample: bytes) -> None:
    assert sniff(sample) == "unknown"


def test_sniff_reads_only_the_head() -> None:
    assert sniff(PDF + b"\x89PNG\r\n\x1a\n" * 10) == "pdf"


@pytest.mark.parametrize(("value", "expected"), [("png", "png"), ("", "unknown"), ("exe", "unknown")])
def test_as_kind_falls_back_to_unknown(value: str, expected: Kind) -> None:
    assert as_kind(value) == expected
