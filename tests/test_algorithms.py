"""核心算法单元测试（只用标准库，直接 ``python tests/run_tests.py`` 运行）。

覆盖范围：
* 最小费用最大流与暴力最优解一致；
* 互评分配满足全部硬约束，并在公平性指标上优于随机基线；
* 评分聚合的 6 种方法行为正确，EM 在存在评审偏差时显著优于算术平均；
* 异常检测能召回注入的异常评审者；
* IRT / ELO 能恢复模拟真值的排序；
* 相似度检测对「完全相同」「变量改名」都给出高相似度，对无关代码给出低相似度；
* 复杂度拟合能识别 O(n)、O(n log n)、O(n²)；
* 评测引擎的输出比较规则（空白、浮点误差）。
"""

from __future__ import annotations

import itertools
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import judge as J  # noqa: E402
from backend.algo import ability as AB  # noqa: E402
from backend.algo import aggregation as AG  # noqa: E402
from backend.algo import anomaly as AN  # noqa: E402
from backend.algo import assignment as AS  # noqa: E402
from backend.algo import complexity as CX  # noqa: E402
from backend.algo import similarity as SIM  # noqa: E402
from backend.algo.flow import MinCostMaxFlow, min_cost_assignment  # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  \u2713 {name}")
    else:
        FAIL += 1
        print(f"  \u2717 {name}  {detail}")


def section(title):
    print("\n" + title)


# ---------------------------------------------------------------- 1. 流


def test_flow():
    section("[1] 最小费用最大流")
    net = MinCostMaxFlow(4)
    net.add_edge(0, 1, 2, 1)
    net.add_edge(0, 2, 1, 3)
    net.add_edge(1, 3, 2, 2)
    net.add_edge(2, 3, 1, 1)
    flow, cost, _ = net.solve(0, 3)
    check("流量正确", flow == 3, f"flow={flow}")
    # 路径：0→1(容量2,费用1) → 1→3(费用2)；0→2(容量1,费用3) → 2→3(费用1)
    # 总费用 = 2*1 + 2*2 + 1*3 + 1*1 = 10
    check("费用最小（2*1+2*2+1*3+1*1=10）", cost == 10, f"cost={cost}")

    # 与暴力枚举对照最小费用完美匹配
    rng = random.Random(7)
    rows = cols = 6
    mat = [[rng.randint(1, 30) for _ in range(cols)] for _ in range(rows)]
    matching, cost = min_cost_assignment(mat)
    brute = min(
        sum(mat[i][p[i]] for i in range(rows)) for p in itertools.permutations(range(cols))
    )
    check("最小费用匹配与暴力一致", abs(cost - brute) < 1e-6, f"{cost} vs {brute}")
    check("匹配是置换", sorted(matching) == list(range(cols)), str(matching))


# ---------------------------------------------------------------- 2. 分配


def test_assignment():
    section("[2] 互评任务分配")
    n = 40
    authors = list(range(1, n + 1))
    klass = {i: ("A" if i <= n // 2 else "B") for i in authors}
    params = AS.AllocationParams(reviews_per_submission=3, max_load=4, seed=11)
    res = AS.allocate_mcmf(authors, authors, klass, params, prev_pairs={})
    m = AS.evaluate_allocation(res.allocations, authors, authors, klass, {}, 3)

    check("覆盖率 100%", m["coverage"] >= 1.0, str(m["coverage"]))
    check("禁止自评", m["self_review"] == 0, str(m["self_review"]))
    check("工作量不超过上限", m["load_max"] <= params.max_load, str(m["load_max"]))
    check("负载完全均衡（基尼=0）", m["gini_load"] == 0, str(m["gini_load"]))
    check("无互为评审", m["reciprocal_pairs"] == 0, str(m["reciprocal_pairs"]))

    rand = AS.allocate_random(authors, authors, klass, params)
    mr = AS.evaluate_allocation(rand.allocations, authors, authors, klass, {}, 3)
    check("公平性优于随机基线", m["gini_load"] <= mr["gini_load"] and m["reciprocal_pairs"] <= mr["reciprocal_pairs"],
          f"gini {m['gini_load']} vs {mr['gini_load']}")

    # 局部搜索不应让目标函数变差
    p2 = AS.AllocationParams(reviews_per_submission=3, max_load=4, seed=5)
    mcmf_only = AS.allocate_mcmf(authors, authors, klass,
                                 AS.AllocationParams(**{**p2.__dict__, "use_local_search": False}))
    obj_before = AS._objective(mcmf_only.allocations, klass, {}, p2)
    obj_after = AS._objective(res.allocations, klass, {}, p2)
    check("局部搜索降低目标函数", obj_after <= obj_before + 1e-9, f"{obj_before} -> {obj_after}")

    # 历史重复互评惩罚应减少重复
    prev = {(a, r): 2 for a in authors for r in authors if a != r and (a * r) % 7 == 0}
    res2 = AS.allocate_mcmf(authors, authors, klass, params, prev_pairs=prev)
    m2 = AS.evaluate_allocation(res2.allocations, authors, authors, klass, prev, 3)
    res3 = AS.allocate_random(authors, authors, klass, params, prev)
    m3 = AS.evaluate_allocation(res3.allocations, authors, authors, klass, prev, 3)
    check("重复互评少于随机基线", m2["repeat_pairs"] < m3["repeat_pairs"],
          f"{m2['repeat_pairs']} vs {m3['repeat_pairs']}")


# ---------------------------------------------------------------- 3. 聚合


def _sim_reviews(n_sub, n_rev, k, bias_sd, noise_sd, malicious=0, seed=3):
    rng = random.Random(seed)
    truth = {s: 60 + 15 * rng.gauss(0, 1) for s in range(1, n_sub + 1)}
    bias = {r: rng.gauss(0, bias_sd) for r in range(1, n_rev + 1)}
    reviews = []
    for s in range(1, n_sub + 1):
        for r in rng.sample(range(1, n_rev + 1), k):
            reviews.append({
                "submission_id": s, "reviewer_id": r, "author_id": s,
                "score": max(0.0, min(100.0, truth[s] + bias[r] + rng.gauss(0, noise_sd))),
                "duration_sec": rng.randint(120, 900),
            })
    for i in range(malicious):
        rv = 900 + i
        for s in range(1, n_sub + 1):
            reviews.append({
                "submission_id": s, "reviewer_id": rv, "author_id": s,
                "score": 99.0 if i % 2 == 0 else 15.0, "duration_sec": 20,
            })
    return reviews, truth


def _rmse(scores, truth):
    vals = [(scores[s] - t) ** 2 for s, t in truth.items() if s in scores]
    return math.sqrt(sum(vals) / len(vals)) if vals else 0.0


def test_aggregation():
    section("[3] 评分聚合")
    reviews, truth = _sim_reviews(60, 60, 5, 8, 5, malicious=2)
    res = {m: AG.aggregate(reviews, m) for m in AG.METHODS}
    check("所有方法都给出全部作业分数",
          all(len(v["scores"]) == 60 for v in res.values()))
    check("分数落在合理区间",
          all(0 <= s <= 100 for v in res.values() for s in v["scores"].values()))

    em = _rmse(res["reliability_em"]["scores"], truth)
    mean = _rmse(res["mean"]["scores"], truth)
    check("EM 精度优于算术平均", em < mean, f"EM={em:.3f} mean={mean:.3f}")
    check("EM 相对提升 > 30%", (mean - em) / mean > 0.3, f"{(mean - em) / mean:.3f}")

    trimmed = _rmse(res["trimmed_mean"]["scores"], truth)
    check("EM 精度优于截尾平均", em < trimmed, f"EM={em:.3f} trimmed={trimmed:.3f}")

    detail = res["reliability_em"]["detail"]
    check("估计出评审者偏差", len(detail["bias"]) == 62)
    check("估计出可信度权重", len(detail["reliability"]) == 62)
    bad_w = detail["reliability"].get(900, 1.0)
    normal_w = [v for k, v in detail["reliability"].items() if k < 900]
    check("恶意评审者权重被下调",
          bad_w < sum(normal_w) / len(normal_w), f"bad={bad_w:.2f}")
    check("权重被裁剪到 [0.25, 3]", all(0.25 <= v <= 3 for v in detail["reliability"].values()))

    st = AG.bootstrap_stability(reviews, "mean", rounds=10)
    check("留一稳定性可计算", st["rounds"] > 0 and st["mad"] >= 0)

    # 干净数据上 EM 不应明显变差
    clean, clean_truth = _sim_reviews(60, 60, 5, 0, 4, seed=9)
    em2 = _rmse(AG.aggregate(clean, "reliability_em")["scores"], clean_truth)
    mean2 = _rmse(AG.aggregate(clean, "mean")["scores"], clean_truth)
    check("无偏差数据上 EM 与平均基本持平", em2 < mean2 * 1.15, f"EM={em2:.3f} mean={mean2:.3f}")


# ---------------------------------------------------------------- 4. 异常


def test_anomaly():
    section("[4] 异常评审检测")
    n_sub, n_rev, k, n_bad = 60, 60, 5, 4
    kinds = set()
    last_stats = {}
    last_det = {}
    for seed in (7, 8, 9):
        rng = random.Random(seed)
        truth = {s: 60 + 15 * rng.gauss(0, 1) for s in range(1, n_sub + 1)}
        bad = set(rng.sample(range(1, n_rev + 1), n_bad))
        bias = {i: (rng.choice([-18, 18]) if i in bad else rng.gauss(0, 3))
                for i in range(1, n_rev + 1)}
        noise = {i: (1.0 if i in bad else abs(rng.gauss(3.5, 1)) + 1)
                 for i in range(1, n_rev + 1)}
        reviews = []
        for s in range(1, n_sub + 1):
            for rv in rng.sample(range(1, n_rev + 1), k):
                reviews.append({
                    "submission_id": s, "reviewer_id": rv, "author_id": s,
                    "score": max(0.0, min(100.0, truth[s] + bias[rv] + rng.gauss(0, noise[rv]))),
                    "duration_sec": (25.0 if rv in bad else rng.gauss(420, 110)),
                    "rubric": {"idea": 20, "complexity": 15, "correctness": 15, "writing": 10},
                })
        det = AN.detect(reviews)
        last_det = det
        last_stats = det["reviewer_stats"]
        kinds |= {a["type"] for a in det["anomalies"]}
    # 直接复用实验台使用的评估流程（5 轮注入实验），保证与文档中的指标口径一致
    from backend import experiments as EX

    exp = EX.experiment_anomaly(rounds=5)
    row = exp["rows"][0]
    check("异常检测 F1 ≥ 0.6（5 轮注入实验）", row["f1"] >= 0.6,
          f"P={row['precision']} R={row['recall']} F1={row['f1']}")
    check("异常检测召回率 ≥ 0.7", row["recall"] >= 0.7, str(row["recall"]))
    check("检出长期偏差", "reviewer_bias" in kinds, str(kinds))
    check("检出异常时长", "duration_anomaly" in kinds, str(kinds))
    check("审查者统计完整", len(last_stats) == n_rev)
    check("关系图有节点与边",
          last_det["graph"]["n_nodes"] > 0 and last_det["graph"]["n_edges"] > 0)
    check("EM 的标准差估计为正", (last_det["sigma"] or 0) > 0)
    pair = [
        {"submission_id": 1, "reviewer_id": 2, "author_id": 1, "score": 95.0},
        {"submission_id": 2, "reviewer_id": 1, "author_id": 2, "score": 94.0},
    ]
    g = AN.detect(pair)["graph"]
    check("关系图识别双向互评", len(g["reciprocal"]) == 1, str(g["reciprocal"]))
    rel = AN._relation_anomalies(g, pair)
    check("双向高分被标记为固定互评关系",
          any(x["type"] == "reciprocal_pair" for x in rel), str(rel))


# ---------------------------------------------------------------- 5. 能力


def test_ability():
    section("[5] 学生能力与题目难度")
    rng = random.Random(11)
    users, probs = list(range(1, 61)), list(range(1, 16))
    tt = {u: rng.gauss(0, 1) for u in users}
    tb = {p: rng.gauss(0, 1.1) for p in probs}
    res = []
    for u in users:
        for p in probs:
            pr = 1 / (1 + math.exp(-1.2 * (tt[u] - tb[p])))
            res.append({"user_id": u, "problem_id": p, "score": 1.0 if rng.random() < pr else 0.0})

    def corr(x, y):
        n = len(x)
        mx, my = sum(x) / n, sum(y) / n
        sx = math.sqrt(sum((a - mx) ** 2 for a in x))
        sy = math.sqrt(sum((b - my) ** 2 for b in y))
        return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)

    irt = AB.irt_2pl(res)
    c_theta = corr([irt["theta"][u] for u in users], [tt[u] for u in users])
    c_b = corr([irt["b"][p] for p in probs], [tb[p] for p in probs])
    check("1PL 恢复学生能力（相关 > 0.8）", c_theta > 0.8, f"{c_theta:.3f}")
    check("1PL 恢复题目难度（相关 > 0.9）", c_b > 0.9, f"{c_b:.3f}")
    check("迭代次数有限", irt["iters"] < 1500, str(irt["iters"]))

    elo = AB.elo_update(res, rounds=30)
    c_elo = corr([elo["rating"][u] for u in users], [tt[u] for u in users])
    check("ELO 也能恢复能力排序（相关 > 0.8）", c_elo > 0.8, f"{c_elo:.3f}")

    diff = AB.difficulty_report(res, irt)
    check("难度报告包含全部题目", len(diff) == len(probs))
    check("难度标签合法",
          all(v["label"] in ("简单", "较易", "适中", "较难", "很难") for v in diff.values()))


# ---------------------------------------------------------------- 6. 相似度


def test_similarity():
    section("[6] 代码相似度检测")
    base = (
        "int main(){int n;scanf(\"%d\",&n);int s=0;for(int i=1;i<=n;i++)s+=i;"
        "printf(\"%d\\n\",s);return 0;}"
    )
    renamed = (
        "int main(){/* 求和 */ int cnt;scanf(\"%d\",&cnt);int total=0;\n"
        "for(int k=1;k<=cnt;k++){total+=k;}printf(\"%d\\n\",total);return 0;}"
    )
    other = (
        "#include <vector>\nint main(){int n;scanf(\"%d\",&n);std::vector<int> a(n);"
        "for(int i=0;i<n;i++)scanf(\"%d\",&a[i]);printf(\"%d\",a[0]);return 0;}"
    )
    subs = [
        {"id": 1, "user_id": 1, "language": "cpp", "code": base},
        {"id": 2, "user_id": 2, "language": "cpp", "code": base},
        {"id": 3, "user_id": 3, "language": "cpp", "code": renamed},
        {"id": 4, "user_id": 4, "language": "cpp", "code": other},
    ]
    res = SIM.pairwise_similarity(subs, threshold=0.5)
    pairs = {(p["a"], p["b"]): p["similarity"] for p in res["pairs"]}
    check("完全相同代码相似度 = 1", pairs.get((1, 2), 0) > 0.99, str(pairs.get((1, 2), 0)))
    check("变量改名仍被判为高相似", pairs.get((1, 3), pairs.get((2, 3), 0)) > 0.5,
          str(pairs.get((1, 3), pairs.get((2, 3), 0))))
    check("无关代码不误报", (1, 4) not in pairs and (2, 4) not in pairs)
    check("形成相似簇", any(len(c) >= 2 for c in res["clusters"]), str(res["clusters"]))

    toks = SIM.normalize_source("int a = 1; // 注释\n", "cpp")
    check("规范化去掉注释与数字", "//" not in " ".join(toks))


# ---------------------------------------------------------------- 7. 复杂度


def test_complexity():
    section("[7] 复杂度自动判定")
    cases = [
        ("O(1)", [1.0] * 6, 0.4),
        ("O(n)", [1, 2, 4, 8, 16, 32], 3.0),
        ("O(n log n)", [n * math.log2(n) * 0.02 for n in (1000, 2000, 4000, 8000, 16000)], 2.0),
        ("O(n²)", [n * n * 1e-5 for n in (100, 200, 400, 800, 1600)], 2.0),
    ]
    for expect, times, noise in cases:
        sizes = [100, 200, 400, 800, 1600, 3200][: len(times)]
        pts = [{"n": n, "time_ms": max(0.01, t)} for n, t in zip(sizes, times)]
        fit = CX.fit_complexity(pts)
        check(f"识别 {expect}", fit["best"] == expect, f"得到 {fit['best']}")
    short = CX.fit_complexity([{"n": 1, "time_ms": 1}])
    check("采样点不足时给出提示", short["ok"] is False)


# ---------------------------------------------------------------- 8. 评测


def test_judge():
    section("[8] 评测引擎")
    check("忽略行尾空白", J.outputs_match("1 2\n", "1  2 "))
    check("忽略多余空行", J.outputs_match("3\n", "\n3\n\n"))
    check("浮点允许 1e-6 误差", J.outputs_match("0.333333", "0.3333334"))
    check("数值不同判为不匹配", not J.outputs_match("1 2", "1 3"))
    check("token 数量不同判为不匹配", not J.outputs_match("1 2 3", "1 2"))
    check("空期望输出视为通过", J.outputs_match("", ""))
    langs = J.available_languages()
    check("至少探测到一种语言", any(l["available"] for l in langs),
          str([l["key"] for l in langs if l["available"]]))
    check("静态检查能发现可疑调用", "system(" in J.static_check("int main(){system(\"ls\");}", "cpp"))


# ---------------------------------------------------------------- main


def main() -> int:
    print("=" * 64)
    print("AlgorithmLab · 核心算法单元测试")
    print("=" * 64)
    for fn in (
        test_flow, test_assignment, test_aggregation, test_anomaly,
        test_ability, test_similarity, test_complexity, test_judge,
    ):
        fn()
    print("\n" + "=" * 64)
    print(f"通过 {PASS} 项，失败 {FAIL} 项")
    print("=" * 64)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
