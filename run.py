#!/usr/bin/env python3
"""一键启动脚本。

    python run.py                 # 默认 127.0.0.1:8000
    python run.py 0.0.0.0 8000    # 监听到局域网，方便同学互相访问
    python run.py --reset         # 重新生成演示数据后再启动

首次运行会自动建库并灌入演示数据（约 2-3 秒）。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend import db, server, seed  # noqa: E402


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = {a for a in sys.argv[1:] if a.startswith("-")}
    host = args[0] if args else os.environ.get("AJP_HOST", "127.0.0.1")
    port = int(args[1]) if len(args) > 1 else int(os.environ.get("AJP_PORT", 8000))
    db.init_db()
    if "--reset" in flags:
        print("重新生成演示数据 ...", flush=True)
        seed.seed(reset=True, verbose=True)
    elif db.is_empty():
        print("首次运行：生成演示数据 ...", flush=True)
        seed.seed(reset=True, verbose=True)
    server.serve(host, port, seed_if_empty=False)


if __name__ == "__main__":
    main()
