"""演示数据生成：一门完整的《算法设计与分析》课程。

生成内容
--------
* 1 位主讲教师 + 1 位助教 + 48 名学生（分 2 个教学班）
* 12 个知识点（对应课程大纲章节）
* 10 道编程题（含真实测试数据与参考程序模板）+ 4 道主观题（含评分细则）
* 6 次作业（3 次编程、2 次互评主观题、1 次综合）
* 约 400 条编程提交记录：判定结果取自 ``verify_templates`` 的**真实评测缓存**，
  因此教师点「重测」时得到的结论与展示一致
* 2 轮 Peer Review（数百条评审），其中注入了「长期偏高」「长期偏低」
  「全部满分」「异常评审时长」「互相打高分」等异常样本
* 学习行为事件、知识点掌握度、成绩分布所需的全部原始数据

所有随机数由固定种子驱动，反复执行结果一致，便于实验复现。
"""

from __future__ import annotations

import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import courseware as CW  # noqa: E402
from backend import db, problem_bank as PB  # noqa: E402
from backend.algo import aggregation as AG  # noqa: E402
from backend.algo import anomaly as AN  # noqa: E402
from backend.algo import assignment as AS  # noqa: E402
from backend.auth import hash_password  # noqa: E402

CACHE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "template_verdicts.json"
)

#: 编程题默认的代码互评评分细则（与 backend/api.py 中的保持同一套维度）
CODE_RUBRIC = [
    {"key": "correctness", "name": "正确性", "max": 35,
     "desc": "算法是否正确，边界情况（n=1、极值、重复元素）是否处理"},
    {"key": "complexity", "name": "效率与复杂度", "max": 25,
     "desc": "是否达到题目要求的复杂度，有无不必要的重复计算"},
    {"key": "clarity", "name": "代码清晰度", "max": 20,
     "desc": "命名、结构、注释是否清晰易读"},
    {"key": "robustness", "name": "健壮性", "max": 20,
     "desc": "是否存在溢出、越界、未初始化等隐患"},
]

SEED = 20260926

#: 知识点直接取自实际授课课件的章节结构（backend/courseware.py），
#: 保证「题库 topics — 知识点统计 — 课件章节」三者是同一套命名。
KNOWLEDGE_POINTS = [
    (c["topic"], f"{c['no']} {c['title']}", c["summary"]) for c in CW.CHAPTERS
]

FIRST_NAMES = list(
    "梓涵子轩雨萱浩然欣怡俊杰诗涵宇轩雅涵思远嘉懿泽宇紫萱博文一诺可欣明轩雨泽佳怡语彤新宇梦琪天佑锦程欣然嘉怡子豪思彤书瑶奕辰"
)
SURNAMES = list(
    "李王张刘陈杨赵黄周吴徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾肖田董袁潘于蒋蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦邱江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤"
)


def _name(rng: random.Random, used: set) -> str:
    while True:
        n = rng.choice(SURNAMES) + rng.choice(FIRST_NAMES)
        if rng.random() < 0.3:
            n += rng.choice(FIRST_NAMES)
        if n not in used:
            used.add(n)
            return n


class Seeder:
    def __init__(self, reset: bool = True, verbose: bool = True):
        self.rng = random.Random(SEED)
        self.verbose = verbose
        self.reset = reset
        self.cache: dict = {}
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                self.cache = json.load(f)

    def log(self, *a) -> None:
        if self.verbose:
            print(*a, flush=True)

    # ------------------------------------------------------------------
    def run(self) -> dict:
        db.init_db()
        conn = db.get_conn()
        if self.reset:
            for t in [
                "users", "courses", "course_members", "knowledge_points", "problems",
                "test_cases", "assignments", "assignment_problems", "submissions",
                "test_results", "subjective_submissions", "allocations", "reviews",
                "anomalies", "events", "experiments", "notices", "settings",
                "sessions", "classes", "materials",
            ]:
                conn.execute(f"DELETE FROM {t}")
            conn.execute("DELETE FROM sqlite_sequence")
            conn.commit()
            self.log("已清空旧数据")

        ids: dict = {}
        ids.update(self._users())
        ids.update(self._course(ids))
        ids.update(self._knowledge(ids))
        ids.update(self._materials(ids))
        ids.update(self._problems(ids))
        ids.update(self._assignments(ids))
        self._submissions(ids)
        self._peer_review(ids)
        self._code_peer_review(ids)
        self._events(ids)
        self._notices(ids)
        self.log("演示数据生成完成")
        return ids

    # ------------------------------------------------------------------
    def _users(self) -> dict:
        now = db.now()
        pw, salt = hash_password("123456")
        rng = self.rng
        rows = [
            ("teacher", "teacher@ajp.edu.cn", pw, salt, "teacher", "张乾坤", None, None, "张"),
            ("ta", "ta@ajp.edu.cn", pw, salt, "ta", "陈思远", None, None, "TA"),
        ]
        used: set = set()
        abilities: dict[int, float] = {}
        for i in range(1, 49):
            name = _name(rng, used)
            cls = "算法2026级1班" if i <= 24 else "算法2026级2班"
            rows.append(("stu%d" % i, None, pw, salt, "student", name,
                         "2026%04d" % i, cls, name[0]))
        conn = db.get_conn()
        conn.executemany(
            "INSERT INTO users(username,email,password,salt,role,name,student_no,class_name,"
            "avatar,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            [tuple(r) + (now,) for r in rows],
        )
        conn.commit()
        users = db.rows2dicts(db.q("SELECT * FROM users ORDER BY id"))
        teacher = next(u for u in users if u["role"] == "teacher")
        ta = next(u for u in users if u["role"] == "ta")
        students = [u for u in users if u["role"] == "student"]
        for s in students:
            abilities[s["id"]] = rng.gauss(0.0, 1.0)
        self.log(f"  用户 {len(users)} 个（教师 1、助教 1、学生 {len(students)}）")
        return {"teacher": teacher, "ta": ta, "students": students, "abilities": abilities}

    # ------------------------------------------------------------------
    def _course(self, ids) -> dict:
        teacher = ids["teacher"]
        cid = db.ex(
            "INSERT INTO courses(name,code,term,teacher_id,description,invite_code,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (
                "算法设计与分析",
                "CS-ALGO-2026",
                "2026 秋",
                teacher["id"],
                "以「问题建模 → 算法设计 → 复杂度分析 → 实验验证」为主线，覆盖分治、贪心、"
                "动态规划、图算法、高级数据结构与字符串算法。",
                "ALGO26",
                db.now(),
            ),
        )
        members = [
            (cid, teacher["id"], "teacher", None, db.now()),
            (cid, ids["ta"]["id"], "ta", None, db.now()),
        ]
        db.exmany(
            "INSERT INTO course_members(course_id,user_id,role,class_id,joined_at) VALUES(?,?,?,?,?)",
            members,
        )
        # 建立班级并把学生关联进去（班级名沿用学生身上的 class_name）
        class_ids = {}
        for name in sorted({s["class_name"] for s in ids["students"] if s.get("class_name")}):
            code = "".join(ch for ch in name if ch.isdigit())[-4:] or name[:2]
            class_ids[name] = db.ex(
                "INSERT INTO classes(course_id,name,description,invite_code,created_at) "
                "VALUES(?,?,?,?,?)",
                (cid, name, "", ("CLS" + code.upper())[:8], db.now()),
            )
        db.exmany(
            "INSERT INTO course_members(course_id,user_id,role,class_id,joined_at) VALUES(?,?,?,?,?)",
            [
                (cid, s["id"], "student", class_ids.get(s.get("class_name")), db.now())
                for s in ids["students"]
            ],
        )
        self.log(
            f"  课程 #{cid} 建立，成员 {len(members) + len(ids['students'])} 人，"
            f"班级 {len(class_ids)} 个"
        )
        return {"course_id": cid}

    # ------------------------------------------------------------------
    def _knowledge(self, ids) -> dict:
        db.exmany(
            "INSERT INTO knowledge_points(course_id,name,chapter,description) VALUES(?,?,?,?)",
            [(ids["course_id"], n, ch, d) for n, ch, d in KNOWLEDGE_POINTS],
        )
        return {"knowledge_points": db.rows2dicts(db.q("SELECT * FROM knowledge_points ORDER BY id"))}

    # ------------------------------------------------------------------
    def _materials(self, ids) -> dict:
        """把导入的授课课件登记到课件库（PDF 本体在 frontend/courseware/）。"""
        rows = CW.material_rows()
        if not rows:
            self.log("  课件：未导入（先运行 tools/import_courseware.py）")
            return {"materials": []}
        db.exmany(
            "INSERT INTO materials(course_id,chapter,chapter_title,title,filename,url,"
            "size_bytes,pages,sha256,topics,summary,order_index,uploaded_by,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    ids["course_id"], r["chapter"], r["chapter_title"], r["title"],
                    r["filename"], r["url"], r["size_bytes"], r["pages"], r["sha256"],
                    db.jdumps(r["topics"]), r["summary"], r["order_index"],
                    ids["teacher"]["id"], db.now(),
                )
                for r in rows
            ],
        )
        total = sum(r["size_bytes"] for r in rows)
        self.log(f"  课件 {len(rows)} 份（{total / 1048576:.1f} MB），覆盖 {len(CW.CHAPTERS)} 个章节")
        return {"materials": rows}

    # ------------------------------------------------------------------
    def _problems(self, ids) -> dict:
        teacher = ids["teacher"]["id"]
        cid = ids["course_id"]
        prog, subj = [], []
        for p in PB.PROBLEMS:
            cases = (self.cache.get(p["key"], {}) or {}).get("cases") or PB.build_cases(p)
            samples = [
                {"input": c["input"], "output": c["expected"]}
                for c in cases
                if c.get("is_sample")
            ]
            pid = db.ex(
                "INSERT INTO problems(course_id,title,type,difficulty,topics,statement,input_format,"
                "output_format,constraints,samples,time_limit_ms,memory_limit_mb,score,rubric,"
                "created_by,created_at,tags,chapter) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    cid, p["title"], "programming", p["difficulty"], db.jdumps(p["topics"]),
                    p["statement"], p["input_format"], p["output_format"], p["constraints"],
                    db.jdumps(samples), p["time_limit_ms"], p["memory_limit_mb"], 100,
                    db.jdumps(CODE_RUBRIC),
                    teacher, db.now(), db.jdumps(p.get("tags", [])),
                    p.get("chapter"),
                ),
            )
            db.exmany(
                "INSERT INTO test_cases(problem_id,name,input,expected,is_sample,score,order_index) "
                "VALUES(?,?,?,?,?,?,?)",
                [
                    (pid, c["name"], c["input"], c["expected"], c.get("is_sample", 0),
                     c.get("score", 10), i)
                    for i, c in enumerate(cases)
                ],
            )
            prog.append({"id": pid, "meta": p})

        for s in PB.SUBJECTIVE:
            pid = db.ex(
                "INSERT INTO problems(course_id,title,type,difficulty,topics,statement,input_format,"
                "output_format,constraints,samples,time_limit_ms,memory_limit_mb,score,rubric,"
                "created_by,created_at,tags,chapter) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    cid, s["title"], s["type"], s["difficulty"], db.jdumps(s["topics"]),
                    s["statement"], "", "", "", db.jdumps([{"sections": s["sections"]}]),
                    0, 0, 100, db.jdumps(PB.RUBRIC_STANDARD), teacher, db.now(), db.jdumps([]),
                    s.get("chapter"),
                ),
            )
            subj.append({"id": pid, "meta": s})
        self.log(f"  题目 {len(prog)} 道编程题 + {len(subj)} 道主观题")
        return {"prog_problems": prog, "subj_problems": subj}

    # ------------------------------------------------------------------
    def _assignments(self, ids) -> dict:
        cid = ids["course_id"]
        teacher = ids["teacher"]["id"]
        by_key = {p["meta"]["key"]: p for p in ids["prog_problems"]}
        subj = ids["subj_problems"]

        def mk(title, desc, probs, start, due, review_due, status, peer=0, k=3, maxload=4):
            aid = db.ex(
                "INSERT INTO assignments(course_id,title,description,type,start_at,due_at,"
                "review_due_at,reviews_per_submission,max_load,aggregation_method,allocate_method,"
                "params,status,peer_review,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    cid, title, desc, "subjective" if peer else "programming", start, due,
                    review_due, k, maxload, "reliability_em", "mcmf", "{}", status, peer,
                    teacher, start,
                ),
            )
            db.exmany(
                "INSERT INTO assignment_problems(assignment_id,problem_id,score,order_index) "
                "VALUES(?,?,?,?)",
                [(aid, p["id"], 100, i) for i, p in enumerate(probs)],
            )
            return aid

        A = {
            # ---- 编程作业（自动评测），按课件章节组织 ----
            "a1": mk("编程作业一：贪心与分治（第 3–4 章）",
                     "对应课件 Chapter 3 区间调度 / 区间分割 / 最小延迟调度，"
                     "以及 Chapter 4 的归并排序与逆序对。",
                     [by_key["ACTIVITY"], by_key["PARTITION"], by_key["LATENESS"],
                      by_key["INVERSION"]],
                     db.days_ago(34, 8, 0), db.days_ago(20, 23, 59), None, "closed"),
            "a2": mk("编程作业二：动态规划（第 5 章）",
                     "最大子数组、0/1 背包、序列对齐（编辑距离）与最长公共子序列，"
                     "重点考察状态定义与递推方向。",
                     [by_key["KADANE"], by_key["KNAPSACK"], by_key["EDITDIST"], by_key["LCS"]],
                     db.days_ago(26, 8, 0), db.days_ago(13, 23, 59), None, "closed"),
            "a3": mk("编程作业三：图的搜索与并查集（第 2、7 章）",
                     "BFS 最短路、拓扑排序、连通块计数与 Kruskal 最小生成树。",
                     [by_key["MAZE"], by_key["TOPO"], by_key["DSU"], by_key["MST"]],
                     db.days_ago(12, 8, 0), db.days_ahead(3, 23, 59), None, "published"),
            "a4": mk("编程作业四：线段树、树状数组与网络流（第 6、8、9 章）",
                     "两道区间数据结构题 + 一道最大流，重点考察复杂度是否达标。",
                     [by_key["SEGTREE"], by_key["BIT"], by_key["MAXFLOW"]],
                     db.days_ago(7, 8, 0), db.days_ahead(7, 23, 59), None, "published"),
            "a5": mk("编程作业五：字符串匹配与综合练习（第 10 章）",
                     "KMP 为主，另附带权最短路与二分答案两道拓展题。",
                     [by_key["KMP"], by_key["DIJKSTRA"], by_key["CUT"]],
                     db.days_ago(3, 8, 0), db.days_ahead(11, 23, 59), None, "published"),
            # ---- 主观题作业（匿名互评）----
            "a6": mk("算法分析报告一：复杂度与动态规划（第 1、5 章）",
                     "主观题作业，提交后由同学匿名互评。请按评分细则分点作答。",
                     [subj[0], subj[3]],
                     db.days_ago(32, 8, 0), db.days_ago(18, 23, 59), db.days_ago(11, 23, 59),
                     "closed", peer=1, k=3, maxload=4),
            "a7": mk("算法设计报告二：贪心正确性与有向图环检测（第 2、3 章）",
                     "证明题 + 开放性设计题。互评进行中，请注意评审截止时间。",
                     [subj[1], subj[2]],
                     db.days_ago(14, 8, 0), db.days_ago(5, 23, 59), db.days_ahead(7, 23, 59),
                     "reviewing", peer=1, k=3, maxload=4),
            "a8": mk("算法分析报告三：主定理与并查集复杂度（第 4、7 章）",
                     "主定理求解递归式、Karatsuba / Strassen 分析，以及并查集两种启发式的复杂度论证。",
                     [subj[4], subj[6]],
                     db.days_ago(10, 8, 0), db.days_ahead(4, 23, 59), db.days_ahead(12, 23, 59),
                     "published", peer=1, k=3, maxload=4),
            "a9": mk("算法分析报告四：最大流最小割与 NP 完全性（第 6、11 章）",
                     "两道证明题，重点考察规约与证明链条是否完整。",
                     [subj[5], subj[8]],
                     db.days_ago(6, 8, 0), db.days_ahead(8, 23, 59), db.days_ahead(16, 23, 59),
                     "published", peer=1, k=3, maxload=4),
            "a10": mk("算法分析报告五：字符串匹配与数据结构选型（第 8、10 章）",
                      "KMP 均摊分析与线段树/树状数组选型设计。",
                      [subj[7], subj[9]],
                      db.days_ago(4, 8, 0), db.days_ahead(10, 23, 59), db.days_ahead(18, 23, 59),
                      "published", peer=1, k=3, maxload=4),
            # ---- 代码互评：评审对象是同学写的代码 ----
            "a11": mk("代码互评：图算法与数据结构实现评析",
                      "对同学提交的代码进行匿名互评，从正确性、复杂度、清晰度与健壮性四个维度打分。",
                      [by_key["MAZE"], by_key["DSU"], by_key["SEGTREE"]],
                      db.days_ago(21, 8, 0), db.days_ago(14, 23, 59), db.days_ago(8, 23, 59),
                      "closed", peer=1, k=3, maxload=4),
        }
        self.log(f"  作业 {len(A)} 次（5 次编程 + 5 次主观互评 + 1 次代码互评）")
        return {"assignments": A}

    # ------------------------------------------------------------------
    def _submissions(self, ids) -> None:
        rng = self.rng
        by_id = {p["id"]: p for p in ids["prog_problems"]}
        studs = ids["students"]
        abilities = ids["abilities"]
        A = ids["assignments"]
        plan = [
            (A["a1"], 0.97), (A["a2"], 0.95), (A["a3"], 0.80),
            (A["a4"], 0.66), (A["a5"], 0.52),
        ]
        sub_rows, tc_rows = [], []
        dist: dict[str, int] = {}
        for aid, prob_rate in plan:
            meta_a = db.q1("SELECT start_at,due_at FROM assignments WHERE id=?", (aid,))
            start, due = self._parse(meta_a["start_at"]), self._parse(meta_a["due_at"])
            probs = db.rows2dicts(
                db.q(
                    "SELECT p.* FROM assignment_problems ap JOIN problems p ON p.id=ap.problem_id "
                    "WHERE ap.assignment_id=? ORDER BY ap.order_index",
                    (aid,),
                )
            )
            for prob in probs:
                meta = by_id[prob["id"]]["meta"]
                key = meta["key"]
                cache_v = (self.cache.get(key, {}) or {}).get("verdicts", {})
                diff = (meta["difficulty"] - 3) * 0.45
                for st in studs:
                    ab = abilities[st["id"]]
                    p_submit = max(0.05, min(0.99, prob_rate + 0.16 * ab - 0.13 * diff))
                    if rng.random() > p_submit:
                        continue
                    skill = ab - diff + rng.gauss(0, 0.55)
                    if skill > 0.65 and "ok" in cache_v:
                        tag = "ok"
                    elif skill < -0.8:
                        tag = "bug" if "bug" in cache_v else "slow"
                    else:
                        tag = rng.choice([t for t in ("slow", "bug", "ok") if t in cache_v] or ["ok"])
                    if tag == "ok" and rng.random() < 0.3:
                        tag = "bug" if "bug" in cache_v else tag
                    v = cache_v.get(tag) or {
                        "verdict": "Wrong Answer", "score": 0.0, "time_ms": 20.0,
                        "memory_kb": 5000.0, "passed": 0, "total_cases": 1,
                    }
                    verdict = v["verdict"]
                    # 语言选择：多数 C++，少数 Python / Java
                    r = rng.random()
                    lang = "cpp" if r < 0.8 else ("python" if r < 0.95 else "java")
                    if lang == "cpp":
                        src = PB.CPP.get(key, {}).get(tag) or PB.PY.get(key, "")
                    elif lang == "python":
                        src = PB.PY.get(key)
                        if not src:
                            lang, src = "cpp", PB.CPP.get(key, {}).get(tag, "")
                    else:
                        lang = "python" if PB.PY.get(key) else "cpp"
                        src = PB.PY.get(key) if lang == "python" else PB.CPP.get(key, {}).get(tag, "")
                    attempts = 1
                    if verdict != "Accepted":
                        attempts += rng.randint(0, 2)
                    when = self._between(start, due, rng)
                    detail = {
                        "passed": v.get("passed"), "total_cases": v.get("total_cases"),
                        "template": tag, "simulated": True,
                    }
                    sub_rows.append(
                        (aid, prob["id"], st["id"], lang, src, when, "done", verdict,
                         float(v["score"]),
                         round(v["time_ms"] * rng.uniform(0.85, 1.28), 2),
                         round(v["memory_kb"] * rng.uniform(0.94, 1.07), 1),
                         "", attempts, db.jdumps(detail), None)
                    )
                    dist[verdict] = dist.get(verdict, 0) + 1
        db.exmany(
            "INSERT INTO submissions(assignment_id,problem_id,user_id,language,source_code,"
            "submitted_at,status,verdict,score,time_ms,memory_kb,compile_message,attempt_no,"
            "detail,complexity) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            sub_rows,
        )
        # 逐测试点明细：AC 全通过，非 AC 按「先通过、后失败」构造
        case_index = {
            p["id"]: db.rows2dicts(
                db.q("SELECT id,name FROM test_cases WHERE problem_id=? ORDER BY id", (p["id"],))
            )
            for p in ids["prog_problems"]
        }
        for s in db.rows2dicts(db.q("SELECT * FROM submissions ORDER BY id")):
            cases = case_index.get(s["problem_id"]) or []
            if not cases:
                continue
            d = db.jloads(s["detail"], {})
            passed = d.get("passed")
            if passed is None:
                passed = len(cases)
            total_cases = len(cases)
            scale = max(1, d.get("total_cases") or total_cases)
            passed_real = int(round(passed / scale * total_cases))
            verdict = s["verdict"]
            for i, c in enumerate(cases):
                if verdict == "Accepted" or i < passed_real:
                    vd, msg = "AC", "通过"
                elif verdict == "Time Limit Exceeded":
                    vd, msg = "TLE", "超过时间限制"
                else:
                    vd, msg = verdict, {"Wrong Answer": "输出与期望不一致",
                                        "Runtime Error": "运行错误"}.get(verdict, "未通过")
                tc_rows.append(
                    (s["id"], c["id"], c["name"], vd,
                     round((s["time_ms"] or 1.0) * rng.uniform(0.55, 1.12), 2),
                     round((s["memory_kb"] or 0) * rng.uniform(0.96, 1.04), 1), msg, "")
                )
        db.exmany(
            "INSERT INTO test_results(submission_id,test_case_id,name,verdict,time_ms,memory_kb,"
            "message,output) VALUES(?,?,?,?,?,?,?,?)",
            tc_rows,
        )
        self.log(
            f"  提交 {len(sub_rows)} 条，测试点明细 {len(tc_rows)} 条；判定分布 "
            + ", ".join(f"{k}={v}" for k, v in sorted(dist.items()))
        )

    # ------------------------------------------------------------------
    def _peer_review(self, ids) -> None:
        rng = self.rng
        studs = ids["students"]
        abilities = ids["abilities"]
        A = ids["assignments"]
        klass = {s["id"]: s["class_name"] for s in studs}

        bias = {s["id"]: rng.gauss(0, 2.6) for s in studs}
        noise = {s["id"]: abs(rng.gauss(4.2, 1.4)) + 1.0 for s in studs}
        speed = {s["id"]: max(0.35, rng.gauss(1.0, 0.25)) for s in studs}
        order = [s["id"] for s in studs]
        harsh, lenient, allmax, rusher, flat = order[7], order[21], order[33], order[44], order[39]
        collude = (order[11], order[12])
        bias[harsh] -= 14.0
        bias[lenient] += 12.0
        speed[rusher] *= 0.04
        noise[allmax] = 0.7

        for aid, status in ((A["a6"], "done"), (A["a7"], "reviewing")):
            tw = db.q1("SELECT reviews_per_submission,max_load FROM assignments WHERE id=?", (aid,))
            k, maxload = tw["reviews_per_submission"], tw["max_load"]
            probs = db.rows2dicts(
                db.q(
                    "SELECT p.* FROM assignment_problems ap JOIN problems p ON p.id=ap.problem_id "
                    "WHERE ap.assignment_id=? ORDER BY ap.order_index",
                    (aid,),
                )
            )
            for prob in probs:
                authors = [s["id"] for s in studs if rng.random() < 0.96]
                truth = {
                    a: max(5.0, min(98.0, 62 + 13 * abilities[a] + rng.gauss(0, 5)))
                    for a in authors
                }
                params = AS.AllocationParams(
                    reviews_per_submission=k, max_load=maxload, seed=SEED + aid + prob["id"]
                )
                res = (
                    AS.allocate_mcmf(authors, authors, klass, params)
                    if status == "done"
                    else AS.allocate_greedy(authors, authors, klass, params)
                )
                allocs = res.allocations
                if status == "done" and prob["id"] == ids["subj_problems"][0]["id"]:
                    # 注入一对「互相打高分」的固定互评关系，用于演示异常关系检测
                    allocs = self._force_mutual(allocs, collude[0], collude[1])
                db.exmany(
                    "INSERT OR IGNORE INTO allocations(assignment_id,problem_id,author_id,reviewer_id,"
                    "status,round,weight,is_anomaly,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    [(aid, prob["id"], a, r, "pending", 1, 1.0, 0, db.now())
                     for (a, r) in allocs],
                )
                db.exmany(
                    "INSERT INTO subjective_submissions(assignment_id,problem_id,user_id,content,"
                    "submitted_at,status,final_score,methods,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    [
                        (aid, prob["id"], a,
                         db.jdumps(self._content(prob, abilities[a], rng)),
                         db.now(), "reviewing" if status == "reviewing" else "done",
                         None, "{}", db.now())
                        for a in authors
                    ],
                )
                if status == "reviewing":
                    continue
                alls = db.rows2dicts(
                    db.q("SELECT * FROM allocations WHERE assignment_id=? AND problem_id=?",
                         (aid, prob["id"]))
                )
                review_rows = []
                for al in alls:
                    a, r = al["author_id"], al["reviewer_id"]
                    t = truth.get(a, 65.0)
                    if r == allmax:
                        base = 98.5
                    elif r == flat:
                        base = 75.0
                    else:
                        base = t + bias[r]
                    if (r == collude[0] and a == collude[1]) or (r == collude[1] and a == collude[0]):
                        base += 9
                    if r == flat:
                        total = 75.0
                    elif r == collude[0] and a == collude[1]:
                        total = 94.0
                    elif r == collude[1] and a == collude[0]:
                        total = 95.0
                    else:
                        total = max(0.0, min(100.0, base + rng.gauss(0, noise[r])))
                    review_rows.append(
                        (al["id"], aid, prob["id"], None, r, a,
                         db.jdumps(self._rubric(total, rng)), round(total, 2),
                         self._comment(total, rng),
                         round(max(8.0, rng.gauss(430, 130) * speed[r]), 1),
                         None, db.now(), 0, None)
                    )
                db.exmany(
                    "INSERT INTO reviews(allocation_id,assignment_id,problem_id,submission_id,"
                    "reviewer_id,author_id,scores,total,comment,duration_sec,started_at,submitted_at,"
                    "flagged,flag_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    review_rows,
                )
                db.ex(
                    "UPDATE allocations SET status='done' WHERE assignment_id=? AND problem_id=?",
                    (aid, prob["id"]),
                )
                self._aggregate(aid, prob["id"])
        self.log("  Peer Review 分配与评分完成")

    # ------------------------------------------------------------------
    def _code_peer_review(self, ids) -> None:
        """代码互评：对象是同学写的代码，与主观题互评走同一套流程。

        评审基准分 = 0.5 × 自动评测得分 + 0.5 × 主观质量（由能力值生成），
        再叠加评审者宽严偏差与噪声——这样「自动评测」与「人工评审」既相关又不重合，
        正好用来演示异常检测与可信度加权。
        """
        rng = self.rng
        aid = ids["assignments"]["a11"]
        studs = ids["students"]
        abilities = ids["abilities"]
        klass = {s["id"]: s["class_name"] for s in studs}
        tw = db.q1("SELECT reviews_per_submission,max_load FROM assignments WHERE id=?", (aid,))
        k, maxload = tw["reviews_per_submission"], tw["max_load"]
        bias = {s["id"]: rng.gauss(0, 2.6) for s in studs}
        noise = {s["id"]: abs(rng.gauss(4.0, 1.3)) + 1.2 for s in studs}
        probs = db.rows2dicts(db.q(
            "SELECT p.* FROM assignment_problems ap JOIN problems p ON p.id=ap.problem_id "
            "WHERE ap.assignment_id=? ORDER BY ap.order_index", (aid,)))
        for prob in probs:
            authors = [r["user_id"] for r in db.q(
                "SELECT DISTINCT user_id FROM submissions WHERE problem_id=? ORDER BY user_id",
                (prob["id"],))]
            if len(authors) < 2:
                continue
            params = AS.AllocationParams(
                reviews_per_submission=k, max_load=maxload, seed=SEED + aid * 7 + prob["id"])
            res = AS.allocate_mcmf(authors, authors, klass, params)
            db.exmany(
                "INSERT OR IGNORE INTO allocations(assignment_id,problem_id,author_id,reviewer_id,"
                "status,round,weight,is_anomaly,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                [(aid, prob["id"], a, r, "pending", 1, 1.0, 0, db.now())
                 for (a, r) in res.allocations],
            )
            # 每位作者最好的一次提交（评审对象）
            best = {}
            for row in db.q(
                "SELECT * FROM submissions WHERE problem_id=? "
                "ORDER BY (verdict='Accepted') DESC, score DESC, id DESC", (prob["id"],)):
                best.setdefault(row["user_id"], row)
            review_rows = []
            for al in db.rows2dicts(db.q(
                    "SELECT * FROM allocations WHERE assignment_id=? AND problem_id=?",
                    (aid, prob["id"]))):
                a, r = al["author_id"], al["reviewer_id"]
                # 留出约 15% 的分配不评，模拟「还有同学没完成互评」，
                # 这样学生端能真实看到待完成的代码互评任务
                if rng.random() < 0.15:
                    continue
                sub = best.get(a)
                auto = float(sub["score"]) if sub else 40.0
                style = 62 + 13 * abilities[a] + rng.gauss(0, 6)
                total = max(0.0, min(100.0, 0.5 * auto + 0.5 * style + bias[r] + rng.gauss(0, noise[r])))
                review_rows.append(
                    (al["id"], aid, prob["id"], sub["id"] if sub else None, r, a,
                     db.jdumps(self._rubric(total, rng)), round(total, 2),
                     self._comment(total, rng),
                     round(max(30.0, rng.gauss(380, 110))), None, db.now(), 0, None)
                )
            if review_rows:
                db.exmany(
                    "INSERT INTO reviews(allocation_id,assignment_id,problem_id,submission_id,"
                    "reviewer_id,author_id,scores,total,comment,duration_sec,started_at,"
                    "submitted_at,flagged,flag_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    review_rows,
                )
            # 只有真正提交了评审的分配才标记为完成，其余保持 pending
            db.ex(
                "UPDATE allocations SET status='done' WHERE assignment_id=? AND problem_id=? "
                "AND id IN (SELECT allocation_id FROM reviews "
                "           WHERE assignment_id=? AND problem_id=?)",
                (aid, prob["id"], aid, prob["id"]),
            )
            self._aggregate(aid, prob["id"])
        self.log("  代码互评（基于学生代码的评审）完成")

    # ------------------------------------------------------------------
    # 辅助：时间与文本
    # ------------------------------------------------------------------
    @staticmethod
    def _force_mutual(alloc: list, x: int, y: int) -> list:
        """强制让 x 与 y 互为评审（用于演示「固定互评关系」异常检测）。

        做法是把 x、y 各自的一条既有分配改写成指向对方，既不增加评审总量，
        也不会破坏「每人评审数量基本一致」的整体约束。
        """
        out = list(alloc)
        have = set(out)
        for author, reviewer in ((y, x), (x, y)):
            if (author, reviewer) in have:
                continue
            idx = next(
                (i for i, (au, rv) in enumerate(out) if au == author and rv != reviewer and (au, rv) != (author, x)),
                None,
            )
            if idx is None:
                continue
            have.discard(out[idx])
            out[idx] = (author, reviewer)
            have.add((author, reviewer))
        return out

    @staticmethod
    def _parse(s: str):
        from datetime import datetime

        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")

    def _between(self, a, b, rng) -> str:
        from datetime import datetime

        now = datetime.now()
        hi = min(b, now)
        if hi <= a:
            hi = a
        span = max(0.0, (hi - a).total_seconds())
        return (a + __import__("datetime").timedelta(seconds=span * rng.uniform(0.1, 0.99))).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    def _content(self, prob: dict, ability: float, rng: random.Random) -> dict:
        meta = next((s for s in PB.SUBJECTIVE if s["title"] == prob["title"]), PB.SUBJECTIVE[0])
        quality = max(0.06, min(0.99, 0.5 + 0.3 * ability + rng.gauss(0, 0.14)))
        out = {}
        for s in meta["sections"]:
            n = int(90 + 430 * quality * rng.uniform(0.7, 1.3))
            out[s["key"]] = self._para(prob, s, n, quality, rng)
        out["_quality"] = round(quality, 4)
        return out

    def _para(self, prob: dict, sec: dict, n: int, q: float, rng: random.Random) -> str:
        topic = prob["title"]
        good = [
            f"针对「{topic}」中的{sec['name']}，我先把问题抽象成三元组（输入规模 n、约束、目标函数），再讨论算法。",
            "复杂度推导用主定理：T(n) = 2T(n/2) + Θ(n) 时 a=2、b=2、log_b a=1 落在第二种情形，故 T(n) = Θ(n log n)。",
            "空间上除存储输入外只额外维护常数个游标，因此 S(n) = O(1)；递归实现时栈深为 O(log n)。",
            "实验固定编译器与优化等级（-O2），每个规模重复 5 次取中位数，并先预热一次以排除首次进程启动与磁盘缓存开销。",
            "边界情况要单独处理：n = 1、全部元素为负、关键字重复、图不连通、存在自环与重边。",
            "用交换论证证明贪心选择性质：设最优解 O 与贪心首选项 g 不同，把 O 中第一个与 g 冲突的元素替换为 g，仍可行且不劣。",
            "无后效性的关键在于把状态定义在「已处理阶段」上，使后续决策只依赖当前状态而不依赖到达路径。",
            "对拍验证：用暴力枚举生成小规模随机数据与优化算法逐一比对，共 2000 组未发现不一致。",
        ]
        weak = [
            f"关于「{topic}」的{sec['name']}，我的想法是直接按题目要求做，复杂度大概是 O(n²) 左右。",
            "时间复杂度没有仔细算，感觉应该不会太慢。",
            "空间复杂度是 O(n)，具体怎么来的我说不太清楚。",
            "实验时随便测了几组数据，发现运行得挺快的。",
            "边界情况应该不用特别处理，题目数据一般不会卡。",
            "证明部分我举了几个例子验证，都能得到正确答案。",
        ]
        pool = good if q > 0.55 else (good[:4] + weak if q > 0.34 else weak)
        parts, total = [], 0
        while total < n:
            s = rng.choice(pool)
            parts.append(s)
            total += len(s)
        text = "".join(parts)[:n]
        if q > 0.6 and rng.random() < 0.6:
            text += (
                "\n\n伪代码：\n```\nfunction solve(n, a):\n    best <- -inf\n    cur <- 0\n"
                "    for i from 1 to n:\n        cur <- max(a[i], cur + a[i])\n"
                "        best <- max(best, cur)\n    return best\n```\n"
                "每轮只做常数次比较与加法，故总复杂度 Θ(n)，空间 Θ(1)。"
            )
        return text

    def _rubric(self, total: float, rng: random.Random) -> dict:
        keys = [(r["key"], r["max"]) for r in PB.RUBRIC_STANDARD]
        raw = []
        for _k, mx in keys:
            raw.append(max(0.0, min(float(mx), total / 100.0 * mx + rng.gauss(0, mx * 0.11))))
        s = sum(raw) or 1.0
        return {k: round(v * (total / s) if s else 0.0, 1) for (k, _m), v in zip(keys, raw)}

    def _comment(self, total: float, rng: random.Random) -> str:
        hi = [
            "思路清晰，复杂度推导完整，对最坏情况的讨论很到位。",
            "对拍实验设计规范，边界情况考虑周全，继续保持。",
            "伪代码规范，正确性证明用交换论证写得很有说服力。",
        ]
        mid = [
            "主体思路正确，但复杂度分析只写了结论，建议补上推导步骤。",
            "证明部分缺少归纳假设的明确表述，读者容易跟不上。",
            "实验方案可以更具体：说明重复次数与计时方法会更有说服力。",
        ]
        lo = [
            "只给出结论，几乎没有推导过程，建议参考教材第 2 章重新整理。",
            "关键步骤缺失，边界情况没有讨论，希望补充完整。",
            "表达偏口语化，建议使用规范术语并分点作答。",
        ]
        pool = hi if total >= 85 else (mid if total >= 68 else lo)
        return rng.choice(pool) + (" 另外建议把伪代码缩进统一一下。" if rng.random() < 0.4 else "")

    # ------------------------------------------------------------------
    def _aggregate(self, aid: int, pid: int) -> None:
        rows = db.rows2dicts(
            db.q("SELECT * FROM reviews WHERE assignment_id=? AND problem_id=?", (aid, pid))
        )
        if not rows:
            return
        rl = [
            {
                "submission_id": r["author_id"],
                "reviewer_id": r["reviewer_id"],
                "score": r["total"],
                "author_id": r["author_id"],
                "duration_sec": r["duration_sec"],
                "rubric": db.jloads(r["scores"]),
            }
            for r in rows
        ]
        methods: dict = {}
        for m in AG.METHODS:
            methods[m] = {
                str(k): round(v, 2) for k, v in AG.aggregate(rl, m)["scores"].items()
            }
        em = AG.aggregate(rl, "reliability_em")
        conn = db.get_conn()
        is_code = bool(db.q1(
            "SELECT id FROM problems WHERE id=? AND type='programming'", (pid,)))
        for uid, sc in em["scores"].items():
            if is_code:
                conn.execute(
                    "UPDATE submissions SET review_score=?, review_methods=? WHERE id=("
                    "  SELECT id FROM submissions WHERE problem_id=? AND user_id=? "
                    "  ORDER BY (verdict='Accepted') DESC, score DESC, id DESC LIMIT 1)",
                    (round(sc, 2), db.jdumps(methods), pid, uid),
                )
            else:
                conn.execute(
                    "UPDATE subjective_submissions SET status='done', final_score=?, methods=?, "
                    "updated_at=? WHERE assignment_id=? AND problem_id=? AND user_id=?",
                    (round(sc, 2), db.jdumps(methods), db.now(), aid, pid, uid),
                )
        conn.commit()
        det = AN.detect(rl)
        rows2 = [
            (aid, a["type"], a["level"], a.get("reviewer_id"), a.get("submission_id"),
             a["title"], a["detail"], db.jdumps(a.get("evidence", {})), a["suggestion"],
             "open", None, None, db.now())
            for a in det["anomalies"]
        ]
        if rows2:
            conn.executemany(
                "INSERT INTO anomalies(assignment_id,type,level,reviewer_id,submission_id,title,"
                "detail,evidence,suggestion,status,handled_by,note,detected_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                rows2,
            )
        conn.executemany(
            "UPDATE allocations SET weight=? WHERE assignment_id=? AND problem_id=? AND reviewer_id=?",
            [
                (round(em["detail"]["reliability"].get(rid, 1.0), 4), aid, pid, rid)
                for rid in em["detail"]["reliability"]
            ],
        )
        conn.commit()

    # ------------------------------------------------------------------
    def _events(self, ids) -> None:
        rng = self.rng
        cid = ids["course_id"]
        types = ["login", "view_problem", "run_code", "submit", "view_solution",
                 "open_review", "submit_review"]
        rows = []
        for s in ids["students"]:
            for _ in range(rng.randint(18, 46)):
                t = rng.choices(types, weights=[6, 12, 14, 10, 3, 6, 5])[0]
                rows.append(
                    (s["id"], cid, t, db.jdumps({"duration": rng.randint(60, 1800)}),
                     db.days_ago(rng.randint(0, 30), rng.randint(8, 23), rng.randint(0, 59)))
                )
        db.exmany(
            "INSERT INTO events(user_id,course_id,type,payload,created_at) VALUES(?,?,?,?,?)", rows
        )
        self.log(f"  学习行为事件 {len(rows)} 条")

    def _notices(self, ids) -> None:
        db.exmany(
            "INSERT INTO notices(course_id,title,content,author_id,created_at) VALUES(?,?,?,?,?)",
            [
                (ids["course_id"], "互评通道已开放",
                 "《算法设计报告二：贪心正确性与有向图环检测》的匿名互评已开放，"
                 "请在本周日 23:59 前完成 3 份评审，"
                 "评审时请按评分细则分点给分。",
                 ids["teacher"]["id"], db.days_ago(3, 10, 0)),
                (ids["course_id"], "编程作业三延长 2 天",
                 "拓扑排序与 Kruskal 两道题需要写完并调通，作业三截止时间顺延两天；"
                 "对应的课件在「课程资源 → Chapter 2 / Chapter 7」。",
                 ids["teacher"]["id"], db.days_ago(1, 16, 30)),
                (ids["course_id"], "课件已按章节上传",
                 "12 个章节的授课课件都放到「课程资源」里了，做题前可以先过一遍对应章节；"
                 "每章的课件页面右上角可以直接跳到本章题目。",
                 ids["teacher"]["id"], db.days_ago(5, 9, 0)),
            ],
        )
        # 标记「当前数据是系统生成的演示数据」，前端会在顶栏显示提示。
        # 当教师导入自己班级的真实名单后，可删除这条记录（见 docs/使用手册.md）。
        db.ex(
            "INSERT OR REPLACE INTO settings(key,value) VALUES('demo_seed',?)", (db.now(),)
        )


def seed(reset: bool = True, verbose: bool = True) -> dict:
    return Seeder(reset=reset, verbose=verbose).run()


if __name__ == "__main__":
    seed(reset="--keep" not in sys.argv, verbose=True)
