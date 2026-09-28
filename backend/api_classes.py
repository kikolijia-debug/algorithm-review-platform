"""班级管理接口：新建 / 重命名 / 删除班级，以及班级成员的增删与查看。

数据模型
--------
* ``classes``            ：班级元数据（名称、说明、邀请码）
* ``course_members.class_id``：学生与班级的关联（权威来源，可为空表示未分班）
* ``users.class_name``   ：班级名称的镜像字段，供多处展示查询使用，
                            每次班级变动后由 :func:`_sync_class_name` 同步

删除班级时默认把学生置为「未分班」，也支持先转移到另一个班级再删除，
避免误删班级导致学生记录消失。
"""

from __future__ import annotations

import hashlib

from . import db
from .api import active_course_id, err, ok, route, uid_rows


def _first_course(ctx=None):
    """当前账号的活动课程；没有 ctx（内部调用）时退回库里的第一门课。"""
    if ctx is not None:
        return active_course_id(ctx, ctx["query"].get("course_id"))
    row = db.q1("SELECT id FROM courses ORDER BY id LIMIT 1")
    return row["id"] if row else None


def _gen_code(name: str) -> str:
    """生成不重复的班级邀请码（6 位十六进制）。"""
    base = hashlib.md5((name + db.now()).encode("utf-8")).hexdigest()[:6].upper()
    code, i = base, 1
    while db.q1("SELECT id FROM classes WHERE invite_code=?", (code,)):
        code = base[:5] + "0123456789ABCDEF"[i % 16]
        i += 1
    return code


def _sync_class_name(user_ids) -> None:
    """把班级归属同步到 ``users.class_name``（多处展示查询用它）。"""
    if not user_ids:
        return
    conn = db.get_conn()
    for uid in user_ids:
        row = conn.execute(
            "SELECT c.name AS name FROM course_members m LEFT JOIN classes c ON c.id=m.class_id "
            "WHERE m.user_id=? ORDER BY m.id LIMIT 1",
            (uid,),
        ).fetchone()
        conn.execute(
            "UPDATE users SET class_name=? WHERE id=?", (row["name"] if row else None, uid)
        )
    conn.commit()


def _assign_class(cid: int, user_ids, course_id: int) -> int:
    conn = db.get_conn()
    for uid in user_ids:
        conn.execute(
            "INSERT OR IGNORE INTO course_members(course_id,user_id,role,class_id,joined_at) "
            "VALUES(?,?,'student',?,?)",
            (course_id, uid, cid, db.now()),
        )
        conn.execute(
            "UPDATE course_members SET class_id=? WHERE course_id=? AND user_id=?",
            (cid, course_id, uid),
        )
    conn.commit()
    _sync_class_name(user_ids)
    return len(user_ids)


def _class_stats(class_id: int, course_id: int) -> dict:
    ids = [
        r["id"]
        for r in db.q(
            "SELECT u.id FROM course_members m JOIN users u ON u.id=m.user_id "
            "WHERE m.course_id=? AND m.class_id=? AND m.role='student'",
            (course_id, class_id),
        )
    ]
    if not ids:
        return {"member_count": 0, "active_count": 0, "ac_rate": 0.0, "total_submissions": 0}
    ph = ",".join("?" * len(ids))
    rows = db.q(
        "SELECT s.user_id, s.problem_id, "
        "MAX(CASE WHEN s.verdict='Accepted' THEN 1 ELSE 0 END) ok, COUNT(*) n "
        "FROM submissions s JOIN problems p ON p.id=s.problem_id "
        f"WHERE p.course_id=? AND s.user_id IN ({ph}) GROUP BY s.user_id, s.problem_id",
        (course_id, *ids),
    )
    # 通过率按「学生 × 题目」统计：尝试过的题目里最终通过的比例
    attempted = len(rows)
    passed = sum(1 for r in rows if r["ok"])
    active = len({r["user_id"] for r in rows})
    avg = db.q1(
        "SELECT AVG(best) v FROM (SELECT MAX(s.score) best FROM submissions s "
        f"JOIN problems p ON p.id=s.problem_id WHERE p.course_id=? AND s.user_id IN ({ph}) "
        "GROUP BY s.user_id, s.problem_id)",
        (course_id, *ids),
    )
    return {
        "member_count": len(ids),
        "active_count": active,
        "ac_rate": round(passed / attempted, 4) if attempted else 0.0,
        "total_submissions": sum(r["n"] for r in rows),
        "avg_score": round(avg["v"], 1) if avg and avg["v"] is not None else None,
    }


# ---------------------------------------------------------------- 班级


@route("GET", "/api/classes")
def api_classes(ctx):
    """班级列表（含人数与通过率）。学生只会看到自己所在的班级。"""
    course_id = _first_course(ctx)
    rows = uid_rows("SELECT * FROM classes WHERE course_id=? ORDER BY name", (course_id,))
    mine = None
    if ctx["user"]["role"] == "student":
        m = db.q1(
            "SELECT class_id FROM course_members WHERE course_id=? AND user_id=?",
            (course_id, ctx["user"]["id"]),
        )
        mine = m["class_id"] if m else None
    for c in rows:
        c.update(_class_stats(c["id"], course_id))
        if mine is not None and c["id"] != mine:
            c["invite_code"] = None
    return ok(rows)


@route("GET", "/api/classes/unassigned", "teacher")
def api_unassigned(ctx):
    """未分班的学生，用于「添加到班级」的选择器。"""
    course_id = _first_course(ctx)
    return ok(
        uid_rows(
            "SELECT u.id,u.name,u.student_no,u.username FROM course_members m "
            "JOIN users u ON u.id=m.user_id "
            "WHERE m.course_id=? AND m.role='student' AND (m.class_id IS NULL OR m.class_id=0) "
            "ORDER BY u.student_no,u.id",
            (course_id,),
        )
    )


@route("POST", "/api/classes", "teacher")
def api_class_create(ctx):
    b = ctx["body"]
    course_id = _first_course(ctx) or b.get("course_id")
    name = (b.get("name") or "").strip()
    if not name:
        return err(400, "班级名称不能为空")
    if len(name) > 40:
        return err(400, "班级名称过长（最多 40 字）")
    if db.q1("SELECT id FROM classes WHERE course_id=? AND name=?", (course_id, name)):
        return err(409, "班级「%s」已存在" % name)
    code = (b.get("invite_code") or "").strip().upper() or _gen_code(name)
    if db.q1("SELECT id FROM classes WHERE invite_code=?", (code,)):
        return err(409, "邀请码 %s 已被占用" % code)
    cid = db.ex(
        "INSERT INTO classes(course_id,name,description,invite_code,created_at) VALUES(?,?,?,?,?)",
        (course_id, name, b.get("description") or "", code, db.now()),
    )
    added = 0
    if b.get("user_ids"):
        added = _assign_class(cid, [int(x) for x in b["user_ids"]], course_id)
    return ok({"id": cid, "name": name, "invite_code": code, "added": added})


@route("PUT", "/api/classes/{id}", "teacher")
def api_class_update(ctx):
    cid = int(ctx["params"]["id"])
    cls = db.q1("SELECT * FROM classes WHERE id=?", (cid,))
    if not cls:
        return err(404, "班级不存在")
    b = ctx["body"]
    name = (b.get("name") or cls["name"]).strip()
    if not name:
        return err(400, "班级名称不能为空")
    if name != cls["name"] and db.q1(
        "SELECT id FROM classes WHERE course_id=? AND name=? AND id<>?",
        (cls["course_id"], name, cid),
    ):
        return err(409, "班级「%s」已存在" % name)
    code = (b.get("invite_code") or cls["invite_code"] or "").strip().upper()
    if code and code != cls["invite_code"] and db.q1(
        "SELECT id FROM classes WHERE invite_code=? AND id<>?", (code, cid)
    ):
        return err(409, "邀请码 %s 已被占用" % code)
    db.ex(
        "UPDATE classes SET name=?,description=?,invite_code=? WHERE id=?",
        (name, b.get("description", cls["description"]), code, cid),
    )
    if name != cls["name"]:
        _sync_class_name(
            [r["user_id"] for r in db.q("SELECT user_id FROM course_members WHERE class_id=?", (cid,))]
        )
    return ok({"id": cid, "name": name, "renamed": name != cls["name"]})


@route("DELETE", "/api/classes/{id}", "teacher")
def api_class_delete(ctx):
    """删除班级。默认把学生置为「未分班」，mode=move&target_id= 则先转入其它班级。"""
    cid = int(ctx["params"]["id"])
    cls = db.q1("SELECT * FROM classes WHERE id=?", (cid,))
    if not cls:
        return err(404, "班级不存在")
    q = ctx["query"]
    mode = q.get("mode") or "unassign"
    members = [
        r["user_id"] for r in db.q("SELECT user_id FROM course_members WHERE class_id=?", (cid,))
    ]
    if mode == "move":
        target = int(q.get("target_id") or 0)
        if not db.q1(
            "SELECT id FROM classes WHERE id=? AND course_id=?", (target, cls["course_id"])
        ):
            return err(400, "目标班级不存在")
        db.ex("UPDATE course_members SET class_id=? WHERE class_id=?", (target, cid))
    else:
        db.ex("UPDATE course_members SET class_id=NULL WHERE class_id=?", (cid,))
    _sync_class_name(members)
    db.ex("DELETE FROM classes WHERE id=?", (cid,))
    return ok({"deleted": cid, "students_affected": len(members), "mode": mode})


# ------------------------------------------------------------ 班级成员


@route("GET", "/api/classes/{id}/students", "teacher")
def api_class_students(ctx):
    cid = int(ctx["params"]["id"])
    cls = db.q1("SELECT * FROM classes WHERE id=?", (cid,))
    if not cls:
        return err(404, "班级不存在")
    rows = uid_rows(
        "SELECT u.id,u.name,u.username,u.student_no,u.email,u.last_login, "
        "(SELECT COUNT(*) FROM submissions s WHERE s.user_id=u.id) AS submissions, "
        "(SELECT COUNT(DISTINCT s.problem_id) FROM submissions s "
        " WHERE s.user_id=u.id AND s.verdict='Accepted') AS solved "
        "FROM course_members m JOIN users u ON u.id=m.user_id "
        "WHERE m.class_id=? ORDER BY u.student_no,u.id",
        (cid,),
    )
    return ok({"class": dict(cls), "students": rows})


@route("POST", "/api/classes/{id}/students", "teacher")
def api_class_add_students(ctx):
    cid = int(ctx["params"]["id"])
    cls = db.q1("SELECT * FROM classes WHERE id=?", (cid,))
    if not cls:
        return err(404, "班级不存在")
    ids = [int(x) for x in (ctx["body"].get("user_ids") or [])]
    if not ids:
        return err(400, "请选择要加入班级的学生")
    return ok({"added": _assign_class(cid, ids, cls["course_id"]), "class_id": cid})


@route("DELETE", "/api/classes/{id}/students/{user_id}", "teacher")
def api_class_remove_student(ctx):
    cid = int(ctx["params"]["id"])
    uid = int(ctx["params"]["user_id"])
    if not db.q1("SELECT id FROM classes WHERE id=?", (cid,)):
        return err(404, "班级不存在")
    db.ex("UPDATE course_members SET class_id=NULL WHERE class_id=? AND user_id=?", (cid, uid))
    _sync_class_name([uid])
    return ok({"class_id": cid, "user_id": uid})
