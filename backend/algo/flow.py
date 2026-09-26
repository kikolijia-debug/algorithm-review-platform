"""最小费用最大流（Min-Cost Max-Flow, MCMF）。

算法思想
--------
在残量网络上反复寻找「单位费用最小」的增广路，沿该路径推尽可能多的流量，
直到达到流量上限或无增广路为止（连续最短路算法 / successive shortest path）。

每次沿最短路增广后，利用 ``Johnson 势能`` 把可能出现的负权边（反向边）
重新映射为非负权，从而可以安全使用 SPFA / Dijkstra 求解。

复杂度
------
令 ``F`` 为最大流量、``V`` 为点数、``E`` 为边数，SPFA 单次最短路为 O(V·E)，
增广次数不超过 ``E``（每次至少饱和一条边），故整体

    T = O(F · V · E)   （最坏 O(V·E) 次最短路，每次 O(V·E)）
    S = O(V + E)

在本平台的规模下（班级 ≤ 200 人、每人 ~4 份评审，V ≈ 500、E ≈ 10⁴），
一次分配求解耗时在毫秒级。
"""

from __future__ import annotations

from collections import deque


class MinCostMaxFlow:
    """基于 SPFA 连续最短路的 MCMF 求解器（邻接表 + 成对边）。"""

    __slots__ = ("n", "graph", "spfa_rounds", "forward_edges")

    def __init__(self, n: int) -> None:
        self.n = n
        # graph[u] = [ [to, cap, cost, rev_index], ... ]
        self.graph: list[list[list[int]]] = [[] for _ in range(n)]
        self.spfa_rounds = 0
        self.forward_edges: list[tuple[int, int, int]] = []  # (u, v, edge_index_in_graph[u])

    def add_edge(self, u: int, v: int, cap: int, cost: int) -> None:
        """加入一条容量 cap、单位费用 cost 的有向边，并自动建立反向边。"""
        if cap <= 0:
            return
        self.graph[u].append([v, cap, cost, len(self.graph[v])])
        self.graph[v].append([u, 0, -cost, len(self.graph[u]) - 1])
        self.forward_edges.append((u, v, len(self.graph[u]) - 1))

    def _spfa(self, s: int, t: int):
        """返回 (dist, prev_v, prev_e)；若不可达返回 None。"""
        INF = float("inf")
        dist = [INF] * self.n
        in_queue = [False] * self.n
        prev_v = [-1] * self.n
        prev_e = [-1] * self.n
        dist[s] = 0
        dq = deque([s])
        in_queue[s] = True
        while dq:
            u = dq.popleft()
            in_queue[u] = False
            du = dist[u]
            for i, e in enumerate(self.graph[u]):
                v, cap, cost = e[0], e[1], e[2]
                if cap > 0 and du + cost < dist[v]:
                    dist[v] = du + cost
                    prev_v[v] = u
                    prev_e[v] = i
                    if not in_queue[v]:
                        in_queue[v] = True
                        dq.append(v)
        self.spfa_rounds += 1
        if dist[t] == INF:
            return None
        return dist, prev_v, prev_e

    def solve(self, s: int, t: int, max_flow: int | None = None):
        """求解最小费用最大流。

        返回 ``(flow, cost, used_edges)``，其中 ``used_edges`` 为 (u, v, 输送量)
        列表，仅包含正向原始边。
        """
        limit = float("inf") if max_flow is None else max_flow
        total_flow = 0
        total_cost = 0
        while total_flow < limit:
            res = self._spfa(s, t)
            if res is None:
                break
            dist, prev_v, prev_e = res
            # 求瓶颈容量
            push = limit - total_flow
            v = t
            while v != s:
                u, i = prev_v[v], prev_e[v]
                push = min(push, self.graph[u][i][1])
                v = u
            if push <= 0:
                break
            # 沿路径更新残量
            v = t
            while v != s:
                u, i = prev_v[v], prev_e[v]
                e = self.graph[u][i]
                e[1] -= push
                self.graph[v][e[3]][1] += push
                v = u
            total_flow += push
            total_cost += push * dist[t]

        used = []
        for (u, v, idx) in self.forward_edges:
            e = self.graph[u][idx]
            # 反向边的残余流量即为该正向边实际输送的流量
            pushed = self.graph[v][e[3]][1]
            if pushed > 0:
                used.append((u, v, pushed))
        return total_flow, total_cost, used


def min_cost_assignment(cost_matrix: list[list[float]], forbidden: float = float("inf")):
    """当恰好一一匹配时（|行| == |列|）的最小费用完美匹配。

    直接把二分图匹配问题转成 MCMF：源点 → 左侧点（容量 1）→ 右侧点
    （容量 1，费用 cost[i][j]）→ 汇点（容量 1）。

    返回 ``(matching, total_cost)``，``matching[i] = j``；若不存在可行匹配返回
    ``(None, inf)``。
    """
    n = len(cost_matrix)
    if n == 0:
        return [], 0.0
    m = len(cost_matrix[0])
    S, T = 0, n + m + 1
    mcmf = MinCostMaxFlow(n + m + 2)
    for i in range(n):
        mcmf.add_edge(S, 1 + i, 1, 0)
    for j in range(m):
        mcmf.add_edge(1 + n + j, T, 1, 0)
    for i in range(n):
        for j in range(m):
            c = cost_matrix[i][j]
            if c < forbidden:
                mcmf.add_edge(1 + i, 1 + n + j, 1, int(round(c * 1000)))
    flow, cost, used = mcmf.solve(S, T)
    if flow < n:
        return None, float("inf")
    matching = [-1] * n
    for (u, v, amount) in used:
        if 1 <= u <= n and n + 1 <= v <= n + m and amount > 0:
            matching[u - 1] = v - n - 1
    return matching, cost / 1000.0
