/** 与业务语义相关的格式化与常量映射。 */

export const VERDICT_TONE = {
  Accepted: 'ok',
  'Wrong Answer': 'danger',
  'Time Limit Exceeded': 'warn',
  'Runtime Error': 'danger',
  'Compile Error': 'neutral',
  'Memory Limit Exceeded': 'warn',
  'Output Limit Exceeded': 'warn',
};

export const VERDICT_ORDER = [
  'Accepted',
  'Wrong Answer',
  'Time Limit Exceeded',
  'Runtime Error',
  'Compile Error',
  'Memory Limit Exceeded',
  'Output Limit Exceeded',
];

export const VERDICT_MEANING = {
  Accepted: '全部测试点通过',
  'Wrong Answer': '输出与期望不一致',
  'Time Limit Exceeded': '运行时间超过限制，通常是复杂度不达标或死循环',
  'Runtime Error': '运行中崩溃：数组越界、栈溢出、除零、空指针等',
  'Compile Error': '编译失败，请查看编译信息',
  'Memory Limit Exceeded': '内存使用超过限制',
  'Output Limit Exceeded': '输出数据量过大',
};

export const PROBLEM_TYPE = {
  programming: '编程题',
  analysis: '算法分析题',
  proof: '证明题',
  open: '开放性问答题',
};

export const ASSIGNMENT_STATUS = {
  draft: '草稿',
  published: '进行中',
  reviewing: '互评中',
  closed: '已结束',
};

export const ANOMALY_TYPE = {
  reviewer_bias: '长期偏高/偏低',
  score_outlier: '单次评分偏离',
  duration_anomaly: '评审时长异常',
  flat_scoring: '评分无区分度',
  all_max: '全部给满分',
  rubric_inconsistent: '评分细则异常',
  reciprocal_pair: '固定互评关系',
  review_cluster: '抱团互评小团体',
};

export const METHOD_LABEL = {
  mean: '算术平均',
  median: '中位数',
  trimmed_mean: '截尾平均',
  weighted_mean: '可信度静态加权',
  robust_huber: 'Huber 稳健估计',
  reliability_em: '可信度动态加权(EM)',
};

export const ALLOC_LABEL = {
  random: '随机分配',
  greedy: '贪心负载均衡',
  mcmf: '最小费用流',
  'mcmf+ls': '最小费用流 + 局部搜索',
};

export function difficultyLabel(d) {
  if (d == null) return '—';
  if (typeof d === 'number') {
    if (d <= 30) return '简单';
    if (d <= 50) return '较易';
    if (d <= 70) return '适中';
    if (d <= 85) return '较难';
    return '很难';
  }
  return d;
}

export function masteryTone(v) {
  if (v >= 80) return 'ok';
  if (v >= 65) return 'brand';
  if (v >= 50) return 'warn';
  return 'danger';
}

/** 判定结果对应的图表颜色（与徽章配色保持一致）。 */
export function verdictColorOf(v) {
  return (
    {
      Accepted: '#17a06a',
      'Wrong Answer': '#c0503f',
      'Time Limit Exceeded': '#c98a1f',
      'Runtime Error': '#b45fa6',
      'Compile Error': '#7b8f87',
      'Memory Limit Exceeded': '#0e9c8c',
      'Output Limit Exceeded': '#5f7f93',
    }[v] || '#5f7f93'
  );
}
