"""核心算法包。

本包集中实现课程大作业要求的核心算法，全部只依赖 Python 标准库：

* ``flow``        : 最小费用最大流（SPFA 增广 + Johnson 势能）
* ``assignment``  : 匿名互评任务分配（流网络建模 + 局部搜索修正）
* ``aggregation`` : 评分聚合（均值 / 截尾 / 中位数 / 可信度动态加权 / EM 估计）
* ``anomaly``     : 异常评审行为检测（残差 z 检验、MAD 时长检测、互评关系图）
* ``ability``     : 学生能力与题目难度的 IRT 联合估计
* ``similarity``  : 代码相似度检测（k-gram 滚动哈希 + Winnowing 指纹 + Jaccard）
* ``complexity``  : 由 (n, t) 实测数据拟合算法复杂度阶
"""

__all__ = [
    "flow",
    "assignment",
    "aggregation",
    "anomaly",
    "ability",
    "similarity",
    "complexity",
]
