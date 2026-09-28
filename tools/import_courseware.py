#!/usr/bin/env python3
"""把授课课件 PDF 导入平台。

    python tools/import_courseware.py "C:\\Users\\kiko\\Desktop\\算法"

做三件事：

1. 按 ``backend/courseware.py`` 里的章节清单，把源目录中的 PDF 复制到
   ``frontend/courseware/``，并改成语义化的英文文件名（避免中文名与空格在 URL 里
   出问题）；
2. 记录每份课件的原始文件名、字节数、页数、sha256，写入
   ``backend/data/courseware_manifest.json``；
3. 打印导入结果，并对清单里缺失的文件给出提示。

数据库里的课件记录由 ``backend/seed.py`` 依据该清单生成；导入完课件后重新灌一次
演示数据（``python run.py --reset``）即可在页面上看到。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import courseware as CW  # noqa: E402

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None  # type: ignore[assignment]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pages_of(path: Path) -> int:
    if PdfReader is None:
        return 0
    try:
        return len(PdfReader(str(path)).pages)
    except Exception:
        return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="课件所在目录")
    parser.add_argument("--keep-name", action="store_true",
                        help="保留原始文件名（默认重命名为语义化文件名）")
    args = parser.parse_args()

    source = Path(args.source)
    if not source.is_dir():
        raise SystemExit(f"目录不存在: {source}")

    target = ROOT / CW.COURSEWARE_DIR
    target.mkdir(parents=True, exist_ok=True)

    files: list[dict] = []
    missing: list[str] = []
    total = 0
    # 先找课件目录，再找仓库根目录（如课程作业指南这类本来就随项目分发的文件）
    search_dirs = [source, ROOT]
    for chapter in CW.CHAPTERS:
        for item in chapter["files"]:
            src = next((d / item["src"] for d in search_dirs if (d / item["src"]).exists()), None)
            if src is None:
                missing.append(f"{chapter['key']} {item['src']}")
                continue
            filename = item["src"] if args.keep_name else item["slug"] + ".pdf"
            dst = target / filename
            shutil.copy2(src, dst)
            size = dst.stat().st_size
            pages = pages_of(dst)
            total += size
            files.append(
                {
                    "chapter": chapter["key"],
                    "slug": item["slug"],
                    "source": item["src"],
                    "filename": filename,
                    "title": item["title"],
                    "size_bytes": size,
                    "pages": pages,
                    "sha256": sha256_of(dst),
                }
            )
            print(f"  {item['src']:<28} -> {filename:<32} {size / 1048576:5.2f} MB  {pages:>4} 页")

    manifest = {
        "imported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_dir": str(source),
        "total_bytes": total,
        "file_count": len(files),
        "files": files,
    }
    (ROOT / "backend" / "data").mkdir(parents=True, exist_ok=True)
    with open(CW.MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)

    print(f"\n导入 {len(files)} 份课件，共 {total / 1048576:.1f} MB")
    print(f"清单已写入 {CW.MANIFEST_PATH}")
    if files and not any(f["pages"] for f in files):
        print("提示：未安装 pypdf，页数记为 0（不影响其它功能）")
    if missing:
        print("\n以下文件在源目录中没有找到：")
        for m in missing:
            print("  " + m)


if __name__ == "__main__":
    main()
