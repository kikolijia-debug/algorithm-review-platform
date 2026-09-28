"""扩展接口：学习过程分析、异常处理、算法实验台、相似度检测与首页看板。

本模块在导入时把路由注册到 ``api.ROUTES``，由 ``server.py`` 统一分发。
所有计算都直接调用 ``backend/algo`` 中的算法实现，不使用模拟结果。
"""

from __future__ import annotations

import time
from datetime import datetime

from . import db, experiments as EX
from .algo import ability as AB
from .algo import similarity as SIM
from .api import (
    active_course_id, anon_label, err, is_teacher, jload, ok, parse_dt, public_user, route,
    uid_rows,
)


def _hist(values, nbins=10):
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [{"x": round(lo, 2), "x2": round(hi, 2), "count": len(values)}]
    n = max(1, min(nbins, int(len(set(values)))))
    step = (hi - lo) / n
    bins = [0] * n
    for v in values:
        bins[min(n - 1, int((v - lo) / step))] += 1
    return [{"x": round(lo + i * step, 2), "x2": round(lo + (i + 1) * step, 2), "count": c}
            for i, c in enumerate(bins)]


def _stats(values):
    if not values:
        return {"n": 0}
    v = sorted(values)
    n = len(v)
    mean = sum(v) / n
    std = (sum((x - mean) ** 2 for x in v) / n) ** 0.5
    return {
        "n": n, "min": round(v[0], 2), "max": round(v[-1], 2), "mean": round(mean, 2),
        "median": round(v[n // 2], 2), "std": round(std, 2),
        "p95": round(v[min(n - 1, int(0.95 * n))], 2),
    }


def _first_course(ctx):
    """当前账号的活动课程（教师=自己的课，学生=已加入的课）。"""
    return active_course_id(ctx, ctx["query"].get("course_id"))


# ---------------------------------------------------------------------------
# 班级 / 题目 / 学生分析
# ---------------------------------------------------------------------------


@route("GET", "/api/assignments/{id}/progress", "teacher")
def api_assignment_progress(ctx):
    """单个作业里每位学生的完成情况。

    教师进入某次作业后需要一眼看到：谁交了、交了几次、过没过、拿了几分、
    主观题答了没有、互评拿了多少分，并且能点开看具体的提交内容。
    """
    aid = int(ctx["params"]["id"])
    a = db.q1("SELECT * FROM assignments WHERE id=?", (aid,))
    if not a:
        return err(404, "作业不存在")
    problems = uid_rows(
        "SELECT p.id,p.title,p.type,p.difficulty,p.score FROM assignment_problems ap "
        "JOIN problems p ON p.id=ap.problem_id WHERE ap.assignment_id=? ORDER BY ap.order_index",
        (aid,))
    students = uid_rows(
        "SELECT u.id,u.name,u.student_no,u.class_name FROM course_members m "
        "JOIN users u ON u.id=m.user_id WHERE m.course_id=? AND m.role='student' "
        "ORDER BY u.class_name, u.student_no, u.id", (a["course_id"],))

    # 编程题：每人每题的最高分 / 提交次数 / 是否通过 / 最近一次提交
    prog = uid_rows(
        "SELECT s.user_id, s.problem_id, COUNT(*) tries, MAX(s.score) best, "
        "MAX(CASE WHEN s.verdict='Accepted' THEN 1 ELSE 0 END) solved, "
        "MAX(s.id) last_id FROM submissions s WHERE s.assignment_id=? "
        "GROUP BY s.user_id, s.problem_id", (aid,))
    # 没有挂作业的历史提交（教师手动组织的代码互评）按题目兜底
    prog_all = uid_rows(
        "SELECT s.user_id, s.problem_id, COUNT(*) tries, MAX(s.score) best, "
        "MAX(CASE WHEN s.verdict='Accepted' THEN 1 ELSE 0 END) solved, MAX(s.id) last_id "
        "FROM submissions s GROUP BY s.user_id, s.problem_id")
    last_rows = {r["id"]: r for r in uid_rows(
        "SELECT id,verdict,language,submitted_at,time_ms,memory_kb FROM submissions "
        "WHERE assignment_id=?", (aid,))}
    if not last_rows:
        last_rows = {r["id"]: r for r in uid_rows(
            "SELECT id,verdict,language,submitted_at,time_ms,memory_kb FROM submissions")}
    subj = uid_rows(
        "SELECT ss.user_id, ss.problem_id, ss.status, ss.final_score, ss.submitted_at, ss.methods "
        "FROM subjective_submissions ss WHERE ss.assignment_id=?", (aid,))
    reviews = uid_rows(
        "SELECT rv.author_id, rv.problem_id, rv.total FROM reviews rv "
        "WHERE rv.assignment_id=?", (aid,))

    prog_map = {}
    for r in prog:
        prog_map[(r["user_id"], r["problem_id"])] = r
    for r in prog_all:
        prog_map.setdefault((r["user_id"], r["problem_id"]), r)
    subj_map = {(r["user_id"], r["problem_id"]): r for r in subj}
    review_sum, review_cnt = {}, {}
    for r in reviews:
        key = (r["author_id"], r["problem_id"])
        review_sum[key] = review_sum.get(key, 0.0) + (r["total"] or 0)
        review_cnt[key] = review_cnt.get(key, 0) + 1

    full = sum(p["score"] or 100 for p in problems)
    rows = []
    for st in students:
        cells, tries, solved, score = {}, 0, 0, 0.0
        for p in problems:
            key = (st["id"], p["id"])
            pr, sj = prog_map.get(key), subj_map.get(key)
            cell = {"problem_id": p["id"], "type": p["type"], "tries": 0, "solved": False,
                    "best": None, "verdict": None, "submitted": False,
                    "submission_id": None, "subjective_id": None, "review_score": None}
            if pr:
                cell.update({"tries": pr["tries"], "solved": bool(pr["solved"]),
                             "best": pr["best"], "submitted": True,
                             "submission_id": pr["last_id"]})
                last = last_rows.get(pr["last_id"]) or {}
                cell["verdict"] = last.get("verdict")
                cell["language"] = last.get("language")
                cell["time_ms"] = last.get("time_ms")
                cell["memory_kb"] = last.get("memory_kb")
                cell["submitted_at"] = last.get("submitted_at")
                tries += pr["tries"]
                solved += 1 if pr["solved"] else 0
                score += pr["best"] or 0
            if sj:
                cell.update({"submitted": True, "subjective_id": sj["problem_id"],
                             "subjective_status": sj["status"],
                             "review_score": sj["final_score"],
                             "submitted_at": cell.get("submitted_at") or sj["submitted_at"]})
                if not pr:
                    tries += 1
                    score += sj["final_score"] or 0
            if review_cnt.get(key):
                cell["review_score"] = round(review_sum[key] / review_cnt[key], 1)
                cell["review_count"] = review_cnt[key]
            cells[str(p["id"])] = cell
        rows.append({
            "user_id": st["id"], "name": st["name"], "student_no": st["student_no"],
            "class_name": st["class_name"], "cells": cells,
            "submitted_problems": sum(1 for c in cells.values() if c["submitted"]),
            "solved_problems": solved, "tries": tries, "score": round(score, 1),
            "score_rate": round(score / full, 4) if full else 0,
        })
    rows.sort(key=lambda r: (-r["score"], r["name"]))
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return ok({
        "assignment": {
            "id": a["id"], "title": a["title"], "description": a["description"],
            "type": a["type"], "peer_review": a["peer_review"], "status": a["status"],
            "allocation_status": (a["allocation_status"] if "allocation_status" in a.keys()
                                  else "confirmed") or "confirmed",
            "due_at": a["due_at"], "review_due_at": a["review_due_at"],
            "reviews_per_submission": a["reviews_per_submission"],
            "max_load": a["max_load"], "aggregation_method": a["aggregation_method"],
        },
        "problems": problems,
        "students": rows,
        "full_score": full,
        "stats": {
            "students": len(rows),
            "submitted_all": sum(1 for r in rows if r["submitted_problems"] == len(problems)),
            "none": sum(1 for r in rows if r["submitted_problems"] == 0),
            "passed_all": sum(1 for r in rows if r["solved_problems"] == len(
                [p for p in problems if p["type"] == "programming"])),
            "avg_score": round(sum(r["score"] for r in rows) / len(rows), 1) if rows else 0,
        },
    })


@route("GET", "/api/analytics/class")
def api_analytics_class(ctx):
    course_id = _first_course(ctx)
    assignment_id = ctx["query"].get("assignment_id")
    if not course_id:
        return ok({})
    where, args = "WHERE p.course_id=?", [course_id]
    if assignment_id:
        where += " AND s.assignment_id=?"
        args.append(assignment_id)
    total = db.q1(
        "SELECT COUNT(*) c FROM submissions s JOIN problems p ON p.id=s.problem_id " + where,
        args)["c"]
    ac = db.q1(
        "SELECT COUNT(*) c FROM submissions s JOIN problems p ON p.id=s.problem_id " + where
        + " AND s.verdict='Accepted'", args)["c"]
    students = db.q1(
        "SELECT COUNT(*) c FROM course_members WHERE course_id=? AND role='student'",
        (course_id,))["c"]
    active = db.q1(
        "SELECT COUNT(DISTINCT s.user_id) c FROM submissions s JOIN problems p ON p.id=s.problem_id "
        + where, args)["c"]
    verdicts = uid_rows(
        "SELECT s.verdict, COUNT(*) c FROM submissions s JOIN problems p ON p.id=s.problem_id "
        + where + " GROUP BY s.verdict ORDER BY c DESC", args)
    problems = uid_rows(
        "SELECT * FROM problems WHERE course_id=? ORDER BY id", (course_id,))
    prob_rows = []
    for p in problems:
        sub_where, sargs = "s.problem_id=?", [p["id"]]
        if assignment_id:
            sub_where += " AND s.assignment_id=?"
            sargs.append(assignment_id)
        if p["type"] == "programming":
            st = uid_rows(
                "SELECT s.user_id, MAX(CASE WHEN s.verdict='Accepted' THEN 1 ELSE 0 END) ok, "
                "COUNT(*) tries, MAX(s.score) best, AVG(s.time_ms) t, MAX(s.time_ms) tmax "
                "FROM submissions s WHERE " + sub_where + " GROUP BY s.user_id", sargs)
        else:
            subj_where, jargs = "ss.problem_id=?", [p["id"]]
            if assignment_id:
                subj_where += " AND ss.assignment_id=?"
                jargs.append(assignment_id)
            st = uid_rows(
                "SELECT ss.user_id, MAX(CASE WHEN ss.status='done' THEN 1 ELSE 0 END) ok, 1 tries, "
                "AVG(ss.final_score) best, 0 t, 0 tmax FROM subjective_submissions ss "
                "WHERE " + subj_where + " GROUP BY ss.user_id", jargs)
        n = len(st)
        prob_rows.append({
            "id": p["id"], "title": p["title"], "type": p["type"],
            "difficulty": p["difficulty"], "topics": jload(p["topics"], []),
            "chapter": p["chapter"], "score": p["score"],
            "students": n, "pass_rate": round(sum(1 for r in st if r["ok"]) / n, 4) if n else 0,
            "ac_count": sum(1 for r in st if r["ok"]),
            "avg_score": round(sum((r["best"] or 0) for r in st) / n, 2) if n else 0,
            "avg_tries": round(sum(r["tries"] for r in st) / n, 2) if n else 0,
            "max_tries": max([r["tries"] for r in st] or [0]),
            "avg_time_ms": round(sum((r["t"] or 0) for r in st) / n, 2) if n else 0,
            "max_time_ms": max([r["tmax"] or 0 for r in st] or [0]),
            "zero_submit": students - n,
        })
    # 累计得分口径：每道题取该生最高分后求和（同一题反复提交不会刷高分数），
    # 主观题取互评聚合后的最终得分。满分 = 纳入统计的题目数 × 每题满分。
    prog = uid_rows(
        "SELECT s.user_id, s.problem_id, MAX(s.score) best, COUNT(*) tries, "
        "MAX(CASE WHEN s.verdict='Accepted' THEN 1 ELSE 0 END) ac "
        "FROM submissions s JOIN problems p ON p.id=s.problem_id " + where
        + " GROUP BY s.user_id, s.problem_id", args)
    subj_where = "WHERE p.course_id=?"
    subj_args = [course_id]
    if assignment_id:
        subj_where += " AND ss.assignment_id=?"
        subj_args.append(assignment_id)
    subj = uid_rows(
        "SELECT ss.user_id, ss.problem_id, MAX(COALESCE(ss.final_score,0)) best, "
        "MAX(CASE WHEN ss.status='done' THEN 1 ELSE 0 END) ac "
        "FROM subjective_submissions ss JOIN problems p ON p.id=ss.problem_id "
        + subj_where + " GROUP BY ss.user_id, ss.problem_id", subj_args)
    per_student = {}
    for r in prog:
        acc = per_student.setdefault(r["user_id"], {"total": 0.0, "c": 0, "ac": 0})
        acc["total"] += r["best"] or 0
        acc["c"] += r["tries"]
        acc["ac"] += r["ac"]
    for r in subj:
        acc = per_student.setdefault(r["user_id"], {"total": 0.0, "c": 0, "ac": 0})
        acc["total"] += r["best"] or 0
        acc["c"] += 1
        acc["ac"] += r["ac"]
    per_student = [{"user_id": k, **v} for k, v in per_student.items()]
    scored_problems = db.q1(
        "SELECT COUNT(*) c, COALESCE(SUM(score),0) s FROM problems " + (
            "WHERE course_id=?" if not assignment_id else
            "WHERE id IN (SELECT problem_id FROM assignment_problems WHERE assignment_id=?)"),
        ([course_id] if not assignment_id else [assignment_id])) or {"c": 0, "s": 0}
    scores = [r["total"] or 0 for r in per_student]
    users = {u["id"]: u for u in uid_rows("SELECT id,name,class_name FROM users")}
    ranking = sorted(
        [{"user_id": r["user_id"], "name": users.get(r["user_id"], {}).get("name"),
          "class_name": users.get(r["user_id"], {}).get("class_name"),
          "score": round(r["total"] or 0, 1), "ac": r["ac"], "submissions": r["c"]}
         for r in per_student], key=lambda x: -x["score"])
    for i, r in enumerate(ranking):
        r["rank"] = i + 1
    errs = uid_rows(
        "SELECT s.verdict, p.title, p.id AS problem_id, p.type AS problem_type, COUNT(*) c "
        "FROM submissions s "
        "JOIN problems p ON p.id=s.problem_id " + where
        + " AND s.verdict<>'Accepted' GROUP BY s.verdict,p.title ORDER BY c DESC LIMIT 15", args)
    return ok({
        "overview": {
            "submissions": total, "accepted": ac,
            "ac_rate": round(ac / total, 4) if total else 0,
            "students": students, "active_students": active,
            "avg_submissions_per_student": round(total / students, 2) if students else 0,
            "active_rate": round(active / students, 4) if students else 0,
        },
        "verdicts": verdicts,
        "problems": prob_rows,
        "score_distribution": _hist(scores, 10),
        "score_stats": _stats(scores),
        "score_rule": {
            "formula": "累计得分 = Σ 每道题的最高分（主观题取互评聚合后的最终得分）",
            "full_score": int(scored_problems["s"] or 0),
            "problem_count": int(scored_problems["c"] or 0),
            "per_problem": 100,
            "note": "同一道题多次提交只计最高分，因此反复提交不会把分数刷高；"
                    "统计范围：" + ("本次作业包含的题目" if assignment_id else "本课程全部题目"),
        },
        "ranking": ranking,
        "error_hotspots": errs,
    })


@route("GET", "/api/analytics/problem/{id}")
def api_analytics_problem(ctx):
    pid = int(ctx["params"]["id"])
    p = db.q1("SELECT * FROM problems WHERE id=?", (pid,))
    if not p:
        return err(404, "题目不存在")
    # 该课程的全部学生（用来回答「谁没提交」）
    all_students = uid_rows(
        "SELECT u.id, u.name, u.student_no, u.class_name FROM course_members m "
        "JOIN users u ON u.id=m.user_id WHERE m.course_id=? AND m.role='student' "
        "ORDER BY u.class_name, u.student_no, u.id",
        (p["course_id"],))
    subs = uid_rows(
        "SELECT s.*,u.name AS user_name,u.class_name FROM submissions s "
        "JOIN users u ON u.id=s.user_id WHERE s.problem_id=? ORDER BY s.id", (pid,))
    by_student = {}
    for s in subs:
        by_student.setdefault(s["user_id"], []).append(s)
    tries_to_ac = []
    for uid, rows in by_student.items():
        for i, r in enumerate(rows):
            if r["verdict"] == "Accepted":
                tries_to_ac.append(i + 1)
                break
    verdicts = {}
    for s in subs:
        verdicts[s["verdict"]] = verdicts.get(s["verdict"], 0) + 1
    times = [s["time_ms"] for s in subs if s["time_ms"]]
    mems = [s["memory_kb"] for s in subs if s["memory_kb"]]
    users = []
    for uid, rows in by_student.items():
        best_row = max(rows, key=lambda r: (r["score"] or 0, -r["id"]))
        users.append({
            "user_id": uid, "name": rows[0]["user_name"], "class_name": rows[0]["class_name"],
            "tries": len(rows), "best": best_row["score"], "verdict": best_row["verdict"],
            "time_ms": best_row["time_ms"], "memory_kb": best_row["memory_kb"],
            "solved": any(r["verdict"] == "Accepted" for r in rows),
        })
    users.sort(key=lambda r: (-(r["best"] or 0), r["tries"]))
    # 每位学生的逐次提交（谁提交了几次、每次什么判定），供教师点开查看
    detail = {}
    for uid, rows in by_student.items():
        detail[uid] = [
            {
                "id": r["id"], "verdict": r["verdict"], "score": r["score"],
                "time_ms": r["time_ms"], "memory_kb": r["memory_kb"],
                "language": r["language"], "submitted_at": r["submitted_at"],
                "attempt_no": r["attempt_no"],
            }
            for r in sorted(rows, key=lambda x: x["id"])
        ]
    submitted_ids = set(by_student)
    not_submitted = [s for s in all_students if s["id"] not in submitted_ids]
    # 主观题：谁交了、谁没交
    if p["type"] != "programming":
        subj_rows = uid_rows(
            "SELECT ss.user_id, ss.status, ss.final_score, ss.submitted_at "
            "FROM subjective_submissions ss JOIN assignments a ON a.id=ss.assignment_id "
            "WHERE ss.problem_id=? ORDER BY ss.id", (pid,))
        for r in subj_rows:
            detail.setdefault(r["user_id"], []).append(
                {"id": None, "verdict": "已提交" if r["status"] != "done" else "已完成评审",
                 "score": r["final_score"], "time_ms": 0, "memory_kb": 0,
                 "language": "text", "submitted_at": r["submitted_at"], "attempt_no": 1})
    total_students = db.q1(
        "SELECT COUNT(*) c FROM course_members WHERE course_id=? AND role='student'",
        (p["course_id"],))["c"]
    return ok({
        "problem": {
            "id": p["id"], "title": p["title"], "type": p["type"], "difficulty": p["difficulty"],
            "topics": jload(p["topics"], []), "time_limit_ms": p["time_limit_ms"],
            "memory_limit_mb": p["memory_limit_mb"], "score": p["score"],
            "chapter": p["chapter"],
        },
        "verdicts": verdicts,
        "attempts_hist": _hist([r["tries"] for r in users], 8),
        "tries_to_ac": {
            "mean": round(sum(tries_to_ac) / len(tries_to_ac), 2) if tries_to_ac else 0,
            "max": max(tries_to_ac) if tries_to_ac else 0,
            "hist": _hist(tries_to_ac, 8),
        },
        "time_stats": _stats(times),
        "memory_stats": _stats(mems),
        "time_hist": _hist(times, 12),
        "submissions": subs,
        "users": users,
        "detail": detail,
        "not_submitted": not_submitted,
        "students_total": total_students,
        "pass_rate": round(sum(1 for r in users if r["solved"]) / total_students, 4)
        if total_students else 0,
    })


@route("GET", "/api/analytics/student/{id}")
def api_analytics_student(ctx):
    uid = int(ctx["params"]["id"])
    if not is_teacher(ctx["user"]) and ctx["user"]["id"] != uid:
        return err(403, "只能查看自己的学习报告")
    course_id = _first_course(ctx)
    u = db.q1("SELECT * FROM users WHERE id=?", (uid,))
    if not u:
        return err(404, "用户不存在")
    subs = uid_rows(
        "SELECT s.*,p.title AS problem_title,p.type AS problem_type,p.topics,p.difficulty "
        "FROM submissions s JOIN problems p ON p.id=s.problem_id "
        "WHERE s.user_id=? AND p.course_id=? ORDER BY s.id DESC", (uid, course_id))
    for s in subs:
        s["topics"] = jload(s["topics"], [])
    solved = {s["problem_id"] for s in subs if s["verdict"] == "Accepted"}
    attempted = {s["problem_id"] for s in subs}
    topic_stat = {}
    for s in subs:
        for t in s["topics"]:
            topic_stat.setdefault(t, []).append(1.0 if s["verdict"] == "Accepted" else 0.0)
    mastery = {t: round(100 * sum(v) / len(v), 1) for t, v in topic_stat.items() if v}
    subj = uid_rows(
        "SELECT ss.id,ss.assignment_id,ss.problem_id,ss.status,ss.final_score,ss.methods,"
        "ss.submitted_at,p.title AS problem_title,a.title AS assignment_title,a.review_due_at "
        "FROM subjective_submissions ss JOIN problems p ON p.id=ss.problem_id "
        "JOIN assignments a ON a.id=ss.assignment_id WHERE ss.user_id=? ORDER BY ss.id DESC", (uid,))
    for s in subj:
        s["methods"] = jload(s["methods"], {})
        end = parse_dt(s["review_due_at"])
        published = bool(end and end < datetime.now())
        if not published and not is_teacher(ctx["user"]):
            s["final_score"] = None
            s["methods"] = {}
        s["published"] = published
    given = uid_rows(
        "SELECT al.id,al.assignment_id,al.problem_id,al.status,r.total,r.duration_sec,"
        "p.title AS problem_title FROM allocations al JOIN problems p ON p.id=al.problem_id "
        "LEFT JOIN reviews r ON r.allocation_id=al.id WHERE al.reviewer_id=? ORDER BY al.id DESC",
        (uid,))
    events = uid_rows(
        "SELECT type, COUNT(*) c FROM events WHERE user_id=? GROUP BY type ORDER BY c DESC", (uid,))
    peers = uid_rows(
        "SELECT s.user_id, COUNT(DISTINCT s.problem_id) n FROM submissions s "
        "JOIN problems p ON p.id=s.problem_id WHERE p.course_id=? AND s.verdict='Accepted' "
        "GROUP BY s.user_id", (course_id,))
    peer_solved = sorted(r["n"] for r in peers)
    my_solved = len(solved)
    rank = sum(1 for n in peer_solved if n > my_solved) + 1
    timeline = {}
    for s in subs:
        d = (s["submitted_at"] or "")[:10]
        timeline[d] = timeline.get(d, 0) + 1
    given_scores = [g["total"] for g in given if g["total"] is not None]
    durations = [g["duration_sec"] for g in given if g["duration_sec"]]
    return ok({
        "user": public_user(dict(u)),
        "submissions": subs,
        "solved": len(solved), "attempted": len(attempted),
        "ac_rate": round(sum(1 for s in subs if s["verdict"] == "Accepted") / len(subs), 4)
        if subs else 0,
        "mastery": mastery,
        "subjective": subj,
        "reviews_given": given,
        "review_stats": {
            "given": len(given), "done": sum(1 for g in given if g["status"] == "done"),
            "mean_score": round(sum(given_scores) / len(given_scores), 2) if given_scores else None,
            "mean_duration": round(sum(durations) / len(durations), 1) if durations else None,
        },
        "events": events,
        "timeline": sorted([{"date": k, "count": v} for k, v in timeline.items()],
                           key=lambda x: x["date"]),
        "rank": rank, "peer_count": len(peer_solved),
        "total_time_ms": round(sum(s["time_ms"] or 0 for s in subs), 2),
        "verdicts": {
            v: sum(1 for s in subs if s["verdict"] == v)
            for v in {s["verdict"] for s in subs}
        },
    })


@route("GET", "/api/analytics/knowledge")
def api_knowledge(ctx):
    course_id = _first_course(ctx)
    results = uid_rows(
        "SELECT s.user_id,s.problem_id,"
        "CASE WHEN s.verdict='Accepted' THEN 1.0 ELSE s.score/100.0 END sc "
        "FROM submissions s JOIN problems p ON p.id=s.problem_id WHERE p.course_id=?", (course_id,))
    problems = {p["id"]: p for p in uid_rows(
        "SELECT id,title,topics FROM problems WHERE course_id=?", (course_id,))}
    topic_acc, user_topic = {}, {}
    for r in results:
        for t in jload(problems[r["problem_id"]]["topics"], []):
            topic_acc.setdefault(t, []).append(r["sc"])
            user_topic.setdefault(r["user_id"], {}).setdefault(t, []).append(r["sc"])
    mastery = {t: round(100 * sum(v) / len(v), 1) for t, v in topic_acc.items()}
    per_user = {uid: {t: round(100 * sum(v) / len(v), 1) for t, v in topics.items()}
                for uid, topics in user_topic.items()}
    rows = [{"user_id": r["user_id"], "problem_id": r["problem_id"],
             "score": min(1.0, max(0.0, r["sc"]))} for r in results]
    irt = AB.irt_2pl(rows) if len(rows) >= 20 else {"ability_100": {}, "b": {}, "a": {}}
    difficulty = AB.difficulty_report(rows, irt)
    attempts = {
        p["id"]: [r["c"] for r in uid_rows(
            "SELECT COUNT(*) c FROM submissions WHERE problem_id=? GROUP BY user_id", (p["id"],))]
        for p in problems.values()
    }
    diff_full = AB.difficulty_report(rows, irt, attempts)
    return ok({
        "mastery": mastery,
        "per_user": per_user,
        "ability": irt.get("ability_100", {}),
        "difficulty": {
            str(k): {**v, "title": problems[k]["title"] if k in problems else "",
                     "mean_attempts_full": diff_full.get(k, {}).get("mean_attempts")}
            for k, v in difficulty.items()
        },
        "irt": {"b": irt.get("b", {}), "a": irt.get("a", {}), "iters": irt.get("iters"),
                "loglik": irt.get("loglik")},
    })


@route("GET", "/api/analytics/ability")
def api_ability(ctx):
    course_id = _first_course(ctx)
    rows = uid_rows(
        "SELECT s.user_id,s.problem_id,"
        "CASE WHEN s.verdict='Accepted' THEN 1.0 ELSE 0.0 END score,s.attempt_no "
        "FROM submissions s JOIN problems p ON p.id=s.problem_id WHERE p.course_id=?", (course_id,))
    first = [r for r in rows if r["attempt_no"] == 1]
    rows = first if len(first) >= 20 else rows
    irt = AB.irt_2pl(rows)
    elo = AB.elo_update(rows, rounds=30)
    users = {u["id"]: u for u in uid_rows("SELECT id,name,class_name FROM users")}
    out = []
    for uid, ab in sorted(irt.get("ability_100", {}).items(), key=lambda kv: -kv[1]):
        u = users.get(int(uid), {})
        out.append({
            "user_id": int(uid), "name": u.get("name"), "class_name": u.get("class_name"),
            "ability": ab, "theta": irt["theta"].get(uid),
            "elo": elo["rating"].get(int(uid)), "n": elo["count"].get(int(uid), 0)})
    problems = uid_rows(
        "SELECT id,title FROM problems WHERE course_id=? AND type='programming' ORDER BY id",
        (course_id,))
    probs = [{"id": p["id"], "title": p["title"], "b": irt["b"].get(p["id"]),
              "a": irt["a"].get(p["id"]),
              "difficulty": irt.get("difficulty_100", {}).get(p["id"]),
              "elo": elo["difficulty"].get(p["id"])} for p in problems]
    return ok({
        "students": out,
        "problems": sorted(probs, key=lambda x: (x["b"] if x["b"] is not None else 0)),
        "loglik": irt.get("loglik"), "iters": irt.get("iters"), "n_obs": irt.get("n_obs"),
    })


@route("GET", "/api/analytics/timeline")
def api_timeline(ctx):
    course_id = _first_course(ctx)
    rows = uid_rows(
        "SELECT substr(s.submitted_at,1,10) d, COUNT(*) n, "
        "SUM(CASE WHEN s.verdict='Accepted' THEN 1 ELSE 0 END) ac "
        "FROM submissions s JOIN problems p ON p.id=s.problem_id WHERE p.course_id=? "
        "GROUP BY d ORDER BY d", (course_id,))
    ev = uid_rows(
        "SELECT substr(created_at,1,10) d, type, COUNT(*) n FROM events WHERE course_id=? "
        "GROUP BY d,type ORDER BY d", (course_id,))
    return ok({"submissions": rows, "events": ev})


# ---------------------------------------------------------------------------
# 异常评审处理
# ---------------------------------------------------------------------------


@route("GET", "/api/anomalies")
def api_anomalies(ctx):
    q = ctx["query"]
    sql = ("SELECT an.*, u.name AS reviewer_name, au.name AS author_name, u.class_name "
           "FROM anomalies an LEFT JOIN users u ON u.id=an.reviewer_id "
           "LEFT JOIN users au ON au.id=an.submission_id "
           "LEFT JOIN assignments a ON a.id=an.assignment_id WHERE 1=1")
    args = []
    for key, col in (("assignment_id", "an.assignment_id"), ("level", "an.level"),
                     ("status", "an.status"), ("type", "an.type")):
        if q.get(key):
            sql += " AND " + col + "=?"
            args.append(q[key])
    # 只看当前课程范围内的异常
    cid = _first_course(ctx)
    if cid:
        sql += " AND a.course_id=?"
        args.append(cid)
    sql += (" ORDER BY CASE an.level WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, an.id DESC")
    rows = uid_rows(sql, args)
    for r in rows:
        r["evidence"] = jload(r["evidence"], {})
        # 教师复核时要直接看到「这个人当时怎么评的」：分数、文字意见、时长、对象
        r["reviews"] = uid_rows(
            "SELECT rv.id, rv.total, rv.scores, rv.comment, rv.duration_sec, rv.submitted_at, "
            "rv.flagged, rv.flag_reason, rv.assignment_id, rv.problem_id, "
            "p.title AS problem_title, a.title AS assignment_title, "
            "au.name AS target_name, au.class_name AS target_class "
            "FROM reviews rv LEFT JOIN problems p ON p.id=rv.problem_id "
            "LEFT JOIN assignments a ON a.id=rv.assignment_id "
            "LEFT JOIN users au ON au.id=rv.author_id "
            "WHERE rv.reviewer_id=? "
            + ("AND rv.assignment_id=? " if r["assignment_id"] else "")
            + "ORDER BY rv.id DESC LIMIT 20",
            ((r["reviewer_id"], r["assignment_id"]) if r["assignment_id"] else (r["reviewer_id"],)),
        )
        for rv in r["reviews"]:
            rv["scores"] = jload(rv["scores"], {})
    weights = {"high": 22, "medium": 11, "low": 4}
    stats = {}
    for r in rows:
        rid = r["reviewer_id"]
        if not rid:
            continue
        s = stats.setdefault(rid, {"reviewer_id": rid, "reviewer_name": r["reviewer_name"],
                                   "class_name": r["class_name"], "count": 0,
                                   "levels": {"high": 0, "medium": 0, "low": 0},
                                   "types": [], "risk": 0})
        s["count"] += 1
        s["levels"][r["level"]] = s["levels"].get(r["level"], 0) + 1
        s["types"].append(r["type"])
    for v in stats.values():
        v["risk"] = min(100, sum(weights.get(k, 4) * c for k, c in v["levels"].items()))
        v["level"] = "高" if v["risk"] >= 45 else ("中" if v["risk"] >= 20 else "低")
        v["types"] = sorted(set(v["types"]))
    return ok({
        "anomalies": rows,
        "reviewer_risk": sorted(stats.values(), key=lambda x: -x["risk"]),
        "counts": {
            "high": sum(1 for r in rows if r["level"] == "high"),
            "medium": sum(1 for r in rows if r["level"] == "medium"),
            "low": sum(1 for r in rows if r["level"] == "low"),
            "open": sum(1 for r in rows if r["status"] == "open"),
        },
    })


@route("POST", "/api/anomalies/{id}/handle", "teacher")
def api_anomaly_handle(ctx):
    b = ctx["body"]
    an_id = int(ctx["params"]["id"])
    status = b.get("status") or "confirmed"
    if status not in ("open", "confirmed", "dismissed", "adjusted"):
        return err(400, "状态不合法")
    db.ex("UPDATE anomalies SET status=?,handled_by=?,note=? WHERE id=?",
          (status, ctx["user"]["id"], b.get("note") or "", an_id))
    if status in ("confirmed", "adjusted") and b.get("adjust_weight") is not None:
        an = db.q1("SELECT * FROM anomalies WHERE id=?", (an_id,))
        if an and an["reviewer_id"]:
            db.ex("UPDATE allocations SET weight=? WHERE reviewer_id=? AND assignment_id=?",
                  (float(b["adjust_weight"]), an["reviewer_id"], an["assignment_id"]))
    return ok({"id": an_id, "status": status})


@route("POST", "/api/anomalies/handle-batch", "teacher")
def api_anomaly_batch(ctx):
    b = ctx["body"] or {}
    ids = b.get("ids") or []
    status = b.get("status") or "confirmed"
    for i in ids:
        db.ex("UPDATE anomalies SET status=?,handled_by=?,note=? WHERE id=?",
              (status, ctx["user"]["id"], b.get("note") or "", i))
    return ok({"updated": len(ids)})


# ---------------------------------------------------------------------------
# 代码相似度与算法实验台
# ---------------------------------------------------------------------------


@route("GET", "/api/similarity")
def api_similarity(ctx):
    q = ctx["query"]
    sql = ("SELECT s.id,s.user_id,s.problem_id,s.source_code,s.language,u.name "
           "FROM submissions s JOIN users u ON u.id=s.user_id "
           "JOIN problems p ON p.id=s.problem_id WHERE 1=1")
    args = []
    if q.get("problem_id"):
        sql += " AND s.problem_id=?"
        args.append(q["problem_id"])
    if q.get("assignment_id"):
        sql += " AND s.assignment_id=?"
        args.append(q["assignment_id"])
    cid = _first_course(ctx)
    if cid:
        sql += " AND p.course_id=?"
        args.append(cid)
    sql += " AND s.id IN (SELECT MAX(id) FROM submissions GROUP BY user_id,problem_id) LIMIT 200"
    rows = uid_rows(sql, args)
    if len(rows) < 2:
        return ok({"pairs": [], "clusters": [], "n_submissions": len(rows)})
    subs = [{"id": r["id"], "user_id": r["user_id"], "code": r["source_code"],
             "language": r["language"]} for r in rows]
    res = SIM.pairwise_similarity(subs, float(q.get("threshold") or 0.6))
    names = {r["id"]: r["name"] for r in rows}
    for p in res["pairs"]:
        p["a_name"] = names.get(p["a"])
        p["b_name"] = names.get(p["b"])
    res["n_submissions"] = len(subs)
    return ok(res)


@route("GET", "/api/experiments")
def api_experiments(ctx):
    rows = uid_rows(
        "SELECT id,name,params,result,elapsed_ms,created_at FROM experiments ORDER BY id DESC LIMIT 40")
    for r in rows:
        r["params"] = jload(r["params"], {})
        r["result"] = jload(r["result"], {})
    return ok(rows)


@route("POST", "/api/experiments/run")
def api_experiment_run(ctx):
    b = ctx["body"] or {}
    key = b.get("key")
    fn = EX.EXPERIMENTS.get(key)
    if not fn:
        return err(400, "未知实验：" + str(key))
    meta = next((m for m in EX.EXPERIMENT_META if m["key"] == key), {})
    kwargs = {}
    for spec in meta.get("params", []):
        v = (b.get("params") or {}).get(spec["key"])
        if v is None or v == "":
            continue
        try:
            kwargs[spec["key"]] = float(v) if spec["type"] == "float" else int(float(v))
        except (TypeError, ValueError):
            continue
    t0 = time.perf_counter()
    try:
        result = fn(**kwargs)
    except TypeError as e:
        return err(400, "参数不合法：" + str(e))
    except Exception as e:  # pragma: no cover
        return err(500, "实验执行失败：" + str(e))
    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    result["elapsed_ms"] = elapsed
    result["id"] = db.ex(
        "INSERT INTO experiments(name,params,result,elapsed_ms,created_at) VALUES(?,?,?,?,?)",
        (key, db.jdumps(kwargs), db.jdumps(result), elapsed, db.now()))
    return ok(result)


# ---------------------------------------------------------------------------
# 通知与看板
# ---------------------------------------------------------------------------


@route("GET", "/api/notices")
def api_notices(ctx):
    cid = ctx["query"].get("course_id")
    if not cid:
        cid = _first_course(ctx)
    rows = uid_rows(
        "SELECT n.*,u.name AS author_name FROM notices n LEFT JOIN users u ON u.id=n.author_id "
        "WHERE (? IS NULL OR n.course_id=?) ORDER BY n.id DESC LIMIT 30", (cid, cid))
    return ok(rows)


@route("POST", "/api/notices", "teacher")
def api_notice_create(ctx):
    b = ctx["body"]
    nid = db.ex(
        "INSERT INTO notices(course_id,title,content,author_id,created_at) VALUES(?,?,?,?,?)",
        (b.get("course_id") or db.q1("SELECT id FROM courses ORDER BY id")["id"],
         b.get("title") or "通知", b.get("content") or "", ctx["user"]["id"], db.now()))
    return ok({"id": nid})


@route("GET", "/api/dashboard/teacher")
def api_dashboard_teacher(ctx):
    cid0 = _first_course(ctx)
    course = db.q1("SELECT * FROM courses WHERE id=?", (cid0,)) if cid0 else None
    if not course:
        # 新注册的教师还没建课时，返回空看板 + 引导，而不是别人的数据
        return ok({"course": None, "need_course": True, "students": 0, "assignments": [],
                   "stats": {"submissions": 0, "accepted": 0, "ac_rate": 0, "pending_reviews": 0,
                             "open_anomalies": 0, "classes": 0, "problems": 0},
                   "notices": []})
    cid = course["id"]
    now = datetime.now()
    assignments = uid_rows("SELECT * FROM assignments WHERE course_id=? ORDER BY id DESC", (cid,))
    for a in assignments:
        a["submitted_users"] = db.q1(
            "SELECT COUNT(DISTINCT user_id) c FROM submissions WHERE assignment_id=?", (a["id"],))["c"]
        a["subjective_users"] = db.q1(
            "SELECT COUNT(DISTINCT user_id) c FROM subjective_submissions WHERE assignment_id=?",
            (a["id"],))["c"]
        a["pending_reviews"] = db.q1(
            "SELECT COUNT(*) c FROM allocations WHERE assignment_id=? AND status='pending'",
            (a["id"],))["c"]
        due = parse_dt(a["due_at"])
        a["overdue"] = bool(due and due < now)
    students = db.q1(
        "SELECT COUNT(*) c FROM course_members WHERE course_id=? AND role='student'", (cid,))["c"]
    subs = db.q1(
        "SELECT COUNT(*) c FROM submissions s JOIN problems p ON p.id=s.problem_id "
        "WHERE p.course_id=?", (cid,))["c"]
    ac = db.q1(
        "SELECT COUNT(*) c FROM submissions s JOIN problems p ON p.id=s.problem_id "
        "WHERE p.course_id=? AND s.verdict='Accepted'", (cid,))["c"]
    return ok({
        "course": dict(course), "students": students, "assignments": assignments,
        "stats": {
            "submissions": subs, "accepted": ac,
            "ac_rate": round(ac / subs, 4) if subs else 0,
            "pending_reviews": sum(a["pending_reviews"] for a in assignments),
            "open_anomalies": db.q1(
                "SELECT COUNT(*) c FROM anomalies an JOIN assignments a ON a.id=an.assignment_id "
                "WHERE a.course_id=? AND an.status='open'", (cid,))["c"],
            "classes": db.q1(
                "SELECT COUNT(DISTINCT class_name) c FROM course_members m "
                "JOIN users u ON u.id=m.user_id WHERE m.course_id=? AND m.role='student'",
                (cid,))["c"],
            "problems": db.q1("SELECT COUNT(*) c FROM problems WHERE course_id=?", (cid,))["c"],
        },
        "recent_submissions": uid_rows(
            "SELECT s.id,s.user_id,s.verdict,s.score,s.submitted_at,p.title,u.name "
            "FROM submissions s JOIN problems p ON p.id=s.problem_id "
            "JOIN users u ON u.id=s.user_id WHERE p.course_id=? ORDER BY s.id DESC LIMIT 12",
            (cid,)),
        "notices": uid_rows(
            "SELECT * FROM notices WHERE course_id=? ORDER BY id DESC LIMIT 5", (cid,)),
        "class_stats": uid_rows(
            "SELECT u.class_name, COUNT(DISTINCT u.id) n, "
            "COUNT(DISTINCT s.problem_id) problems FROM course_members m "
            "JOIN users u ON u.id=m.user_id LEFT JOIN submissions s ON s.user_id=u.id "
            "WHERE m.course_id=? AND m.role='student' GROUP BY u.class_name", (cid,)),
    })


@route("GET", "/api/dashboard/student")
def api_dashboard_student(ctx):
    uid = ctx["user"]["id"]
    cid0 = _first_course(ctx)
    course = db.q1("SELECT * FROM courses WHERE id=?", (cid0,)) if cid0 else None
    if not course:
        return ok({"course": None, "need_course": True, "assignments": [], "todo": [],
                   "submissions": [], "notices": []})
    cid = course["id"] if course else None
    now = datetime.now()
    assignments = uid_rows(
        "SELECT * FROM assignments WHERE course_id=? ORDER BY "
        "CASE WHEN due_at IS NULL THEN 1 ELSE 0 END, due_at DESC", (cid,))
    todo = []
    for a in assignments:
        probs = uid_rows(
            "SELECT p.id,p.title,p.type FROM assignment_problems ap "
            "JOIN problems p ON p.id=ap.problem_id WHERE ap.assignment_id=? ORDER BY ap.order_index",
            (a["id"],))
        done = 0
        for p in probs:
            if p["type"] == "programming":
                hit = db.q1(
                    "SELECT id FROM submissions WHERE problem_id=? AND user_id=? "
                    "AND verdict='Accepted' LIMIT 1", (p["id"], uid))
            else:
                hit = db.q1(
                    "SELECT id FROM subjective_submissions WHERE assignment_id=? AND problem_id=? "
                    "AND user_id=?", (a["id"], p["id"], uid))
            if hit:
                done += 1
        a["problems"] = probs
        a["progress"] = {"done": done, "total": len(probs),
                         "ratio": round(done / len(probs), 3) if probs else 0}
        due = parse_dt(a["due_at"])
        a["overdue"] = bool(due and due < now)
        if a["peer_review"]:
            a["my_review_pending"] = db.q1(
                "SELECT COUNT(*) c FROM allocations WHERE assignment_id=? AND reviewer_id=? "
                "AND status='pending'", (a["id"], uid))["c"]
        if done < len(probs) and not a["overdue"]:
            todo.append(a)
    subs = uid_rows(
        "SELECT s.id,s.verdict,s.score,s.time_ms,s.submitted_at,p.title,p.type "
        "FROM submissions s JOIN problems p ON p.id=s.problem_id "
        "WHERE s.user_id=? ORDER BY s.id DESC LIMIT 20", (uid,))
    pending = uid_rows(
        "SELECT al.id,a.title,a.id AS assignment_id,a.review_due_at,p.title AS problem_title "
        "FROM allocations al JOIN assignments a ON a.id=al.assignment_id "
        "JOIN problems p ON p.id=al.problem_id WHERE al.reviewer_id=? AND al.status='pending' "
        "ORDER BY a.review_due_at", (uid,))
    total_subs = db.q1("SELECT COUNT(*) c FROM submissions WHERE user_id=?", (uid,))["c"]
    total_ac = db.q1(
        "SELECT COUNT(*) c FROM submissions WHERE user_id=? AND verdict='Accepted'", (uid,))["c"]
    solved = db.q1(
        "SELECT COUNT(DISTINCT problem_id) c FROM submissions WHERE user_id=? "
        "AND verdict='Accepted'", (uid,))["c"]
    return ok({
        "course": dict(course) if course else None,
        "todo": todo[:5], "assignments": assignments, "recent_submissions": subs,
        "pending_reviews": pending,
        "stats": {
            "submissions": total_subs, "accepted": total_ac,
            "ac_rate": round(total_ac / total_subs, 4) if total_subs else 0,
            "solved": solved, "pending_reviews": len(pending),
        },
        "notices": uid_rows(
            "SELECT * FROM notices WHERE course_id=? ORDER BY id DESC LIMIT 3", (cid,)),
    })
