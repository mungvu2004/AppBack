"""Tokenizer + cây khối nginx, không cần `nginx -t` (container verify không có nginx).

Từ, chuỗi `'…'`/`"…"` (thoát `\\`), `{`, `}`, `;`, comment `#` tới cuối dòng. `${VAR}`
liền trong một từ (không khoảng trắng) là một phần của từ đó — hợp đồng B0-08 §3.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

_SINGLE_CHAR_TOKENS = "{};"
_WORD_BREAK_CHARS = _SINGLE_CHAR_TOKENS + "'\"#"


@dataclass(frozen=True)
class Token:
    """Một token nginx: `kind` ∈ {"word", "string", "{", "}", ";"}."""

    kind: str
    value: str


@dataclass
class Node:
    """Một chỉ thị nginx: tên, đối số (word/string đã giải), khối con nếu có `{…}`."""

    directive: str
    args: list[str]
    children: list[Node] = field(default_factory=list)


def _read_word(text: str, start: int) -> tuple[str, int]:
    """Đọc một từ, nhảy qua `${…}` nguyên khối kể cả khi bên trong có `{`/`}`."""
    i = start
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace() or ch in _WORD_BREAK_CHARS:
            break
        if ch == "$" and i + 1 < n and text[i + 1] == "{":
            end = text.index("}", i + 2)
            i = end + 1
            continue
        i += 1
    return text[start:i], i


def tokenize(text: str) -> list[Token]:
    """Cắt một file nginx thành token, bỏ comment và khoảng trắng."""
    tokens: list[Token] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "#":
            newline = text.find("\n", i)
            i = n if newline == -1 else newline + 1
            continue
        if ch in _SINGLE_CHAR_TOKENS:
            tokens.append(Token(ch, ch))
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            j = i + 1
            buf: list[str] = []
            while j < n and text[j] != quote:
                if text[j] == "\\" and j + 1 < n:
                    buf.append(text[j + 1])
                    j += 2
                    continue
                buf.append(text[j])
                j += 1
            tokens.append(Token("string", "".join(buf)))
            i = j + 1
            continue
        word, i = _read_word(text, i)
        tokens.append(Token("word", word))
    return tokens


def _parse_block(tokens: list[Token], pos: int) -> tuple[list[Node], int]:
    """Dựng danh sách chỉ thị tại một mức lồng, dừng ở `}` hoặc hết token."""
    nodes: list[Node] = []
    n = len(tokens)
    while pos < n and tokens[pos].kind != "}":
        directive = tokens[pos].value
        pos += 1
        args: list[str] = []
        while pos < n and tokens[pos].kind not in ("{", ";"):
            args.append(tokens[pos].value)
            pos += 1
        if pos >= n:
            raise ValueError(f"thiếu `;` hoặc `{{` sau chỉ thị {directive!r}")
        if tokens[pos].kind == ";":
            nodes.append(Node(directive, args, []))
            pos += 1
            continue
        pos += 1  # bỏ qua "{"
        children, pos = _parse_block(tokens, pos)
        if pos >= n or tokens[pos].kind != "}":
            raise ValueError(f"thiếu `}}` đóng khối {directive!r}")
        pos += 1
        nodes.append(Node(directive, args, children))
    return nodes, pos


def parse_nginx(text: str) -> list[Node]:
    """Dựng cây chỉ thị nginx cấp cao nhất từ nội dung một file."""
    tokens = tokenize(text)
    nodes, pos = _parse_block(tokens, 0)
    if pos != len(tokens):
        raise ValueError("thừa `}` không khớp khối nào")
    return nodes


def walk(nodes: list[Node]) -> Iterator[Node]:
    """Duyệt trước (pre-order) toàn bộ cây, kể cả khối lồng nhiều cấp."""
    for node in nodes:
        yield node
        yield from walk(node.children)


def find_directive(nodes: list[Node], name: str) -> list[Node]:
    """Mọi node có `directive == name` ở bất kỳ độ sâu nào."""
    return [n for n in walk(nodes) if n.directive == name]


def direct_includes(node: Node) -> set[str]:
    """Tên tệp (basename, không đường dẫn) của mọi `include` trực tiếp trong `node.children`."""
    return {Path(c.args[0]).name for c in node.children if c.directive == "include" and c.args}


def load_nginx_files(root: Path) -> dict[Path, list[Node]]:
    """Đọc mọi `deploy/nginx/**/*.conf` và `*.conf.template` dưới `root`, đã dựng cây."""
    files = sorted({*root.glob("**/*.conf"), *root.glob("**/*.conf.template")})
    return {path: parse_nginx(path.read_text(encoding="utf-8")) for path in files}


_INCLUDE_PREFIX = "/etc/nginx/appback/"


def resolve_includes(nodes: list[Node], nginx_root: Path, _seen: frozenset[Path] = frozenset()) -> list[Node]:
    """Thay mọi `include` (đường tuyệt đối dưới `/etc/nginx/appback/`, ánh xạ về
    `nginx_root`) bằng nội dung đã phân tích của file đó, đệ quy.

    Snippet không tự đứng làm cấu hình (luôn được `include` vào file template) nên
    ngữ cảnh xuyên file như `resolver` hay biến `set` khai ở file cha chỉ thấy được
    qua cây đã "lắp ráp" này — cây vật lý mỗi file (`load_nginx_files`) vẫn giữ
    nguyên `include` cho luật kiểm include trực tiếp (một `location` có include
    đúng snippet của nó)."""
    resolved: list[Node] = []
    for node in nodes:
        if node.directive == "include" and node.args and node.args[0].startswith(_INCLUDE_PREFIX):
            target = (nginx_root / node.args[0][len(_INCLUDE_PREFIX) :]).resolve()
            if target in _seen or not target.exists():
                resolved.append(node)
                continue
            target_nodes = parse_nginx(target.read_text(encoding="utf-8"))
            resolved.extend(resolve_includes(target_nodes, nginx_root, _seen | {target}))
            continue
        resolved.append(Node(node.directive, node.args, resolve_includes(node.children, nginx_root, _seen)))
    return resolved
