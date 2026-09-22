"""Đọc Dockerfile thành lệnh theo tầng, không cần Docker CLI (BE-00 §12 bước 5).

Tách theo `FROM` (một tệp có nhiều tầng multi-stage), gộp dòng nối `\\`, bỏ
comment (`#` đầu dòng sau khi rstrip khoảng trắng — Dockerfile không có chuỗi
nhiều dòng nên không cần tokenizer đầy đủ như nginx).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DockerStage:
    """Một tầng build: chỉ số 0-based, ảnh nền của `FROM`, tên tầng (`AS`) nếu có."""

    index: int
    base: str
    name: str | None


@dataclass(frozen=True)
class DockerInstruction:
    """Một lệnh Dockerfile: tên lệnh viết hoa, đối số thô (chưa tách token), tầng chứa nó.

    `stage == -1` cho lệnh (thường là `ARG`) đứng trước `FROM` đầu tiên.
    """

    name: str
    args: str
    stage: int


def _join_continuations(text: str) -> list[str]:
    """Gộp các dòng kết thúc bằng `\\` với dòng kế tiếp thành một dòng logic.

    Dockerfile chỉ dùng `\\` cuối dòng (sau khi bỏ khoảng trắng thừa) để nối dòng;
    không có trường hợp thoát `\\\\` giữ nguyên hai gạch chéo trong cú pháp này.
    """
    joined: list[str] = []
    buffer = ""
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.endswith("\\"):
            buffer += line[:-1] + " "
            continue
        joined.append(buffer + line)
        buffer = ""
    if buffer:
        joined.append(buffer)
    return joined


def _split_from(args: str) -> tuple[str, str | None]:
    """Tách `<ảnh nền> [AS <tên tầng>]` không phân biệt hoa/thường của `AS`."""
    lowered = args.lower()
    marker = " as "
    idx = lowered.find(marker)
    if idx == -1:
        return args.strip(), None
    return args[:idx].strip(), args[idx + len(marker) :].strip()


def parse_dockerfile(path: Path) -> tuple[list[DockerStage], list[DockerInstruction]]:
    """Phân tích một Dockerfile thành `(stages, instructions)`.

    Test tĩnh của B0-08 chỉ cần biết lệnh nào ở tầng nào (đặc biệt tầng cuối), nên
    không dựng cây token đầy đủ như cú pháp nginx — tách từ đầu tiên làm tên lệnh
    là đủ cho mọi chỉ thị Dockerfile hợp lệ (`FROM`, `RUN`, `COPY`, `USER`, …).
    """
    stages: list[DockerStage] = []
    instructions: list[DockerInstruction] = []
    stage_index = -1
    for logical_line in _join_continuations(path.read_text(encoding="utf-8")):
        code = logical_line.strip()
        if not code or code.startswith("#"):
            continue
        head, _, rest = code.partition(" ")
        name = head.upper()
        args = rest.strip()
        if name == "FROM":
            stage_index += 1
            base, alias = _split_from(args)
            stages.append(DockerStage(index=stage_index, base=base, name=alias))
            continue
        instructions.append(DockerInstruction(name=name, args=args, stage=stage_index))
    return stages, instructions


def last_stage_instructions(
    instructions: list[DockerInstruction], stages: list[DockerStage]
) -> list[DockerInstruction]:
    """Lọc lệnh của tầng build cuối cùng (dùng cho luật `USER 10001` ở tầng chạy)."""
    if not stages:
        return []
    last_index = stages[-1].index
    return [i for i in instructions if i.stage == last_index]


def stage_name_at(stages: list[DockerStage], index: int) -> str | None:
    """Tên tầng (`AS <tên>`) tại `index`, hoặc `None` nếu tầng đó không đặt tên."""
    for stage in stages:
        if stage.index == index:
            return stage.name
    return None
