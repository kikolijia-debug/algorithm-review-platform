"""前端语法检查：用 Node 的 ESM 解析器把所有前端模块过一遍。

前端是纯原生 ES Module，没有打包步骤，语法错误只能在浏览器里才发现。
这个脚本让 ``python tools/check_frontend.py`` 就能提前拦住这类问题
（需要本机有 Node；没有 Node 时自动跳过，不影响主流程）。

    python tools/check_frontend.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_DIR = os.path.join(ROOT, "frontend", "js")

RUNNER = r"""
const fs = require('node:fs');
const vm = require('node:vm');
let bad = 0;
for (const f of process.argv.slice(2)) {
  try {
    new vm.SourceTextModule(fs.readFileSync(f, 'utf8'), { identifier: f });
  } catch (e) {
    bad += 1;
    console.log('  [语法错误] ' + f + '\n      ' + e.message);
  }
}
process.exit(bad ? 1 : 0);
"""


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("未检测到 Node，跳过前端语法检查")
        return 0
    files = []
    for base, _dirs, names in os.walk(JS_DIR):
        for n in names:
            if n.endswith(".js") or n.endswith(".mjs"):
                files.append(os.path.join(base, n))
    files.sort()
    print("=" * 64)
    print(f"前端语法检查：{len(files)} 个模块")
    print("=" * 64)
    proc = subprocess.run(
        [node, "--experimental-vm-modules", "-e", RUNNER, *files],
        capture_output=True, text=True, encoding="utf-8",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    noise = ("ExperimentalWarning", "Use `node --trace-warnings")
    for line in out.splitlines():
        if line.strip() and not any(x in line for x in noise):
            print(line)
    if proc.returncode == 0:
        print(f"\n全部 {len(files)} 个模块语法正确")
    else:
        print("\n存在语法错误，请修正后重试")
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
