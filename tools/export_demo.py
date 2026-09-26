"""把数据库快照导出为前端可直接使用的 ``frontend/demo/dataset.json``。

用途：GitHub Pages 等纯静态托管环境没有 Python 后端，前端会进入「演示模式」，
由 ``frontend/js/demo/demo-api.js`` 从这个 JSON 提供数据（只读）。

运行：``python tools/export_demo.py``
"""

from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend import db, experiments as EX, judge as J  # noqa: E402

OUT = os.path.join(ROOT, "frontend", "demo", "dataset.json")


def rows(sql, args=()):
    return db.rows2dicts(db.q(sql, args))


def build() -> dict:
    course = db.q1("SELECT * FROM courses ORDER BY id LIMIT 1")
    cid = course["id"]
    teachers = rows("SELECT id,name,email,role,class_name,student_no FROM users WHERE role<>'student'")
    students = rows(
        "SELECT u.id,u.name,u.student_no,u.class_name,u.username FROM course_members m "
        "JOIN users u ON u.id=m.user_id WHERE m.course_id=? AND m.role='student' ORDER BY u.id",
        (cid,),
    )
    problems = rows("SELECT * FROM problems WHERE course_id=? ORDER BY id", (cid,))
    assignments = rows("SELECT * FROM assignments WHERE course_id=? ORDER BY id DESC", (cid,))
    submissions = rows(
        "SELECT s.id,s.assignment_id,s.problem_id,s.user_id,s.language,s.verdict,s.score,s.time_ms,"
        "s.memory_kb,s.attempt_no,s.submitted_at,s.detail,u.name AS user_name,u.class_name,"
        "p.title AS problem_title FROM submissions s JOIN problems p ON p.id=s.problem_id "
        "JOIN users u ON u.id=s.user_id ORDER BY s.id DESC LIMIT 400"
    )
    # 只保留少量源码，避免演示包过大
    codes = {
        r["id"]: r["source_code"]
        for r in rows("SELECT id,source_code FROM submissions ORDER BY id DESC LIMIT 60")
    }
    for s in submissions:
        s["source_code"] = codes.get(s["id"], "")
        s["detail"] = db.jloads(s.get("detail"), {})
        s["detail"].pop("results", None)
    subjective = rows(
        "SELECT ss.*,p.title AS problem_title,a.title AS assignment_title FROM subjective_submissions ss "
        "JOIN problems p ON p.id=ss.problem_id JOIN assignments a ON a.id=ss.assignment_id ORDER BY ss.id"
    )
    for s in subjective:
        s["content"] = {k: v for k, v in db.jloads(s["content"], {}).items() if not k.startswith("_")}
        s["methods"] = db.jloads(s["methods"], {})
    allocations = rows(
        "SELECT al.*,au.name AS author_name,au.class_name AS author_class,rv.name AS reviewer_name,"
        "rv.class_name AS reviewer_class FROM allocations al JOIN users au ON au.id=al.author_id "
        "JOIN users rv ON rv.id=al.reviewer_id ORDER BY al.id LIMIT 1200"
    )
    reviews = rows("SELECT * FROM reviews ORDER BY id LIMIT 1200")
    for r in reviews:
        r["scores"] = db.jloads(r["scores"], {})
    anomalies = rows(
        "SELECT an.*,u.name AS reviewer_name,u.class_name FROM anomalies an "
        "LEFT JOIN users u ON u.id=an.reviewer_id ORDER BY an.id"
    )
    for a in anomalies:
        a["evidence"] = db.jloads(a["evidence"], {})
    notices = rows("SELECT * FROM notices ORDER BY id DESC")
    events = rows(
        "SELECT user_id,type,COUNT(*) c FROM events WHERE course_id=? GROUP BY user_id,type", (cid,)
    )
    return {
        "generated_at": db.now(),
        "meta": {
            "languages": J.available_languages(),
            "verdicts": J.VERDICT_FULL,
            "aggregation_methods": [
                {"key": m, "label": __import__("backend.algo.aggregation", fromlist=["x"]).METHOD_LABELS[m]}
                for m in ["mean", "median", "trimmed_mean", "weighted_mean", "robust_huber", "reliability_em"]
            ],
            "allocation_methods": [
                {"key": "random", "label": "随机分配（基线）"},
                {"key": "greedy", "label": "贪心负载均衡（基线）"},
                {"key": "mcmf", "label": "最小费用最大流"},
                {"key": "mcmf+ls", "label": "最小费用流 + 局部搜索"},
            ],
            "experiments": EX.EXPERIMENT_META,
            "problem_types": [
                {"key": "programming", "label": "编程题"},
                {"key": "analysis", "label": "算法分析题"},
                {"key": "proof", "label": "证明题"},
                {"key": "open", "label": "开放性问答题"},
            ],
        },
        "course": dict(course),
        "teachers": teachers,
        "students": students,
        "problems": problems,
        "assignments": assignments,
        "submissions": submissions,
        "subjective": subjective,
        "allocations": allocations,
        "reviews": reviews,
        "anomalies": anomalies,
        "notices": notices,
        "events": events,
    }


def build_experiments() -> dict:
    """预计算 5 组实验结果（静态站点不能真的编译运行 C++）。"""
    out = {}
    for key, fn in (
        ("allocation", EX.experiment_allocation),
        ("aggregation", EX.experiment_aggregation),
        ("anomaly", EX.experiment_anomaly),
        ("similarity", EX.experiment_similarity),
    ):
        t0 = time.perf_counter()
        try:
            res = fn()
            res["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            out[key] = res
        except Exception as e:  # pragma: no cover
            print("  跳过", key, e)
    return out


def main() -> None:
    db.init_db()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    data = build()
    data["experiments_cache"] = build_experiments()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    size = os.path.getsize(OUT) / 1024 / 1024
    print(f"已导出 {OUT}（{size:.2f} MB）")
    print(
        f"  题目 {len(data['problems'])} · 作业 {len(data['assignments'])} · "
        f"提交 {len(data['submissions'])} · 评审 {len(data['reviews'])} · 异常 {len(data['anomalies'])}"
    )


if __name__ == "__main__":
    main()
