#!/usr/bin/env python3
"""把课件 PDF 抽取成纯文本，便于导入题库与课件库。

依赖 pypdf（可选安装）：

    python -m pip install --target <某个可写目录> pypdf
    set PYTHONPATH=<某个可写目录>

用法：

    python tools/extract_pdf_text.py <课件目录> <输出目录> [--max-pages N]
    python tools/extract_pdf_text.py <课件目录> --outline

--outline 只打印每份课件的标题与疑似章节标题，用于快速了解课件结构，
不会写出大堆中间文件。
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None  # type: ignore[assignment]


def read_pages(path: Path, max_pages: int | None = None) -> list[str]:
    if PdfReader is None:
        raise SystemExit("缺少 pypdf，请先安装（见文件头说明）")
    reader = PdfReader(str(path))
    pages = []
    for index, page in enumerate(reader.pages):
        if max_pages is not None and index >= max_pages:
            break
        try:
            pages.append(page.extract_text() or "")
        except Exception as exc:  # 个别页面损坏时不要中断整份课件
            pages.append(f"<<抽取失败: {exc}>>")
    return pages


def normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def outline(path: Path, max_pages: int | None = None) -> str:
    pages = read_pages(path, max_pages=max_pages)
    lines = [f"===== {path.name} ({len(pages)} 页) ====="]
    seen: set[str] = set()
    for index, raw in enumerate(pages[:60], start=1):
        for line in normalize(raw).split("\n"):
            line = line.strip()
            if not 2 <= len(line) <= 60:
                continue
            # 章节标题的一般形态：编号开头、或全是实词短语
            if not re.match(r"^(\d+(\.\d+)*[\.、,，\s]|[（(]?[一二三四五六七八九十]+[)）、]|[A-Z][a-z]+)", line):
                continue
            key = line.lower()
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"  p{index:>3}: {line}")
    return "\n".join(lines)


def main() -> None:
    # Windows 控制台默认 GBK，遇到公式符号会炸；统一切到 UTF-8
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="课件目录或单个 PDF")
    parser.add_argument("target", nargs="?", help="文本输出目录（--outline 时可省略）")
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--outline", action="store_true", help="只打印结构概览")
    args = parser.parse_args()

    source = Path(args.source)
    if not source.exists():
        raise SystemExit(f"路径不存在: {source}")

    files = [source] if source.is_file() else sorted(source.glob("*.pdf"))
    if not files:
        raise SystemExit(f"{source} 下没有 PDF")

    if args.outline:
        for path in files:
            print(outline(path, args.max_pages))
        return

    if not args.target:
        raise SystemExit("请给出文本输出目录")
    target = Path(args.target)
    target.mkdir(parents=True, exist_ok=True)
    for path in files:
        text = "\n\n".join(
            f"--- page {i} ---\n{normalize(page)}"
            for i, page in enumerate(read_pages(path, args.max_pages), start=1)
        )
        out = target / (path.stem + ".txt")
        out.write_text(text, encoding="utf-8")
        print(f"{path.name} -> {out.name} ({len(text)} 字符)")


if __name__ == "__main__":
    sys.exit(main())
