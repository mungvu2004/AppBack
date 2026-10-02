"""Nguồn CubiCasa5K không tin được: giải zip an toàn, dò thư mục mẫu, đọc tệp thường (K13, K14, BE-00 §11).

Mọi byte nguồn coi như do kẻ xấu dựng (B6-02b [7]): tên mục zip, symlink, FIFO, tên thư mục,
kích thước khai. Dò mẫu và đọc tệp nằm cạnh giải nén vì chung một mô hình đe doạ: thư mục giải
từ zip và thư mục người vận hành đưa vào đi qua đúng một cửa kiểm.
"""

import errno
import os
import re
import shutil
import stat
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

ArchiveReason = Literal["path", "symlink", "encrypted", "too_many_files", "too_large", "ratio", "corrupt", "disk"]
"""`reason` của `ARCHIVE_UNSAFE` in cho người vận hành (B6-02b [2])."""


class UnsafeArchiveError(ValueError):
    """Zip bị từ chối trước hay trong khi giải; `reason` nói vì sao (B6-02b [6] `safe_extract`)."""

    def __init__(self, reason: ArchiveReason) -> None:
        """Thông điệp ngoại lệ chính là `reason`, để log và stderr in cùng một chuỗi."""
        super().__init__(reason)
        self.reason: Final = reason


class UnsafePathError(ValueError):
    """Tệp nguồn không phải tệp thường (symlink, FIFO, thư mục): mẫu chứa nó bị bỏ `unsafe_path`.

    Lớp con của `ValueError`, **không** của `OSError`: `OSError` khi đọc nguồn là lỗi cả lượt
    (`SOURCE_READ_FAILED`), còn một tệp lạ chỉ làm hỏng một mẫu.
    """


class FileTooLargeError(ValueError):
    """Tệp nguồn dài hơn trần người gọi đặt; phát hiện trước khi đọc hết (đọc tối đa trần + 1 byte)."""


@dataclass(frozen=True, slots=True)
class SampleDir:
    """Một thư mục mẫu đã qua dò: `subset` là tên thư mục cha, `sample_id` khớp toàn bộ `[0-9]{1,10}`."""

    subset: str
    sample_id: str
    path: Path


_ZIP_MAGIC: Final = b"PK\x03\x04"
_CHUNK_SIZE: Final = 65536
_SAMPLE_ID_RE: Final = re.compile(r"[0-9]{1,10}")
_CONTROL_CHARS: Final = frozenset({127, *range(32)})
_MAX_SCAN_DEPTH: Final = 3
_CORRUPT_READ_ERRORS: Final = (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError)
"""Lỗi khi mở/đọc một mục zip hỏng hay nén kiểu không hỗ trợ — đều quy về `reason == "corrupt"`."""


def is_zip(path: Path) -> bool:
    """Tệp thường có 4 byte đầu khớp magic zip local-file-header (K14: không theo đuôi tên)."""
    if not path.is_file():
        return False
    with path.open("rb") as handle:
        return handle.read(len(_ZIP_MAGIC)) == _ZIP_MAGIC


def _bad_name_reason(name: str, seen: set[str]) -> ArchiveReason | None:
    """`path` nếu tên mục zip không an toàn (rỗng, tuyệt đối, ổ đĩa, `\\`, `..`, ký tự điều khiển, trùng)."""
    if not name or name.startswith("/") or re.match(r"^[A-Za-z]:", name) or "\\" in name:
        return "path"
    if any(part == ".." for part in name.split("/")):
        return "path"
    if any(ord(ch) in _CONTROL_CHARS for ch in name):
        return "path"
    if name in seen:
        return "path"
    seen.add(name)
    return None


def _member_reason(
    info: zipfile.ZipInfo, seen: set[str], *, max_file_bytes: int, max_ratio: int
) -> ArchiveReason | None:
    """Lý do từ chối của một mục zip, hay `None` nếu an toàn (thứ tự tất định: tên → symlink → mã hoá → tỉ lệ)."""
    name_reason = _bad_name_reason(info.filename, seen)
    if name_reason is not None:
        return name_reason
    if stat.S_ISLNK(info.external_attr >> 16):
        return "symlink"
    if info.flag_bits & 0x1:
        return "encrypted"
    if info.file_size > max_file_bytes or info.file_size / max(info.compress_size, 1) > max_ratio:
        return "ratio"
    return None


def _check_members(archive: zipfile.ZipFile, *, max_files: int, max_file_bytes: int, max_ratio: int) -> int:
    """Kiểm cả danh mục trước byte ghi đầu tiên (thứ tự tất định); trả tổng `file_size` khai báo."""
    infos = archive.infolist()
    if len(infos) > max_files:
        raise UnsafeArchiveError("too_many_files")
    seen: set[str] = set()
    total = 0
    for info in infos:
        reason = _member_reason(info, seen, max_file_bytes=max_file_bytes, max_ratio=max_ratio)
        if reason is not None:
            raise UnsafeArchiveError(reason)
        total += info.file_size
    return total


def _extract_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo, dest: Path) -> bool:
    """Giải một mục bằng chép khúc `_CHUNK_SIZE` (không `extract`/`extractall`, K13); trả `True` nếu là tệp."""
    target = (dest / info.filename).resolve()
    if not target.is_relative_to(dest.resolve()):
        raise UnsafeArchiveError("path")
    if info.filename.endswith("/"):
        target.mkdir(parents=True, exist_ok=True)
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with archive.open(info) as source, target.open("xb") as sink:
            while chunk := source.read(_CHUNK_SIZE):
                written += len(chunk)
                if written > info.file_size:
                    raise UnsafeArchiveError("corrupt")
                sink.write(chunk)
    except _CORRUPT_READ_ERRORS as exc:
        raise UnsafeArchiveError("corrupt") from exc
    return True


def safe_extract(
    zip_path: Path, dest: Path, *, max_files: int, max_total_bytes: int, max_file_bytes: int, max_ratio: int
) -> int:
    """Giải `zip_path` vào `dest` sau khi kiểm cả danh mục; trả số tệp đã giải (K13, không đệ quy đuôi tên).

    Lỗi giữa chừng xoá sạch nội dung `dest` rồi ném lại; `dest` do người gọi tạo (`mkdtemp`) và tự xoá.
    """
    try:
        with zipfile.ZipFile(zip_path) as archive:
            total = _check_members(archive, max_files=max_files, max_file_bytes=max_file_bytes, max_ratio=max_ratio)
            if total > max_total_bytes:
                raise UnsafeArchiveError("too_large")
            if shutil.disk_usage(dest).free < 1.1 * total:
                raise UnsafeArchiveError("disk")
            extracted = 0
            for info in archive.infolist():
                if _extract_member(archive, info, dest):
                    extracted += 1
            return extracted
    except _CORRUPT_READ_ERRORS as exc:
        _clear_dir(dest)
        raise UnsafeArchiveError("corrupt") from exc
    except (UnsafeArchiveError, OSError):
        _clear_dir(dest)
        raise


def _clear_dir(dest: Path) -> None:
    """Xoá mọi mục con của `dest`, giữ lại `dest` cho người gọi tự dọn (`mkdtemp` + `finally`)."""
    for child in dest.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def discover_samples(root: Path, *, limit: int | None) -> tuple[tuple[SampleDir, ...], dict[str, int]]:
    """Dò thư mục mẫu (chứa `model.svg`) sâu ≤ 3 cấp dưới `root`, không đệ quy (ngăn xếp tường minh).

    `subset` = tên thư mục cha của thư mục mẫu. Symlink-thư-mục đếm `unsafe_path`, không đi vào;
    symlink tới tệp/hỏng bỏ qua im lặng. Sắp theo `(subset, int(sample_id), path)`, bỏ id trùng
    (giữ bản đầu), rồi cắt `limit`. Trả `(mẫu đã sắp, đếm unsafe_path/bad_id/duplicate_id — chỉ khoá > 0)`.
    """
    counts = {"unsafe_path": 0, "bad_id": 0, "duplicate_id": 0}
    root_resolved = root.resolve()
    found: list[SampleDir] = []
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        dir_path, depth = stack.pop()
        try:
            children = sorted(os.scandir(dir_path), key=lambda e: e.name)
        except OSError:
            continue
        for child in children:
            _visit_child(child, dir_path, depth, root_resolved, stack, found, counts)
    return _finalize_samples(found, counts, limit)


def _visit_child(
    child: os.DirEntry[str],
    dir_path: Path,
    depth: int,
    root_resolved: Path,
    stack: list[tuple[Path, int]],
    found: list[SampleDir],
    counts: dict[str, int],
) -> None:
    """Xét một mục con khi quét `dir_path`: symlink-thư-mục đếm `unsafe_path`; mẫu hoặc đẩy tiếp vào ngăn xếp."""
    if child.is_symlink():
        if _points_to_dir(child):
            counts["unsafe_path"] += 1
        return
    try:
        if not child.is_dir():
            return
    except OSError:
        return
    child_path = Path(child.path)
    child_depth = depth + 1
    if os.path.lexists(child_path / "model.svg"):
        _register_sample(child_path, dir_path.name, root_resolved, found, counts)
        return
    if child_depth < _MAX_SCAN_DEPTH:
        stack.append((child_path, child_depth))


def _points_to_dir(entry: os.DirEntry[str]) -> bool:
    """`True` nếu symlink `entry` trỏ tới một thư mục còn sống (stat theo symlink); hỏng/trỏ tệp → `False`."""
    try:
        return entry.is_dir(follow_symlinks=True)
    except OSError:
        return False


def _register_sample(
    child_path: Path, subset: str, root_resolved: Path, found: list[SampleDir], counts: dict[str, int]
) -> None:
    """Ghi nhận `child_path` là thư mục mẫu: ngoài gốc → `unsafe_path`; id sai dạng → `bad_id`."""
    if not child_path.resolve().is_relative_to(root_resolved):
        counts["unsafe_path"] += 1
        return
    sample_id = child_path.name
    if not _SAMPLE_ID_RE.fullmatch(sample_id):
        counts["bad_id"] += 1
        return
    found.append(SampleDir(subset, sample_id, child_path))


def _finalize_samples(
    found: list[SampleDir], counts: dict[str, int], limit: int | None
) -> tuple[tuple[SampleDir, ...], dict[str, int]]:
    """Sắp, bỏ id trùng (giữ bản đầu theo thứ tự đã sắp), cắt `limit`, rồi lọc `counts` chỉ giữ khoá > 0."""
    found.sort(key=lambda sample: (sample.subset, int(sample.sample_id), str(sample.path)))
    deduped: list[SampleDir] = []
    seen_ids: set[str] = set()
    for sample in found:
        if sample.sample_id in seen_ids:
            counts["duplicate_id"] += 1
            continue
        seen_ids.add(sample.sample_id)
        deduped.append(sample)
    limited = tuple(deduped) if limit is None else tuple(deduped[:limit])
    return limited, {key: value for key, value in counts.items() if value > 0}


def read_regular(path: Path, *, max_bytes: int) -> bytes:
    """Đọc toàn bộ `path` nếu là tệp thường và không dài hơn `max_bytes` (K22, không giữ session).

    `UnsafePathError` nếu không phải tệp thường (symlink, FIFO, thư mục) hay symlink tráo vào sau
    `lstat` (`ELOOP`); `FileTooLargeError` nếu dài hơn trần; `OSError` khác (thiếu tệp, quyền, I/O)
    nổi lên nguyên dạng — importer đổi thành `SOURCE_READ_FAILED`, không phải lỗi một mẫu.
    """
    lstat_result = os.lstat(path)
    if not stat.S_ISREG(lstat_result.st_mode):
        raise UnsafePathError("not_regular")
    fd = _open_nofollow(path)
    try:
        return _read_regular_fd(fd, max_bytes)
    finally:
        os.close(fd)


def _open_nofollow(path: Path) -> int:
    """Mở `path` không theo symlink (`O_NOFOLLOW`); `O_NONBLOCK` để FIFO tráo vào giữa lúc kiểm không làm treo.

    Chỉ `errno.ELOOP` (symlink tráo vào sau `lstat`) đổi thành `UnsafePathError`; `OSError` khác
    (quyền, thiếu tệp đổi tên giữa chừng) nổi lên nguyên dạng.
    """
    try:
        return os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise UnsafePathError("not_regular") from exc
        raise


def _read_regular_fd(fd: int, max_bytes: int) -> bytes:
    """Kiểm lại `fstat` là tệp thường và trần kích thước trước khi đọc tối đa `max_bytes + 1` byte."""
    fstat_result = os.fstat(fd)
    if not stat.S_ISREG(fstat_result.st_mode):
        raise UnsafePathError("not_regular")
    if fstat_result.st_size > max_bytes:
        raise FileTooLargeError("too_large")
    data = bytearray()
    while chunk := os.read(fd, max_bytes + 1 - len(data)):
        data.extend(chunk)
        if len(data) > max_bytes:
            raise FileTooLargeError("too_large")
    return bytes(data)
