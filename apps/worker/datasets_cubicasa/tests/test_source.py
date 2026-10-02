"""Test `discover_samples`/`read_regular` trên cây thư mục thật (symlink, FIFO qua `os.mkfifo`, K22)."""

import errno
import os
from pathlib import Path

import pytest

from apps.worker.datasets_cubicasa.archive import (
    FileTooLargeError,
    SampleDir,
    UnsafePathError,
    _clear_dir,
    _open_nofollow,
    _read_regular_fd,
    _register_sample,
    discover_samples,
    read_regular,
)
from apps.worker.datasets_cubicasa.tests.fake_cubicasa import write_dataset, write_room_sample


def test_discover_samples_orders_by_subset_then_id(tmp_path: Path) -> None:
    """3 mẫu 2 subset → sắp theo `(subset, int(id))`, không theo thứ tự ghi đĩa."""
    root = write_dataset(tmp_path, {"high_quality": ["2", "1"], "colorful": ["5"]})
    samples, counts = discover_samples(root, limit=None)
    assert [(s.subset, s.sample_id) for s in samples] == [
        ("colorful", "5"),
        ("high_quality", "1"),
        ("high_quality", "2"),
    ]
    assert counts == {}


def test_discover_samples_limit_takes_first_n(tmp_path: Path) -> None:
    """`limit=2` → chỉ 2 mẫu đầu theo thứ tự đã sắp."""
    root = write_dataset(tmp_path, {"high_quality": ["2", "1"], "colorful": ["5"]})
    samples, _ = discover_samples(root, limit=2)
    assert [(s.subset, s.sample_id) for s in samples] == [("colorful", "5"), ("high_quality", "1")]


def test_discover_samples_skips_symlinked_sample_dir(tmp_path: Path) -> None:
    """Thư mục mẫu là symlink trỏ ra ngoài gốc → đếm `unsafe_path`, không đi vào xem bên trong."""
    outside = tmp_path / "outside"
    write_room_sample(outside, "ext", "9")
    root = tmp_path / "root"
    (root / "high_quality").mkdir(parents=True)
    os.symlink(outside / "ext" / "9", root / "high_quality" / "9", target_is_directory=True)
    samples, counts = discover_samples(root, limit=None)
    assert samples == ()
    assert counts == {"unsafe_path": 1}


def test_discover_samples_rejects_bad_sample_id(tmp_path: Path) -> None:
    """Tên thư mục mẫu `12a` không khớp toàn bộ `[0-9]{1,10}` → đếm `bad_id`, mẫu bị bỏ."""
    root = tmp_path / "root"
    write_room_sample(root, "high_quality", "12a")
    samples, counts = discover_samples(root, limit=None)
    assert samples == ()
    assert counts == {"bad_id": 1}


def test_discover_samples_rejects_sample_id_with_trailing_newline(tmp_path: Path) -> None:
    """Tên thư mục mẫu `"123\\n"` (Linux cho phép) → `fullmatch` bắt được, không lọt qua như `$` cũ → `bad_id`."""
    root = tmp_path / "root"
    write_room_sample(root, "high_quality", "123\n")
    samples, counts = discover_samples(root, limit=None)
    assert samples == ()
    assert counts == {"bad_id": 1}


def test_discover_samples_counts_duplicate_id_across_subsets(tmp_path: Path) -> None:
    """Id trùng ở hai subset khác nhau → giữ bản đầu (theo thứ tự đã sắp), bản sau đếm `duplicate_id`."""
    root = write_dataset(tmp_path, {"colorful": ["7"], "high_quality": ["7"]})
    samples, counts = discover_samples(root, limit=None)
    assert [(s.subset, s.sample_id) for s in samples] == [("colorful", "7")]
    assert counts == {"duplicate_id": 1}


def test_discover_samples_finds_depth_three_not_depth_four(tmp_path: Path) -> None:
    """Mẫu ở cấp 3 (`root/cubicasa5k/subset/id`) tìm thấy; cấp 4 (thêm một tầng) thì không."""
    root = tmp_path / "root"
    write_room_sample(root / "cubicasa5k", "subset", "1")
    write_room_sample(root / "cubicasa5k" / "subset", "extra", "2")
    samples, _ = discover_samples(root, limit=None)
    assert [(s.subset, s.sample_id) for s in samples] == [("subset", "1")]


def test_read_regular_rejects_symlink(tmp_path: Path) -> None:
    """`model.svg` là symlink → `UnsafePathError`."""
    target = tmp_path / "real.svg"
    target.write_bytes(b"<svg/>")
    link = tmp_path / "model.svg"
    os.symlink(target, link)
    with pytest.raises(UnsafePathError):
        read_regular(link, max_bytes=100)


def test_read_regular_rejects_fifo_without_hanging(tmp_path: Path) -> None:
    """`model.svg` là FIFO (`os.mkfifo`) → `UnsafePathError`, không treo (`O_NONBLOCK`)."""
    fifo_path = tmp_path / "model.svg"
    os.mkfifo(fifo_path)
    with pytest.raises(UnsafePathError):
        read_regular(fifo_path, max_bytes=100)


def test_read_regular_rejects_directory(tmp_path: Path) -> None:
    """`model.svg` là thư mục → `UnsafePathError`."""
    dir_path = tmp_path / "model.svg"
    dir_path.mkdir()
    with pytest.raises(UnsafePathError):
        read_regular(dir_path, max_bytes=100)


def test_read_regular_rejects_file_longer_than_max_bytes(tmp_path: Path) -> None:
    """Tệp dài hơn `max_bytes` → `FileTooLargeError`, không đọc hết."""
    path = tmp_path / "model.svg"
    path.write_bytes(b"x" * 101)
    with pytest.raises(FileTooLargeError):
        read_regular(path, max_bytes=100)


def test_read_regular_reads_file_at_exact_limit(tmp_path: Path) -> None:
    """Tệp đúng bằng trần `max_bytes` → đọc đủ, không lỗi."""
    path = tmp_path / "model.svg"
    data = b"y" * 100
    path.write_bytes(data)
    assert read_regular(path, max_bytes=100) == data


def test_read_regular_rejects_missing_path(tmp_path: Path) -> None:
    """Đường dẫn không tồn tại → `FileNotFoundError` nổi lên nguyên dạng (importer đổi `SOURCE_READ_FAILED`)."""
    with pytest.raises(FileNotFoundError):
        read_regular(tmp_path / "missing.svg", max_bytes=10)


def test_open_nofollow_raises_unsafe_path_on_eloop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`os.open` ném `OSError(errno.ELOOP)` (symlink tráo vào sau `lstat`) → `UnsafePathError`."""
    path = tmp_path / "model.svg"
    path.write_bytes(b"data")

    def fake_open(target: Path, flags: int) -> int:
        """Giả `os.open` luôn báo `ELOOP`, mô phỏng symlink vừa tráo vào."""
        raise OSError(errno.ELOOP, "symlink loop")

    monkeypatch.setattr(os, "open", fake_open)
    with pytest.raises(UnsafePathError):
        _open_nofollow(path)


def test_open_nofollow_reraises_other_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`os.open` ném `OSError(errno.EACCES)` (lỗi I/O thật) → nổi lên nguyên dạng, không hoá `UnsafePathError`."""
    path = tmp_path / "model.svg"
    path.write_bytes(b"data")

    def fake_open(target: Path, flags: int) -> int:
        """Giả `os.open` luôn báo `EACCES`, mô phỏng lỗi quyền thật."""
        raise OSError(errno.EACCES, "permission denied")

    monkeypatch.setattr(os, "open", fake_open)
    with pytest.raises(PermissionError):
        _open_nofollow(path)


def test_read_regular_fd_rejects_non_regular_after_open(tmp_path: Path) -> None:
    """`_read_regular_fd` tự kiểm lại `fstat` (phòng đua giữa `lstat` và `open`): FIFO mở trực tiếp → lỗi."""
    fifo_path = tmp_path / "race.fifo"
    os.mkfifo(fifo_path)
    fd = os.open(fifo_path, os.O_RDONLY | os.O_NONBLOCK)
    try:
        with pytest.raises(UnsafePathError):
            _read_regular_fd(fd, 100)
    finally:
        os.close(fd)


def test_clear_dir_removes_files_and_subdirectories(tmp_path: Path) -> None:
    """`_clear_dir` xoá cả tệp và thư mục con bằng `shutil.rmtree`, giữ lại `dest` chính nó."""
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "file.txt").write_text("x")
    (dest / "sub").mkdir()
    (dest / "sub" / "nested.txt").write_text("y")
    _clear_dir(dest)
    assert list(dest.iterdir()) == []
    assert dest.exists()


def test_register_sample_rejects_path_outside_root(tmp_path: Path) -> None:
    """`_register_sample` tự kiểm lại `resolve()` nằm dưới root (lớp phòng vệ song song với dò symlink)."""
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside" / "5"
    outside.mkdir(parents=True)
    found: list[SampleDir] = []
    counts = {"unsafe_path": 0, "bad_id": 0, "duplicate_id": 0}
    _register_sample(outside, "subset", root.resolve(), found, counts)
    assert found == []
    assert counts["unsafe_path"] == 1


def test_discover_samples_ignores_symlink_to_file(tmp_path: Path) -> None:
    """Symlink trong cây quét trỏ tới tệp (không phải thư mục) → bỏ qua im lặng, không đếm gì."""
    root = tmp_path / "root"
    root.mkdir()
    target = tmp_path / "target.txt"
    target.write_text("x")
    os.symlink(target, root / "link.txt")
    samples, counts = discover_samples(root, limit=None)
    assert samples == ()
    assert counts == {}


def test_discover_samples_skips_directory_scan_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`os.scandir` lỗi ở một thư mục con (ví dụ gỡ quyền giữa chừng) → bỏ qua thư mục đó, không văng."""
    root = tmp_path / "root"
    locked = root / "locked"
    locked.mkdir(parents=True)
    real_scandir = os.scandir

    def fake_scandir(path: Path) -> list[os.DirEntry[str]]:
        """Giả `os.scandir` ném lỗi đúng cho `locked`, chuyển tiếp mọi thư mục khác."""
        if Path(path) == locked:
            raise OSError("no access")
        return list(real_scandir(path))

    monkeypatch.setattr(os, "scandir", fake_scandir)
    samples, counts = discover_samples(root, limit=None)
    assert samples == ()
    assert counts == {}


class _FakeEntry:
    """`os.DirEntry` giả để mô phỏng lỗi `OSError` lúc đo (đua tiến trình), không dựng được bằng tệp thật."""

    def __init__(self, path: Path, *, is_link: bool) -> None:
        """Giữ `path` và cờ `is_link` để `is_symlink`/`is_dir` trả lời tương ứng rồi ném lỗi."""
        self.path = str(path)
        self.name = path.name
        self._is_link = is_link

    def is_symlink(self) -> bool:
        """Trả cờ `is_link` được truyền lúc dựng."""
        return self._is_link

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        """Luôn ném `OSError` để mô phỏng đo thất bại giữa `scandir` và lúc xét mục con."""
        raise OSError("stat failed")


def test_discover_samples_skips_non_symlink_stat_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`DirEntry.is_dir()` lỗi trên mục không phải symlink (đua tiến trình) → bỏ qua, không văng."""
    root = tmp_path / "root"
    root.mkdir()
    entry = _FakeEntry(root / "broken", is_link=False)
    monkeypatch.setattr(os, "scandir", lambda _path: [entry])
    samples, counts = discover_samples(root, limit=None)
    assert samples == ()
    assert counts == {}


def test_discover_samples_ignores_symlink_stat_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Symlink mà việc đo (`is_dir`) lỗi giữa đường → bỏ qua im lặng, không đếm `unsafe_path`."""
    root = tmp_path / "root"
    root.mkdir()
    entry = _FakeEntry(root / "link", is_link=True)
    monkeypatch.setattr(os, "scandir", lambda _path: [entry])
    samples, counts = discover_samples(root, limit=None)
    assert samples == ()
    assert counts == {}
