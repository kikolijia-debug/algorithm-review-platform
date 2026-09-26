"""评分聚合算法（核心问题二）。

同一份主观题会收到 k 份匿名评审。评审者之间存在系统性差异：

* **宽严偏差 (bias)**：有的评审者习惯给高分，有的偏严；
* **一致性 (consistency)**：有的评审者打分稳定，有的波动很大；
* **可信度 (reliability)**：结合上述两点得到的综合权重。

本模块实现 6 种聚合方案并给出统一的评测指标，用于实验对比：

===================  ==========================================================
方法                 说明
===================  ==========================================================
``mean``             算术平均（基线）
``median``           中位数（抗离群）
``trimmed_mean``     去掉最高/最低各 p 比例后平均
``weighted_mean``    按评审者历史可信度静态加权
``robust_huber``     Huber M 估计（中位数 + MAD 初始化，迭代重加权最小二乘）
``reliability_em``   **本平台主算法**：交替估计「作业真实分 s_j、评审者偏差 b_i、
                     评审者可信度 w_i」的 EM 式迭代
===================  ==========================================================

主算法模型
----------
令 ``r_ij`` 为评审者 i 对作业 j 的评分（0-100 标准化后），

    r_ij = s_j + b_i + ε_ij ,   ε_ij ~ N(0, σ² / w_i)

其中 ``s_j`` 是作业真实水平，``b_i`` 是评审者宽严偏差，``w_i`` 是可信度权重。
对数似然最大化等价于以下交替迭代（EM / 坐标上升）：

    E 步：给定 (s, b, w) 计算残差
    M 步：
        b_i ← Σ_j w_i (r_ij - s_j) / Σ_j w_i
        s_j ← Σ_i w_i (r_ij - b_i) / Σ_i w_i
        v_i ← Σ_j (r_ij - b_i - s_j)² / n_i          # 残差方差
        w_i ← n_i / (n_i + λ) · 1 / (v_i + ε)        # 收缩 + 归一化

收缩因子 ``n_i / (n_i + λ)`` 防止「只评过 1 次」的评审者获得过高权重。

复杂度
------
设评审总数 R、迭代次数 T（实测 20 次内收敛，Δ<1e-6）：

    T = O(T · R)      S = O(n + m + R)

对比：``mean`` 为 O(R)，``trimmed_mean`` 为 O(R log R)，``robust_huber`` 为
O(T·R)。
"""

from __future__ import annotations

import math
import random
import statistics
from collections import defaultdict


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


# --------------------------------------------------------------------------
# 基础统计
# --------------------------------------------------------------------------


def trimmed_mean(values: list[float], trim_ratio: float = 0.2) -> float:
    """截尾平均：按比例去掉两端后求平均。``O(n log n)``"""
    if not values:
        return 0.0
    v = sorted(values)
    k = int(math.floor(len(v) * trim_ratio))
    if len(v) - 2 * k <= 0:
        k = max(0, (len(v) - 1) // 2)
    core = v[k : len(v) - k] if len(v) - 2 * k > 0 else v
    return sum(core) / len(core)


def median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def weighted_mean(values: list[float], weights: list[float]) -> float:
    sw = sum(weights)
    if sw <= 0:
        return statistics.fmean(values) if values else 0.0
    return sum(v * w for v, w in zip(values, weights)) / sw


def robust_huber(values: list[float], iters: int = 25, c: float = 1.345) -> float:
    """Huber M 估计（IRLS）。``O(T · n)``

    以中位数初始化、MAD 估计尺度，再迭代重加权：
    残差在 ``c·σ`` 内的样本权重为 1，之外的权重按 ``c·σ/|r|`` 衰减。
    """
    if not values:
        return 0.0
    if len(values) <= 2:
        return statistics.fmean(values)
    mu = statistics.median(values)
    mad = statistics.median([abs(v - mu) for v in values]) or 1.0
    sigma = 1.4826 * mad
    for _ in range(iters):
        num = den = 0.0
        for v in values:
            r = abs(v - mu)
            w = 1.0 if r <= c * sigma else (c * sigma / r)
            num += w * v
            den += w
        new_mu = num / den if den > 0 else mu
        if abs(new_mu - mu) < 1e-9:
            mu = new_mu
            break
        mu = new_mu
    return mu


# --------------------------------------------------------------------------
# 主算法：可信度加权 EM
# --------------------------------------------------------------------------


def reliability_em(
    reviews: list[dict],
    iters: int = 100,
    lam_b: float = 2.0,
    lam_v: float = 3.0,
    eps: float = 1e-3,
) -> dict:
    """可信度动态加权的 EM 迭代（带经验贝叶斯收缩）。

    ``reviews``: ``[{"submission_id": int, "reviewer_id": int, "score": float}, ...]``

    小样本修正
    ----------
    在真实课堂数据中，每位评审者往往只评 3-5 份，直接按样本均值估计 ``b_i``、
    按样本方差估计 ``w_i`` 会严重过拟合（一次偶然的极端打分就会让该评审者
    权重崩塌）。因此本实现采用**经验贝叶斯收缩**：

        b_i ← n_i/(n_i + λ_b) · mean_j(r_ij - s_j)
        ṽ_i ← (n_i · v_i + λ_v · σ²) / (n_i + λ_v)      # 方差向全班 σ² 收缩
        w_i ← 1 / ṽ_i

    其中 ``σ²`` 为全班残差方差。这样「只评过 2 次」的评审者权重会自动靠近
    平均水平，只有在大样本下才体现出真实的宽严/一致性强弱。

    返回::

        {
          "scores":     {submission_id: 聚合分},
          "bias":       {reviewer_id: 宽严偏差 b_i},
          "reliability":{reviewer_id: 可信度 w_i},
          "raw_weight": {reviewer_id: 未归一化权重},
          "residuals":  [(submission_id, reviewer_id, 残差)],
          "iterations": 实际迭代次数,
        }
    """
    by_sub: dict[int, list[tuple[int, float]]] = defaultdict(list)
    by_rev: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for r in reviews:
        sid, rid, sc = r["submission_id"], r["reviewer_id"], float(r["score"])
        by_sub[sid].append((rid, sc))
        by_rev[rid].append((sid, sc))
    if not by_sub:
        return {"scores": {}, "bias": {}, "reliability": {}, "residuals": [], "iterations": 0}

    allscores = [float(r["score"]) for r in reviews]
    lo, hi = min(allscores), max(allscores)
    s = {sid: sum(sc for _r, sc in items) / len(items) for sid, items in by_sub.items()}
    sigma2 = statistics.pvariance(allscores) if len(allscores) > 1 else 1.0
    b = {rid: 0.0 for rid in by_rev}
    w = {rid: 1.0 for rid in by_rev}
    raw: dict[int, float] = dict(w)

    used_iters = 0
    for it in range(iters):
        used_iters = it + 1
        # --- M 步 1：更新评审者偏差 b_i（收缩）---
        for rid, items in by_rev.items():
            num = sum(sc - s[sid] for sid, sc in items)
            n_i = len(items)
            b[rid] = (n_i / (n_i + lam_b)) * (num / n_i)
        # 偏差中心化，避免与 s_j 的整体平移不可辨识
        mean_b = sum(b.values()) / len(b)
        for rid in b:
            b[rid] -= mean_b
        # --- M 步 2：更新作业真实分 s_j ---
        new_s = {}
        for sid, items in by_sub.items():
            num = sum(w[rid] * (sc - b[rid]) for rid, sc in items)
            den = sum(w[rid] for rid, _sc in items)
            new_s[sid] = num / den if den > 0 else s[sid]
        delta = max(abs(new_s[sid] - s[sid]) for sid in new_s)
        s = new_s
        # --- M 步 3：更新全班残差方差 σ² 与可信度 w_i ---
        ss = 0.0
        cnt = 0
        for rid, items in by_rev.items():
            for sid, sc in items:
                ss += (sc - b[rid] - s[sid]) ** 2
                cnt += 1
        sigma2 = ss / max(1, cnt)
        raw = {}
        for rid, items in by_rev.items():
            n_i = len(items)
            var = sum((sc - b[rid] - s[sid]) ** 2 for sid, sc in items) / n_i
            var_shrunk = (n_i * var + lam_v * sigma2) / (n_i + lam_v)
            raw[rid] = 1.0 / (var_shrunk + eps)
        mean_w = sum(raw.values()) / len(raw)
        if mean_w > 0:
            for rid in raw:
                w[rid] = clamp(raw[rid] / mean_w, 0.25, 3.0)
        if delta < 1e-7:
            break

    # 把估计分限制在观测区间内（避免个别极值把分数拉出合理范围）
    for sid in list(s):
        s[sid] = clamp(s[sid], lo, hi)
    residuals = []
    for r in reviews:
        sid, rid, sc = r["submission_id"], r["reviewer_id"], float(r["score"])
        residuals.append((sid, rid, sc - s[sid] - b[rid]))
    return {
        "scores": s,
        "bias": b,
        "reliability": w,
        "raw_weight": raw,
        "residuals": residuals,
        "iterations": used_iters,
        "sigma": (sum(e * e for _s, _r, e in residuals) / max(1, len(residuals))) ** 0.5,
    }


# --------------------------------------------------------------------------
# 统一聚合入口
# --------------------------------------------------------------------------

METHODS = ["mean", "median", "trimmed_mean", "weighted_mean", "robust_huber", "reliability_em"]

METHOD_LABELS = {
    "mean": "算术平均",
    "median": "中位数",
    "trimmed_mean": "截尾平均",
    "weighted_mean": "可信度静态加权",
    "robust_huber": "Huber 稳健估计",
    "reliability_em": "可信度动态加权(EM)",
}


def aggregate(
    reviews: list[dict],
    method: str = "reliability_em",
    prior_weights: dict[int, float] | None = None,
    trim_ratio: float = 0.2,
) -> dict:
    """按指定方法聚合评分。

    返回 ``{"scores": {...}, "detail": {...}}``，``detail`` 中保存偏差 / 可信度
    / 残差等可用于异常检测与可视化的中间量。
    """
    by_sub: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for r in reviews:
        by_sub[r["submission_id"]].append((r["reviewer_id"], float(r["score"])))
    out: dict[int, float] = {}
    detail: dict = {"method": method, "label": METHOD_LABELS.get(method, method)}

    if method == "reliability_em":
        res = reliability_em(reviews)
        out = res["scores"]
        detail.update(
            bias=res["bias"],
            reliability=res["reliability"],
            residuals=res["residuals"],
            iterations=res["iterations"],
            sigma=res.get("sigma"),
        )
    elif method == "weighted_mean":
        weights = prior_weights or {}
        for sid, items in by_sub.items():
            ws = [max(0.05, weights.get(rid, 1.0)) for rid, _ in items]
            out[sid] = weighted_mean([sc for _r, sc in items], ws)
    elif method == "trimmed_mean":
        for sid, items in by_sub.items():
            out[sid] = trimmed_mean([sc for _r, sc in items], trim_ratio)
    elif method == "median":
        for sid, items in by_sub.items():
            out[sid] = median([sc for _r, sc in items])
    elif method == "robust_huber":
        for sid, items in by_sub.items():
            out[sid] = robust_huber([sc for _r, sc in items])
    else:  # mean
        for sid, items in by_sub.items():
            out[sid] = sum(sc for _r, sc in items) / len(items)
    return {"scores": out, "detail": detail}


# --------------------------------------------------------------------------
# 实验评测指标
# --------------------------------------------------------------------------


def bootstrap_stability(
    reviews: list[dict],
    method: str,
    rounds: int = 40,
    seed: int = 7,
) -> dict:
    """留一评审稳定性（Leave-One-Review-Out）。

    对随机抽取的若干条评审，每次只删掉这一条后重算全部聚合分，统计
    ``|新分 - 原分|`` 的均值与最大值。相比「随机丢弃 25% 评审」，留一法
    的单次扰动更小、含义更明确：**一次评审的改变会让学生最终得分变化多少分**。

    复杂度 ``O(rounds · T · R)``（T 为聚合方法的迭代次数，mean 方法为 O(1)）。
    """
    rng = random.Random(seed)
    base = aggregate(reviews, method)["scores"]
    if not reviews:
        return {"mad": 0.0, "max_dev": 0.0, "rounds": 0}
    idxs = list(range(len(reviews)))
    rng.shuffle(idxs)
    idxs = idxs[: max(1, min(rounds, len(idxs)))]
    devs = []
    for drop in idxs:
        keep = [r for i, r in enumerate(reviews) if i != drop]
        if not keep:
            continue
        cur = aggregate(keep, method)["scores"]
        for sid, v in cur.items():
            if sid in base:
                devs.append(abs(v - base[sid]))
    if not devs:
        return {"mad": 0.0, "max_dev": 0.0, "rounds": 0}
    return {
        "mad": round(sum(devs) / len(devs), 4),
        "max_dev": round(max(devs), 4),
        "p95": round(sorted(devs)[int(0.95 * (len(devs) - 1))], 4),
        "rounds": len(idxs),
    }


def _rank(values: dict) -> dict:
    order = sorted(values.items(), key=lambda kv: -kv[1])
    return {k: i + 1 for i, (k, _v) in enumerate(order)}


def spearman(a: dict, b: dict) -> float:
    """Spearman 秩相关系数。``O(n log n)``"""
    keys = [k for k in a if k in b]
    if len(keys) < 2:
        return 1.0
    ra, rb = _rank({k: a[k] for k in keys}), _rank({k: b[k] for k in keys})
    n = len(keys)
    d2 = sum((ra[k] - rb[k]) ** 2 for k in keys)
    return 1 - (6 * d2) / (n * (n * n - 1))


def evaluate_aggregation(
    reviews: list[dict],
    truth: dict[int, float] | None = None,
    methods: list[str] | None = None,
    prior_weights: dict[int, float] | None = None,
) -> list[dict]:
    """对比多种聚合方法：精度(RMSE) / 稳定性 / 对异常评审的鲁棒性 / 秩相关。"""
    methods = methods or METHODS
    rows = []
    base_scores = aggregate(reviews, "mean")["scores"]
    for m in methods:
        res = aggregate(reviews, m, prior_weights)
        scores = res["scores"]
        row = {
            "method": m,
            "label": METHOD_LABELS.get(m, m),
            "mean": round(sum(scores.values()) / max(1, len(scores)), 3),
        }
        if truth:
            rmse = 0.0
            cnt = 0
            for sid, t in truth.items():
                if sid in scores:
                    rmse += (scores[sid] - t) ** 2
                    cnt += 1
            row["rmse"] = round(math.sqrt(rmse / cnt), 4) if cnt else None
        st = bootstrap_stability(reviews, m)
        row["stability_mad"] = st["mad"]
        row["stability_max"] = st["max_dev"]
        row["rank_corr_vs_mean"] = round(spearman(scores, base_scores), 4)
        rows.append(row)
    return rows
