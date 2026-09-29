"""智能出题：把课程知识点展开成「可以直接评测」的编程题。

设计思路
--------
题库里的题是**固定**的一道道题；这里换一种做法：每个知识点写成一族
*参数化题目*（模板）。教师选定「章节 + 难度」后，系统会

1. 按难度挑一个规模参数（同一个模板，难度越高数据规模越大）；
2. 现场生成输入数据，并用模板自带的 **Python 参考解法** 算出期望输出——
   所以测试数据一定自洽，学生提交后是真评测，不是假结果；
3. 把题面、输入输出格式、约束按实际参数写清楚；
4. 算一个 ``gen_key``（模板 + 难度 + 参数指纹）并与题库已有题目比对，
   用「相同 gen_key」+「题面字符 n-gram 的 Jaccard 相似度」两道关卡避免重复出题。

``solve(text)`` 必须是**自包含**的纯函数（用到 heapq / collections 之类就在函数体里
import），因为 ``solution_source`` 会把它的源码原样导出成一份可独立运行的参考答案。
"""

from __future__ import annotations

import hashlib
import inspect
import random
import re
import textwrap
import time

# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------


def _fmt(a) -> str:
    return " ".join(str(x) for x in a)


def _size(d: int, table: list[int]) -> int:
    """把 1~5 的难度映射到一组规模参数上。"""
    return table[max(0, min(len(table) - 1, int(d) - 1))]


def _mk(samples: list, hidden: list) -> list[dict]:
    cases: list[dict] = []
    for i, (inp, exp) in enumerate(samples):
        cases.append({"name": "样例 %d" % (i + 1), "input": inp,
                      "expected": exp, "is_sample": 1, "score": 0})
    for i, (inp, exp) in enumerate(hidden):
        cases.append({"name": "测试点 %d" % (i + 1), "input": inp,
                      "expected": exp, "is_sample": 0, "score": 10})
    return cases


def solution_source(fn) -> str:
    """把参考解法导出成能独立运行的 Python 程序（生成 <-> 校验共用一份代码）。"""
    body = textwrap.dedent(inspect.getsource(fn)).rstrip()
    return (
        body
        + "\n\n\nif __name__ == '__main__':\n"
        + "    import sys\n"
        + "    sys.stdout.write(str(solve(sys.stdin.read())))\n"
    )


_PUNCT = re.compile(r"[\s，。；：、（）【】“”‘’！？·,.;:()\[\]!?/\\|<>\"'`~^*+=_—-]+")


def _shingles(text: str, k: int = 6) -> set[str]:
    s = _PUNCT.sub("", text or "")
    if len(s) < k:
        return {s} if s else set()
    return {s[i:i + k] for i in range(len(s) - k + 1)}


def text_similarity(a: str, b: str, k: int = 6) -> float:
    """题面相似度：去掉标点后取 k 元字符组合，算 Jaccard 系数（0~1）。

    只用来做「是不是同一道题」的粗筛，比编辑距离稳定，也不受题目里
    数字规模变化的影响。
    """
    sa, sb = _shingles(a, k), _shingles(b, k)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


# ---------------------------------------------------------------------------
# 1. Chapter 1 · 增长率排序（渐近分析）
# ---------------------------------------------------------------------------


def b_growth(rng: random.Random, d: int) -> dict:
    def solve(text):
        import math

        def log2_of(name, n):
            # 统一取 log2，避免 2^n 这类函数直接算出天文数字
            lg = math.log2(n)
            if name == '1':
                return 0.0
            if name == 'logn':
                return math.log2(lg)
            if name == 'n':
                return lg
            if name == 'nlogn':
                return lg + math.log2(lg)
            if name == 'nlogsq':
                return lg + 2.0 * math.log2(lg)
            if name == 'sqrtn':
                return 0.5 * lg
            if name == 'n15':
                return 1.5 * lg
            if name == 'n2':
                return 2.0 * lg
            if name == 'n3':
                return 3.0 * lg
            if name == '2n':
                return float(n)
            raise ValueError(name)

        toks = text.split()[1:]        # 第一个数是函数个数 m，后面才是记号
        n = 10 ** 9
        vals = [log2_of(t, n) for t in toks]
        order = sorted(range(len(toks)), key=lambda i: (vals[i], i))
        return " ".join(str(i + 1) for i in order) + "\n"

    base = ['1', 'logn', 'n', 'nlogn', 'n2', '2n']
    extra = ['sqrtn', 'n15', 'n3', 'nlogsq']
    samples, hidden = [], []
    for _ in range(2):
        m = rng.randint(3, 4)
        toks = rng.sample(base, m)
        samples.append(("%d\n%s\n" % (m, _fmt(toks)), solve("%d\n%s\n" % (m, _fmt(toks)))))
    rounds = _size(d, [4, 5, 6, 8, 10])
    for _ in range(rounds):
        m = rng.randint(3, 6 if d <= 3 else 8)
        pool = base + (extra if d >= 3 else [])
        toks = rng.sample(pool, m)
        samples_text = "%d\n%s\n" % (m, _fmt(toks))
        hidden.append((samples_text, solve(samples_text)))
    return {
        "title": "函数增长率排序",
        "statement": (
            "在算法分析里，比较两个函数的增长速度是最基本的操作。本题给出若干函数，"
            "请你按它们在 n = 10⁹ 时的取值从小到大排序。\n\n"
            "函数用固定记号表示：1、logn、sqrtn、n、nlogn、nlogsq(=n·log²n)、"
            "n15(=n^1.5)、n2、n3、2n(=2^n)。\n"
            "若两个函数在同一 n 下取值相同，则下标小的排在前面。\n"
            "提示：直接算数值容易溢出，可以先取对数再比较（对数函数单调，不改变大小关系）。"
        ),
        "input_format": "第一行一个整数 m，表示函数个数；第二行 m 个记号（用空格分隔，记号含义见题目描述）。",
        "output_format": "一行，按增长速度从小到大输出这些函数的下标（从 1 开始），用空格分隔。",
        "constraints": "3 ≤ m ≤ 8；记号取值范围见题目描述。\n提示：时间复杂度 O(m log m)，m 很小，难点在比较方式而不是代码量。",
        "time_limit_ms": 1000,
        "memory_limit_mb": 64,
        "tags": ["渐近分析", "对数比较", "第1章"],
        "samples": samples,
        "hidden": hidden,
        "solve": solve,
        "param": {"m_max": 6 if d <= 3 else 8, "extra": d >= 3},
    }


# ---------------------------------------------------------------------------
# 2. Chapter 2 · 连通块计数（BFS / DFS）
# ---------------------------------------------------------------------------


def b_connected(rng: random.Random, d: int) -> dict:
    def solve(text):
        from collections import deque

        lines = text.split("\n")
        r, c = map(int, lines[0].split())
        grid = lines[1:1 + r]
        seen = [[False] * c for _ in range(r)]
        cnt = 0
        for i in range(r):
            for j in range(c):
                if grid[i][j] != '1' or seen[i][j]:
                    continue
                cnt += 1
                seen[i][j] = True
                dq = deque([(i, j)])
                while dq:
                    x, y = dq.popleft()
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < r and 0 <= ny < c and not seen[nx][ny] and grid[nx][ny] == '1':
                            seen[nx][ny] = True
                            dq.append((nx, ny))
        return "%d\n" % cnt

    def make(r, c, density):
        grid = ["".join("1" if rng.random() < density else "0" for _ in range(c)) for _ in range(r)]
        return "%d %d\n%s\n" % (r, c, "\n".join(grid))

    samples, hidden = [], []
    samples.append(("3 4\n1100\n0110\n0001\n", solve("3 4\n1100\n0110\n0001\n")))
    samples.append(("2 2\n00\n00\n", solve("2 2\n00\n00\n")))
    for _ in range(2):
        sx = rng.randint(2, 5)
        t = make(sx, sx, 0.5)
        hidden.append((t, solve(t)))
    big = _size(d, [12, 40, 90, 160, 220])
    for _ in range(3):
        t = make(big, big, rng.choice([0.18, 0.35, 0.6, 0.82]))
        hidden.append((t, solve(t)))
    edge = "1 6\n101101\n"
    hidden.append((edge, solve(edge)))
    return {
        "title": "01 矩阵的连通块计数",
        "statement": (
            "给定一个由 0 和 1 组成的矩阵，把上下左右相邻的 1 看成同一块，"
            "求矩阵中一共有多少块「1 的连通区域」。\n\n"
            "注意只算上下左右四个方向，斜着相邻不算连通。"
        ),
        "input_format": "第一行两个整数 R、C；接下来 R 行，每行一个长度为 C 的 01 串。",
        "output_format": "一个整数，表示 1 的连通块个数。",
        "constraints": "R, C ≤ %d；矩阵中 1 的密度随机。\n"
                       "提示：BFS / DFS / 并查集都可以，O(RC)；注意递归 DFS 在 %d×%d 的规模下可能爆栈。"
                       % (big, big, big),
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "tags": ["图搜索", "BFS", "第2章"],
        "samples": samples,
        "hidden": hidden,
        "solve": solve,
        "param": {"big": big},
    }


# ---------------------------------------------------------------------------
# 3. Chapter 2 · 字典序最小拓扑序
# ---------------------------------------------------------------------------


def b_topo(rng: random.Random, d: int) -> dict:
    def solve(text):
        import heapq

        data = text.split()
        p = 0
        n = int(data[p]); p += 1
        m = int(data[p]); p += 1
        adj = [[] for _ in range(n + 1)]
        indeg = [0] * (n + 1)
        for _ in range(m):
            u = int(data[p]); v = int(data[p + 1]); p += 2
            adj[u].append(v)
            indeg[v] += 1
        heap = [i for i in range(1, n + 1) if indeg[i] == 0]
        heapq.heapify(heap)
        out = []
        while heap:
            u = heapq.heappop(heap)
            out.append(u)
            for v in adj[u]:
                indeg[v] -= 1
                if indeg[v] == 0:
                    heapq.heappush(heap, v)
        if len(out) != n:
            return "-1\n"
        return " ".join(map(str, out)) + "\n"

    def make(n, extra, force_dag=True):
        edges = set()
        for v in range(2, n + 1):
            u = rng.randint(1, v - 1)
            edges.add((u, v))
        tries = 0
        while len(edges) < n - 1 + extra and tries < extra * 20:
            u = rng.randint(1, n)
            v = rng.randint(1, n)
            tries += 1
            if u == v:
                continue
            if force_dag and u > v:
                u, v = v, u
            edges.add((u, v))
        body = "\n".join("%d %d" % e for e in edges)
        return "%d %d\n%s\n" % (n, len(edges), body)

    samples, hidden = [], []
    samples.append(("4 3\n1 2\n2 3\n2 4\n", solve("4 3\n1 2\n2 3\n2 4\n")))
    cyc = "3 3\n1 2\n2 3\n3 1\n"
    samples.append((cyc, solve(cyc)))
    for _ in range(2):
        t = make(rng.randint(3, 6), rng.randint(0, 3))
        hidden.append((t, solve(t)))
    n = _size(d, [300, 1200, 5000, 12000, 24000])
    for _ in range(3):
        t = make(n, max(1, n // 2))
        hidden.append((t, solve(t)))
    hidden.append((make(n // 3, 0), solve(make(n // 3, 0))))
    # 一个必定有环的测试点
    cycbig = "5 5\n1 2\n2 3\n3 4\n4 5\n5 2\n"
    hidden.append((cycbig, solve(cycbig)))
    return {
        "title": "字典序最小的拓扑序",
        "statement": (
            "给定一张有向图，它的节点编号为 1~n。如果图中没有环，"
            "请输出字典序最小的拓扑序；如果存在环，输出 -1。\n\n"
            "字典序最小是指：在所有合法的拓扑序中，第一个数尽量小，"
            "在第一个数相同的前提下第二个数尽量小，依此类推。"
        ),
        "input_format": "第一行两个整数 n、m；接下来 m 行，每行两个整数 u v，表示一条 u → v 的有向边。",
        "output_format": "一行，字典序最小的拓扑序（用空格分隔）；若图中有环则输出 -1。",
        "constraints": "n ≤ %d，m ≤ %d，允许重边。\n"
                       "提示：不能直接拿任意拓扑序排序，要用小根堆维护入度为 0 的点，O((n+m)log n)。"
                       % (n, 2 * n),
        "time_limit_ms": 1500,
        "memory_limit_mb": 128,
        "tags": ["拓扑排序", "贪心", "第2章"],
        "samples": samples,
        "hidden": hidden,
        "solve": solve,
        "param": {"n": n},
    }


# ---------------------------------------------------------------------------
# 4. Chapter 3 · 最少箭数（区间选点，贪心）
# ---------------------------------------------------------------------------


def b_arrows(rng: random.Random, d: int) -> dict:
    def solve(text):
        data = text.split()
        n = int(data[0])
        segs = []
        p = 1
        for _ in range(n):
            segs.append((int(data[p]), int(data[p + 1])))
            p += 2
        segs.sort(key=lambda s: s[1])
        cnt, last = 0, None
        for l, r in segs:
            if last is None or l > last:
                cnt += 1
                last = r
        return "%d\n" % cnt

    def make(n, span):
        segs = []
        for _ in range(n):
            l = rng.randint(0, span)
            r = l + rng.randint(1, max(1, span // 4))
            segs.append((l, r))
        body = "\n".join("%d %d" % s for s in segs)
        return "%d\n%s\n" % (n, body)

    samples, hidden = [], []
    t = "3\n1 3\n2 4\n4 6\n"
    samples.append((t, solve(t)))
    t = "1\n5 9\n"
    samples.append((t, solve(t)))
    for _ in range(2):
        tt = make(rng.randint(2, 5), 12)
        hidden.append((tt, solve(tt)))
    n = _size(d, [500, 3000, 12000, 40000, 90000])
    for _ in range(3):
        tt = make(n, rng.choice([2000, 10 ** 6]))
        hidden.append((tt, solve(tt)))
    # 两两不重叠：答案就是 n
    disjoint = "%d\n%s\n" % (4, "\n".join("%d %d" % (i * 10, i * 10 + 5) for i in range(4)))
    hidden.append((disjoint, solve(disjoint)))
    return {
        "title": "最少的箭引爆所有气球",
        "statement": (
            "在一条水平线上飘着 n 个气球，每个气球给出它占据的水平区间 [l, r]。"
            "弓箭手可以垂直向上射出无限高的箭，一支箭会射爆所有水平位置包含它的气球。\n\n"
            "问：最少需要多少支箭，才能把所有气球都射爆？"
        ),
        "input_format": "第一行一个整数 n；接下来 n 行，每行两个整数 l、r，表示一个气球的区间。",
        "output_format": "一个整数，表示最少的箭数。",
        "constraints": "n ≤ %d，0 ≤ l < r ≤ 10⁶。\n"
                       "提示：按右端点排序后贪心放置箭，可用交换论证证明最优，O(n log n)。" % n,
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "tags": ["贪心", "区间选点", "第3章"],
        "samples": samples,
        "hidden": hidden,
        "solve": solve,
        "param": {"n": n},
    }


# ---------------------------------------------------------------------------
# 5. Chapter 3 · 合并果子（Huffman 贪心 + 堆）
# ---------------------------------------------------------------------------


def b_huffman(rng: random.Random, d: int) -> dict:
    def solve(text):
        import heapq

        data = text.split()
        n = int(data[0])
        heap = [int(x) for x in data[1:1 + n]]
        heapq.heapify(heap)
        total = 0
        while len(heap) > 1:
            a = heapq.heappop(heap)
            b = heapq.heappop(heap)
            total += a + b
            heapq.heappush(heap, a + b)
        return "%d\n" % total

    def make(n, hi):
        arr = [rng.randint(1, hi) for _ in range(n)]
        return "%d\n%s\n" % (n, _fmt(arr))

    samples, hidden = [], []
    t = "3\n1 2 9\n"
    samples.append((t, solve(t)))
    t = "2\n5 7\n"
    samples.append((t, solve(t)))
    for _ in range(2):
        tt = make(rng.randint(2, 5), 20)
        hidden.append((tt, solve(tt)))
    n = _size(d, [400, 2000, 8000, 20000, 40000])
    for _ in range(3):
        tt = make(n, rng.choice([10, 10000]))
        hidden.append((tt, solve(tt)))
    hidden.append(("1\n7\n", "0\n"))
    return {
        "title": "合并果子（最小合并代价）",
        "statement": (
            "有 n 堆果子，每堆的重量为 aᵢ。每次可以把任意两堆合并成一堆，"
            "消耗的体力等于两堆重量之和。\n\n"
            "把 n 堆果子合并成一堆，最少要消耗多少体力？"
        ),
        "input_format": "第一行一个整数 n；第二行 n 个整数 aᵢ。",
        "output_format": "一个整数，表示最小总代价。",
        "constraints": "n ≤ %d，1 ≤ aᵢ ≤ 10⁴。答案可能超出 32 位整数，请使用 64 位整数。\n"
                       "提示：每次合并当前最小的两堆（Huffman 贪心），用优先队列做到 O(n log n)；"
                       "答案的错误量级常来自用 int 存中间结果。" % n,
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "tags": ["贪心", "Huffman", "优先队列", "第3章"],
        "samples": samples,
        "hidden": hidden,
        "solve": solve,
        "param": {"n": n},
    }


# ---------------------------------------------------------------------------
# 6. Chapter 4 · 快速幂取模（分治）
# ---------------------------------------------------------------------------


def b_powmod(rng: random.Random, d: int) -> dict:
    def solve(text):
        a, b, m = (int(x) for x in text.split()[:3])
        if m == 1:
            return "0\n"
        r = 1
        a %= m
        while b:
            if b & 1:
                r = r * a % m
            a = a * a % m
            b >>= 1
        return "%d\n" % r

    samples, hidden = [], []
    t = "2 10 1000\n"
    samples.append((t, solve(t)))
    t = "7 0 13\n"
    samples.append((t, solve(t)))
    for _ in range(2):
        tt = "%d %d %d\n" % (rng.randint(0, 50), rng.randint(0, 30), rng.randint(1, 100))
        hidden.append((tt, solve(tt)))
    hi = _size(d, [10 ** 6, 10 ** 9, 10 ** 12, 10 ** 15, 10 ** 18])
    for _ in range(5):
        tt = "%d %d %d\n" % (rng.randint(1, 10 ** 9), rng.randint(1, hi), rng.randint(2, 10 ** 9))
        hidden.append((tt, solve(tt)))
    hidden.append(("5 999999999999 1\n", solve("5 999999999999 1\n")))
    return {
        "title": "快速幂取模",
        "statement": (
            "计算 a^b mod m 的值。b 可能非常大，直接用循环乘 b 次会超时，"
            "请用「平方—倍增」的分治思想把它降到 O(log b)。"
        ),
        "input_format": "一行三个整数 a、b、m。",
        "output_format": "一个整数，即 a^b mod m。",
        "constraints": "0 ≤ a < 10⁹，0 ≤ b ≤ %d，1 ≤ m < 10⁹。\n"
                       "提示：m = 1 时答案是 0，别忘了这个边界。" % hi,
        "time_limit_ms": 1000,
        "memory_limit_mb": 64,
        "tags": ["分治", "快速幂", "第4章"],
        "samples": samples,
        "hidden": hidden,
        "solve": solve,
        "param": {"b_max": hi},
    }


# ---------------------------------------------------------------------------
# 7. Chapter 4 · 二维最近点对（分治）
# ---------------------------------------------------------------------------


def b_closest(rng: random.Random, d: int) -> dict:
    def solve(text):
        data = text.split()
        n = int(data[0])
        pts = [(int(data[1 + 2 * i]), int(data[2 + 2 * i])) for i in range(n)]

        def rec(ps):
            if len(ps) <= 3:
                best = None
                for i in range(len(ps)):
                    for j in range(i + 1, len(ps)):
                        dx = ps[i][0] - ps[j][0]
                        dy = ps[i][1] - ps[j][1]
                        dd = dx * dx + dy * dy
                        if best is None or dd < best:
                            best = dd
                return best, sorted(ps, key=lambda p: p[1])
            mid = len(ps) // 2
            midx = ps[mid][0]
            dl, yl = rec(ps[:mid])
            dr, yr = rec(ps[mid:])
            best = dl if dl is not None and (dr is None or dl <= dr) else dr
            y = []
            i = j = 0
            while i < len(yl) and j < len(yr):
                if yl[i][1] <= yr[j][1]:
                    y.append(yl[i]); i += 1
                else:
                    y.append(yr[j]); j += 1
            y.extend(yl[i:])
            y.extend(yr[j:])
            strip = [p for p in y if (p[0] - midx) ** 2 < best]
            for a in range(len(strip)):
                for b in range(a + 1, len(strip)):
                    if (strip[b][1] - strip[a][1]) ** 2 >= best:
                        break
                    dx = strip[a][0] - strip[b][0]
                    dy = strip[a][1] - strip[b][1]
                    dd = dx * dx + dy * dy
                    if dd < best:
                        best = dd
            return best, y

        pts.sort()
        best, _ = rec(pts)
        return "%d\n" % best

    def make(n, span):
        seen = set()
        while len(seen) < n:
            seen.add((rng.randint(0, span), rng.randint(0, span)))
        pts = list(seen)
        return "%d\n%s\n" % (n, "\n".join("%d %d" % p for p in pts))

    samples, hidden = [], []
    t = "3\n0 0\n3 4\n6 8\n"
    samples.append((t, solve(t)))
    t = "2\n0 0\n1 1\n"
    samples.append((t, solve(t)))
    for _ in range(2):
        tt = make(rng.randint(3, 6), 20)
        hidden.append((tt, solve(tt)))
    n = _size(d, [400, 1500, 3000, 5000, 6000])
    for _ in range(3):
        tt = make(n, rng.choice([10 ** 6, 5000]))
        hidden.append((tt, solve(tt)))
    hidden.append(("2\n0 0\n1000000 1000000\n", "2000000000000\n"))
    return {
        "title": "平面最近点对的距离",
        "statement": (
            "平面上有 n 个互不相同的整点，求距离最近的一对点之间距离的**平方**。\n\n"
            "答案一定是整数（距离平方 = Δx² + Δy²），请直接输出它，不要开根号、不要四舍五入。"
        ),
        "input_format": "第一行一个整数 n；接下来 n 行，每行两个整数 x、y。",
        "output_format": "一个整数，表示最近点对距离的平方。",
        "constraints": "2 ≤ n ≤ %d，|x|, |y| ≤ 10⁶，点互不相同。答案可能很大，请用 64 位整数。\n"
                       "提示：按 x 排序分治，合并时只检查宽度小于当前最优解的中轴带，"
                       "每个点最多与带内常数个点比较，O(n log n)；暴力 O(n²) 会超时。" % n,
        "time_limit_ms": 2000,
        "memory_limit_mb": 256,
        "tags": ["分治", "最近点对", "第4章"],
        "samples": samples,
        "hidden": hidden,
        "solve": solve,
        "param": {"n": n},
    }


# ---------------------------------------------------------------------------
# 8. Chapter 5 · 最长上升子序列
# ---------------------------------------------------------------------------


def b_lis(rng: random.Random, d: int) -> dict:
    def solve(text):
        from bisect import bisect_left

        data = text.split()
        n = int(data[0])
        a = [int(x) for x in data[1:1 + n]]
        tails = []
        for x in a:
            i = bisect_left(tails, x)
            if i == len(tails):
                tails.append(x)
            else:
                tails[i] = x
        return "%d\n" % len(tails)

    def make(n, hi):
        return "%d\n%s\n" % (n, _fmt([rng.randint(1, hi) for _ in range(n)]))

    samples, hidden = [], []
    t = "6\n1 7 3 5 9 4\n"
    samples.append((t, solve(t)))
    t = "4\n4 3 2 1\n"
    samples.append((t, solve(t)))
    for _ in range(2):
        tt = make(rng.randint(3, 8), 10)
        hidden.append((tt, solve(tt)))
    n = _size(d, [2000, 8000, 20000, 40000, 80000])
    for _ in range(3):
        tt = make(n, rng.choice([50, 10 ** 9]))
        hidden.append((tt, solve(tt)))
    hidden.append(("1\n42\n", "1\n"))
    return {
        "title": "最长上升子序列的长度",
        "statement": (
            "给定一个长度为 n 的整数序列，求它的最长**严格上升**子序列的长度。\n\n"
            "子序列不要求连续，但要求下标递增、数值严格递增。"
        ),
        "input_format": "第一行一个整数 n；第二行 n 个整数。",
        "output_format": "一个整数，最长严格上升子序列的长度。",
        "constraints": "n ≤ %d，1 ≤ aᵢ ≤ 10⁹。\n"
                       "提示：维护「长度为 i 的上升子序列的最小结尾」，在有序数组上二分，"
                       "O(n log n)；朴素 DP 的 O(n²) 会超时。" % n,
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "tags": ["动态规划", "二分", "第5章"],
        "samples": samples,
        "hidden": hidden,
        "solve": solve,
        "param": {"n": n},
    }


# ---------------------------------------------------------------------------
# 9. Chapter 5 · 凑出目标金额的最少硬币数（完全背包）
# ---------------------------------------------------------------------------


def b_coin(rng: random.Random, d: int) -> dict:
    def solve(text):
        data = text.split()
        n = int(data[0])
        w = int(data[1])
        coins = [int(x) for x in data[2:2 + n]]
        INF = float('inf')
        dp = [0] + [INF] * w
        for c in coins:
            for x in range(c, w + 1):
                if dp[x - c] + 1 < dp[x]:
                    dp[x] = dp[x - c] + 1
        return "%d\n" % (-1 if dp[w] == INF else int(dp[w]))

    def make(n, w, hi):
        coins = rng.sample(range(1, hi + 1), n)
        return "%d %d\n%s\n" % (n, w, _fmt(coins))

    samples, hidden = [], []
    t = "3 11\n1 2 5\n"
    samples.append((t, solve(t)))
    t = "1 3\n2\n"
    samples.append((t, solve(t)))
    for _ in range(2):
        tt = make(rng.randint(2, 4), rng.randint(3, 20), 12)
        hidden.append((tt, solve(tt)))
    w = _size(d, [500, 2000, 6000, 12000, 24000])
    for _ in range(3):
        tt = make(rng.randint(3, 8), w, max(12, w // 3))
        hidden.append((tt, solve(tt)))
    hidden.append(("1 %d\n1\n" % w, "%d\n" % w))
    return {
        "title": "凑出目标金额的最少硬币数",
        "statement": (
            "给定 n 种硬币的面额，每种硬币可以使用任意多枚，"
            "问凑出金额 W 最少需要多少枚硬币；如果凑不出来输出 -1。"
        ),
        "input_format": "第一行两个整数 n、W；第二行 n 个互不相同的整数，表示硬币面额。",
        "output_format": "一个整数，最少硬币数；凑不出来输出 -1。",
        "constraints": "n ≤ 20，面额 ≤ %d，W ≤ %d。\n"
                       "提示：这是完全背包，内层循环要**正序**枚举金额，O(nW)。"
                       % (max(12, w // 3), w),
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "tags": ["动态规划", "完全背包", "第5章"],
        "samples": samples,
        "hidden": hidden,
        "solve": solve,
        "param": {"w": w},
    }


# ---------------------------------------------------------------------------
# 10. Chapter 6 · 最大流（Dinic）
# ---------------------------------------------------------------------------


def b_maxflow(rng: random.Random, d: int) -> dict:
    def solve(text):
        from collections import deque

        data = text.split()
        p = 0
        n = int(data[p]); p += 1
        m = int(data[p]); p += 1
        s = int(data[p]); p += 1
        t = int(data[p]); p += 1
        to, cap, nxt = [], [], [[] for _ in range(n + 1)]
        for _ in range(m):
            u = int(data[p]); v = int(data[p + 1]); c = int(data[p + 2]); p += 3
            nxt[u].append(len(to)); to.append(v); cap.append(c)
            nxt[v].append(len(to)); to.append(u); cap.append(0)

        flow = 0
        while True:
            level = [-1] * (n + 1)
            level[s] = 0
            dq = deque([s])
            while dq:
                u = dq.popleft()
                for eid in nxt[u]:
                    if cap[eid] > 0 and level[to[eid]] < 0:
                        level[to[eid]] = level[u] + 1
                        dq.append(to[eid])
            if level[t] < 0:
                break
            it = [0] * (n + 1)

            def dfs(u, f):
                if u == t:
                    return f
                while it[u] < len(nxt[u]):
                    eid = nxt[u][it[u]]
                    v = to[eid]
                    if cap[eid] > 0 and level[v] == level[u] + 1:
                        got = dfs(v, min(f, cap[eid]))
                        if got:
                            cap[eid] -= got
                            cap[eid ^ 1] += got
                            return got
                    it[u] += 1
                return 0

            while True:
                f = dfs(s, float('inf'))
                if not f:
                    break
                flow += f
        return "%d\n" % int(flow)

    def make(n, extra, hi):
        edges = set()
        for v in range(2, n + 1):
            u = rng.randint(1, v - 1)
            edges.add((u, v))
        tries = 0
        while len(edges) < n - 1 + extra and tries < extra * 20:
            u = rng.randint(1, n)
            v = rng.randint(1, n)
            tries += 1
            if u != v:
                edges.add((u, v))
        lines = ["%d %d %d" % (u, v, rng.randint(1, hi)) for u, v in edges]
        return "%d %d 1 %d\n%s\n" % (n, len(lines), n, "\n".join(lines))

    samples, hidden = [], []
    t = "4 5 1 4\n1 2 3\n1 3 2\n2 3 1\n2 4 2\n3 4 4\n"
    samples.append((t, solve(t)))
    t = "3 2 1 3\n1 2 5\n2 3 5\n"
    samples.append((t, solve(t)))
    n = _size(d, [10, 20, 40, 70, 110])
    extra = _size(d, [4, 12, 30, 70, 160])
    for _ in range(3):
        tt = make(n, extra, rng.choice([10, 10 ** 4]))
        hidden.append((tt, solve(tt)))
    hidden.append(("2 1 1 2\n1 2 7\n", "7\n"))
    hidden.append(("2 0 1 2\n", "0\n"))
    return {
        "title": "网络的最大流",
        "statement": (
            "给定一张有向网络（含源点 s 和汇点 t），每条边有非负容量，"
            "求从 s 到 t 的最大流值。"
        ),
        "input_format": "第一行四个整数 n、m、s、t；接下来 m 行，每行三个整数 u、v、c，表示一条 u → v 容量为 c 的有向边。",
        "output_format": "一个整数，最大流的值。",
        "constraints": "n ≤ %d，m ≤ %d，1 ≤ c ≤ 10⁴，1 ≤ s, t ≤ n，s ≠ t。\n"
                       "提示：Dinic（BFS 分层 + DFS 多路增广）在本题规模下足够快；"
                       "只用一次 BFS 找一条增广路的做法会被大容量边拖慢。"
                       % (n, n - 1 + extra),
        "time_limit_ms": 1500,
        "memory_limit_mb": 128,
        "tags": ["网络流", "最大流", "第6章"],
        "samples": samples,
        "hidden": hidden,
        "solve": solve,
        "param": {"n": n, "extra": extra},
    }


# ---------------------------------------------------------------------------
# 11. Chapter 7 · 并查集（合并 + 查询）
# ---------------------------------------------------------------------------


def b_dsu(rng: random.Random, d: int) -> dict:
    def solve(text):
        data = text.split()
        p = 0
        n = int(data[p]); p += 1
        q = int(data[p]); p += 1
        par = list(range(n + 1))
        size = [1] * (n + 1)

        def find(x):
            root = x
            while par[root] != root:
                root = par[root]
            while par[x] != root:
                par[x], x = root, par[x]
            return root

        out = []
        for _ in range(q):
            op = data[p]; a = int(data[p + 1]); b = int(data[p + 2]); p += 3
            ra, rb = find(a), find(b)
            if op == '1':
                if ra != rb:
                    if size[ra] < size[rb]:
                        ra, rb = rb, ra
                    par[rb] = ra
                    size[ra] += size[rb]
            else:
                out.append("Y" if ra == rb else "N")
        return "\n".join(out) + ("\n" if out else "")

    def make(n, q, merge_p):
        lines = []
        for _ in range(q):
            a = rng.randint(1, n)
            b = rng.randint(1, n)
            if rng.random() < merge_p:
                lines.append("1 %d %d" % (a, b))
            else:
                lines.append("2 %d %d" % (a, b))
        return "%d %d\n%s\n" % (n, q, "\n".join(lines))

    samples, hidden = [], []
    t = "4 5\n1 1 2\n2 1 2\n2 1 3\n1 3 4\n2 1 4\n"
    samples.append((t, solve(t)))
    t = "2 2\n2 1 2\n1 1 2\n"
    samples.append((t, solve(t)))
    for _ in range(2):
        tt = make(rng.randint(2, 6), rng.randint(3, 10), 0.5)
        hidden.append((tt, solve(tt)))
    n = _size(d, [2000, 20000, 50000, 80000, 120000])
    q = n
    for _ in range(3):
        tt = make(n, q, rng.choice([0.3, 0.5, 0.75]))
        hidden.append((tt, solve(tt)))
    hidden.append(("3 3\n2 1 2\n2 2 3\n1 1 3\n", "N\nN\n"))
    return {
        "title": "并查集：动态连通性查询",
        "statement": (
            "有 n 个元素，初始时各自独立。支持两种操作：\n\n"
            "· 1 a b：把 a 所在的集合与 b 所在的集合合并；\n"
            "· 2 a b：询问 a 与 b 现在是否属于同一个集合。\n\n"
            "请按顺序处理所有操作，对每个询问输出一行结果。"
        ),
        "input_format": "第一行两个整数 n、q；接下来 q 行，每行三个整数 op a b。",
        "output_format": "对每个 2 操作输出一行：同一个集合输出 Y，否则输出 N。",
        "constraints": "n, q ≤ %d。\n"
                       "提示：路径压缩 + 按大小合并，均摊 O(α(n))；"
                       "只做朴素链接（把一棵树直接挂到另一棵上）会退化成链，最坏 O(n) 一次。" % n,
        "time_limit_ms": 1500,
        "memory_limit_mb": 128,
        "tags": ["并查集", "路径压缩", "第7章"],
        "samples": samples,
        "hidden": hidden,
        "solve": solve,
        "param": {"n": n, "q": q},
    }


# ---------------------------------------------------------------------------
# 12. Chapter 8 · 区间最大值查询（静态 RMQ）
# ---------------------------------------------------------------------------


def b_rangemax(rng: random.Random, d: int) -> dict:
    def solve(text):
        data = text.split()
        p = 0
        n = int(data[p]); p += 1
        q = int(data[p]); p += 1
        a = [int(x) for x in data[p:p + n]]; p += n
        LOG = [0] * (n + 1)
        for i in range(2, n + 1):
            LOG[i] = LOG[i // 2] + 1
        k = LOG[n] + 1
        sp = [a[:]]
        for j in range(1, k):
            prev = sp[-1]
            span = 1 << (j - 1)
            cur = [max(prev[i], prev[i + span]) for i in range(n - (1 << j) + 1)]
            sp.append(cur)
        out = []
        for _ in range(q):
            l = int(data[p]); r = int(data[p + 1]); p += 2
            j = LOG[r - l + 1]
            out.append(str(max(sp[j][l - 1], sp[j][r - (1 << j)])))
        return "\n".join(out) + ("\n" if out else "")

    def make(n, q, hi):
        arr = [rng.randint(-hi, hi) for _ in range(n)]
        lines = []
        for _ in range(q):
            l = rng.randint(1, n)
            r = rng.randint(l, n)
            lines.append("%d %d" % (l, r))
        return "%d %d\n%s\n%s\n" % (n, q, _fmt(arr), "\n".join(lines))

    samples, hidden = [], []
    t = "5 3\n3 -1 4 1 5\n1 5\n2 3\n4 4\n"
    samples.append((t, solve(t)))
    t = "1 1\n-7\n1 1\n"
    samples.append((t, solve(t)))
    for _ in range(2):
        tt = make(rng.randint(2, 8), rng.randint(1, 5), 20)
        hidden.append((tt, solve(tt)))
    n = _size(d, [2000, 8000, 20000, 40000, 60000])
    q = max(1, n)
    for _ in range(3):
        tt = make(n, q, rng.choice([10, 10 ** 9]))
        hidden.append((tt, solve(tt)))
    return {
        "title": "静态区间最大值查询",
        "statement": (
            "给定一个长度为 n 的数组，回答 q 次询问：每次给出区间 [l, r]，"
            "求该区间内元素的最大值。数组在询问过程中不会改变。"
        ),
        "input_format": "第一行两个整数 n、q；第二行 n 个整数；接下来 q 行，每行两个整数 l、r（1 ≤ l ≤ r ≤ n）。",
        "output_format": "共 q 行，每行一个整数，表示对应询问的答案。",
        "constraints": "n, q ≤ %d，|aᵢ| ≤ 10⁹。\n"
                       "提示：稀疏表（ST 表）预处理 O(n log n)、单次询问 O(1)；"
                       "每次询问都扫一遍区间是 O(nq)，一定会超时。" % n,
        "time_limit_ms": 1500,
        "memory_limit_mb": 256,
        "tags": ["线段树", "稀疏表", "RMQ", "第8章"],
        "samples": samples,
        "hidden": hidden,
        "solve": solve,
        "param": {"n": n, "q": q},
    }


# ---------------------------------------------------------------------------
# 13. Chapter 8 · 区间加 + 区间求和（线段树 / 双树状数组）
# ---------------------------------------------------------------------------


def b_range_add_sum(rng: random.Random, d: int) -> dict:
    def solve(text):
        data = text.split()
        p = 0
        n = int(data[p]); p += 1
        m = int(data[p]); p += 1
        a = [0] * (n + 1)
        for i in range(1, n + 1):
            a[i] = int(data[p]); p += 1
        b1 = [0] * (n + 2)
        b2 = [0] * (n + 2)

        def add(b, i, v):
            while i <= n:
                b[i] += v
                i += i & (-i)

        def pre(b, i):
            s = 0
            while i > 0:
                s += b[i]
                i -= i & (-i)
            return s

        def pre_sum(i):
            return pre(b1, i) * (i + 1) - pre(b2, i)

        def range_add(l, r, v):
            add(b1, l, v); add(b1, r + 1, -v)
            add(b2, l, v * l); add(b2, r + 1, -v * (r + 1))

        out = []
        for i in range(1, n + 1):
            range_add(i, i, a[i])
        for _ in range(m):
            op = data[p]; p += 1
            if op == '1':
                l = int(data[p]); r = int(data[p + 1]); v = int(data[p + 2]); p += 3
                range_add(l, r, v)
            else:
                l = int(data[p]); r = int(data[p + 1]); p += 2
                out.append(str(pre_sum(r) - pre_sum(l - 1)))
        return "\n".join(out) + ("\n" if out else "")

    def make(n, m, hi):
        arr = [rng.randint(-hi, hi) for _ in range(n)]
        lines = []
        for _ in range(m):
            if rng.random() < 0.5:
                l = rng.randint(1, n)
                r = rng.randint(l, n)
                lines.append("1 %d %d %d" % (l, r, rng.randint(-100, 100)))
            else:
                l = rng.randint(1, n)
                r = rng.randint(l, n)
                lines.append("2 %d %d" % (l, r))
        return "%d %d\n%s\n%s\n" % (n, m, _fmt(arr), "\n".join(lines))

    samples, hidden = [], []
    t = "5 3\n1 2 3 4 5\n1 2 4 10\n2 1 5\n2 3 3\n"
    samples.append((t, solve(t)))
    t = "3 2\n0 0 0\n1 1 3 5\n2 1 3\n"
    samples.append((t, solve(t)))
    for _ in range(2):
        tt = make(rng.randint(2, 8), rng.randint(2, 6), 20)
        hidden.append((tt, solve(tt)))
    n = _size(d, [2000, 8000, 20000, 40000, 60000])
    m = max(2, n)
    for _ in range(3):
        tt = make(n, m, rng.choice([1000, 10 ** 6]))
        hidden.append((tt, solve(tt)))
    return {
        "title": "区间加与区间求和",
        "statement": (
            "维护一个长度为 n 的整数数组，支持两种操作：\n\n"
            "· 1 l r v：把 a[l..r] 的每个元素都加上 v；\n"
            "· 2 l r：询问 a[l..r] 的元素之和。\n\n"
            "请对每个询问输出一行答案。"
        ),
        "input_format": "第一行两个整数 n、m；第二行 n 个整数 a₁…aₙ；接下来 m 行，每行是 1 l r v 或 2 l r。",
        "output_format": "对每个 2 操作输出一行，表示区间和。",
        "constraints": "n, m ≤ %d，|aᵢ| ≤ 10⁶，|v| ≤ 100。\n"
                       "提示：带懒标记的线段树，或者「两个树状数组」的差分做法，O(log n) 每次操作；"
                       "每次询问都累加一遍是 O(nm)，会超时。" % n,
        "time_limit_ms": 2000,
        "memory_limit_mb": 256,
        "tags": ["线段树", "懒标记", "树状数组", "第8章"],
        "samples": samples,
        "hidden": hidden,
        "solve": solve,
        "param": {"n": n, "m": m},
    }


# ---------------------------------------------------------------------------
# 14. Chapter 9 · 区间加 + 单点查询（差分树状数组）
# ---------------------------------------------------------------------------


def b_range_add_point(rng: random.Random, d: int) -> dict:
    def solve(text):
        data = text.split()
        p = 0
        n = int(data[p]); p += 1
        m = int(data[p]); p += 1
        bit = [0] * (n + 2)

        def add(i, v):
            while i <= n:
                bit[i] += v
                i += i & (-i)

        def pre(i):
            s = 0
            while i > 0:
                s += bit[i]
                i -= i & (-i)
            return s

        out = []
        for _ in range(m):
            op = data[p]; p += 1
            if op == '1':
                l = int(data[p]); r = int(data[p + 1]); v = int(data[p + 2]); p += 3
                add(l, v)
                if r + 1 <= n:
                    add(r + 1, -v)
            else:
                i = int(data[p]); p += 1
                out.append(str(pre(i)))
        return "\n".join(out) + ("\n" if out else "")

    def make(n, m):
        lines = []
        for _ in range(m):
            if rng.random() < 0.55:
                l = rng.randint(1, n)
                r = rng.randint(l, n)
                lines.append("1 %d %d %d" % (l, r, rng.randint(-50, 50)))
            else:
                lines.append("2 %d" % rng.randint(1, n))
        return "%d %d\n%s\n" % (n, m, "\n".join(lines))

    samples, hidden = [], []
    t = "5 4\n1 1 3 4\n2 2\n1 3 5 1\n2 5\n"
    samples.append((t, solve(t)))
    t = "2 1\n2 1\n"
    samples.append((t, solve(t)))
    for _ in range(2):
        tt = make(rng.randint(2, 8), rng.randint(2, 8))
        hidden.append((tt, solve(tt)))
    n = _size(d, [2000, 10000, 30000, 50000, 80000])
    m = max(2, n)
    for _ in range(3):
        tt = make(n, m)
        hidden.append((tt, solve(tt)))
    return {
        "title": "区间加与单点查询",
        "statement": (
            "初始时数组 a[1..n] 全为 0，支持两种操作：\n\n"
            "· 1 l r v：把 a[l..r] 的每个元素都加上 v；\n"
            "· 2 i：输出当前 a[i] 的值。\n\n"
            "请对每个询问输出一行答案。"
        ),
        "input_format": "第一行两个整数 n、m；接下来 m 行，每行是 1 l r v 或 2 i。",
        "output_format": "对每个 2 操作输出一行，表示 a[i] 当前的值。",
        "constraints": "n, m ≤ %d，|v| ≤ 50。\n"
                       "提示：区间修改、单点查询用差分数组，套上树状数组做到 O(log n)；"
                       "直接维护原数组每次修改都改一段是 O(nm)，会超时。" % n,
        "time_limit_ms": 1500,
        "memory_limit_mb": 128,
        "tags": ["树状数组", "差分", "第9章"],
        "samples": samples,
        "hidden": hidden,
        "solve": solve,
        "param": {"n": n, "m": m},
    }


# ---------------------------------------------------------------------------
# 15. Chapter 10 · 最小循环节（前缀函数）
# ---------------------------------------------------------------------------


def b_period(rng: random.Random, d: int) -> dict:
    def solve(text):
        s = text.strip().split()[0]
        n = len(s)
        pi = [0] * n
        for i in range(1, n):
            j = pi[i - 1]
            while j > 0 and s[i] != s[j]:
                j = pi[j - 1]
            if s[i] == s[j]:
                j += 1
            pi[i] = j
        p = n - pi[-1]
        if n % p == 0 and p < n:
            return "%d\n" % p
        return "%d\n" % n

    def repeat(unit, times):
        return unit * times

    samples, hidden = [], []
    for s in ("abab", "abcabcabc", "abcd"):
        samples.append((s + "\n", solve(s + "\n")))
    for _ in range(2):
        unit = "".join(rng.choice("ab") for _ in range(rng.randint(2, 4)))
        s = repeat(unit, rng.randint(2, 4))
        hidden.append((s + "\n", solve(s + "\n")))
    n = _size(d, [2000, 20000, 60000, 120000, 300000])
    for _ in range(3):
        unit = "".join(rng.choice("ab") for _ in range(max(2, n // rng.randint(2, 8))))
        s = repeat(unit, len(unit) and max(1, n // len(unit))) or "a"
        hidden.append((s + "\n", solve(s + "\n")))
    hidden.append(("a\n", "1\n"))
    hidden.append(("abcab\n", "5\n"))
    return {
        "title": "字符串的最小循环节",
        "statement": (
            "给定一个由小写字母组成的字符串 s。如果 s 可以写成某个前缀重复 k ≥ 2 次的结果，"
            "输出这个前缀的最小长度（最小循环节）；否则输出 |s|。"
        ),
        "input_format": "一行，一个非空字符串 s。",
        "output_format": "一个整数，表示最小循环节的长度（不存在则输出字符串长度）。",
        "constraints": "|s| ≤ %d。\n"
                       "提示：先求前缀函数 π，令 p = n − π[n−1]；当 n 能被 p 整除且 p < n 时 p 就是答案，"
                       "O(n)。" % n,
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "tags": ["字符串匹配", "KMP", "前缀函数", "第10章"],
        "samples": samples,
        "hidden": hidden,
        "solve": solve,
        "param": {"n": n},
    }


# ---------------------------------------------------------------------------
# 16. Chapter 10 · 模式串出现次数（可重叠）
# ---------------------------------------------------------------------------


def b_kmp_count(rng: random.Random, d: int) -> dict:
    def solve(text):
        s, p = text.split()[:2]
        if len(p) > len(s):
            return "0\n"
        pi = [0] * len(p)
        for i in range(1, len(p)):
            j = pi[i - 1]
            while j > 0 and p[i] != p[j]:
                j = pi[j - 1]
            if p[i] == p[j]:
                j += 1
            pi[i] = j
        cnt = 0
        j = 0
        for ch in s:
            while j > 0 and ch != p[j]:
                j = pi[j - 1]
            if ch == p[j]:
                j += 1
            if j == len(p):
                cnt += 1
                j = pi[j - 1]      # 允许重叠：回到最长真前缀
        return "%d\n" % cnt

    samples, hidden = [], []
    t = "aaaa aaa\n"
    samples.append((t, solve(t)))
    t = "abcabcab abc\n"
    samples.append((t, solve(t)))
    for _ in range(2):
        unit = "".join(rng.choice("ab") for _ in range(rng.randint(2, 3)))
        s = unit * rng.randint(2, 5)
        hidden.append(("%s %s\n" % (s, unit), solve("%s %s\n" % (s, unit))))
    n = _size(d, [2000, 20000, 60000, 150000, 300000])
    for _ in range(3):
        s = "".join(rng.choice("abc") for _ in range(n))
        p = s[rng.randint(0, max(0, n - 1)):][:max(1, n // 5)]
        if not p:
            p = "a"
        hidden.append(("%s %s\n" % (s, p), solve("%s %s\n" % (s, p))))
    hidden.append(("abc def\n", "0\n"))
    return {
        "title": "统计模式串的出现次数",
        "statement": (
            "给定主串 s 和模式串 p，统计 p 在 s 中出现的次数。\n\n"
            "注意：允许**重叠**出现。例如 s = aaaa、p = aa，答案是 3 而不是 2。"
        ),
        "input_format": "一行，两个字符串 s 和 p，用空格分隔（均为小写字母）。",
        "output_format": "一个整数，p 在 s 中出现的次数（可重叠）。",
        "constraints": "|s| ≤ %d，|p| ≤ 10⁴。\n"
                       "提示：KMP 匹配成功后要令 j = π[j−1] 再继续，才能统计重叠的出现，O(|s| + |p|)。" % n,
        "time_limit_ms": 1500,
        "memory_limit_mb": 128,
        "tags": ["字符串匹配", "KMP", "第10章"],
        "samples": samples,
        "hidden": hidden,
        "solve": solve,
        "param": {"n": n},
    }


# ---------------------------------------------------------------------------
# 17. Chapter 11 · 小规模最大独立集（位枚举 / 状压 DP）
# ---------------------------------------------------------------------------


def b_indepset(rng: random.Random, d: int) -> dict:
    def solve(text):
        data = text.split()
        p = 0
        n = int(data[p]); p += 1
        m = int(data[p]); p += 1
        adj = [0] * n
        for _ in range(m):
            u = int(data[p]) - 1; v = int(data[p + 1]) - 1; p += 2
            adj[u] |= 1 << v
            adj[v] |= 1 << u
        ok = bytearray(1 << n)
        ok[0] = 1                      # 空集一定是独立集
        best = 0
        for mask in range(1, 1 << n):
            low = mask & (-mask)
            v = low.bit_length() - 1
            rest = mask ^ low
            if ok[rest] and (adj[v] & rest) == 0:
                ok[mask] = 1
                cnt = bin(mask).count('1')
                if cnt > best:
                    best = cnt
        return "%d\n" % best

    def make(n, extra):
        edges = set()
        for _ in range(extra):
            u = rng.randrange(n)
            v = rng.randrange(n)
            if u != v:
                edges.add((min(u, v), max(u, v)))
        body = "\n".join("%d %d" % (u + 1, v + 1) for u, v in sorted(edges))
        return "%d %d\n%s\n" % (n, len(edges), body)

    samples, hidden = [], []
    t = "3 2\n1 2\n2 3\n"
    samples.append((t, solve(t)))
    t = "4 6\n1 2\n1 3\n1 4\n2 3\n2 4\n3 4\n"
    samples.append((t, solve(t)))
    for _ in range(2):
        tt = make(rng.randint(3, 7), rng.randint(2, 8))
        hidden.append((tt, solve(tt)))
    n = _size(d, [10, 12, 14, 16, 18])
    for _ in range(3):
        tt = make(n, rng.randint(n, n * 2))
        hidden.append((tt, solve(tt)))
    hidden.append(("5 0\n", "5\n"))
    return {
        "title": "最大独立集（小规模）",
        "statement": (
            "给定一张无向图，找一个点数最多的顶点集合，使集合内任意两个顶点之间都没有边——"
            "这样的集合称为独立集。输出它的顶点个数。\n\n"
            "本题顶点数很小，可以放心使用指数级算法。"
        ),
        "input_format": "第一行两个整数 n、m；接下来 m 行，每行两个整数 u、v，表示一条无向边。",
        "output_format": "一个整数，最大独立集的大小。",
        "constraints": "n ≤ %d，m ≤ 2n，无自环。\n"
                       "提示：题目规模小，可以用状态压缩：用位掩码表示每个顶点，"
                       "枚举 2ⁿ 个集合并借助「去掉最低位后的集合是否独立」递推，O(2ⁿ)。" % n,
        "time_limit_ms": 2000,
        "memory_limit_mb": 256,
        "tags": ["NP 完全", "状态压缩", "第11章"],
        "samples": samples,
        "hidden": hidden,
        "solve": solve,
        "param": {"n": n},
    }


# ---------------------------------------------------------------------------
# 模板注册表
# ---------------------------------------------------------------------------


TEMPLATES: list[dict] = [
    {"key": "GROWTH", "name": "函数增长率排序", "chapter": "ch1",
     "topics": ["渐近记号", "增长率比较"], "level": (1, 3), "build": b_growth},
    {"key": "CONNECTED", "name": "01 矩阵连通块", "chapter": "ch2",
     "topics": ["图的表示", "BFS", "连通分量"], "level": (1, 3), "build": b_connected},
    {"key": "TOPO", "name": "字典序最小拓扑序", "chapter": "ch2",
     "topics": ["有向无环图", "拓扑排序"], "level": (3, 5), "build": b_topo},
    {"key": "ARROWS", "name": "最少箭数", "chapter": "ch3",
     "topics": ["区间调度", "贪心选择性质"], "level": (2, 4), "build": b_arrows},
    {"key": "HUFFMAN", "name": "合并果子", "chapter": "ch3",
     "topics": ["贪心算法", "优先队列"], "level": (2, 5), "build": b_huffman},
    {"key": "POWMOD", "name": "快速幂取模", "chapter": "ch4",
     "topics": ["分治与递归式"], "level": (1, 3), "build": b_powmod},
    {"key": "CLOSEST", "name": "平面最近点对", "chapter": "ch4",
     "topics": ["最近点对", "分治与递归式"], "level": (4, 5), "build": b_closest},
    {"key": "LIS", "name": "最长上升子序列", "chapter": "ch5",
     "topics": ["动态规划"], "level": (2, 4), "build": b_lis},
    {"key": "COINMIN", "name": "最少硬币数", "chapter": "ch5",
     "topics": ["背包问题", "动态规划"], "level": (1, 3), "build": b_coin},
    {"key": "MAXFLOW", "name": "最大流", "chapter": "ch6",
     "topics": ["最大流", "增广路"], "level": (3, 5), "build": b_maxflow},
    {"key": "DSU", "name": "并查集连通性", "chapter": "ch7",
     "topics": ["并查集", "路径压缩"], "level": (1, 3), "build": b_dsu},
    {"key": "RANGEMAX", "name": "区间最大值查询", "chapter": "ch8",
     "topics": ["线段树", "区间查询"], "level": (1, 3), "build": b_rangemax},
    {"key": "RANGEADDSUM", "name": "区间加与区间求和", "chapter": "ch8",
     "topics": ["线段树", "懒标记"], "level": (3, 5), "build": b_range_add_sum},
    {"key": "RANGEADDPOINT", "name": "区间加与单点查询", "chapter": "ch9",
     "topics": ["树状数组", "前缀和"], "level": (2, 4), "build": b_range_add_point},
    {"key": "PERIOD", "name": "最小循环节", "chapter": "ch10",
     "topics": ["KMP", "前缀函数"], "level": (3, 5), "build": b_period},
    {"key": "KMPCOUNT", "name": "模式串出现次数", "chapter": "ch10",
     "topics": ["字符串匹配", "KMP"], "level": (2, 4), "build": b_kmp_count},
    {"key": "INDEPSET", "name": "最大独立集", "chapter": "ch11",
     "topics": ["NP 完全", "独立集"], "level": (3, 5), "build": b_indepset},
]

TEMPLATE_BY_KEY = {t["key"]: t for t in TEMPLATES}

#: 判定「和已有题目重复」的题面相似度阈值
DUPLICATE_THRESHOLD = 0.62


def _level_gap(tpl: dict, d: int) -> int:
    lo, hi = tpl["level"]
    return 0 if lo <= d <= hi else min(abs(d - lo), abs(d - hi))


def _param_sig(param: dict) -> str:
    raw = "|".join("%s=%s" % (k, param[k]) for k in sorted(param))
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]


def make_draft(tpl: dict, difficulty: int, seed: int) -> dict:
    """用某个模板生成一道完整的题目草稿（题面 + 测试数据 + 参考答案）。"""
    rng = random.Random(seed)
    d = max(1, min(5, int(difficulty)))
    built = tpl["build"](rng, d)
    cases = _mk(built["samples"], built["hidden"])
    samples = [{"input": i, "output": o} for i, o in built["samples"]]
    sig = _param_sig({**built.get("param", {}), "seed": seed})
    return {
        "title": built["title"],
        "type": "programming",
        "difficulty": d,
        "chapter": tpl["chapter"],
        "topics": list(tpl.get("topics") or []),
        "tags": list(built.get("tags") or []),
        "statement": built["statement"],
        "input_format": built["input_format"],
        "output_format": built["output_format"],
        "constraints": built["constraints"],
        "samples": samples,
        "test_cases": cases,
        "time_limit_ms": built.get("time_limit_ms", 1000),
        "memory_limit_mb": built.get("memory_limit_mb", 128),
        "score": 100,
        "solution": solution_source(built["solve"]),
        "gen_key": "%s-%d-%s" % (tpl["key"], d, sig),
        "gen_source": "模板 %s · 难度 %d" % (tpl["name"], d),
    }


def _candidates(chapter: str | None, difficulty: int) -> list[dict]:
    cands = [t for t in TEMPLATES if chapter is None or t["chapter"] == chapter]
    if not cands:
        cands = list(TEMPLATES)
    exact = [t for t in cands if t["level"][0] <= difficulty <= t["level"][1]]
    if exact:
        # 精确命中难度的模板优先，再按「和难度的接近程度」兜底
        return sorted(exact, key=lambda t: (abs(difficulty - sum(t["level"]) / 2.0), t["key"]))
    return sorted(cands, key=lambda t: (_level_gap(t, difficulty), t["key"]))


def generate(
    chapter: str | None,
    difficulty: int,
    existing_keys: set[str] | None = None,
    existing_texts: list[tuple[str, str]] | None = None,
    avoid_keys: set[str] | None = None,
    allow_other_chapter: bool = True,
) -> dict:
    """生成一道新题，并给出「和已有题目是否重复」的检查报告。

    ``existing_keys``   题库里已有的 gen_key（精确去重）
    ``existing_texts``  [(题目名, 题面)]，用于算题面相似度
    ``avoid_keys``      本次会话里已经生成过的 gen_key（连点「换一题」时不重复）
    """
    started = time.time()
    existing_keys = set(existing_keys or ())
    avoid_keys = set(avoid_keys or ())
    existing_texts = list(existing_texts or [])
    difficulty = max(1, min(5, int(difficulty)))

    tried: list[dict] = []
    # 第一轮只在本章节里找；找不到再看其它章节（换一题时按需放宽）
    pools = [_candidates(chapter, difficulty)]
    if allow_other_chapter:
        other = sorted(TEMPLATES, key=lambda t: (_level_gap(t, difficulty), t["key"]))
        pools.append(other)

    best = None
    for pool in pools:
        for tpl in pool:
            for attempt in range(4):
                seed = random.randrange(1, 10 ** 9)
                draft = make_draft(tpl, difficulty, seed)
                best_sim, best_title = 0.0, ""
                for name, text in existing_texts:
                    sim = text_similarity(draft["statement"], text)
                    if sim > best_sim:
                        best_sim, best_title = sim, name
                rec = {"template": tpl["key"], "name": tpl["name"], "similarity": round(best_sim, 4),
                       "gen_key": draft["gen_key"], "dup_key": draft["gen_key"] in existing_keys,
                       "avoid": draft["gen_key"] in avoid_keys}
                tried.append(rec)
                if rec["dup_key"] or rec["avoid"]:
                    continue
                if best_sim >= DUPLICATE_THRESHOLD:
                    if best is None or best_sim < best[0]:
                        best = (best_sim, draft, best_title, tpl)
                    continue
                report = {
                    "template": tpl["key"],
                    "template_name": tpl["name"],
                    "difficulty": difficulty,
                    "attempts": len(tried),
                    "max_similarity": round(best_sim, 4),
                    "closest_title": best_title,
                    "reused": False,
                    "chapter_matched": tpl["chapter"] == chapter,
                    "tried": tried,
                    "elapsed_ms": round((time.time() - started) * 1000, 1),
                }
                return {"draft": draft, "report": report}

    # 所有模板都和已有题目撞上了：把最不像的一道交给教师，并说明原因
    if best is not None:
        sim, draft, title, tpl = best
        report = {
            "template": tpl["key"], "template_name": tpl["name"], "difficulty": difficulty,
            "attempts": len(tried), "max_similarity": round(sim, 4), "closest_title": title,
            "reused": True, "chapter_matched": tpl["chapter"] == chapter,
            "tried": tried, "elapsed_ms": round((time.time() - started) * 1000, 1),
        }
        return {"draft": draft, "report": report}
    raise RuntimeError("没有可用的出题模板")


def template_overview() -> list[dict]:
    """给前端展示的模板清单（章节 → 可用难度）。"""
    return [
        {"key": t["key"], "name": t["name"], "chapter": t["chapter"],
         "topics": t["topics"], "level": list(t["level"])}
        for t in TEMPLATES
    ]
