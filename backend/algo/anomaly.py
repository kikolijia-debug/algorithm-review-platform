"""异常评审行为检测（核心问题三）。

检测目标
--------
1. **单次评分偏离**：某条评分与「该作业真实水平 + 该评审者固有偏差」相差过大；
2. **长期偏高 / 偏低**：评审者偏差 ``b_i`` 显著非零；
3. **异常评审时长**：明显过短（未认真阅读）或过长（挂机）；
4. **打分退化**：对所有作业给完全相同（或几乎相同）的分数 / 所有评分都满分；
5. **固定互评关系 / 串通**：互评关系图中出现重复互评、双向互评、封闭小团体。

统计工具
--------
* 残差 z 检验：``z = (r_ij - s_j - b_i) / σ``，``|z| > 3`` 视为离群；
* MAD 稳健离群：``|x - median| / (1.4826 · MAD) > 3.5``，对单个极端值不敏感；
* 偏差显著性：``t = b_i / (σ / sqrt(n_i))``，用正态近似得到双尾 p 值；
* 图算法：标签传播（label propagation）做社区发现，用互惠边密度刻画小团体。

复杂度
------
设 R 为评审数、m 为评审者数、g 为互评关系图边数、I 为标签传播轮数：

    T = O(R + m·I + g·I)      S = O(m + g + R)

全部为线性 / 近线性，可在教师端实时运行。
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict

from .aggregation import reliability_em


def _norm_sf(z: float) -> float:
    """标准正态分布上尾概率 P(Z > z)。"""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def _two_sided_p(z: float) -> float:
    return 2 * _norm_sf(abs(z))


def _mad(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    med = statistics.median(values)
    mad = statistics.median([abs(v - med) for v in values]) or 1e-9
    return med, 1.4826 * mad


def detect(
    reviews: list[dict],
    rubric_keys: list[str] | None = None,
    min_reviews_for_bias: int = 3,
    z_threshold: float = 2.8,
    duration_z: float = 2.8,
) -> dict:
    """对一轮互评执行全套异常检测。

    ``reviews`` 元素需要包含：
        ``submission_id``, ``reviewer_id``, ``score``, 可选 ``duration_sec``,
        ``rubric``(dict), ``author_id``

    返回 ``{"anomalies": [...], "reviewer_stats": {...}, "graph": {...}}``。
    """
    if not reviews:
        return {"anomalies": [], "reviewer_stats": {}, "graph": {}}

    est = reliability_em(reviews)
    s, b, w = est["scores"], est["bias"], est["reliability"]
    sigma = est.get("sigma") or 1.0
    sigma = max(sigma, 1e-6)

    by_rev: dict[int, list[dict]] = defaultdict(list)
    for r in reviews:
        by_rev[r["reviewer_id"]].append(r)

    anomalies: list[dict] = []
    reviewer_stats: dict[int, dict] = {}

    # ---------------- 1. 评审者级别的统计量 ----------------
    durations = [float(r["duration_sec"]) for r in reviews if r.get("duration_sec")]
    dur_med, dur_sigma = _mad(durations)

    for rid, items in by_rev.items():
        n = len(items)
        scores = [float(it["score"]) for it in items]
        sd = statistics.pstdev(scores) if n > 1 else 0.0
        std_err = sigma / math.sqrt(max(1, n)) if n else sigma
        t_bias = b[rid] / std_err if std_err else 0.0
        p_bias = _two_sided_p(t_bias)
        mean_dur = (
            sum(float(it["duration_sec"]) for it in items if it.get("duration_sec")) / n
            if any(it.get("duration_sec") for it in items)
            else None
        )
        # 评分区分度：对同一批作业打分越集中，越可能是「一键打分」
        flat = sd < 1.0 and n >= 3
        all_max = n >= 3 and all(x >= 97 for x in scores)
        all_same = n >= 2 and len(set(scores)) == 1
        reviewer_stats[rid] = {
            "n_reviews": n,
            "mean_score": round(statistics.fmean(scores), 3),
            "std_score": round(sd, 3),
            "bias": round(b[rid], 4),
            "bias_t": round(t_bias, 3),
            "bias_p": round(p_bias, 5),
            "reliability": round(w[rid], 4),
            "mean_duration": round(mean_dur, 1) if mean_dur is not None else None,
            "flat_scoring": flat,
            "all_max": all_max,
        }
        if n >= min_reviews_for_bias and p_bias < 0.05 and abs(b[rid]) >= 4:
            direction = "偏高" if b[rid] > 0 else "偏低"
            anomalies.append(
                {
                    "type": "reviewer_bias",
                    "level": "high" if p_bias < 0.01 else "medium",
                    "reviewer_id": rid,
                    "title": f"评审者长期{direction}打分",
                    "detail": (
                        f"平均偏差 {b[rid]:+.2f} 分（t={t_bias:.2f}, p={p_bias:.4f}），"
                        f"基于 {n} 份评审；可信度权重已下调至 {w[rid]:.2f}"
                    ),
                    "evidence": {"bias": round(b[rid], 3), "p_value": round(p_bias, 5), "n": n},
                    "suggestion": "降低该评审者权重，或安排教师复核其评分",
                }
            )
        if flat and n >= 3:
            anomalies.append(
                {
                    "type": "flat_scoring",
                    "level": "medium",
                    "reviewer_id": rid,
                    "title": "评分无区分度",
                    "detail": f"{n} 份评审的标准差仅 {sd:.2f}，疑似未按标准逐项评分",
                    "evidence": {"std": round(sd, 3), "n": n},
                    "suggestion": "提醒评审者按评分细则打分，并抽查其文字意见质量",
                }
            )
        if all_max:
            anomalies.append(
                {
                    "type": "all_max",
                    "level": "medium",
                    "reviewer_id": rid,
                    "title": "全部给满分",
                    "detail": f"{n} 份评审全部 >= 97 分，可能存在「友情评分」",
                    "evidence": {"mean": round(statistics.fmean(scores), 2), "n": n},
                    "suggestion": "降低权重并要求补充评审理由",
                }
            )

    # ---------------- 2. 单条评审的残差离群 ----------------
    for r in reviews:
        sid, rid = r["submission_id"], r["reviewer_id"]
        sc = float(r["score"])
        resid = sc - s.get(sid, sc) - b.get(rid, 0.0)
        z = resid / sigma
        if abs(z) > z_threshold:
            anomalies.append(
                {
                    "type": "score_outlier",
                    "level": "high" if abs(z) > 3.5 else "medium",
                    "reviewer_id": rid,
                    "submission_id": sid,
                    "title": "单次评分显著偏离",
                    "detail": (
                        f"给出 {sc:.1f} 分，而综合同侪意见该作业应为 "
                        f"{s.get(sid, sc) + b.get(rid, 0.0):.1f} 分左右（残差 {resid:+.1f}，z={z:+.2f}）"
                    ),
                    "evidence": {"residual": round(resid, 3), "z": round(z, 3)},
                    "suggestion": "请教师复核该条评分，必要时以修正分替代",
                }
            )
        # 时长异常
        if r.get("duration_sec") and dur_sigma > 0:
            d = float(r["duration_sec"])
            zd = (d - dur_med) / dur_sigma
            if abs(zd) > duration_z:
                anomalies.append(
                    {
                        "type": "duration_anomaly",
                        "level": "medium",
                        "reviewer_id": rid,
                        "submission_id": sid,
                        "title": "评审时长异常",
                        "detail": (
                            f"用时 {d:.0f} 秒，全班中位数 {dur_med:.0f} 秒（稳健 z={zd:+.2f}）"
                        ),
                        "evidence": {"duration": d, "median": dur_med, "z": round(zd, 3)},
                        "suggestion": "时长过短者提示重评，过长者确认是否存在挂机",
                    }
                )
        # 评分细则内部不一致（各维度差异过大）
        rubric = r.get("rubric") or {}
        if rubric and len(rubric) >= 3:
            vals = [float(v) for v in rubric.values()]
            if max(vals) - min(vals) >= 40:
                anomalies.append(
                    {
                        "type": "rubric_inconsistent",
                        "level": "low",
                        "reviewer_id": rid,
                        "submission_id": sid,
                        "title": "评分细则各维度差异过大",
                        "detail": f"维度极差 {max(vals) - min(vals):.0f} 分，可能存在误操作",
                        "evidence": {"rubric": rubric},
                        "suggestion": "提示评审者核对各维度分值",
                    }
                )

    graph = _relation_graph(reviews)
    anomalies.extend(_relation_anomalies(graph, reviews))
    return {
        "anomalies": anomalies,
        "reviewer_stats": reviewer_stats,
        "graph": graph,
        "estimates": {
            "scores": {str(k): round(v, 3) for k, v in s.items()},
            "bias": {str(k): round(v, 3) for k, v in b.items()},
            "reliability": {str(k): round(v, 3) for k, v in w.items()},
        },
        "sigma": round(sigma, 4),
    }


def _relation_anomalies(graph: dict, reviews: list[dict]) -> list[dict]:
    """把互评关系图中的可疑结构转成异常条目。

    判定规则（刻意保守，避免误伤正常同学）：

    * **双向互评**：A 评 B 且 B 评 A。若两个方向的评分都异常高（均 ≥ 88），
      或这种关系在多轮中重复出现（count ≥ 2），则判定为「固定互评关系」；
    * **紧密小团体**：标签传播得到的社区规模 ≥ 4 且内部边密度 ≥ 0.6，
      提示可能存在抱团互评，交由教师复核。
    """
    score_of = {(r["reviewer_id"], r.get("author_id")): float(r.get("score") or 0) for r in reviews}
    out: list[dict] = []
    for p in graph.get("reciprocal", []):
        a, b = p["a"], p["b"]
        s_ab = score_of.get((a, b))
        s_ba = score_of.get((b, a))
        both_high = s_ab is not None and s_ba is not None and s_ab >= 88 and s_ba >= 88
        if not (both_high or p["count"] >= 2):
            continue
        out.append(
            {
                "type": "reciprocal_pair",
                "level": "high" if both_high else "medium",
                "reviewer_id": a,
                "title": "固定互评关系（双向互评）",
                "detail": (
                    f"评审者 {a} 与 {b} 互为评审，评分分别为 "
                    f"{s_ab if s_ab is not None else '—'} / {s_ba if s_ba is not None else '—'} 分，"
                    f"累计 {p['count']} 次；建议检查是否存在「互相打高分」"
                ),
                "evidence": {"pair": [a, b], "score_ab": s_ab, "score_ba": s_ba, "rounds": p["count"]},
                "suggestion": "打散这两人后续轮次的互评关系，并人工复核两轮的打分",
            }
        )
    for c in graph.get("clusters", [])[:2]:
        members = set(c)
        inner = sum(
            1
            for e in graph.get("edges", [])
            if e["source"] in members and e["target"] in members
        )
        density = inner / max(1, len(c) * (len(c) - 1))
        if len(c) >= 4 and density >= 0.6:
            out.append(
                {
                    "type": "review_cluster",
                    "level": "medium",
                    "reviewer_id": c[0],
                    "title": "疑似抱团互评小团体",
                    "detail": (
                        f"互评关系图中出现规模 {len(c)}、内部边密度 {density:.2f} 的社区："
                        + "、".join(str(x) for x in c[:8])
                        + ("…" if len(c) > 8 else "")
                    ),
                    "evidence": {"members": c, "density": round(density, 3)},
                    "suggestion": "下一轮分配时把该组成员拆散到不同组",
                }
            )
    return out


# --------------------------------------------------------------------------
# 互评关系图与串通检测
# --------------------------------------------------------------------------


def _relation_graph(reviews: list[dict]) -> dict:
    """构建互评关系图，检测双向互评、重复互评与小团体。

    边 ``(u → v)`` 表示 u 评审了 v 的作业（u 是评审者，v 是作者）。
    复杂度 ``O(R + m·I + g·I)``。
    """
    cnt: dict[tuple[int, int], int] = defaultdict(int)
    for r in reviews:
        author = r.get("author_id")
        if author is None:
            continue
        cnt[(r["reviewer_id"], author)] += 1
    adj: dict[int, dict[int, int]] = defaultdict(dict)
    for (u, v), c in cnt.items():
        adj[u][v] = c

    reciprocal = []
    seen = set()
    for (u, v), c in cnt.items():
        if (v, u) in cnt and (v, u) not in seen:
            seen.add((u, v))
            seen.add((v, u))
            reciprocal.append(
                {
                    "a": u,
                    "b": v,
                    "count": c + cnt[(v, u)],
                    "reason": "双向互评",
                }
            )
    repeated = [
        {"a": u, "b": v, "count": c, "reason": "重复互评"}
        for (u, v), c in cnt.items()
        if c >= 2
    ]

    # ---- 标签传播社区发现 ----
    nodes = sorted(adj.keys() | {v for _u, vs in adj.items() for v in vs})
    label = {n: n for n in nodes}
    for _ in range(30):
        changed = False
        for n in nodes:
            nb = list(adj[n].keys()) + [u for u, vs in adj.items() if n in vs]
            if not nb:
                continue
            tally: dict[int, int] = defaultdict(int)
            for x in nb:
                tally[label[x]] += 1
            best = max(tally.items(), key=lambda kv: (kv[1], -kv[0]))[0]
            if best != label[n]:
                label[n] = best
                changed = True
        if not changed:
            break
    comm: dict[int, list[int]] = defaultdict(list)
    for n in nodes:
        comm[label[n]].append(n)
    clusters = sorted(
        [sorted(v) for v in comm.values() if len(v) >= 3], key=len, reverse=True
    )

    edges = [
        {"source": u, "target": v, "weight": c}
        for (u, v), c in sorted(cnt.items(), key=lambda kv: -kv[1])
    ]
    # 簇内边密度（刻画小团体紧密度）
    cluster_members = _flat(clusters)
    intra = sum(
        1
        for e in edges
        if e["source"] in cluster_members
        and e["target"] in cluster_members
        and _same_cluster(clusters, e["source"], e["target"])
    )
    density = intra / max(1, len(edges))

    return {
        "nodes": nodes,
        "edges": edges,
        "reciprocal": reciprocal,
        "repeated": repeated,
        "clusters": clusters,
        "intra_cluster_density": round(density, 4),
        "n_nodes": len(nodes),
        "n_edges": len(edges),
    }


def _flat(clusters: list[list[int]]) -> set[int]:
    return {x for c in clusters for x in c}


def _same_cluster(clusters: list[list[int]], a: int, b: int) -> bool:
    for c in clusters:
        if a in c and b in c:
            return True
    return False


def risk_score(stats: dict, anomalies: list[dict], rid: int) -> dict:
    """把某位评审者的异常证据汇总为 0-100 的风险分与等级。"""
    mine = [a for a in anomalies if a.get("reviewer_id") == rid]
    weight = {"high": 22, "medium": 11, "low": 4}
    score = sum(weight.get(a["level"], 4) for a in mine)
    st = stats.get(rid) or {}
    if abs(st.get("bias_t", 0)) > 2:
        score += 8
    if (st.get("reliability") or 1) < 0.6:
        score += 8
    score = min(100, int(round(score)))
    level = "高" if score >= 45 else ("中" if score >= 20 else "低")
    return {"reviewer_id": rid, "risk": score, "level": level, "count": len(mine)}
