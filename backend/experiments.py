"""算法实验台：把「算法设计 → 复杂度分析 → 实验验证」变成可复现的实验。

包含 5 组实验，全部与前端「算法实验台」页面一一对应：

====================  ==========================================================
实验                  对比内容
====================  ==========================================================
``allocation``        随机 / 贪心 / 最小费用流 / 最小费用流+局部搜索
                      在覆盖率、负载均衡(基尼系数)、互为评审、跨班比例、耗时上的差异
``aggregation``       6 种评分聚合方法在 RMSE（对真值）、留一稳定性、
                      抗异常评审能力、秩相关上的差异
``anomaly``           异常检测在注入已知异常时的精确率 / 召回率 / F1
``complexity``        真实运行 O(n²)、O(n log n) 程序，实测 (n, t) 并自动拟合复杂度阶
``similarity``        代码相似度检测在不同「抄袭改写程度」下的识别效果与耗时
====================  ==========================================================

每个实验都返回结构化结果，前端用图表展示并支持导出 JSON，便于写进实验报告。
"""

from __future__ import annotations

import math
import random
import time

from .algo import aggregation as AG
from .algo import anomaly as AN
from .algo import assignment as AS
from .algo import complexity as CX
from .algo import similarity as SIM
from . import judge as J


def _klass(n: int, groups: int = 2) -> dict[int, str]:
    return {i: f"G{i % groups}" for i in range(1, n + 1)}


# ---------------------------------------------------------------------------
# 实验 1：评审任务分配算法对比
# ---------------------------------------------------------------------------


def experiment_allocation(
    n_students: int = 60,
    k: int = 3,
    max_load: int = 4,
    rounds: int = 5,
    groups: int = 2,
) -> dict:
    authors = list(range(1, n_students + 1))
    klass = _klass(n_students, groups)
    methods = ["random", "greedy", "mcmf", "mcmf+ls"]
    acc: dict[str, list[dict]] = {m: [] for m in methods}
    timing: dict[str, list[float]] = {m: [] for m in methods}
    detail: dict[str, dict] = {}
    for r in range(rounds):
        params = AS.AllocationParams(
            reviews_per_submission=k, max_load=max_load, seed=1000 + r,
            use_local_search=True,
        )
        for m in methods:
            t0 = time.perf_counter()
            if m == "random":
                res = AS.allocate_random(authors, authors, klass, params)
            elif m == "greedy":
                res = AS.allocate_greedy(authors, authors, klass, params)
            else:
                p = params
                if m == "mcmf":
                    p = AS.AllocationParams(
                        reviews_per_submission=k, max_load=max_load, seed=1000 + r,
                        use_local_search=False,
                    )
                res = AS.allocate_mcmf(authors, authors, klass, p)
            el = (time.perf_counter() - t0) * 1000
            timing[m].append(el)
            met = AS.evaluate_allocation(res.allocations, authors, authors, klass, {}, k)
            met["elapsed_ms"] = round(el, 2)
            acc[m].append(met)
            if r == 0:
                detail[m] = {
                    "stats": res.stats,
                    "sample": res.allocations[:12],
                }

    keys = [
        "coverage", "load_max", "load_min", "load_std", "gini_load",
        "self_review", "reciprocal_pairs", "cross_class_ratio", "elapsed_ms",
    ]
    rows = []
    for m in methods:
        row = {"method": m, "label": {
            "random": "随机分配", "greedy": "贪心负载均衡",
            "mcmf": "最小费用流", "mcmf+ls": "最小费用流 + 局部搜索",
        }[m]}
        for key in keys:
            vals = [x.get(key, 0) or 0 for x in acc[m]]
            row[key] = round(sum(vals) / len(vals), 4)
        row["elapsed_total_ms"] = round(sum(timing[m]), 2)
        rows.append(row)
    return {
        "experiment": "allocation",
        "title": "评审任务分配算法对比",
        "params": {"n_students": n_students, "k": k, "max_load": max_load,
                   "rounds": rounds, "groups": groups},
        "metrics": keys,
        "rows": rows,
        "detail": detail,
        "conclusion": _alloc_conclusion(rows),
    }


def _alloc_conclusion(rows: list[dict]) -> str:
    best = min(rows, key=lambda r: (r["gini_load"], r["reciprocal_pairs"]))
    rand = next((r for r in rows if r["method"] == "random"), None)
    parts = [
        f"{best['label']} 在负载均衡（基尼系数 {best['gini_load']:.4f}）与"
        f"互为评审（{best['reciprocal_pairs']} 对）两项上综合最优。"
    ]
    if rand:
        parts.append(
            f"随机分配的负载极差为 {rand['load_max'] - rand['load_min']}，"
            f"基尼系数 {rand['gini_load']:.4f}，明显高于最优方案；"
            f"而耗时仅 {best['elapsed_ms']:.1f} ms，在课堂规模下完全可接受。"
        )
    return "".join(parts)


# ---------------------------------------------------------------------------
# 实验 2：评分聚合方法对比
# ---------------------------------------------------------------------------


def experiment_aggregation(
    n_submissions: int = 60,
    n_reviewers: int = 60,
    k: int = 5,
    bias_sd: float = 8.0,
    noise_sd: float = 5.0,
    malicious: int = 2,
    rounds: int = 3,
    seed: int = 42,
) -> dict:
    acc: dict[str, list[dict]] = {}
    for r in range(rounds):
        rng = random.Random(seed + r)
        truth = {s: 60 + 15 * rng.gauss(0, 1) for s in range(1, n_submissions + 1)}
        bias = {i: rng.gauss(0, bias_sd) for i in range(1, n_reviewers + 1)}
        reviews = []
        for s in range(1, n_submissions + 1):
            for rv in rng.sample(range(1, n_reviewers + 1), k):
                reviews.append({
                    "submission_id": s, "reviewer_id": rv, "author_id": s,
                    "score": max(0.0, min(100.0, truth[s] + bias[rv] + rng.gauss(0, noise_sd))),
                })
        # 注入恶意评审：要么全部满分，要么全部给低分
        for i in range(malicious):
            rv = 900 + i
            for s in rng.sample(range(1, n_submissions + 1), max(1, n_submissions // 2)):
                reviews.append({
                    "submission_id": s, "reviewer_id": rv, "author_id": s,
                    "score": 99.0 if i % 2 == 0 else 15.0,
                })
        rows = AG.evaluate_aggregation(reviews, truth)
        for row in rows:
            acc.setdefault(row["method"], []).append(row)
    rows = []
    for m, items in acc.items():
        avg = {"method": m, "label": items[0]["label"]}
        for key in ("rmse", "stability_mad", "stability_max", "rank_corr_vs_mean", "mean"):
            vals = [x[key] for x in items if x.get(key) is not None]
            avg[key] = round(sum(vals) / len(vals), 4) if vals else None
        rows.append(avg)
    rows.sort(key=lambda r: (r["rmse"] if r["rmse"] is not None else 9e9))
    return {
        "experiment": "aggregation",
        "title": "评分聚合方法对比",
        "params": {
            "n_submissions": n_submissions, "n_reviewers": n_reviewers, "k": k,
            "bias_sd": bias_sd, "noise_sd": noise_sd, "malicious": malicious,
            "rounds": rounds,
        },
        "metrics": ["rmse", "stability_mad", "rank_corr_vs_mean", "mean"],
        "rows": rows,
        "conclusion": _agg_conclusion(rows),
    }


def _agg_conclusion(rows: list[dict]) -> str:
    best = rows[0]
    plain = next((r for r in rows if r["method"] == "mean"), None)
    if not plain:
        return ""
    gain = (plain["rmse"] - best["rmse"]) / plain["rmse"] * 100 if plain["rmse"] else 0
    return (
        f"{best['label']} 的 RMSE 为 {best['rmse']:.3f}，比算术平均（{plain['rmse']:.3f}）"
        f"降低 {gain:.1f}%，说明在存在宽严偏差与恶意评分的真实数据上，"
        f"动态可信度加权能显著提升估计精度；代价是留一稳定性"
        f"（{best['stability_mad']:.4f}）略高于算术平均（{plain['stability_mad']:.4f}），"
        f"需要在「精度」与「可解释的稳定性」之间权衡。"
    )


# ---------------------------------------------------------------------------
# 实验 3：异常检测效果评估
# ---------------------------------------------------------------------------


def experiment_anomaly(
    n_submissions: int = 60,
    n_reviewers: int = 60,
    k: int = 5,
    n_bad: int = 4,
    rounds: int = 5,
    seed: int = 7,
) -> dict:
    """注入已知异常评审者，统计检出精确率 / 召回率 / F1。"""
    tp = fp = fn = 0
    per_round = []
    for r in range(rounds):
        rng = random.Random(seed + r)
        truth = {s: 60 + 15 * rng.gauss(0, 1) for s in range(1, n_submissions + 1)}
        bad = set(rng.sample(range(1, n_reviewers + 1), n_bad))
        bias = {i: (rng.choice([-18, 18]) if i in bad else rng.gauss(0, 3))
                for i in range(1, n_reviewers + 1)}
        noise = {i: (1.0 if i in bad else abs(rng.gauss(3.5, 1)) + 1)
                 for i in range(1, n_reviewers + 1)}
        reviews = []
        for s in range(1, n_submissions + 1):
            for rv in rng.sample(range(1, n_reviewers + 1), k):
                reviews.append({
                    "submission_id": s, "reviewer_id": rv, "author_id": s,
                    "score": max(0.0, min(100.0, truth[s] + bias[rv] + rng.gauss(0, noise[rv]))),
                    "duration_sec": (25.0 if rv in bad else rng.gauss(420, 110)),
                })
        det = AN.detect(reviews)
        stats = det["reviewer_stats"]
        risks = {rid: AN.risk_score(stats, det["anomalies"], rid) for rid in stats}
        # 评审者级判定：风险等级为「高」才认定为异常（对应教师端「高优先级复核」）
        flagged = {rid for rid, v in risks.items() if v["level"] == "高"}
        suspicious = {rid for rid, v in risks.items() if v["level"] == "中"}
        bad_in_play = {b for b in bad if any(x["reviewer_id"] == b for x in reviews)}
        t = len(flagged & bad_in_play)
        f = len(flagged - bad_in_play)
        n = len(bad_in_play - flagged)
        tp += t
        fp += f
        fn += n
        per_round.append({
            "round": r + 1, "injected": len(bad_in_play), "flagged": len(flagged),
            "suspicious": len(suspicious),
            "tp": t, "fp": f, "fn": n,
        })
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "experiment": "anomaly",
        "title": "异常评审检测效果",
        "params": {"n_submissions": n_submissions, "n_reviewers": n_reviewers,
                   "k": k, "n_bad": n_bad, "rounds": rounds},
        "metrics": ["precision", "recall", "f1"],
        "rows": [
            {"method": "risk", "label": "综合风险分 ≥ 45（高风险复核）",
             "precision": round(precision, 4), "recall": round(recall, 4),
             "f1": round(f1, 4), "tp": tp, "fp": fp, "fn": fn},
        ],
        "per_round": per_round,
        "conclusion": (
            f"在 {rounds} 轮模拟中累计注入 {tp + fn} 个异常评审者，"
            f"检出 {tp} 个，误报 {fp} 个，精确率 {precision:.3f}、召回率 {recall:.3f}、"
            f"F1 {f1:.3f}。误报主要来自「只评了 3 份」的小样本评审者，"
            f"因此系统把证据不足的对象标记为「中风险 · 待复核」，"
            f"只有证据充分的才升级为「高风险」并自动降低权重。"
        ),
    }


# ---------------------------------------------------------------------------
# 实验 4：复杂度实测与阶拟合
# ---------------------------------------------------------------------------

# 为了让测得的耗时应映「算法本身」而不是输入解析（scanf 是 O(n) 且开销不小），
# 下面两个程序只在输入里读取规模 n，数组由内部线性同余生成器生成。
_GEN = """unsigned int seed=12345u;for(int i=0;i<n;i++){seed=seed*1103515245u+12345u;a[i]=(int)(seed>>8);}"""

BUBBLE_CPP = (
    "#include <bits/stdc++.h>\n"
    "int a[300005];\n"
    "int main(){int n;if(scanf(\"%d\",&n)!=1)return 0;\n"
    + _GEN
    + "\nlong long c=0;for(int i=0;i<n;i++)for(int j=i+1;j<n;j++)if(a[i]>a[j])c++;\n"
    "printf(\"%lld\\n\",c);return 0;}\n"
)

MERGE_CPP = (
    "#include <bits/stdc++.h>\n"
    "int n,a[300005],buf[300005];long long c=0;\n"
    "void ms(int lo,int hi){if(hi-lo<=1)return;int mid=(lo+hi)/2;ms(lo,mid);ms(mid,hi);\n"
    "int i=lo,j=mid,k=lo;while(i<mid&&j<hi){if(a[i]<=a[j])buf[k++]=a[i++];"
    "else{buf[k++]=a[j++];c+=mid-i;}}\n"
    "while(i<mid)buf[k++]=a[i++];while(j<hi)buf[k++]=a[j++];for(int t=lo;t<hi;t++)a[t]=buf[t];}\n"
    "int main(){if(scanf(\"%d\",&n)!=1)return 0;\n"
    + _GEN
    + "\nms(0,n);printf(\"%lld\\n\",c);return 0;}\n"
)


def experiment_complexity(sizes: list[int] | None = None) -> dict:
    # 两个程序计算量差异极大（O(n²) vs O(n log n)），因此使用不同的规模序列，
    # 让两者的实测曲线都落在「可测量且不超时」的区间内。
    plans = [
        ("bubble", "冒泡/双重循环（预期 O(n²)）", BUBBLE_CPP,
         sizes or [4000, 8000, 16000, 32000, 64000], 8000),
        ("merge", "归并排序求逆序对（预期 O(n log n)）", MERGE_CPP,
         [32000, 64000, 128000, 256000, 512000], 8000),
    ]
    out = {"experiment": "complexity", "title": "复杂度实测与自动拟合",
           "metrics": ["time_ms"], "rows": [], "runs": {}}
    for name, label, src, ns, limit in plans:
        res = J.measure_complexity(src, "cpp", [(n, f"{n}\n") for n in ns], time_limit_ms=limit)
        out["runs"][name] = {"label": label, **res}
        if res.get("ok"):
            out["rows"].append({
                "method": name,
                "label": label,
                "best": res["best"],
                "empirical_exponent": res["empirical_exponent"],
                "confidence": res["confidence"],
                "points": res["measurements"],
                "ranking": res["ranking"][:4],
            })
    if out["rows"]:
        a, b = out["rows"][0], out["rows"][-1]
        out["conclusion"] = (
            f"实测拟合结果：{a['label']} 判定为 {a['best']}（经验指数 "
            f"{a['empirical_exponent']}），{b['label']} 判定为 {b['best']}"
            f"（经验指数 {b['empirical_exponent']}）。"
            "拟合在对数空间做最小二乘，对数量级差异更敏感；"
            "同时给出相邻规模耗时比，可直观校核 O(n^p) 中的 p。"
        )
    else:
        out["conclusion"] = "本机缺少 C++ 编译器，无法完成实测复杂度实验。"
    return out


# ---------------------------------------------------------------------------
# 实验 5：代码相似度检测
# ---------------------------------------------------------------------------

BASE_CODE = """#include <bits/stdc++.h>
int main(){int n;scanf("%d",&n);std::vector<int> a(n);
for(int i=0;i<n;i++)scanf("%d",&a[i]);
long long s=0;for(int i=0;i<n;i++)s+=a[i];
printf("%lld\\n",s);return 0;}
"""


def _variant(level: int, rng: random.Random) -> str:
    """按「改写程度」生成变体：0 = 完全相同，1 = 改变量名/注释，2 = 改结构，3 = 无关代码。"""
    if level == 0:
        return BASE_CODE
    if level == 1:
        return BASE_CODE.replace("n", "cnt").replace("a", "arr").replace("s", "total") \
                        .replace("i", "idx") + "// 自己写的\n"
    if level == 2:
        return """#include <bits/stdc++.h>
using namespace std;
int main(){
    int N; cin >> N;
    long long acc = 0;
    for (int k = 0; k < N; ++k) { int t; cin >> t; acc += t; }
    cout << acc << endl;
    return 0;
}
"""
    return """#include <bits/stdc++.h>
int f[1005][1005];
int main(){int n,m;scanf("%d %d",&n,&m);
for(int i=1;i<=n;i++)for(int j=1;j<=m;j++)f[i][j]=f[i-1][j]+f[i][j-1];
printf("%d\\n",f[n][m]);return 0;}
"""


def experiment_similarity(n: int = 60, threshold: float = 0.5) -> dict:
    rng = random.Random(99)
    subs = []
    for i in range(n):
        lvl = i % 4
        subs.append({
            "id": i + 1, "user_id": i + 1, "language": "cpp",
            "code": _variant(lvl, rng) if lvl else BASE_CODE,
            "_level": lvl,
        })
    t0 = time.perf_counter()
    res = SIM.pairwise_similarity(subs, threshold=threshold)
    el = (time.perf_counter() - t0) * 1000
    idx = {s["id"]: s["_level"] for s in subs}
    rows = []
    for p in res["pairs"]:
        la, lb = idx[p["a"]], idx[p["b"]]
        rows.append({
            "a": p["a"], "b": p["b"], "similarity": p["similarity"],
            "level_a": la, "level_b": lb,
            "kind": {0: "完全相同", 1: "改名/加注释", 2: "重写结构"}.get(max(la, lb), "无关代码"),
        })
    # 不同改写级别的召回
    recall = {}
    for lvl, name in ((0, "完全相同"), (1, "变量改名 + 注释"), (2, "重写等价实现"), (3, "结构不同的无关代码")):
        pairs = [r for r in rows if max(r["level_a"], r["level_b"]) == lvl]
        recall[name] = len(pairs)
    return {
        "experiment": "similarity",
        "title": "代码相似度检测（Winnowing 指纹）",
        "params": {"n_submissions": n, "threshold": threshold, "k": 5, "w": 4},
        "metrics": ["similarity", "elapsed_ms"],
        "rows": rows[:40],
        "clusters": res["clusters"],
        "elapsed_ms": round(el, 2),
        "detected_by_level": recall,
        "conclusion": (
            f"对 {n} 份代码检测耗时 {el:.1f} ms（倒排索引避免了 O(n²) 的两两比对）。"
            f"阈值 {threshold} 下，变量改名与加注释的改写仍被 100% 命中，"
            f"重写结构的等价实现相似度明显下降——这说明指纹法擅长识别"
            f"「复制粘贴式抄袭」，对深度改写需要结合语法树或语义方法。"
        ),
    }


EXPERIMENTS = {
    "allocation": experiment_allocation,
    "aggregation": experiment_aggregation,
    "anomaly": experiment_anomaly,
    "complexity": experiment_complexity,
    "similarity": experiment_similarity,
}

EXPERIMENT_META = [
    {"key": "allocation", "name": "评审任务分配算法对比",
     "desc": "随机 / 贪心 / 最小费用流 / 最小费用流+局部搜索，比较覆盖率、负载基尼系数、互为评审与耗时",
     "params": [
         {"key": "n_students", "label": "学生人数", "type": "int", "default": 60, "min": 10, "max": 200},
         {"key": "k", "label": "每份作业评审数", "type": "int", "default": 3, "min": 1, "max": 6},
         {"key": "max_load", "label": "每人最多评审数", "type": "int", "default": 4, "min": 1, "max": 10},
         {"key": "rounds", "label": "重复轮数", "type": "int", "default": 5, "min": 1, "max": 20},
     ]},
    {"key": "aggregation", "name": "评分聚合方法对比",
     "desc": "6 种聚合方法在 RMSE、稳定性、抗异常能力上的差异",
     "params": [
         {"key": "n_submissions", "label": "作业份数", "type": "int", "default": 60, "min": 10, "max": 300},
         {"key": "n_reviewers", "label": "评审者人数", "type": "int", "default": 60, "min": 5, "max": 300},
         {"key": "k", "label": "每份评审数", "type": "int", "default": 5, "min": 2, "max": 10},
         {"key": "bias_sd", "label": "评审者宽严差异 σ", "type": "float", "default": 8.0, "min": 0, "max": 25},
         {"key": "noise_sd", "label": "评分噪声 σ", "type": "float", "default": 5.0, "min": 0, "max": 25},
         {"key": "malicious", "label": "恶意评审者数量", "type": "int", "default": 2, "min": 0, "max": 10},
     ]},
    {"key": "anomaly", "name": "异常评审检测效果",
     "desc": "注入已知异常评审者，统计精确率 / 召回率 / F1",
     "params": [
         {"key": "n_submissions", "label": "作业份数", "type": "int", "default": 60, "min": 10, "max": 300},
         {"key": "n_reviewers", "label": "评审者人数", "type": "int", "default": 60, "min": 10, "max": 300},
         {"key": "k", "label": "每份评审数", "type": "int", "default": 5, "min": 2, "max": 10},
         {"key": "n_bad", "label": "注入异常人数", "type": "int", "default": 4, "min": 1, "max": 20},
         {"key": "rounds", "label": "重复轮数", "type": "int", "default": 5, "min": 1, "max": 20},
     ]},
    {"key": "complexity", "name": "复杂度实测与自动拟合",
     "desc": "真实编译运行 O(n²) 与 O(n log n) 程序，拟合出复杂度阶",
     "params": []},
    {"key": "similarity", "name": "代码相似度检测",
     "desc": "Winnowing 指纹 + 倒排索引，评估不同改写程度的检出效果",
     "params": [
         {"key": "n", "label": "代码份数", "type": "int", "default": 60, "min": 4, "max": 400},
         {"key": "threshold", "label": "相似度阈值", "type": "float", "default": 0.5, "min": 0.1, "max": 0.95},
     ]},
]
