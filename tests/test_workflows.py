"""HTTP 回归：临时空数据库，覆盖跨课程、截止时间、评分、匿名与重分配。

    python tests/test_workflows.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
WORK = tempfile.TemporaryDirectory(prefix="ajp-regression-")
os.environ["AJP_DB"] = str(Path(WORK.name) / "test.db")
from backend import api, db, server  # noqa: E402


class Workflows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()
        server.compile_routes()
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.httpd.daemon_threads = True
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:" + str(cls.httpd.server_port)
        cls.serial = 0

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()
        db.close_conn()
        WORK.cleanup()

    def call(self, path, body=None, token=None, method=None, want=200):
        req = urllib.request.Request(self.base + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None)
        req.add_header("Content-Type", "application/json")
        req.add_header("Connection", "close")
        if token:
            req.add_header("Authorization", "Bearer " + token)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                status, data = response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            with exc:
                status, data = exc.code, json.load(exc)
        self.assertEqual(status, want, (path, data))
        return data.get("data", data)

    def register(self, role, suffix, invite=None):
        return self.call("/api/auth/register", {
            "username": f"workflow{self.serial}_{suffix}", "name": suffix,
            "password": "test123456", "role": role, "invite_code": invite})

    def setUp(self):
        type(self).serial += 1
        a = self.register("teacher", "teacher")
        b = self.register("teacher", "other")
        self.t, self.other = a["token"], b["token"]
        self.cid = a["course_id"]
        code = self.call("/api/courses", token=self.t)[0]["invite_code"]
        u = self.register("student", "student", code)
        v = self.register("student", "reviewer", code)
        self.st, self.rv = u["token"], v["token"]
        self.uid, self.rid = u["user"]["id"], v["user"]["id"]
        self.unjoined = self.register("student", "unjoined")["token"]
        self.rubric = [{"key": "idea", "max": 60}, {"key": "analysis", "max": 40}]
        self.pid = self.call("/api/problems", {
            "title": "Sum", "type": "programming", "solution": "PRIVATE_SOLUTION",
            "test_cases": [{"input": "1 2", "expected": "3", "is_sample": True}]}, self.t)["id"]
        self.subj = self.call("/api/problems", {
            "title": "Proof", "type": "proof", "rubric": self.rubric}, self.t)["id"]
        self.aid = self.assignment([self.pid, self.subj])

    def assignment(self, pids, **kwargs):
        body = {"title": "Assignment", "problem_ids": pids, "status": "published",
                "start_at": "2000-01-01 00:00:00", "due_at": "2099-01-01 00:00:00",
                "review_due_at": "2099-01-02 00:00:00", "peer_review": True,
                "reviews_per_submission": 1, "max_load": 2, **kwargs}
        return self.call("/api/assignments", body, self.t)["id"]

    def subjective(self, token=None, aid=None):
        return self.call("/api/subjective", {"assignment_id": aid or self.aid,
                         "problem_id": self.subj, "content": {"answer": "A valid answer"}}, token or self.st)["id"]

    def task(self, score=None, reviewer=None, author=None):
        reviewer, author = reviewer or self.uid, author or self.rid
        db.ex("UPDATE assignments SET allocation_status='confirmed',status='reviewing' WHERE id=?", (self.aid,))
        al = db.ex("INSERT INTO allocations(assignment_id,problem_id,author_id,reviewer_id,status,weight,created_at) "
                   "VALUES(?,?,?,?,?,?,?)", (self.aid, self.subj, author, reviewer, "pending", 1, db.now()))
        if score is not None:
            db.ex("INSERT INTO reviews(allocation_id,assignment_id,problem_id,reviewer_id,author_id,scores,total,submitted_at) "
                  "VALUES(?,?,?,?,?,?,?,?)", (al, self.aid, self.subj, reviewer, author, "{}", score, db.now()))
        return al

    def judge_result(self, verdict="Accepted"):
        return {"verdict": verdict, "score": 100 if verdict == "Accepted" else 0, "time_ms": 1,
                "memory_kb": 1000, "passed": 1, "total_cases": 1,
                "results": [{"test_case_id": 1, "name": "sample", "verdict": "AC",
                             "time_ms": 1, "memory_kb": 1000, "actual": "3", "message": ""}]}

    def test_handled_anomalies_leave_pending_risk_and_stay_closed(self):
        from backend.api import AN
        an = db.ex("INSERT INTO anomalies(assignment_id,reviewer_id,type,level,title,detected_at) VALUES(?,?,?,?,?,?)",
                   (self.aid, self.rid, "bias", "high", "test", db.now()))
        initial = self.call("/api/anomalies", token=self.t)
        self.assertEqual(initial["counts"]["high"], 1)
        self.assertEqual(len(initial["reviewer_risk"]), 1)
        self.call(f"/api/anomalies/{an}/handle", {"status": "dismissed"}, self.t)
        after = self.call("/api/anomalies", token=self.t)
        self.assertEqual(after["counts"]["open"], 0)
        self.assertEqual(after["counts"]["high"], 0)
        self.assertEqual(after["reviewer_risk"], [])
        self.assertEqual(after["anomalies"][0]["status"], "dismissed")
        self.task(score=75, reviewer=self.rid, author=self.uid)
        detected = {"anomalies": [{"type": "bias", "level": "high", "reviewer_id": self.rid,
                    "title": "test", "detail": "test", "suggestion": "test"}]}
        with patch.object(AN, "detect", return_value=detected):
            self.call(f"/api/assignments/{self.aid}/aggregate", {}, self.t)
        self.assertEqual(self.call("/api/anomalies?status=open", token=self.t)["anomalies"], [])

    def test_seed_scores_match_rubric_and_total(self):
        import random
        from backend.seed import Seeder
        from backend.api import default_code_rubric
        maker = Seeder(verbose=False)
        rubric = default_code_rubric()
        for total in (0, 1.1, 63.04, 74.1, 99.9, 100):
            scores = maker._rubric(total, random.Random(7), rubric)
            self.assertEqual(set(scores), {r["key"] for r in rubric})
            self.assertAlmostEqual(sum(scores.values()), round(total, 1))
            self.assertTrue(all(0 <= scores[r["key"]] <= r["max"] for r in rubric))

    def test_experiment_execution_is_staff_only(self):
        with patch.object(__import__("backend.api_ext", fromlist=["EX"]).EX, "EXPERIMENTS", {"test": lambda: {"ok": True}}):
            self.call("/api/experiments/run", {"key": "test"}, self.st, want=403)
            self.call("/api/experiments/run", {"key": "test"}, self.t)
        for n in (1000000, "NaN", -1, 3.5):
            self.call("/api/experiments/run", {"key": "allocation", "params": {"n_students": n}}, self.t, want=400)

    def test_subjective_review_version_is_frozen(self):
        sid = self.subjective()
        db.ex("UPDATE subjective_submissions SET final_score=75 WHERE id=?", (sid,))
        self.task(score=75, reviewer=self.rid, author=self.uid)
        db.ex("UPDATE assignments SET status='published' WHERE id=?", (self.aid,))
        self.call("/api/subjective", {"assignment_id": self.aid, "problem_id": self.subj,
                  "content": {"answer": "A different answer"}}, self.st, want=409)
        self.assertEqual(db.q1("SELECT final_score FROM subjective_submissions WHERE id=?", (sid,))[0], 75)
        self.subjective()
        self.assertEqual(db.q1("SELECT final_score FROM subjective_submissions WHERE id=?", (sid,))[0], 75)

    def test_large_request_rejected_before_reading(self):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=5)
        conn.putrequest("POST", "/api/auth/login")
        conn.putheader("Content-Length", str(3*1024*1024))
        conn.endheaders()
        response = conn.getresponse()
        self.assertEqual(response.status, 413)
        response.read()
        conn.close()

    def test_delete_keeps_referenced_problem_and_submission(self):
        self.call(f"/api/problems/{self.pid}", {}, self.t, "DELETE", want=409)
        sid = db.ex("INSERT INTO submissions(problem_id,user_id,assignment_id,language,source_code,submitted_at) VALUES(?,?,?,?,?,?)",
                    (self.pid, self.uid, self.aid, "python", "print(3)", db.now()))
        other_aid = self.assignment([self.pid])
        db.ex("INSERT INTO allocations(assignment_id,problem_id,author_id,reviewer_id,submission_id,created_at) VALUES(?,?,?,?,?,?)",
              (other_aid, self.pid, self.uid, self.rid, sid, db.now()))
        self.call(f"/api/assignments/{self.aid}", {}, self.t, "DELETE", want=409)
        self.assertIsNotNone(db.q1("SELECT id FROM submissions WHERE id=?", (sid,)))
        self.call(f"/api/assignments/{other_aid}", {}, self.t, "DELETE")
        self.call(f"/api/assignments/{self.aid}", {}, self.t, "DELETE")
        self.assertIsNone(db.q1("SELECT id FROM submissions WHERE id=?", (sid,)))

    def test_no_course_is_empty(self):
        for path in ("/api/problems", "/api/assignments", "/api/notices", "/api/subjective"):
            self.assertEqual(self.call(path, token=self.unjoined), [])

    def test_cross_course_resources_are_denied(self):
        for path in (f"/api/problems/{self.pid}", f"/api/assignments/{self.aid}",
                     f"/api/assignments/{self.aid}/progress", f"/api/analytics/student/{self.uid}"):
            self.call(path, token=self.other, want=403)
        self.call(f"/api/problems/{self.pid}", {"title": "changed"}, self.other, "PUT", want=403)
        self.call(f"/api/assignments/{self.aid}", {}, self.other, "DELETE", want=403)
        self.assertNotIn(self.uid, [u["id"] for u in self.call("/api/users", token=self.other)])
        self.call(f"/api/problems?course_id={self.cid}", token=self.other, want=403)

    def test_draft_and_reference_answer_hidden(self):
        draft = self.assignment([self.pid], status="draft")
        self.assertNotIn(draft, [a["id"] for a in self.call("/api/assignments", token=self.st)])
        self.call(f"/api/assignments/{draft}", token=self.st, want=404)
        data = self.call(f"/api/assignments/{self.aid}", token=self.st)
        self.assertNotIn("PRIVATE_SOLUTION", json.dumps(data))
        self.assertNotIn("solution", data["problems"][0])

    def test_subjective_context_and_original_answer(self):
        sid = self.subjective()
        p = self.call(f"/api/problems/{self.subj}?assignment_id={self.aid}", token=self.st)
        self.assertEqual(p["assignment_id"], self.aid)
        self.assertEqual(p["my_subjective"]["id"], sid)
        self.assertEqual(p["my_subjective"]["content"]["answer"], "A valid answer")
        self.assertIn(self.aid, [a["id"] for a in p["assignments"]])

    def test_closed_early_and_mismatched_submissions_denied(self):
        for values in ({"status": "closed"}, {"due_at": "2001-01-01 00:00:00"},
                       {"start_at": "2098-01-01 00:00:00"}):
            aid = self.assignment([self.subj], **values)
            self.call("/api/subjective", {"assignment_id": aid, "problem_id": self.subj,
                      "content": {"answer": "x"}}, self.st, want=403)
        wrong = self.assignment([self.pid])
        self.call("/api/subjective", {"assignment_id": wrong, "problem_id": self.subj,
                  "content": {"answer": "x"}}, self.st, want=400)
        with patch.object(api.J, "judge_submission") as judge:
            self.call("/api/submissions", {"assignment_id": wrong, "problem_id": self.subj,
                      "source_code": "print(3)", "language": "python"}, self.st, want=400)
            judge.assert_not_called()

    def test_review_score_state_and_deadline_checks(self):
        al = self.task()
        self.call(f"/api/reviews/task/{al}", token=self.st)
        for scores in ({"wrong": 1000}, {"idea": 61, "analysis": 40},
                       {"idea": -1, "analysis": 0}, {"idea": "NaN", "analysis": 0},
                       {"idea": 10}, {"idea": True, "analysis": 0}):
            self.call(f"/api/reviews/{al}", {"scores": scores, "comment": "客观具体的建议，包含足够的文字。"},
                      self.st, want=400)
        body = {"scores": {"idea": 0, "analysis": 0}, "comment": "客观具体的建议，包含足够的文字。"}
        self.call(f"/api/reviews/{al}", dict(body, duration_sec=-1), self.st, want=400)
        self.assertEqual(self.call(f"/api/reviews/{al}", body, self.st)["total"], 0)
        db.ex("UPDATE assignments SET allocation_status='draft' WHERE id=?", (self.aid,))
        self.call(f"/api/reviews/{al}", body, self.st, want=403)
        db.ex("UPDATE assignments SET allocation_status='confirmed',review_due_at='2001-01-01 00:00:00' WHERE id=?", (self.aid,))
        self.call(f"/api/reviews/{al}", body, self.st, want=403)

    def test_server_records_actual_review_duration(self):
        al = self.task()
        self.call(f"/api/reviews/task/{al}", token=self.st)
        body = {"scores": {"idea": 30, "analysis": 30}, "duration_sec": 99999,
                "comment": "客观具体的建议，包含足够的文字。"}
        result = self.call(f"/api/reviews/{al}", body, self.st)
        self.assertLess(result["duration_sec"], 10)

    def test_scores_hidden_before_publication(self):
        sid = self.subjective()
        db.ex("UPDATE subjective_submissions SET final_score=88,methods=? WHERE id=?",
              (db.jdumps({"mean": {str(self.uid): 88, str(self.rid): 99}}), sid))
        for data in (self.call(f"/api/subjective/{sid}", token=self.st),
                     self.call("/api/subjective", token=self.st)[0]):
            self.assertIsNone(data["final_score"])
            self.assertEqual(data["methods"], {})
        db.ex("UPDATE assignments SET review_due_at='2001-01-01 00:00:00',allocation_status='confirmed' WHERE id=?", (self.aid,))
        data = self.call(f"/api/subjective/{sid}", token=self.st)
        self.assertEqual(data["methods"], {"mean": 88})
        self.assertEqual(data["final_score"], 88)

    def test_author_identity_is_opaque(self):
        self.task()
        rows = self.call("/api/reviews/mine", token=self.st)
        self.assertNotIn("author_id", rows[0])
        self.assertTrue(rows[0]["author"].startswith("匿名#"))
        self.assertNotEqual(api.anon_label(self.rid, self.aid, 1), api.anon_label(self.rid, self.aid, 2))

    def test_manual_weight_changes_saved_and_displayed_score(self):
        sid = self.subjective()
        # 两个评审者对同一作者评分，隔离算法权重的影响。
        self.task(10, reviewer=self.uid, author=self.uid)
        self.task(90, reviewer=self.rid, author=self.uid)
        self.call(f"/api/assignments/{self.aid}/aggregate", {}, self.t)
        before = db.q1("SELECT final_score FROM subjective_submissions WHERE id=?", (sid,))["final_score"]
        an = db.ex("INSERT INTO anomalies(assignment_id,reviewer_id,type,level,title,detected_at) VALUES(?,?,?,?,?,?)",
                   (self.aid, self.rid, "bias", "high", "bias", db.now()))
        self.call(f"/api/anomalies/{an}/handle", {"status": "adjusted", "adjust_weight": 0.01}, self.t)
        after = db.q1("SELECT final_score FROM subjective_submissions WHERE id=?", (sid,))["final_score"]
        self.assertLess(after, before - 10)
        shown = self.call(f"/api/assignments/{self.aid}/review-results", token=self.t)[0]["rows"][0]["score"]
        self.assertEqual(after, shown)
        self.call(f"/api/anomalies/{an}/handle", {"status": "adjusted", "adjust_weight": "NaN"}, self.t, want=400)

    def test_reallocation_archives_old_scores(self):
        self.subjective()
        self.subjective(self.rv)
        self.task(90)
        self.call(f"/api/assignments/{self.aid}/allocate", {"method": "random", "reviews_per_submission": 1}, self.t)
        self.assertEqual(db.q1("SELECT COUNT(*) n FROM reviews WHERE assignment_id=?", (self.aid,))["n"], 0)
        history = db.q1("SELECT snapshot FROM review_round_history WHERE assignment_id=?", (self.aid,))
        self.assertEqual(len(json.loads(history["snapshot"])["reviews"]), 1)
        self.assertEqual(self.call(f"/api/assignments/{self.aid}/review-results", token=self.t), [])

    def test_submission_and_rejudge_save_same_details(self):
        body = {"problem_id": self.pid, "assignment_id": self.aid, "language": "python", "source_code": "print(3)"}
        with patch.object(api.J, "judge_submission", return_value=self.judge_result()):
            sid = self.call("/api/submissions", body, self.st)["submission_id"]
            self.assertEqual(len(self.call(f"/api/submissions/{sid}", token=self.st)["test_results"]), 1)
            self.call(f"/api/assignments/{self.aid}/rejudge", {}, self.t)
            data = self.call(f"/api/submissions/{sid}", token=self.st)
            self.assertEqual(data["verdict"], data["detail"]["results"][0]["verdict"].replace("AC", "Accepted"))
            self.assertEqual(len(data["test_results"]), 1)

    def test_practice_does_not_complete_assignment_and_rate_is_bounded(self):
        for _ in range(3):
            db.ex("INSERT INTO submissions(problem_id,user_id,language,source_code,submitted_at,verdict,score) "
                  "VALUES(?,?,?,?,?,?,?)", (self.pid, self.uid, "python", "print(3)", db.now(), "Accepted", 100))
        data = self.call("/api/problems", token=self.st)
        p = next(x for x in data if x["id"] == self.pid)
        self.assertEqual(p["pass_rate"], 1)
        progress = self.call(f"/api/assignments/{self.aid}/progress", token=self.t)
        mine = next(s for s in progress["students"] if s["user_id"] == self.uid)
        self.assertEqual(mine["submitted_problems"], 0)
        dash = self.call("/api/dashboard/student", token=self.st)
        a = next(a for a in dash["assignments"] if a["id"] == self.aid)
        self.assertEqual(a["progress"]["done"], 0)

    def test_password_change_invalidates_sessions(self):
        self.call("/api/auth/password", {"current_password": "wrong", "new_password": "newpassword"}, self.st, "PUT", want=400)
        self.call("/api/auth/password", {"current_password": "test123456", "new_password": "newpassword"}, self.st, "PUT")
        self.call("/api/auth/me", token=self.st, want=401)
        self.call(f"/api/users/{self.rid}/reset-password", {"new_password": "newpassword"}, self.other, want=403)
        self.call(f"/api/users/{self.rid}/reset-password", {"new_password": "newpassword"}, self.t)
        self.call("/api/auth/me", token=self.rv, want=401)

    def test_failed_reviewer_swap_keeps_original_allocation(self):
        al = self.task()
        self.call(f"/api/assignments/{self.aid}/allocation/adjust", {
            "problem_id": self.subj, "author_id": self.rid,
            "remove_reviewer_id": self.uid, "add_reviewer_id": self.rid}, self.t, want=400)
        self.assertIsNotNone(db.q1("SELECT id FROM allocations WHERE id=?", (al,)))

    def test_unconfirmed_round_stays_private_after_deadline(self):
        sid = self.subjective(self.rv)
        self.task(80)
        db.ex("UPDATE assignments SET review_due_at='2000-01-01',allocation_status='draft' WHERE id=?", (self.aid,))
        data = self.call(f"/api/subjective/{sid}", token=self.rv)
        self.assertFalse(data["review_published"])
        self.assertEqual(data["reviews"], [])

    def test_batch_weight_changes_reaggregate_after_all_records_updated(self):
        self.subjective(self.rv)
        self.task(80)
        ids = [db.ex("INSERT INTO anomalies(assignment_id,reviewer_id,type,level,title,detected_at) VALUES(?,?,?,?,?,?)",
                     (self.aid, self.uid, "bias", "high", "review", db.now())) for _ in range(2)]
        self.call("/api/anomalies/handle-batch", {"ids": ids, "status": "adjusted", "adjust_weight": 0}, self.t)
        self.assertTrue(all(db.q1("SELECT status FROM anomalies WHERE id=?", (i,))[0] == "adjusted" for i in ids))
        self.assertIsNone(db.q1("SELECT final_score FROM subjective_submissions WHERE assignment_id=?", (self.aid,))[0])

    def test_aggregation_method_persists_and_invalid_request_does_not_mutate(self):
        self.subjective(self.rv)
        self.task(80)
        self.call(f"/api/assignments/{self.aid}/aggregate", {"method": "median"}, self.t)
        self.assertEqual(db.q1("SELECT aggregation_method FROM assignments WHERE id=?", (self.aid,))[0], "median")
        self.call(f"/api/assignments/{self.aid}/aggregate", {"methods": ["invalid"]}, self.t, want=400)
        self.assertEqual(db.q1("SELECT aggregation_method FROM assignments WHERE id=?", (self.aid,))[0], "median")

    def test_batch_rejudge_processes_more_than_eighty(self):
        for _ in range(81):
            db.ex("INSERT INTO submissions(assignment_id,problem_id,user_id,language,source_code,submitted_at) "
                  "VALUES(?,?,?,?,?,?)", (self.aid, self.pid, self.uid, "python", "print(3)", db.now()))
        with patch.object(api.J, "judge_submission", return_value=self.judge_result()) as judge:
            first = self.call(f"/api/assignments/{self.aid}/rejudge", {}, self.t)
            self.assertEqual(first["remaining"], 1)
            self.call(f"/api/assignments/{self.aid}/rejudge", {"offset": first["next_offset"]}, self.t)
            self.assertEqual(judge.call_count, 81)
        self.assertEqual(db.q1("SELECT COUNT(*) FROM test_results tr JOIN submissions s ON s.id=tr.submission_id WHERE s.assignment_id=?", (self.aid,))[0], 81)

    def test_code_review_uses_pinned_submission(self):
        sid = db.ex("INSERT INTO submissions(problem_id,user_id,language,source_code,submitted_at) "
                    "VALUES(?,?,?,?,?)", (self.pid, self.rid, "python", "print('original')", db.now()))
        al = self.task()
        db.ex("UPDATE allocations SET problem_id=?,submission_id=? WHERE id=?", (self.pid, sid, al))
        db.ex("INSERT INTO submissions(assignment_id,problem_id,user_id,language,source_code,submitted_at) "
              "VALUES(?,?,?,?,?,?)", (self.aid, self.pid, self.rid, "python", "print('new')", db.now()))
        task = self.call(f"/api/reviews/task/{al}", token=self.st)
        self.assertEqual(task["code"], "print('original')")
        self.assertTrue(task["uses_historical_submission"])

    def test_course_selection_changes_resource_scope(self):
        cid = self.call("/api/courses", {"name": "Second course"}, self.t)["id"]
        self.assertEqual(self.call(f"/api/problems?course_id={cid}", token=self.t), [])
        self.assertTrue(self.call(f"/api/problems?course_id={self.cid}", token=self.t))


if __name__ == "__main__":
    unittest.main(verbosity=2)
