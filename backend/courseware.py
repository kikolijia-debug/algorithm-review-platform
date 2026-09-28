"""课程课件与章节知识结构。

本文件是「课件库」的唯一数据源：章节划分、每章的知识点名称、以及该章对应的
课件 PDF 文件，全部按实际授课课件（《算法》文件夹）整理。题库里的每道题都会
挂到一个章节上（``problems.chapter``），教师选题、学情分析、课件浏览都据此对齐。

课件 PDF 通过 ``tools/import_courseware.py`` 复制到 ``frontend/courseware/``，
并把实际的文件大小、页数写进 ``backend/data/courseware_manifest.json``。
"""

from __future__ import annotations

import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MANIFEST_PATH = os.path.join(DATA_DIR, "courseware_manifest.json")
COURSEWARE_DIR = os.path.join("frontend", "courseware")

#: 课程主页（校内站点，仅作跳转链接）
COURSE_HOMEPAGE = "https://222.20.126.111/student/course/1803"

#: 章节 → 知识点名称（题库 topics 与知识点统计都用这个名字，保证能对得上）
CHAPTERS: list[dict] = [
    {
        "key": "ch0",
        "no": "Chapter 0",
        "title": "课程概述",
        "topic": "算法基础与课程导论",
        "summary": "课程安排、考核方式、CSP 认证简介，以及算法设计与分析在整门课中的位置。",
        "topics": ["课程安排", "算法设计范式", "CSP 认证"],
        "files": [
            {"slug": "ch00-overview", "src": "chapter0 (1).pdf", "title": "Chapter 0：课程概述"},
            {"slug": "ch00-course-guide", "src": "算法设计与分析课程作业指南2026.pdf",
             "title": "课程作业指南（2026）",
             "topics": ["课程安排", "考核方式", "大作业要求"]},
        ],
    },
    {
        "key": "ch1",
        "no": "Chapter 1",
        "title": "渐近分析",
        "topic": "渐近分析与复杂度",
        "summary": "算法分析基础、函数的增长、渐近记号，以及最好 / 最坏 / 平均情形复杂度。",
        "topics": ["渐近记号", "增长率比较", "最坏情形", "平均情形", "均摊分析"],
        "files": [
            {"slug": "ch01-asymptotic", "src": "chapter1.pdf", "title": "Chapter 1：Asymptotic Analysis"},
        ],
    },
    {
        "key": "ch2",
        "no": "Chapter 2",
        "title": "图的搜索",
        "topic": "图的搜索与拓扑排序",
        "summary": "图的基本定义、连通性、广度优先 / 深度优先遍历，以及有向无环图与拓扑排序。",
        "topics": ["图的表示", "BFS", "DFS", "连通分量", "有向无环图", "拓扑排序"],
        "files": [
            {"slug": "ch02-graph-search", "src": "chapter2.pdf", "title": "Chapter 2：Graph Search"},
        ],
    },
    {
        "key": "ch3",
        "no": "Chapter 3",
        "title": "贪心算法",
        "topic": "贪心算法",
        "summary": "区间调度（选最多不冲突任务）、区间划分（最少机器数）与最小化延迟调度。",
        "topics": ["区间调度", "区间划分", "最小延迟调度", "交换论证", "贪心选择性质"],
        "files": [
            {"slug": "ch03-greedy", "src": "chapter3.pdf", "title": "Chapter 3-1：Greedy"},
        ],
    },
    {
        "key": "ch4",
        "no": "Chapter 4",
        "title": "分治算法",
        "topic": "分治与递归式",
        "summary": "归并排序、逆序对计数、最近点对；主定理求解递归式、Karatsuba 整数乘法与 Strassen 矩阵乘法。",
        "topics": ["归并排序", "逆序对", "最近点对", "主定理", "Karatsuba", "Strassen"],
        "files": [
            {"slug": "ch04-divide-conquer-i", "src": "chapter4-1.pdf", "title": "Chapter 4-1：Divide And Conquer"},
            {"slug": "ch04-divide-conquer-ii", "src": "chapter4-2.pdf",
             "title": "Chapter 4-2：Divide And Conquer II（主定理）",
             "topics": ["主定理", "Karatsuba", "Strassen", "递归式求解"]},
        ],
    },
    {
        "key": "ch5",
        "no": "Chapter 5",
        "title": "动态规划",
        "topic": "动态规划",
        "summary": "加权区间调度、分段最小二乘、背包问题、序列对齐与 RNA 二级结构，重点在状态设计与无后效性。",
        "topics": ["加权区间调度", "分段最小二乘", "背包问题", "序列对齐", "状态设计", "无后效性"],
        "files": [
            {"slug": "ch05-dynamic-programming", "src": "chapter5.pdf", "title": "Chapter 5：Dynamic Programming"},
        ],
    },
    {
        "key": "ch6",
        "no": "Chapter 6",
        "title": "网络流",
        "topic": "网络流",
        "summary": "最大流与最小割、Ford-Fulkerson 增广路算法、最大流最小割定理、容量缩放与最短增广路。",
        "topics": ["最大流", "最小割", "Ford-Fulkerson", "增广路", "最大流最小割定理", "容量缩放"],
        "files": [
            {"slug": "ch06-network-flow", "src": "chapter6.pdf", "title": "Chapter 6：Network Flow"},
        ],
    },
    {
        "key": "ch7",
        "no": "Chapter 7",
        "title": "并查集",
        "topic": "并查集",
        "summary": "不相交集合数据结构、link-by-size / link-by-rank、路径压缩，以及 Kruskal 最小生成树。",
        "topics": ["不相交集合", "并查集", "按秩合并", "路径压缩", "Kruskal"],
        "files": [
            {"slug": "ch07-union-find", "src": "chapter7-union-find.pdf", "title": "Chapter 7：Union-find"},
        ],
    },
    {
        "key": "ch8",
        "no": "Chapter 8",
        "title": "线段树",
        "topic": "线段树",
        "summary": "区间树的构造、单点修改与区间查询、区间修改与懒标记（延迟更新），以及 4 倍数组的存储技巧。",
        "topics": ["线段树", "区间查询", "懒标记", "延迟更新", "区间加法"],
        "files": [
            {"slug": "ch08-segment-tree", "src": "08.线段树.pdf", "title": "Chapter 8：线段树与树状数组"},
        ],
    },
    {
        "key": "ch9",
        "no": "Chapter 9",
        "title": "树状数组",
        "topic": "树状数组",
        "summary": "树状数组（Fenwick Tree）的 lowbit 结构与单点修改、前缀和查询。",
        "topics": ["树状数组", "lowbit", "前缀和", "单点修改"],
        "files": [
            {"slug": "ch09-fenwick-tree", "src": "树状数组.pdf", "title": "Chapter 9：树状数组"},
        ],
    },
    {
        "key": "ch10",
        "no": "Chapter 10",
        "title": "字符串匹配（KMP）",
        "topic": "字符串匹配 KMP",
        "summary": "字符串模式匹配、前缀函数（失配数组）的构造、匹配过程的均摊分析，以及最小循环节等应用。",
        "topics": ["字符串匹配", "KMP", "前缀函数", "失配跳转", "均摊分析", "最小循环节"],
        "files": [
            {"slug": "ch10-kmp", "src": "kmp帮助理解版.pdf", "title": "Chapter 10：KMP（理解版）"},
            {"slug": "ch10-kmp-exam", "src": "KMP-考试版.pdf",
             "title": "Chapter 10：KMP（考试版）",
             "topics": ["前缀函数", "失配跳转", "最小循环节", "考试要点"]},
        ],
    },
    {
        "key": "ch11",
        "no": "Chapter 11",
        "title": "NP 完全性",
        "topic": "NP 完全性",
        "summary": "多项式时间规约、P / NP / NP 完全 / NP 难、约束可满足性、packing 与 covering 问题及不可计算性。",
        "topics": ["多项式时间规约", "P 与 NP", "NP 完全", "NP 难", "SAT", "独立集", "顶点覆盖"],
        "files": [
            {"slug": "ch11-np-completeness", "src": "chapter11.pdf", "title": "Chapter 11：NP 完全性"},
            {"slug": "ch11-np-completeness-ii", "src": "chapter11-2.pdf",
             "title": "Chapter 11-2：NP 完全性（续）",
             "topics": ["P 与 NP", "NP 完全", "NP 难", "不可计算性"]},
        ],
    },
]

CHAPTER_BY_KEY = {c["key"]: c for c in CHAPTERS}
TOPIC_TO_CHAPTER = {c["topic"]: c["key"] for c in CHAPTERS}


def chapter_of(topic: str) -> str | None:
    """把知识点名称映射回章节 key（题库 topics 用得到）。"""
    return TOPIC_TO_CHAPTER.get((topic or "").strip())


def chapter_label(key: str) -> str:
    c = CHAPTER_BY_KEY.get(key)
    return f"{c['no']} {c['title']}" if c else (key or "未分章")


def load_manifest() -> dict:
    """读取导入工具生成的清单；没有导入过课件时返回空结构。"""
    if not os.path.exists(MANIFEST_PATH):
        return {"imported_at": None, "files": [], "total_bytes": 0}
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {"imported_at": None, "files": [], "total_bytes": 0}
    return data


def material_rows() -> list[dict]:
    """把清单展开成可直接入库的课件记录（按章节、按章节内顺序）。"""
    manifest = load_manifest()
    by_slug = {f["slug"]: f for f in manifest.get("files", [])}
    rows: list[dict] = []
    for chapter in CHAPTERS:
        for order, item in enumerate(chapter["files"]):
            info = by_slug.get(item["slug"], {})
            rows.append(
                {
                    "chapter": chapter["key"],
                    "chapter_title": f"{chapter['no']} {chapter['title']}",
                    "title": item["title"],
                    "filename": info.get("filename") or (item["slug"] + ".pdf"),
                    "url": "/courseware/" + (info.get("filename") or (item["slug"] + ".pdf")),
                    "size_bytes": info.get("size_bytes") or 0,
                    "pages": info.get("pages") or 0,
                    "sha256": info.get("sha256") or "",
                    "topics": item.get("topics") or chapter["topics"],
                    "summary": chapter["summary"],
                    "order_index": order,
                    "source": item["src"],
                }
            )
    return rows
