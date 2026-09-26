"""算法复杂度自动判定（实验验证工具）。

给定同一程序在若干输入规模 ``n`` 下的实测耗时 ``t``，判定它最接近哪种
渐进复杂度。用于教学演示与课程实验，帮助理解「实测曲线 ⇒ 复杂度阶」。

方法
----
对候选模型集合 ``F = {1, log n, n, n log n, n², n³, 2ⁿ}``，
在**对数空间**做最小二乘拟合 ``log t ≈ log c + log f(n)``，
即最小化 ``Σ (log t_i - log c - log f(n_i))²``。

对数空间拟合的好处：对不同数量级的耗时同样敏感（相对误差而非绝对误差），
并且能容纳 ``2ⁿ`` 这样增长极快的模型（不会数值溢出）。

最优常数 ``log c = mean(log t_i - log f(n_i))``，目标值
``E(f) = std(log t_i - log f(n_i))``（残差标准差，越小越吻合）。

另外给出**倍增比诊断**：若 ``t(2n)/t(n)`` 稳定在 ``2^p``，则阶为 ``O(n^p)``，
可用来直观校核拟合结果。

复杂度：``O(|F| · P)``，``P`` 为采样点数（通常 ≤ 8），即常数时间开销。
"""

from __future__ import annotations

import math

MODELS = {
    "O(1)": lambda n: 1.0,
    "O(log n)": lambda n: max(1.0, math.log2(max(2, n))),
    "O(n)": lambda n: float(n),
    "O(n log n)": lambda n: n * max(1.0, math.log2(max(2, n))),
    "O(n²)": lambda n: float(n) ** 2,
    "O(n³)": lambda n: float(n) ** 3,
    "O(2ⁿ)": lambda n: 2.0 ** min(n, 40),
}


def fit_complexity(points: list[dict]) -> dict:
    """``points``: ``[{"n": int, "time_ms": float}, ...]``（至少 3 个点）。"""
    pts = [(float(p["n"]), max(float(p["time_ms"]), 1e-6)) for p in points if p.get("n")]
    pts = [(n, t) for n, t in pts if n > 0]
    if len(pts) < 3:
        return {"ok": False, "reason": "需要至少 3 个 (n, t) 采样点"}

    results = []
    for name, f in MODELS.items():
        logs = [math.log(t) for _n, t in pts]
        flogs = [math.log(max(f(n), 1e-12)) for n, _t in pts]
        resid = [a - b for a, b in zip(logs, flogs)]
        mean_r = sum(resid) / len(resid)
        var = sum((r - mean_r) ** 2 for r in resid) / len(resid)
        rmse = math.sqrt(var)
        results.append({"model": name, "log_rmse": round(rmse, 5), "log_c": round(mean_r, 4)})
    results.sort(key=lambda r: r["log_rmse"])
    best = results[0]

    ratios = []
    pts_sorted = sorted(pts)
    for (n1, t1), (n2, t2) in zip(pts_sorted, pts_sorted[1:]):
        if n2 > n1 and t1 > 0:
            ratios.append(
                {
                    "from": n1,
                    "to": n2,
                    "ratio": round(t2 / t1, 4),
                    "exponent": round(math.log(t2 / t1) / math.log(n2 / n1), 3),
                }
            )
    # 拟合出的经验幂次
    try:
        xs = [math.log(n) for n, _t in pts]
        ys = [math.log(t) for _n, t in pts]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        denom = sum((x - mx) ** 2 for x in xs)
        slope = (
            sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom if denom > 0 else 0.0
        )
    except ValueError:
        slope = 0.0

    return {
        "ok": True,
        "points": [{"n": n, "time_ms": round(t, 4)} for n, t in pts],
        "best": best["model"],
        "best_log_rmse": best["log_rmse"],
        "ranking": results,
        "doubling": ratios,
        "empirical_exponent": round(slope, 3),
        "confidence": (
            "高"
            if len(results) > 1 and results[1]["log_rmse"] - best["log_rmse"] > 0.25
            else "中" if len(results) > 1 and results[1]["log_rmse"] - best["log_rmse"] > 0.08 else "低"
        ),
    }
