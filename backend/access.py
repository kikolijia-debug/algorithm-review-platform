"""课程资源授权与学生响应脱敏。所有 HTTP 路由共用同一套规则。"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime

from . import db


class APIError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


def require_course(user, cid, teaching=False):
    from .api import user_course_ids
    if not cid or int(cid) not in user_course_ids(user):
        raise APIError(403, "无权访问该课程的数据")
    if teaching:
        owner = db.q1("SELECT id FROM courses WHERE id=? AND teacher_id=?", (cid, user["id"]))
        staff = db.q1("SELECT id FROM course_members WHERE course_id=? AND user_id=? "
                     "AND role IN ('teacher','ta')", (cid, user["id"]))
        if not (owner or staff):
            raise APIError(403, "只有本课程教师或助教可以执行此操作")


def resource(user, table, ident, teaching=False):
    if table == "submissions":
        row = db.q1("SELECT s.*,p.course_id FROM submissions s JOIN problems p "
                    "ON p.id=s.problem_id WHERE s.id=?", (ident,))
    elif table in ("allocations", "subjective_submissions", "anomalies"):
        row = db.q1(f"SELECT r.*,a.course_id FROM {table} r JOIN assignments a "
                    "ON a.id=r.assignment_id WHERE r.id=?", (ident,))
    else:
        row = db.q1(f"SELECT * FROM {table} WHERE id=?", (ident,))
    if not row:
        raise APIError(404, "记录不存在")
    require_course(user, row["course_id"], teaching)
    return row


def published(aid):
    from .api import parse_dt
    a = db.q1("SELECT review_due_at,allocation_status FROM assignments WHERE id=?", (aid,))
    end = parse_dt(a["review_due_at"]) if a else None
    return bool(a and a["allocation_status"] == "confirmed" and end and end <= datetime.now())


def validate_submission(ctx, pid, aid=None, subjective=False):
    from .api import is_teacher, parse_dt
    user = ctx["user"]
    p = resource(user, "problems", pid)
    if subjective == (p["type"] == "programming"):
        raise APIError(400, "题目类型与提交方式不匹配")
    if not aid:
        if subjective:
            raise APIError(400, "请先选择所属作业")
        return p
    a = resource(user, "assignments", aid)
    if not db.q1("SELECT 1 FROM assignment_problems WHERE assignment_id=? AND problem_id=?", (aid, pid)):
        raise APIError(400, "该题目不属于本次作业")
    if a["course_id"] != p["course_id"]:
        raise APIError(400, "作业与题目不属于同一课程")
    if not is_teacher(user):
        now = datetime.now()
        start, due = parse_dt(a["start_at"]), parse_dt(a["due_at"])
        if a["status"] != "published":
            raise APIError(403, "本次作业当前不接受提交")
        if start and start > now:
            raise APIError(403, "作业尚未开放")
        if due and due < now:
            raise APIError(403, "作业已截止，请联系教师延长截止时间")
    return p


def authorize(path, auth, ctx):
    from .api import is_teacher
    user, b, q, params = ctx["user"], ctx["body"], ctx["query"], ctx["params"]
    if not user:
        if auth != "public":
            raise APIError(401, "请先登录")
        return
    if auth == "teacher" and not is_teacher(user):
        raise APIError(403, "该操作仅教师/助教可用")
    for source in (q, b):
        if source.get("course_id"):
            require_course(user, source["course_id"], auth == "teacher")
    tables = {"problems": "problems", "assignments": "assignments", "classes": "classes",
              "materials": "materials", "notices": "notices", "submissions": "submissions",
              "subjective": "subjective_submissions", "anomalies": "anomalies"}
    parts = path.strip("/").split("/")
    if len(parts) > 2 and parts[1] in tables and "id" in params:
        row = resource(user, tables[parts[1]], params["id"], auth == "teacher")
        if parts[1] in ("submissions", "subjective") and not is_teacher(user) and row["user_id"] != user["id"]:
            raise APIError(403, "只能查看自己的提交")
        if parts[1] == "assignments" and not is_teacher(user) and row["status"] == "draft":
            raise APIError(404, "作业尚未发布")
    if "allocation_id" in params:
        resource(user, "allocations", params["allocation_id"], is_teacher(user))
    # 同时校验请求体、查询中的关联资源，防止借用本课程路径操作其它课程资源。
    for source in (q, b):
        for key, table in (("assignment_id", "assignments"), ("problem_id", "problems"), ("class_id", "classes")):
            if source.get(key):
                resource(user, table, source[key], auth == "teacher")
        for pid in source.get("problem_ids", []) or []:
            p = resource(user, "problems", pid, True)
            cid = b.get("course_id") or q.get("course_id")
            if "id" in params and parts[1] == "assignments":
                cid = db.q1("SELECT course_id FROM assignments WHERE id=?", (params["id"],))["course_id"]
            if cid and int(cid) != p["course_id"]:
                raise APIError(400, "作业只能包含同一课程的题目")
    if parts[1] == "users" and "id" in params or path == "/api/analytics/student/{id}":
        target = int(params["id"])
        if target != user["id"]:
            from .api import active_course_id
            cid = active_course_id(ctx)
            require_course(user, cid, True)
            if not db.q1("SELECT 1 FROM course_members WHERE course_id=? AND user_id=?", (cid, target)):
                raise APIError(403, "该用户不在本课程中")
    if path == "/api/anomalies/handle-batch":
        for ident in b.get("ids") or []:
            resource(user, "anomalies", ident, True)


def anonymous(user_id, aid=0, round_no=1):
    # 每次作业、轮次使用服务端随机密钥，无法通过名册中的数字 ID 反推身份。
    key = f"anonymous:{aid}:{round_no}"
    row = db.q1("SELECT value FROM settings WHERE key=?", (key,))
    if not row:
        db.ex("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (key, secrets.token_hex(32)))
        row = db.q1("SELECT value FROM settings WHERE key=?", (key,))
    secret = row["value"]
    return "匿名#" + hmac.new(secret.encode(), str(user_id).encode(), hashlib.sha256).hexdigest()[:10].upper()


def student_response(value, user, aid=None):
    if isinstance(value, list):
        return [student_response(v, user, aid) for v in value]
    if not isinstance(value, dict):
        if hasattr(value, "keys"):
            value = dict(value)
        else:
            return value
    value = dict(value)
    aid = value.get("assignment_id") or aid
    if "problems" in value and "review_due_at" in value:
        aid = value.get("id") or aid
    for key in ("solution", "gen_key", "author_id", "reviewer_id"):
        value.pop(key, None)
    visible = bool(aid and published(aid))
    if "review_published" in value:
        value["review_published"] = visible
    for key in ("methods", "review_methods"):
        if key in value:
            methods = db.jloads(value[key], {}) if isinstance(value[key], str) else value[key]
            value[key] = ({m: (v.get(str(user["id"])) if isinstance(v, dict) else v)
                           for m, v in (methods or {}).items()} if visible else {})
    if not visible:
        for key in ("reviews", "peer_reviews"):
            if isinstance(value.get(key), list):
                value[key] = []
        for key in ("final_score", "review_score"):
            if key in value:
                value[key] = None
    return {k: student_response(v, user, aid) for k, v in value.items()}
