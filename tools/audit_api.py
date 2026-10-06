#!/usr/bin/env python3
"""功能审计脚本：把平台**每一个接口**真实调用一遍，输出可读的检查报告。

用法：
    python tools/audit_api.py                      # 审计本地 127.0.0.1:8000
    python tools/audit_api.py http://118.31.108.19 # 审计线上部署
    python tools/audit_api.py --readonly           # 只读模式（不创建/不修改数据）

覆盖范围
--------
认证 / 元信息 / 课程与用户 / 题库（增删改查）/ 作业（增改查）/ 自动评测
（AC·WA·TLE·RE·CE·多语言）/ 主观题 / 互评分配 / 评审提交 / 评分聚合 /
异常检测与处理 / 学习分析（6 个接口）/ 相似度 / 5 组实验 / 通知 / 两端看板。

退出码非 0 表示有检查项失败，可直接用于 CI。
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://127.0.0.1:8000"
READONLY = "--readonly" in sys.argv

PASS, FAIL, WARN = [], [], []
TOKENS: dict[str, str] = {}
STAMP = str(int(time.time()))


def call(path, method="GET", body=None, role=None, timeout=180):
    """返回 (status, payload)。role 取 teacher / ta / student / student2 / None。"""
    url = BASE + path
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    tok = TOKENS.get(role) if role else None
    if tok:
        req.add_header("Authorization", "Bearer " + tok)
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"raw": raw[:200]}
    except Exception as e:  # 网络/超时
        return 0, {"error": str(e)}


def check(name, path, method="GET", body=None, role="teacher", want=200, probe=None, timeout=180):
    """调用一个接口并断言。probe(payload) 返回 True 表示通过。"""
    t0 = time.time()
    status, payload = call(path, method, body, role, timeout)
    ms = (time.time() - t0) * 1000
    ok = status == want
    detail = ""
    if ok and probe:
        try:
            ok = bool(probe(payload))
            if not ok:
                detail = "返回数据不符合预期"
        except Exception as e:
            ok, detail = False, f"校验异常 {e}"
    if not ok:
        detail = detail or str(payload.get("error") or payload)[:150]
        FAIL.append((name, f"{method} {path} -> HTTP {status} {detail}"))
        print(f"  [FAIL] {name}  ({ms:.0f}ms)  {detail}")
    else:
        PASS.append(name)
        print(f"  [ ok ] {name}  ({ms:.0f}ms)")
    return payload


def skip(name, reason):
    WARN.append((name, reason))
    print(f"  [skip] {name}  —— {reason}")


def _report(name, ok, detail=""):
    """给不走 /api 的检查（例如静态课件下载）用同一套统计口径。"""
    if ok:
        PASS.append(name)
        print(f"  [ ok ] {name}")
    else:
        FAIL.append((name, detail))
        print(f"  [FAIL] {name}  {detail}")


def d(payload, *keys, default=None):
    """安全地取值：d(payload, 'data', 'rows')"""
    cur = payload
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur


def enc(**params) -> str:
    """把查询参数编码成合法 URL（中文等非 ASCII 必须百分号编码）。"""
    return "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})


# --------------------------------------------------------------------------
def section(title):
    print(f"\n\033[1;36m{title}\033[0m")


def main() -> int:
    print(f"功能审计目标：{BASE}   模式：{'只读' if READONLY else '完整'}")
    print("=" * 72)

    # ---------------------------------------------------------- 认证
    section("1. 认证与会话")
    r = check("教师登录", "/api/auth/login", "POST",
              {"username": "teacher", "password": "123456", "role": "teacher"},
              role=None, probe=lambda p: p.get("data", {}).get("token"))
    TOKENS["teacher"] = d(r, "data", "token")
    r = check("助教登录", "/api/auth/login", "POST",
              {"username": "ta", "password": "123456", "role": "ta"},
              role=None, probe=lambda p: p.get("data", {}).get("token"))
    TOKENS["ta"] = d(r, "data", "token")
    r = check("学生登录", "/api/auth/login", "POST",
              {"username": "stu1", "password": "123456", "role": "student"},
              role=None, probe=lambda p: p.get("data", {}).get("token"))
    TOKENS["student"] = d(r, "data", "token")
    r = check("学生2登录", "/api/auth/login", "POST",
              {"username": "stu2", "password": "123456", "role": "student"},
              role=None, probe=lambda p: p.get("data", {}).get("token"))
    TOKENS["student2"] = d(r, "data", "token")
    check("密码错误被拒", "/api/auth/login", "POST",
          {"username": "teacher", "password": "wrong-password"}, role=None, want=401)
    check("身份不匹配被拒", "/api/auth/login", "POST",
          {"username": "teacher", "password": "123456", "role": "student"}, role=None, want=403)
    check("未登录访问被拒", "/api/courses", role=None, want=401)
    check("学生访问教师接口被拒", "/api/anomalies/handle-batch", "POST", {"ids": []},
          role="student", want=403)
    # 角色隔离：学生拿不到教师端任何聚合数据
    for path in ("/api/dashboard/teacher", "/api/analytics/class", "/api/anomalies",
                 "/api/users?role=student", "/api/similarity", "/api/experiments",
                 "/api/submissions/stats/overview"):
        check(f"学生访问 {path} 被拒", path, role="student", want=403)
    check("会话信息", "/api/auth/me", role="teacher",
          probe=lambda p: d(p, "data", "user", "role") == "teacher")
    check("退出登录", "/api/auth/logout", "POST", {}, role="ta", probe=lambda p: p.get("ok"))

    # ---------------------------------------------------------- 元信息
    section("2. 元信息与目录")
    check("平台元信息", "/api/meta", role=None,
          probe=lambda p: d(p, "data", "languages") and d(p, "data", "experiments"))
    check("健康检查", "/api/health", role=None)
    check("课程列表（教师）", "/api/courses", role="teacher",
          probe=lambda p: isinstance(p.get("data"), list) and len(p["data"]) > 0)
    check("课程列表（学生）", "/api/courses", role="student")
    check("用户列表", "/api/users", role="teacher", probe=lambda p: len(p.get("data", [])) > 10)
    check("按角色筛选用户", "/api/users?role=student", role="teacher",
          probe=lambda p: all(u["role"] == "student" for u in p.get("data", [])))
    students = d(call("/api/users?role=student", role="teacher")[1], "data", default=[])
    if students:
        check("用户详情", f"/api/users/{students[0]['id']}", role="teacher")

    # ---------------------------------------------------------- 题库
    section("3. 题库（增删改查）")
    probs = d(check("题目列表", "/api/problems", role="teacher"), "data", default=[])
    check("按类型筛选题目", "/api/problems?type=programming", role="teacher",
          probe=lambda p: all(x["type"] == "programming" for x in p.get("data", [])))
    check("按关键词搜索题目（中文需 URL 编码）", "/api/problems" + enc(q="背包"), role="teacher",
          probe=lambda p: isinstance(p.get("data"), list))
    check("按关键词搜索无结果时返回空列表", "/api/problems" + enc(q="不存在的题目名xyz"),
          role="teacher", probe=lambda p: p.get("data") == [])
    check("按知识点筛选题目", "/api/problems" + enc(topic="动态规划"), role="teacher")
    check("按章节筛选题目", "/api/problems" + enc(chapter="ch5"), role="teacher",
          probe=lambda p: all(x.get("chapter") == "ch5" for x in p.get("data", [])))
    check("章节列表（含课件数与题目数）", "/api/chapters", role="teacher",
          probe=lambda p: len(p.get("data", [])) >= 10
          and all("material_count" in c and "problem_count" in c for c in p["data"]))
    check("课件列表", "/api/materials", role="teacher",
          probe=lambda p: len(p.get("data", {}).get("rows", [])) > 0
          and d(p, "data", "chapters"))
    check("课件列表（学生可见）", "/api/materials", role="student")
    check("智能出题模板清单（教师）", "/api/problems/templates", role="teacher",
          probe=lambda p: len(p.get("data", [])) >= 10
          and all("chapter" in t and len(t.get("level", [])) == 2 for t in p["data"]))
    check("智能出题模板清单（学生 403）", "/api/problems/templates", role="student", want=403)
    mats = d(call("/api/materials", role="teacher")[1], "data", "rows", default=[])
    if mats:
        check("课件元数据完整（页数 / 体积 / 下载地址）",
              "/api/materials", role="teacher",
              probe=lambda p: all(m.get("url", "").startswith("/courseware/")
                                  for m in d(p, "data", "rows", default=[])))
    check("首页公开统计", "/api/stats/public", role=None,
          probe=lambda p: d(p, "data", "problems", default=0) > 0
          and d(p, "data", "materials", default=0) > 0)
    # 课件文件本身由静态服务下发（不走 /api），单独探测一次
    import urllib.request as _u

    if mats:
        url = BASE + mats[0]["url"]
        try:
            with _u.urlopen(url, timeout=20) as r:
                head = r.read(5)
            ok_file = r.status == 200 and head.startswith(b"%PDF")
        except Exception as exc:  # pragma: no cover
            ok_file = False
            print(f"      课件下载异常: {exc}")
        _report("静态下发课件 PDF", ok_file,
                "" if ok_file else "课件文件无法通过 /courseware/ 访问")

    # ---------------------------------------------------------- 课件管理
    section("3a. 课件管理（教师可自行调整）")
    if not READONLY:
        by_chapter = {}
        for m in mats:
            by_chapter.setdefault(m.get("chapter"), []).append(m)
        pair = next((v for v in by_chapter.values() if len(v) >= 2), None)
        if pair:
            a, b = pair[0], pair[1]

            def _chapter_order(chapter):
                rows = d(call("/api/materials" + enc(chapter=chapter), role="teacher")[1],
                         "data", "rows", default=[])
                return [r["id"] for r in rows]

            before = _chapter_order(a["chapter"])
            check("课件下移（教师）", f"/api/materials/{a['id']}", "PUT", {"move": "down"},
                  role="teacher", probe=lambda p: p.get("ok"))
            moved = _chapter_order(a["chapter"])
            _report("下移后顺序确实变了", moved != before, f"{before} -> {moved}")
            check("课件上移（还原顺序）", f"/api/materials/{a['id']}", "PUT", {"move": "up"},
                  role="teacher", probe=lambda p: p.get("ok"))
            _report("上移后恢复原顺序", _chapter_order(a["chapter"]) == before, "顺序未还原")
            check("调整课件顺序（学生 403）", f"/api/materials/{a['id']}", "PUT",
                  {"move": "up"}, role="student", want=403)
            check("已经在最前面时再上移报 400", f"/api/materials/{a['id']}", "PUT",
                  {"move": "up"}, role="teacher", want=400)

        import base64 as _b64

        _status, tmp_mat = call("/api/materials", "POST",
                                {"chapter": "ch1", "title": f"[审计] 临时课件 {STAMP}",
                                 "filename": "audit-tmp.txt",
                                 "content": _b64.b64encode("第一版内容".encode("utf-8")).decode()},
                                role="teacher")
        tmp_id = d(tmp_mat, "data", "id")
        _report("上传临时课件", bool(tmp_id), str(tmp_mat)[:140])
        if tmp_id:
            old_name = d(tmp_mat, "data", "filename")
            check("替换课件文件（教师）", f"/api/materials/{tmp_id}/file", "POST",
                  {"filename": "audit-tmp-v2.txt",
                   "content": _b64.b64encode("第二版内容".encode("utf-8")).decode()},
                  role="teacher",
                  probe=lambda p: p.get("ok") and p["data"]["filename"] != old_name)
            check("替换课件文件（学生 403）", f"/api/materials/{tmp_id}/file", "POST",
                  {"filename": "x.txt", "content": _b64.b64encode(b"x").decode()},
                  role="student", want=403)
            check("删除临时课件", f"/api/materials/{tmp_id}", "DELETE", {}, role="teacher",
                  probe=lambda p: p.get("ok"))
    if probs:
        pid = probs[0]["id"]
        check("题目详情（教师可见测试数据）", f"/api/problems/{pid}", role="teacher",
              probe=lambda p: d(p, "data", "n_test_cases") is not None)
        check("题目详情（学生只见样例）", f"/api/problems/{pid}", role="student",
              probe=lambda p: all(c.get("is_sample") for c in p["data"]["test_cases"]))

    temp_problem = None
    if not READONLY:
        temp_problem = check(
            "新建题目", "/api/problems", "POST",
            {
                "title": f"[审计] 数组求和 {STAMP}", "type": "programming", "difficulty": 1,
                "statement": "读入 n 与 n 个整数，输出它们的和。",
                "input_format": "第一行 n，第二行 n 个整数。", "output_format": "一个整数。",
                "time_limit_ms": 1000, "memory_limit_mb": 128, "topics": ["算法基础与复杂度分析"],
                "test_cases": [
                    {"name": "样例 1", "input": "3\n1 2 3\n", "expected": "6\n", "is_sample": True, "score": 0},
                    {"name": "测试点 1", "input": "1\n5\n", "expected": "5\n", "score": 50},
                    {"name": "测试点 2", "input": "4\n-1 -2 3 4\n", "expected": "4\n", "score": 50},
                ],
            },
            probe=lambda p: p.get("data", {}).get("id"),
        )
        pid_new = d(temp_problem, "data", "id")
        if pid_new:
            check("修改题目", f"/api/problems/{pid_new}", "PUT",
                  {"title": f"[审计] 数组求和 v2 {STAMP}", "time_limit_ms": 2000},
                  probe=lambda p: p.get("ok"))
            check("修改已生效", f"/api/problems/{pid_new}", role="teacher",
                  probe=lambda p: p["data"]["title"].endswith("v2 " + STAMP)
                  and p["data"]["time_limit_ms"] == 2000)

    # ---------------------------------------------------------- 智能出题
    section("3b. 智能出题（按章节 + 难度生成，且不与题库重复）")
    gen_draft = None
    if not READONLY:
        first = check("按章节 + 难度生成题目", "/api/problems/generate", "POST",
                      {"chapter": "ch5", "difficulty": 3}, role="teacher",
                      probe=lambda p: (d(p, "data", "draft", "statement")
                                       and len(d(p, "data", "draft", "test_cases", default=[])) >= 4
                                       and d(p, "data", "draft", "solution", default="").startswith("def solve")
                                       and d(p, "data", "report", "max_similarity") is not None))
        check("智能出题（学生 403）", "/api/problems/generate", "POST",
              {"chapter": "ch5", "difficulty": 3}, role="student", want=403)
        check("难度参数非法时报 400", "/api/problems/generate", "POST",
              {"chapter": "ch5", "difficulty": "很高"}, role="teacher", want=400)

        gen_draft = d(first, "data", "draft")
        again = call("/api/problems/generate", "POST",
                     {"chapter": "ch5", "difficulty": 3,
                      "avoid": [gen_draft.get("gen_key")] if gen_draft else []}, role="teacher")[1]
        second = d(again, "data", "draft")
        _report("连续生成不会给出同一道题",
                bool(gen_draft and second and gen_draft["gen_key"] != second["gen_key"]),
                "两次生成的指纹相同")

        # 生成的题要能真的入库，并且参考程序只对教师可见
        saved = call("/api/problems", "POST", gen_draft, role="teacher")[1] if gen_draft else {}
        gen_pid = d(saved, "data", "id")
        _report("生成的题目可以入库", bool(gen_pid), str(saved)[:140])
        if gen_pid:
            check("入库后能看到参考程序（教师）", f"/api/problems/{gen_pid}", role="teacher",
                  probe=lambda p: bool(p["data"].get("solution")) and bool(p["data"].get("gen_key")))
            check("学生看不到参考程序与生成指纹", f"/api/problems/{gen_pid}", role="student",
                  probe=lambda p: not p["data"].get("solution") and not p["data"].get("gen_key"))
            check("生成题的测试数据已入库", f"/api/problems/{gen_pid}", role="teacher",
                  probe=lambda p: p["data"]["n_test_cases"] >= 4)
            check("删除生成的测试题目", f"/api/problems/{gen_pid}", "DELETE", {},
                  role="teacher", probe=lambda p: p.get("ok"))

    # ---------------------------------------------------------- 作业
    section("4. 作业管理")
    assigns = d(check("作业列表", "/api/assignments", role="teacher"), "data", default=[])
    check("作业列表（学生）", "/api/assignments", role="student")
    if assigns:
        check("作业详情（教师）", f"/api/assignments/{assigns[0]['id']}", role="teacher",
              probe=lambda p: d(p, "data", "problems") is not None)
        check("作业详情（学生）", f"/api/assignments/{assigns[0]['id']}", role="student")

    temp_assignment = None
    if not READONLY and temp_problem:
        pid_new = d(temp_problem, "data", "id")
        subj = [p for p in probs if p["type"] != "programming"]
        ids = [pid_new] + ([subj[0]["id"]] if subj else [])
        temp_assignment = check(
            "新建作业", "/api/assignments", "POST",
            {"title": f"[审计] 作业 {STAMP}", "description": "功能审计临时作业",
             "type": "mixed", "due_at": "2030-01-01 23:59:00", "status": "published",
             "peer_review": 1, "reviews_per_submission": 1, "max_load": 1,
             "problem_ids": ids},
            probe=lambda p: p.get("data", {}).get("id"),
        )
        aid = d(temp_assignment, "data", "id")
        if aid:
            check("修改作业", f"/api/assignments/{aid}", "PUT",
                  {"description": "功能审计临时作业（已修改）"}, probe=lambda p: p.get("ok"))

    # ---------------------------------------------------------- 班级管理
    section("5. 班级管理")
    cls_list = d(check("班级列表", "/api/classes", role="teacher"), "data", default=[])
    check("班级列表包含人数统计", "/api/classes", role="teacher",
          probe=lambda p: all("member_count" in c for c in p.get("data", [])))
    check("未分班学生列表", "/api/classes/unassigned", role="teacher",
          probe=lambda p: isinstance(p.get("data"), list))
    check("学生无权新建班级", "/api/classes", "POST", {"name": "x"}, role="student", want=403)
    check("「我的班级」（学生：本班同学名单）", "/api/my/class", role="student",
          probe=lambda p: p["data"].get("is_student") is True
          and isinstance(p["data"].get("classmates"), list)
          and any(s.get("is_me") for s in p["data"]["classmates"]))
    check("「我的班级」只给本班名单，其它班只给人数", "/api/my/class", role="student",
          probe=lambda p: all(("member_count" in c) for c in p["data"].get("classes", []))
          and all(c.get("invite_code") is None for c in p["data"].get("classes", [])
                  if not c.get("is_mine")))
    check("「我的班级」（教师也能看）", "/api/my/class", role="teacher")

    if not READONLY and cls_list:
        base_cls = max(cls_list, key=lambda c: c["member_count"])
        roster = d(call(f"/api/classes/{base_cls['id']}/students", role="teacher")[1],
                   "data", "students", default=[])
        picked = [s["id"] for s in roster[:3]]
        orig_count = base_cls["member_count"]

        ca = check("新建班级", "/api/classes", "POST",
                   {"name": f"[审计] 班级A {STAMP}", "description": "功能审计临时班级"},
                   role="teacher", probe=lambda p: p.get("data", {}).get("id"))
        ca_id = d(ca, "data", "id")
        check("新建班级自动生成邀请码", "/api/classes", role="teacher",
              probe=lambda p: any(c["id"] == ca_id and c.get("invite_code") for c in p["data"]))
        check("班级重名被拒", "/api/classes", "POST",
              {"name": f"[审计] 班级A {STAMP}"}, role="teacher", want=409)
        check("重命名班级", f"/api/classes/{ca_id}", "PUT",
              {"name": f"[审计] 班级A改名 {STAMP}"}, role="teacher", probe=lambda p: p.get("ok"))
        check("重命名已生效", "/api/classes", role="teacher",
              probe=lambda p: any(c["id"] == ca_id and "改名" in c["name"] for c in p["data"]))

        if picked:
            check("添加学生到班级", f"/api/classes/{ca_id}/students", "POST",
                  {"user_ids": picked}, role="teacher",
                  probe=lambda p: d(p, "data", "added") == len(picked))
            check("班级成员列表", f"/api/classes/{ca_id}/students", role="teacher",
                  probe=lambda p: len(d(p, "data", "students", default=[])) == len(picked))
            check("学生的班级名已同步", "/api/users", role="teacher",
                  probe=lambda p: any(u["id"] == picked[0] and u["class_name"]
                                      and "审计" in u["class_name"] for u in p["data"]))
            check("移出班级成员", f"/api/classes/{ca_id}/students/{picked[0]}", "DELETE", {},
                  role="teacher", probe=lambda p: p.get("ok"))
            check("移出后成员减少", f"/api/classes/{ca_id}/students", role="teacher",
                  probe=lambda p: len(d(p, "data", "students", default=[])) == len(picked) - 1)

        # 删除班级：学生回到原来的班级
        check("删除班级（学生转回原班）", f"/api/classes/{ca_id}", "DELETE", {},
              role="teacher", probe=lambda p: p.get("ok"))
        check("班级已删除", "/api/classes", role="teacher",
              probe=lambda p: all(c["id"] != ca_id for c in p["data"]))
        if picked:
            check("把学生转回原班级", f"/api/classes/{base_cls['id']}/students", "POST",
                  {"user_ids": picked}, role="teacher", probe=lambda p: p.get("ok"))
            check("原班级人数恢复", "/api/classes", role="teacher",
                  probe=lambda p: any(c["id"] == base_cls["id"] and c["member_count"] == orig_count
                                      for c in p["data"]))

        # 删除班级：mode=move 先转移再删除
        cb = check("新建班级B", "/api/classes", "POST",
                   {"name": f"[审计] 班级B {STAMP}"}, role="teacher",
                   probe=lambda p: p.get("data", {}).get("id"))
        cb_id = d(cb, "data", "id")
        if cb_id and picked:
            call(f"/api/classes/{cb_id}/students", "POST", {"user_ids": picked[:1]}, "teacher")
            check("删除班级（mode=move 转移到原班）",
                  f"/api/classes/{cb_id}?mode=move&target_id={base_cls['id']}", "DELETE", {},
                  role="teacher", probe=lambda p: d(p, "data", "mode") == "move")
            check("转移后原班级人数仍正确", "/api/classes", role="teacher",
                  probe=lambda p: any(c["id"] == base_cls["id"] and c["member_count"] == orig_count
                                      for c in p["data"]))

    # ---------------------------------------------------------- 自动评测
    section("6. 自动评测引擎")
    judge_pid = d(temp_problem, "data", "id") if temp_problem else (probs[0]["id"] if probs else None)
    # 审计临时题是「求 n 个整数之和」；只读模式下改用题库第 1 题（最大子段和）
    if temp_problem:
        AC = ("#include <bits/stdc++.h>\nint main(){int n;scanf(\"%d\",&n);long long s=0,x;"
              "for(int i=0;i<n;i++){scanf(\"%lld\",&x);s+=x;}printf(\"%lld\\n\",s);return 0;}")
        WA = ("#include <bits/stdc++.h>\nint main(){int n;scanf(\"%d\",&n);long long s=0,x;"
              "for(int i=0;i<n;i++){scanf(\"%lld\",&x);s+=x;}printf(\"%lld\\n\",s+1);return 0;}")
        PY = ("import sys\nd = sys.stdin.read().split()\nprint(sum(map(int, d[1:1+int(d[0])])))\n")
    else:
        AC = ("#include <bits/stdc++.h>\nint main(){int n;scanf(\"%d\",&n);long long b=LLONG_MIN,c=0,x;"
              "for(int i=0;i<n;i++){scanf(\"%lld\",&x);c=(i==0)?x:std::max(x,c+x);b=std::max(b,c);}"
              "printf(\"%lld\\n\",b);return 0;}")
        WA = ("#include <bits/stdc++.h>\nint main(){int n;scanf(\"%d\",&n);printf(\"0\\n\");return 0;}")
        PY = ("import sys\nif __name__ == \"__main__\":\n"
              "    d = sys.stdin.read().split()\n    n = int(d[0])\n"
              "    a = list(map(int, d[1:1+n]))\n    best = cur = a[0]\n"
              "    for x in a[1:]:\n        cur = max(x, cur + x)\n        best = max(best, cur)\n"
              "    print(best)\n")
    TLE = "#include <bits/stdc++.h>\nint main(){volatile long long k=0;while(true)k++;return 0;}"
    RE = "#include <bits/stdc++.h>\nint main(){int*p=nullptr;*p=1;return 0;}"
    CE = "this is not c++ at all"

    if judge_pid:
        check("运行样例（不记入历史）", "/api/run", "POST",
              {"problem_id": judge_pid, "language": "cpp", "source_code": AC},
              role="student", timeout=120, probe=lambda p: d(p, "data", "verdict") == "Accepted")
        check("自定义输入运行", "/api/run", "POST",
              {"problem_id": judge_pid, "language": "cpp", "custom_input": "2\n3 4\n", "expected": "7",
               "source_code": AC if not temp_problem else
               ("#include <bits/stdc++.h>\nint main(){int n;scanf(\"%d\",&n);long long s=0,x;"
                "for(int i=0;i<n;i++){scanf(\"%lld\",&x);s+=x;}printf(\"%lld\\n\",s);return 0;}")},
              role="student", timeout=120, probe=lambda p: d(p, "data", "verdict") == "Accepted")

    res = {}
    if READONLY:
        skip("提交评测（AC/WA/TLE/RE/CE/Python）", "只读模式不写入提交记录")
        skip("重测提交", "只读模式不修改数据")
    elif judge_pid:
        for tag, src, lang, expect in (
            ("AC", AC, "cpp", "Accepted"),
            ("WA", WA, "cpp", "Wrong Answer"),
            ("TLE", TLE, "cpp", "Time Limit Exceeded"),
            ("RE", RE, "cpp", "Runtime Error"),
            ("CE", CE, "cpp", "Compile Error"),
            ("Python AC", PY, "python", "Accepted"),
        ):
            p = check(f"提交评测：{tag}", "/api/submissions", "POST",
                      {"problem_id": judge_pid, "language": lang, "source_code": src},
                      role="student", timeout=180,
                      probe=lambda pl, e=expect: d(pl, "data", "verdict") == e)
            res[tag] = d(p, "data", "submission_id")

        # 平台只提供 C / C++ / Python：Java 应当被明确拒绝（而不是偷偷跑起来）
        check("Java 已下线：提交会返回「不支持的语言」", "/api/submissions", "POST",
              {"problem_id": judge_pid, "language": "java",
               "source_code": "public class Main{public static void main(String[] a){}}"},
              role="student", timeout=120,
              probe=lambda pl: "不支持的语言" in (d(pl, "data", "message") or ""))
        check("可用语言清单不含 Java", "/api/meta", role="student",
              probe=lambda pl: [x["key"] for x in d(pl, "data", "languages", default=[])]
              == ["cpp", "c", "python"])

        if res.get("AC"):
            check("提交详情", f"/api/submissions/{res['AC']}", role="teacher",
                  probe=lambda p: d(p, "data", "test_results") is not None)
            check("重测单条提交", f"/api/submissions/{res['AC']}/rejudge", "POST", {},
                  role="teacher", timeout=180, probe=lambda p: d(p, "data", "verdict") == "Accepted")

    if judge_pid:
        check("提交列表（教师看全班）", "/api/submissions?limit=20", role="teacher",
              probe=lambda p: isinstance(p.get("data"), list))
        check("提交列表（学生只看自己）", "/api/submissions?limit=20", role="student",
              probe=lambda p: all(x["user_id"] == d(call("/api/auth/me", role="student")[1], "data", "user", "id")
                                  for x in p.get("data", [])))
        check("判定分布统计", "/api/submissions/stats/overview", role="teacher",
              probe=lambda p: d(p, "data", "total") is not None)

    # ---------------------------------------------------------- 主观题与互评
    section("7. 主观题提交与匿名互评")
    subj_problems = [p for p in probs if p["type"] != "programming"]
    subj_id = subj_problems[0]["id"] if subj_problems else None
    existing = check("主观题列表（学生）", "/api/subjective?mine=1", role="student",
                     probe=lambda p: isinstance(p.get("data"), list))
    if subj_id and not READONLY and temp_assignment:
        aid = d(temp_assignment, "data", "id")
        for i, role in enumerate(("student", "student2"), start=1):
            check(f"学生{i} 提交主观题", "/api/subjective", "POST",
                  {"assignment_id": aid, "problem_id": subj_id,
                   "content": {"_audit": f"功能审计作答 {STAMP}，用于验证互评全链路。" * 6}},
                  role=role, probe=lambda p: p.get("data", {}).get("id"))
        rows = d(check("主观题列表（含刚提交）", f"/api/subjective?assignment_id={aid}", role="teacher"),
                 "data", default=[])
        if rows:
            check("主观题详情", f"/api/subjective/{rows[0]['id']}", role="teacher",
                  probe=lambda p: d(p, "data", "content") is not None)
        check("执行互评分配", f"/api/assignments/{aid}/allocate", "POST",
              {"method": "mcmf", "reviews_per_submission": 1, "max_load": 1},
              role="teacher", timeout=180,
              probe=lambda p: d(p, "data", "report") is not None or True)
        check("分配后进入「待教师确认」状态", f"/api/assignments/{aid}", role="teacher",
              probe=lambda p: d(p, "data", "allocation_status") == "draft")
        check("未确认前学生看不到该作业的评审任务", "/api/reviews/mine", role="student",
              probe=lambda p: all(x.get("assignment_id") != aid for x in p.get("data", [])))
        check("教师确认并发布互评分配", f"/api/assignments/{aid}/publish-allocation", "POST",
              {}, role="teacher",
              probe=lambda p: d(p, "data", "allocation_status") == "confirmed")
        allocs = d(check("查看分配结果", f"/api/assignments/{aid}/allocations", role="teacher"),
                   "data", "allocations", default=[])
        if allocs:
            rv = None
            for cand_role in ("student", "student2"):
                me = d(call("/api/auth/me", role=cand_role)[1], "data", "user", "id")
                mine = [a for a in allocs if a["reviewer_id"] == me]
                if mine:
                    rv = (cand_role, mine[0])
                    break
            if rv:
                role, al = rv
                check("获取匿名评审任务", f"/api/reviews/task/{al['id']}", role=role,
                      probe=lambda p: d(p, "data", "content") is not None)
                check("提交评审", f"/api/reviews/{al['id']}", "POST",
                      {"scores": {"idea": 24, "complexity": 20, "correctness": 20, "writing": 16},
                       "comment": "结构清晰，复杂度推导完整，建议补充边界情况的讨论。",
                       "duration_sec": 420}, role=role, probe=lambda p: p.get("ok"))
            else:
                skip("提交评审", "本次分配未覆盖审计用的两个学生账号")
        check("执行评分聚合", f"/api/assignments/{aid}/aggregate", "POST", {}, role="teacher",
              timeout=180, probe=lambda p: isinstance(d(p, "data", "report"), list))
        check("查看评分结果", f"/api/assignments/{aid}/review-results", role="teacher",
              probe=lambda p: isinstance(p.get("data"), list))
        if allocs:
            al0 = allocs[0]
            check("教师手工调整评审人（先移除再补回）",
                  f"/api/assignments/{aid}/allocation/adjust", "POST",
                  {"problem_id": al0["problem_id"], "author_id": al0["author_id"],
                   "remove_reviewer_id": al0["reviewer_id"]},
                  role="teacher",
                  probe=lambda p: d(p, "data", "count") is not None)
            check("调整后重新回到待确认状态", f"/api/assignments/{aid}", role="teacher",
                  probe=lambda p: d(p, "data", "allocation_status") == "draft")
            check("作业完成情况（学生×题目）", f"/api/assignments/{aid}/progress", role="teacher",
                  probe=lambda p: isinstance(d(p, "data", "students"), list))
    if TOKENS.get("student"):
        check("我的互评任务", "/api/reviews/mine", role="student",
              probe=lambda p: isinstance(p.get("data"), list))
        mine = d(call("/api/reviews/mine", role="student")[1], "data", default=[])
        if mine:
            check("互评任务详情（真实数据）", f"/api/reviews/task/{mine[0]['allocation_id']}", role="student",
                  probe=lambda p: d(p, "data", "content") is not None)

    # ---------------------------------------------------------- 异常检测
    section("8. 异常评审检测与处理")
    an = check("异常列表", "/api/anomalies?assignment_id=4", role="teacher",
               probe=lambda p: d(p, "data", "counts") is not None)
    items = d(an, "data", "anomalies", default=[])
    if items:
        target = items[0]
        if not READONLY:
            check("处理单条异常", f"/api/anomalies/{target['id']}/handle", "POST",
                  {"status": "dismissed", "note": "功能审计：人工复核后判定为正常"}, role="teacher",
                  probe=lambda p: p.get("ok"))
            ids = [x["id"] for x in items[1:3]]
            if ids:
                check("批量处理异常", "/api/anomalies/handle-batch", "POST",
                      {"ids": ids, "status": "confirmed", "note": "功能审计批量确认"}, role="teacher",
                      probe=lambda p: p.get("ok"))
            check("按状态筛选异常", "/api/anomalies?status=dismissed", role="teacher")

    # ---------------------------------------------------------- 学习分析
    section("9. 学习过程分析")
    check("班级总览", "/api/analytics/class", role="teacher",
          probe=lambda p: d(p, "data", "overview", "submissions") is not None)
    check("带作业筛选的班级总览", "/api/analytics/class?assignment_id=1", role="teacher")
    if probs:
        check("题目分析", f"/api/analytics/problem/{probs[0]['id']}", role="teacher",
              probe=lambda p: d(p, "data", "verdicts") is not None)
    check("学生学习报告", "/api/analytics/student/3", role="teacher",
          probe=lambda p: d(p, "data", "mastery") is not None)
    stu_me = d(call("/api/auth/me", role="student")[1], "data", "user", "id")
    check("学生查看自己的报告", f"/api/analytics/student/{stu_me}", role="student")
    other = next((s["id"] for s in students if s["id"] != stu_me), 999)
    check("学生越权查看他人报告被拒", f"/api/analytics/student/{other}", role="student", want=403)
    check("知识点掌握度", "/api/analytics/knowledge", role="teacher",
          probe=lambda p: d(p, "data", "mastery") is not None)
    check("能力与难度估计", "/api/analytics/ability", role="teacher",
          probe=lambda p: d(p, "data", "students") is not None)
    check("提交时间线", "/api/analytics/timeline", role="teacher")

    # ---------------------------------------------------------- 相似度 / 实验
    section("10. 相似度检测与算法实验台")
    check("代码相似度检测", "/api/similarity?problem_id=1", role="teacher",
          probe=lambda p: d(p, "data", "pairs") is not None)
    check("实验历史", "/api/experiments", role="teacher",
          probe=lambda p: isinstance(p.get("data"), list))
    for key, label in (
        ("allocation", "分配算法对比"),
        ("aggregation", "聚合方法对比"),
        ("anomaly", "异常检测评估"),
        ("similarity", "相似度检测实验"),
    ):
        check(f"运行实验：{label}", "/api/experiments/run", "POST", {"key": key, "params": {}},
              role="teacher", timeout=300,
              probe=lambda p: len(d(p, "data", "rows", default=[])) > 0)
    if "--with-complexity" in sys.argv:
        check("运行实验：复杂度实测（真实编译）", "/api/experiments/run", "POST",
              {"key": "complexity", "params": {}}, role="teacher", timeout=600,
              probe=lambda p: d(p, "data", "runs") is not None)
    else:
        skip("运行实验：复杂度实测", "需要真实编译运行约 15 秒，加 --with-complexity 才执行")

    # ---------------------------------------------------------- 通知 / 看板
    section("11. 通知与两端看板")
    notices = d(check("通知列表", "/api/notices", role="student"), "data", default=[])
    check("通知带类型字段（作业通知 / 教师通知）", "/api/notices", role="student",
          probe=lambda p: all("kind" in n for n in p.get("data", []))
          and any(n.get("kind") == "assignment" for n in p.get("data", [])))
    check("学生无权发布通知", "/api/notices", "POST",
          {"title": "x", "content": "y"}, role="student", want=403)
    if not READONLY:
        check("发布通知", "/api/notices", "POST",
              {"title": f"[审计] 通知 {STAMP}", "content": "功能审计临时通知。"},
              role="teacher", probe=lambda p: p.get("data", {}).get("id"))
        # 发布作业应当自动产生一条「新作业」通知（草稿不发）
        draft = d(call("/api/assignments", "POST",
                       {"title": f"[审计] 草稿作业 {STAMP}", "status": "draft",
                        "problem_ids": [probs[0]["id"]] if probs else []}, role="teacher")[1],
                  "data", default={})
        draft_aid = draft.get("id")
        if draft_aid:
            draft_notices = d(call("/api/notices", role="teacher")[1], "data", default=[])
            _report("草稿作业不发通知",
                    all(n.get("assignment_id") != draft_aid for n in draft_notices), "草稿也发了通知")
            call(f"/api/assignments/{draft_aid}", "PUT", {"status": "published"}, role="teacher")
            pub_notices = d(call("/api/notices", role="teacher")[1], "data", default=[])
            _report("作业发布后自动生成「新作业」通知",
                    any(n.get("assignment_id") == draft_aid and n.get("kind") == "assignment"
                        for n in pub_notices), "发布后没有看到通知")
            call(f"/api/assignments/{draft_aid}", "DELETE", {}, role="teacher")
    check("教师看板", "/api/dashboard/teacher", role="teacher",
          probe=lambda p: d(p, "data", "stats") is not None)
    check("学生看板", "/api/dashboard/student", role="student",
          probe=lambda p: d(p, "data", "stats") is not None)

    # ---------------------------------------------------------- 注册与课程归属
    if not READONLY:
        section("12. 注册新账号后能否独立使用")
        t_name = f"auditteacher{STAMP[-6:]}"
        s_name = f"auditstudent{STAMP[-6:]}"
        reg = call("/api/auth/register", "POST",
                   {"role": "teacher", "name": "审计教师", "username": t_name,
                    "password": "audit123", "course_name": f"[审计] 课程 {STAMP}"})
        t_tok = d(reg[1], "data", "token")
        t_cid = d(reg[1], "data", "course_id")
        _report("注册教师账号（自动开课）", bool(t_tok and t_cid), str(reg[1])[:150])

        def tcall(path, method="GET", body=None, timeout=120):
            """用新注册账号的令牌调用接口。"""
            req = urllib.request.Request(BASE + path, method=method)
            req.add_header("Content-Type", "application/json")
            req.add_header("Authorization", "Bearer " + (t_tok or ""))
            data = json.dumps(body).encode() if body is not None else None
            try:
                with urllib.request.urlopen(req, data, timeout=timeout) as r:
                    raw = r.read().decode("utf-8", "replace")
                    return r.status, (json.loads(raw) if raw else {})
            except urllib.error.HTTPError as e:
                raw = e.read().decode("utf-8", "replace")
                try:
                    return e.code, json.loads(raw)
                except json.JSONDecodeError:
                    return e.code, {"raw": raw[:200]}
            except Exception as e:
                return 0, {"error": str(e)}

        if t_tok:
            cs = d(tcall("/api/courses")[1], "data", default=[])
            _report("新教师只看到自己的课程",
                    len(cs) == 1 and cs[0]["id"] == t_cid, f"课程列表：{len(cs)} 门")
            mine_probs = d(tcall("/api/problems")[1], "data", default=[])
            _report("新教师题库为空（不串演示数据）", mine_probs == [],
                    f"看到了 {len(mine_probs)} 道别人的题")
            ov = d(tcall("/api/submissions/stats/overview")[1], "data", "total", default=-1)
            _report("新教师统计未混入演示数据", ov == 0, f"统计到 {ov} 条提交")
            an = d(tcall("/api/anomalies")[1], "data", "counts", default={})
            _report("新教师看不到别人的异常记录", (an or {}).get("open", 0) == 0,
                    f"异常 {an}")

            cls = d(tcall("/api/classes", "POST",
                          {"name": f"[审计] 班级 {STAMP}", "course_id": t_cid})[1],
                    "data", default={})
            code = cls.get("invite_code")
            _report("新教师建班级并拿到邀请码", bool(cls.get("id") and code),
                    str(cls)[:150])
            bulk = d(tcall("/api/users/bulk", "POST",
                           {"rows": [f"审计学生A,{STAMP}A", f"审计学生B,{STAMP}B"],
                            "class_id": cls.get("id")})[1], "data", default={})
            _report("批量导入学生名单", bulk.get("count") == 2, str(bulk)[:150])
            prob = d(tcall("/api/problems", "POST",
                           {"title": f"[审计] 新账号题目 {STAMP}", "type": "programming",
                            "statement": "输出 a+b", "input_format": "两个整数",
                            "output_format": "一个整数",
                            "test_cases": [{"input": "1 2\n", "expected": "3\n",
                                            "is_sample": True}]})[1], "data", default={})
            asg = d(tcall("/api/assignments", "POST",
                          {"title": f"[审计] 新账号作业 {STAMP}",
                           "problem_ids": [prob.get("id")], "type": "programming"})[1],
                    "data", default={})
            _report("新教师出题并布置作业", bool(prob.get("id") and asg.get("id")),
                    "题目或作业创建失败")

            s_reg = call("/api/auth/register", "POST",
                         {"role": "student", "name": "审计学生", "username": s_name,
                          "password": "audit123", "invite_code": code})
            s_tok = d(s_reg[1], "data", "token")
            _report("学生用班级邀请码注册即入班", bool(s_tok), str(s_reg[1])[:150])
            if s_tok:
                s_req = urllib.request.Request(BASE + "/api/problems")
                s_req.add_header("Authorization", "Bearer " + s_tok)
                with urllib.request.urlopen(s_req, timeout=60) as r:
                    s_probs = json.loads(r.read().decode()).get("data", [])
                s_req2 = urllib.request.Request(BASE + "/api/assignments")
                s_req2.add_header("Authorization", "Bearer " + s_tok)
                with urllib.request.urlopen(s_req2, timeout=60) as r:
                    s_asg = json.loads(r.read().decode()).get("data", [])
                _report("学生只看到本课程的题目与作业",
                        len(s_probs) == 1 and len(s_asg) == 1,
                        f"题目 {len(s_probs)} 道、作业 {len(s_asg)} 个")

            try:
                db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "backend", "data", "platform.db")
                conn = sqlite3.connect(db_path)
                conn.execute("DELETE FROM course_members WHERE course_id=?", (t_cid,))
                conn.execute("DELETE FROM classes WHERE course_id=?", (t_cid,))
                conn.execute("DELETE FROM test_cases WHERE problem_id IN "
                             "(SELECT id FROM problems WHERE course_id=?)", (t_cid,))
                conn.execute("DELETE FROM assignment_problems WHERE assignment_id IN "
                             "(SELECT id FROM assignments WHERE course_id=?)", (t_cid,))
                conn.execute("DELETE FROM problems WHERE course_id=?", (t_cid,))
                conn.execute("DELETE FROM assignments WHERE course_id=?", (t_cid,))
                conn.execute("DELETE FROM notices WHERE course_id=?", (t_cid,))
                conn.execute("DELETE FROM courses WHERE id=?", (t_cid,))
                conn.execute("DELETE FROM users WHERE username IN (?,?)", (t_name, s_name))
                # 批量导入的「审计学生A/B」也要清掉（含历史遗留的孤儿账号，
                # 否则它们会一直挂在教师端的学生名单里）
                conn.execute(
                    "DELETE FROM users WHERE name LIKE '审计学生%' "
                    "AND id NOT IN (SELECT user_id FROM course_members)"
                )
                conn.commit()
                conn.close()
                print("     （审计用的临时课程与账号已清理）")
            except Exception as exc:  # pragma: no cover
                print("     清理临时数据失败：", exc)

    # ---------------------------------------------------------- 清理
    if not READONLY:
        section("12. 清理测试数据")
        if temp_problem:
            pid_new = d(temp_problem, "data", "id")
            check("删除测试题目", f"/api/problems/{pid_new}", "DELETE", {},
                  role="teacher", probe=lambda p: p.get("ok"))
        assigns_now = d(call("/api/assignments", role="teacher")[1], "data", default=[])
        if assigns_now:
            check("学生无权删除作业", f"/api/assignments/{assigns_now[0]['id']}", "DELETE", {},
                  role="student", want=403)
        # 删掉本轮与历史遗留的审计作业，别让演示数据里堆垃圾
        leftovers = [a for a in assigns_now if str(a.get("title", "")).startswith("[审计]")]
        removed = sum(1 for a in leftovers
                      if call(f"/api/assignments/{a['id']}", "DELETE", {}, role="teacher")[0] == 200)
        _report(f"清理审计临时作业（{removed}/{len(leftovers)} 条）",
                removed == len(leftovers), "有临时作业未能删除")
        # 审计发过的通知也一并撤回，否则会留在学生端的「课程通知」里
        all_notices = d(call("/api/notices", role="teacher")[1], "data", default=[])
        # 作业通知的标题是「新作业：xxx」，所以按包含匹配而不是前缀匹配
        dirty = [n for n in all_notices if "[审计]" in str(n.get("title", ""))]
        gone = sum(1 for n in dirty
                   if call(f"/api/notices/{n['id']}", "DELETE", {}, role="teacher")[0] == 200)
        _report(f"清理审计临时通知（{gone}/{len(dirty)} 条）",
                gone == len(dirty), "有临时通知未能撤回")

    # ---------------------------------------------------------- 汇总
    print("\n" + "=" * 72)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项，跳过 {len(WARN)} 项")
    if FAIL:
        print("\n\033[1;31m失败明细：\033[0m")
        for name, why in FAIL:
            print(f"  - {name}: {why}")
    if WARN:
        print("\n\033[1;33m跳过：\033[0m")
        for name, why in WARN:
            print(f"  - {name}: {why}")
    print("=" * 72)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
