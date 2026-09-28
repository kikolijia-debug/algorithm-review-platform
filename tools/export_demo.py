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
    # 静态演示模式下前端要据此还原「作业包含哪些题」，所以随作业一起导出
    ap_rows = rows(
        "SELECT ap.assignment_id, ap.problem_id FROM assignment_problems ap "
        "JOIN assignments a ON a.id=ap.assignment_id WHERE a.course_id=? "
        "ORDER BY ap.assignment_id, ap.order_index",
        (cid,),
    )
    ap_map: dict = {}
    for r in ap_rows:
        ap_map.setdefault(r["assignment_id"], []).append(r["problem_id"])
    for a in assignments:
        a["problem_ids"] = json.dumps(ap_map.get(a["id"], []))
    # 每个作业各取最近若干条（而不是只取全局最新的几百条），
    # 否则静态演示里点开旧作业会看到「全班都没交」。
    base_sql = (
        "SELECT s.id,s.assignment_id,s.problem_id,s.user_id,s.language,s.verdict,s.score,s.time_ms,"
        "s.memory_kb,s.attempt_no,s.submitted_at,s.detail,u.name AS user_name,u.class_name,"
        "p.title AS problem_title FROM submissions s JOIN problems p ON p.id=s.problem_id "
        "JOIN users u ON u.id=s.user_id "
    )
    submissions: list = []
    for a in assignments:
        submissions += rows(base_sql + "WHERE s.assignment_id=? ORDER BY s.id DESC LIMIT 60", (a["id"],))
    submissions += rows(base_sql + "WHERE s.assignment_id IS NULL ORDER BY s.id DESC LIMIT 40")
    seen_ids = set()
    submissions = [s for s in submissions if not (s["id"] in seen_ids or seen_ids.add(s["id"]))]
    submissions.sort(key=lambda r: -r["id"])
    # 只保留少量源码，避免演示包过大
    codes = {
        r["id"]: r["source_code"]
        for r in rows("SELECT id,source_code FROM submissions ORDER BY id DESC LIMIT 120")
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
    # 课件库与章节结构：静态演示模式下「课程资源」页直接读这两个字段
    materials = rows(
        "SELECT id,chapter,chapter_title,title,filename,url,size_bytes,pages,topics,summary,"
        "order_index FROM materials WHERE course_id=? ORDER BY chapter,order_index,id",
        (cid,),
    )
    for m in materials:
        m["topics"] = db.jloads(m.get("topics"), [])
    from backend import courseware as CW

    chapters = [
        {
            "key": c["key"], "no": c["no"], "title": c["title"],
            "label": f"{c['no']} {c['title']}", "topic": c["topic"],
            "summary": c["summary"], "topics": c["topics"],
        }
        for c in CW.CHAPTERS
    ]
    course_dict = dict(course)
    course_dict["homepage"] = CW.COURSE_HOMEPAGE
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
        "course": course_dict,
        "chapters": chapters,
        "materials": materials,
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
    # 在 CI（或全新克隆）环境下数据库是空的，需要先灌一遍演示数据
    if db.is_empty():
        from backend import seed as seedmod

        print("检测到空数据库，先生成演示数据 ...")
        seedmod.seed(reset=True, verbose=True)
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
