"""一次性校验脚本：把题库中每个模板实际跑一遍评测，缓存真实判定结果。

用途：
* 保证演示数据中「学生提交的代码」与「记录的判定结果」完全一致；
* 生成 ``backend/data/template_verdicts.json``，后续重新灌数据时直接复用，
  不必再次编译运行（把几十秒的编译开销变成毫秒级读取）。

运行：``python backend/verify_templates.py [--force]``
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import judge as J  # noqa: E402
from backend import problem_bank as PB  # noqa: E402

CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "template_verdicts.json")


def gen_cases(problem: dict, seed: int = 2026) -> list[dict]:
    return PB.build_cases(problem, seed)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="忽略缓存，重新跑全部模板")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)

    cache: dict = {}
    if os.path.exists(CACHE_PATH) and not args.force:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)

    print(f"可用语言: {json.dumps(J.available_languages(), ensure_ascii=False)}")
    print(f"C++ 标准: {J.cpp_std_flag()}")
    changed = 0
    t_all = time.time()
    for prob in PB.PROBLEMS:
        key = prob["key"]
        cases = gen_cases(prob)
        entry = cache.setdefault(key, {})
        entry["cases"] = cases
        for tag in ("ok", "slow", "bug"):
            src = PB.CPP.get(key, {}).get(tag)
            if not src or tag in entry.get("verdicts", {}):
                continue
            t0 = time.time()
            r = J.judge_submission(
                src, "cpp", cases, prob["time_limit_ms"], prob["memory_limit_mb"]
            )
            entry.setdefault("verdicts", {})[tag] = {
                "verdict": r["verdict"],
                "score": r["score"],
                "time_ms": r.get("time_ms", 0),
                "memory_kb": r.get("memory_kb", 0),
                "passed": r.get("passed"),
                "total_cases": r.get("total_cases"),
                "message": (r.get("message") or r.get("compile_message") or "")[:400],
            }
            changed += 1
            v = entry["verdicts"][tag]
            print(
                f"  {key:<11} {tag:<5} -> {v['verdict']:<9} score={v['score']:>6} "
                f"time={v['time_ms']:>9.1f}ms passed={v['passed']}/{v['total_cases']} "
                f"({time.time() - t0:.1f}s)"
            )
            if v["verdict"] == "CE":
                print("      CE:", v["message"][:200])
        # Python 模板
        if "PY" in dir(PB) and PB.PY.get(key) and "python" not in entry.get("verdicts", {}):
            t0 = time.time()
            r = J.judge_submission(
                PB.PY[key], "python", cases, prob["time_limit_ms"] * 3, prob["memory_limit_mb"]
            )
            entry.setdefault("verdicts", {})["python"] = {
                "verdict": r["verdict"],
                "score": r["score"],
                "time_ms": r.get("time_ms", 0),
                "memory_kb": r.get("memory_kb", 0),
                "passed": r.get("passed"),
                "total_cases": r.get("total_cases"),
                "message": (r.get("message") or r.get("compile_message") or "")[:400],
            }
            changed += 1
            v = entry["verdicts"]["python"]
            print(
                f"  {key:<11} py    -> {v['verdict']:<9} score={v['score']:>6} "
                f"time={v['time_ms']:>9.1f}ms passed={v['passed']}/{v['total_cases']} "
                f"({time.time() - t0:.1f}s)"
            )

    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    size_mb = os.path.getsize(CACHE_PATH) / 1024 / 1024
    print(f"\n完成：新增/更新 {changed} 个模板，用时 {time.time() - t_all:.1f}s")
    print(f"缓存写入 {CACHE_PATH}（{size_mb:.2f} MB）")


if __name__ == "__main__":
    main()
