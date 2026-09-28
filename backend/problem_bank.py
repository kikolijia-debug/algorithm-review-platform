"""课程题库：题目元数据 + 测试数据生成器 + 参考程序模板。

每个编程题都提供

* ``gen``      : 用 Python 参考解法生成 (输入, 期望输出) 测试点（含边界）
* ``cpp_ok``   : 正确实现（C++）
* ``cpp_slow`` : 复杂度不达标的实现（用于制造 TLE 样本）
* ``cpp_bug``  : 含典型 bug 的实现（用于制造 WA 样本）

因此演示数据中的历史提交记录都是**真实可运行的代码**，教师点击「重测」
会得到与记录一致的评测结果，而不是伪造的数据。
"""

from __future__ import annotations

import heapq
import random
import zlib


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------


def _fmt_list(a) -> str:
    return " ".join(str(x) for x in a)


def _cases(samples: list[tuple[str, str]], hidden: list[tuple[str, str]]):
    out = []
    for i, (inp, exp) in enumerate(samples):
        out.append({"name": f"样例 {i + 1}", "input": inp, "expected": exp, "is_sample": 1})
    for i, (inp, exp) in enumerate(hidden):
        out.append({"name": f"测试点 {i + 1}", "input": inp, "expected": exp, "is_sample": 0})
    return out


def build_cases(problem: dict, base_seed: int = 2026) -> list[dict]:
    """确定性地生成某道题的测试点集合（供灌数据与模板校验共用）。

    使用 ``zlib.crc32`` 而不是内置 ``hash``，避免 Python 的哈希随机化导致
    两次运行生成不同数据。
    """
    seed = base_seed + zlib.crc32(problem["key"].encode("utf-8")) % 100000
    rng = random.Random(seed)
    raw = problem["gen"](rng)
    return [
        {
            "id": i + 1,
            "name": c["name"],
            "input": c["input"],
            "expected": c["expected"],
            "is_sample": c["is_sample"],
            "score": 0 if c["is_sample"] else 10,
        }
        for i, c in enumerate(raw)
    ]


# ---------------------------------------------------------------------------
# 1. 最大子段和
# ---------------------------------------------------------------------------


def _max_subarray_gen(rng: random.Random):
    def solve(n, a):
        best = cur = a[0]
        for x in a[1:]:
            cur = max(x, cur + x)
            best = max(best, cur)
        return best

    samples, hidden = [], []
    for i in range(2):
        n = rng.randint(3, 6)
        a = [rng.randint(-9, 9) for _ in range(n)]
        samples.append((f"{n}\n{_fmt_list(a)}\n", f"{solve(n, a)}\n"))
    for i in range(6):
        n = rng.randint(1, 8) if i < 2 else rng.randint(2000, 8000)
        a = [rng.randint(-30, 30) for _ in range(n)]
        hidden.append((f"{n}\n{_fmt_list(a)}\n", f"{solve(n, a)}\n"))
    hidden.append(("1\n-7\n", "-7\n"))
    # 大规模测试点：O(n²) 暴力实现会超时，用来区分复杂度是否达标
    for n in (200000,):
        a = [rng.randint(-10000, 10000) for _ in range(n)]
        hidden.append((f"{n}\n{_fmt_list(a)}\n", f"{solve(n, a)}\n"))
    return _cases(samples, hidden)


# ---------------------------------------------------------------------------
# 2. 逆序对计数
# ---------------------------------------------------------------------------


def _inversions_gen(rng: random.Random):
    def solve(a):
        cnt = 0
        buf = [0] * len(a)

        def ms(lo, hi):
            nonlocal cnt
            if hi - lo <= 1:
                return
            mid = (lo + hi) // 2
            ms(lo, mid)
            ms(mid, hi)
            i, j, k = lo, mid, lo
            while i < mid and j < hi:
                if a[i] <= a[j]:
                    buf[k] = a[i]
                    i += 1
                else:
                    buf[k] = a[j]
                    j += 1
                    cnt += mid - i
                k += 1
            while i < mid:
                buf[k] = a[i]
                i += 1
                k += 1
            while j < hi:
                buf[k] = a[j]
                j += 1
                k += 1
            a[lo:hi] = buf[lo:hi]

        ms(0, len(a))
        return cnt

    samples, hidden = [], []
    for _ in range(2):
        n = rng.randint(3, 6)
        a = [rng.randint(1, 9) for _ in range(n)]
        samples.append((f"{n}\n{_fmt_list(a)}\n", f"{solve(a[:])}\n"))
    for i in range(6):
        n = rng.randint(1, 10) if i < 2 else rng.randint(500, 2000)
        a = [rng.randint(1, 50) for _ in range(n)]
        hidden.append((f"{n}\n{_fmt_list(a)}\n", f"{solve(a[:])}\n"))
    n = 8
    a = list(range(n, 0, -1))
    hidden.append((f"{n}\n{_fmt_list(a)}\n", f"{solve(a[:])}\n"))
    for n in (120000,):
        a = [rng.randint(1, 10**9) for _ in range(n)]
        hidden.append((f"{n}\n{_fmt_list(a)}\n", f"{solve(a[:])}\n"))
    return _cases(samples, hidden)


# ---------------------------------------------------------------------------
# 3. 活动安排
# ---------------------------------------------------------------------------


def _activity_gen(rng: random.Random):
    def solve(items):
        items = sorted(items, key=lambda x: x[1])
        cnt, last = 0, -1
        for s, e in items:
            if s >= last:
                cnt += 1
                last = e
        return cnt

    def make(n, span):
        items = []
        for _ in range(n):
            s = rng.randint(0, span)
            e = s + rng.randint(1, max(1, span // 3))
            items.append((s, e))
        return items

    samples, hidden = [], []
    for _ in range(2):
        items = make(rng.randint(3, 5), 10)
        body = "\n".join(f"{s} {e}" for s, e in items)
        samples.append((f"{len(items)}\n{body}\n", f"{solve(items)}\n"))
    for i in range(6):
        items = make(rng.randint(1, 8) if i < 2 else rng.randint(200, 900), 200000)
        body = "\n".join(f"{s} {e}" for s, e in items)
        hidden.append((f"{len(items)}\n{body}\n", f"{solve(items)}\n"))
    items = make(3000, 10**6)
    body = "\n".join(f"{s} {e}" for s, e in items)
    hidden.append((f"{len(items)}\n{body}\n", f"{solve(items)}\n"))
    return _cases(samples, hidden)


# ---------------------------------------------------------------------------
# 4. 0/1 背包
# ---------------------------------------------------------------------------


def _knapsack_gen(rng: random.Random):
    def solve(W, items):
        dp = [0] * (W + 1)
        for w, v in items:
            for c in range(W, w - 1, -1):
                dp[c] = max(dp[c], dp[c - w] + v)
        return dp[W]

    samples, hidden = [], []
    for _ in range(2):
        n, W = rng.randint(2, 4), rng.randint(5, 12)
        items = [(rng.randint(1, 5), rng.randint(1, 10)) for _ in range(n)]
        body = "\n".join(f"{w} {v}" for w, v in items)
        samples.append((f"{n} {W}\n{body}\n", f"{solve(W, items)}\n"))
    for i in range(6):
        n = rng.randint(1, 5) if i < 2 else rng.randint(30, 40)
        W = rng.randint(10, 30) if i < 2 else rng.randint(200, 250)
        items = [(rng.randint(1, W), rng.randint(1, 100)) for _ in range(n)]
        body = "\n".join(f"{w} {v}" for w, v in items)
        hidden.append((f"{n} {W}\n{body}\n", f"{solve(W, items)}\n"))
    n, W = 40, 250
    items = [(rng.randint(1, W), rng.randint(1, 100)) for _ in range(n)]
    body = "\n".join(f"{w} {v}" for w, v in items)
    hidden.append((f"{n} {W}\n{body}\n", f"{solve(W, items)}\n"))
    return _cases(samples, hidden)


# ---------------------------------------------------------------------------
# 5. 最长公共子序列
# ---------------------------------------------------------------------------


def _lcs_gen(rng: random.Random):
    def solve(a, b):
        dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
        for i in range(1, len(a) + 1):
            for j in range(1, len(b) + 1):
                dp[i][j] = dp[i - 1][j - 1] + 1 if a[i - 1] == b[j - 1] else max(
                    dp[i - 1][j], dp[i][j - 1]
                )
        return dp[len(a)][len(b)]

    alpha = "abcde"
    samples, hidden = [], []
    for _ in range(2):
        a = "".join(rng.choice(alpha) for _ in range(rng.randint(3, 6)))
        b = "".join(rng.choice(alpha) for _ in range(rng.randint(3, 6)))
        samples.append((f"{a}\n{b}\n", f"{solve(a, b)}\n"))
    for i in range(6):
        L = rng.randint(1, 6) if i < 2 else rng.randint(200, 800)
        a = "".join(rng.choice(alpha) for _ in range(L))
        b = "".join(rng.choice(alpha) for _ in range(L))
        hidden.append((f"{a}\n{b}\n", f"{solve(a, b)}\n"))
    for L in (1500, 3000):
        a = "".join(rng.choice(alpha) for _ in range(L))
        b = "".join(rng.choice(alpha) for _ in range(L))
        hidden.append((f"{a}\n{b}\n", f"{solve(a, b)}\n"))
    return _cases(samples, hidden)


# ---------------------------------------------------------------------------
# 6. 迷宫最短路（BFS）
# ---------------------------------------------------------------------------


def _maze_gen(rng: random.Random):
    def solve(g, sx, sy, tx, ty):
        R, C = len(g), len(g[0])
        from collections import deque

        if g[sx][sy] == "#" or g[tx][ty] == "#":
            return -1
        dist = [[-1] * C for _ in range(R)]
        dist[sx][sy] = 0
        dq = deque([(sx, sy)])
        while dq:
            x, y = dq.popleft()
            if (x, y) == (tx, ty):
                return dist[x][y]
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < R and 0 <= ny < C and g[nx][ny] == "." and dist[nx][ny] < 0:
                    dist[nx][ny] = dist[x][y] + 1
                    dq.append((nx, ny))
        return -1

    def make(R, C, wall):
        g = [["." if rng.random() > wall else "#" for _ in range(C)] for _ in range(R)]
        g[0][0] = "."
        g[R - 1][C - 1] = "."
        return g

    def pack(g):
        R, C = len(g), len(g[0])
        body = "\n".join("".join(row) for row in g)
        return f"{R} {C}\n0 0\n{R - 1} {C - 1}\n{body}\n", solve(g, 0, 0, R - 1, C - 1)

    samples, hidden = [], []
    for _ in range(2):
        g = make(rng.randint(3, 4), rng.randint(3, 4), 0.2)
        s, v = pack(g)
        samples.append((s, f"{v}\n"))
    for i in range(6):
        g = make(rng.randint(2, 4), rng.randint(2, 4), 0.25) if i < 2 else make(
            rng.randint(40, 90), rng.randint(40, 90), 0.22
        )
        s, v = pack(g)
        hidden.append((s, f"{v}\n"))
    s, v = pack(make(200, 200, 0.10))
    hidden.append((s, f"{v}\n"))
    return _cases(samples, hidden)


# ---------------------------------------------------------------------------
# 7. 单源最短路（Dijkstra）
# ---------------------------------------------------------------------------


def _dijkstra_gen(rng: random.Random):
    def solve(n, adj):
        INF = float("inf")
        dist = [INF] * (n + 1)
        dist[1] = 0
        pq = [(0, 1)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue
            for v, w in adj[u]:
                if d + w < dist[v]:
                    dist[v] = d + w
                    heapq.heappush(pq, (dist[v], v))
        return dist

    def make(n, m, maxw):
        edges, adj = [], [[] for _ in range(n + 1)]
        for _ in range(m):
            u = rng.randint(1, n)
            v = rng.randint(1, n)
            if u == v:
                continue
            w = rng.randint(1, maxw)
            edges.append((u, v, w))
            adj[u].append((v, w))
            adj[v].append((u, w))
        return edges, adj

    def pack(n, edges, dist):
        body = "\n".join(f"{u} {v} {w}" for u, v, w in edges)
        inp = f"{n} {len(edges)}\n{body}\n"
        out = " ".join("-1" if dist[i] == float("inf") else str(dist[i]) for i in range(1, n + 1))
        return inp, out + "\n"

    samples, hidden = [], []
    for _ in range(2):
        n = rng.randint(3, 5)
        edges, adj = make(n, rng.randint(3, 6), 10)
        inp, out = pack(n, edges, solve(n, adj))
        samples.append((inp, out))
    for i in range(6):
        n = rng.randint(2, 5) if i < 2 else rng.randint(300, 1200)
        edges, adj = make(n, rng.randint(n, n * 3), 1000)
        inp, out = pack(n, edges, solve(n, adj))
        hidden.append((inp, out))
    n = 4000
    edges, adj = make(n, n * 3, 1000)
    inp, out = pack(n, edges, solve(n, adj))
    hidden.append((inp, out))
    return _cases(samples, hidden)


# ---------------------------------------------------------------------------
# 8. 连通块计数（并查集）
# ---------------------------------------------------------------------------


def _dsu_gen(rng: random.Random):
    def solve(n, edges):
        p = list(range(n + 1))

        def find(x):
            while p[x] != x:
                p[x] = p[p[x]]
                x = p[x]
            return x

        for u, v in edges:
            ru, rv = find(u), find(v)
            if ru != rv:
                p[rv] = ru
        return len({find(i) for i in range(1, n + 1)})

    samples, hidden = [], []
    for _ in range(2):
        n = rng.randint(3, 6)
        edges = [(rng.randint(1, n), rng.randint(1, n)) for _ in range(rng.randint(1, 5))]
        body = "\n".join(f"{u} {v}" for u, v in edges)
        samples.append((f"{n} {len(edges)}\n{body}\n", f"{solve(n, edges)}\n"))
    for i in range(6):
        n = rng.randint(2, 6) if i < 2 else rng.randint(20000, 60000)
        m = rng.randint(1, n * 2)
        edges = [(rng.randint(1, n), rng.randint(1, n)) for _ in range(m)]
        body = "\n".join(f"{u} {v}" for u, v in edges)
        hidden.append((f"{n} {len(edges)}\n{body}\n", f"{solve(n, edges)}\n"))
    n = 100000
    m = 200000
    edges = [(rng.randint(1, n), rng.randint(1, n)) for _ in range(m)]
    body = "\n".join(f"{u} {v}" for u, v in edges)
    hidden.append((f"{n} {m}\n{body}\n", f"{solve(n, edges)}\n"))
    return _cases(samples, hidden)


# ---------------------------------------------------------------------------
# 9. KMP 匹配计数
# ---------------------------------------------------------------------------


def _kmp_gen(rng: random.Random):
    def solve(s, p):
        if not p:
            return 0
        pi = [0] * len(p)
        k = 0
        for i in range(1, len(p)):
            while k and p[i] != p[k]:
                k = pi[k - 1]
            if p[i] == p[k]:
                k += 1
            pi[i] = k
        cnt, k = 0, 0
        for ch in s:
            while k and ch != p[k]:
                k = pi[k - 1]
            if ch == p[k]:
                k += 1
            if k == len(p):
                cnt += 1
                k = pi[k - 1]
        return cnt

    alpha = "ab"
    samples, hidden = [], []
    for _ in range(2):
        s = "".join(rng.choice(alpha) for _ in range(rng.randint(4, 10)))
        p = "".join(rng.choice(alpha) for _ in range(rng.randint(1, 3)))
        samples.append((f"{s}\n{p}\n", f"{solve(s, p)}\n"))
    for i in range(6):
        L = rng.randint(3, 8) if i < 2 else rng.randint(20000, 80000)
        s = "".join(rng.choice(alpha) for _ in range(L))
        pl = rng.randint(1, 3) if i < 2 else rng.randint(3, 12)
        p = "".join(rng.choice(alpha) for _ in range(pl))
        hidden.append((f"{s}\n{p}\n", f"{solve(s, p)}\n"))
    hidden.append(("aaaaa\naa\n", "4\n"))
    # 全 a 串是 KMP 最坏情况：暴力匹配退化为 O(|s|·|p|)
    for L, PL in ((200000, 3000), (400000, 5000)):
        s = "a" * L
        p = "a" * PL
        hidden.append((f"{s}\n{p}\n", f"{solve(s, p)}\n"))
    return _cases(samples, hidden)


# ---------------------------------------------------------------------------
# 10. 木棍切割（二分答案）
# ---------------------------------------------------------------------------


def _cut_gen(rng: random.Random):
    def solve(sticks, m):
        lo, hi = 1, max(sticks)
        ans = 0
        while lo <= hi:
            mid = (lo + hi) // 2
            if sum(x // mid for x in sticks) >= m:
                ans = mid
                lo = mid + 1
            else:
                hi = mid - 1
        return ans

    samples, hidden = [], []
    for _ in range(2):
        n = rng.randint(2, 4)
        sticks = [rng.randint(5, 20) for _ in range(n)]
        m = rng.randint(1, 6)
        samples.append((f"{n} {m}\n{_fmt_list(sticks)}\n", f"{solve(sticks, m)}\n"))
    for i in range(6):
        n = rng.randint(1, 4) if i < 2 else rng.randint(200, 900)
        sticks = [rng.randint(1, 100) if i < 2 else rng.randint(50, 10000) for _ in range(n)]
        m = rng.randint(1, 10) if i < 2 else rng.randint(10, 5000)
        hidden.append((f"{n} {m}\n{_fmt_list(sticks)}\n", f"{solve(sticks, m)}\n"))
    hidden.append(("1 10\n50\n", "5\n"))
    n = 100000
    sticks = [rng.randint(1, 10000) for _ in range(n)]
    hidden.append((f"{n} 1000000\n{_fmt_list(sticks)}\n", f"{solve(sticks, 10**6)}\n"))
    return _cases(samples, hidden)


# ---------------------------------------------------------------------------
# 11. 拓扑排序（Chapter 2：图的搜索）
# ---------------------------------------------------------------------------


def _topo_gen(rng: random.Random):
    def solve(n, edges):
        adj = [[] for _ in range(n + 1)]
        indeg = [0] * (n + 1)
        for u, v in edges:
            adj[u].append(v)
            indeg[v] += 1
        heap = [i for i in range(1, n + 1) if indeg[i] == 0]
        heapq.heapify(heap)
        order = []
        while heap:
            u = heapq.heappop(heap)
            order.append(u)
            for v in adj[u]:
                indeg[v] -= 1
                if indeg[v] == 0:
                    heapq.heappush(heap, v)
        return order if len(order) == n else None

    def make_dag(n, m, lo, hi):
        perm = list(range(1, n + 1))
        rng.shuffle(perm)
        seen, edges = set(), []
        while len(edges) < m:
            i = rng.randint(0, n - 1)
            j = rng.randint(0, n - 1)
            if i >= j:
                continue
            key = (perm[i], perm[j])
            if key in seen:
                continue
            seen.add(key)
            edges.append(key)
        return edges

    def fmt(n, edges):
        return f"{n} {len(edges)}\n" + "".join(f"{u} {v}\n" for u, v in edges)

    def expect(n, edges):
        o = solve(n, edges)
        return "-1\n" if o is None else _fmt_list(o) + "\n"

    samples, hidden = [], []
    for _ in range(2):
        n = rng.randint(3, 5)
        e = make_dag(n, min(rng.randint(2, 5), n * (n - 1) // 2), 1, n)
        samples.append((fmt(n, e), expect(n, e)))
    # 边界：没有边、单点、自环、环
    hidden.append((fmt(1, []), expect(1, [])))
    hidden.append((fmt(5, []), expect(5, [])))
    hidden.append((fmt(3, [(1, 2), (2, 3), (3, 1)]), "-1\n"))
    hidden.append((fmt(2, [(1, 1)]), "-1\n"))
    for n, m in ((8, 12), (60, 90), (2000, 5000)):
        e = make_dag(n, m, 1, n)
        hidden.append((fmt(n, e), expect(n, e)))
    # 大规模：边全部由小编号指向大编号，保证是 DAG；
    # 「每轮线性扫描最小入度点」的 O(n²) 实现会超时
    n, m = 100000, 200000
    e = [(i, i + 1) for i in range(1, n)]
    seen = set(e)
    while len(e) < m:
        u = rng.randint(1, n - 1)
        v = rng.randint(u + 1, n)
        if (u, v) in seen:
            continue
        seen.add((u, v))
        e.append((u, v))
    hidden.append((fmt(n, e), expect(n, e)))
    return _cases(samples, hidden)


# ---------------------------------------------------------------------------
# 12. 区间分割：最少教室数（Chapter 3：贪心）
# ---------------------------------------------------------------------------


def _partition_gen(rng: random.Random):
    def solve(iv):
        events = []
        for s, f in iv:
            events.append((s, 1))
            events.append((f, -1))
        events.sort(key=lambda e: (e[0], e[1]))
        cur = best = 0
        for _, d in events:
            cur += d
            best = max(best, cur)
        return best

    def fmt(iv):
        return f"{len(iv)}\n" + "".join(f"{s} {f}\n" for s, f in iv)

    samples, hidden = [], []
    for _ in range(2):
        n = rng.randint(2, 5)
        iv = []
        for _ in range(n):
            s = rng.randint(1, 12)
            iv.append((s, s + rng.randint(1, 4)))
        samples.append((fmt(iv), f"{solve(iv)}\n"))
    # 边界：首尾相接的区间不需要新教室
    hidden.append(("3\n1 3\n3 5\n5 7\n", "1\n"))
    hidden.append(("3\n1 5\n2 3\n3 6\n", "2\n"))
    hidden.append(("1\n7 9\n", "1\n"))
    hidden.append((fmt([(0, 1)] * 4), "4\n"))
    for n in (20, 200, 3000):
        iv = []
        for _ in range(n):
            s = rng.randint(0, 10000)
            iv.append((s, s + rng.randint(1, 500)))
        hidden.append((fmt(iv), f"{solve(iv)}\n"))
    n = 100000
    iv = []
    for _ in range(n):
        s = rng.randint(0, 10 ** 7)
        iv.append((s, s + rng.randint(1, 10 ** 5)))
    hidden.append((fmt(iv), f"{solve(iv)}\n"))
    return _cases(samples, hidden)


# ---------------------------------------------------------------------------
# 13. 最小化最大延迟（Chapter 3：贪心）
# ---------------------------------------------------------------------------


def _lateness_gen(rng: random.Random):
    def solve(jobs):
        cur = 0
        worst = -10 ** 18
        for t, d in sorted(jobs, key=lambda j: j[1]):
            cur += t
            worst = max(worst, cur - d)
        return worst

    def fmt(jobs):
        return f"{len(jobs)}\n" + "".join(f"{t} {d}\n" for t, d in jobs)

    samples, hidden = [], []
    for _ in range(2):
        n = rng.randint(2, 5)
        jobs = [(rng.randint(1, 6), rng.randint(1, 25)) for _ in range(n)]
        samples.append((fmt(jobs), f"{solve(jobs)}\n"))
    hidden.append(("1\n5 5\n", "0\n"))
    hidden.append(("2\n3 1\n3 2\n", "4\n"))
    hidden.append(("2\n1 100\n1 100\n", "-98\n"))
    for n in (8, 60, 1000):
        jobs = [(rng.randint(1, 50), rng.randint(1, 4000)) for _ in range(n)]
        hidden.append((fmt(jobs), f"{solve(jobs)}\n"))
    # 大规模：O(n²) 的「每次扫描找最早截止期」实现会超时
    n = 100000
    jobs = [(rng.randint(1, 1000), rng.randint(1, 10 ** 8)) for _ in range(n)]
    hidden.append((fmt(jobs), f"{solve(jobs)}\n"))
    return _cases(samples, hidden)


# ---------------------------------------------------------------------------
# 14. 最近点对（Chapter 4：分治）
# ---------------------------------------------------------------------------


def _closest_gen(rng: random.Random):
    def closest_sq(pts):
        px = sorted(pts)

        def dist2(a, b):
            return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2

        def rec(lo, hi):
            if hi - lo <= 3:
                best = None
                for i in range(lo, hi):
                    for j in range(i + 1, hi):
                        d = dist2(px[i], px[j])
                        if best is None or d < best:
                            best = d
                return best if best is not None else 10 ** 18
            mid = (lo + hi) // 2
            midx = px[mid][0]
            d = min(rec(lo, mid), rec(mid, hi))
            strip = [p for p in px[lo:hi] if (p[0] - midx) ** 2 < d]
            strip.sort(key=lambda p: p[1])
            for i in range(len(strip)):
                for j in range(i + 1, len(strip)):
                    if (strip[j][1] - strip[i][1]) ** 2 >= d:
                        break
                    dd = dist2(strip[i], strip[j])
                    if dd < d:
                        d = dd
            return d

        return rec(0, len(px))

    def fmt(pts):
        return f"{len(pts)}\n" + "".join(f"{x} {y}\n" for x, y in pts)

    samples, hidden = [], []
    for _ in range(2):
        pts = [(rng.randint(0, 20), rng.randint(0, 20)) for _ in range(rng.randint(2, 6))]
        samples.append((fmt(pts), f"{closest_sq(pts)}\n"))
    hidden.append(("2\n0 0\n3 4\n", "25\n"))
    hidden.append(("2\n1000000 -1000000\n-1000000 1000000\n", "8000000000000\n"))
    hidden.append(("4\n0 0\n0 1000000\n1000000 0\n1000000 1000000\n", "1000000000000\n"))
    for n in (50, 800, 4000):
        pts = [(rng.randint(0, 10 ** 6), rng.randint(0, 10 ** 6)) for _ in range(n)]
        hidden.append((fmt(pts), f"{closest_sq(pts)}\n"))
    # 大规模：暴力 O(n²) 会超时，分治 O(n log n) 秒过
    n = 120000
    pts = [(rng.randint(0, 10 ** 7), rng.randint(0, 10 ** 7)) for _ in range(n)]
    hidden.append((fmt(pts), f"{closest_sq(pts)}\n"))
    return _cases(samples, hidden)


# ---------------------------------------------------------------------------
# 15. 编辑距离 / 序列对齐（Chapter 5：动态规划）
# ---------------------------------------------------------------------------


def _edit_gen(rng: random.Random):
    def solve(a, b):
        m = len(b)
        dp = list(range(m + 1))
        for i, ca in enumerate(a, 1):
            prev, dp[0] = dp[0], i
            for j, cb in enumerate(b, 1):
                cur = dp[j]
                dp[j] = prev if ca == cb else 1 + min(prev, dp[j], dp[j - 1])
                prev = cur
        return dp[m]

    alpha = "abc"
    samples, hidden = [], []
    for _ in range(2):
        a = "".join(rng.choice(alpha) for _ in range(rng.randint(1, 6)))
        b = "".join(rng.choice(alpha) for _ in range(rng.randint(1, 6)))
        samples.append((f"{a}\n{b}\n", f"{solve(a, b)}\n"))
    hidden.append(("kitten\nsitting\n", "3\n"))
    hidden.append(("abc\nabc\n", "0\n"))
    hidden.append(("abc\nxyz\n", "3\n"))
    hidden.append(("algorithm\nlogarithm\n", "3\n"))
    for L in (20, 200, 400):
        a = "".join(rng.choice(alpha) for _ in range(L))
        b = "".join(rng.choice(alpha) for _ in range(L))
        hidden.append((f"{a}\n{b}\n", f"{solve(a, b)}\n"))
    # 大规模：规模 400 时朴素递归（不记记忆化）会呈指数级超时
    a = "".join(rng.choice("abcd") for _ in range(400))
    b = "".join(rng.choice("abcd") for _ in range(400))
    hidden.append((f"{a}\n{b}\n", f"{solve(a, b)}\n"))
    return _cases(samples, hidden)


# ---------------------------------------------------------------------------
# 16. Kruskal 最小生成树（Chapter 7：并查集）
# ---------------------------------------------------------------------------


def _mst_gen(rng: random.Random):
    def solve(n, edges):
        p = list(range(n + 1))

        def find(x):
            while p[x] != x:
                p[x] = p[p[x]]
                x = p[x]
            return x

        total, used = 0, 0
        for w, u, v in sorted((w, u, v) for u, v, w in edges):
            ru, rv = find(u), find(v)
            if ru == rv:
                continue
            p[rv] = ru
            total += w
            used += 1
            if used == n - 1:
                break
        return total if used == n - 1 else None

    def fmt(n, edges):
        return f"{n} {len(edges)}\n" + "".join(f"{u} {v} {w}\n" for u, v, w in edges)

    def expect(n, edges):
        t = solve(n, edges)
        return "-1\n" if t is None else f"{t}\n"

    def connected_edges(n, m, wmax):
        edges = [(i, i + 1, rng.randint(0, wmax)) for i in range(1, n)]
        seen = {(u, v) for u, v, _ in edges}
        while len(edges) < m:
            u = rng.randint(1, n)
            v = rng.randint(1, n)
            if u == v:
                continue
            key = (min(u, v), max(u, v))
            if key in seen:
                continue
            seen.add(key)
            edges.append((key[0], key[1], rng.randint(0, wmax)))
        return edges

    samples, hidden = [], []
    for _ in range(2):
        n = rng.randint(3, 5)
        e = connected_edges(n, rng.randint(n - 1, n + 2), 20)
        samples.append((fmt(n, e), expect(n, e)))
    hidden.append((fmt(1, []), "0\n"))
    hidden.append((fmt(3, [(1, 2, 5), (2, 3, 7)]), "12\n"))
    hidden.append(("3 1\n2 3 4\n", "-1\n"))  # 1 号点孤立
    hidden.append((fmt(4, [(1, 2, 1)] * 3 + [(3, 4, 1)]), "-1\n"))  # 两个连通块
    for n in (10, 300, 2000):
        e = connected_edges(n, min(n * 2, n * (n - 1) // 2), 10 ** 6)
        hidden.append((fmt(n, e), expect(n, e)))
    n, m = 100000, 200000
    e = connected_edges(n, m, 10 ** 9)
    hidden.append((fmt(n, e), expect(n, e)))
    return _cases(samples, hidden)


# ---------------------------------------------------------------------------
# 17. 线段树：区间加 + 区间求和（Chapter 8：线段树）
# ---------------------------------------------------------------------------


def _segtree_gen(rng: random.Random):
    def solve(a, ops):
        n = len(a) - 1
        tree = [0] * (4 * n + 4)
        lazy = [0] * (4 * n + 4)

        def build(node, lo, hi):
            if lo == hi:
                tree[node] = a[lo]
                return
            mid = (lo + hi) // 2
            build(node * 2, lo, mid)
            build(node * 2 + 1, mid + 1, hi)
            tree[node] = tree[node * 2] + tree[node * 2 + 1]

        def apply(node, lo, hi, v):
            tree[node] += v * (hi - lo + 1)
            lazy[node] += v

        def push(node, lo, hi):
            if not lazy[node] or lo == hi:
                return
            mid = (lo + hi) // 2
            apply(node * 2, lo, mid, lazy[node])
            apply(node * 2 + 1, mid + 1, hi, lazy[node])
            lazy[node] = 0

        def update(node, lo, hi, l, r, v):
            if r < lo or hi < l:
                return
            if l <= lo and hi <= r:
                apply(node, lo, hi, v)
                return
            push(node, lo, hi)
            mid = (lo + hi) // 2
            update(node * 2, lo, mid, l, r, v)
            update(node * 2 + 1, mid + 1, hi, l, r, v)
            tree[node] = tree[node * 2] + tree[node * 2 + 1]

        def query(node, lo, hi, l, r):
            if r < lo or hi < l:
                return 0
            if l <= lo and hi <= r:
                return tree[node]
            push(node, lo, hi)
            mid = (lo + hi) // 2
            return query(node * 2, lo, mid, l, r) + query(node * 2 + 1, mid + 1, hi, l, r)

        build(1, 1, n)
        out = []
        for op in ops:
            if op[0] == 1:
                update(1, 1, n, op[1], op[2], op[3])
            else:
                out.append(query(1, 1, n, op[1], op[2]))
        return out

    def fmt(a, ops):
        return (
            f"{len(a) - 1} {len(ops)}\n"
            + _fmt_list(a[1:]) + "\n"
            + "".join(" ".join(str(x) for x in op) + "\n" for op in ops)
        )

    samples, hidden = [], []
    for _ in range(2):
        n, q = rng.randint(2, 5), rng.randint(2, 4)
        a = [0] + [rng.randint(1, 9) for _ in range(n)]
        ops = []
        for _ in range(q):
            l = rng.randint(1, n)
            r = rng.randint(l, n)
            if rng.random() < 0.5:
                ops.append((1, l, r, rng.randint(-5, 5)))
            else:
                ops.append((2, l, r))
        if not any(o[0] == 2 for o in ops):
            ops.append((2, 1, n))
        samples.append((fmt(a, ops), "".join(f"{x}\n" for x in solve(a, ops))))
    hidden.append(("1 3\n5\n1 1 1 4\n2 1 1\n2 1 1\n", "9\n9\n"))
    hidden.append(("3 3\n1 2 3\n1 1 3 1\n2 1 3\n2 2 2\n", "9\n3\n"))
    hidden.append(("4 2\n0 0 0 0\n2 1 4\n1 2 3 -7\n", "0\n"))
    for n, q in ((20, 40), (500, 800), (4000, 4000)):
        a = [0] + [rng.randint(-50, 50) for _ in range(n)]
        ops = []
        for _ in range(q):
            l = rng.randint(1, n)
            r = rng.randint(l, n)
            if rng.random() < 0.5:
                ops.append((1, l, r, rng.randint(-100, 100)))
            else:
                ops.append((2, l, r))
        hidden.append((fmt(a, ops), "".join(f"{x}\n" for x in solve(a, ops))))
    # 大规模：20 万次操作、区间长度接近全长，逐元素处理的 O(n) 做法会超时
    # （线段树 O(log n) 轻松通过）。查询占比压到 15%，避免期望输出超过 1 MB。
    n, q = 200000, 200000
    a = [0] + [rng.randint(-1000, 1000) for _ in range(n)]
    ops = []
    for _ in range(q):
        l = rng.randint(1, n)
        r = rng.randint(l, n)
        if rng.random() < 0.85:
            ops.append((1, l, r, rng.randint(-1000, 1000)))
        else:
            ops.append((2, l, r))
    hidden.append((fmt(a, ops), "".join(f"{x}\n" for x in solve(a, ops))))
    return _cases(samples, hidden)


# ---------------------------------------------------------------------------
# 18. 树状数组（Chapter 9：树状数组）
# ---------------------------------------------------------------------------


def _bit_gen(rng: random.Random):
    def solve(a, ops):
        n = len(a) - 1
        bit = [0] * (n + 1)
        for i in range(1, n + 1):
            bit[i] += a[i]
            j = i + (i & -i)
            if j <= n:
                bit[j] += bit[i]

        def add(i, v):
            while i <= n:
                bit[i] += v
                i += i & -i

        def pre(i):
            s = 0
            while i > 0:
                s += bit[i]
                i -= i & -i
            return s

        out = []
        for op in ops:
            if op[0] == 1:
                add(op[1], op[2])
            else:
                out.append(pre(op[2]) - pre(op[1] - 1))
        return out

    def fmt(a, ops):
        return (
            f"{len(a) - 1} {len(ops)}\n"
            + _fmt_list(a[1:]) + "\n"
            + "".join(" ".join(str(x) for x in op) + "\n" for op in ops)
        )

    samples, hidden = [], []
    for _ in range(2):
        n, q = rng.randint(2, 6), rng.randint(2, 4)
        a = [0] + [rng.randint(1, 20) for _ in range(n)]
        ops = []
        for _ in range(q):
            if rng.random() < 0.5:
                ops.append((1, rng.randint(1, n), rng.randint(-10, 10)))
            else:
                l = rng.randint(1, n)
                ops.append((2, l, rng.randint(l, n)))
        if not any(o[0] == 2 for o in ops):
            ops.append((2, 1, n))
        samples.append((fmt(a, ops), "".join(f"{x}\n" for x in solve(a, ops))))
    hidden.append(("1 2\n7\n1 1 3\n2 1 1\n", "10\n"))
    hidden.append(("2 3\n5 5\n2 1 2\n1 2 -5\n2 1 2\n", "10\n5\n"))
    hidden.append(("5 2\n-3 4 0 9 -2\n2 1 5\n2 3 3\n", "8\n0\n"))
    for n, q in ((30, 60), (600, 900), (5000, 5000)):
        a = [0] + [rng.randint(-100, 100) for _ in range(n)]
        ops = []
        for _ in range(q):
            if rng.random() < 0.5:
                ops.append((1, rng.randint(1, n), rng.randint(-100, 100)))
            else:
                l = rng.randint(1, n)
                ops.append((2, l, rng.randint(l, n)))
        hidden.append((fmt(a, ops), "".join(f"{x}\n" for x in solve(a, ops))))
    # 大规模：单次查询退化成 O(n) 会超时（树状数组 O(log n)）。
    # 数值范围取小，避免 8 万行输出超过 1 MB。
    n, q = 200000, 200000
    a = [0] + [rng.randint(-50, 50) for _ in range(n)]
    ops = []
    for _ in range(q):
        if rng.random() < 0.6:
            ops.append((1, rng.randint(1, n), rng.randint(-50, 50)))
        else:
            l = rng.randint(1, n)
            ops.append((2, l, rng.randint(l, n)))
    hidden.append((fmt(a, ops), "".join(f"{x}\n" for x in solve(a, ops))))
    return _cases(samples, hidden)


# ---------------------------------------------------------------------------
# 19. 最大流（Chapter 6：网络流）
# ---------------------------------------------------------------------------


def _maxflow_gen(rng: random.Random):
    def solve(n, s, t, edges):
        graph = [[] for _ in range(n + 1)]
        for u, v, c in edges:
            graph[u].append([v, c, len(graph[v])])
            graph[v].append([u, 0, len(graph[u]) - 1])
        flow = 0
        while True:
            level = [-1] * (n + 1)
            level[s] = 0
            queue = [s]
            for u in queue:
                for e in graph[u]:
                    if e[1] > 0 and level[e[0]] < 0:
                        level[e[0]] = level[u] + 1
                        queue.append(e[0])
            if level[t] < 0:
                return flow
            it = [0] * (n + 1)
            while True:
                pushed = [0]

                def dfs(u, limit):
                    if u == t:
                        return limit
                    while it[u] < len(graph[u]):
                        e = graph[u][it[u]]
                        v = e[0]
                        if e[1] > 0 and level[v] == level[u] + 1:
                            d = dfs(v, min(limit, e[1]))
                            if d > 0:
                                e[1] -= d
                                graph[v][e[2]][1] += d
                                return d
                        it[u] += 1
                    return 0

                f = dfs(s, 10 ** 18)
                if f == 0:
                    break
                flow += f

    def fmt(n, s, t, edges):
        return f"{n} {len(edges)} {s} {t}\n" + "".join(
            f"{u} {v} {c}\n" for u, v, c in edges
        )

    samples, hidden = [], []
    for _ in range(2):
        n = rng.randint(3, 5)
        s, t = 1, n
        edges = []
        for u in range(1, n + 1):
            for v in range(1, n + 1):
                if u != v and rng.random() < 0.45:
                    edges.append((u, v, rng.randint(1, 12)))
        samples.append((fmt(n, s, t, edges), f"{solve(n, s, t, edges)}\n"))
    hidden.append(("2 1 1 2\n1 2 7\n", "7\n"))
    hidden.append(("3 3 1 3\n1 2 5\n2 3 5\n1 3 1\n", "6\n"))
    hidden.append(("4 4 1 4\n1 2 1\n1 3 1\n2 4 1\n3 4 1\n", "2\n"))
    hidden.append(("3 1 1 3\n1 2 10\n", "0\n"))
    # 需要退流（反向边）才能取到最优解的经典结构
    hidden.append(
        ("4 5 1 4\n1 2 1\n1 3 1\n2 3 1\n2 4 1\n3 4 1\n", "2\n")
    )
    for n, m in ((6, 12), (20, 60), (60, 200)):
        s, t = 1, n
        edges = []
        for _ in range(m):
            u = rng.randint(1, n - 1)
            v = rng.randint(u + 1, n)
            edges.append((u, v, rng.randint(1, 1000)))
        hidden.append((fmt(n, s, t, edges), f"{solve(n, s, t, edges)}\n"))
    # 大规模一：随机稠密图
    n, m = 200, 1200
    s, t = 1, n
    edges = []
    for _ in range(m):
        u = rng.randint(1, n - 1)
        v = rng.randint(u + 1, n)
        edges.append((u, v, rng.randint(1, 10 ** 5)))
    hidden.append((fmt(n, s, t, edges), f"{solve(n, s, t, edges)}\n"))
    # 大规模二：星型结构 + 单位容量，最大流 5×10⁴；
    # 每次只推 1 个单位的朴素增广（Ford-Fulkerson / Edmonds-Karp）会超时，
    # Dinic 的分层阻塞流一个阶段就能推完
    k = 50000
    n = k + 2
    s, t = 1, 2
    edges = []
    for i in range(3, n + 1):
        edges.append((1, i, 1))
        edges.append((i, 2, 1))
    hidden.append((fmt(n, s, t, edges), f"{solve(n, s, t, edges)}\n"))
    return _cases(samples, hidden)


# ---------------------------------------------------------------------------
# C++ 模板
# ---------------------------------------------------------------------------

HDR = "#include <bits/stdc++.h>\nusing namespace std;\n\n"
CPP = {
"KADANE": {
  "ok": HDR + """int main() {
    int n;
    if(scanf("%d",&n)!=1)return 0;
    long long best=LLONG_MIN, cur=0;
    for(int i=0;i<n;i++) {
        long long x;
        scanf("%lld",&x);
        cur=(i==0)?x:max(x,cur+x);
        best=max(best,cur);
    }
    printf("%lld\\n",best);
    return 0;
}
""",
  "slow": HDR + """int main() {
    int n;
    scanf("%d",&n);
    vector<long long>a(n);
    for(int i=0;i<n;i++)scanf("%lld",&a[i]);
    long long best=LLONG_MIN;
    for(int i=0;i<n;i++) {
        long long s=0;
        for(int j=i;j<n;j++) {
            s+=a[j];
            best=max(best,s);
        }
    }
    printf("%lld\\n",best);
    return 0;
}
""",
  "bug": HDR + """int main() {
    int n;
    scanf("%d",&n);
    long long best=-1, cur=0;
    for(int i=0;i<n;i++) {
        long long x;
        scanf("%lld",&x);
        cur+=x;
        if(cur<0)cur=0;
        best=max(best,cur);
    }
    printf("%lld\\n",best);
    return 0;
}
""",
},
"INVERSION": {
  "ok": HDR + """int n, a[200005], buf[200005];
long long cnt=0;
void ms(int lo,int hi) {
    if(hi-lo<=1)return;
    int mid=(lo+hi)/2;
    ms(lo,mid);
    ms(mid,hi);
    int i=lo, j=mid, k=lo;
    while(i<mid&&j<hi) {
        if(a[i]<=a[j])buf[k++]=a[i++];
        else {
            buf[k++]=a[j++];
            cnt+=mid-i;
        }
    }
    while(i<mid)buf[k++]=a[i++];
    while(j<hi)buf[k++]=a[j++];
    for(int t=lo;t<hi;t++)a[t]=buf[t];
}

int main() {
    scanf("%d",&n);
    for(int i=0;i<n;i++)scanf("%d",&a[i]);
    ms(0,n);
    printf("%lld\\n",cnt);
    return 0;
}
""",
  "slow": HDR + """int main() {
    int n;
    scanf("%d",&n);
    vector<long long>a(n);
    for(int i=0;i<n;i++)scanf("%lld",&a[i]);
    long long c=0;
    for(int i=0;i<n;i++)for(int j=i+1;j<n;j++)if(a[i]>a[j])c++;
    printf("%lld\\n",c);
    return 0;
}
""",
  "bug": HDR + """int n, a[200005], buf[200005];
long long cnt=0;
void ms(int lo,int hi) {
    if(hi-lo<=1)return;
    int mid=(lo+hi)/2;
    ms(lo,mid);
    ms(mid,hi);
    int i=lo, j=mid, k=lo;
    while(i<mid&&j<hi) {
        if(a[i]<a[j])buf[k++]=a[i++];
        else {
            buf[k++]=a[j++];
            cnt+=mid-i;
        }
    }
    while(i<mid)buf[k++]=a[i++];
    while(j<hi)buf[k++]=a[j++];
    for(int t=lo;t<hi;t++)a[t]=buf[t];
}

int main() {
    scanf("%d",&n);
    for(int i=0;i<n;i++)scanf("%d",&a[i]);
    ms(0,n);
    printf("%lld\\n",cnt);
    return 0;
}
""",
},
"ACTIVITY": {
  "ok": HDR + """int main() {
    int n;
    scanf("%d",&n);
    vector<pair<int, int>>v(n);
    for(int i=0;i<n;i++)scanf("%d %d",&v[i].second,&v[i].first);
    sort(v.begin(),v.end());
    int c=0, last=-1;
    for(int i=0;i<n;i++)if(v[i].second>=last) {
        c++;
        last=v[i].first;
    }
    printf("%d\\n",c);
    return 0;
}
""",
  "slow": HDR + """int n, s[3000], e[3000], dp[3000];
int main() {
    scanf("%d",&n);
    for(int i=0;i<n;i++)scanf("%d %d",&s[i],&e[i]);
    // 朴素的 O(n^2) 区间动态规划：枚举「第一个活动」，不做贪心排序
    int best=0;
    for(int i=0;i<n;i++) {
        for(int j=0;j<n;j++)dp[j]=0;
        int last=e[i], cnt=1;
        for(int t=0;t<n;t++) {
            if(s[t]>=last) {
                cnt++;
                last=e[t];
            }
        }
        best=max(best,cnt);
    }
    printf("%d\\n",best);
    return 0;
}
""",
  "bug": HDR + """int main() {
    int n;
    scanf("%d",&n);
    vector<pair<int, int>>v(n);
    for(int i=0;i<n;i++)scanf("%d %d",&v[i].first,&v[i].second);
    sort(v.begin(),v.end());
    int c=0, last=-1;
    for(int i=0;i<n;i++)if(v[i].first>=last) {
        c++;
        last=v[i].second;
    }
    printf("%d\\n",c);
    return 0;
}
""",
},
"KNAPSACK": {
  "ok": HDR + """int main() {
    int n, W;
    scanf("%d %d",&n,&W);
    vector<int>dp(W+1,0);
    for(int i=0;i<n;i++) {
        int w, v;
        scanf("%d %d",&w,&v);
        for(int c=W;c>=w;c--)dp[c]=max(dp[c],dp[c-w]+v);
    }
    printf("%d\\n",dp[W]);
    return 0;
}
""",
  "slow": HDR + """int n, W, w[40], v[40];
long long best=0;
void dfs(int i,int cw,long long cv) {
    if(i==n) {
        best=max(best,cv);
        return;
    }
    dfs(i+1,cw,cv);
    if(cw+w[i]<=W)dfs(i+1,cw+w[i],cv+v[i]);
}

int main() {
    scanf("%d %d",&n,&W);
    for(int i=0;i<n;i++)scanf("%d %d",&w[i],&v[i]);
    dfs(0,0,0);
    printf("%lld\\n",best);
    return 0;
}
""",
  "bug": HDR + """int main() {
    int n, W;
    scanf("%d %d",&n,&W);
    vector<int>dp(W+1,0);
    for(int i=0;i<n;i++) {
        int w, v;
        scanf("%d %d",&w,&v);
        for(int c=w;c<=W;c++)dp[c]=max(dp[c],dp[c-w]+v);
    }
    printf("%d\\n",dp[W]);
    return 0;
}
""",
},
"LCS": {
  "ok": HDR + """int main() {
    char a[3005], b[3005];
    if(scanf("%s %s",a,b)!=2)return 0;
    int n=strlen(a), m=strlen(b);
    vector<vector<short>>dp(n+1,vector<short>(m+1,0));
    for(int i=1;i<=n;i++)for(int j=1;j<=m;j++)dp[i][j]=a[i-1]==b[j-1]?dp[i-1][j-1]+1:max(dp[i-1][j],dp[i][j-1]);
    printf("%d\\n",(int)dp[n][m]);
    return 0;
}
""",
  "slow": HDR + """char a[3005], b[3005];
int memo[200][200];
int n, m;
int f(int i,int j) {
    if(i==n||j==m)return 0;
    if(memo[i][j]>=0)return memo[i][j];
    int r=memo[i][j]=a[i]==b[j]?f(i+1,j+1)+1:max(f(i+1,j),f(i,j+1));
    return r;
}

int main() {
    scanf("%s %s",a,b);
    n=strlen(a);
    m=strlen(b);
    memset(memo,-1,sizeof memo);
    printf("%d\\n",f(0,0));
    return 0;
}
""",
  "bug": HDR + """int main() {
    char a[3005], b[3005];
    scanf("%s %s",a,b);
    int n=strlen(a), m=strlen(b);
    vector<vector<short>>dp(n+1,vector<short>(m+1,0));
    for(int i=1;i<=n;i++)for(int j=1;j<=m;j++)dp[i][j]=a[i-1]==b[j-1]?dp[i-1][j-1]+1:dp[i-1][j];
    printf("%d\\n",(int)dp[n][m]);
    return 0;
}
""",
},
"MAZE": {
  "ok": HDR + """int main() {
    int R, C;
    scanf("%d %d",&R,&C);
    int sx, sy, tx, ty;
    scanf("%d %d %d %d",&sx,&sy,&tx,&ty);
    vector<string>g(R);
    for(int i=0;i<R;i++) {
        char buf[1005];
        scanf("%s",buf);
        g[i]=buf;
    }
    vector<vector<int>>d(R,vector<int>(C,-1));
    queue<pair<int, int>>q;
    if(g[sx][sy]=='.') {
        d[sx][sy]=0;
        q.push({sx,sy});
    }
    int dx[4]={1, -1, 0, 0}, dy[4]={0, 0, 1, -1};
    while(!q.empty()) {
        pair<int, int> cur=q.front();
        q.pop();
        int u=cur.first, v=cur.second;
        for(int k=0;k<4;k++) {
            int nx=u+dx[k], ny=v+dy[k];
            if(nx>=0&&nx<R&&ny>=0&&ny<C&&g[nx][ny]=='.'&&d[nx][ny]<0) {
                d[nx][ny]=d[u][v]+1;
                q.push(make_pair(nx,ny));
            }
        }
    }
    printf("%d\\n",d[tx][ty]);
    return 0;
}
""",
  "slow": HDR + """int R, C, sx, sy, tx, ty;
vector<string>g;
int best=INT_MAX;
void dfs(int x,int y,int d) {
    if(d>=best)return;
    if(x==tx&&y==ty) {
        best=d;
        return;
    }
    int dx[4]={1, -1, 0, 0}, dy[4]={0, 0, 1, -1};
    g[x][y]='#';
    for(int k=0;k<4;k++) {
        int nx=x+dx[k], ny=y+dy[k];
        if(nx>=0&&nx<R&&ny>=0&&ny<C&&g[nx][ny]=='.')dfs(nx,ny,d+1);
    }
    g[x][y]='.';
}

int main() {
    scanf("%d %d",&R,&C);
    scanf("%d %d %d %d",&sx,&sy,&tx,&ty);
    g.resize(R);
    for(int i=0;i<R;i++) {
        char buf[1005];
        scanf("%s",buf);
        g[i]=buf;
    }
    dfs(sx,sy,0);
    printf("%d\\n",best==INT_MAX?-1:best);
    return 0;
}
""",
  "bug": HDR + """int main() {
    int R, C;
    scanf("%d %d",&R,&C);
    int sx, sy, tx, ty;
    scanf("%d %d %d %d",&sx,&sy,&tx,&ty);
    vector<string>g(R);
    for(int i=0;i<R;i++) {
        char buf[1005];
        scanf("%s",buf);
        g[i]=buf;
    }
    vector<vector<int>>d(R,vector<int>(C,-1));
    queue<pair<int, int>>q;
    q.push({sx,sy});
    d[sx][sy]=0;
    int dx[4]={1, -1, 0, 0}, dy[4]={0, 0, 1, -1};
    while(!q.empty()) {
        pair<int, int> cur=q.front();
        q.pop();
        int u=cur.first, v=cur.second;
        for(int k=0;k<4;k++) {
            int nx=u+dx[k], ny=v+dy[k];
            if(nx>=0&&nx<R&&ny>=0&&ny<C&&g[nx][ny]=='.'&&d[nx][ny]<0) {
                d[nx][ny]=d[u][v]+1;
                q.push(make_pair(nx,ny));
            }
        }
    }
    printf("%d\\n",d[tx][ty]);
    return 0;
}
""",
},
"DIJKSTRA": {
  "ok": HDR + """int main() {
    int n, m;
    scanf("%d %d",&n,&m);
    vector<vector<pair<int, int>>>adj(n+1);
    for(int i=0;i<m;i++) {
        int u, v, w;
        scanf("%d %d %d",&u,&v,&w);
        adj[u].push_back({v,w});
        adj[v].push_back({u,w});
    }
    const long long INF=LLONG_MAX/4;
    vector<long long>d(n+1,INF);
    d[1]=0;
    typedef pair<long long, int> pli;
    priority_queue<pli, vector<pli>, greater<pli>>pq;
    pq.push(make_pair(0LL,1));
    while(!pq.empty()) {
        pli top=pq.top();
        pq.pop();
        long long du=top.first;
        int u=top.second;
        if(du>d[u])continue;
        for(size_t i=0;i<adj[u].size();i++) {
            int v=adj[u][i].first, w=adj[u][i].second;
            if(du+w<d[v]) {
                d[v]=du+w;
                pq.push(make_pair(d[v],v));
            }
        }
    }
    for(int i=1;i<=n;i++)printf("%lld%c",d[i]>=INF?-1:d[i],i==n?'\\n':' ');
    return 0;
}
""",
  "slow": HDR + """int main() {
    int n, m;
    scanf("%d %d",&n,&m);
    const long long INF=LLONG_MAX/4;
    vector<vector<long long>>w(n+1,vector<long long>(n+1,INF));
    for(int i=1;i<=n;i++)w[i][i]=0;
    for(int i=0;i<m;i++) {
        int u, v, ww;
        scanf("%d %d %d",&u,&v,&ww);
        w[u][v]=min(w[u][v],(long long)ww);
        w[v][u]=min(w[v][u],(long long)ww);
    }
    for(int k=1;k<=n;k++)for(int i=1;i<=n;i++)for(int j=1;j<=n;j++) if(w[i][k]<INF&&w[k][j]<INF&&w[i][k]+w[k][j]<w[i][j])w[i][j]=w[i][k]+w[k][j];
    for(int i=1;i<=n;i++)printf("%lld%c",w[1][i]>=INF?-1:w[1][i],i==n?'\\n':' ');
    return 0;
}
""",
  "bug": HDR + """int main() {
    int n, m;
    scanf("%d %d",&n,&m);
    vector<vector<pair<int, int>>>adj(n+1);
    for(int i=0;i<m;i++) {
        int u, v, w;
        scanf("%d %d %d",&u,&v,&w);
        adj[u].push_back({v,w});
        adj[v].push_back({u,w});
    }
    const long long INF=LLONG_MAX/4;
    vector<long long>d(n+1,INF);
    d[1]=0;
    queue<int>q;
    q.push(1);
    vector<int>inq(n+1,0);
    inq[1]=1;
    while(!q.empty()) {
        int u=q.front();
        q.pop();
        inq[u]=0;
        for(auto&e:adj[u])if(d[u]+e.second<d[e.first]) {
            d[e.first]=d[u]+e.second;
            if(!inq[e.first]) {
                inq[e.first]=1;
                q.push(e.first);
            }
        }
    }
    for(int i=1;i<=n;i++)printf("%lld%c",d[i]>=INF?-1:d[i],i==n?'\\n':' ');
    return 0;
}
""",
},
"DSU": {
  "ok": HDR + """int p[500005];
int find(int x) {
    while(p[x]!=x) {
        p[x]=p[p[x]];
        x=p[x];
    }
    return x;
}

int main() {
    int n, m;
    scanf("%d %d",&n,&m);
    for(int i=1;i<=n;i++)p[i]=i;
    for(int i=0;i<m;i++) {
        int u, v;
        scanf("%d %d",&u,&v);
        int a=find(u), b=find(v);
        if(a!=b)p[b]=a;
    }
    int c=0;
    for(int i=1;i<=n;i++)if(find(i)==i)c++;
    printf("%d\\n",c);
    return 0;
}
""",
  "slow": HDR + """int main() {
    int n, m;
    scanf("%d %d",&n,&m);
    vector<vector<int>>g(n+1);
    for(int i=0;i<m;i++) {
        int u, v;
        scanf("%d %d",&u,&v);
        g[u].push_back(v);
        g[v].push_back(u);
    }
    vector<int>vis(n+1,0);
    int c=0;
    for(int i=1;i<=n;i++) {
        if(vis[i])continue;
        c++;
        queue<int>q;
        q.push(i);
        vis[i]=1;
        while(!q.empty()) {
            int u=q.front();
            q.pop();
            for(int v:g[u])if(!vis[v]) {
                vis[v]=1;
                q.push(v);
            }
        }
    }
    printf("%d\\n",c);
    return 0;
}
""",
  "bug": HDR + """int p[500005];
int find(int x) {
    return p[x]==x?x:find(p[x]);
}

int main() {
    int n, m;
    scanf("%d %d",&n,&m);
    for(int i=1;i<=n;i++)p[i]=i;
    for(int i=0;i<m;i++) {
        int u, v;
        scanf("%d %d",&u,&v);
        p[find(u)]=find(v);
    }
    int c=0;
    for(int i=1;i<=n;i++)if(p[i]==i)c++;
    printf("%d\\n",c);
    return 0;
}
""",
},
"KMP": {
  "ok": HDR + """char s[1000006], p[1000006];
int pi[1000006];
int main() {
    scanf("%s %s",s,p);
    int n=strlen(s), m=strlen(p);
    if(m==0) {
        printf("0\\n");
        return 0;
    }
    for(int i=1;i<m;i++) {
        int k=pi[i-1];
        while(k&&p[i]!=p[k])k=pi[k-1];
        if(p[i]==p[k])k++;
        pi[i]=k;
    }
    int c=0, k=0;
    for(int i=0;i<n;i++) {
        while(k&&s[i]!=p[k])k=pi[k-1];
        if(s[i]==p[k])k++;
        if(k==m) {
            c++;
            k=pi[k-1];
        }
    }
    printf("%d\\n",c);
    return 0;
}
""",
  "slow": HDR + """int main() {
    char s[1000006], p[1000006];
    scanf("%s %s",s,p);
    int n=strlen(s), m=strlen(p), c=0;
    for(int i=0;i+m<=n;i++) {
        int ok=1;
        for(int j=0;j<m;j++)if(s[i+j]!=p[j]) {
            ok=0;
            break;
        }
        if(ok)c++;
    }
    printf("%d\\n",c);
    return 0;
}
""",
  "bug": HDR + """char s[1000006], p[1000006];
int pi[1000006];
int main() {
    scanf("%s %s",s,p);
    int n=strlen(s), m=strlen(p);
    for(int i=1;i<m;i++) {
        int k=pi[i-1];
        while(k&&p[i]!=p[k])k=pi[k-1];
        if(p[i]==p[k])k++;
        pi[i]=k;
    }
    int c=0, k=0;
    for(int i=0;i<n;i++) {
        while(k&&s[i]!=p[k])k=pi[k-1];
        if(s[i]==p[k])k++;
        if(k==m) {
            c++;
        }
    }
    printf("%d\\n",c);
    return 0;
}
""",
},
"CUT": {
  "ok": HDR + """int main() {
    int n, m;
    scanf("%d %d",&n,&m);
    vector<long long>a(n);
    for(int i=0;i<n;i++)scanf("%lld",&a[i]);
    long long lo=1, hi=*max_element(a.begin(),a.end()), ans=0;
    while(lo<=hi) {
        long long mid=(lo+hi)/2, cnt=0;
        for(auto x:a)cnt+=x/mid;
        if(cnt>=m) {
            ans=mid;
            lo=mid+1;
        }
        else hi=mid-1;
    }
    printf("%lld\\n",ans);
    return 0;
}
""",
  "slow": HDR + """int main() {
    int n, m;
    scanf("%d %d",&n,&m);
    vector<long long>a(n);
    for(int i=0;i<n;i++)scanf("%lld",&a[i]);
    long long ans=0;
    for(long long L=1;L<=*max_element(a.begin(),a.end());L++) {
        long long c=0;
        for(auto x:a)c+=x/L;
        if(c>=m)ans=L;
        else break;
    }
    printf("%lld\\n",ans);
    return 0;
}
""",
  "bug": HDR + """int main() {
    int n, m;
    scanf("%d %d",&n,&m);
    vector<long long>a(n);
    for(int i=0;i<n;i++)scanf("%lld",&a[i]);
    long long lo=1, hi=*max_element(a.begin(),a.end()), ans=0;
    while(lo<=hi) {
        long long mid=(lo+hi)/2, cnt=0;
        for(auto x:a)cnt+=x/mid;
        if(cnt>m) {
            ans=mid;
            lo=mid+1;
        }
        else hi=mid-1;
    }
    printf("%lld\\n",ans);
    return 0;
}
""",
},
"TOPO": {
  "ok": HDR + """// Kahn 拓扑排序 + 小根堆：输出字典序最小的拓扑序
int main() {
    int n, m;
    if(scanf("%d %d",&n,&m)!=2)return 0;
    vector<vector<int>> adj(n+1);
    vector<int> deg(n+1,0);
    for(int i=0;i<m;i++) {
        int u,v;
        scanf("%d %d",&u,&v);
        adj[u].push_back(v);
        deg[v]++;
    }
    priority_queue<int,vector<int>,greater<int>> pq;
    for(int i=1;i<=n;i++) if(!deg[i]) pq.push(i);
    vector<int> order;
    while(!pq.empty()) {
        int u=pq.top();
        pq.pop();
        order.push_back(u);
        for(int v:adj[u]) if(--deg[v]==0) pq.push(v);
    }
    if((int)order.size()!=n) { printf("-1\\n"); return 0; }
    for(int i=0;i<n;i++) printf("%d%c",order[i],i+1==n?'\\n':' ');
    return 0;
}
""",
  "slow": HDR + """// 每轮线性扫描最小入度为 0 的点：O(n^2)，大规模会超时
int main() {
    int n, m;
    scanf("%d %d",&n,&m);
    vector<vector<int>> adj(n+1);
    vector<int> deg(n+1,0), done(n+1,0);
    for(int i=0;i<m;i++) {
        int u,v;
        scanf("%d %d",&u,&v);
        adj[u].push_back(v);
        deg[v]++;
    }
    vector<int> order;
    for(int step=0;step<n;step++) {
        int pick=0;
        // 每轮完整扫描一遍所有点（不提前退出），因此是 O(n^2)
        for(int i=1;i<=n;i++)
            if(!done[i]&&deg[i]==0&&(pick==0||i<pick)) pick=i;
        if(!pick) { printf("-1\\n"); return 0; }
        done[pick]=1;
        order.push_back(pick);
        for(int v:adj[pick]) deg[v]--;
    }
    for(int i=0;i<n;i++) printf("%d%c",order[i],i+1==n?'\\n':' ');
    return 0;
}
""",
  "bug": HDR + """// 用了大根堆：输出仍是合法拓扑序，但不是字典序最小的那个
int main() {
    int n, m;
    scanf("%d %d",&n,&m);
    vector<vector<int>> adj(n+1);
    vector<int> deg(n+1,0);
    for(int i=0;i<m;i++) {
        int u,v;
        scanf("%d %d",&u,&v);
        adj[u].push_back(v);
        deg[v]++;
    }
    priority_queue<int> pq;
    for(int i=1;i<=n;i++) if(!deg[i]) pq.push(i);
    vector<int> order;
    while(!pq.empty()) {
        int u=pq.top();
        pq.pop();
        order.push_back(u);
        for(int v:adj[u]) if(--deg[v]==0) pq.push(v);
    }
    if((int)order.size()!=n) { printf("-1\\n"); return 0; }
    for(int i=0;i<n;i++) printf("%d%c",order[i],i+1==n?'\\n':' ');
    return 0;
}
""",
},
"PARTITION": {
  "ok": HDR + """// 扫描线：最少教室数 = 区间集合的最大深度
int main() {
    int n;
    if(scanf("%d",&n)!=1)return 0;
    vector<pair<int,int>> ev;
    ev.reserve(2*n);
    for(int i=0;i<n;i++) {
        int s,f;
        scanf("%d %d",&s,&f);
        ev.push_back({s,1});
        ev.push_back({f,-1});
    }
    sort(ev.begin(),ev.end());
    int cur=0,best=0;
    for(auto&e:ev) { cur+=e.second; best=max(best,cur); }
    printf("%d\\n",best);
    return 0;
}
""",
  "slow": HDR + """// 逐个起点统计覆盖数：O(n^2)
int main() {
    int n;
    scanf("%d",&n);
    vector<int> s(n),f(n);
    for(int i=0;i<n;i++) scanf("%d %d",&s[i],&f[i]);
    int best=0;
    for(int i=0;i<n;i++) {
        int c=0;
        for(int j=0;j<n;j++) if(s[j]<=s[i]&&s[i]<f[j]) c++;
        best=max(best,c);
    }
    printf("%d\\n",best);
    return 0;
}
""",
  "bug": HDR + """// 把区间当成闭区间：[s,f] 与 [f,g] 被误判为冲突
int main() {
    int n;
    scanf("%d",&n);
    vector<pair<int,int>> ev;
    for(int i=0;i<n;i++) {
        int s,f;
        scanf("%d %d",&s,&f);
        ev.push_back({s,1});
        ev.push_back({f-1,-1});
    }
    sort(ev.begin(),ev.end());
    int cur=0,best=0;
    for(auto&e:ev) { cur+=e.second; best=max(best,cur); }
    printf("%d\\n",best);
    return 0;
}
""",
},
"LATENESS": {
  "ok": HDR + """// 最早截止期优先（EDF）是最优策略：按 d 升序依次执行
int main() {
    int n;
    if(scanf("%d",&n)!=1)return 0;
    vector<pair<long long,long long>> job(n);
    for(int i=0;i<n;i++) scanf("%lld %lld",&job[i].second,&job[i].first);
    sort(job.begin(),job.end());
    long long cur=0,worst=LLONG_MIN;
    for(auto&j:job) { cur+=j.second; worst=max(worst,cur-j.first); }
    printf("%lld\\n",worst);
    return 0;
}
""",
  "slow": HDR + """// 每轮线性扫描最早截止期的任务：结果正确但 O(n^2)
int main() {
    int n;
    scanf("%d",&n);
    vector<long long> t(n),d(n);
    vector<char> used(n,0);
    for(int i=0;i<n;i++) scanf("%lld %lld",&t[i],&d[i]);
    long long cur=0,worst=LLONG_MIN;
    for(int step=0;step<n;step++) {
        int pick=-1;
        for(int i=0;i<n;i++)
            if(!used[i]&&(pick<0||d[i]<d[pick])) pick=i;
        used[pick]=1;
        cur+=t[pick];
        worst=max(worst,cur-d[pick]);
    }
    printf("%lld\\n",worst);
    return 0;
}
""",
  "bug": HDR + """// 按处理时间从短到长排：直觉上“先做快的”，但最大延迟会变大
int main() {
    int n;
    scanf("%d",&n);
    vector<pair<long long,long long>> job(n);
    for(int i=0;i<n;i++) scanf("%lld %lld",&job[i].first,&job[i].second);
    sort(job.begin(),job.end());
    long long cur=0,worst=LLONG_MIN;
    for(auto&j:job) { cur+=j.first; worst=max(worst,cur-j.second); }
    printf("%lld\\n",worst);
    return 0;
}
""",
},
"CLOSEST": {
  "ok": HDR + """// 分治求最近点对（返回距离平方，避免浮点误差）
typedef long long ll;
struct P { ll x,y; };
vector<P> px;

ll d2(const P&a,const P&b){ ll dx=a.x-b.x, dy=a.y-b.y; return dx*dx+dy*dy; }

ll rec(int lo,int hi) {
    if(hi-lo<=3) {
        ll best=LLONG_MAX;
        for(int i=lo;i<hi;i++)
            for(int j=i+1;j<hi;j++) best=min(best,d2(px[i],px[j]));
        return best;
    }
    int mid=(lo+hi)/2;
    ll midx=px[mid].x;
    ll d=min(rec(lo,mid),rec(mid,hi));
    vector<P> strip;
    for(int i=lo;i<hi;i++) {
        ll dx=px[i].x-midx;
        if(dx*dx<d) strip.push_back(px[i]);
    }
    sort(strip.begin(),strip.end(),[](const P&a,const P&b){return a.y<b.y;});
    for(size_t i=0;i<strip.size();i++)
        for(size_t j=i+1;j<strip.size();j++) {
            ll dy=strip[j].y-strip[i].y;
            if(dy*dy>=d) break;
            d=min(d,d2(strip[i],strip[j]));
        }
    return d;
}

int main() {
    int n;
    if(scanf("%d",&n)!=1)return 0;
    px.resize(n);
    for(int i=0;i<n;i++) scanf("%lld %lld",&px[i].x,&px[i].y);
    sort(px.begin(),px.end(),[](const P&a,const P&b){return a.x<b.x;});
    printf("%lld\\n",rec(0,n));
    return 0;
}
""",
  "slow": HDR + """// 枚举所有点对：O(n^2)
int main() {
    int n;
    scanf("%d",&n);
    vector<long long> x(n),y(n);
    for(int i=0;i<n;i++) scanf("%lld %lld",&x[i],&y[i]);
    long long best=LLONG_MAX;
    for(int i=0;i<n;i++)
        for(int j=i+1;j<n;j++) {
            long long dx=x[i]-x[j], dy=y[i]-y[j];
            best=min(best,dx*dx+dy*dy);
        }
    printf("%lld\\n",best);
    return 0;
}
""",
  "bug": HDR + """// 只比较 y 序上相邻的两点：会漏掉真正的最近点对
typedef long long ll;
struct P { ll x,y; };
int main() {
    int n;
    scanf("%d",&n);
    vector<P> p(n);
    for(int i=0;i<n;i++) scanf("%lld %lld",&p[i].x,&p[i].y);
    sort(p.begin(),p.end(),[](const P&a,const P&b){return a.y<b.y;});
    ll best=LLONG_MAX;
    for(int i=0;i+1<n;i++) {
        ll dx=p[i].x-p[i+1].x, dy=p[i].y-p[i+1].y;
        best=min(best,dx*dx+dy*dy);
    }
    printf("%lld\\n",best);
    return 0;
}
""",
},
"EDITDIST": {
  "ok": HDR + """// 编辑距离：插入 / 删除 / 替换代价均为 1，滚动数组 O(|a|·|b|)
int main() {
    string a,b;
    if(!(cin>>a)) return 0;
    cin>>b;
    int m=b.size();
    vector<int> dp(m+1);
    for(int j=0;j<=m;j++) dp[j]=j;
    for(int i=1;i<=(int)a.size();i++) {
        int prev=dp[0];
        dp[0]=i;
        for(int j=1;j<=m;j++) {
            int cur=dp[j];
            if(a[i-1]==b[j-1]) dp[j]=prev;
            else dp[j]=1+min(min(prev,dp[j]),dp[j-1]);
            prev=cur;
        }
    }
    printf("%d\\n",dp[m]);
    return 0;
}
""",
  "slow": HDR + """// 朴素递归（不做记忆化）：规模稍大就指数级超时
string a,b;
int go(int i,int j) {
    if(i==(int)a.size()) return (int)b.size()-j;
    if(j==(int)b.size()) return (int)a.size()-i;
    if(a[i]==b[j]) return go(i+1,j+1);
    return 1+min(min(go(i+1,j),go(i,j+1)),go(i+1,j+1));
}
int main() {
    if(!(cin>>a)) return 0;
    cin>>b;
    printf("%d\\n",go(0,0));
    return 0;
}
""",
  "bug": HDR + """// 忘了考虑替换操作：只允许插入与删除
int main() {
    string a,b;
    cin>>a>>b;
    int m=b.size();
    vector<int> dp(m+1);
    for(int j=0;j<=m;j++) dp[j]=j;
    for(int i=1;i<=(int)a.size();i++) {
        int prev=dp[0];
        dp[0]=i;
        for(int j=1;j<=m;j++) {
            int cur=dp[j];
            if(a[i-1]==b[j-1]) dp[j]=prev;
            else dp[j]=1+min(dp[j],dp[j-1]);
            prev=cur;
        }
    }
    printf("%d\\n",dp[m]);
    return 0;
}
""",
},
"MST": {
  "ok": HDR + """// Kruskal：按边权排序 + 并查集，O(m log m)
int p[100005];
int find(int x){ while(p[x]!=x){ p[x]=p[p[x]]; x=p[x]; } return x; }

int main() {
    int n,m;
    if(scanf("%d %d",&n,&m)!=2)return 0;
    vector<array<long long,3>> e(m);
    for(int i=0;i<m;i++) scanf("%lld %lld %lld",&e[i][1],&e[i][2],&e[i][0]);
    for(int i=1;i<=n;i++) p[i]=i;
    sort(e.begin(),e.end());
    long long total=0;
    int used=0;
    for(auto&t:e) {
        int u=find((int)t[1]), v=find((int)t[2]);
        if(u==v) continue;
        p[v]=u;
        total+=t[0];
        if(++used==n-1) break;
    }
    if(used!=n-1) printf("-1\\n");
    else printf("%lld\\n",total);
    return 0;
}
""",
  "slow": HDR + """// 每轮扫描所有边找连接两个连通块的最小边：O(n·m)
int p[100005];
int find(int x){ while(p[x]!=x){ p[x]=p[p[x]]; x=p[x]; } return x; }

int main() {
    int n,m;
    scanf("%d %d",&n,&m);
    vector<int> u(m),v(m),w(m),used(m,0);
    for(int i=0;i<m;i++) scanf("%d %d %d",&u[i],&v[i],&w[i]);
    for(int i=1;i<=n;i++) p[i]=i;
    long long total=0;
    int cnt=0;
    while(cnt<n-1) {
        int best=-1;
        for(int i=0;i<m;i++) {
            if(used[i]) continue;
            if(find(u[i])==find(v[i])) { used[i]=1; continue; }
            if(best<0||w[i]<w[best]) best=i;
        }
        if(best<0) break;
        used[best]=1;
        p[find(u[best])]=find(v[best]);
        total+=w[best];
        cnt++;
    }
    if(cnt!=n-1) printf("-1\\n");
    else printf("%lld\\n",total);
    return 0;
}
""",
  "bug": HDR + """// 忘了判断连通性：图不连通时把森林的权值当答案输出
int p[100005];
int find(int x){ while(p[x]!=x){ p[x]=p[p[x]]; x=p[x]; } return x; }

int main() {
    int n,m;
    scanf("%d %d",&n,&m);
    vector<array<long long,3>> e(m);
    for(int i=0;i<m;i++) scanf("%lld %lld %lld",&e[i][1],&e[i][2],&e[i][0]);
    for(int i=1;i<=n;i++) p[i]=i;
    sort(e.begin(),e.end());
    long long total=0;
    for(auto&t:e) {
        int u=find((int)t[1]), v=find((int)t[2]);
        if(u==v) continue;
        p[v]=u;
        total+=t[0];
    }
    printf("%lld\\n",total);
    return 0;
}
""",
},
"SEGTREE": {
  "ok": HDR + """// 线段树：区间加 + 区间求和，带懒标记
typedef long long ll;
ll tree[800020], lazy[800020];
int n;

void apply(int o,int lo,int hi,ll v){ tree[o]+=v*(hi-lo+1); lazy[o]+=v; }
void push(int o,int lo,int hi){
    if(!lazy[o]||lo==hi) return;
    int mid=(lo+hi)/2;
    apply(o*2,lo,mid,lazy[o]);
    apply(o*2+1,mid+1,hi,lazy[o]);
    lazy[o]=0;
}
void build(int o,int lo,int hi){
    if(lo==hi){ scanf("%lld",&tree[o]); return; }
    int mid=(lo+hi)/2;
    build(o*2,lo,mid);
    build(o*2+1,mid+1,hi);
    tree[o]=tree[o*2]+tree[o*2+1];
}
void update(int o,int lo,int hi,int l,int r,ll v){
    if(r<lo||hi<l) return;
    if(l<=lo&&hi<=r){ apply(o,lo,hi,v); return; }
    push(o,lo,hi);
    int mid=(lo+hi)/2;
    update(o*2,lo,mid,l,r,v);
    update(o*2+1,mid+1,hi,l,r,v);
    tree[o]=tree[o*2]+tree[o*2+1];
}
ll query(int o,int lo,int hi,int l,int r){
    if(r<lo||hi<l) return 0;
    if(l<=lo&&hi<=r) return tree[o];
    push(o,lo,hi);
    int mid=(lo+hi)/2;
    return query(o*2,lo,mid,l,r)+query(o*2+1,mid+1,hi,l,r);
}
int main() {
    int q;
    if(scanf("%d %d",&n,&q)!=2)return 0;
    build(1,1,n);
    while(q--) {
        int op,l,r;
        scanf("%d %d %d",&op,&l,&r);
        if(op==1) {
            ll v;
            scanf("%lld",&v);
            update(1,1,n,l,r,v);
        } else {
            printf("%lld\\n",query(1,1,n,l,r));
        }
    }
    return 0;
}
""",
  "slow": HDR + """// 每次操作直接扫区间：O(n) / 次
int main() {
    int n,q;
    scanf("%d %d",&n,&q);
    vector<long long> a(n+1);
    for(int i=1;i<=n;i++) scanf("%lld",&a[i]);
    while(q--) {
        int op,l,r;
        scanf("%d %d %d",&op,&l,&r);
        if(op==1) {
            long long v;
            scanf("%lld",&v);
            for(int i=l;i<=r;i++) a[i]+=v;
        } else {
            long long s=0;
            for(int i=l;i<=r;i++) s+=a[i];
            printf("%lld\\n",s);
        }
    }
    return 0;
}
""",
  "bug": HDR + """// 部分覆盖时忘记把懒标记下推给儿子：查询结果偏小
typedef long long ll;
ll tree[800020], lazy[800020];
int n;

void apply(int o,int lo,int hi,ll v){ tree[o]+=v*(hi-lo+1); lazy[o]+=v; }
void build(int o,int lo,int hi){
    if(lo==hi){ scanf("%lld",&tree[o]); return; }
    int mid=(lo+hi)/2;
    build(o*2,lo,mid);
    build(o*2+1,mid+1,hi);
    tree[o]=tree[o*2]+tree[o*2+1];
}
void update(int o,int lo,int hi,int l,int r,ll v){
    if(r<lo||hi<l) return;
    if(l<=lo&&hi<=r){ apply(o,lo,hi,v); return; }
    int mid=(lo+hi)/2;
    update(o*2,lo,mid,l,r,v);
    update(o*2+1,mid+1,hi,l,r,v);
    tree[o]=tree[o*2]+tree[o*2+1];
}
ll query(int o,int lo,int hi,int l,int r){
    if(r<lo||hi<l) return 0;
    if(l<=lo&&hi<=r) return tree[o];
    int mid=(lo+hi)/2;
    return query(o*2,lo,mid,l,r)+query(o*2+1,mid+1,hi,l,r);
}
int main() {
    int q;
    scanf("%d %d",&n,&q);
    build(1,1,n);
    while(q--) {
        int op,l,r;
        scanf("%d %d %d",&op,&l,&r);
        if(op==1) {
            ll v;
            scanf("%lld",&v);
            update(1,1,n,l,r,v);
        } else {
            printf("%lld\\n",query(1,1,n,l,r));
        }
    }
    return 0;
}
""",
},
"BIT": {
  "ok": HDR + """// 树状数组：单点修改 + 区间求和
typedef long long ll;
ll bit[300005];
int n;
void add(int i,ll v){ for(;i<=n;i+=i&-i) bit[i]+=v; }
ll pre(int i){ ll s=0; for(;i>0;i-=i&-i) s+=bit[i]; return s; }
int main() {
    int q;
    if(scanf("%d %d",&n,&q)!=2)return 0;
    for(int i=1;i<=n;i++) {
        ll v;
        scanf("%lld",&v);
        add(i,v);
    }
    while(q--) {
        int op,a,b;
        scanf("%d %d %d",&op,&a,&b);
        if(op==1) add(a,b);
        else printf("%lld\\n",pre(b)-pre(a-1));
    }
    return 0;
}
""",
  "slow": HDR + """// 用前缀和暴力：修改 O(n)、查询 O(n)
int main() {
    int n,q;
    scanf("%d %d",&n,&q);
    vector<long long> a(n+1);
    for(int i=1;i<=n;i++) scanf("%lld",&a[i]);
    while(q--) {
        int op,x,y;
        scanf("%d %d %d",&op,&x,&y);
        if(op==1) a[x]+=y;
        else {
            long long s=0;
            for(int i=x;i<=y;i++) s+=a[i];
            printf("%lld\\n",s);
        }
    }
    return 0;
}
""",
  "bug": HDR + """// 建树时只写了 bit[i]=a[i]，没有向后续位置累加贡献
typedef long long ll;
ll bit[300005];
int n;
void add(int i,ll v){ for(;i<=n;i+=i&-i) bit[i]+=v; }
ll pre(int i){ ll s=0; for(;i>0;i-=i&-i) s+=bit[i]; return s; }
int main() {
    int q;
    scanf("%d %d",&n,&q);
    for(int i=1;i<=n;i++) {
        ll v;
        scanf("%lld",&v);
        bit[i]=v;
    }
    while(q--) {
        int op,a,b;
        scanf("%d %d %d",&op,&a,&b);
        if(op==1) add(a,b);
        else printf("%lld\\n",pre(b)-pre(a-1));
    }
    return 0;
}
""",
},
"MAXFLOW": {
  "ok": HDR + """// Dinic 最大流
struct Edge { int to, rev; long long cap; };
vector<vector<Edge>> g;
vector<int> level, it;

void add_edge(int u,int v,long long c) {
    g[u].push_back({v,(int)g[v].size(),c});
    g[v].push_back({u,(int)g[u].size()-1,0});
}
bool bfs(int s,int t) {
    fill(level.begin(),level.end(),-1);
    queue<int> q;
    level[s]=0;
    q.push(s);
    while(!q.empty()) {
        int u=q.front();
        q.pop();
        for(auto&e:g[u]) if(e.cap>0&&level[e.to]<0) {
            level[e.to]=level[u]+1;
            q.push(e.to);
        }
    }
    return level[t]>=0;
}
long long dfs(int u,int t,long long f) {
    if(u==t) return f;
    for(int &i=it[u];i<(int)g[u].size();i++) {
        Edge &e=g[u][i];
        if(e.cap>0&&level[e.to]==level[u]+1) {
            long long d=dfs(e.to,t,min(f,e.cap));
            if(d>0) { e.cap-=d; g[e.to][e.rev].cap+=d; return d; }
        }
    }
    return 0;
}
int main() {
    int n,m,s,t;
    if(scanf("%d %d %d %d",&n,&m,&s,&t)!=4)return 0;
    g.assign(n+1,{});
    level.assign(n+1,-1);
    it.assign(n+1,0);
    for(int i=0;i<m;i++) {
        int u,v;
        long long c;
        scanf("%d %d %lld",&u,&v,&c);
        add_edge(u,v,c);
    }
    long long flow=0;
    while(bfs(s,t)) {
        fill(it.begin(),it.end(),0);
        while(long long f=dfs(s,t,LLONG_MAX)) flow+=f;
    }
    printf("%lld\\n",flow);
    return 0;
}
""",
  "slow": HDR + """// Edmonds-Karp：每次 BFS 只推一条路径，边多时退化
struct Edge { int to, rev; long long cap; };
vector<vector<Edge>> g;

void add_edge(int u,int v,long long c) {
    g[u].push_back({v,(int)g[v].size(),c});
    g[v].push_back({u,(int)g[u].size()-1,0});
}
int main() {
    int n,m,s,t;
    scanf("%d %d %d %d",&n,&m,&s,&t);
    g.assign(n+1,{});
    for(int i=0;i<m;i++) {
        int u,v;
        long long c;
        scanf("%d %d %lld",&u,&v,&c);
        add_edge(u,v,c);
    }
    long long flow=0;
    while(true) {
        vector<int> pe(n+1,-1), pv(n+1,-1);
        vector<char> vis(n+1,0);
        queue<int> q;
        q.push(s); vis[s]=1;
        while(!q.empty()) {
            int u=q.front(); q.pop();
            for(int i=0;i<(int)g[u].size();i++) {
                Edge&e=g[u][i];
                if(e.cap>0&&!vis[e.to]) {
                    vis[e.to]=1; pe[e.to]=u; pv[e.to]=i; q.push(e.to);
                }
            }
        }
        if(!vis[t]) break;
        long long f=LLONG_MAX;
        for(int v=t;v!=s;v=pe[v]) f=min(f,g[pe[v]][pv[v]].cap);
        for(int v=t;v!=s;v=pe[v]) {
            Edge&e=g[pe[v]][pv[v]];
            e.cap-=f;
            g[v][e.rev].cap+=f;
        }
        flow+=f;
    }
    printf("%lld\\n",flow);
    return 0;
}
""",
  "bug": HDR + """// 用 DFS 找增广路且只减正向边、不恢复反向边：无法退流，答案偏小
struct Edge { int to, rev; long long cap; };
vector<vector<Edge>> g;
vector<char> vis;

void add_edge(int u,int v,long long c) {
    g[u].push_back({v,(int)g[v].size(),c});
    g[v].push_back({u,(int)g[u].size()-1,0});
}
long long dfs(int u,int t,long long f) {
    if(u==t) return f;
    vis[u]=1;
    for(auto&e:g[u]) {
        if(e.cap>0&&!vis[e.to]) {
            long long d=dfs(e.to,t,min(f,e.cap));
            if(d>0) { e.cap-=d; return d; }
        }
    }
    return 0;
}
int main() {
    int n,m,s,t;
    scanf("%d %d %d %d",&n,&m,&s,&t);
    g.assign(n+1,{});
    for(int i=0;i<m;i++) {
        int u,v;
        long long c;
        scanf("%d %d %lld",&u,&v,&c);
        add_edge(u,v,c);
    }
    long long flow=0;
    while(true) {
        vis.assign(n+1,0);
        long long f=dfs(s,t,LLONG_MAX);
        if(!f) break;
        flow+=f;
    }
    printf("%lld\\n",flow);
    return 0;
}
""",
},
}

PY = {
"TOPO": """import sys, heapq
def main():
    data = sys.stdin.buffer.read().split()
    if not data:
        return
    n = int(data[0]); m = int(data[1])
    adj = [[] for _ in range(n + 1)]
    deg = [0] * (n + 1)
    p = 2
    for _ in range(m):
        u = int(data[p]); v = int(data[p + 1]); p += 2
        adj[u].append(v)
        deg[v] += 1
    heap = [i for i in range(1, n + 1) if deg[i] == 0]
    heapq.heapify(heap)
    order = []
    while heap:
        u = heapq.heappop(heap)
        order.append(u)
        for v in adj[u]:
            deg[v] -= 1
            if deg[v] == 0:
                heapq.heappush(heap, v)
    if len(order) != n:
        print(-1)
    else:
        print(" ".join(map(str, order)))
main()
""",
"PARTITION": """import sys
def main():
    data = sys.stdin.buffer.read().split()
    n = int(data[0])
    ev = []
    p = 1
    for _ in range(n):
        s = int(data[p]); f = int(data[p + 1]); p += 2
        ev.append((s, 1))
        ev.append((f, -1))
    ev.sort()
    cur = best = 0
    for _, d in ev:
        cur += d
        if cur > best:
            best = cur
    print(best)
main()
""",
"LATENESS": """import sys
def main():
    data = sys.stdin.buffer.read().split()
    n = int(data[0])
    jobs = []
    p = 1
    for _ in range(n):
        t = int(data[p]); d = int(data[p + 1]); p += 2
        jobs.append((d, t))
    jobs.sort()
    cur = 0
    worst = None
    for d, t in jobs:
        cur += t
        late = cur - d
        if worst is None or late > worst:
            worst = late
    print(worst)
main()
""",
"EDITDIST": """import sys
def main():
    data = sys.stdin.buffer.read().split()
    if len(data) < 2:
        return
    a = data[0].decode(); b = data[1].decode()
    m = len(b)
    dp = list(range(m + 1))
    for i, ca in enumerate(a, 1):
        prev = dp[0]
        dp[0] = i
        for j, cb in enumerate(b, 1):
            cur = dp[j]
            dp[j] = prev if ca == cb else 1 + min(prev, dp[j], dp[j - 1])
            prev = cur
    print(dp[m])
main()
""",
"MST": """import sys
def main():
    data = sys.stdin.buffer.read().split()
    n = int(data[0]); m = int(data[1])
    parent = list(range(n + 1))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    edges = []
    p = 2
    for _ in range(m):
        u = int(data[p]); v = int(data[p + 1]); w = int(data[p + 2]); p += 3
        edges.append((w, u, v))
    edges.sort()
    total = 0
    used = 0
    for w, u, v in edges:
        ru, rv = find(u), find(v)
        if ru == rv:
            continue
        parent[rv] = ru
        total += w
        used += 1
        if used == n - 1:
            break
    print(total if used == n - 1 else -1)
main()
""",
"BIT": """import sys
def main():
    data = sys.stdin.buffer.read().split()
    n = int(data[0]); q = int(data[1])
    bit = [0] * (n + 2)
    for i in range(1, n + 1):
        v = int(data[1 + i])
        j = i
        while j <= n:
            bit[j] += v
            j += j & -j
    out = []
    p = 2 + n
    for _ in range(q):
        op = int(data[p]); a = int(data[p + 1]); b = int(data[p + 2]); p += 3
        if op == 1:
            j = a
            while j <= n:
                bit[j] += b
                j += j & -j
        else:
            def pre(i):
                s = 0
                while i > 0:
                    s += bit[i]
                    i -= i & -i
                return s
            out.append(pre(b) - pre(a - 1))
    sys.stdout.write("".join(str(x) + "\\n" for x in out))
main()
""",
"MAXFLOW": """import sys
from collections import deque
def main():
    data = sys.stdin.buffer.read().split()
    n = int(data[0]); m = int(data[1]); s = int(data[2]); t = int(data[3])
    graph = [[] for _ in range(n + 1)]
    p = 4
    for _ in range(m):
        u = int(data[p]); v = int(data[p + 1]); c = int(data[p + 2]); p += 3
        graph[u].append([v, c, len(graph[v])])
        graph[v].append([u, 0, len(graph[u]) - 1])
    flow = 0
    while True:
        level = [-1] * (n + 1)
        level[s] = 0
        dq = deque([s])
        while dq:
            u = dq.popleft()
            for e in graph[u]:
                if e[1] > 0 and level[e[0]] < 0:
                    level[e[0]] = level[u] + 1
                    dq.append(e[0])
        if level[t] < 0:
            break
        it = [0] * (n + 1)
        sys.setrecursionlimit(10000)
        def dfs(u, limit):
            if u == t:
                return limit
            while it[u] < len(graph[u]):
                e = graph[u][it[u]]
                v = e[0]
                if e[1] > 0 and level[v] == level[u] + 1:
                    d = dfs(v, min(limit, e[1]))
                    if d > 0:
                        e[1] -= d
                        graph[v][e[2]][1] += d
                        return d
                it[u] += 1
            return 0
        while True:
            f = dfs(s, 1 << 60)
            if f == 0:
                break
            flow += f
    print(flow)
main()
""",
"KADANE": """import sys
def main():
    data=sys.stdin.read().split()
    n=int(data[0]); a=list(map(int,data[1:1+n]))
    best=cur=a[0]
    for x in a[1:]:
        cur=max(x,cur+x); best=max(best,cur)
    print(best)
main()
""",
"INVERSION": """import sys
def main():
    d=sys.stdin.read().split(); n=int(d[0]); a=list(map(int,d[1:1+n]))
    cnt=0
    def ms(lo,hi):
        nonlocal cnt
        if hi-lo<=1: return
        mid=(lo+hi)//2; ms(lo,mid); ms(mid,hi)
        i,j,k=lo,mid,lo; buf=[]
        while i<mid and j<hi:
            if a[i]<=a[j]: buf.append(a[i]); i+=1
            else: buf.append(a[j]); j+=1; cnt+=mid-i
        buf+=a[i:mid]; buf+=a[j:hi]
        a[lo:hi]=buf
    ms(0,n); print(cnt)
main()
""",
"ACTIVITY": """import sys
def main():
    d=sys.stdin.read().split(); n=int(d[0]); items=[]
    for i in range(n): items.append((int(d[1+2*i]),int(d[2+2*i])))
    items.sort(key=lambda x:x[1])
    c=0; last=-1
    for s,e in items:
        if s>=last: c+=1; last=e
    print(c)
main()
""",
"KNAPSACK": """import sys
def main():
    d=sys.stdin.read().split(); n=int(d[0]); W=int(d[1])
    dp=[0]*(W+1)
    for i in range(n):
        w=int(d[2+2*i]); v=int(d[3+2*i])
        for c in range(W,w-1,-1): dp[c]=max(dp[c],dp[c-w]+v)
    print(dp[W])
main()
""",
"LCS": """import sys
def main():
    d=sys.stdin.read().split(); a=d[0]; b=d[1]
    n,m=len(a),len(b)
    dp=[[0]*(m+1) for _ in range(n+1)]
    for i in range(1,n+1):
        for j in range(1,m+1):
            dp[i][j]=dp[i-1][j-1]+1 if a[i-1]==b[j-1] else max(dp[i-1][j],dp[i][j-1])
    print(dp[n][m])
main()
""",
"MAZE": """import sys
from collections import deque
def main():
    d=sys.stdin.read().split(); R=int(d[0]); C=int(d[1])
    sx,sy,tx,ty=int(d[2]),int(d[3]),int(d[4]),int(d[5])
    g=d[6:6+R]
    dist=[[-1]*C for _ in range(R)]
    if g[sx][sy]=='.':
        dist[sx][sy]=0; q=deque([(sx,sy)])
        while q:
            x,y=q.popleft()
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                nx,ny=x+dx,y+dy
                if 0<=nx<R and 0<=ny<C and g[nx][ny]=='.' and dist[nx][ny]<0:
                    dist[nx][ny]=dist[x][y]+1; q.append((nx,ny))
    print(dist[tx][ty])
main()
""",
"DIJKSTRA": """import sys, heapq
def main():
    d=sys.stdin.read().split(); n=int(d[0]); m=int(d[1])
    adj=[[] for _ in range(n+1)]
    for i in range(m):
        u,v,w=int(d[2+3*i]),int(d[3+3*i]),int(d[4+3*i])
        adj[u].append((v,w)); adj[v].append((u,w))
    INF=float('inf'); dist=[INF]*(n+1); dist[1]=0; pq=[(0,1)]
    while pq:
        du,u=heapq.heappop(pq)
        if du>dist[u]: continue
        for v,w in adj[u]:
            if du+w<dist[v]: dist[v]=du+w; heapq.heappush(pq,(dist[v],v))
    print(' '.join('-1' if dist[i]==INF else str(dist[i]) for i in range(1,n+1)))
main()
""",
"DSU": """import sys
def main():
    d=sys.stdin.read().split(); n=int(d[0]); m=int(d[1])
    p=list(range(n+1))
    def find(x):
        while p[x]!=x: p[x]=p[p[x]]; x=p[x]
        return x
    for i in range(m):
        u,v=int(d[2+2*i]),int(d[3+2*i])
        ru,rv=find(u),find(v)
        if ru!=rv: p[rv]=ru
    print(len({find(i) for i in range(1,n+1)}))
main()
""",
"KMP": """import sys
def main():
    d=sys.stdin.read().split(); s=d[0]; p=d[1]
    if not p: print(0); return
    pi=[0]*len(p); k=0
    for i in range(1,len(p)):
        while k and p[i]!=p[k]: k=pi[k-1]
        if p[i]==p[k]: k+=1
        pi[i]=k
    c=0; k=0
    for ch in s:
        while k and ch!=p[k]: k=pi[k-1]
        if ch==p[k]: k+=1
        if k==len(p): c+=1; k=pi[k-1]
    print(c)
main()
""",
"CUT": """import sys
def main():
    d=sys.stdin.read().split(); n=int(d[0]); m=int(d[1])
    a=list(map(int,d[2:2+n]))
    lo,hi,ans=1,max(a),0
    while lo<=hi:
        mid=(lo+hi)//2
        if sum(x//mid for x in a)>=m: ans=mid; lo=mid+1
        else: hi=mid-1
    print(ans)
main()
""",
}


# ---------------------------------------------------------------------------
# 题目定义
# ---------------------------------------------------------------------------

PROBLEMS = [
    {
        "key": "KADANE",
        "title": "最大子段和",
        "type": "programming",
        "chapter": "ch5",
        "difficulty": 2,
        "topics": ["动态规划"],
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "statement": (
            "给定 n 个整数（可能为负），求一段连续子序列，使其元素之和最大。\n"
            "要求输出这个最大和。若所有数均为负数，答案为其中最大的那个数。"
        ),
        "input_format": "第一行一个整数 n (1 ≤ n ≤ 200000)。第二行 n 个整数 aᵢ (|aᵢ| ≤ 10⁴)。",
        "output_format": "一个整数，表示最大子段和。",
        "constraints": "n ≤ 2×10⁵；时间限制 1s；空间限制 128MB。\n提示：O(n²) 的暴力枚举会超时，请用 Bellman 等式设计 O(n) 的递推。",
        "tags": ["经典", "DP", "第5章"],
        "gen": _max_subarray_gen,
    },
    {
        "key": "INVERSION",
        "title": "逆序对计数",
        "type": "programming",
        "chapter": "ch4",
        "difficulty": 3,
        "topics": ["分治与递归式"],
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "statement": (
            "给定长度为 n 的序列，统计满足 i < j 且 aᵢ > aⱼ 的数对数量（逆序对）。\n"
            "请在归并排序的过程中顺便统计，要求复杂度 O(n log n)。"
        ),
        "input_format": "第一行一个整数 n。第二行 n 个整数。",
        "output_format": "一个整数，逆序对总数。",
        "constraints": "n ≤ 2×10⁵；答案可能超过 32 位整数范围，请使用 long long。",
        "tags": ["分治", "经典", "第4章"],
        "gen": _inversions_gen,
    },
    {
        "key": "ACTIVITY",
        "title": "活动安排问题",
        "type": "programming",
        "chapter": "ch3",
        "difficulty": 2,
        "topics": ["贪心算法"],
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "statement": (
            "有 n 个活动，每个活动有开始时间 s 和结束时间 e。同一时刻只能参加一个活动，\n"
            "且一个活动结束后可以立刻开始下一个（s ≥ 上一个的 e）。求最多能参加多少个活动。"
        ),
        "input_format": "第一行整数 n。接下来 n 行，每行两个整数 s e。",
        "output_format": "一个整数，最多可参加的活动数。",
        "constraints": "n ≤ 3×10³，0 ≤ s < e ≤ 10⁶。\n提示：最早结束时间优先，可用交换论证证明其最优性。",
        "tags": ["贪心", "第3章"],
        "gen": _activity_gen,
    },
    {
        "key": "KNAPSACK",
        "title": "0/1 背包",
        "type": "programming",
        "chapter": "ch5",
        "difficulty": 3,
        "topics": ["动态规划"],
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "statement": (
            "有 n 件物品，第 i 件重量 wᵢ、价值 vᵢ。背包容量 W，每件物品至多选一次，\n"
            "求能装入的最大总价值。"
        ),
        "input_format": "第一行 n W。接下来 n 行，每行 wᵢ vᵢ。",
        "output_format": "一个整数，最大总价值。",
        "constraints": "n ≤ 40，W ≤ 250。\n提示：注意一维数组必须**逆序**枚举容量，否则会退化成完全背包。",
        "tags": ["DP", "经典"],
        "gen": _knapsack_gen,
    },
    {
        "key": "LCS",
        "title": "最长公共子序列",
        "type": "programming",
        "chapter": "ch5",
        "difficulty": 3,
        "topics": ["动态规划"],
        "time_limit_ms": 1500,
        "memory_limit_mb": 256,
        "statement": "给定两个字符串 a、b（仅含小写字母），求它们最长公共子序列的长度。",
        "input_format": "两行，分别为字符串 a 和 b。",
        "output_format": "一个整数，LCS 的长度。",
        "constraints": "|a|, |b| ≤ 3000。",
        "tags": ["DP"],
        "gen": _lcs_gen,
    },
    {
        "key": "MAZE",
        "title": "迷宫最短路",
        "type": "programming",
        "chapter": "ch2",
        "difficulty": 2,
        "topics": ["图的搜索与拓扑排序"],
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "statement": (
            "给定 R×C 的迷宫，'.' 表示可通行，'#' 表示墙。求从起点到终点的最少步数，\n"
            "不可达输出 -1。每步只能上下左右移动一格。"
        ),
        "input_format": "第一行 R C；第二行起点行列；第三行终点行列；接下来 R 行每行 C 个字符。",
        "output_format": "一个整数，最少步数；不可达输出 -1。",
        "constraints": "R, C ≤ 1000。\n提示：BFS 求无权图最短路，DFS 会超时。",
        "tags": ["图论", "BFS"],
        "gen": _maze_gen,
    },
    {
        "key": "DIJKSTRA",
        "title": "单源最短路",
        "type": "programming",
        "chapter": "ch2",
        "difficulty": 4,
        "topics": ["图的搜索与拓扑排序"],
        "time_limit_ms": 1500,
        "memory_limit_mb": 128,
        "statement": (
            "给定 n 个点、m 条边的无向带权图，边权为正整数。求 1 号点到所有点的最短距离，\n"
            "不可达输出 -1。"
        ),
        "input_format": "第一行 n m。接下来 m 行，每行 u v w。",
        "output_format": "一行 n 个整数，依次为 1 号点到各点的最短距离。",
        "constraints": "n ≤ 10⁵，m ≤ 3×10⁵，w ≤ 10³。\n提示：Floyd O(n³) 与 SPFA 都可能超时，请使用堆优化 Dijkstra。",
        "tags": ["图论", "最短路"],
        "gen": _dijkstra_gen,
    },
    {
        "key": "DSU",
        "title": "连通块计数",
        "type": "programming",
        "chapter": "ch7",
        "difficulty": 2,
        "topics": ["并查集"],
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "statement": "给定 n 个点和 m 条无向边，求连通块的个数。",
        "input_format": "第一行 n m。接下来 m 行，每行两个整数 u v。",
        "output_format": "一个整数，连通块数量。",
        "constraints": "n ≤ 5×10⁵，m ≤ 10⁶。",
        "tags": ["并查集"],
        "gen": _dsu_gen,
    },
    {
        "key": "KMP",
        "title": "KMP 模式匹配计数",
        "type": "programming",
        "chapter": "ch10",
        "difficulty": 4,
        "topics": ["字符串匹配 KMP"],
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "statement": "给定主串 s 和模式串 p，统计 p 在 s 中作为连续子串出现的次数（允许重叠）。",
        "input_format": "两行，分别为 s 和 p。",
        "output_format": "一个整数，出现次数。",
        "constraints": "|s| ≤ 10⁶，|p| ≤ 10⁶。\n提示：暴力匹配 O(|s|·|p|) 会超时，请使用 KMP。",
        "tags": ["字符串", "KMP"],
        "gen": _kmp_gen,
    },
    {
        "key": "CUT",
        "title": "木棍切割（二分答案）",
        "type": "programming",
        "chapter": None,
        "difficulty": 3,
        "topics": ["拓展：二分答案"],
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "statement": (
            "有 n 根木棍，长度分别为 aᵢ。要把它们切成等长的 m 段（可以剩下边角料），\n"
            "求每段的最大长度（整数）。"
        ),
        "input_format": "第一行 n m。第二行 n 个整数 aᵢ。",
        "output_format": "一个整数，每段的最大长度。",
        "constraints": "n ≤ 10⁵，aᵢ ≤ 10⁴，m ≤ 10⁶。\n提示：答案具有单调性，可以二分。",
        "tags": ["二分", "贪心"],
        "gen": _cut_gen,
    },
    # ------------------------------------------------------------------
    # 以下题目按授课课件的章节顺序排列（Chapter 2 → Chapter 10）
    # ------------------------------------------------------------------
    {
        "key": "TOPO",
        "title": "课程安排（拓扑排序）",
        "type": "programming",
        "chapter": "ch2",
        "difficulty": 3,
        "topics": ["图的搜索与拓扑排序"],
        "time_limit_ms": 1500,
        "memory_limit_mb": 256,
        "statement": (
            "有 n 门课程，课程 v 必须在课程 u 之后修读（给定 m 条先修关系 u → v）。\n"
            "请给出一个合法的修读顺序；如果存在循环依赖则输出 -1。\n"
            "为了让答案唯一，要求输出所有合法顺序中字典序最小的那一个。"
        ),
        "input_format": "第一行 n m；接下来 m 行，每行两个整数 u v，表示 u 必须在 v 之前。",
        "output_format": "一行 n 个整数，表示字典序最小的拓扑序；有环输出 -1。",
        "constraints": (
            "n ≤ 10⁵，m ≤ 2×10⁵，可能有自环与重边。\n"
            "提示：Kahn 算法 + 小根堆，O(n log n + m)。"
        ),
        "tags": ["图", "拓扑排序", "第2章"],
        "gen": _topo_gen,
    },
    {
        "key": "PARTITION",
        "title": "区间分割（最少教室数）",
        "type": "programming",
        "chapter": "ch3",
        "difficulty": 3,
        "topics": ["贪心算法"],
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "statement": (
            "有 n 节课，第 j 节课占用时间区间 [sⱼ, fⱼ)。同一间教室在同一时刻只能安排一节课，\n"
            "但一节课在 fⱼ 结束、另一节课恰好在 fⱼ 开始时不算冲突。求最少需要的教室数量。"
        ),
        "input_format": "第一行整数 n；接下来 n 行，每行两个整数 s f。",
        "output_format": "一个整数，最少教室数。",
        "constraints": (
            "n ≤ 10⁵，0 ≤ s < f ≤ 10⁷。\n"
            "提示：最少教室数等于区间集合的最大深度（同一时刻最多有多少节课重叠）。"
        ),
        "tags": ["贪心", "扫描线", "第3章"],
        "gen": _partition_gen,
    },
    {
        "key": "LATENESS",
        "title": "最小化最大延迟",
        "type": "programming",
        "chapter": "ch3",
        "difficulty": 3,
        "topics": ["贪心算法"],
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "statement": (
            "有一台机器和 n 个任务，任务 j 需要 tⱼ 的处理时间、要求在 dⱼ 之前完成。\n"
            "机器从 0 时刻开始、不空闲地依次执行所有任务（可以任意决定顺序）。\n"
            "任务 j 的延迟为 ℓⱼ = max(0, fⱼ - dⱼ)，其中 fⱼ 是它的完成时刻。\n"
            "请安排执行顺序，使最大延迟 L = max ℓⱼ 最小，输出这个最小值。"
        ),
        "input_format": "第一行整数 n；接下来 n 行，每行两个整数 t d。",
        "output_format": "一个整数，最小的最大延迟（可以为负，表示全部提前完成）。",
        "constraints": (
            "n ≤ 10⁵，1 ≤ t ≤ 10³，|d| ≤ 10⁸。\n"
            "提示：最早截止期优先（EDF），可用交换论证证明最优。"
        ),
        "tags": ["贪心", "调度", "第3章"],
        "gen": _lateness_gen,
    },
    {
        "key": "CLOSEST",
        "title": "平面最近点对",
        "type": "programming",
        "chapter": "ch4",
        "difficulty": 4,
        "topics": ["分治与递归式"],
        "time_limit_ms": 1500,
        "memory_limit_mb": 256,
        "statement": (
            "给定平面上的 n 个点，求最近两点之间距离的平方（用整数输出，避免浮点误差）。"
        ),
        "input_format": "第一行整数 n（n ≥ 2）；接下来 n 行，每行两个整数 x y。",
        "output_format": "一个整数，最近点对距离的平方。",
        "constraints": (
            "2 ≤ n ≤ 1.2×10⁵，|x|, |y| ≤ 10⁷，允许坐标重复。\n"
            "提示：暴力 O(n²) 会超时，请用分治 + 按 y 排序的带状区域剪枝。"
        ),
        "tags": ["分治", "几何", "第4章"],
        "gen": _closest_gen,
    },
    {
        "key": "EDITDIST",
        "title": "编辑距离（序列对齐）",
        "type": "programming",
        "chapter": "ch5",
        "difficulty": 3,
        "topics": ["动态规划"],
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "statement": (
            "给定两个非空字符串 a、b，允许的操作为插入一个字符、删除一个字符、替换一个字符，\n"
            "每次操作代价为 1。求把 a 变成 b 所需的最小代价（编辑距离）。"
        ),
        "input_format": "两行，分别为字符串 a 和 b（仅含可见 ASCII 字符，长度 ≥ 1）。",
        "output_format": "一个整数，编辑距离。",
        "constraints": "|a|, |b| ≤ 400。\n提示：按序列对齐定义 OPT(i, j)，注意替换操作也不能漏。",
        "tags": ["DP", "序列对齐", "第5章"],
        "gen": _edit_gen,
    },
    {
        "key": "MST",
        "title": "最小生成树（Kruskal）",
        "type": "programming",
        "chapter": "ch7",
        "difficulty": 3,
        "topics": ["并查集"],
        "time_limit_ms": 1500,
        "memory_limit_mb": 256,
        "statement": (
            "给定 n 个点和 m 条无向带权边，求最小生成树的边权之和；图不连通时输出 -1。"
        ),
        "input_format": "第一行 n m；接下来 m 行，每行三个整数 u v w。",
        "output_format": "一个整数，最小生成树的总权值；不连通输出 -1。",
        "constraints": (
            "n ≤ 10⁵，m ≤ 2×10⁵，0 ≤ w ≤ 10⁹。\n"
            "提示：按边权排序后用并查集判断是否成环，O(m log m)。"
        ),
        "tags": ["并查集", "MST", "第7章"],
        "gen": _mst_gen,
    },
    {
        "key": "SEGTREE",
        "title": "区间加与区间求和（线段树）",
        "type": "programming",
        "chapter": "ch8",
        "difficulty": 4,
        "topics": ["线段树"],
        "time_limit_ms": 1500,
        "memory_limit_mb": 256,
        "statement": (
            "维护一个长度为 n 的整数序列，支持两种操作：\n"
            "  1 l r x：把区间 [l, r] 内的每个数都加上 x；\n"
            "  2 l r  ：询问区间 [l, r] 的元素之和。"
        ),
        "input_format": (
            "第一行 n q；第二行 n 个整数；接下来 q 行，每行一个操作（格式见题意）。"
        ),
        "output_format": "对每个 2 操作输出一行，即区间和。",
        "constraints": (
            "n, q ≤ 2×10⁵，|元素| ≤ 10³，|x| ≤ 10³。\n"
            "提示：逐元素修改是 O(n) 每次、会超时；需要用带懒标记的线段树。"
        ),
        "tags": ["线段树", "懒标记", "第8章"],
        "gen": _segtree_gen,
    },
    {
        "key": "BIT",
        "title": "单点修改与区间求和（树状数组）",
        "type": "programming",
        "chapter": "ch9",
        "difficulty": 3,
        "topics": ["树状数组"],
        "time_limit_ms": 1000,
        "memory_limit_mb": 256,
        "statement": (
            "维护一个长度为 n 的整数序列，支持两种操作：\n"
            "  1 i x：把 aᵢ 增加 x；\n"
            "  2 l r：询问区间 [l, r] 的元素之和。"
        ),
        "input_format": (
            "第一行 n q；第二行 n 个整数；接下来 q 行，每行一个操作（格式见题意）。"
        ),
        "output_format": "对每个 2 操作输出一行，即区间和。",
        "constraints": (
            "n, q ≤ 2×10⁵，|元素|, |x| ≤ 10³。\n"
            "提示：lowbit 维护前缀和，单次操作 O(log n)。"
        ),
        "tags": ["树状数组", "第9章"],
        "gen": _bit_gen,
    },
    {
        "key": "MAXFLOW",
        "title": "最大流",
        "type": "programming",
        "chapter": "ch6",
        "difficulty": 4,
        "topics": ["网络流"],
        "time_limit_ms": 1500,
        "memory_limit_mb": 256,
        "statement": (
            "给定一个容量网络：n 个点、m 条有向边，每条边有非负容量，给定源点 s 与汇点 t。\n"
            "求从 s 到 t 的最大流值。"
        ),
        "input_format": "第一行 n m s t；接下来 m 行，每行三个整数 u v c，表示 u → v 的容量为 c。",
        "output_format": "一个整数，最大流值。",
        "constraints": (
            "n ≤ 5×10⁴，m ≤ 10⁵，0 ≤ c ≤ 10⁵，s ≠ t。\n"
            "提示：注意反向边（退流）必须要建，否则得到的不是最大流。"
        ),
        "tags": ["网络流", "最大流", "第6章"],
        "gen": _maxflow_gen,
    },
]


# ---------------------------------------------------------------------------
# 主观题（互评题）
# ---------------------------------------------------------------------------

RUBRIC_STANDARD = [
    {"key": "idea", "name": "算法思想与建模", "max": 30, "desc": "问题抽象是否准确、思路是否清晰、方案是否可行"},
    {"key": "complexity", "name": "复杂度分析", "max": 25, "desc": "时间/空间复杂度推导是否正确，是否区分最好/最坏/平均"},
    {"key": "correctness", "name": "正确性论证", "max": 25, "desc": "证明是否完整，边界条件是否讨论"},
    {"key": "writing", "name": "表达与规范", "max": 20, "desc": "结构完整、术语准确、图文/伪代码规范"},
]

SUBJECTIVE = [
    {
        "title": "算法分析题：最大子段和的三种解法对比",
        "type": "analysis",
        "chapter": "ch5",
        "difficulty": 3,
        "topics": ["动态规划", "渐近分析与复杂度"],
        "statement": (
            "最大子段和问题有三种经典解法：暴力枚举、分治、动态规划（Kadane）。\n\n"
            "请完成以下任务：\n"
            "1. 写出三种算法的伪代码，并分别给出时间与空间复杂度（说明推导过程）；\n"
            "2. 设计一个实验方案：如何在本地测量三种算法的实际运行时间？\n"
            "   说明输入规模 n 的选取、重复次数、计时方法以及如何避免计时误差；\n"
            "3. 预测 n = 10³、10⁴、10⁵ 时三者的耗时比值，并说明你的预测依据；\n"
            "4. 讨论：在什么场景下分治解法反而比 DP 更有优势？"
        ),
        "sections": [
            {"key": "pseudocode", "name": "伪代码与复杂度推导", "hint": "三种算法各写一段伪代码，并写出复杂度推导步骤"},
            {"key": "experiment", "name": "实验设计方案", "hint": "说明输入规模、重复次数、计时方法与误差控制"},
            {"key": "prediction", "name": "复杂度增长预测", "hint": "给出不同 n 下的耗时比值预测与依据"},
            {"key": "discussion", "name": "适用场景讨论", "hint": "分治 vs DP 的取舍分析"},
        ],
    },
    {
        "title": "证明题：活动安排问题的贪心正确性",
        "type": "proof",
        "chapter": "ch3",
        "difficulty": 4,
        "topics": ["贪心算法"],
        "statement": (
            "活动安排问题：给定 n 个活动的时间区间 [sᵢ, eᵢ)，选择最多的两两不重叠活动。\n"
            "贪心策略为：按结束时间 e 升序排序，依次选择与已选活动不冲突的活动。\n\n"
            "请证明该贪心算法的最优性，要求：\n"
            "1. 用**交换论证法（exchange argument）**证明贪心选择性质；\n"
            "2. 说明最优子结构性质，并写出归纳证明的框架；\n"
            "3. 举出至少一个「按开始时间排序」或「按持续时间排序」会失败的反例，\n"
            "   画出时间轴并说明贪心在这里为什么失效。"
        ),
        "sections": [
            {"key": "exchange", "name": "交换论证证明", "hint": "构造性证明：把最优解改造成包含贪心首选项的解且不更差"},
            {"key": "substructure", "name": "最优子结构与归纳", "hint": "写出归纳假设与递推框架"},
            {"key": "counterexample", "name": "失败反例", "hint": "给出具体数据与时间轴说明"},
        ],
    },
    {
        "title": "开放性设计题：有向图环检测",
        "type": "open",
        "chapter": "ch2",
        "difficulty": 3,
        "topics": ["图的搜索与拓扑排序"],
        "statement": (
            "请设计判断一个有向图是否存在环的算法，至少给出两种不同的思路，并比较它们：\n"
            "1. 基于 DFS 的三色标记法；\n"
            "2. 基于 Kahn 拓扑排序（入度法）。\n\n"
            "要求分析：时间复杂度、空间复杂度、对「自环」「重边」「非连通图」的鲁棒性、\n"
            "递归深度风险，以及如何输出一个具体的环。"
        ),
        "sections": [
            {"key": "dfs_idea", "name": "DFS 三色标记法", "hint": "说明颜色状态含义与回溯过程"},
            {"key": "kahn_idea", "name": "Kahn 拓扑排序法", "hint": "说明入度数组与队列的作用"},
            {"key": "compare", "name": "对比与边界讨论", "hint": "复杂度、鲁棒性、递归风险、如何输出环"},
        ],
    },
    {
        "title": "算法设计报告：两种背包的状态设计",
        "type": "open",
        "chapter": "ch5",
        "difficulty": 4,
        "topics": ["动态规划"],
        "statement": (
            "0/1 背包与完全背包的状态转移只差一个枚举方向，但语义完全不同。\n\n"
            "请完成：\n"
            "1. 分别定义状态 dp[j] 的语义（要精确到「前 i 件物品」还是「已考虑若干件」）；\n"
            "2. 推导两者的转移方程，并解释为什么 0/1 背包必须逆序枚举容量；\n"
            "3. 用「无后效性」与「阶段划分」两个角度论证一元数组做法的正确性；\n"
            "4. 若要求输出具体方案（选了哪些物品），需要怎样修改算法？给出复杂度变化。"
        ),
        "sections": [
            {"key": "state", "name": "状态定义", "hint": "精确写出 dp 数组每一维的含义"},
            {"key": "transition", "name": "转移方程与枚举方向", "hint": "解释逆序/顺序枚举的本质区别"},
            {"key": "proof", "name": "无后效性与正确性论证", "hint": "用阶段划分证明一元数组的正确性"},
            {"key": "scheme", "name": "方案输出扩展", "hint": "讨论如何回溯方案及复杂度变化"},
        ],
    },
    {
        "title": "主定理应用：Karatsuba 与 Strassen 的复杂度推导",
        "type": "analysis",
        "chapter": "ch4",
        "difficulty": 4,
        "topics": ["分治与递归式"],
        "statement": (
            "课件 Chapter 4-2 用主定理分析了整数乘法与矩阵乘法的分治改进。请完成：\n\n"
            "1. 写出主定理的三种情形（含条件与结论）；\n"
            "2. 用主定理求解下列递归式（写出 a、b、f(n) 并说明落在哪种情形）：\n"
            "   (a) T(n) = 3T(n/2) + 5n；(b) T(n) = 48T(n/4) + n³；\n"
            "   (c) T(n) = 2T(n/2) + n log n；(d) T(n) = T(n/5) + T(7n/10) + n；\n"
            "3. Karatsuba 把 n 位整数乘法从 Θ(n²) 降到 Θ(n^1.585)，说明「3 次乘法」是怎么省下来的；\n"
            "4. Strassen 算法的递归式与渐近复杂度是多少？为什么实际工程中很少直接使用它？\n"
            "5. (d) 不能用主定理直接套，请说明理由并给出另一种求解思路。"
        ),
        "sections": [
            {"key": "theorem", "name": "主定理陈述", "hint": "三种情形各自的判定条件与结果"},
            {"key": "solve", "name": "递归式求解", "hint": "(a)~(d) 逐个写出 a、b、f(n) 与结论"},
            {"key": "karatsuba", "name": "Karatsuba 分析", "hint": "说明三次乘法的构造与复杂度推导"},
            {"key": "strassen", "name": "Strassen 与工程取舍", "hint": "递归式、常数因子、数值稳定性"},
            {"key": "ab", "name": "Akra–Bazzi 思路", "hint": "对 (d) 给出不能套主定理的原因与替代解法"},
        ],
    },
    {
        "title": "证明题：最大流最小割定理",
        "type": "proof",
        "chapter": "ch6",
        "difficulty": 5,
        "topics": ["网络流"],
        "statement": (
            "课件 Chapter 6 给出：最大流的值等于最小割的容量。请完成：\n\n"
            "1. 叙述并证明「弱对偶」：任何流的值都不超过任何割的容量；\n"
            "2. 证明「不存在增广路径 ⟺ 当前流是最大流」，并说明如何由此构造一个割 (A, B)，\n"
            "   使该割的容量恰好等于当前流的值；\n"
            "3. 由此得到最大流最小割定理，写出完整的证明链条；\n"
            "4. 解释 Ford-Fulkerson 在整数容量下为什么会终止，并举例说明实数容量时可能不终止、\n"
            "   或容量很大时迭代次数为什么会爆炸；\n"
            "5. 说明「容量缩放」或「最短增广路（Edmonds-Karp）」分别把复杂度改进到了多少。"
        ),
        "sections": [
            {"key": "weak", "name": "弱对偶证明", "hint": "从流的守恒与容量约束出发推导"},
            {"key": "augment", "name": "无增广路即最优", "hint": "构造割 (A,B) 并证明容量等于流值"},
            {"key": "theorem", "name": "定理证明链条", "hint": "串起 1、2 两步得到结论"},
            {"key": "termination", "name": "终止性与反例", "hint": "整数容量终止、实数或大容量退化"},
            {"key": "improve", "name": "复杂度改进", "hint": "容量缩放与最短增广路的复杂度对比"},
        ],
    },
    {
        "title": "分析题：KMP 的均摊复杂度与失配数组构造",
        "type": "analysis",
        "chapter": "ch10",
        "difficulty": 4,
        "topics": ["字符串匹配 KMP"],
        "statement": (
            "课件 Chapter 10 给出了 KMP 匹配与前缀函数（next 数组）。请完成：\n\n"
            "1. 用「前缀 = 后缀且长度最大」的定义，手动求出模式串 ababaca 的 next 数组，写出每一步；\n"
            "2. 为什么 KMP 匹配阶段的时间是 O(|s| + |p|)？请用「j 每次至多加 1」的势能（摊还）分析给出证明；\n"
            "3. 朴素匹配算法为什么是 O(|s| · |p|)？请给出一个让朴素算法达到最坏复杂度的具体输入；\n"
            "4. 如何用 next 数组求一个字符串的**最小循环节**？给出做法并说明正确性；\n"
            "5. 若要统计模式串在主串中出现的所有位置（允许重叠），匹配成功后 j 应当如何处理？"
        ),
        "sections": [
            {"key": "next", "name": "手算 next 数组", "hint": "逐步写出每个位置的前缀函数值"},
            {"key": "amortized", "name": "摊还分析证明", "hint": "用 j 的增减关系说明总比较次数的上界"},
            {"key": "worst", "name": "朴素算法的坏输入", "hint": "构造使每次匹配都推进到末尾才失败的串"},
            {"key": "period", "name": "最小循环节", "hint": "用 n - next[n] 判断周期并说明理由"},
            {"key": "overlap", "name": "重叠匹配处理", "hint": "匹配成功后如何回退 j"},
        ],
    },
    {
        "title": "分析题：并查集的两种启发式与均摊复杂度",
        "type": "analysis",
        "chapter": "ch7",
        "difficulty": 4,
        "topics": ["并查集"],
        "statement": (
            "课件 Chapter 7 用并查集实现了 Kruskal 算法。请完成：\n\n"
            "1. 分别写出 Naïve Linking、Link-by-size、Link-by-rank 三种 Union 策略，\n"
            "   并给出单次 Union / Find 的最坏复杂度（用 Θ 记号）；\n"
            "2. 对朴素链接构造一个让树退化成链的 Union 序列，画出每一步的树形；\n"
            "3. Link-by-size 为什么能把树高控制在 O(log n)？给出归纳证明的思路；\n"
            "4. 加上路径压缩后，为什么单次操作是均摊 O(α(n))？说明 α 的含义与量级；\n"
            "5. Kruskal 算法总复杂度是多少？并查集部分与排序部分各占多少？"
        ),
        "sections": [
            {"key": "strategies", "name": "三种策略与复杂度", "hint": "逐条给出策略描述与最坏复杂度"},
            {"key": "degenerate", "name": "链式退化示例", "hint": "给出 Union 序列并画出树的变化"},
            {"key": "size", "name": "按大小合并的证明", "hint": "归纳论证树高上界 O(log n)"},
            {"key": "compress", "name": "路径压缩与 α(n)", "hint": "说明均摊结论与 α 的量级"},
            {"key": "mst", "name": "Kruskal 总复杂度", "hint": "拆出排序与并查集两部分"},
        ],
    },
    {
        "title": "设计题：线段树与树状数组的选型",
        "type": "open",
        "chapter": "ch8",
        "difficulty": 4,
        "topics": ["线段树", "树状数组"],
        "statement": (
            "课件 Chapter 8、Chapter 9 分别介绍了线段树与树状数组。请围绕「如何选型」完成：\n\n"
            "1. 从支持的操作、常数因子、代码量、内存占用四个维度对比两种数据结构；\n"
            "2. 各给出一个适合线段树、但不适合树状数组的场景，并说明原因；\n"
            "3. 说明线段树为什么需要开到 4n 的空间，给出简要论证；\n"
            "4. 区间加 + 区间求和：树状数组能否做到？如果能，说明做法与复杂度；\n"
            "5. 如果询问改成「区间内元素的最大值，并支持区间赋值」，两种结构各自是否可行？"
        ),
        "sections": [
            {"key": "compare", "name": "四维对比", "hint": "操作集合、常数、代码量、内存"},
            {"key": "scenario", "name": "适用场景", "hint": "各举一个只在其中一种结构上可行的例子"},
            {"key": "space", "name": "4n 空间的论证", "hint": "从递归划分的形状说明最坏下标"},
            {"key": "range_add", "name": "区间加 + 区间和", "hint": "给出树状数组的双数组做法或说明线段树方案"},
            {"key": "assignment", "name": "区间赋值与区间最值", "hint": "讨论可行性与需要的额外信息"},
        ],
    },
    {
        "title": "证明题：从独立集到顶点覆盖的多项式时间规约",
        "type": "proof",
        "chapter": "ch11",
        "difficulty": 5,
        "topics": ["NP 完全性"],
        "statement": (
            "课件 Chapter 11 用多项式时间规约证明了若干问题的 NP 完全性。请完成：\n\n"
            "1. 写出 P、NP、NP 完全、NP 难的定义（NP 要用「证书 + 多项式时间验证」刻画）；\n"
            "2. 证明：图 G 有大小为 k 的独立集 ⟺ G 有大小为 n - k 的顶点覆盖。\n"
            "   请写清两个方向，并说明这个变换是多项式时间的；\n"
            "3. 由此说明 Independent Set ≤p Vertex Cover 且 Vertex Cover ≤p Independent Set；\n"
            "4. 已知 3-SAT 是 NP 完全的，请给出 3-SAT ≤p Independent Set 的构造思路；\n"
            "5. 讨论：为什么「都是 NP 完全」并不意味着它们在实际中一样难解？"
        ),
        "sections": [
            {"key": "defs", "name": "四个基本定义", "hint": "P / NP / NPC / NP-hard，NP 用验证器刻画"},
            {"key": "equiv", "name": "独立集与顶点覆盖的等价", "hint": "两个方向都要写清楚"},
            {"key": "reduce", "name": "双向规约", "hint": "说明变换的多项式时间可构造性"},
            {"key": "sat", "name": "3-SAT 到独立集的构造", "hint": "三元组与冲突边的构造思路"},
            {"key": "practice", "name": "理论与实际的差异", "hint": "实例规模、近似算法、SAT 求解器现状"},
        ],
    },
]
