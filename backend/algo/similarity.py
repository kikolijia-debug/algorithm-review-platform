"""代码相似性检测（拓展核心问题）。

算法：**Winnowing 指纹 + 倒排索引 + 并查集聚类**

1. **规范化**：去除注释与字符串字面量（保留占位符）、统一空白、可选地把
   标识符按首次出现顺序重命名，从而抵抗变量改名与格式调整；
2. **k-gram 滚动哈希**：对 token 序列取长度 k=5 的窗口，用 Rabin-Karp
   多项式滚动哈希在 O(1) 内得到每个窗口的哈希；
3. **Winnowing 选择**：在宽度 w=4 的滑动窗口中取最小哈希（Karp-Rabin
   指纹），使指纹集合大小与代码长度成常数比例，且对局部插入删除稳健；
4. **倒排索引**：``hash → [submission]``，把两两比对从 O(n²) 降到
   ``O(Σ|F_i| + Σ_q hits(q))``；
5. **相似度**：``Jaccard = |F_i ∩ F_j| / |F_i ∪ F_j|``；
6. **聚类**：在相似度图上用并查集合并超过阈值 τ 的连通分量，得到抄袭簇。

复杂度
------
设提交数 n、第 i 份代码 token 数 L_i、指纹数 |F_i| ≈ 2 L_i / (k + w)：

    T = O(Σ L_i           规范化 + 滚动哈希 + winnowing
          + Σ |F_i|       倒排索引插入
          + Σ_q hits(q)   相似度累计，q 为重复指纹)
      ≈ O(Σ L_i · 平均重复度)
    S = O(Σ |F_i| + n²)   （成对相似度矩阵，n ≤ 500 时可忽略）
"""

from __future__ import annotations

import re
from collections import defaultdict

# ---------------------------------------------------------------------------
# 词法规范化
# ---------------------------------------------------------------------------

CPP_KEYWORDS = {
    "alignas","alignof","asm","auto","bool","break","case","catch","char","class",
    "const","constexpr","continue","decltype","default","delete","do","double",
    "else","enum","explicit","extern","false","float","for","friend","goto","if",
    "inline","int","long","mutable","namespace","new","nullptr","operator","private",
    "protected","public","register","return","short","signed","sizeof","static",
    "struct","switch","template","this","throw","true","try","typedef","typename",
    "union","unsigned","using","virtual","void","volatile","while","cin","cout","endl",
    "vector","string","map","set","queue","stack","pair","sort","push_back","size",
    "begin","end","first","second","scanf","printf","std","max","min","abs",
}

PY_KEYWORDS = {
    "and","as","assert","async","await","break","class","continue","def","del","elif",
    "else","except","False","finally","for","from","global","if","import","in","is",
    "lambda","None","nonlocal","not","or","pass","raise","return","True","try","while",
    "with","yield","print","range","len","int","str","list","dict","set","input",
    "map","sum","min","max","abs","sorted","enumerate","append","split","join",
}


def normalize_source(code: str, language: str = "cpp", rename_identifiers: bool = True) -> list[str]:
    """把源码规范化为 token 序列。``O(L)``"""
    lang = (language or "cpp").lower()
    s = code
    # 去掉块注释与行注释
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.S)
    if lang in ("python", "py"):
        s = re.sub(r"#.*", " ", s)
    else:
        s = re.sub(r"//.*", " ", s)
    # 字符串 / 字符字面量 → 统一占位符（抵抗改名、换内容）
    s = re.sub(r'"(?:\\.|[^"\\])*"', " STR ", s)
    s = re.sub(r"'(?:\\.|[^'\\])*'", " CHR ", s)
    # 数字字面量归一
    s = re.sub(r"\b\d+(\.\d+)?\b", " NUM ", s)
    tokens = re.findall(r"[A-Za-z_]\w*|[+\-*/%=<>!&|^~?:;,.(){}\[\]#]+|NUM|STR|CHR", s)
    tokens = [t for t in tokens if not re.fullmatch(r"\s+", t)]
    if not rename_identifiers:
        return tokens
    keywords = PY_KEYWORDS if lang in ("python", "py") else CPP_KEYWORDS
    mapping: dict[str, str] = {}
    out: list[str] = []
    for t in tokens:
        if re.fullmatch(r"[A-Za-z_]\w*", t) and t not in keywords:
            if t not in mapping:
                mapping[t] = f"v{len(mapping)}"
            out.append(mapping[t])
        else:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# 滚动哈希 + Winnowing
# ---------------------------------------------------------------------------

_BASE = 131
_MOD = (1 << 61) - 1


def kgram_hashes(tokens: list[str], k: int = 5) -> list[int]:
    """Rabin-Karp 多项式滚动哈希。``O(L)``"""
    if len(tokens) < k:
        return []
    tok_id: dict[str, int] = {}
    ids = []
    for t in tokens:
        if t not in tok_id:
            tok_id[t] = len(tok_id) + 1
        ids.append(tok_id[t])
    pow_k = pow(_BASE, k - 1, _MOD)
    h = 0
    out = []
    for i, v in enumerate(ids):
        h = (h * _BASE + v) % _MOD
        if i >= k:
            h = (h - ids[i - k] * pow_k % _MOD) % _MOD
        if i >= k - 1:
            out.append(h)
    return out


def winnow(hashes: list[int], w: int = 4) -> set[int]:
    """Winnowing：每个宽度 w 窗口中取最小哈希作为指纹。``O(L)``

    返回指纹集合（同时保证相邻窗口共享的指纹不会重复计算）。
    """
    if not hashes:
        return set()
    if len(hashes) < w:
        return set(hashes)
    out: set[int] = set()
    last_min_idx = -1
    for i in range(len(hashes) - w + 1):
        mn_idx = i
        for j in range(i + 1, i + w):
            if hashes[j] < hashes[mn_idx]:
                mn_idx = j
        if mn_idx != last_min_idx:
            out.add(hashes[mn_idx])
            last_min_idx = mn_idx
    return out


def fingerprint(code: str, language: str = "cpp", k: int = 5, w: int = 4) -> set[int]:
    return winnow(kgram_hashes(normalize_source(code, language), k), w)


# ---------------------------------------------------------------------------
# 相似度与聚类
# ---------------------------------------------------------------------------


def pairwise_similarity(
    submissions: list[dict],
    threshold: float = 0.55,
    k: int = 5,
    w: int = 4,
) -> dict:
    """用倒排索引计算所有高相似度代码对。

    ``submissions``: ``[{"id": int, "user_id": int, "code": str, "language": str}]``
    """
    fps: dict[int, set[int]] = {}
    inverted: dict[int, list[int]] = defaultdict(list)
    for s in submissions:
        f = fingerprint(s.get("code", ""), s.get("language", "cpp"), k, w)
        fps[s["id"]] = f
        for hh in f:
            inverted[hh].append(s["id"])

    overlap: dict[tuple[int, int], int] = defaultdict(int)
    for hh, ids in inverted.items():
        if len(ids) < 2:
            continue
        if len(ids) > 60:      # 过于常见的指纹（如模板代码）直接忽略
            continue
        ids_sorted = sorted(ids)
        for i in range(len(ids_sorted)):
            for j in range(i + 1, len(ids_sorted)):
                overlap[(ids_sorted[i], ids_sorted[j])] += 1

    pairs = []
    for (a, b), inter in overlap.items():
        fa, fb = fps.get(a) or set(), fps.get(b) or set()
        union = len(fa) + len(fb) - inter
        if union <= 0:
            continue
        sim = inter / union
        if sim >= threshold:
            pairs.append({"a": a, "b": b, "similarity": round(sim, 4), "shared": inter})
    pairs.sort(key=lambda x: -x["similarity"])

    # 并查集聚类
    parent = {s["id"]: s["id"] for s in submissions}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    for p in pairs:
        union(p["a"], p["b"])
    groups: dict[int, list[int]] = defaultdict(list)
    for s in submissions:
        groups[find(s["id"])].append(s["id"])
    clusters = sorted([sorted(v) for v in groups.values() if len(v) > 1], key=len, reverse=True)

    return {
        "pairs": pairs,
        "clusters": clusters,
        "n_submissions": len(submissions),
        "n_fingerprints": {str(k2): len(v) for k2, v in fps.items()},
        "threshold": threshold,
    }


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    u = len(a | b)
    return len(a & b) / u if u else 0.0
