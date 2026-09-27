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
}

PY = {
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
        "difficulty": 2,
        "topics": ["分治", "动态规划"],
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "statement": (
            "给定 n 个整数（可能为负），求一段连续子序列，使其元素之和最大。\n"
            "要求输出这个最大和。若所有数均为负数，答案为其中最大的那个数。"
        ),
        "input_format": "第一行一个整数 n (1 ≤ n ≤ 200000)。第二行 n 个整数 aᵢ (|aᵢ| ≤ 10⁴)。",
        "output_format": "一个整数，表示最大子段和。",
        "constraints": "n ≤ 2×10⁵；时间限制 1s；空间限制 128MB。\n提示：O(n²) 的暴力枚举会超时。",
        "tags": ["经典", "DP", "分治"],
        "gen": _max_subarray_gen,
    },
    {
        "key": "INVERSION",
        "title": "逆序对计数",
        "type": "programming",
        "difficulty": 3,
        "topics": ["分治", "排序"],
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "statement": (
            "给定长度为 n 的序列，统计满足 i < j 且 aᵢ > aⱼ 的数对数量（逆序对）。\n"
            "请在归并排序的过程中顺便统计，要求复杂度 O(n log n)。"
        ),
        "input_format": "第一行一个整数 n。第二行 n 个整数。",
        "output_format": "一个整数，逆序对总数。",
        "constraints": "n ≤ 2×10⁵；答案可能超过 32 位整数范围，请使用 long long。",
        "tags": ["分治", "经典"],
        "gen": _inversions_gen,
    },
    {
        "key": "ACTIVITY",
        "title": "活动安排问题",
        "type": "programming",
        "difficulty": 2,
        "topics": ["贪心"],
        "time_limit_ms": 1000,
        "memory_limit_mb": 128,
        "statement": (
            "有 n 个活动，每个活动有开始时间 s 和结束时间 e。同一时刻只能参加一个活动，\n"
            "且一个活动结束后可以立刻开始下一个（s ≥ 上一个的 e）。求最多能参加多少个活动。"
        ),
        "input_format": "第一行整数 n。接下来 n 行，每行两个整数 s e。",
        "output_format": "一个整数，最多可参加的活动数。",
        "constraints": "n ≤ 3×10³，0 ≤ s < e ≤ 10⁶。\n提示：按结束时间升序排序后贪心选择。",
        "tags": ["贪心"],
        "gen": _activity_gen,
    },
    {
        "key": "KNAPSACK",
        "title": "0/1 背包",
        "type": "programming",
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
        "difficulty": 3,
        "topics": ["动态规划", "字符串匹配"],
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
        "difficulty": 2,
        "topics": ["图搜索", "BFS"],
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
        "difficulty": 4,
        "topics": ["图优化", "最短路"],
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
        "difficulty": 2,
        "topics": ["高级数据结构", "并查集"],
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
        "difficulty": 4,
        "topics": ["字符串匹配", "KMP"],
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
        "difficulty": 3,
        "topics": ["二分查找", "贪心"],
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
        "difficulty": 3,
        "topics": ["分治", "动态规划", "算法分析"],
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
        "difficulty": 4,
        "topics": ["贪心", "正确性证明"],
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
        "difficulty": 3,
        "topics": ["图搜索", "DFS", "拓扑排序"],
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
        "difficulty": 4,
        "topics": ["动态规划", "正确性证明"],
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
]
