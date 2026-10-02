"""Test `safe_extract`/`is_zip`: zip độc dựng tay phải bị từ chối đúng `reason`, không rò tệp ra ngoài `dest` (K13)."""

import io
import shutil
import stat
import struct
import types
import zipfile
from pathlib import Path

import pytest

from apps.worker.datasets_cubicasa.archive import UnsafeArchiveError, _extract_member, is_zip, safe_extract
from apps.worker.datasets_cubicasa.tests.fake_cubicasa import zip_tree

_LIMITS = {"max_files": 10, "max_total_bytes": 10_000_000, "max_file_bytes": 5_000_000, "max_ratio": 100}


def _write_zip(path: Path, entries: list[tuple[zipfile.ZipInfo, bytes]]) -> Path:
    """Dựng zip tay từ danh sách `(ZipInfo, dữ liệu)`, giữ `external_attr`/`flag_bits` đã gán sẵn trên `info`."""
    with zipfile.ZipFile(path, "w") as archive:
        for info, data in entries:
            archive.writestr(info, data)
    return path


def _bad_name_info(name: str) -> zipfile.ZipInfo:
    """Một `ZipInfo` tệp thường nhỏ với tên mục `name` (để kiểm nhánh `path`)."""
    return zipfile.ZipInfo(name)


@pytest.mark.parametrize(
    "name",
    ["../evil", "/abs", "C:/x", "a\\b", "a/../../b", "a\x01b"],
)
def test_safe_extract_rejects_unsafe_names(tmp_path: Path, name: str) -> None:
    """Tên mục zip không an toàn (duyệt lên, tuyệt đối, ổ đĩa, backslash, điều khiển) → `reason == "path"`."""
    zip_path = _write_zip(tmp_path / "evil.zip", [(_bad_name_info(name), b"x")])
    dest = tmp_path / "dest"
    dest.mkdir()
    with pytest.raises(UnsafeArchiveError) as excinfo:
        safe_extract(zip_path, dest, **_LIMITS)
    assert excinfo.value.reason == "path"
    assert list(dest.iterdir()) == []


def test_safe_extract_rejects_duplicate_names(tmp_path: Path) -> None:
    """Hai mục cùng tên trong zip → `reason == "path"` (chống ghi đè lẫn nhau)."""
    entries = [(_bad_name_info("f.txt"), b"a"), (_bad_name_info("f.txt"), b"b")]
    zip_path = _write_zip(tmp_path / "dup.zip", entries)
    dest = tmp_path / "dest"
    dest.mkdir()
    with pytest.raises(UnsafeArchiveError) as excinfo:
        safe_extract(zip_path, dest, **_LIMITS)
    assert excinfo.value.reason == "path"


def test_safe_extract_rejects_symlink_entry(tmp_path: Path) -> None:
    """Mục zip khai `external_attr` là symlink → `reason == "symlink"`, không giải gì."""
    info = zipfile.ZipInfo("link")
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    zip_path = _write_zip(tmp_path / "link.zip", [(info, b"/etc/passwd")])
    dest = tmp_path / "dest"
    dest.mkdir()
    with pytest.raises(UnsafeArchiveError) as excinfo:
        safe_extract(zip_path, dest, **_LIMITS)
    assert excinfo.value.reason == "symlink"
    assert list(dest.iterdir()) == []


def _set_encrypted_flag(raw: bytearray) -> None:
    """Bật bit mã hoá (bit 0) của `general purpose flag` trong cả header cục bộ và trung tâm thư mục."""
    local_idx = raw.find(b"PK\x03\x04")
    central_idx = raw.find(b"PK\x01\x02")
    raw[local_idx + 6] |= 0x01
    raw[central_idx + 8] |= 0x01


def test_safe_extract_rejects_encrypted_entry(tmp_path: Path) -> None:
    """Mục zip có bit mã hoá trong `flag_bits` → `reason == "encrypted"` (`writestr` tự reset cờ nên vá byte thô)."""
    zip_path = _write_zip(tmp_path / "enc.zip", [(_bad_name_info("secret.bin"), b"data")])
    raw = bytearray(zip_path.read_bytes())
    _set_encrypted_flag(raw)
    zip_path.write_bytes(bytes(raw))
    dest = tmp_path / "dest"
    dest.mkdir()
    with pytest.raises(UnsafeArchiveError) as excinfo:
        safe_extract(zip_path, dest, **_LIMITS)
    assert excinfo.value.reason == "encrypted"


def test_safe_extract_rejects_too_many_files(tmp_path: Path) -> None:
    """11 mục với `max_files=10` → `reason == "too_many_files"`, kiểm trước khi giải byte nào."""
    entries = [(_bad_name_info(f"f{i}.txt"), b"x") for i in range(11)]
    zip_path = _write_zip(tmp_path / "many.zip", entries)
    dest = tmp_path / "dest"
    dest.mkdir()
    with pytest.raises(UnsafeArchiveError) as excinfo:
        safe_extract(zip_path, dest, **_LIMITS)
    assert excinfo.value.reason == "too_many_files"
    assert list(dest.iterdir()) == []


def test_safe_extract_rejects_too_large_total(tmp_path: Path) -> None:
    """Tổng `file_size` khai vượt `max_total_bytes` → `reason == "too_large"`."""
    data = b"\x00" * 1000
    zip_path = _write_zip(tmp_path / "big.zip", [(_bad_name_info("f.bin"), data)])
    dest = tmp_path / "dest"
    dest.mkdir()
    limits = {**_LIMITS, "max_total_bytes": 500}
    with pytest.raises(UnsafeArchiveError) as excinfo:
        safe_extract(zip_path, dest, **limits)
    assert excinfo.value.reason == "too_large"


def test_safe_extract_rejects_high_compression_ratio(tmp_path: Path) -> None:
    """Tỉ lệ giải nén 1 MB số 0 nén cực nhỏ, vượt `max_ratio` → `reason == "ratio"`."""
    data = b"\x00" * 1_000_000
    info = zipfile.ZipInfo("ratio.bin")
    info.compress_type = zipfile.ZIP_DEFLATED
    zip_path = _write_zip(tmp_path / "ratio.zip", [(info, data)])
    dest = tmp_path / "dest"
    dest.mkdir()
    limits = {**_LIMITS, "max_total_bytes": 10_000_000}
    with pytest.raises(UnsafeArchiveError) as excinfo:
        safe_extract(zip_path, dest, **limits)
    assert excinfo.value.reason == "ratio"


def _patch_declared_uncompressed_size(raw: bytearray, declared_size: int) -> None:
    """Vá riêng trường `uncompressed size` (không đụng `compressed size` trùng giá trị ở zip `STORED`)."""
    local_idx = raw.find(b"PK\x03\x04")
    central_idx = raw.find(b"PK\x01\x02")
    size_bytes = struct.pack("<I", declared_size)
    raw[local_idx + 22 : local_idx + 26] = size_bytes
    raw[central_idx + 24 : central_idx + 28] = size_bytes


def test_safe_extract_rejects_declared_size_mismatch(tmp_path: Path) -> None:
    """Mục khai 10 byte mà dữ liệu thật 11 byte (khai sai cố ý) → `reason == "corrupt"` (không tin khai báo)."""
    data = b"x" * 11
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("f.bin", data)
    raw = bytearray(buffer.getvalue())
    _patch_declared_uncompressed_size(raw, 10)
    zip_path = tmp_path / "mismatch.zip"
    zip_path.write_bytes(bytes(raw))
    dest = tmp_path / "dest"
    dest.mkdir()
    with pytest.raises(UnsafeArchiveError) as excinfo:
        safe_extract(zip_path, dest, **_LIMITS)
    assert excinfo.value.reason == "corrupt"
    assert list(dest.iterdir()) == []


def test_safe_extract_rejects_truncated_zip(tmp_path: Path) -> None:
    """Tệp `PK\\x03\\x04` bị cụt (thiếu trung tâm thư mục) → `reason == "corrupt"`."""
    zip_path = _write_zip(tmp_path / "ok.zip", [(_bad_name_info("f.bin"), b"hello world")])
    truncated = zip_path.read_bytes()[:20]
    zip_path.write_bytes(truncated)
    dest = tmp_path / "dest"
    dest.mkdir()
    with pytest.raises(UnsafeArchiveError) as excinfo:
        safe_extract(zip_path, dest, **_LIMITS)
    assert excinfo.value.reason == "corrupt"


def test_safe_extract_rejects_low_disk_space(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`shutil.disk_usage(dest).free` giả nhỏ hơn 1.1x tổng khai → `reason == "disk"`."""
    zip_path = _write_zip(tmp_path / "ok.zip", [(_bad_name_info("f.bin"), b"hello")])
    dest = tmp_path / "dest"
    dest.mkdir()
    monkeypatch.setattr(shutil, "disk_usage", lambda _path: types.SimpleNamespace(total=0, used=0, free=0))
    with pytest.raises(UnsafeArchiveError) as excinfo:
        safe_extract(zip_path, dest, **_LIMITS)
    assert excinfo.value.reason == "disk"


def test_safe_extract_extracts_valid_archive(tmp_path: Path) -> None:
    """Zip hợp lệ của `zip_tree` (tệp `.dat` thật) → giải đủ số tệp, byte trùng nguồn."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.dat").write_bytes(b"alpha")
    (src / "sub").mkdir()
    (src / "sub" / "b.dat").write_bytes(b"beta")
    zip_path = zip_tree(src, tmp_path / "out.zip")
    dest = tmp_path / "dest"
    dest.mkdir()
    extracted = safe_extract(zip_path, dest, **_LIMITS)
    assert extracted == 2
    assert (dest / "cubicasa5k" / "a.dat").read_bytes() == b"alpha"
    assert (dest / "cubicasa5k" / "sub" / "b.dat").read_bytes() == b"beta"


def test_is_zip_detects_magic_regardless_of_extension(tmp_path: Path) -> None:
    """`.dat` có magic `PK\\x03\\x04` → `True` (K14: không theo đuôi tên)."""
    path = tmp_path / "data.dat"
    path.write_bytes(b"PK\x03\x04" + b"junk")
    assert is_zip(path) is True


def test_is_zip_rejects_directory_named_zip(tmp_path: Path) -> None:
    """Thư mục tên `x.zip` → `False` (không phải tệp thường)."""
    path = tmp_path / "x.zip"
    path.mkdir()
    assert is_zip(path) is False


def test_is_zip_rejects_zip_extension_without_magic(tmp_path: Path) -> None:
    """Tệp `.zip` không có magic đầu → `False`."""
    path = tmp_path / "fake.zip"
    path.write_bytes(b"not a zip")
    assert is_zip(path) is False


def test_safe_extract_creates_directory_entries(tmp_path: Path) -> None:
    """Mục zip là thư mục (tên kết `/`) → tạo thư mục, không tính vào số tệp đã giải."""
    zip_path = tmp_path / "dirs.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(zipfile.ZipInfo("emptydir/"), "")
        archive.writestr("emptydir/file.txt", "x")
    dest = tmp_path / "dest"
    dest.mkdir()
    extracted = safe_extract(zip_path, dest, **_LIMITS)
    assert extracted == 1
    assert (dest / "emptydir").is_dir()
    assert (dest / "emptydir" / "file.txt").read_text() == "x"


def test_extract_member_rejects_target_escaping_dest(tmp_path: Path) -> None:
    """`_extract_member` tự kiểm lại target ngoài `dest` (lớp phòng vệ song song với `_check_members`)."""
    zip_path = tmp_path / "ok.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("safe.txt", "data")
    dest = tmp_path / "dest"
    dest.mkdir()
    with zipfile.ZipFile(zip_path) as archive:
        info = archive.infolist()[0]
        info.filename = "../escape.txt"
        with pytest.raises(UnsafeArchiveError) as excinfo:
            _extract_member(archive, info, dest)
    assert excinfo.value.reason == "path"


def test_extract_member_rejects_oversized_actual_data(tmp_path: Path) -> None:
    """`info.file_size` giả nhỏ hơn dữ liệu thật (mutate trực tiếp sau khi mở) → `reason == "corrupt"`."""
    zip_path = tmp_path / "ok.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("f.bin", b"x" * 11)
    dest = tmp_path / "dest"
    dest.mkdir()
    with zipfile.ZipFile(zip_path) as archive:
        info = archive.infolist()[0]
        info.file_size = 5
        with pytest.raises(UnsafeArchiveError) as excinfo:
            _extract_member(archive, info, dest)
    assert excinfo.value.reason == "corrupt"


def test_safe_extract_rejects_corrupted_deflate_stream(tmp_path: Path) -> None:
    """Byte nén DEFLATE của mục bị đảo (giữ header nguyên) → `zlib.error`/`EOFError` → `reason == "corrupt"`."""
    data = b"abcdefgh" * 200
    zip_path = tmp_path / "corrupt.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("f.bin", data)
    raw = bytearray(zip_path.read_bytes())
    local_idx = raw.find(b"PK\x03\x04")
    name_len = struct.unpack_from("<H", raw, local_idx + 26)[0]
    extra_len = struct.unpack_from("<H", raw, local_idx + 28)[0]
    compress_size = struct.unpack_from("<I", raw, local_idx + 18)[0]
    data_start = local_idx + 30 + name_len + extra_len
    mid = data_start + compress_size // 2
    raw[mid] ^= 0xFF
    zip_path.write_bytes(bytes(raw))
    dest = tmp_path / "dest"
    dest.mkdir()
    with pytest.raises(UnsafeArchiveError) as excinfo:
        safe_extract(zip_path, dest, **_LIMITS)
    assert excinfo.value.reason == "corrupt"
    assert list(dest.iterdir()) == []


def test_safe_extract_rejects_unknown_compression_method(tmp_path: Path) -> None:
    """`compress_type` lạ (vá byte phương thức nén ở cả local header **và** trung tâm thư mục) → `reason=="corrupt"`."""
    zip_path = tmp_path / "weird.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("f.bin", b"hello")
    raw = bytearray(zip_path.read_bytes())
    local_idx = raw.find(b"PK\x03\x04")
    central_idx = raw.find(b"PK\x01\x02")
    unknown_method = struct.pack("<H", 99)
    raw[local_idx + 8 : local_idx + 10] = unknown_method
    raw[central_idx + 10 : central_idx + 12] = unknown_method
    zip_path.write_bytes(bytes(raw))
    dest = tmp_path / "dest"
    dest.mkdir()
    with pytest.raises(UnsafeArchiveError) as excinfo:
        safe_extract(zip_path, dest, **_LIMITS)
    assert excinfo.value.reason == "corrupt"
    assert list(dest.iterdir()) == []
