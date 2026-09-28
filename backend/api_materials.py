"""课件库接口：章节结构、课件列表、上传 / 修改 / 删除。

课件按授课章节组织（见 ``backend/courseware.py``），PDF 本体由 ``server.py``
当作静态资源从 ``frontend/courseware/`` 直接下发，这里只负责元数据。

* 学生与教师都可以查看、下载课件；
* 只有教师 / 助教可以上传、改标题归属章节、删除；
* 上传走 JSON + base64，避免为了 multipart 再引入依赖。
"""

from __future__ import annotations

import base64
import binascii
import os
import re
from datetime import datetime

from . import courseware as CW
from . import db
from .api import err, is_teacher, jload, ok, route, uid_rows

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(ROOT, "frontend", "courseware")

#: 单个课件大小上限（base64 解码前，单位字节）
MAX_UPLOAD_BYTES = 60 * 1024 * 1024


def _course_id(ctx) -> int | None:
    cid = ctx["query"].get("course_id") or (ctx["body"].get("course_id") if ctx["body"] else None)
    if cid:
        return int(cid)
    rows = uid_rows("SELECT id FROM courses ORDER BY id")
    if not rows:
        return None
    if is_teacher(ctx["user"]):
        return rows[0]["id"]
    mine = db.q1(
        "SELECT course_id FROM course_members WHERE user_id=? ORDER BY course_id LIMIT 1",
        (ctx["user"]["id"],),
    )
    return mine["course_id"] if mine else rows[0]["id"]


def _safe_slug(name: str) -> str:
    base = re.sub(r"[^0-9A-Za-z_-]+", "-", os.path.splitext(name)[0]).strip("-").lower()
    return base or ("material-" + datetime.now().strftime("%Y%m%d%H%M%S"))


def _material_dict(row: dict) -> dict:
    row = dict(row)
    row["topics"] = jload(row.get("topics"), [])
    row["chapter_no"] = (CW.CHAPTER_BY_KEY.get(row.get("chapter")) or {}).get("no", "")
    row["chapter_name"] = (CW.CHAPTER_BY_KEY.get(row.get("chapter")) or {}).get("title", "")
    row["size_mb"] = round((row.get("size_bytes") or 0) / 1048576, 2)
    return row


# ---------------------------------------------------------------------------
# 章节
# ---------------------------------------------------------------------------


def chapter_overview(course_id: int | None) -> list[dict]:
    """章节列表：附带该章的课件数与题目数，供选题、课件浏览与学情分析共用。"""
    counts, prob_counts = {}, {}
    if course_id is not None:
        counts = {
            r["chapter"]: r["c"]
            for r in uid_rows(
                "SELECT chapter,COUNT(*) c FROM materials WHERE course_id=? GROUP BY chapter",
                (course_id,),
            )
        }
        prob_counts = {
            r["chapter"]: r["c"]
            for r in uid_rows(
                "SELECT chapter,COUNT(*) c FROM problems WHERE course_id=? "
                "AND chapter IS NOT NULL GROUP BY chapter",
                (course_id,),
            )
        }
    out = []
    for c in CW.CHAPTERS:
        out.append(
            {
                "key": c["key"],
                "no": c["no"],
                "title": c["title"],
                "label": f"{c['no']} {c['title']}",
                "topic": c["topic"],
                "summary": c["summary"],
                "topics": c["topics"],
                "material_count": counts.get(c["key"], 0),
                "problem_count": prob_counts.get(c["key"], 0),
            }
        )
    return out


@route("GET", "/api/chapters")
def api_chapters(ctx):
    return ok(chapter_overview(_course_id(ctx)))


@route("GET", "/api/stats/public", "public")
def api_public_stats(ctx):
    """首页用的真实规模数据（学生数、题目数、评测数、互评份数、章节与课件数）。"""
    def count(sql, args=()):
        row = db.q1(sql, args)
        return (row[0] if row is not None else 0) or 0

    return ok({
        "students": count("SELECT COUNT(*) FROM users WHERE role='student'"),
        "problems": count("SELECT COUNT(*) FROM problems"),
        "programming": count("SELECT COUNT(*) FROM problems WHERE type='programming'"),
        "subjective": count("SELECT COUNT(*) FROM problems WHERE type<>'programming'"),
        "submissions": count("SELECT COUNT(*) FROM submissions"),
        "reviews": count("SELECT COUNT(*) FROM reviews"),
        "test_cases": count("SELECT COUNT(*) FROM test_cases"),
        "chapters": len(CW.CHAPTERS),
        "materials": count("SELECT COUNT(*) FROM materials"),
        "assignments": count("SELECT COUNT(*) FROM assignments"),
    })


# ---------------------------------------------------------------------------
# 课件
# ---------------------------------------------------------------------------


@route("GET", "/api/materials")
def api_materials(ctx):
    cid = _course_id(ctx)
    sql = "SELECT * FROM materials WHERE 1=1"
    args: list = []
    if cid is not None:
        sql += " AND course_id=?"
        args.append(cid)
    if ctx["query"].get("chapter"):
        sql += " AND chapter=?"
        args.append(ctx["query"]["chapter"])
    if ctx["query"].get("q"):
        sql += " AND (title LIKE ? OR summary LIKE ?)"
        args += ["%" + ctx["query"]["q"] + "%"] * 2
    sql += " ORDER BY chapter,order_index,id"
    rows = [_material_dict(r) for r in uid_rows(sql, args)]
    total = sum(r.get("size_bytes") or 0 for r in rows)
    return ok({
        "rows": rows,
        "chapters": chapter_overview(cid),
        "homepage": CW.COURSE_HOMEPAGE,
        "total_mb": round(total / 1048576, 1),
    })


@route("POST", "/api/materials", "teacher")
def api_material_create(ctx):
    b = ctx["body"]
    title = (b.get("title") or "").strip()
    if not title:
        return err(400, "请填写课件标题")
    chapter = (b.get("chapter") or "").strip()
    if chapter and chapter not in CW.CHAPTER_BY_KEY:
        return err(400, "未知章节：" + chapter)

    content_b64 = b.get("content") or ""
    if not content_b64:
        return err(400, "请选择要上传的课件文件")
    if "," in content_b64[:80] and content_b64.strip().startswith("data:"):
        content_b64 = content_b64.split(",", 1)[1]
    try:
        blob = base64.b64decode(content_b64, validate=True)
    except (binascii.Error, ValueError):
        return err(400, "文件内容不是合法的 base64")
    if len(blob) > MAX_UPLOAD_BYTES:
        return err(413, "课件超过 %d MB 上限" % (MAX_UPLOAD_BYTES // 1048576))

    filename = b.get("filename") or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".pdf", ".pptx", ".ppt", ".doc", ".docx", ".zip", ".md", ".txt"):
        return err(400, "只支持 pdf / ppt(x) / doc(x) / zip / md / txt")
    slug = _safe_slug(b.get("slug") or filename or title)
    # 同名文件自动加序号，不覆盖已有课件
    final = slug + ext
    n = 2
    while os.path.exists(os.path.join(UPLOAD_DIR, final)):
        final = f"{slug}-{n}{ext}"
        n += 1

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with open(os.path.join(UPLOAD_DIR, final), "wb") as fh:
        fh.write(blob)

    chapter_meta = CW.CHAPTER_BY_KEY.get(chapter) or {}
    cid = _course_id(ctx)
    order = (db.q1(
        "SELECT COALESCE(MAX(order_index),-1)+1 n FROM materials WHERE chapter=?", (chapter,)
    ) or {"n": 0})["n"]
    mid = db.ex(
        "INSERT INTO materials(course_id,chapter,chapter_title,title,filename,url,size_bytes,"
        "pages,sha256,topics,summary,order_index,uploaded_by,created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            cid, chapter,
            f"{chapter_meta.get('no','')} {chapter_meta.get('title','')}".strip(),
            title, final, "/courseware/" + final, len(blob), 0, "",
            db.jdumps(chapter_meta.get("topics", [])), b.get("summary") or "",
            order, ctx["user"]["id"], db.now(),
        ),
    )
    row = db.q1("SELECT * FROM materials WHERE id=?", (mid,))
    return ok(_material_dict(row))


@route("PUT", "/api/materials/{id}", "teacher")
def api_material_update(ctx):
    mid = ctx["params"]["id"]
    row = db.q1("SELECT * FROM materials WHERE id=?", (mid,))
    if not row:
        return err(404, "课件不存在")
    b = ctx["body"]
    sets, args = [], []
    for k in ("title", "summary", "chapter"):
        if b.get(k) is not None:
            if k == "chapter" and b[k] and b[k] not in CW.CHAPTER_BY_KEY:
                return err(400, "未知章节：" + b[k])
            sets.append(k + "=?")
            args.append(b[k])
    if b.get("chapter") is not None:
        meta = CW.CHAPTER_BY_KEY.get(b["chapter"]) or {}
        sets.append("chapter_title=?")
        args.append(f"{meta.get('no','')} {meta.get('title','')}".strip())
        sets.append("topics=?")
        args.append(db.jdumps(meta.get("topics", [])))
    if not sets:
        return err(400, "没有需要修改的字段")
    args.append(mid)
    db.ex("UPDATE materials SET " + ",".join(sets) + " WHERE id=?", args)
    return ok(_material_dict(db.q1("SELECT * FROM materials WHERE id=?", (mid,))))


@route("DELETE", "/api/materials/{id}", "teacher")
def api_material_delete(ctx):
    mid = ctx["params"]["id"]
    row = db.q1("SELECT * FROM materials WHERE id=?", (mid,))
    if not row:
        return err(404, "课件不存在")
    db.ex("DELETE FROM materials WHERE id=?", (mid,))
    # 只删除课件目录下的文件；其它路径一律不动
    full = os.path.abspath(os.path.join(UPLOAD_DIR, os.path.basename(row["filename"])))
    if full.startswith(os.path.abspath(UPLOAD_DIR)) and os.path.exists(full):
        try:
            os.remove(full)
        except OSError:
            pass
    return ok({"id": int(mid)})
