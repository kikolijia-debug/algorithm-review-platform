/**
 * 教师端分析类页面：
 *   学习过程分析、能力与难度估计、评审过程管理、异常评审检测、
 *   代码相似度检测、算法实验台。
 */

import { h, clear, esc } from '../core/dom.js';
import { state } from '../core/store.js';
import * as api from '../core/api.js';
import * as router from '../core/router.js';
import { ok, fail, info, confirmDialog } from '../core/toast.js';
import * as U from '../core/ui.js';
import * as C from '../core/charts.js';
import { PROBLEM_TYPE, ANOMALY_TYPE, METHOD_LABEL, ALLOC_LABEL, masteryTone, verdictColorOf } from '../core/format.js';

/* ==================================================== 学习过程分析 */

export async function loadAnalytics() {
  const [klass, knowledge, timeline, ability] = await Promise.all([
    api.get('/api/analytics/class'),
    api.get('/api/analytics/knowledge').catch(() => null),
    api.get('/api/analytics/timeline').catch(() => null),
    api.get('/api/analytics/ability').catch(() => null),
  ]);
  return { klass, knowledge, timeline, ability };
}

export function renderAnalytics({ klass, knowledge, timeline, ability }, container) {
  const tabsBox = h('div');
  const overview = () => {
    const ov = klass.overview;
    const verdicts = klass.verdicts || [];
    const scores = (klass.ranking || []).map((r) => r.score);
    return h(
      'div',
      {},
      h('div', { class: 'stat-row mb16' },
        U.stat(ov.submissions, '提交总数', { tone: 'brand' }),
        U.stat(Math.round(ov.ac_rate * 100) + '%', '整体通过率', { tone: 'ok' }),
        U.stat(ov.students, '学生人数', { tone: 'blue' }),
        U.stat(`${ov.active_students}`, '有提交的学生', { hint: `活跃率 ${Math.round(ov.active_rate * 100)}%`, tone: 'warn' }),
        U.stat(ov.avg_submissions_per_student, '人均提交次数', { tone: 'brand' })),
      h('div', { class: 'grid grid--side' },
        U.card(
          U.cardHead('题目通过率与提交次数', { sub: '点击表头排序，横向滚轮查看更多题目' }),
          U.table(
            [
              { title: '题目', render: (p) => h('div', {}, h('b', {}, p.title), U.tagList(p.topics, 'soft')) },
              { title: '类型', width: '92px', render: (p) => U.badge(PROBLEM_TYPE[p.type] || p.type, p.type === 'programming' ? 'brand' : 'blue') },
              { title: '通过率', width: '170px', render: (p) => h('div', {}, U.progress(p.pass_rate), h('span', { class: 'small muted' }, `${p.ac_count}/${p.students} 人`)) },
              { title: '人均提交', width: '96px', class: 'num', render: (p) => p.avg_tries },
              { title: '最多提交', width: '96px', class: 'num', render: (p) => p.max_tries },
              { title: '平均用时', width: '104px', class: 'num', render: (p) => (p.avg_time_ms ? U.fmtTime(p.avg_time_ms) : '—') },
              { title: '未提交', width: '86px', class: 'num', render: (p) => (p.zero_submit ? h('span', { class: 'tone-warn' }, p.zero_submit) : 0) },
              { title: '', width: '70px', render: (p) => h('button', { class: 'btn btn--plain btn--xs', onclick: () => router.navigate('/problem/' + p.id) }, '查看') },
            ],
            klass.problems,
            { dense: true }
          )
        ),
        h('div', { class: 'col', style: { gap: '16px' } },
          U.card(
            U.cardHead('判定分布', { sub: '整合全部提交' }),
            verdicts.length
              ? C.donutChart(
                  verdicts.map((v) => ({ label: v.verdict, value: v.c, color: verdictColorOf(v.verdict) })),
                  { width: 280, height: 210, centerValue: ov.submissions, centerLabel: '次提交' })
              : U.empty('暂无数据', '')
          ),
          U.card(
            U.cardHead('成绩分布', { sub: '按学生累计得分统计' }),
            scores.length ? C.barChart(
              histogram(scores, 10).map((b) => ({ label: b.x.toFixed(0) + '~', value: b.count })),
              { width: 420, height: 210, tone: 'brand' }
            ) : U.empty('暂无数据', '')
          )
        )),
      h('div', { class: 'grid grid--2 mt16' },
        U.card(
          U.cardHead('常见错误热点', { sub: '低通过率 + 高提交次数 = 教学重点' }),
          klass.error_hotspots.length
            ? U.table(
                [
                  { title: '题目', render: (e) => e.title },
                  { title: '判定', render: (e) => U.verdictBadge(e.verdict) },
                  { title: '次数', class: 'num', render: (e) => e.c },
                ],
                klass.error_hotspots, { dense: true })
            : U.empty('暂无错误记录', '')
        ),
        U.card(
          U.cardHead('学生成绩排名', { sub: `共 ${klass.ranking.length} 人` }),
          U.table(
            [
              { title: '#', width: '50px', render: (r) => r.rank },
              { title: '姓名', render: (r) => h('div', {}, h('b', {}, r.name), h('div', { class: 'small muted' }, r.class_name || '')) },
              { title: '累计得分', width: '100px', class: 'num', render: (r) => Math.round(r.score) },
              { title: '通过次数', width: '90px', class: 'num', render: (r) => r.ac },
              { title: '提交次数', width: '90px', class: 'num', render: (r) => r.submissions },
              { title: '', width: '70px', render: (r) => h('button', { class: 'btn btn--plain btn--xs', onclick: () => router.navigate('/student/report') }, '报告') },
            ],
            klass.ranking.slice(0, 20), { dense: true })
        ))
    );
  };

  const knowledgePane = () => {
    const mastery = (knowledge && knowledge.mastery) || {};
    const perUser = (knowledge && knowledge.per_user) || {};
    const labels = Object.keys(mastery);
    const students = Object.keys(perUser).slice(0, 18);
    const names = {};
    (klass.ranking || []).forEach((r) => (names[r.user_id] = r.name));
    const matrix = students.map((uid) => labels.map((t) => perUser[uid][t] || 0));
    const radarCard = U.card(
      U.cardHead('知识点掌握度（班级平均）', { sub: '按全部编程题提交计算' }),
      labels.length
        ? C.radarChart(labels, labels.map((l) => mastery[l]), { width: 420, height: 340 })
        : U.empty('暂无数据', '')
    );
    const weakList = h(
      'div',
      { class: 'score-list' },
      ...Object.entries(mastery)
        .sort((a, b) => a[1] - b[1])
        .map(([k, v]) =>
          h(
            'div',
            { class: 'score-item' },
            h('span', { class: 'score-item__name', title: k }, k),
            U.meter(v, { tone: masteryTone(v) }),
            h('span', { class: ['score-item__val', 'tone-' + masteryTone(v)] }, String(v))
          )
        )
    );
    const weakCard = U.card(U.cardHead('知识点薄弱排行', { sub: '低于 60 分需要重点讲解' }), weakList);
    const heatCard = U.card(
      U.cardHead('学生 × 知识点 掌握度热力图', { sub: '颜色越深表示掌握越好，可快速发现班级共性问题' }),
      students.length
        ? C.heatmap(matrix, {
            xLabels: labels,
            yLabels: students.map((u) => names[u] || u),
            width: 760,
            height: Math.max(240, students.length * 22 + 60),
          })
        : U.empty('暂无数据', '')
    );
    return h('div', {}, h('div', { class: 'grid grid--side' }, radarCard, weakCard), heatCard);
  };

  const problemPane = () => {
    const sel = h('select', { class: 'input' });
    (klass.problems || []).forEach((p) => sel.appendChild(h('option', { value: p.id }, p.title)));
    const pane = h('div', { class: 'mt16' });
    const loadOne = async (pid) => {
      clear(pane).appendChild(U.loading());
      try {
        const d = await api.get('/api/analytics/problem/' + pid);
        clear(pane);
        pane.appendChild(renderProblemAnalytics(d));
      } catch (e) {
        clear(pane).appendChild(U.empty('加载失败', e.message));
      }
    };
    sel.addEventListener('change', () => loadOne(sel.value));
    if (klass.problems.length) loadOne(klass.problems[0].id);
    return h(
      'div',
      {},
      U.note('通过率看正确性，用时看效率，提交次数看调试成本。'),
      h('div', { class: 'filterbar mt12' }, sel),
      pane
    );
  };

  const timelinePane = () => {
    const subs = (timeline && timeline.submissions) || [];
    return subs.length
      ? U.card(
          U.cardHead('提交活动时间线', { sub: '每日提交次数与通过次数' }),
          C.lineChart(
            [
              { name: '提交次数', values: subs.map((s) => s.n), color: '#3f8fd6' },
              { name: '通过次数', values: subs.map((s) => s.ac), color: '#17a06a' },
            ],
            { xLabels: subs.map((s) => s.d.slice(5)), width: 900, height: 300 }
          )
        )
      : U.empty('暂无数据', '');
  };

  const panes = { overview, problem: problemPane, knowledge: knowledgePane, timeline: timelinePane };
  const show = (k) => {
    clear(tabsBox);
    const r = panes[k]();
    tabsBox.appendChild(r instanceof Node ? r : r);
  };
  const tabBar = U.tabs(
    [
      { key: 'overview', label: '班级总览' },
      { key: 'problem', label: '题目分析' },
      { key: 'knowledge', label: '知识点掌握' },
      { key: 'timeline', label: '提交时间线' },
    ],
    { onChange: show }
  );
  show('overview');
  return h('div', {},
    U.pageHeader('学习过程分析', {
      eyebrow: 'LEARNING ANALYTICS',
      sub: '通过率、提交次数、运行时间与主观题评分的多维统计。',
    }),
    tabBar, tabsBox);
}

function renderProblemAnalytics(d) {
  const p = d.problem;
  const timeHist = (d.time_hist || []).map((b) => ({ label: b.x + '~', value: b.count }));
  return h(
    'div',
    {},
    h('div', { class: 'stat-row mb16' },
      U.stat(Math.round(d.pass_rate * 100) + '%', '通过率', { tone: 'ok', hint: `${d.users.filter((u) => u.solved).length}/${d.students_total} 人` }),
      U.stat(d.users.length, '提交人数', { tone: 'brand' }),
      U.stat(d.tries_to_ac.mean, '平均通过尝试次数', { tone: 'blue' }),
      U.stat(d.tries_to_ac.max, '最多尝试次数', { tone: 'warn' }),
      U.stat(U.fmtTime(d.time_stats.max), '最长运行时间', { tone: 'danger', hint: `时限 ${p.time_limit_ms} ms` })),
    h('div', { class: 'grid grid--2' },
      U.card(U.cardHead('通过所需尝试次数分布'), timeHist.length || d.tries_to_ac.hist.length
        ? C.barChart((d.tries_to_ac.hist || []).map((b) => ({ label: b.x + ' 次', value: b.count })), { width: 420, height: 220, tone: 'brand' })
        : U.empty('暂无数据', '')),
      U.card(U.cardHead('通过提交的耗时分布', { sub: '用于观察是否出现接近时限的实现' }),
        timeHist.length ? C.barChart(timeHist, { width: 420, height: 220, tone: 'blue' }) : U.empty('暂无数据', '')),
      U.card(U.cardHead('运行资源统计'),
        U.kv([
          ['用时中位数', U.fmtTime(d.time_stats.median)],
          ['用时 P95', U.fmtTime(d.time_stats.p95)],
          ['内存中位数', U.fmtMem(d.memory_stats.median)],
          ['内存峰值', U.fmtMem(d.memory_stats.max)],
        ])),
      U.card(U.cardHead('判定分布'),
        Object.keys(d.verdicts).length
          ? C.donutChart(Object.entries(d.verdicts).map(([k, v]) => ({ label: k, value: v, color: verdictColorOf(k) })),
              { width: 260, height: 200, centerValue: Object.values(d.verdicts).reduce((a, b) => a + b, 0), centerLabel: '次提交' })
          : U.empty('暂无数据', ''))),
    U.card(
      U.cardHead('学生明细'),
      U.table(
        [
          { title: '学生', render: (u) => h('div', {}, h('b', {}, u.name), h('div', { class: 'small muted' }, u.class_name || '')) },
          { title: '状态', width: '110px', render: (u) => (u.solved ? U.badge('已通过', 'ok') : U.verdictBadge(u.verdict)) },
          { title: '最佳得分', width: '100px', class: 'num', render: (u) => u.best },
          { title: '提交次数', width: '100px', class: 'num', render: (u) => u.tries },
          { title: '最短用时', width: '110px', class: 'num', render: (u) => U.fmtTime(u.time_ms) },
          { title: '内存', width: '100px', class: 'num', render: (u) => U.fmtMem(u.memory_kb) },
        ],
        d.users, { dense: true, empty: '暂无提交' })
    )
  );
}

function histogram(values, bins = 10) {
  if (!values.length) return [];
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const step = (hi - lo) / bins || 1;
  const out = [];
  for (let i = 0; i < bins; i++) out.push({ x: lo + step * i, count: 0 });
  values.forEach((v) => {
    const i = Math.min(bins - 1, Math.floor((v - lo) / step));
    out[i].count += 1;
  });
  return out;
}

/* ==================================================== 能力与难度估计 */

export async function loadAbility() {
  const [ability, knowledge] = await Promise.all([
    api.get('/api/analytics/ability'),
    api.get('/api/analytics/knowledge').catch(() => null),
  ]);
  return { ability, knowledge };
}

export function renderAbility({ ability, knowledge }) {
  const students = ability.students || [];
  const problems = ability.problems || [];
  const diff = (knowledge && knowledge.difficulty) || {};
  const points = students.map((s) => ({
    x: s.ability || 0, y: s.elo || 0, label: s.name, color: '#0f6b4f',
  }));
  return h(
    'div',
    {},
    U.pageHeader('能力与难度估计', {
      eyebrow: 'IRT / ELO',
      sub: '1PL Rasch 联合估计能力 θ 与难度 b，并与 ELO 对照。',
    }),
    U.note(`基于 ${ability.n_obs || 0} 条首次提交，迭代 ${ability.iters} 次，对数似然 ${ability.loglik}。`
      + 'θ 与 b 只依赖差值，已做中心化。', 'ok'),
    h('div', { class: 'grid grid--side mt16' },
      U.card(
        U.cardHead('学生能力分布', { sub: 'IRT 能力值（0-100 归一化）' }),
        students.length
          ? C.barChart(students.slice(0, 30).map((s) => ({ label: s.name, value: s.ability })), { width: 700, height: 260, tone: 'brand', unit: '' })
          : U.empty('暂无数据', '')
      ),
      U.card(
        U.cardHead('IRT 能力 vs ELO 评分', { sub: '两种估计的一致性检验' }),
        points.length > 2
          ? C.scatterChart(points, { width: 420, height: 280, xLabel: 'IRT 能力值', yLabel: 'ELO 评分', trend: true })
          : U.empty('暂无数据', '')
      )),
    h('div', { class: 'grid grid--2 mt16' },
      U.card(
        U.cardHead('学生能力表', { sub: 'θ 越高表示综合能力越强' }),
        U.table(
          [
            { title: '#', width: '48px', render: (_s, i) => i + 1 },
            { title: '姓名', render: (s) => h('div', {}, h('b', {}, s.name), h('div', { class: 'small muted' }, s.class_name || '')) },
            { title: 'IRT 能力', width: '100px', class: 'num', render: (s) => s.ability },
            { title: 'θ (logit)', width: '100px', class: 'num', render: (s) => (s.theta == null ? '—' : s.theta) },
            { title: 'ELO', width: '90px', class: 'num', render: (s) => (s.elo == null ? '—' : Math.round(s.elo)) },
            { title: '作答数', width: '80px', class: 'num', render: (s) => s.n },
          ],
          students, { dense: true, empty: '暂无数据' })
      ),
      U.card(
        U.cardHead('题目难度与区分度', { sub: 'b 越大越难；a 越大对能力区分越敏感（2PL 模式下）' }),
        U.table(
          [
            { title: '题目', render: (p) => h('div', {}, h('b', {}, p.title),
                diff[String(p.id)] ? h('div', { class: 'small muted' }, `通过率 ${Math.round(diff[String(p.id)].pass_rate * 100)}% · ${diff[String(p.id)].label}`) : null) },
            { title: '难度 b', width: '90px', class: 'num', render: (p) => (p.b == null ? '—' : p.b) },
            { title: '区分度 a', width: '90px', class: 'num', render: (p) => (p.a == null ? '—' : p.a) },
            { title: '难度指数', width: '100px', class: 'num', render: (p) => (p.difficulty == null ? '—' : Math.round(100 - p.difficulty)) },
            { title: 'ELO 难度', width: '100px', class: 'num', render: (p) => (p.elo == null ? '—' : Math.round(p.elo)) },
          ],
          problems, { dense: true, empty: '暂无数据' })
      ))
  );
}

/* ==================================================== 评审过程管理 */

export async function loadReviewAdmin(ctx) {
  const assignments = await api.get('/api/assignments');
  const peer = assignments.filter((a) => a.peer_review);
  const selected = ctx.query.assignment_id || (peer[0] && peer[0].id);
  let allocs = null;
  let results = null;
  let anomalies = null;
  if (selected) {
    [allocs, results, anomalies] = await Promise.all([
      api.get(`/api/assignments/${selected}/allocations`).catch(() => null),
      api.get(`/api/assignments/${selected}/review-results`).catch(() => null),
      api.get('/api/anomalies', { assignment_id: selected }).catch(() => null),
    ]);
  }
  return { assignments: peer, selected, allocs, results, anomalies };
}

export function renderReviewAdmin({ assignments, selected, allocs, results, anomalies }, container) {
  const current = assignments.find((a) => String(a.id) === String(selected));
  const pane = h('div');

  const allocPane = () => {
    const params = {
      method: (current && current.allocate_method) || 'mcmf',
      reviews_per_submission: (current && current.reviews_per_submission) || 3,
      max_load: (current && current.max_load) || 4,
      prev_pair_penalty: 3,
      cross_group_bonus: 4,
      reciprocity_penalty: 2.5,
      variety_weight: 0.8,
      seed: 2026,
    };
    const metricBox = h('div');
    const renderMetrics = (report) => {
      clear(metricBox);
      report.forEach((r) => {
        const m = r.metrics;
        metricBox.appendChild(
          U.card(
            U.cardHead(r.problem_title + ' · 分配结果', {
              sub: `方法：${ALLOC_LABEL[r.method] || r.method} · 求解耗时 ${m.elapsed_ms} ms`,
              actions: r.stats.spfa_rounds != null ? U.badge('SPFA 轮数 ' + r.stats.spfa_rounds, 'neutral') : null,
            }),
            h('div', { class: 'stat-row' },
              U.stat(Math.round(m.coverage * 100) + '%', '覆盖率', { tone: m.coverage >= 1 ? 'ok' : 'warn' }),
              U.stat(`${m.load_min}~${m.load_max}`, '工作量区间', { tone: 'brand' }),
              U.stat(m.gini_load, '负载基尼系数', { tone: m.gini_load < 0.05 ? 'ok' : 'warn', hint: '越小越均衡' }),
              U.stat(m.reciprocal_pairs, '互为评审对', { tone: m.reciprocal_pairs === 0 ? 'ok' : 'danger' }),
              U.stat(Math.round(m.cross_class_ratio * 100) + '%', '跨班比例', { tone: 'blue' }),
              U.stat(m.self_review, '自评次数', { tone: m.self_review ? 'danger' : 'ok' })),
            r.stats.objective_before_ls != null
              ? U.note(`局部搜索把成对目标从 ${r.stats.objective_before_ls} 降到 ${r.stats.objective_after_ls}`
                  + `（接受 ${r.stats.local_search_rounds} 次交换），主要消除了互为评审与班级分布不均。`, 'ok')
              : U.note('未启用局部搜索：可能存在互为评审（A 评 B 且 B 评 A）的固定互评关系。', 'warn')
          )
        );
      });
    };
    if (allocs && allocs.stats.total) {
      renderMetrics([
        {
          problem_title: '当前已生效的分配',
          method: (current && current.allocate_method) || 'mcmf',
          stats: {},
          metrics: {
            coverage: 1, load_min: allocs.stats.load_min, load_max: allocs.stats.load_max,
            gini_load: gini(allocationsLoads()), reciprocal_pairs: 0, cross_class_ratio: 0, self_review: 0,
            elapsed_ms: 0,
          },
        },
      ]);
    }
    function allocationsLoads() {
      const m = {};
      (allocs.allocations || []).forEach((a) => (m[a.reviewer_id] = (m[a.reviewer_id] || 0) + 1));
      return Object.values(m);
    }

    const form = h(
      'div',
      { class: 'grid grid--2', style: { gap: '12px' } },
      U.field('分配算法', U.select([
        { value: 'mcmf', label: '最小费用最大流 + 局部搜索（推荐）' },
        { value: 'greedy', label: '贪心负载均衡（基线）' },
        { value: 'random', label: '随机分配（基线）' },
      ], { value: params.method, onchange: (e) => (params.method = e.target.value) })),
      U.field('每份作业评审数 k', h('input', { class: 'input', type: 'number', min: 1, max: 6, value: params.reviews_per_submission, oninput: (e) => (params.reviews_per_submission = +e.target.value) })),
      U.field('每人最多评审数 c', h('input', { class: 'input', type: 'number', min: 1, max: 10, value: params.max_load, oninput: (e) => (params.max_load = +e.target.value) })),
      U.field('历史重复互评惩罚 α', h('input', { class: 'input', type: 'number', step: '0.5', value: params.prev_pair_penalty, oninput: (e) => (params.prev_pair_penalty = +e.target.value) }), { hint: '越大越倾向于避开上一轮已互相评过的人' }),
      U.field('跨班组权重 β', h('input', { class: 'input', type: 'number', step: '0.5', value: params.cross_group_bonus, oninput: (e) => (params.cross_group_bonus = +e.target.value) }), { hint: '鼓励跨班级分配，降低熟人效应' }),
      U.field('互为评审惩罚 ρ', h('input', { class: 'input', type: 'number', step: '0.5', value: params.reciprocity_penalty, oninput: (e) => (params.reciprocity_penalty = +e.target.value) })),
      U.field('班级分布均衡权重 γ', h('input', { class: 'input', type: 'number', step: '0.2', value: params.variety_weight, oninput: (e) => (params.variety_weight = +e.target.value) })),
      U.field('随机种子', h('input', { class: 'input', type: 'number', value: params.seed, oninput: (e) => (params.seed = +e.target.value) }), { hint: '同一种子结果可复现，便于实验对比' })
    );

    return h(
      'div',
      {},
      U.card(
        U.cardHead('执行匿名互评分配', { sub: '最小费用最大流建模 + 2-opt 局部搜索修正' }),
        U.note('分配约束：每份作业恰好获得 k 份评审、每位评审者工作量不超过 c、禁止自评、'
          + '尽量避开历史互评关系与互为评审，并让每位评审者评到的作业班级分布尽量均匀。', 'ok'),
        h('div', { class: 'mt16' }, form),
        h('div', { class: 'row mt16' },
          U.btn('重新分配', {
            tone: 'primary', icon: U.icon.spark,
            onClick: async (e) => {
              const btn = e.target.closest('button');
              btn.disabled = true;
              const old = btn.textContent;
              btn.textContent = '正在求解…';
              try {
                const r = await api.post(`/api/assignments/${selected}/allocate`, params);
                ok(`分配完成，用时 ${r.elapsed_ms} ms`);
                renderMetrics(r.report);
              } catch (err) { fail(err.message); }
              finally { btn.disabled = false; btn.textContent = old; }
            },
          }),
          U.btn('对当前结果执行评分聚合', {
            tone: 'ghost',
            onClick: async () => {
              info('正在聚合评分并执行异常检测…');
              try {
                const r = await api.post(`/api/assignments/${selected}/aggregate`, { methods: Object.keys(METHOD_LABEL) });
                ok(`聚合完成，共处理 ${r.report.length} 道主观题`);
                router.resolve();
              } catch (err) { fail(err.message); }
            },
          }))
      ),
      h('div', { class: 'mt16' }, metricBox),
      allocs && allocs.allocations.length
        ? U.card(
            U.cardHead('分配明细', {
              sub: `${allocs.stats.total} 条 · 已完成 ${allocs.stats.done} 条 · 待完成 ${allocs.stats.pending} 条`,
              actions: h('span', { class: 'small muted' }, `工作量区间 ${allocs.stats.load_min}~${allocs.stats.load_max}`),
            }),
            C.bipartiteGraph(
              allocs.allocations.slice(0, 220).map((a) => ({ author: a.author_id, reviewer: a.reviewer_id })),
              { width: 900, height: 340, authorLabel: (x) => '作业#' + x, reviewerLabel: (x) => '评审者#' + x }
            ),
            U.table(
              [
                { title: '作业（匿名）', render: (a) => h('span', { class: 'anon-tag' }, a.anon) },
                { title: '作者', render: (a) => a.author_name },
                { title: '评审者', render: (a) => h('div', {}, h('b', {}, a.reviewer_name), h('div', { class: 'small muted' }, a.reviewer_class || '')) },
                { title: '题目', render: (a) => (a.problem_id ? '#' + a.problem_id : '—') },
                { title: '状态', width: '100px', render: (a) => U.badge(a.status === 'done' ? '已完成' : '待评审', a.status === 'done' ? 'ok' : 'warn') },
                { title: '权重', width: '80px', class: 'num', render: (a) => a.weight },
              ],
              allocs.allocations.slice(0, 200), { dense: true })
          )
        : null
    );
  };

  const resultPane = () => {
    if (!results || !results.length) return U.empty('暂无评分结果', '请先在「分配管理」中执行分配，并等待评审完成后聚合。');
    return h('div', {}, ...results.map((r) =>
      h('div', { style: { marginBottom: '16px' } },
        U.card(
          U.cardHead(r.problem_title + ' · 评分结果', { sub: `共 ${r.rows.length} 份提交` }),
          U.table(
            [
              { title: '#', width: '48px', render: (_x, i) => i + 1 },
              { title: '学生', render: (x) => h('div', {}, h('b', {}, x.name), h('div', { class: 'small muted' }, x.class_name || '')) },
              { title: '最终得分', width: '100px', class: 'num', render: (x) => h('b', { style: { color: 'var(--brand)' } }, x.score) },
              { title: '各评审原始分', render: (x) => h('div', { class: 'mono small' }, x.raw.map((v) => v.toFixed(0)).join(' / ')) },
              { title: '极差', width: '80px', class: 'num', render: (x) => (x.spread > 25 ? h('span', { class: 'tone-danger' }, x.spread) : x.spread) },
              { title: '评审数', width: '80px', class: 'num', render: (x) => x.n_reviews },
            ],
            r.rows, { dense: true })
        ))))
      ;
  };

  const reviewerPane = () => {
    if (!results || !results.length) return U.empty('暂无数据', '');
    const r = results[0];
    const stats = r.reviewer_stats || [];
    return h(
      'div',
      {},
      U.note('bias 为宽严偏差（正值偏松），reliability 为一致性权重。', 'ok'),
      U.card(
        U.cardHead('评审者偏差与可信度', { sub: '按 |bias| 降序排列' }),
        h('div', { class: 'grid grid--2' },
          C.barChart(stats.slice(0, 16).map((s) => ({ label: s.name || ('#' + s.reviewer_id), value: Math.abs(s.bias) })), { width: 520, height: 240, tone: 'warn', unit: '' }),
          C.barChart(stats.slice(0, 16).map((s) => ({ label: s.name || ('#' + s.reviewer_id), value: s.reliability })), { width: 520, height: 240, tone: 'brand', unit: '' })),
        U.table(
          [
            { title: '评审者', render: (s) => h('div', {}, h('b', {}, s.name), h('div', { class: 'small muted' }, '#' + s.reviewer_id)) },
            { title: '宽严偏差 b', width: '110px', class: 'num', render: (s) => h('span', { class: s.bias > 4 ? 'tone-warn' : s.bias < -4 ? 'tone-danger' : '' }, s.bias) },
            { title: '可信度权重', width: '110px', class: 'num', render: (s) => s.reliability },
            { title: '评审份数', width: '90px', class: 'num', render: (s) => s.n },
            { title: '一致性', width: '150px', render: (s) => U.meter(Math.round(s.reliability * 50), { tone: s.reliability > 0.9 ? 'ok' : s.reliability > 0.6 ? 'brand' : 'warn' }) },
          ],
          stats, { dense: true })
      ),
      anomalies && anomalies.counts && anomalies.counts.open
        ? U.card(
            U.cardHead('该作业的异常评审', { sub: `${anomalies.counts.open} 条待处理`, actions: h('a', { class: 'btn btn--soft btn--sm', href: '#/teacher/anomalies' }, '去处理') }),
            U.table(
              [
                { title: '级别', width: '90px', render: (a) => U.badge(a.level === 'high' ? '高' : a.level === 'medium' ? '中' : '低', a.level === 'high' ? 'danger' : 'warn') },
                { title: '类型', width: '140px', render: (a) => ANOMALY_TYPE[a.type] || a.type },
                { title: '评审者', width: '110px', render: (a) => a.reviewer_name || '#' + a.reviewer_id },
                { title: '说明', render: (a) => a.detail },
              ],
              anomalies.anomalies.slice(0, 12), { dense: true })
          )
        : null
    );
  };

  const panes = { alloc: allocPane, result: resultPane, reviewer: reviewerPane };
  const show = (k) => {
    clear(pane);
    const node = panes[k]();
    pane.appendChild(node instanceof Node ? node : node);
  };
  const bar = U.tabs(
    [
      { key: 'alloc', label: '分配管理' },
      { key: 'result', label: '评分结果' },
      { key: 'reviewer', label: '可信度与异常' },
    ],
    { onChange: show }
  );
  show('alloc');

  const selector = h(
    'div',
    { class: 'filterbar' },
    U.select(
      assignments.map((a) => ({ value: a.id, label: a.title + '（' + a.problems.length + ' 题）' })),
      { value: selected, onchange: (e) => router.navigate('/teacher/reviews?assignment_id=' + e.target.value) }
    ),
    current ? U.badge(`每份 ${current.reviews_per_submission} 份评审`, 'brand') : null,
    current ? U.badge(`每人最多 ${current.max_load} 份`, 'neutral') : null,
    current ? U.badge(METHOD_LABEL[current.aggregation_method] || current.aggregation_method, 'blue') : null
  );

  return h(
    'div',
    {},
    U.pageHeader('评审过程管理', {
      eyebrow: 'PEER REVIEW OPS',
      sub: '分配方案、评分聚合与可疑评分复核。',
    }),
    selector, bar, pane
  );
}

function gini(values) {
  if (!values.length) return 0;
  const v = [...values].sort((a, b) => a - b);
  const n = v.length;
  const total = v.reduce((a, b) => a + b, 0);
  if (!total) return 0;
  const cum = v.reduce((acc, x, i) => acc + (i + 1) * x, 0);
  return Math.round(((2 * cum) / (n * total) - (n + 1) / n) * 10000) / 10000;
}

/* ==================================================== 异常评审检测 */

export async function loadAnomalies(ctx) {
  const [assignments, data] = await Promise.all([
    api.get('/api/assignments'),
    api.get('/api/anomalies', ctx.query),
  ]);
  return { assignments, data };
}

export function renderAnomalies({ assignments, data }) {
  let level = '';
  let status = '';
  const box = h('div');
  const paint = () => {
    const rows = (data.anomalies || []).filter(
      (a) => (!level || a.level === level) && (!status || a.status === status)
    );
    clear(box);
    box.appendChild(
      U.card(
        U.cardHead('异常记录', { sub: `${rows.length} 条` }),
        U.table(
          [
            { title: '级别', width: '84px', render: (a) => U.badge(a.level === 'high' ? '高' : a.level === 'medium' ? '中' : '低', a.level === 'high' ? 'danger' : a.level === 'medium' ? 'warn' : 'blue') },
            { title: '类型', width: '150px', render: (a) => ANOMALY_TYPE[a.type] || a.type },
            { title: '对象', width: '130px', render: (a) => h('div', {}, h('b', {}, a.reviewer_name || ('#' + a.reviewer_id)), h('div', { class: 'small muted' }, a.class_name || '')) },
            { title: '说明', render: (a) => h('div', {}, h('div', {}, a.title), h('div', { class: 'small muted' }, a.detail)) },
            { title: '建议', width: '230px', render: (a) => h('span', { class: 'small muted' }, a.suggestion) },
            { title: '状态', width: '100px', render: (a) => U.badge(
                { open: '待复核', confirmed: '已确认', dismissed: '已排除', adjusted: '已修正' }[a.status] || a.status,
                a.status === 'open' ? 'warn' : a.status === 'dismissed' ? 'neutral' : 'ok') },
            { title: '', width: '150px', render: (a) => h('div', { class: 'row', style: { gap: '4px' } },
                U.btn('确认', { tone: 'soft', size: 'xs', onClick: () => handle(a, 'confirmed') }),
                U.btn('排除', { tone: 'plain', size: 'xs', onClick: () => handle(a, 'dismissed') }),
                U.btn('降权', { tone: 'ghost', size: 'xs', onClick: () => handle(a, 'adjusted', 0.3) })) },
          ],
          rows, { dense: true, empty: '没有符合条件的异常记录' })
      )
    );
  };
  const handle = async (a, st, weight) => {
    const note = st === 'dismissed' ? '教师复核后判定为正常' : st === 'adjusted' ? '教师复核后下调该评审者权重' : '教师复核确认异常';
    try {
      await api.post(`/api/anomalies/${a.id}/handle`, { status: st, note, adjust_weight: weight });
      a.status = st;
      ok(st === 'dismissed' ? '已标记为「已排除」' : st === 'adjusted' ? '已下调该评审者权重' : '已确认异常');
      paint();
    } catch (e) { fail(e.message); }
  };
  paint();
  const risk = (data.reviewer_risk || []).slice(0, 12);
  return h(
    'div',
    {},
    U.pageHeader('异常评审检测', {
      eyebrow: 'ANOMALY DETECTION',
      sub: '长期偏高/偏低、单次偏离、异常时长、无区分度与固定互评关系。',
    }),
    h('div', { class: 'stat-row mb16' },
      U.stat(data.counts.high, '高风险', { tone: 'danger' }),
      U.stat(data.counts.medium, '中风险', { tone: 'warn' }),
      U.stat(data.counts.low, '低风险', { tone: 'blue' }),
      U.stat(data.counts.open, '待处理', { tone: 'brand' })),
    risk.length
      ? U.card(
          U.cardHead('评审者风险汇总', { sub: '风险分 = Σ 异常权重（高 22 / 中 11 / 低 4），≥45 为高风险' }),
          h('div', { class: 'grid grid--2' },
            C.barChart(risk.map((r) => ({ label: r.reviewer_name || ('#' + r.reviewer_id), value: r.risk })), { width: 520, height: 250, tone: 'danger', unit: '' }),
            U.table(
              [
                { title: '评审者', render: (r) => h('div', {}, h('b', {}, r.reviewer_name), h('div', { class: 'small muted' }, r.class_name || '')) },
                { title: '风险分', width: '90px', class: 'num', render: (r) => r.risk },
                { title: '等级', width: '80px', render: (r) => U.badge(r.level, r.level === '高' ? 'danger' : r.level === '中' ? 'warn' : 'neutral') },
                { title: '异常数', width: '80px', class: 'num', render: (r) => r.count },
                { title: '类型', render: (r) => U.tagList(r.types.map((t) => ANOMALY_TYPE[t] || t), 'soft') },
              ],
              risk, { dense: true })
          )
        )
      : null,
    h('div', { class: 'filterbar mt16' },
      U.select([{ value: '', label: '全部级别' }, { value: 'high', label: '高风险' }, { value: 'medium', label: '中风险' }, { value: 'low', label: '低风险' }],
        { onchange: (e) => { level = e.target.value; paint(); } }),
      U.select([{ value: '', label: '全部状态' }, { value: 'open', label: '待复核' }, { value: 'confirmed', label: '已确认' }, { value: 'dismissed', label: '已排除' }, { value: 'adjusted', label: '已修正' }],
        { onchange: (e) => { status = e.target.value; paint(); } })),
    box
  );
}

/* ==================================================== 代码相似度 */

export async function loadSimilarity(ctx) {
  const [problems, data] = await Promise.all([
    api.get('/api/problems', { type: 'programming' }),
    api.get('/api/similarity', ctx.query),
  ]);
  return { problems, data };
}

export function renderSimilarity({ problems, data }) {
  const thresholdBox = h('input', { class: 'input', type: 'number', step: '0.05', min: '0.1', max: '0.95', value: '0.6', onchange: (e) => router.navigate('/teacher/similarity?' + new URLSearchParams({ ...router.currentRoute().query, threshold: e.target.value })) });
  const pairs = data.pairs || [];
  return h(
    'div',
    {},
    U.pageHeader('代码相似度检测', {
      eyebrow: 'PLAGIARISM DETECTION',
      sub: 'Winnowing 指纹 + 倒排索引 + 并查集聚类。',
    }),
    U.note('对变量改名、加注释、调格式几乎免疫；对深度重写灵敏度有限，需结合语法树或语义方法。', 'ok'),
    h('div', { class: 'filterbar mt12 mb16' },
      U.select([{ value: '', label: '全部题目' }, ...problems.map((p) => ({ value: p.id, label: p.title }))],
        { value: router.currentRoute().query.problem_id || '', onchange: (e) => router.navigate('/teacher/similarity?' + new URLSearchParams({ ...router.currentRoute().query, problem_id: e.target.value })) }),
      h('span', { class: 'small muted' }, '相似度阈值'),
      thresholdBox,
      h('span', { class: 'small muted' }, `共检测 ${data.n_submissions || 0} 份代码，命中 ${pairs.length} 对`)),
    h('div', { class: 'grid grid--side' },
      U.card(
        U.cardHead('高相似代码对', { sub: `阈值 ${data.threshold}` }),
        pairs.length
          ? h('div', {}, ...pairs.slice(0, 40).map((p) =>
              h('div', { class: 'sim-pair' },
                h('span', { class: 'grow' }, h('b', {}, p.a_name || ('#' + p.a)), ' ↔ ', h('b', {}, p.b_name || ('#' + p.b))),
                h('span', { class: 'sim-pair__bar' }, U.meter(Math.round(p.similarity * 100), { tone: p.similarity > 0.85 ? 'danger' : p.similarity > 0.7 ? 'warn' : 'brand' })),
                h('span', { class: ['sim-pair__score', p.similarity > 0.85 ? 'sim-high' : p.similarity > 0.7 ? 'sim-mid' : 'sim-low'] }, (p.similarity * 100).toFixed(1) + '%'))))
          : U.empty('未发现高相似代码', '可以降低阈值重新检测，或换一道题试试。')
      ),
      U.card(
        U.cardHead('相似代码簇', { sub: '并查集连通分量，规模 ≥ 2' }),
        (data.clusters || []).length
          ? h('div', { class: 'col', style: { gap: '10px' } }, ...data.clusters.map((c, i) =>
              h('div', { class: 'list-row' },
                h('span', { class: 'badge badge--danger' }, '簇 ' + (i + 1)),
                h('span', { class: 'grow small' }, c.map((x) => (pairs.find((p) => p.a === x) ? '' : '') + '#' + x).join('、')),
                U.badge(c.length + ' 份', 'warn'))))
          : U.empty('没有形成相似簇', '')
      ))
  );
}

/* ==================================================== 算法实验台 */

export async function loadExperiments() {
  const [meta, history] = await Promise.all([api.get('/api/meta'), api.get('/api/experiments')]);
  return { meta, history };
}

export function renderExperiments({ meta, history }) {
  const experiments = meta.experiments || [];
  let current = experiments[0];
  const values = {};
  const paramsBox = h('div', { class: 'form-grid' });
  const out = h('div');
  const inputBox = h('div', { class: 'card', style: { marginBottom: '16px' } });

  const paintParams = () => {
    clear(paramsBox);
    (current.params || []).forEach((p) => {
      values[p.key] = p.default;
      paramsBox.appendChild(
        U.field(p.label, h('input', {
          class: 'input', type: 'number', step: p.type === 'float' ? '0.5' : '1',
          min: p.min, max: p.max, value: p.default,
          oninput: (e) => (values[p.key] = p.type === 'float' ? parseFloat(e.target.value) : parseInt(e.target.value, 10)),
        }), { hint: p.min != null ? `取值范围 ${p.min} ~ ${p.max}` : '' })
      );
    });
    if (!(current.params || []).length) {
      paramsBox.appendChild(U.note('该实验无需参数，直接点击「运行实验」即可。'));
    }
  };

  const listBox = h('div', { class: 'exp-list' });
  experiments.forEach((e) => {
    const item = h(
      'div',
      {
        class: ['exp-item', e.key === current.key ? 'is-active' : ''],
        onclick: () => {
          current = e;
          Array.from(listBox.children).forEach((c) => c.classList.remove('is-active'));
          item.classList.add('is-active');
          clear(out);
          paintParams();
          paintHead();
        },
      },
      h('b', {}, e.name),
      h('span', {}, e.desc)
    );
    listBox.appendChild(item);
  });
  paintParams();

  const headBox = h('div');
  function paintHead() {
    clear(inputBox);
    inputBox.appendChild(
      U.card(
        U.cardHead(current.name, {
          sub: current.desc,
          actions: U.btn('运行实验', {
            tone: 'primary', icon: U.icon.play,
            onClick: async (e) => {
              const btn = e.target.closest('button');
              btn.disabled = true;
              clear(out).appendChild(U.loading('正在运行实验，复杂度实验需要真实编译运行程序，请稍候…'));
              try {
                const r = await api.post('/api/experiments/run', { key: current.key, params: values });
                clear(out);
                out.appendChild(renderExperimentResult(r));
                ok(`实验完成，用时 ${r.elapsed_ms} ms`);
              } catch (err) {
                clear(out).appendChild(U.empty('实验失败', err.message));
              } finally { btn.disabled = false; }
            },
          }),
        }),
        paramsBox
      )
    );
  }
  paintHead();

  return h(
    'div',
    {},
    U.pageHeader('算法实验台', {
      eyebrow: 'ALGORITHM LAB',
      sub: '每组实验给出指标对比、图表与结论，结果可导出。',
    }),
    h('div', { class: 'exp-panel' },
      h('div', {}, U.card(U.cardHead('实验列表', { sub: `${experiments.length} 组` }), listBox)),
      h('div', {}, inputBox, out))
  );
}

function renderExperimentResult(r) {
  const rows = r.rows || [];
  const head = h(
    'div',
    { class: 'card', style: { marginBottom: '14px' } },
    U.cardHead(r.title, { sub: `参数：${JSON.stringify(r.params || {})}`, actions: U.badge(`耗时 ${r.elapsed_ms} ms`, 'brand') }),
    h('div', { class: 'conclusion' }, r.conclusion || '')
  );
  const children = [head];
  const metrics = r.metrics || [];
  const isPrimary = (k) => ['f1', 'rmse', 'gini_load', 'f1_score'].includes(k);

  if (r.experiment === 'allocation') {
    children.push(
      U.card(
        U.cardHead('分配算法指标对比'),
        U.table(
          [
            { title: '方法', render: (x) => h('b', {}, x.label) },
            { title: '覆盖率', class: 'num', render: (x) => Math.round(x.coverage * 100) + '%' },
            { title: '负载区间', class: 'num', render: (x) => `${x.load_min}~${x.load_max}` },
            { title: '负载基尼', class: 'num', render: (x) => h('span', { class: x.gini_load < 0.05 ? 'tone-ok' : 'tone-warn' }, x.gini_load) },
            { title: '互为评审', class: 'num', render: (x) => h('span', { class: x.reciprocal_pairs === 0 ? 'tone-ok' : 'tone-danger' }, x.reciprocal_pairs) },
            { title: '跨班比例', class: 'num', render: (x) => Math.round(x.cross_class_ratio * 100) + '%' },
            { title: '自评', class: 'num', render: (x) => x.self_review },
            { title: '求解耗时', class: 'num', render: (x) => x.elapsed_ms.toFixed(1) + ' ms' },
          ],
          rows
        )
      ),
      h('div', { class: 'grid grid--2 mt16' },
        U.card(U.cardHead('负载均衡（基尼系数，越小越好）'),
          C.barChart(rows.map((x) => ({ label: x.label, value: x.gini_load })), { width: 480, height: 240, tone: 'brand' })),
        U.card(U.cardHead('互为评审对数量（越小越好）'),
          C.barChart(rows.map((x) => ({ label: x.label, value: x.reciprocal_pairs })), { width: 480, height: 240, tone: 'danger' }))),
      U.card(U.cardHead('求解耗时（对数对照）'),
        C.barChart(rows.map((x) => ({ label: x.label, value: Math.max(0.1, x.elapsed_ms) })), { width: 900, height: 240, tone: 'blue', unit: ' ms' }))
    );
  } else if (r.experiment === 'aggregation') {
    children.push(
      U.card(
        U.cardHead('聚合方法对比', { sub: 'RMSE 越低越准，留一 MAD 越小越稳' }),
        U.table(
          [
            { title: '方法', render: (x) => h('b', {}, x.label) },
            { title: 'RMSE（对真值）', class: 'num', render: (x) => h('span', { class: x.rmse != null && x.rmse === rows[0].rmse ? 'tone-ok' : '' }, x.rmse) },
            { title: '平均分', class: 'num', render: (x) => x.mean },
            { title: '留一稳定性 MAD', class: 'num', render: (x) => x.stability_mad },
            { title: '最大单次影响', class: 'num', render: (x) => x.stability_max },
            { title: '相对平均分的秩相关', class: 'num', render: (x) => x.rank_corr_vs_mean },
          ],
          rows
        )
      ),
      h('div', { class: 'grid grid--2 mt16' },
        U.card(U.cardHead('精度对比（RMSE，越低越好）'),
          C.barChart(rows.map((x) => ({ label: x.label, value: x.rmse || 0 })), { width: 500, height: 260, tone: 'brand' })),
        U.card(U.cardHead('稳定性对比（留一 MAD，越低越稳）'),
          C.barChart(rows.map((x) => ({ label: x.label, value: x.stability_mad })), { width: 500, height: 260, tone: 'blue' })))
    );
  } else if (r.experiment === 'anomaly') {
    const row = rows[0] || {};
    children.push(
      U.card(
        U.cardHead('检测效果'),
        h('div', { class: 'stat-row' },
          U.stat((row.precision * 100).toFixed(1) + '%', '精确率 Precision', { tone: 'brand' }),
          U.stat((row.recall * 100).toFixed(1) + '%', '召回率 Recall', { tone: 'ok' }),
          U.stat((row.f1 * 100).toFixed(1) + '%', 'F1', { tone: 'blue' }),
          U.stat(row.tp, '正确检出', { tone: 'ok' }),
          U.stat(row.fp, '误报', { tone: 'warn' }),
          U.stat(row.fn, '漏报', { tone: 'danger' })),
        h('div', { class: 'mt16' },
          C.barChart([
            { label: '正确检出', value: row.tp },
            { label: '误报', value: row.fp },
            { label: '漏报', value: row.fn },
          ], { width: 520, height: 220, tone: 'brand' })),
        U.table(
          [
            { title: '轮次', render: (x) => x.round },
            { title: '注入异常', class: 'num', render: (x) => x.injected },
            { title: '高风险判定', class: 'num', render: (x) => x.flagged },
            { title: '中风险待复核', class: 'num', render: (x) => x.suspicious },
            { title: 'TP', class: 'num', render: (x) => x.tp },
            { title: 'FP', class: 'num', render: (x) => x.fp },
            { title: 'FN', class: 'num', render: (x) => x.fn },
          ],
          r.per_round || [], { dense: true })
      )
    );
  } else if (r.experiment === 'complexity') {
    children.push(
      ...rows.map((x) =>
        h('div', { style: { marginBottom: '14px' } },
          U.card(
            U.cardHead(x.label, {
              sub: `判定复杂度 ${x.best}（经验指数 ${x.empirical_exponent}，置信度 ${x.confidence}）`,
              actions: U.badge('实测 ' + x.points.length + ' 个规模', 'brand'),
            }),
            C.complexityChart(x.points, { width: 900, height: 320 }),
            U.table(
              [
                { title: '模型', render: (m) => m.model },
                { title: '对数残差标准差', class: 'num', render: (m) => m.log_rmse },
              ],
              x.ranking, { dense: true })
          ))
      )
    );
  } else if (r.experiment === 'similarity') {
    children.push(
      U.card(
        U.cardHead('不同改写程度的检出情况', { sub: `检测 ${r.params.n_submissions} 份代码用时 ${r.elapsed_ms} ms` }),
        h('div', { class: 'stat-row' },
          ...Object.entries(r.detected_by_level || {}).map(([k, v]) => U.stat(v, k, { tone: k.includes('无关') ? 'warn' : v > 0 ? 'ok' : 'neutral' }))),
        U.table(
          [
            { title: '代码 A', width: '100px', render: (x) => '#' + x.a },
            { title: '代码 B', width: '100px', render: (x) => '#' + x.b },
            { title: '相似度', class: 'num', render: (x) => (x.similarity * 100).toFixed(1) + '%' },
            { title: '共享指纹', class: 'num', render: (x) => x.shared },
            { title: '改写类型', render: (x) => U.badge(x.kind, x.kind === '完全相同' ? 'danger' : 'warn') },
          ],
          rows, { dense: true })
      )
    );
  } else {
    children.push(U.card(U.cardHead('结果'), U.table(metrics.map((m) => ({ title: m, key: m })), rows)));
  }

  children.push(
    U.card(
      U.cardHead('原始结果（可导出到实验报告）', {
        actions: U.btn('复制 JSON', {
          tone: 'ghost', size: 'sm',
          onClick: () => {
            navigator.clipboard.writeText(JSON.stringify(r, null, 2)).then(() => ok('已复制到剪贴板')).catch(() => fail('浏览器拒绝了剪贴板访问'));
          },
        }),
      }),
      U.codeBlock(JSON.stringify({ experiment: r.experiment, params: r.params, rows: rows.slice(0, 8), conclusion: r.conclusion }, null, 2), 'json')
    )
  );
  return h('div', {}, ...children);
}
