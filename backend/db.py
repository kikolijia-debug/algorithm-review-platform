"""SQLite 存储层：连接管理、建表、通用查询辅助。

设计取舍
--------
* 只用 Python 标准库 ``sqlite3``，不需要任何第三方依赖，方便助教/老师一条命令跑起来；
* 复杂结构（评分细则、测试点列表、参数配置、算法中间量）直接以 **JSON 文本**
  存入 TEXT 字段：既保留了关系表的强一致查询能力，又免去为每个小结构建表的开销；
* 所有查询走参数绑定，避免 SQL 注入。
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

DB_PATH = os.environ.get("AJP_DB") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "platform.db"
)

_local = threading.local()

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT UNIQUE NOT NULL,
    email       TEXT,
    password    TEXT NOT NULL,
    salt        TEXT NOT NULL,
    role        TEXT NOT NULL,              -- teacher | student | ta
    name        TEXT NOT NULL,
    student_no  TEXT,
    class_name  TEXT,
    avatar      TEXT,
    created_at  TEXT NOT NULL,
    last_login  TEXT
);

CREATE TABLE IF NOT EXISTS courses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    code        TEXT,
    term        TEXT,
    teacher_id  INTEGER,
    description TEXT,
    invite_code TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS course_members (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    user_id   INTEGER NOT NULL,
    role      TEXT NOT NULL,
    joined_at TEXT NOT NULL,
    UNIQUE(course_id, user_id)
);

CREATE TABLE IF NOT EXISTS knowledge_points (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id   INTEGER NOT NULL,
    name        TEXT NOT NULL,
    chapter     TEXT,
    description TEXT,
    parent_id   INTEGER
);

CREATE TABLE IF NOT EXISTS problems (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id       INTEGER NOT NULL,
    title           TEXT NOT NULL,
    type            TEXT NOT NULL,          -- programming | analysis | proof | open
    difficulty      INTEGER DEFAULT 3,
    topics          TEXT DEFAULT '[]',
    statement       TEXT,
    input_format    TEXT,
    output_format   TEXT,
    constraints     TEXT,
    samples         TEXT DEFAULT '[]',
    time_limit_ms   INTEGER DEFAULT 1000,
    memory_limit_mb INTEGER DEFAULT 256,
    score           INTEGER DEFAULT 100,
    rubric          TEXT DEFAULT '[]',
    created_by      INTEGER,
    created_at      TEXT NOT NULL,
    tags            TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS test_cases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id  INTEGER NOT NULL,
    name        TEXT,
    input       TEXT,
    expected    TEXT,
    is_sample   INTEGER DEFAULT 0,
    score       INTEGER DEFAULT 10,
    order_index INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS assignments (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id             INTEGER NOT NULL,
    title                 TEXT NOT NULL,
    description           TEXT,
    type                  TEXT DEFAULT 'mixed',   -- programming | subjective | mixed
    start_at              TEXT,
    due_at                TEXT,
    review_due_at         TEXT,
    reviews_per_submission INTEGER DEFAULT 3,
    max_load              INTEGER DEFAULT 4,
    aggregation_method    TEXT DEFAULT 'reliability_em',
    allocate_method       TEXT DEFAULT 'mcmf',
    params                TEXT DEFAULT '{}',
    status                TEXT DEFAULT 'draft',   -- draft | published | reviewing | closed
    peer_review           INTEGER DEFAULT 0,
    created_by            INTEGER,
    created_at            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assignment_problems (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER NOT NULL,
    problem_id    INTEGER NOT NULL,
    score         INTEGER DEFAULT 100,
    order_index   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS submissions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER,
    problem_id    INTEGER NOT NULL,
    user_id       INTEGER NOT NULL,
    language      TEXT NOT NULL,
    source_code   TEXT NOT NULL,
    submitted_at  TEXT NOT NULL,
    status        TEXT DEFAULT 'done',       -- queued | judging | done | failed
    verdict       TEXT,
    score         REAL DEFAULT 0,
    time_ms       REAL DEFAULT 0,
    memory_kb     REAL DEFAULT 0,
    compile_message TEXT,
    attempt_no    INTEGER DEFAULT 1,
    detail        TEXT DEFAULT '{}',
    complexity    TEXT
);

CREATE TABLE IF NOT EXISTS test_results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL,
    test_case_id  INTEGER,
    name          TEXT,
    verdict       TEXT,
    time_ms       REAL,
    memory_kb     REAL,
    message       TEXT,
    output        TEXT
);

CREATE TABLE IF NOT EXISTS subjective_submissions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER NOT NULL,
    problem_id    INTEGER NOT NULL,
    user_id       INTEGER NOT NULL,
    content       TEXT DEFAULT '{}',
    submitted_at  TEXT NOT NULL,
    status        TEXT DEFAULT 'submitted',  -- submitted | reviewing | done
    final_score   REAL,
    methods       TEXT DEFAULT '{}',
    updated_at    TEXT
);

CREATE TABLE IF NOT EXISTS allocations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER NOT NULL,
    problem_id    INTEGER,
    author_id     INTEGER NOT NULL,
    reviewer_id   INTEGER NOT NULL,
    status        TEXT DEFAULT 'pending',    -- pending | done
    round         INTEGER DEFAULT 1,
    weight        REAL DEFAULT 1.0,
    is_anomaly    INTEGER DEFAULT 0,
    created_at    TEXT NOT NULL,
    UNIQUE(assignment_id, problem_id, author_id, reviewer_id)
);

CREATE TABLE IF NOT EXISTS reviews (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    allocation_id INTEGER,
    assignment_id INTEGER NOT NULL,
    problem_id    INTEGER,
    submission_id INTEGER,
    reviewer_id   INTEGER NOT NULL,
    author_id     INTEGER NOT NULL,
    scores        TEXT DEFAULT '{}',
    total         REAL NOT NULL,
    comment       TEXT,
    duration_sec  REAL,
    started_at    TEXT,
    submitted_at  TEXT NOT NULL,
    flagged       INTEGER DEFAULT 0,
    flag_reason   TEXT
);

CREATE TABLE IF NOT EXISTS anomalies (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER,
    type          TEXT,
    level         TEXT,
    reviewer_id   INTEGER,
    submission_id INTEGER,
    title         TEXT,
    detail        TEXT,
    evidence      TEXT,
    suggestion    TEXT,
    status        TEXT DEFAULT 'open',       -- open | confirmed | dismissed | adjusted
    handled_by    INTEGER,
    note          TEXT,
    detected_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER,
    course_id  INTEGER,
    type       TEXT,
    payload    TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT,
    params     TEXT,
    result     TEXT,
    elapsed_ms REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notices (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id  INTEGER,
    title      TEXT,
    content    TEXT,
    author_id  INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_sub_problem ON submissions(problem_id);
CREATE INDEX IF NOT EXISTS idx_sub_user ON submissions(user_id);
CREATE INDEX IF NOT EXISTS idx_alloc_a ON allocations(assignment_id);
CREATE INDEX IF NOT EXISTS idx_review_a ON reviews(assignment_id);
CREATE INDEX IF NOT EXISTS idx_eval_user ON events(user_id);
"""


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def days_ago(n: int, hour: int = 20, minute: int = 30) -> str:
    d = datetime.now() - timedelta(days=n)
    return d.replace(hour=hour, minute=minute, second=0, microsecond=0).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def days_ahead(n: int, hour: int = 23, minute: int = 59) -> str:
    d = datetime.now() + timedelta(days=n)
    return d.replace(hour=hour, minute=minute, second=0, microsecond=0).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def get_conn() -> sqlite3.Connection:
    """线程安全的连接获取（每个线程一个连接）。"""
    conn = getattr(_local, "conn", None)
    if conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()


def q(sql: str, args: Iterable = ()) -> list[sqlite3.Row]:
    return get_conn().execute(sql, tuple(args)).fetchall()


def q1(sql: str, args: Iterable = ()):
    rows = q(sql, args)
    return rows[0] if rows else None


def ex(sql: str, args: Iterable = ()) -> int:
    conn = get_conn()
    cur = conn.execute(sql, tuple(args))
    conn.commit()
    return cur.lastrowid


def exmany(sql: str, seq: list[tuple]) -> None:
    conn = get_conn()
    conn.executemany(sql, seq)
    conn.commit()


def row2dict(row) -> dict:
    return dict(row) if row is not None else None


def rows2dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


def jloads(text: str | None, default: Any = None):
    if not text:
        return default if default is not None else {}
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else {}


def jdumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def is_empty() -> bool:
    try:
        row = q1("SELECT COUNT(*) AS c FROM users")
        return not row or row["c"] == 0
    except sqlite3.OperationalError:
        return True
