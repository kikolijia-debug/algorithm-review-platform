"""REST API 层（核心接口）。

所有接口统一返回 JSON；路由以 ``(METHOD, /api/path/{param})`` 注册，
由 ``server.py`` 完成匹配与分发。约定：

* 需要登录的接口在未携带有效令牌时返回 401；
* 仅教师可用的接口（题库编辑、任务分配、异常处理）在角色不符时返回 403；
* 学生查看互评任务时，**作者身份被脱敏**（只返回稳定的匿名编号），满足「匿名互评」要求。

文件末尾会导入 ``api_ext``，把学习分析、异常检测、实验台等接口注册到同一张路由表。
"""

from __future__ import annotations

import time
from datetime import datetime

from . import db, judge as J
from .algo import aggregation as AG
from .algo import anomaly as AN
from .algo import assignment as AS
from .auth import create_session, drop_session, hash_password, verify_password

#: 路由表：``(method, path, handler, auth)``；``auth`` = public | user | teacher
ROUTES: list[tuple[str, str, callable, str]] = []


def route(method: str, path: str, auth: str = "user"):
    def deco(fn):
        ROUTES.append((method.upper(), path, fn, auth))
        return fn

    return deco


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------


def ok(data=None, **extra):
    payload = {"ok": True}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return 200, payload


def err(status: int, message: str, **extra):
    payload = {"ok": False, "error": message}
    payload.update(extra)
    return status, payload


def uid_rows(sql, args=()):
    return db.rows2dicts(db.q(sql, args))


def jload(text, default=None):
    return db.jloads(text, default if default is not None else {})


def parse_dt(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return None


def is_teacher(user) -> bool:
    return user.get("role") in ("teacher", "ta")


def public_user(u):
    if not u:
        return None
    return {
        "id": u["id"], "username": u["username"], "name": u["name"], "role": u["role"],
        "email": u["email"], "student_no": u["student_no"], "class_name": u["class_name"],
        "avatar": u["avatar"],
    }


def anon_label(user_id: int) -> str:
    """把学生 id 映射成稳定匿名编号（可追溯但对评审者不可识别）。"""
    return "匿名#%d" % (1000 + (int(user_id) * 7919) % 8999)


# ---------------------------------------------------------------------------
# 课程归属：每个账号只应看到「自己的课程」，而不是库里的第一门课
# ---------------------------------------------------------------------------


def user_course_ids(user) -> list[int]:
    """当前账号可见的课程：教师=自己开设或协作的；学生=已加入的。"""
    if not user:
        return []
    uid = user["id"]
    if user.get("role") in ("teacher", "ta"):
        rows = db.q(
            "SELECT id FROM courses WHERE teacher_id=? "
            "UNION SELECT course_id AS id FROM course_members "
            "WHERE user_id=? AND role<>'student' ORDER BY id",
            (uid, uid),
        )
    else:
        rows = db.q(
            "SELECT course_id AS id FROM course_members WHERE user_id=? ORDER BY course_id",
            (uid,),
        )
    return [r["id"] for r in rows]


def active_course_id(ctx, explicit=None) -> int | None:
    """当前活动课程。

    * 显式传入的 course_id 只有在属于当前用户时才生效，避免越权看到别人的课；
    * 否则取该用户的第一门课；没有任何课程时返回 ``None``（由调用方给出空数据/引导）。
    """
    mine = user_course_ids(ctx.get("user"))
    if explicit:
        try:
            cid = int(explicit)
        except (TypeError, ValueError):
            cid = None
        if cid and cid in mine:
            return cid
    return mine[0] if mine else None


def gen_invite_code(prefix: str = "CLS") -> str:
    import hashlib
    import random as _random

    for _ in range(50):
        code = prefix + "".join(_random.choice("0123456789ABCDEF") for _ in range(4))
        if not db.q1("SELECT id FROM courses WHERE invite_code=?", (code,)):
            return code
    return prefix + hashlib.md5(db.now().encode()).hexdigest()[:4].upper()


#: 编程题（代码互评）的默认评分细则；教师可在题库里为每道题单独配置
DEFAULT_CODE_RUBRIC = [
    {"key": "correctness", "name": "正确性", "max": 35,
     "desc": "算法是否正确，边界情况（n=1、极值、重复元素）是否处理"},
    {"key": "complexity", "name": "效率与复杂度", "max": 25,
     "desc": "是否达到题目要求的复杂度，有无不必要的重复计算"},
    {"key": "clarity", "name": "代码清晰度", "max": 20,
     "desc": "命名、结构、注释是否清晰易读"},
    {"key": "robustness", "name": "健壮性", "max": 20,
     "desc": "是否存在溢出、越界、未初始化等隐患"},
]


def default_code_rubric() -> list:
    return [dict(x) for x in DEFAULT_CODE_RUBRIC]


# ---------------------------------------------------------------------------
# 认证
# ---------------------------------------------------------------------------


@route("POST", "/api/auth/register", "public")
def api_register(ctx):
    """注册账号。

    * 教师 / 助教：自动创建一门属于自己的课程（课程名可自填），注册完就能直接用；
    * 学生：填写邀请码后直接加入对应课程（或班级）；不填则先进入「未加入课程」状态，
      登录后可以在学习动态里用邀请码加入，不会污染别人的课程。
    """
    b = ctx["body"]
    username = (b.get("username") or "").strip()
    name = (b.get("name") or "").strip()
    pwd = b.get("password") or ""
    role = b.get("role") or "student"
    if len(username) < 3 or len(pwd) < 6 or not name:
        return err(400, "账号至少 3 位、密码至少 6 位，姓名不能为空")
    if role not in ("student", "teacher", "ta"):
        return err(400, "角色不合法")
    if db.q1("SELECT id FROM users WHERE username=?", (username,)):
        return err(409, "该账号已被注册")
    pw, salt = hash_password(pwd)
    uid = db.ex(
        "INSERT INTO users(username,email,password,salt,role,name,student_no,class_name,avatar,"
        "created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (username, b.get("email"), pw, salt, role, name, b.get("student_no"),
         b.get("class_name"), name[0], db.now()),
    )
    code = (b.get("invite_code") or "").strip().upper()
    joined = None
    if role in ("teacher", "ta"):
        # 自己开一门课，课程名默认「某某 的课程」
        course_name = (b.get("course_name") or "").strip() or (name + " 的课程")
        joined = db.ex(
            "INSERT INTO courses(name,code,term,teacher_id,description,invite_code,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (course_name, None, b.get("term") or None, uid, "", gen_invite_code("CRS"), db.now()),
        )
        db.ex(
            "INSERT OR IGNORE INTO course_members(course_id,user_id,role,class_id,joined_at) "
            "VALUES(?,?,?,?,?)",
            (joined, uid, role, None, db.now()),
        )
    elif code:
        course = db.q1("SELECT * FROM courses WHERE UPPER(invite_code)=?", (code,))
        cls = db.q1("SELECT * FROM classes WHERE UPPER(invite_code)=?", (code,))
        if not course and cls:
            course = db.q1("SELECT * FROM courses WHERE id=?", (cls["course_id"],))
        if not course:
            db.ex("DELETE FROM users WHERE id=?", (uid,))
            return err(404, "邀请码无效，请向任课老师确认后再注册")
        joined = course["id"]
        db.ex(
            "INSERT OR IGNORE INTO course_members(course_id,user_id,role,class_id,joined_at) "
            "VALUES(?,?,?,?,?)",
            (joined, uid, role, cls["id"] if cls else None, db.now()),
        )
        if cls:
            db.ex("UPDATE users SET class_name=? WHERE id=?", (cls["name"], uid))
    u = dict(db.q1("SELECT * FROM users WHERE id=?", (uid,)))
    return ok({
        "token": create_session(u), "user": public_user(u),
        "course_id": joined,
        "need_course": role == "student" and not joined,
    })


@route("POST", "/api/auth/login", "public")
def api_login(ctx):
    body = ctx["body"]
    ident = (body.get("username") or body.get("email") or "").strip()
    pwd = body.get("password") or ""
    if not ident or not pwd:
        return err(400, "请输入账号与密码")
    u = db.q1("SELECT * FROM users WHERE username=? OR email=?", (ident, ident))
    if not u:
        return err(401, "账号不存在")
    if not verify_password(pwd, u["password"], u["salt"]):
        return err(401, "密码错误")
    if body.get("role") and u["role"] != body["role"]:
        role_name = {"teacher": "教师", "student": "学生", "ta": "助教"}.get(u["role"], u["role"])
        return err(403, "该账号是「%s」身份，请切换对应的登录入口" % role_name)
    token = create_session(dict(u))
    db.ex("UPDATE users SET last_login=? WHERE id=?", (db.now(), u["id"]))
    db.ex(
        "INSERT INTO events(user_id,course_id,type,payload,created_at) VALUES(?,?,?,?,?)",
        (u["id"], None, "login", "{}", db.now()),
    )
    return ok({"token": token, "user": public_user(dict(u))})


@route("POST", "/api/auth/logout")
def api_logout(ctx):
    drop_session(ctx.get("token"))
    return ok()


@route("GET", "/api/auth/me")
def api_me(ctx):
    u = db.q1("SELECT * FROM users WHERE id=?", (ctx["user"]["id"],))
    courses = uid_rows(
        "SELECT c.*, m.role AS member_role FROM course_members m JOIN courses c ON c.id=m.course_id "
        "WHERE m.user_id=? ORDER BY c.id",
        (ctx["user"]["id"],),
    )
    peer_pending = db.q1(
        "SELECT COUNT(*) c FROM allocations al JOIN assignments a ON a.id=al.assignment_id "
        "WHERE al.reviewer_id=? AND al.status='pending' AND a.allocation_status='confirmed'",
        (ctx["user"]["id"],),
    )["c"]
    return ok({"user": public_user(dict(u)), "courses": courses, "peer_pending": peer_pending})


# ---------------------------------------------------------------------------
# 元信息
# ---------------------------------------------------------------------------


@route("GET", "/api/meta", "public")
def api_meta(ctx):
    from . import experiments as EX

    demo_row = db.q1("SELECT value FROM settings WHERE key='demo_seed'")
    return ok(
        {
            "demo": bool(demo_row),
            "demo_seed_at": demo_row["value"] if demo_row else None,
            "languages": J.available_languages(),
            "verdicts": J.VERDICT_FULL,
            "aggregation_methods": [
                {"key": m, "label": AG.METHOD_LABELS[m]} for m in AG.METHODS
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
        }
    )


@route("GET", "/api/health", "public")
def api_health(ctx):
    return ok({"time": db.now(), "db": "sqlite", "judge": J.available_languages()})


# ---------------------------------------------------------------------------
# 课程与用户
# ---------------------------------------------------------------------------


@route("GET", "/api/courses")
def api_courses(ctx):
    u = ctx["user"]
    ids = user_course_ids(u)
    if not ids:
        return ok([])
    ph = ",".join("?" * len(ids))
    rows = uid_rows("SELECT c.* FROM courses c WHERE c.id IN (%s) ORDER BY c.id" % ph, ids)
    for c in rows:
        c["is_owner"] = c["teacher_id"] == u["id"]
        c["students"] = db.q1(
            "SELECT COUNT(*) c FROM course_members WHERE course_id=? AND role='student'",
            (c["id"],),
        )["c"]
        c["assignments"] = db.q1(
            "SELECT COUNT(*) c FROM assignments WHERE course_id=?", (c["id"],)
        )["c"]
        c["problems"] = db.q1(
            "SELECT COUNT(*) c FROM problems WHERE course_id=?", (c["id"],)
        )["c"]
        c["classes"] = uid_rows(
            "SELECT u.class_name, COUNT(*) c FROM course_members m JOIN users u ON u.id=m.user_id "
            "WHERE m.course_id=? AND m.role='student' GROUP BY u.class_name",
            (c["id"],),
        )
    return ok(rows)


@route("POST", "/api/courses", "teacher")
def api_course_create(ctx):
    """教师创建一门自己的课程（注册时也会自动创建一门）。"""
    b = ctx["body"] or {}
    name = (b.get("name") or "").strip()
    if not name:
        return err(400, "请填写课程名称")
    u = ctx["user"]
    cid = db.ex(
        "INSERT INTO courses(name,code,term,teacher_id,description,invite_code,created_at) "
        "VALUES(?,?,?,?,?,?,?)",
        (name, b.get("code") or None, b.get("term") or None, u["id"],
         b.get("description") or "", gen_invite_code("CRS"), db.now()),
    )
    db.ex(
        "INSERT OR IGNORE INTO course_members(course_id,user_id,role,class_id,joined_at) "
        "VALUES(?,?,?,?,?)",
        (cid, u["id"], u["role"], None, db.now()),
    )
    return ok(public_course(cid))


def public_course(cid: int) -> dict:
    c = dict(db.q1("SELECT * FROM courses WHERE id=?", (cid,)))
    c["students"] = db.q1(
        "SELECT COUNT(*) c FROM course_members WHERE course_id=? AND role='student'", (cid,))["c"]
    c["problems"] = db.q1("SELECT COUNT(*) c FROM problems WHERE course_id=?", (cid,))["c"]
    c["assignments"] = db.q1("SELECT COUNT(*) c FROM assignments WHERE course_id=?", (cid,))["c"]
    return c


@route("POST", "/api/courses/join")
def api_course_join(ctx):
    """用邀请码加入课程（也可以是某个班级的邀请码，加入时直接分班）。"""
    code = ((ctx["body"] or {}).get("invite_code") or "").strip().upper()
    if not code:
        return err(400, "请输入老师提供的邀请码")
    u = ctx["user"]
    course = db.q1("SELECT * FROM courses WHERE UPPER(invite_code)=?", (code,))
    cls = db.q1("SELECT * FROM classes WHERE UPPER(invite_code)=?", (code,))
    if not course and cls:
        course = db.q1("SELECT * FROM courses WHERE id=?", (cls["course_id"],))
    if not course:
        return err(404, "邀请码无效，请向任课老师确认")
    already = db.q1(
        "SELECT id FROM course_members WHERE course_id=? AND user_id=?", (course["id"], u["id"]))
    if already:
        db.ex(
            "UPDATE course_members SET class_id=COALESCE(?,class_id) WHERE id=?",
            (cls["id"] if cls else None, already["id"]),
        )
    else:
        db.ex(
            "INSERT INTO course_members(course_id,user_id,role,class_id,joined_at) VALUES(?,?,?,?,?)",
            (course["id"], u["id"], u["role"], cls["id"] if cls else None, db.now()),
        )
    if cls:
        db.ex("UPDATE users SET class_name=? WHERE id=?", (cls["name"], u["id"]))
    return ok({"course": public_course(course["id"]),
               "class_name": cls["name"] if cls else None})


@route("GET", "/api/users")
def api_users(ctx):
    role = ctx["query"].get("role")
    cid = active_course_id(ctx, ctx["query"].get("course_id"))
    if cid and ctx["query"].get("in_course"):
        rows = uid_rows(
            "SELECT u.* FROM course_members m JOIN users u ON u.id=m.user_id "
            "WHERE m.course_id=? AND (? IS NULL OR u.role=?) ORDER BY u.class_name,u.student_no,u.id",
            (cid, role, role))
    elif role:
        rows = uid_rows("SELECT * FROM users WHERE role=? ORDER BY id", (role,))
    else:
        rows = uid_rows("SELECT * FROM users ORDER BY id")
    return ok([public_user(r) for r in rows])


@route("POST", "/api/users", "teacher")
def api_user_create(ctx):
    """教师在自己的课程里新建学生（或助教）账号。"""
    b = ctx["body"] or {}
    cid = active_course_id(ctx, b.get("course_id") or ctx["query"].get("course_id"))
    if not cid:
        return err(400, "请先创建或加入一门课程")
    name = (b.get("name") or "").strip()
    username = (b.get("username") or "").strip()
    if not name or not username:
        return err(400, "姓名与账号都不能为空")
    if len(username) < 3:
        return err(400, "账号至少 3 位")
    if db.q1("SELECT id FROM users WHERE username=?", (username,)):
        return err(409, "账号 %s 已存在" % username)
    role = b.get("role") or "student"
    if role not in ("student", "ta"):
        return err(400, "只能创建学生或助教账号")
    pwd = b.get("password") or "123456"
    if len(pwd) < 6:
        return err(400, "密码至少 6 位")
    pw, salt = hash_password(pwd)
    class_id = b.get("class_id") or None
    cls = db.q1("SELECT * FROM classes WHERE id=? AND course_id=?", (class_id, cid)) if class_id else None
    uid = db.ex(
        "INSERT INTO users(username,email,password,salt,role,name,student_no,class_name,avatar,"
        "created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (username, b.get("email") or None, pw, salt, role, name,
         b.get("student_no") or None, cls["name"] if cls else None, name[0], db.now()),
    )
    db.ex(
        "INSERT OR IGNORE INTO course_members(course_id,user_id,role,class_id,joined_at) "
        "VALUES(?,?,?,?,?)",
        (cid, uid, role, cls["id"] if cls else None, db.now()),
    )
    return ok({"id": uid, "username": username, "name": name, "password": pwd,
               "class_name": cls["name"] if cls else None})


@route("POST", "/api/users/bulk", "teacher")
def api_users_bulk(ctx):
    """批量导入学生名单。

    请求体 ``rows`` 每项可以是 ``{name, username?, student_no?}``，
    也支持直接传字符串数组（``"张三,20260001"`` 或 ``"张三 20260001"``）。
    """
    b = ctx["body"] or {}
    cid = active_course_id(ctx, b.get("course_id"))
    if not cid:
        return err(400, "请先创建或加入一门课程")
    raw = b.get("rows") or []
    if not raw:
        return err(400, "请粘贴学生名单")
    default_pwd = b.get("password") or "123456"
    if len(default_pwd) < 6:
        return err(400, "默认密码至少 6 位")
    class_id = b.get("class_id") or None
    cls = db.q1("SELECT * FROM classes WHERE id=? AND course_id=?", (class_id, cid)) if class_id else None
    existing = {r["username"] for r in db.q("SELECT username FROM users")}
    pw, salt = hash_password(default_pwd)
    created, skipped = [], []
    for item in raw:
        if isinstance(item, str):
            parts = [x for x in item.replace("\t", ",").replace(" ", ",").split(",") if x.strip()]
            name = parts[0].strip() if parts else ""
            no = parts[1].strip() if len(parts) > 1 else ""
            username = parts[2].strip() if len(parts) > 2 else ""
        else:
            name = (item.get("name") or "").strip()
            no = (item.get("student_no") or "").strip()
            username = (item.get("username") or "").strip()
        if not name:
            continue
        username = username or (no if no else "s" + str(abs(hash(name)) % 10 ** 8))
        base, n = username, 2
        while username in existing:
            username = "%s%d" % (base, n)
            n += 1
        existing.add(username)
        uid = db.ex(
            "INSERT INTO users(username,email,password,salt,role,name,student_no,class_name,avatar,"
            "created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (username, None, pw, salt, "student", name, no or None,
             cls["name"] if cls else None, name[0], db.now()),
        )
        db.ex(
            "INSERT OR IGNORE INTO course_members(course_id,user_id,role,class_id,joined_at) "
            "VALUES(?,?,?,?,?)",
            (cid, uid, "student", cls["id"] if cls else None, db.now()),
        )
        created.append({"id": uid, "name": name, "username": username, "student_no": no})
    if not created:
        return err(400, "没有解析出有效的名单行")
    return ok({"created": created, "count": len(created),
               "password": default_pwd, "class_name": cls["name"] if cls else None,
               "skipped": skipped})


@route("GET", "/api/users/{id}")
def api_user(ctx):
    u = db.q1("SELECT * FROM users WHERE id=?", (ctx["params"]["id"],))
    return ok(public_user(dict(u))) if u else err(404, "用户不存在")


# ---------------------------------------------------------------------------
# 题库
# ---------------------------------------------------------------------------


@route("GET", "/api/problems")
def api_problems(ctx):
    q = ctx["query"]
    sql = "SELECT * FROM problems WHERE 1=1"
    args = []
    cid = active_course_id(ctx, q.get("course_id"))
    if cid:
        sql += " AND course_id=?"
        args.append(cid)
    if q.get("type"):
        sql += " AND type=?"
        args.append(q["type"])
    if q.get("topic"):
        sql += " AND topics LIKE ?"
        args.append("%" + q["topic"] + "%")
    if q.get("chapter"):
        sql += " AND chapter=?"
        args.append(q["chapter"])
    if q.get("q"):
        sql += " AND (title LIKE ? OR tags LIKE ?)"
        args += ["%" + q["q"] + "%", "%" + q["q"] + "%"]
    sql += " ORDER BY id"
    rows = uid_rows(sql, args)
    for p in rows:
        p["topics"] = jload(p["topics"], [])
        p["tags"] = jload(p["tags"], [])
        p["rubric"] = jload(p["rubric"], [])
        p["samples"] = jload(p["samples"], [])
        p["n_cases"] = db.q1(
            "SELECT COUNT(*) c FROM test_cases WHERE problem_id=?", (p["id"],))["c"]
        p["submit_count"] = db.q1(
            "SELECT COUNT(*) c FROM submissions WHERE problem_id=?", (p["id"],))["c"]
        p["ac_count"] = db.q1(
            "SELECT COUNT(*) c FROM submissions WHERE problem_id=? AND verdict='Accepted'",
            (p["id"],))["c"]
        p["ac_rate"] = round(p["ac_count"] / p["submit_count"], 4) if p["submit_count"] else 0.0
        st = db.q1(
            "SELECT COUNT(DISTINCT user_id) c FROM submissions WHERE problem_id=?", (p["id"],))["c"]
        p["student_count"] = st
        p["pass_rate"] = round(p["ac_count"] / st, 4) if st else 0.0
    return ok(rows)


@route("GET", "/api/problems/{id}")
def api_problem(ctx):
    pid = ctx["params"]["id"]
    p = db.q1("SELECT * FROM problems WHERE id=?", (pid,))
    if not p:
        return err(404, "题目不存在")
    d = dict(p)
    d["topics"] = jload(d["topics"], [])
    d["tags"] = jload(d["tags"], [])
    d["rubric"] = jload(d["rubric"], [])
    d["samples"] = jload(d["samples"], [])
    cases = uid_rows(
        "SELECT * FROM test_cases WHERE problem_id=? ORDER BY order_index,id", (pid,))
    d["n_test_cases"] = len(cases)
    d["hidden_count"] = sum(1 for c in cases if not c["is_sample"])
    if is_teacher(ctx["user"]):
        d["test_cases"] = cases
    else:
        d["test_cases"] = [dict(c) for c in cases if c["is_sample"]]
    u = ctx["user"]["id"]
    d["my_submissions"] = uid_rows(
        "SELECT id,verdict,score,time_ms,memory_kb,language,submitted_at,attempt_no "
        "FROM submissions WHERE problem_id=? AND user_id=? ORDER BY id DESC LIMIT 20",
        (pid, u))
    best = db.q1(
        "SELECT MAX(score) s FROM submissions WHERE problem_id=? AND user_id=?", (pid, u))
    d["my_best"] = best["s"] if best else None
    d["solved"] = bool(db.q1(
        "SELECT id FROM submissions WHERE problem_id=? AND user_id=? AND verdict='Accepted' LIMIT 1",
        (pid, u)))
    return ok(d)


@route("POST", "/api/problems", "teacher")
def api_problem_create(ctx):
    b = ctx["body"]
    pid = db.ex(
        "INSERT INTO problems(course_id,title,type,difficulty,topics,statement,input_format,"
        "output_format,constraints,samples,time_limit_ms,memory_limit_mb,score,rubric,created_by,"
        "created_at,tags,chapter) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            active_course_id(ctx, b.get("course_id")),
            b.get("title") or "未命名题目", b.get("type") or "programming",
            int(b.get("difficulty") or 3), db.jdumps(b.get("topics") or []),
            b.get("statement") or "", b.get("input_format") or "",
            b.get("output_format") or "", b.get("constraints") or "",
            db.jdumps(b.get("samples") or []), int(b.get("time_limit_ms") or 1000),
            int(b.get("memory_limit_mb") or 256), int(b.get("score") or 100),
            db.jdumps(b.get("rubric") or []), ctx["user"]["id"], db.now(),
            db.jdumps(b.get("tags") or []),
            b.get("chapter") or None,
        ),
    )
    for i, tc in enumerate(b.get("test_cases") or []):
        db.ex(
            "INSERT INTO test_cases(problem_id,name,input,expected,is_sample,score,order_index) "
            "VALUES(?,?,?,?,?,?,?)",
            (pid, tc.get("name") or ("测试点 %d" % (i + 1)), tc.get("input") or "",
             tc.get("expected") or "", 1 if tc.get("is_sample") else 0,
             int(tc.get("score") or 10), i),
        )
    return ok({"id": pid})


@route("PUT", "/api/problems/{id}", "teacher")
def api_problem_update(ctx):
    pid = ctx["params"]["id"]
    b = ctx["body"]
    sets, args = [], []
    for k in ("title", "type", "difficulty", "statement", "input_format", "output_format",
              "constraints", "time_limit_ms", "memory_limit_mb", "score", "chapter"):
        if b.get(k) is not None:
            sets.append(k + "=?")
            args.append(b[k])
    for k in ("topics", "tags", "rubric", "samples"):
        if b.get(k) is not None:
            sets.append(k + "=?")
            args.append(db.jdumps(b[k]))
    if sets:
        args.append(pid)
        db.ex("UPDATE problems SET " + ",".join(sets) + " WHERE id=?", args)
    if b.get("test_cases") is not None:
        db.ex("DELETE FROM test_cases WHERE problem_id=?", (pid,))
        for i, tc in enumerate(b["test_cases"]):
            db.ex(
                "INSERT INTO test_cases(problem_id,name,input,expected,is_sample,score,order_index) "
                "VALUES(?,?,?,?,?,?,?)",
                (pid, tc.get("name") or ("测试点 %d" % (i + 1)), tc.get("input") or "",
                 tc.get("expected") or "", 1 if tc.get("is_sample") else 0,
                 int(tc.get("score") or 10), i),
            )
    return ok({"id": int(pid)})


@route("DELETE", "/api/problems/{id}", "teacher")
def api_problem_delete(ctx):
    pid = ctx["params"]["id"]
    db.ex("DELETE FROM submissions WHERE problem_id=?", (pid,))
    db.ex("DELETE FROM test_cases WHERE problem_id=?", (pid,))
    db.ex("DELETE FROM problems WHERE id=?", (pid,))
    return ok()


# ---------------------------------------------------------------------------
# 作业
# ---------------------------------------------------------------------------


def assignment_detail(aid, user):
    a = db.q1("SELECT * FROM assignments WHERE id=?", (aid,))
    if not a:
        return None
    d = dict(a)
    d["params"] = jload(d.get("params"), {})
    probs = uid_rows(
        "SELECT p.*, ap.score AS assign_score, ap.order_index FROM assignment_problems ap "
        "JOIN problems p ON p.id=ap.problem_id WHERE ap.assignment_id=? ORDER BY ap.order_index",
        (aid,))
    for p in probs:
        p["topics"] = jload(p["topics"], [])
        p["rubric"] = jload(p["rubric"], [])
        p["samples"] = jload(p["samples"], [])
        best = db.q1(
            "SELECT MAX(score) s FROM submissions WHERE problem_id=? AND user_id=?",
            (p["id"], user["id"]))
        p["my_best"] = best["s"] if best else None
        p["my_tries"] = db.q1(
            "SELECT COUNT(*) c FROM submissions WHERE problem_id=? AND user_id=?",
            (p["id"], user["id"]))["c"]
        last = db.q1(
            "SELECT verdict FROM submissions WHERE problem_id=? AND user_id=? ORDER BY id DESC LIMIT 1",
            (p["id"], user["id"]))
        p["my_verdict"] = last["verdict"] if last else None
        p["n_submit"] = db.q1(
            "SELECT COUNT(DISTINCT user_id) c FROM submissions WHERE problem_id=?", (p["id"],))["c"]
        p["ac_count"] = db.q1(
            "SELECT COUNT(DISTINCT user_id) c FROM submissions WHERE problem_id=? "
            "AND verdict='Accepted'", (p["id"],))["c"]
        if p["type"] != "programming":
            p["my_subjective"] = db.q1(
                "SELECT id,status,final_score FROM subjective_submissions WHERE assignment_id=? "
                "AND problem_id=? AND user_id=?", (aid, p["id"], user["id"]))
            p["n_subjective"] = db.q1(
                "SELECT COUNT(*) c FROM subjective_submissions WHERE assignment_id=? "
                "AND problem_id=?", (aid, p["id"]))["c"]
    d["problems"] = probs
    d["submitted_users"] = db.q1(
        "SELECT COUNT(DISTINCT user_id) c FROM submissions WHERE assignment_id=?", (aid,))["c"]
    d["subjective_users"] = db.q1(
        "SELECT COUNT(DISTINCT user_id) c FROM subjective_submissions WHERE assignment_id=?",
        (aid,))["c"]
    return d


@route("GET", "/api/assignments")
def api_assignments(ctx):
    q = ctx["query"]
    sql = "SELECT * FROM assignments WHERE 1=1"
    args = []
    cid = active_course_id(ctx, q.get("course_id"))
    if cid:
        sql += " AND course_id=?"
        args.append(cid)
    sql += " ORDER BY id DESC"
    rows = uid_rows(sql, args)
    u = ctx["user"]
    now = datetime.now()
    for a in rows:
        a["params"] = jload(a.get("params"), {})
        a["problems"] = uid_rows(
            "SELECT p.id,p.title,p.type,p.difficulty FROM assignment_problems ap "
            "JOIN problems p ON p.id=ap.problem_id WHERE ap.assignment_id=? ORDER BY ap.order_index",
            (a["id"],))
        a["problem_count"] = len(a["problems"])
        a["submissions"] = db.q1(
            "SELECT COUNT(*) c FROM submissions WHERE assignment_id=?", (a["id"],))["c"]
        a["submitted_users"] = db.q1(
            "SELECT COUNT(DISTINCT user_id) c FROM submissions WHERE assignment_id=?", (a["id"],))["c"]
        a["subjective_users"] = db.q1(
            "SELECT COUNT(DISTINCT user_id) c FROM subjective_submissions WHERE assignment_id=?",
            (a["id"],))["c"]
        a["students"] = db.q1(
            "SELECT COUNT(*) c FROM course_members WHERE course_id=? AND role='student'",
            (a["course_id"],))["c"]
        # 作业完成情况：通过人数与平均分（按每人的最高分统计）
        a["accepted_users"] = db.q1(
            "SELECT COUNT(DISTINCT user_id) c FROM submissions "
            "WHERE assignment_id=? AND verdict='Accepted'", (a["id"],))["c"]
        avg = db.q1(
            "SELECT AVG(best) v FROM (SELECT MAX(score) best FROM submissions "
            "WHERE assignment_id=? GROUP BY user_id, problem_id)", (a["id"],))
        a["avg_score"] = round(avg["v"], 1) if avg and avg["v"] is not None else None
        if a["peer_review"]:
            confirmed = (a.get("allocation_status") or "confirmed") == "confirmed"
            a["my_review_pending"] = db.q1(
                "SELECT COUNT(*) c FROM allocations WHERE assignment_id=? AND reviewer_id=? "
                "AND status='pending'", (a["id"], u["id"]))["c"]
            a["my_review_done"] = db.q1(
                "SELECT COUNT(*) c FROM allocations WHERE assignment_id=? AND reviewer_id=? "
                "AND status='done'", (a["id"], u["id"]))["c"]
            a["pending_reviews"] = 0 if not confirmed else db.q1(
                "SELECT COUNT(*) c FROM allocations WHERE assignment_id=? AND status='pending'",
                (a["id"],))["c"]
            a["review_total"] = db.q1(
                "SELECT COUNT(*) c FROM allocations WHERE assignment_id=?", (a["id"],))["c"]
            a["review_done"] = a["review_total"] - a["pending_reviews"]
            a["need_confirm"] = not confirmed and a["review_total"] > 0
        due = parse_dt(a["due_at"])
        a["overdue"] = bool(due and due < now)
    return ok(rows)


@route("GET", "/api/assignments/{id}")
def api_assignment(ctx):
    d = assignment_detail(int(ctx["params"]["id"]), ctx["user"])
    return ok(d) if d else err(404, "作业不存在")


@route("POST", "/api/assignments", "teacher")
def api_assignment_create(ctx):
    b = ctx["body"]
    aid = db.ex(
        "INSERT INTO assignments(course_id,title,description,type,start_at,due_at,review_due_at,"
        "reviews_per_submission,max_load,aggregation_method,allocate_method,params,status,peer_review,"
        "created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            active_course_id(ctx, b.get("course_id")),
            b.get("title") or "未命名作业", b.get("description") or "",
            b.get("type") or "mixed", b.get("start_at") or db.now(), b.get("due_at"),
            b.get("review_due_at"), int(b.get("reviews_per_submission") or 3),
            int(b.get("max_load") or 4), b.get("aggregation_method") or "reliability_em",
            b.get("allocate_method") or "mcmf", db.jdumps(b.get("params") or {}),
            b.get("status") or "published", 1 if b.get("peer_review") else 0,
            ctx["user"]["id"], db.now(),
        ),
    )
    for i, pid in enumerate(b.get("problem_ids") or []):
        db.ex(
            "INSERT OR IGNORE INTO assignment_problems(assignment_id,problem_id,score,order_index) "
            "VALUES(?,?,?,?)", (aid, pid, 100, i))
    return ok({"id": aid})


@route("PUT", "/api/assignments/{id}", "teacher")
def api_assignment_update(ctx):
    aid = ctx["params"]["id"]
    b = ctx["body"]
    sets, args = [], []
    for k in ("title", "description", "type", "start_at", "due_at", "review_due_at",
              "reviews_per_submission", "max_load", "aggregation_method",
              "allocate_method", "status"):
        if b.get(k) is not None:
            sets.append(k + "=?")
            args.append(b[k])
    if b.get("peer_review") is not None:
        sets.append("peer_review=?")
        args.append(1 if b["peer_review"] else 0)
    if b.get("params") is not None:
        sets.append("params=?")
        args.append(db.jdumps(b["params"]))
    if sets:
        args.append(aid)
        db.ex("UPDATE assignments SET " + ",".join(sets) + " WHERE id=?", args)
    if b.get("problem_ids") is not None:
        db.ex("DELETE FROM assignment_problems WHERE assignment_id=?", (aid,))
        for i, pid in enumerate(b["problem_ids"]):
            db.ex(
                "INSERT INTO assignment_problems(assignment_id,problem_id,score,order_index) "
                "VALUES(?,?,?,?)", (aid, pid, 100, i))
    return ok({"id": int(aid)})


# ---------------------------------------------------------------------------
# 代码提交与自动评测
# ---------------------------------------------------------------------------


def _problem_cases(pid, only_sample=False):
    sql = "SELECT * FROM test_cases WHERE problem_id=?"
    if only_sample:
        sql += " AND is_sample=1"
    sql += " ORDER BY order_index,id"
    return uid_rows(sql, (pid,))


@route("POST", "/api/submissions")
def api_submit(ctx):
    b = ctx["body"]
    pid = b.get("problem_id")
    code = b.get("source_code") or ""
    lang = b.get("language") or "cpp"
    p = db.q1("SELECT * FROM problems WHERE id=?", (pid,))
    if not p:
        return err(404, "题目不存在")
    if not code.strip():
        return err(400, "代码不能为空")
    warn = J.static_check(code, lang)
    cases = _problem_cases(pid)
    started = time.time()
    res = J.judge_submission(
        code, lang, cases, p["time_limit_ms"], p["memory_limit_mb"], p["score"])
    elapsed = round((time.time() - started) * 1000, 1)
    sid = db.ex(
        "INSERT INTO submissions(assignment_id,problem_id,user_id,language,source_code,submitted_at,"
        "status,verdict,score,time_ms,memory_kb,compile_message,attempt_no,detail,complexity) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            b.get("assignment_id"), pid, ctx["user"]["id"], lang, code, db.now(), "done",
            res["verdict"], res["score"], res.get("time_ms", 0), res.get("memory_kb", 0),
            res.get("compile_message") or "", 1,
            db.jdumps({
                "passed": res.get("passed"), "total_cases": res.get("total_cases"),
                "results": res.get("results"), "wall_ms": res.get("wall_ms"),
                "startup_overhead_ms": res.get("startup_overhead_ms"),
                "judge_ms": elapsed, "warnings": warn,
            }),
            None,
        ),
    )
    tries = db.q1(
        "SELECT COUNT(*) c FROM submissions WHERE problem_id=? AND user_id=?",
        (pid, ctx["user"]["id"]))["c"]
    db.ex("UPDATE submissions SET attempt_no=? WHERE id=?", (tries, sid))
    db.ex(
        "INSERT INTO events(user_id,course_id,type,payload,created_at) VALUES(?,?,?,?,?)",
        (ctx["user"]["id"], p["course_id"], "submit",
         db.jdumps({"problem_id": pid, "verdict": res["verdict"]}), db.now()))
    res["submission_id"] = sid
    res["attempt_no"] = tries
    res["judge_ms"] = elapsed
    res["warnings"] = warn
    return ok(res)


@route("POST", "/api/run")
def api_run(ctx):
    """只运行样例或自定义输入（不写入提交历史），用于学生调试。"""
    b = ctx["body"]
    pid = b.get("problem_id")
    p = db.q1("SELECT * FROM problems WHERE id=?", (pid,))
    if not p:
        return err(404, "题目不存在")
    if b.get("custom_input") is not None and b.get("custom_input") != "":
        cases = [{"id": -1, "name": "自定义输入", "input": b["custom_input"],
                  "expected": b.get("expected") or "", "score": 1}]
    else:
        cases = _problem_cases(pid, only_sample=True) or _problem_cases(pid)[:2]
    res = J.judge_submission(
        b.get("source_code") or "", b.get("language") or "cpp", cases,
        p["time_limit_ms"], p["memory_limit_mb"], 100)
    return ok(res)


@route("GET", "/api/submissions")
def api_submissions(ctx):
    q = ctx["query"]
    sql = (
        "SELECT s.id,s.assignment_id,s.problem_id,s.user_id,s.language,s.verdict,s.score,"
        "s.time_ms,s.memory_kb,s.attempt_no,s.submitted_at,s.review_score,"
        "p.title AS problem_title,"
        "u.name AS user_name,u.class_name FROM submissions s "
        "JOIN problems p ON p.id=s.problem_id JOIN users u ON u.id=s.user_id WHERE 1=1"
    )
    args = []
    if q.get("problem_id"):
        sql += " AND s.problem_id=?"
        args.append(q["problem_id"])
    if q.get("assignment_id"):
        sql += " AND s.assignment_id=?"
        args.append(q["assignment_id"])
    if q.get("user_id"):
        sql += " AND s.user_id=?"
        args.append(q["user_id"])
    elif not is_teacher(ctx["user"]):
        sql += " AND s.user_id=?"
        args.append(ctx["user"]["id"])
    if q.get("verdict"):
        sql += " AND s.verdict=?"
        args.append(q["verdict"])
    # 默认只显示当前账号所在课程的数据，避免跨课程串数据
    cid = active_course_id(ctx, q.get("course_id"))
    if cid:
        sql += " AND p.course_id=?"
        args.append(cid)
    sql += " ORDER BY s.id DESC LIMIT ?"
    args.append(int(q.get("limit") or 100))
    rows = uid_rows(sql, args)
    for r in rows:
        r["is_mine"] = r["user_id"] == ctx["user"]["id"]
    return ok(rows)


@route("GET", "/api/submissions/{id}")
def api_submission(ctx):
    sid = ctx["params"]["id"]
    s = db.q1(
        "SELECT s.*,p.title AS problem_title,p.time_limit_ms,p.memory_limit_mb,"
        "u.name AS user_name FROM submissions s JOIN problems p ON p.id=s.problem_id "
        "JOIN users u ON u.id=s.user_id WHERE s.id=?", (sid,))
    if not s:
        return err(404, "提交不存在")
    d = dict(s)
    d["detail"] = jload(d["detail"], {})
    d["test_results"] = uid_rows(
        "SELECT * FROM test_results WHERE submission_id=? ORDER BY id", (sid,))
    teacher = is_teacher(ctx["user"])
    owner = d["user_id"] == ctx["user"]["id"]
    if not teacher and not owner:
        d["source_code"] = "（其他同学的代码不可见）"
    # 代码互评结果：仅本人与教师可见，且评审截止后才公布
    if teacher or owner:
        reviews = uid_rows(
            "SELECT r.*, u.name AS reviewer_name FROM reviews r "
            "JOIN users u ON u.id=r.reviewer_id "
            "WHERE r.problem_id=? AND r.author_id=?",
            (d["problem_id"], d["user_id"]),
        )
        a = (db.q1("SELECT review_due_at FROM assignments WHERE id=?",
                   (d["assignment_id"],)) if d["assignment_id"] else None)
        end = parse_dt(a["review_due_at"]) if a else None
        published = bool(end and end < datetime.now())
        if teacher or published:
            d["peer_reviews"] = [
                {
                    "reviewer": (r["reviewer_name"] if teacher else anon_label(r["reviewer_id"])),
                    "total": r["total"], "scores": jload(r["scores"], {}),
                    "comment": r["comment"], "duration_sec": r["duration_sec"],
                    "submitted_at": r["submitted_at"],
                }
                for r in reviews
            ]
        else:
            d["peer_reviews"] = []
            d["peer_review_pending"] = (
                "评审尚未结束，结果将在互评截止后公布" if reviews else None
            )
    return ok(d)


@route("POST", "/api/submissions/{id}/rejudge", "teacher")
def api_rejudge(ctx):
    sid = ctx["params"]["id"]
    s = db.q1("SELECT * FROM submissions WHERE id=?", (sid,))
    if not s:
        return err(404, "提交不存在")
    p = db.q1("SELECT * FROM problems WHERE id=?", (s["problem_id"],))
    res = J.judge_submission(
        s["source_code"], s["language"], _problem_cases(s["problem_id"]),
        p["time_limit_ms"], p["memory_limit_mb"], p["score"])
    db.ex("DELETE FROM test_results WHERE submission_id=?", (sid,))
    for r in res.get("results") or []:
        db.ex(
            "INSERT INTO test_results(submission_id,test_case_id,name,verdict,time_ms,memory_kb,"
            "message,output) VALUES(?,?,?,?,?,?,?,?)",
            (sid, r["test_case_id"], r["name"], r["verdict"], r["time_ms"], r["memory_kb"],
             r["message"], (r.get("actual") or "")[:1000]))
    d = jload(s["detail"], {})
    d.update({"passed": res.get("passed"), "total_cases": res.get("total_cases"),
              "results": res.get("results"), "rejudged": True})
    db.ex(
        "UPDATE submissions SET verdict=?,score=?,time_ms=?,memory_kb=?,compile_message=?,detail=? "
        "WHERE id=?",
        (res["verdict"], res["score"], res.get("time_ms", 0), res.get("memory_kb", 0),
         res.get("compile_message") or "", db.jdumps(d), sid))
    res["submission_id"] = int(sid)
    return ok(res)


@route("POST", "/api/assignments/{id}/rejudge", "teacher")
def api_rejudge_assignment(ctx):
    aid = ctx["params"]["id"]
    subs = uid_rows("SELECT * FROM submissions WHERE assignment_id=? ORDER BY id", (aid,))
    done = []
    for s in subs[:80]:
        p = db.q1("SELECT * FROM problems WHERE id=?", (s["problem_id"],))
        res = J.judge_submission(
            s["source_code"], s["language"], _problem_cases(s["problem_id"]),
            p["time_limit_ms"], p["memory_limit_mb"], p["score"])
        db.ex(
            "UPDATE submissions SET verdict=?,score=?,time_ms=?,memory_kb=? WHERE id=?",
            (res["verdict"], res["score"], res.get("time_ms", 0), res.get("memory_kb", 0), s["id"]))
        done.append({"id": s["id"], "before": s["verdict"], "after": res["verdict"]})
    return ok({"rejudged": len(done), "changes": [d for d in done if d["before"] != d["after"]]})


@route("GET", "/api/submissions/stats/overview")
def api_submission_stats(ctx):
    q = ctx["query"]
    where, args = "WHERE 1=1", []
    cid = active_course_id(ctx, q.get("course_id"))
    if cid:
        where += " AND p.course_id=?"
        args.append(cid)
    if q.get("assignment_id"):
        where += " AND s.assignment_id=?"
        args.append(q["assignment_id"])
    rows = uid_rows(
        "SELECT s.verdict, COUNT(*) c FROM submissions s JOIN problems p ON p.id=s.problem_id "
        + where + " GROUP BY s.verdict", args)
    total = sum(r["c"] for r in rows)
    ac = next((r["c"] for r in rows if r["verdict"] == "Accepted"), 0)
    return ok({"total": total, "by_verdict": {r["verdict"]: r["c"] for r in rows},
               "ac_rate": round(ac / total, 4) if total else 0.0})


# ---------------------------------------------------------------------------
# 主观题提交与互评
# ---------------------------------------------------------------------------


@route("POST", "/api/subjective")
def api_subjective_submit(ctx):
    b = ctx["body"]
    aid, pid = b.get("assignment_id"), b.get("problem_id")
    content = b.get("content")
    if not aid or not pid:
        return err(400, "缺少作业或题目")
    existed = db.q1(
        "SELECT * FROM subjective_submissions WHERE assignment_id=? AND problem_id=? AND user_id=?",
        (aid, pid, ctx["user"]["id"]))
    if existed:
        db.ex(
            "UPDATE subjective_submissions SET content=?, status='submitted', updated_at=? WHERE id=?",
            (db.jdumps(content or {}), db.now(), existed["id"]))
        sid = existed["id"]
    else:
        sid = db.ex(
            "INSERT INTO subjective_submissions(assignment_id,problem_id,user_id,content,submitted_at,"
            "status,final_score,methods,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (aid, pid, ctx["user"]["id"], db.jdumps(content or {}), db.now(), "submitted",
             None, "{}", db.now()))
    db.ex(
        "INSERT INTO events(user_id,course_id,type,payload,created_at) VALUES(?,?,?,?,?)",
        (ctx["user"]["id"], None, "submit_subjective",
         db.jdumps({"assignment_id": aid, "problem_id": pid}), db.now()))
    return ok({"id": sid})


@route("GET", "/api/subjective")
def api_subjective_list(ctx):
    q = ctx["query"]
    sql = (
        "SELECT ss.*,p.title AS problem_title,p.rubric,p.type AS problem_type,"
        "a.title AS assignment_title FROM subjective_submissions ss "
        "JOIN problems p ON p.id=ss.problem_id JOIN assignments a ON a.id=ss.assignment_id WHERE 1=1"
    )
    args = []
    if q.get("assignment_id"):
        sql += " AND ss.assignment_id=?"
        args.append(q["assignment_id"])
    if q.get("problem_id"):
        sql += " AND ss.problem_id=?"
        args.append(q["problem_id"])
    if q.get("mine") or not is_teacher(ctx["user"]):
        sql += " AND ss.user_id=?"
        args.append(ctx["user"]["id"])
    sql += " ORDER BY ss.id DESC LIMIT 200"
    rows = uid_rows(sql, args)
    for r in rows:
        r["content"] = {k: v for k, v in jload(r["content"], {}).items() if not k.startswith("_")}
        r["methods"] = jload(r["methods"], {})
        r["rubric"] = jload(r["rubric"], [])
    return ok(rows)


@route("GET", "/api/subjective/{id}")
def api_subjective_detail(ctx):
    sid = ctx["params"]["id"]
    s = db.q1(
        "SELECT ss.*,p.title AS problem_title,p.rubric,u.name AS user_name "
        "FROM subjective_submissions ss JOIN problems p ON p.id=ss.problem_id "
        "JOIN users u ON u.id=ss.user_id WHERE ss.id=?", (sid,))
    if not s:
        return err(404, "提交不存在")
    d = dict(s)
    d["content"] = {k: v for k, v in jload(d["content"], {}).items() if not k.startswith("_")}
    d["methods"] = jload(d["methods"], {})
    d["rubric"] = jload(d["rubric"], [])
    is_owner = d["user_id"] == ctx["user"]["id"]
    teacher = is_teacher(ctx["user"])
    if not (is_owner or teacher):
        return err(403, "无权查看该提交")
    reviews = uid_rows(
        "SELECT * FROM reviews WHERE assignment_id=? AND problem_id=? AND author_id=?",
        (d["assignment_id"], d["problem_id"], d["user_id"]))
    if teacher:
        d["reviews"] = [
            dict(r, scores=jload(r["scores"], {}),
                 reviewer_name=(db.q1("SELECT name FROM users WHERE id=?", (r["reviewer_id"],))
                                or {"name": ""})["name"])
            for r in reviews
        ]
    else:
        d["reviews"] = [
            {"id": r["id"], "total": r["total"], "scores": jload(r["scores"], {}),
             "comment": r["comment"], "duration_sec": r["duration_sec"],
             "reviewer": anon_label(r["reviewer_id"])}
            for r in reviews
        ]
    a = db.q1("SELECT review_due_at,due_at FROM assignments WHERE id=?", (d["assignment_id"],))
    review_end = parse_dt(a["review_due_at"]) if a else None
    d["review_published"] = bool(review_end and review_end < datetime.now())
    if not teacher and not d["review_published"]:
        d["reviews"] = []
        d["final_score"] = None
        d["pending_reason"] = "评审尚未结束，为保证匿名与公平，结果将在评审截止后公布"
    return ok(d)


def _load_review_context(aid, pid=None):
    sql = ("SELECT r.*, u.name AS reviewer_name,u.class_name FROM reviews r "
           "JOIN users u ON u.id=r.reviewer_id WHERE r.assignment_id=?")
    args = [aid]
    if pid:
        sql += " AND r.problem_id=?"
        args.append(pid)
    return uid_rows(sql, args)


@route("POST", "/api/assignments/{id}/allocate", "teacher")
def api_allocate(ctx):
    """执行匿名互评任务分配（核心算法一的在线入口）。"""
    aid = int(ctx["params"]["id"])
    b = ctx["body"] or {}
    a = db.q1("SELECT * FROM assignments WHERE id=?", (aid,))
    if not a:
        return err(404, "作业不存在")
    method = b.get("method") or a["allocate_method"] or "mcmf"
    k = int(b.get("reviews_per_submission") or a["reviews_per_submission"] or 3)
    maxload = int(b.get("max_load") or a["max_load"] or 4)
    params = AS.AllocationParams(
        reviews_per_submission=k,
        max_load=maxload,
        prev_pair_penalty=float(b.get("prev_pair_penalty") or 3.0),
        cross_group_bonus=float(b.get("cross_group_bonus") or 4.0),
        prefer_cross_class=bool(b.get("prefer_cross_class", True)),
        reciprocity_penalty=float(b.get("reciprocity_penalty") or 2.5),
        variety_weight=float(b.get("variety_weight") or 0.8),
        seed=int(b.get("seed") or 2026),
        use_local_search=(method != "mcmf"),
    )
    prev_rows = uid_rows(
        "SELECT author_id,reviewer_id,COUNT(*) c FROM allocations WHERE assignment_id<>? "
        "GROUP BY author_id,reviewer_id", (aid,))
    prev_pairs = {(r["author_id"], r["reviewer_id"]): r["c"] for r in prev_rows}
    studs = uid_rows(
        "SELECT u.* FROM course_members m JOIN users u ON u.id=m.user_id "
        "WHERE m.course_id=? AND m.role='student' ORDER BY u.id", (a["course_id"],))
    klass = {s["id"]: (s["class_name"] or "未分班") for s in studs}
    probs = uid_rows(
        "SELECT p.* FROM assignment_problems ap JOIN problems p ON p.id=ap.problem_id "
        "WHERE ap.assignment_id=? ORDER BY ap.order_index", (aid,))
    t0 = time.perf_counter()
    report = []
    for prob in probs:
        # 主观题以便提交为作者来源；编程题以「有提交记录的学生」为作者来源，
        # 这样代码互评与主观题互评走同一套分配/聚合/异常检测流程。
        if prob["type"] == "programming":
            authors = [
                r["user_id"] for r in uid_rows(
                    # 代码互评的对象是「该学生在这道题上的提交」，不限于本作业——
                    # 教师可以对已经练过的题目再组织一轮代码互评
                    "SELECT DISTINCT user_id FROM submissions WHERE problem_id=? "
                    "ORDER BY user_id",
                    (prob["id"],),
                )
            ]
        else:
            authors = [
                r["user_id"] for r in uid_rows(
                    "SELECT user_id FROM subjective_submissions "
                    "WHERE assignment_id=? AND problem_id=?",
                    (aid, prob["id"]),
                )
            ]
        if len(authors) < 2:
            continue
        if method == "random":
            res = AS.allocate_random(authors, authors, klass, params, prev_pairs)
        elif method == "greedy":
            res = AS.allocate_greedy(authors, authors, klass, params, prev_pairs)
        else:
            res = AS.allocate_mcmf(authors, authors, klass, params, prev_pairs)
        el = round((time.perf_counter() - t0) * 1000, 2)
        metrics = AS.evaluate_allocation(res.allocations, authors, authors, klass, prev_pairs, k)
        metrics["elapsed_ms"] = el
        db.ex("DELETE FROM allocations WHERE assignment_id=? AND problem_id=?", (aid, prob["id"]))
        for (au, rv) in res.allocations:
            db.ex(
                "INSERT OR IGNORE INTO allocations(assignment_id,problem_id,author_id,reviewer_id,"
                "status,round,weight,is_anomaly,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (aid, prob["id"], au, rv, "pending", 1, 1.0, 0, db.now()))
        report.append({"problem_id": prob["id"], "problem_title": prob["title"],
                       "method": res.method, "stats": res.stats, "metrics": metrics})
        db.ex(
            "INSERT INTO experiments(name,params,result,elapsed_ms,created_at) VALUES(?,?,?,?,?)",
            ("allocate", db.jdumps({"assignment_id": aid, "problem_id": prob["id"], **b}),
             db.jdumps({"metrics": metrics, "stats": res.stats}), el, db.now()))
    # 分配结果先进入「待教师确认」，教师确认后学生才看得到评审任务
    db.ex("UPDATE assignments SET status='reviewing', allocation_status='draft' WHERE id=?", (aid,))
    return ok({
        "report": report,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
        "allocation_status": "draft",
        "need_confirm": True,
    })


@route("POST", "/api/assignments/{id}/publish-allocation", "teacher")
def api_publish_allocation(ctx):
    """教师确认本轮互评分配后发布：学生端才出现评审任务。"""
    aid = int(ctx["params"]["id"])
    a = db.q1("SELECT * FROM assignments WHERE id=?", (aid,))
    if not a:
        return err(404, "作业不存在")
    total = db.q1("SELECT COUNT(*) c FROM allocations WHERE assignment_id=?", (aid,))["c"]
    if not total:
        return err(400, "还没有分配结果，请先执行「重新分配」")
    db.ex("UPDATE assignments SET allocation_status='confirmed', status='reviewing' WHERE id=?", (aid,))
    db.ex(
        "INSERT INTO events(user_id,course_id,type,payload,created_at) VALUES(?,?,?,?,?)",
        (ctx["user"]["id"], a["course_id"], "allocation_published",
         db.jdumps({"assignment_id": aid, "allocations": total}), db.now()),
    )
    return ok({"assignment_id": aid, "allocation_status": "confirmed", "allocations": total})


@route("POST", "/api/assignments/{id}/allocation/adjust", "teacher")
def api_adjust_allocation(ctx):
    """人工调整某一份作业的评审人：换人 / 加人 / 减人。

    请求体：
        problem_id, author_id        必填，定位「谁的哪道题」
        remove_reviewer_id           可选，先移除某个评审者
        add_reviewer_id              可选，再加入新的评审者（禁止自评、禁止重复）
    """
    aid = int(ctx["params"]["id"])
    b = ctx["body"] or {}
    a = db.q1("SELECT * FROM assignments WHERE id=?", (aid,))
    if not a:
        return err(404, "作业不存在")
    problem_id = b.get("problem_id")
    author_id = b.get("author_id")
    if not problem_id or not author_id:
        return err(400, "缺少 problem_id / author_id")
    problem_id, author_id = int(problem_id), int(author_id)

    mine = uid_rows(
        "SELECT * FROM allocations WHERE assignment_id=? AND problem_id=? AND author_id=? "
        "ORDER BY id", (aid, problem_id, author_id))
    if not mine:
        return err(404, "找不到该作业的分配记录")

    remove_id = b.get("remove_reviewer_id")
    if remove_id:
        rows = [r for r in mine if int(r["reviewer_id"]) == int(remove_id)]
        if not rows:
            return err(400, "该评审者不在当前分配里")
        if any(r["status"] == "done" for r in rows):
            return err(400, "该评审者已经完成评审，不能直接移除；请改用「重新分配」")
        for r in rows:
            db.ex("DELETE FROM allocations WHERE id=?", (r["id"],))

    add_id = b.get("add_reviewer_id")
    if add_id:
        add_id = int(add_id)
        if add_id == author_id:
            return err(400, "不能把自己分配给自己评审")
        member = db.q1(
            "SELECT id FROM course_members WHERE course_id=? AND user_id=? AND role='student'",
            (a["course_id"], add_id))
        if not member:
            return err(400, "该学生不在本课程中")
        current = db.q1(
            "SELECT id FROM allocations WHERE assignment_id=? AND problem_id=? AND author_id=? "
            "AND reviewer_id=?", (aid, problem_id, author_id, add_id))
        if current:
            return err(400, "该评审者已经在名单里")
        load = db.q1(
            "SELECT COUNT(*) c FROM allocations WHERE assignment_id=? AND reviewer_id=?",
            (aid, add_id))["c"]
        if load >= int(a["max_load"] or 4):
            return err(400, "该学生的工作量已达上限 %d 份" % int(a["max_load"] or 4))
        db.ex(
            "INSERT OR IGNORE INTO allocations(assignment_id,problem_id,author_id,reviewer_id,"
            "status,round,weight,is_anomaly,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (aid, problem_id, author_id, add_id, "pending", 1, 1.0, 0, db.now()))

    rows = uid_rows(
        "SELECT al.id, al.reviewer_id, u.name AS reviewer_name, u.class_name, al.status "
        "FROM allocations al JOIN users u ON u.id=al.reviewer_id "
        "WHERE al.assignment_id=? AND al.problem_id=? AND al.author_id=? ORDER BY al.id",
        (aid, problem_id, author_id))
    # 教师手工调整过分配 → 必须重新确认发布
    db.ex("UPDATE assignments SET allocation_status='draft' WHERE id=?", (aid,))
    return ok({
        "assignment_id": aid, "problem_id": problem_id, "author_id": author_id,
        "reviewers": rows, "count": len(rows),
        # 只要教师动了分配，就需要重新确认后发布
        "allocation_status": "draft",
    })


@route("GET", "/api/assignments/{id}/allocations", "teacher")
def api_allocations(ctx):
    aid = ctx["params"]["id"]
    rows = uid_rows(
        "SELECT al.*, au.name AS author_name, au.class_name AS author_class, "
        "rv.name AS reviewer_name, rv.class_name AS reviewer_class "
        "FROM allocations al JOIN users au ON au.id=al.author_id "
        "JOIN users rv ON rv.id=al.reviewer_id WHERE al.assignment_id=? ORDER BY al.id", (aid,))
    loads = {}
    for r in rows:
        r["anon"] = anon_label(r["author_id"])
        loads[r["reviewer_id"]] = loads.get(r["reviewer_id"], 0) + 1
    return ok({
        "allocations": rows,
        "stats": {
            "total": len(rows),
            "done": sum(1 for r in rows if r["status"] == "done"),
            "pending": sum(1 for r in rows if r["status"] == "pending"),
            "reviewers": len(loads),
            "load_min": min(loads.values()) if loads else 0,
            "load_max": max(loads.values()) if loads else 0,
        },
    })


@route("GET", "/api/reviews/mine")
def api_my_reviews(ctx):
    uid = ctx["user"]["id"]
    rows = uid_rows(
        "SELECT al.id AS allocation_id, al.assignment_id, al.problem_id, al.status, al.weight, "
        "al.author_id, p.title AS problem_title, p.type AS problem_type, p.rubric, "
        "a.title AS assignment_title, a.review_due_at, a.reviews_per_submission, "
        "a.allocation_status "
        "FROM allocations al JOIN problems p ON p.id=al.problem_id "
        "JOIN assignments a ON a.id=al.assignment_id "
        "WHERE al.reviewer_id=? AND a.allocation_status='confirmed' "
        "ORDER BY al.status, al.assignment_id DESC, al.id", (uid,))
    for r in rows:
        r["rubric"] = [x for x in jload(r["rubric"], []) if isinstance(x, dict) and "key" in x]
        r["author"] = anon_label(r["author_id"])
        rv = db.q1("SELECT * FROM reviews WHERE allocation_id=?", (r["allocation_id"],))
        r["my_review"] = (
            {"total": rv["total"], "comment": rv["comment"], "scores": jload(rv["scores"], {})}
            if rv else None)
    return ok(rows)


@route("GET", "/api/reviews/task/{allocation_id}")
def api_review_task(ctx):
    al = db.q1(
        "SELECT al.*,p.title AS problem_title,p.statement,p.rubric,p.type AS problem_type,"
        "a.title AS assignment_title,a.review_due_at,a.allocation_status FROM allocations al "
        "JOIN problems p ON p.id=al.problem_id JOIN assignments a ON a.id=al.assignment_id "
        "WHERE al.id=?", (ctx["params"]["allocation_id"],))
    if not al:
        return err(404, "评审任务不存在")
    teacher = is_teacher(ctx["user"])
    if al["reviewer_id"] != ctx["user"]["id"] and not teacher:
        return err(403, "这不是分配给你的评审任务")
    # 教师确认发布前，学生看不到评审对象
    if al["allocation_status"] != "confirmed" and not teacher:
        return err(403, "教师尚未确认本轮互评分配，请稍后再试")
    rubric = jload(al["rubric"], [])
    sections = []
    if rubric and isinstance(rubric[0], dict) and "sections" in rubric[0]:
        sections = rubric[0]["sections"]
    base = {
        "allocation_id": al["id"], "assignment_id": al["assignment_id"],
        "assignment_title": al["assignment_title"], "problem_id": al["problem_id"],
        "problem_title": al["problem_title"], "problem_statement": al["statement"],
        "problem_type": al["problem_type"],
        "author": al["author_id"] if teacher else anon_label(al["author_id"]),
        "rubric": [r for r in rubric if isinstance(r, dict) and "key" in r],
        "status": al["status"], "review_due_at": al["review_due_at"],
    }
    # 编程题：把作者最好的一次提交作为评审对象（附自动评测结论，便于评审者判断）
    if al["problem_type"] == "programming":
        sub = db.q1(
            "SELECT s.* FROM submissions s WHERE s.problem_id=? AND s.user_id=? "
            "ORDER BY (s.verdict='Accepted') DESC, s.score DESC, s.id DESC LIMIT 1",
            (al["problem_id"], al["author_id"]),
        )
        detail = jload(sub["detail"], {}) if sub else {}
        base.update({
            "kind": "code",
            "code": sub["source_code"] if sub else "",
            "language": sub["language"] if sub else "cpp",
            "verdict": sub["verdict"] if sub else None,
            "auto_score": sub["score"] if sub else None,
            "time_ms": sub["time_ms"] if sub else None,
            "memory_kb": sub["memory_kb"] if sub else None,
            "attempt_no": sub["attempt_no"] if sub else None,
            "submitted_at": sub["submitted_at"] if sub else None,
            "passed": detail.get("passed"),
            "total_cases": detail.get("total_cases"),
            "sections": [], "content": {},
            "estimated_minutes": 10,
            "rubric": [r for r in rubric if isinstance(r, dict) and "key" in r]
                      or default_code_rubric(),
        })
        return ok(base)
    ss = db.q1(
        "SELECT * FROM subjective_submissions WHERE assignment_id=? AND problem_id=? AND user_id=?",
        (al["assignment_id"], al["problem_id"], al["author_id"]))
    content = jload(ss["content"], {}) if ss else {}
    base.update({
        "kind": "text",
        "content": {k: v for k, v in content.items() if not k.startswith("_")},
        "sections": sections,
        "estimated_minutes": 12,
    })
    return ok(base)


@route("POST", "/api/reviews/{allocation_id}")
def api_submit_review(ctx):
    al = db.q1("SELECT * FROM allocations WHERE id=?", (ctx["params"]["allocation_id"],))
    if not al:
        return err(404, "评审任务不存在")
    if al["reviewer_id"] != ctx["user"]["id"] and not is_teacher(ctx["user"]):
        return err(403, "无权提交该评审")
    b = ctx["body"]
    scores = b.get("scores") or {}
    comment = (b.get("comment") or "").strip()
    if not scores:
        return err(400, "请先完成评分细则")
    total = sum(float(v or 0) for v in scores.values())
    existed = db.q1("SELECT id FROM reviews WHERE allocation_id=?", (al["id"],))
    if existed:
        db.ex(
            "UPDATE reviews SET scores=?,total=?,comment=?,duration_sec=?,submitted_at=? WHERE id=?",
            (db.jdumps(scores), round(total, 2), comment, b.get("duration_sec"),
             db.now(), existed["id"]))
    else:
        db.ex(
            "INSERT INTO reviews(allocation_id,assignment_id,problem_id,submission_id,reviewer_id,"
            "author_id,scores,total,comment,duration_sec,started_at,submitted_at,flagged,flag_reason) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (al["id"], al["assignment_id"], al["problem_id"], None, al["reviewer_id"],
             al["author_id"], db.jdumps(scores), round(total, 2), comment,
             b.get("duration_sec"), b.get("started_at"), db.now(), 0, None))
    db.ex("UPDATE allocations SET status='done' WHERE id=?", (al["id"],))
    db.ex(
        "INSERT INTO events(user_id,course_id,type,payload,created_at) VALUES(?,?,?,?,?)",
        (ctx["user"]["id"], None, "submit_review",
         db.jdumps({"allocation_id": al["id"], "total": round(total, 2)}), db.now()))
    return ok({"total": round(total, 2)})


@route("POST", "/api/assignments/{id}/aggregate", "teacher")
def api_aggregate(ctx):
    """执行评分聚合（核心算法二）与异常检测（核心算法三）。"""
    aid = int(ctx["params"]["id"])
    b = ctx["body"] or {}
    methods = b.get("methods") or AG.METHODS
    probs = uid_rows(
        "SELECT p.* FROM assignment_problems ap JOIN problems p ON p.id=ap.problem_id "
        "WHERE ap.assignment_id=? ORDER BY ap.order_index", (aid,))
    report = []
    for prob in probs:
        reviews = _load_review_context(aid, prob["id"])
        if not reviews:
            continue
        rl = [
            {"submission_id": r["author_id"], "reviewer_id": r["reviewer_id"],
             "score": r["total"], "author_id": r["author_id"],
             "duration_sec": r["duration_sec"], "rubric": jload(r["scores"], {})}
            for r in reviews
        ]
        per_method = {
            m: {str(k): round(v, 2) for k, v in AG.aggregate(rl, m)["scores"].items()}
            for m in methods
        }
        em = AG.aggregate(rl, b.get("method") or "reliability_em")
        conn = db.get_conn()
        for uid, sc in em["scores"].items():
            if prob["type"] == "programming":
                # 代码互评：把聚合分写回该作者最好的一次提交
                conn.execute(
                    "UPDATE submissions SET review_score=?, review_methods=? WHERE id=("
                    "  SELECT id FROM submissions WHERE problem_id=? AND user_id=? "
                    "  ORDER BY (verdict='Accepted') DESC, score DESC, id DESC LIMIT 1)",
                    (round(sc, 2), db.jdumps(per_method), prob["id"], uid),
                )
            else:
                conn.execute(
                    "UPDATE subjective_submissions SET status='done', final_score=?, methods=?, "
                    "updated_at=? WHERE assignment_id=? AND problem_id=? AND user_id=?",
                    (round(sc, 2), db.jdumps(per_method), db.now(), aid, prob["id"], uid))
        conn.commit()
        det = AN.detect(rl)
        conn.execute(
            "DELETE FROM anomalies WHERE assignment_id=? AND reviewer_id IN "
            "(SELECT reviewer_id FROM reviews WHERE assignment_id=? AND problem_id=?)",
            (aid, aid, prob["id"]))
        for a in det["anomalies"]:
            conn.execute(
                "INSERT INTO anomalies(assignment_id,type,level,reviewer_id,submission_id,title,"
                "detail,evidence,suggestion,status,handled_by,note,detected_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (aid, a["type"], a["level"], a.get("reviewer_id"), a.get("submission_id"),
                 a["title"], a["detail"], db.jdumps(a.get("evidence", {})), a["suggestion"],
                 "open", None, None, db.now()))
        conn.commit()
        rows = []
        for uid in sorted(em["scores"]):
            mine = [r["total"] for r in reviews if r["author_id"] == uid]
            rows.append({
                "author_id": uid, "author": anon_label(uid),
                "methods": {m: per_method[m].get(str(uid)) for m in methods},
                "final": round(em["scores"][uid], 2),
                "n_reviews": len(mine),
                "spread": round((max(mine) - min(mine)) if mine else 0, 2),
            })
        report.append({
            "problem_id": prob["id"], "problem_title": prob["title"], "results": rows,
            "comparison": AG.evaluate_aggregation(rl, None, methods),
            "reviewer_bias": {str(k): round(v, 3) for k, v in em["detail"]["bias"].items()},
            "reviewer_reliability": {
                str(k): round(v, 3) for k, v in em["detail"]["reliability"].items()},
            "sigma": em["detail"].get("sigma"), "n_anomalies": len(det["anomalies"]),
        })
    return ok({"report": report})


@route("GET", "/api/assignments/{id}/review-results", "teacher")
def api_review_results(ctx):
    aid = ctx["params"]["id"]
    probs = uid_rows(
        "SELECT p.* FROM assignment_problems ap JOIN problems p ON p.id=ap.problem_id "
        "WHERE ap.assignment_id=? ORDER BY ap.order_index", (aid,))
    out = []
    for prob in probs:
        reviews = _load_review_context(aid, prob["id"])
        if not reviews:
            continue
        rl = [
            {"submission_id": r["author_id"], "reviewer_id": r["reviewer_id"],
             "score": r["total"], "author_id": r["author_id"],
             "duration_sec": r["duration_sec"], "rubric": jload(r["scores"], {})}
            for r in reviews
        ]
        em = AG.aggregate(rl, "reliability_em")
        rows = []
        for uid in sorted(em["scores"]):
            u = db.q1("SELECT name,class_name,student_no FROM users WHERE id=?", (uid,)) or {}
            mine = [r["total"] for r in reviews if r["author_id"] == uid]
            # 谁评了这份作业、分别给了多少分、写了什么意见——教师审核时要逐条看
            details = []
            for r in reviews:
                if r["author_id"] != uid:
                    continue
                details.append({
                    "reviewer_id": r["reviewer_id"],
                    "reviewer_name": dict(db.q1(
                        "SELECT name FROM users WHERE id=?", (r["reviewer_id"],)) or {}).get("name"),
                    "reviewer_class": dict(db.q1(
                        "SELECT class_name FROM users WHERE id=?", (r["reviewer_id"],)) or {}).get("class_name"),
                    "total": round(r["total"], 2) if r["total"] is not None else None,
                    "scores": jload(r["scores"], {}),
                    "comment": r["comment"],
                    "duration_sec": r["duration_sec"],
                    "submitted_at": r["submitted_at"],
                    "flagged": r["flagged"],
                })
            details.sort(key=lambda d: -(d["total"] or 0))
            rows.append({
                "user_id": uid, "name": u["name"], "class_name": u["class_name"],
                "student_no": u["student_no"], "score": round(em["scores"][uid], 2),
                "raw": mine, "n_reviews": len(mine),
                "spread": round((max(mine) - min(mine)) if mine else 0, 2),
                "details": details,
            })
        rows.sort(key=lambda r: -r["score"])
        out.append({
            "problem_id": prob["id"], "problem_title": prob["title"], "rows": rows,
            "comparison": AG.evaluate_aggregation(rl, None),
            "reviewer_stats": [
                {"reviewer_id": int(rid),
                 "name": dict(db.q1("SELECT name FROM users WHERE id=?", (rid,)) or {}).get("name"),
                 "bias": round(b, 3),
                 "reliability": round(em["detail"]["reliability"].get(int(rid), 1.0), 3),
                 "n": sum(1 for r in reviews if r["reviewer_id"] == int(rid))}
                for rid, b in sorted(em["detail"]["bias"].items(), key=lambda kv: -abs(kv[1]))
            ],
        })
    return ok(out)


# 注册扩展接口（学习分析、异常检测、实验台、看板）
from . import api_ext  # noqa: E402,F401

# 班级管理接口
from . import api_classes  # noqa: E402,F401

# 课件库与章节接口
from . import api_materials  # noqa: E402,F401
