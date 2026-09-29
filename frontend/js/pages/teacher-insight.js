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
import { openReviewDetail, openSubmissionDrawerById } from './teacher-core.js';

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

export function renderAnalytics({ klass, knowledge, timeline, ability }, container, extraTabs = []) {
  const tabsBox = h('div');
  const overview = () => {
    const ov = klass.overview;
    const verdicts = klass.verdicts || [];
    const scores = (klass.ranking || []).map((r) => r.score);
    const rule = klass.score_rule || {};
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
          U.cardHead('题目通过率与提交次数', {
            sub: '每题满分 100 分；通过率 = 通过人数 ÷ 提交人数，横向滚动可看更多列',
          }),
          U.table(
            [
              {
                title: '题目', width: '260px',
                render: (p) => h('div', { class: 'topic-cell' },
                  h('b', {}, p.title), U.tagList(p.topics, 'soft')),
              },
              { title: '类型', width: '92px', render: (p) => U.badge(PROBLEM_TYPE[p.type] || p.type, p.type === 'programming' ? 'brand' : 'blue') },
              { title: '满分', width: '74px', class: 'num', render: (p) => (p.score == null ? 100 : p.score) },
              { title: '通过率', width: '170px', render: (p) => h('div', {}, U.progress(p.pass_rate), h('span', { class: 'small muted' }, `${p.ac_count}/${p.students} 人`)) },
              { title: '人均提交', width: '96px', class: 'num', render: (p) => p.avg_tries },
              { title: '最多提交', width: '96px', class: 'num', render: (p) => p.max_tries },
              { title: '平均用时', width: '104px', class: 'num', render: (p) => (p.avg_time_ms ? U.fmtTime(p.avg_time_ms) : '—') },
              { title: '未提交', width: '86px', class: 'num', render: (p) => (p.zero_submit ? h('span', { class: 'tone-warn' }, p.zero_submit) : 0) },
              {
                title: '', width: '110px',
                render: (p) => h('button', {
                  class: 'btn btn--plain btn--xs',
                  onclick: () => openSubmissionStatus(p),
                }, '查看提交情况'),
              },
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
            U.cardHead('成绩分布', { sub: rule.formula || '按学生累计得分统计' }),
            scores.length ? C.barChart(
              histogram(scores, 10).map((b) => ({ label: b.x.toFixed(0), value: b.count })),
              { width: 420, height: 230, tone: 'brand', labelUnit: ' 分', valueUnit: ' 人' }
            ) : U.empty('暂无数据', ''),
            rule.formula
              ? U.note(`${rule.note}　满分 = ${rule.problem_count} 道题 × ${rule.per_problem} 分 = ${rule.full_score} 分。`, 'ok')
              : null
          )
        )),
      h('div', { class: 'grid grid--2 mt16' },
        U.card(
          U.cardHead('常见错误热点', { sub: '低通过率 + 高提交次数 = 教学重点；点一行看这个错误为什么会发生' }),
          klass.error_hotspots.length
            ? U.table(
                [
                  { title: '题目', render: (e) => e.title },
                  { title: '判定', render: (e) => U.verdictBadge(e.verdict) },
                  { title: '次数', class: 'num', render: (e) => e.c },
                  { title: '', width: '74px', render: (e) => h('span', { class: 'small muted', html: U.icon.arrow }) },
                ],
                klass.error_hotspots,
                { dense: true, onRow: (e) => openErrorDetail(e) })
            : U.empty('暂无错误记录', '')
        ),
        U.card(
          U.cardHead('学生成绩排名', { sub: `共 ${klass.ranking.length} 人` }),
          U.table(
            [
              { title: '#', width: '50px', render: (r) => r.rank },
              { title: '姓名', render: (r) => h('div', {}, h('b', {}, r.name), h('div', { class: 'small muted' }, r.class_name || '')) },
              { title: '累计得分', width: '110px', class: 'num', render: (r) => h('div', {}, h('b', {}, Math.round(r.score)), h('div', { class: 'small muted' }, `满分 ${rule.full_score || '—'}`)) },
              { title: '通过次数', width: '90px', class: 'num', render: (r) => r.ac },
              { title: '提交次数', width: '90px', class: 'num', render: (r) => r.submissions },
              {
                title: '', width: '86px',
                render: (r) => h('button', {
                  class: 'btn btn--plain btn--xs',
                  onclick: () => router.navigate('/teacher/student/' + r.user_id),
                }, '查看报告'),
              },
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
  extraTabs.forEach((t) => (panes[t.key] = t.render));
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
      ...extraTabs.map((t) => ({ key: t.key, label: t.label })),
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

/**
 * 「查看提交情况」：谁交了、交了几次、谁还没交。
 * 数据来自 /api/analytics/problem/{id}（users + not_submitted + detail）。
 */
async function openSubmissionStatus(p) {
  const body = h('div', {}, U.loading('正在统计提交情况…'));
  U.drawer(p.title + ' · 提交情况', body, { width: 760 });
  try {
    const d = await api.get('/api/analytics/problem/' + p.id);
    const detail = d.detail || {};
    const submitted = (d.users || []).map((u) => ({
      ...u, records: detail[u.user_id] || [],
    }));
    const missing = d.not_submitted || [];
    const totalTries = submitted.reduce((a, u) => a + u.tries, 0);
    clear(body).appendChild(h('div', {},
      h('div', { class: 'stat-row mb16' },
        U.stat(d.students_total, '班级人数'),
        U.stat(submitted.length, '已提交', { tone: 'ok' }),
        U.stat(missing.length, '未提交', { tone: missing.length ? 'warn' : 'ok' }),
        U.stat(totalTries, '提交总次数', { tone: 'blue' }),
        U.stat(submitted.length ? Math.round(submitted.reduce((a, u) => a + u.tries, 0) / submitted.length * 10) / 10 : 0, '人均提交次数', { tone: 'brand' })),
      missing.length
        ? U.card(
            U.cardHead('未提交名单', { sub: `${missing.length} 人` }),
            h('div', { class: 'row row--wrap', style: { gap: '8px' } },
              ...missing.map((s) => h('span', { class: 'badge badge--warn' },
                s.name + (s.class_name ? ' · ' + s.class_name : '')))))
        : U.note('全班都提交了这道题', 'ok'),
      h('div', { class: 'mt16' },
        U.card(
          U.cardHead('已提交学生明细', { sub: '按最高分排序；点行可看每次提交的判定' }),
          U.table(
            [
              { title: '学生', render: (u) => h('div', {}, h('b', {}, u.name), h('div', { class: 'small muted' }, u.class_name || '')) },
              { title: '状态', width: '100px', render: (u) => (u.solved ? U.badge('已通过', 'ok') : U.verdictBadge(u.verdict)) },
              { title: '最高分', width: '84px', class: 'num', render: (u) => u.best },
              { title: '提交次数', width: '90px', class: 'num', render: (u) => u.tries },
              { title: '每次判定', render: (u) => h('div', { class: 'dot-line' },
                  ...u.records.map((r) => h('span', {
                    class: 'cell-dot cell-dot--' + (r.verdict === 'Accepted' ? 'ok' : 'bad'),
                    title: `第 ${r.attempt_no} 次 · ${r.verdict} · ${r.score} 分${r.submitted_at ? ' · ' + r.submitted_at : ''}`,
                  }, r.verdict === 'Accepted' ? '✓' : '×'))) },
              { title: '', width: '80px', render: (u) => (u.records.length && u.records[u.records.length - 1].id
                  ? h('button', {
                      class: 'btn btn--plain btn--xs',
                      onclick: () => openSubmissionDrawerById(u.records[u.records.length - 1].id),
                    }, '看代码')
                  : null) },
            ],
            submitted,
            { dense: true, empty: '还没有学生提交' })
        ))
    ));
  } catch (e) {
    clear(body).appendChild(U.empty('加载失败', e.message));
  }
}

/** 「常见错误热点」点开后的解释：这类判定一般是什么原因造成的 */
function openErrorDetail(e) {
  const why = ERROR_REASONS[e.verdict] || {
    title: e.verdict,
    cause: '这类判定表示程序输出与期望不一致，需要结合具体测试点排查。',
    advice: '建议让学生对照样例与边界数据自查，或调用「重测」查看逐测试点结果。',
  };
  U.modal(`常见错误：${why.title}`, h('div', {},
    h('div', { class: 'row mb16', style: { gap: '10px' } },
      U.verdictBadge(e.verdict),
      U.badge(e.title, 'brand'),
      U.badge(`出现 ${e.c} 次`, 'warn')),
    h('div', { class: 'conclusion' },
      h('p', {}, h('b', {}, '为什么会这样：'), why.cause),
      h('p', { class: 'mt8' }, h('b', {}, '怎么处理：'), why.advice)),
    why.points && why.points.length
      ? h('div', { class: 'mt16' },
          h('h4', { class: 'small' }, '常见触发点'),
          U.tagList(why.points, 'soft'))
      : null,
    h('div', { class: 'row mt16', style: { gap: '8px' } },
      h('button', {
        class: 'btn btn--soft btn--sm',
        onclick: () => router.navigate('/problem/' + e.problem_id),
      }, '查看题目与测试点'))
  ), { width: 620 });
}

const ERROR_REASONS = {
  'Wrong Answer': {
    title: 'Wrong Answer（答案错误）',
    cause: '程序能跑完，但在某些输入上给出的输出和标准答案不同。多数来自：边界没考虑（n=1、空输入、极大值）、'
      + '下标越界访问到随机值、整数溢出、或者算法本身的理解有偏差。',
    advice: '让学生先用样例和自己在纸上算的小数据自查，再对着「逐测试点」找出第一个失败的点；'
      + '教师端可以直接点开该提交看每个测试点的输入规模与耗时。',
    points: ['边界数据', '溢出', '下标越界', '题意理解偏差'],
  },
  'Time Limit Exceeded': {
    title: 'Time Limit Exceeded（超时）',
    cause: '程序在时限内没跑完。最常见的是复杂度不达标：该用 O(n log n) 的写了 O(n²)，'
      + '或者用了递归但没有记忆化、反复重复计算。',
    advice: '对照题目要求的复杂度检查算法，用「算法实验台 → 复杂度实测」验证实际增长阶；'
      + '也可以在题目详情里比较不同规模测试点的耗时，看是否出现倍增比异常的测试点。',
    points: ['复杂度不达标', '未记忆化', '常数过大', '死循环'],
  },
  'Runtime Error': {
    title: 'Runtime Error（运行时错误）',
    cause: '程序异常退出，通常是数组越界、除零、递归太深导致栈溢出，或者对空结构取元素。',
    advice: '检查数组开得够不够（例如线段树要 4n）、递归深度与边界判断；'
      + 'Java 的 StackOverflowError、C++ 的段错误都属于这一类。',
    points: ['数组越界', '除零', '栈溢出', '空指针'],
  },
  'Memory Limit Exceeded': {
    title: 'Memory Limit Exceeded（超内存）',
    cause: '运行期内存峰值超过限制。常见于开了过大的二维数组、把 O(n²) 的数据结构塞进内存、'
      + '或者把编译/启动开销算进了程序本身。',
    advice: '把二维改成一维滚动数组，或换用更省内存的表示；注意平台的评测已经把编译器启动开销扣除。',
    points: ['二维数组过大', '未滚动数组', '递归占用大'],
  },
  'Compile Error': {
    title: 'Compile Error（编译错误）',
    cause: '语法错误、拼写错误、缺少头文件，或者用了当前标准不支持的写法。',
    advice: '页面里会直接展示编译器的报错信息和行号，按提示逐条修改；',
    points: ['语法错误', '缺少头文件', '标准版本'],
  },
  'Output Limit Exceeded': {
    title: 'Output Limit Exceeded（输出过多）',
    cause: '程序输出了远超预期的内容，多半是死循环里不断打印，或者把调试信息留在了提交里。',
    advice: '检查循环终止条件，提交前删除调试输出。',
    points: ['死循环打印', '调试输出未删'],
  },
};

function renderProblemAnalytics(d) {
  const p = d.problem;
  // 耗时区间的标签用「起点~终点」，避免十几位小数挤在一起看不清
  const timeHist = (d.time_hist || []).map((b) => ({
    label: `${Math.round(b.x)}~${Math.round(b.x2 != null ? b.x2 : b.x)}`,
    value: b.count,
  }));
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
      U.card(
        U.cardHead('通过所需尝试次数分布', {
          sub: '横轴是「第几次提交才通过」，纵轴是人数；分布靠右说明这道题调试成本高',
        }),
        (d.tries_to_ac.hist || []).length
          ? C.barChart(
              (d.tries_to_ac.hist || []).map((b) => ({ label: '第 ' + b.x + ' 次', value: b.count })),
              { width: 420, height: 240, tone: 'brand', valueUnit: ' 人' })
          : U.empty('暂无数据', '还没有学生通过这道题')),
      U.card(
        U.cardHead('通过提交的耗时分布', {
          sub: `横轴是运行耗时区间（毫秒），纵轴是通过该题的提交数；时限 ${p.time_limit_ms} ms，`
            + '柱子越靠近右侧说明实现越接近超时',
        }),
        timeHist.length
          ? C.barChart(timeHist, { width: 420, height: 240, tone: 'blue', valueUnit: ' 次' })
          : U.empty('暂无数据', '还没有通过的提交')),
      U.card(U.cardHead('运行资源统计', { sub: '通过这道题的提交在时间与内存上的分布' }),
        U.kv([
          ['用时中位数', U.fmtTime(d.time_stats.median)],
          ['用时 P95', U.fmtTime(d.time_stats.p95)],
          ['内存中位数', U.fmtMem(d.memory_stats.median)],
          ['内存峰值', U.fmtMem(d.memory_stats.max)],
        ]),
        U.note('P95 表示「95% 的提交都比这个值更快」，用它来判断是否存在普遍接近时限的写法。')),
      U.card(U.cardHead('判定分布', { sub: '这道题全部提交的判定构成' }),
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
    U.card(
      U.cardHead('这两个模型分别是干什么的', { sub: 'IRT 估能力与难度，ELO 追踪能力变化——两者相互独立、互为验证' }),
      h('div', { class: 'grid grid--2' },
        h('div', { class: 'conclusion' },
          h('b', {}, 'IRT（项目反应理论）—— 用来“同时”估计学生能力和题目难度'),
          h('p', { class: 'mt8' },
            '它把「某个学生做对某道题」看成一条概率曲线：能力 θ 越高、题目难度 b 越低，做对的概率越大。'
            + '用全部作答记录一起做极大似然估计，就能得到每位学生的能力值 θ 和每道题的难度 b。'
            + '下方表格里的「IRT 能力（0-100 归一化）」就是把 θ 线性映射到 0~100 便于比较；'
            + '「区分度 a」表示这道题对中等水平学生的分辨能力（2PL 才放开该参数）。')),
        h('div', { class: 'conclusion' },
          h('b', {}, 'ELO —— 用来“实时”追踪能力变化'),
          h('p', { class: 'mt8' },
            '借鉴棋类评分：每交一次题就按结果更新一次分数，做对了涨分、做错了扣分，涨跌幅度取决于对手（题目）的强度。'
            + 'IRT 是“全量一次性”估计，ELO 是“逐次在线”更新，两者相互独立。'
            + '右侧散点图就是二者的对照：点越接近一条直线，说明两种估计给出的排序越一致，'
            + '也侧面说明这套作答数据本身比较可信。'))),
      U.note('怎么看：能力值高低是相对本班同学而言的（已经做中心化），难度 b 也是相对值；'
        + 'b 越大越难，学生 θ 与题目 b 的差值才是预测“做不做得出来”的关键量。', 'ok')
    ),
    U.note(`基于 ${ability.n_obs || 0} 条首次提交，迭代 ${ability.iters} 次，对数似然 ${ability.loglik}。`
      + 'θ 与 b 只依赖差值，已做中心化。', 'ok'),
    h('div', { class: 'grid grid--side mt16' },
      U.card(
        U.cardHead('学生能力分布', { sub: 'IRT 能力值（0-100 归一化），条形越长表示该生综合能力越强' }),
        students.length
          ? C.barChart(
              students.slice(0, 20).map((s) => ({ label: s.name, value: s.ability })),
              {
                width: 700, horizontal: true, height: Math.max(220, Math.min(20, students.length) * 24 + 26),
                tone: 'brand', unit: '',
              })
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

/* ==================================================== 单个学生的学习报告 */

export async function loadStudentReport(ctx) {
  const id = ctx.params.id;
  const [report, problems] = await Promise.all([
    api.get('/api/analytics/student/' + id),
    api.get('/api/problems').catch(() => []),
  ]);
  return { report, problems };
}

/**
 * 教师视角的学生报告：点「查看报告」进来看到的是**这位同学**的数据，
 * 而不是登录教师自己的报告。
 */
export function renderStudentReport({ report, problems }) {
  const u = report.user || {};
  const subs = report.submissions || [];
  const mastery = Object.entries(report.mastery || {});
  const solved = report.solved || 0;
  const tried = report.attempted || 0;
  const best = {};
  subs.forEach((s) => {
    const cur = best[s.problem_id];
    if (!cur || (s.score || 0) > (cur.score || 0)) best[s.problem_id] = s;
  });
  const titleOf = {};
  (problems || []).forEach((p) => (titleOf[p.id] = p.title));
  return h(
    'div',
    {},
    U.pageHeader(`${u.name} 的学习报告`, {
      eyebrow: u.student_no || ('#' + u.id),
      sub: `${u.class_name || '未分班'} · 共 ${subs.length} 次提交 · 通过 ${solved} 题 / 作答 ${tried} 题`,
      actions: h('a', {
        class: 'btn btn--ghost btn--sm',
        href: '#/teacher/analytics',
      }, '返回学情分析'),
    }),
    h('div', { class: 'stat-row mb16' },
      U.stat(subs.length, '提交次数', { tone: 'brand' }),
      U.stat(solved, '通过题目数', { tone: 'ok' }),
      U.stat(tried, '作答题目数', { tone: 'blue' }),
      U.stat(subs.length ? Math.round((subs.filter((s) => s.verdict === 'Accepted').length / subs.length) * 100) + '%' : '—',
        '提交通过率', { tone: 'warn' })),
    h('div', { class: 'grid grid--side' },
      U.card(
        U.cardHead('知识点掌握', { sub: '按该生在这道题上的最好成绩折算' }),
        mastery.length
          ? h('div', { class: 'score-list' },
              ...mastery.sort((a, b) => a[1] - b[1]).map(([k, v]) =>
                h('div', { class: 'score-item' },
                  h('span', { class: 'score-item__name' }, k),
                  U.meter(v, { tone: masteryTone(v) }),
                  h('span', { class: ['score-item__val', 'tone-' + masteryTone(v)] }, String(v)))))
          : U.empty('暂无数据', '')),
      U.card(
        U.cardHead('主观题与互评', { sub: '提交情况与互评得分' }),
        (report.subjective || []).length
          ? U.table(
              [
                { title: '题目', render: (r) => r.problem_title },
                { title: '状态', width: '110px', render: (r) => U.badge(r.status === 'done' ? '已出分' : '评审中', r.status === 'done' ? 'ok' : 'warn') },
                { title: '互评得分', width: '100px', class: 'num', render: (r) => (r.final_score == null ? '—' : r.final_score) },
              ],
              report.subjective, { dense: true })
          : U.empty('没有主观题提交', ''))
    ),
    h('div', { class: 'mt16' },
      U.card(
        U.cardHead('逐题作答情况', { sub: '点击一行查看这份提交的代码与逐测试点结果' }),
        U.table(
          [
            { title: '题目', render: (s) => h('div', {}, h('b', {}, s.problem_title || titleOf[s.problem_id] || ('#' + s.problem_id)),
                h('div', { class: 'small muted' }, s.problem_type === 'programming' ? '编程题' : '主观题')) },
            { title: '判定', width: '120px', render: (s) => U.verdictBadge(s.verdict) },
            { title: '得分', width: '80px', class: 'num', render: (s) => s.score },
            { title: '用时', width: '100px', class: 'num', render: (s) => U.fmtTime(s.time_ms) },
            { title: '语言', width: '80px', render: (s) => U.badge(s.language, 'neutral') },
            { title: '提交时间', width: '150px', render: (s) => U.fmtDate(s.submitted_at) },
          ],
          subs,
          {
            dense: true, empty: '这位同学还没有提交记录',
            onRow: (s) => openSubmissionDrawerById(s.id),
          })
      ))
  );
}

/* ==================================================== 评审过程管理 */

export async function loadReviewAdmin(ctx) {
  const [assignments, students] = await Promise.all([
    api.get('/api/assignments'),
    api.get('/api/users', { role: 'student', in_course: 1 }).catch(() => []),
  ]);
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
  return { assignments: peer, selected, allocs, results, anomalies, students };
}

export function renderReviewAdmin({ assignments, selected, allocs, results, anomalies, students },
                                   container, extraTabs = []) {
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

    // 常用参数只有 3 个，其余算法权重收进「高级参数」，避免一屏全是输入框
    const form = h(
      'div',
      {},
      h(
        'div',
        { class: 'grid grid--3', style: { gap: '12px' } },
        U.field('分配算法', U.select([
          { value: 'mcmf', label: '最小费用流 + 局部搜索（推荐）' },
          { value: 'greedy', label: '贪心负载均衡' },
          { value: 'random', label: '随机分配' },
        ], { value: params.method, onchange: (e) => (params.method = e.target.value) })),
        U.field('每份作业评几次 k', h('input', { class: 'input', type: 'number', min: 1, max: 6, value: params.reviews_per_submission, oninput: (e) => (params.reviews_per_submission = +e.target.value) })),
        U.field('每人最多评几份 c', h('input', { class: 'input', type: 'number', min: 1, max: 10, value: params.max_load, oninput: (e) => (params.max_load = +e.target.value) }))
      ),
      h('details', { class: 'mt12' },
        h('summary', { style: { cursor: 'pointer', fontSize: '13px', color: 'var(--brand)' } },
          '高级参数（算法权重，一般不用改）'),
        h(
          'div',
          { class: 'grid grid--2 mt12', style: { gap: '12px' } },
          U.field('历史重复互评惩罚 α', h('input', { class: 'input', type: 'number', step: '0.5', value: params.prev_pair_penalty, oninput: (e) => (params.prev_pair_penalty = +e.target.value) }), { hint: '越大越避开上一轮互评过的人' }),
          U.field('跨班组权重 β', h('input', { class: 'input', type: 'number', step: '0.5', value: params.cross_group_bonus, oninput: (e) => (params.cross_group_bonus = +e.target.value) }), { hint: '鼓励跨班分配，降低熟人效应' }),
          U.field('互为评审惩罚 ρ', h('input', { class: 'input', type: 'number', step: '0.5', value: params.reciprocity_penalty, oninput: (e) => (params.reciprocity_penalty = +e.target.value) })),
          U.field('班级分布均衡权重 γ', h('input', { class: 'input', type: 'number', step: '0.2', value: params.variety_weight, oninput: (e) => (params.variety_weight = +e.target.value) })),
          U.field('随机种子', h('input', { class: 'input', type: 'number', value: params.seed, oninput: (e) => (params.seed = +e.target.value) }), { hint: '同一种子结果可复现' })
        ))
    );

    return h(
      'div',
      {},
      current && current.peer_review
        ? (current.allocation_status === 'draft'
            ? U.alertRow('high', '本轮互评分配待你确认',
                `已生成 ${allocs && allocs.stats ? allocs.stats.total : 0} 条评审任务，但还没有发布，学生看不到。`
                + '确认名单没问题后点击「确认并发布」；需要换人可以在下面的「分配明细」里逐条调整。',
                h('div', { class: 'row', style: { gap: '6px' } },
                  U.btn('确认并发布', {
                    tone: 'primary', size: 'xs',
                    onClick: async (e) => {
                      const yes = await confirmDialog({
                        title: '确认并发布互评分配',
                        message: '发布后学生就能看到分配给自己的评审任务，且无法再静默改动。确定发布吗？',
                        confirmText: '确认发布',
                      });
                      if (!yes) return;
                      try {
                        const r = await api.post(`/api/assignments/${selected}/publish-allocation`);
                        ok(`已发布 ${r.allocations} 条评审任务，学生现在可以看到`);
                        router.resolve();
                      } catch (err) { fail(err.message); }
                    },
                  })))
            : U.alertRow('low', '本轮互评分配已发布',
                `学生已经可以看到各自的评审任务（共 ${allocs && allocs.stats ? allocs.stats.total : 0} 条）。`
                + '如需换人，调整后需要重新确认发布。'))
        : null,
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
              sub: `${allocs.stats.total} 条评审任务 · 已完成 ${allocs.stats.done} 条 · 待完成 ${allocs.stats.pending} 条`
                + ` · 人均工作量 ${allocs.stats.load_min}~${allocs.stats.load_max} 份`,
            }),
            U.note('按「谁的哪道题」分组列出评审者。想换人就直接点右侧「调整评审人」；'
              + '改过名单后需要重新点「确认并发布」，学生才会看到新任务。', 'ok'),
            U.table(
              [
                { title: '作业（匿名）', width: '120px', render: (g) => h('span', { class: 'anon-tag' }, g.anon) },
                {
                  title: '作者', width: '150px',
                  render: (g) => h('div', {}, h('b', {}, g.author_name),
                    h('div', { class: 'small muted' }, g.author_class || '')),
                },
                { title: '题目', width: '190px', render: (g) => g.problem_title || ('#' + g.problem_id) },
                {
                  title: '评审者',
                  render: (g) => h('div', { class: 'col', style: { gap: '4px' } },
                    ...g.reviewers.map((r) => h('div', { class: 'row', style: { gap: '8px' } },
                      h('span', {}, h('b', {}, r.reviewer_name)),
                      h('span', { class: 'small muted' }, r.reviewer_class || ''),
                      U.badge(r.status === 'done' ? '已评' : '待评', r.status === 'done' ? 'ok' : 'warn')))),
                },
                {
                  title: '', width: '120px',
                  render: (g) => h('button', {
                    class: 'btn btn--soft btn--xs',
                    onclick: () => openAdjustReviewers(selected, g, students, () => router.resolve()),
                  }, '调整评审人'),
                },
              ],
              groupAllocations(allocs.allocations).slice(0, 200),
              { dense: true }),
            h('details', { class: 'mt16' },
              h('summary', { style: { cursor: 'pointer', fontSize: '13px', color: 'var(--brand)' } },
                '查看分配关系图（作者 ↔ 评审者）'),
              h('div', { class: 'mt12' },
                C.bipartiteGraph(
                  allocs.allocations.slice(0, 220).map((a) => ({ author: a.author_id, reviewer: a.reviewer_id })),
                  { width: 900, height: 340, authorLabel: (x) => '作业#' + x, reviewerLabel: (x) => '评审者#' + x })))
          )
        : null
    );
  };

  const resultPane = () => {
    if (!results || !results.length) return U.empty('暂无评分结果', '请先在「分配管理」中执行分配，并等待评审完成后聚合。');
    return h('div', {}, ...results.map((r) =>
      h('div', { style: { marginBottom: '16px' } },
        U.card(
          U.cardHead(r.problem_title + ' · 评分结果', {
            sub: `共 ${r.rows.length} 份提交 · 点「评审人」名字可以看到他给的分与文字意见`,
          }),
          U.table(
            [
              { title: '#', width: '48px', render: (_x, i) => i + 1 },
              { title: '学生', render: (x) => h('div', {}, h('b', {}, x.name), h('div', { class: 'small muted' }, x.class_name || '')) },
              { title: '最终得分', width: '100px', class: 'num', render: (x) => h('b', { style: { color: 'var(--brand)' } }, x.score) },
              { title: '各评审原始分', render: (x) => h('div', { class: 'mono small' }, x.raw.map((v) => v.toFixed(0)).join(' / ')) },
              { title: '极差', width: '80px', class: 'num', render: (x) => (x.spread > 25 ? h('span', { class: 'tone-danger' }, x.spread) : x.spread) },
              { title: '评审数', width: '80px', class: 'num', render: (x) => x.n_reviews },
              {
                title: '评审人', width: '150px',
                render: (x) => {
                  const ds = x.details || [];
                  if (!ds.length) return h('span', { class: 'small muted' }, '还没有人评');
                  // 直接把评审者的名字做成按钮：教师一眼能看出是谁评的，点进去看分数与意见
                  const head = ds[0].reviewer_name || ('#' + ds[0].reviewer_id);
                  const label = ds.length > 1 ? `${head} 等 ${ds.length} 人` : head;
                  return h('button', {
                    class: 'btn btn--soft btn--xs',
                    title: ds.map((d) => `${d.reviewer_name || '#' + d.reviewer_id}：${d.total == null ? '—' : d.total} 分`).join('\n'),
                    onclick: () => openReviewDetail(x, r.problem_title),
                  }, label);
                },
              },
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
          C.barChart(
            stats.slice(0, 12).map((s) => ({ label: s.name || ('#' + s.reviewer_id), value: Math.abs(s.bias) })),
            { width: 520, horizontal: true, height: 320, tone: 'warn', unit: '' }),
          C.barChart(
            stats.slice(0, 12).map((s) => ({ label: s.name || ('#' + s.reviewer_id), value: s.reliability })),
            { width: 520, horizontal: true, height: 320, tone: 'brand', unit: '' })),
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
  extraTabs.forEach((t) => (panes[t.key] = t.render));
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
      ...extraTabs.map((t) => ({ key: t.key, label: t.label, badge: t.badge })),
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

/** 把逐条 allocation 合并成「谁（作者）的哪道题由哪些人评」 */
function groupAllocations(rows) {
  const map = new Map();
  rows.forEach((a) => {
    const key = `${a.problem_id}|${a.author_id}`;
    if (!map.has(key)) {
      map.set(key, {
        problem_id: a.problem_id, problem_title: a.problem_title,
        author_id: a.author_id, author_name: a.author_name, author_class: a.author_class,
        anon: a.anon, reviewers: [],
      });
    }
    map.get(key).reviewers.push({
      reviewer_id: a.reviewer_id, reviewer_name: a.reviewer_name,
      reviewer_class: a.reviewer_class, status: a.status,
    });
  });
  return Array.from(map.values());
}

/** 教师人工调整某一份作业的评审人 */
function openAdjustReviewers(assignmentId, group, students, refresh) {
  const bodyBox = h('div');
  const pick = h('select', { class: 'input' });
  (students || []).forEach((s) => {
    if (s.id === group.author_id) return;
    const already = group.reviewers.some((r) => r.reviewer_id === s.id);
    pick.appendChild(h('option', { value: s.id, disabled: already || null },
      `${s.name}${s.class_name ? '（' + s.class_name + '）' : ''}${already ? ' · 已在名单' : ''}`));
  });

  const paint = () => {
    clear(bodyBox).appendChild(h('div', {},
      h('div', { class: 'row mb12', style: { gap: '8px', flexWrap: 'wrap' } },
        U.badge(group.anon, 'neutral'),
        U.badge(group.author_name, 'brand'),
        U.badge(`当前 ${group.reviewers.length} 位评审者`, 'blue')),
      h('div', { class: 'col', style: { gap: '8px' } },
        ...group.reviewers.map((r) => h('div', { class: 'list-row' },
          h('div', { class: 'list-row__main' },
            h('div', { class: 'list-row__title' }, r.reviewer_name,
              U.badge(r.status === 'done' ? '已完成评审' : '待评审', r.status === 'done' ? 'ok' : 'warn')),
            h('div', { class: 'list-row__meta' }, h('span', {}, r.reviewer_class || ''))),
          h('div', { class: 'list-row__side' },
            r.status === 'done'
              ? h('span', { class: 'small muted' }, '已评完，不能移除')
              : U.btn('移除', {
                  tone: 'plain', size: 'xs',
                  onClick: async () => {
                    const yes = await confirmDialog({
                      title: '移除评审者',
                      message: `确定把「${r.reviewer_name}」从这份作业的评审名单里移除吗？`,
                      confirmText: '移除',
                    });
                    if (!yes) return;
                    try {
                      await api.post(`/api/assignments/${assignmentId}/allocation/adjust`, {
                        problem_id: group.problem_id, author_id: group.author_id,
                        remove_reviewer_id: r.reviewer_id,
                      });
                      ok('已移除，请记得重新确认发布');
                      refresh();
                    } catch (e) { fail(e.message); }
                  },
                })))),
        group.reviewers.length ? null : U.empty('这位同学还没有评审者', '请在下面选一位加入。')),
      h('div', { class: 'row mt16', style: { gap: '8px' } },
        pick,
        U.btn('加入评审', {
          tone: 'primary', size: 'sm',
          onClick: async () => {
            if (!pick.value) return fail('请选择要加入的学生');
            try {
              await api.post(`/api/assignments/${assignmentId}/allocation/adjust`, {
                problem_id: group.problem_id, author_id: group.author_id,
                add_reviewer_id: Number(pick.value),
              });
              ok('已加入，请记得重新确认发布');
              refresh();
            } catch (e) { fail(e.message); }
          },
        })),
      U.note('名单调整后这次作业的互评状态会回到「待确认」，需要你重新点「确认并发布」，学生才会看到变更。', 'warn')));
  };
  paint();
  U.modal(`调整评审人 · ${group.anon}`, bodyBox, {
    width: 640,
    actions: (close) => [U.btn('关闭', { tone: 'ghost', onClick: close })],
  });
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
            { title: '', width: '230px', render: (a) => h('div', { class: 'row', style: { gap: '4px' } },
                U.btn('查看详情', { tone: 'ghost', size: 'xs', onClick: () => openAnomalyDetail(a) }),
                U.btn('确认', { tone: 'soft', size: 'xs', onClick: () => handle(a, 'confirmed') }),
                U.btn('排除', { tone: 'plain', size: 'xs', onClick: () => handle(a, 'dismissed') }),
                U.btn('降权', { tone: 'ghost', size: 'xs', onClick: () => openAdjustWeight(a, paint) })) },
          ],
          rows, { dense: true, empty: '没有符合条件的异常记录' })
      )
    );
  };
  const handle = async (a, st, weight) => {
    // 确认/排除/降权都会影响该评审者后续的权重与聚合结果，先让教师二次确认
    const meta = {
      confirmed: {
        title: '确认这条异常评审',
        message: `确认后系统会记录「${a.reviewer_name || '#' + a.reviewer_id}」存在异常评分行为，`
          + '该评审者在后续聚合中的权重会被下调，并保留处理痕迹。',
        confirmText: '确认异常',
      },
      dismissed: {
        title: '排除这条异常',
        message: '排除表示经人工复核认为该评分正常，异常记录会被关闭，评审者的权重不受影响。',
        confirmText: '排除异常',
      },
      adjusted: {
        title: '下调评审者权重',
        message: `将把「${a.reviewer_name || '#' + a.reviewer_id}」的权重调整为 ${weight}，`
          + '其给出的分数在聚合时影响变小。',
        confirmText: '调整权重',
      },
    }[st];
    if (meta) {
      const yes = await confirmDialog(meta);
      if (!yes) return;
    }
    const note = st === 'dismissed' ? '教师复核后判定为正常'
      : st === 'adjusted' ? `教师复核后把权重调整为 ${weight}` : '教师复核确认异常';
    try {
      await api.post(`/api/anomalies/${a.id}/handle`, { status: st, note, adjust_weight: weight });
      a.status = st;
      ok(st === 'dismissed' ? '已标记为「已排除」' : st === 'adjusted' ? '已调整该评审者权重' : '已确认异常');
      paint();
      router.resolve();
    } catch (e) { fail(e.message); }
  };

  /** 查看这位评审者当时到底怎么评的：分数、文字意见、时长、被评对象 */
  const openAnomalyDetail = (a) => {
    const reviews = a.reviews || [];
    U.drawer(`异常详情 · ${a.reviewer_name || '#' + a.reviewer_id}`, h('div', {},
      h('div', { class: 'row mb16', style: { gap: '8px', flexWrap: 'wrap' } },
        U.badge(a.level === 'high' ? '高风险' : a.level === 'medium' ? '中风险' : '低风险',
          a.level === 'high' ? 'danger' : a.level === 'medium' ? 'warn' : 'blue'),
        U.badge(ANOMALY_TYPE[a.type] || a.type, 'neutral'),
        U.badge(a.status === 'open' ? '待复核' : '已处理', a.status === 'open' ? 'warn' : 'ok')),
      U.card(U.cardHead('异常判定的依据'), h('div', {},
        h('p', {}, h('b', {}, a.title)),
        h('p', { class: 'muted' }, a.detail),
        a.suggestion ? U.note('系统建议：' + a.suggestion) : null,
        Object.keys(a.evidence || {}).length
          ? U.kv(Object.entries(a.evidence).map(([k, v]) => [k, typeof v === 'object' ? JSON.stringify(v) : String(v)]))
          : null)),
      h('div', { class: 'mt16' },
        U.card(
          U.cardHead(`这位评审者的评审记录（最近 ${reviews.length} 条）`, {
            sub: '分数明显偏离、或文字意见与分数不匹配，都可以作为人工复核的依据',
          }),
          reviews.length
            ? h('div', { class: 'col', style: { gap: '10px' } }, ...reviews.map((r) =>
                h('div', { class: 'sub-line' },
                  h('div', { class: 'sub-line__head' },
                    h('b', {}, r.problem_title || ('#' + r.problem_id)),
                    U.badge('给分 ' + (r.total == null ? '—' : r.total), (r.total || 0) >= 90 ? 'warn' : 'brand'),
                    r.flagged ? U.badge('已被标记', 'danger') : null),
                  h('div', { class: 'sub-line__meta' },
                    r.target_name ? h('span', {}, '被评：' + r.target_name) : null,
                    r.assignment_title ? h('span', {}, r.assignment_title) : null,
                    r.duration_sec ? h('span', {}, `用时 ${Math.round(r.duration_sec)} 秒`) : null,
                    r.submitted_at ? h('span', {}, U.fmtDate(r.submitted_at)) : null),
                  Object.keys(r.scores || {}).length
                    ? h('div', { class: 'sub-line__meta' },
                        ...Object.entries(r.scores).map(([k, v]) => h('span', {}, `${k} ${v}`)))
                    : null,
                  r.comment ? h('div', { class: 'conclusion mt8' }, r.comment) : null)))
            : U.empty('没有找到这位评审者的评审记录', '')),
        h('div', { class: 'row mt16', style: { gap: '8px' } },
          U.btn('确认异常', { tone: 'soft', size: 'sm', onClick: () => handle(a, 'confirmed') }),
          U.btn('排除', { tone: 'ghost', size: 'sm', onClick: () => handle(a, 'dismissed') }),
          U.btn('手动下调权重', { tone: 'ghost', size: 'sm', onClick: () => openAdjustWeight(a, paint) })))
    ), { width: 760 });
  };

  /** 降权比例由教师自己定，而不是固定 0.3 */
  const openAdjustWeight = (a, done) => {
    const input = h('input', { class: 'input', type: 'number', min: '0.05', max: '1', step: '0.05', value: '0.3' });
    U.modal('下调评审者权重', h('div', { class: 'col', style: { gap: '12px' } },
      U.field('权重比例（0.05 ~ 1）', input, {
        hint: '1 = 保持原权重；0.3 = 该评审者的评分在聚合时只算 30% 的影响',
      }),
      U.note(`评审者：${a.reviewer_name || '#' + a.reviewer_id}　`
        + `异常类型：${ANOMALY_TYPE[a.type] || a.type}`),
      U.note('权重会写回该评审者的分配记录，重新执行「评分聚合」后生效（聚合方法选「可信度动态加权」时影响最明显）。', 'warn')
    ), {
      width: 560,
      actions: (close) => [
        U.btn('取消', { tone: 'ghost', onClick: close }),
        U.btn('确认调整', {
          tone: 'primary',
          onClick: async () => {
            const w = Number(input.value);
            if (!(w > 0 && w <= 1)) return fail('权重需要在 0.05 ~ 1 之间');
            close();
            await handle(a, 'adjusted', w);
          },
        }),
      ],
    });
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
            C.barChart(
              risk.map((r) => ({ label: r.reviewer_name || ('#' + r.reviewer_id), value: r.risk })),
              { width: 520, horizontal: true, height: Math.max(240, risk.length * 26 + 26), tone: 'danger', unit: '' }),
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
    h('div', { class: 'grid grid--2 mt12 mb16' },
      h('div', { class: 'conclusion' },
        h('b', {}, '相似度阈值是什么？'),
        h('p', { class: 'mt8' },
          '系统不看变量名和注释，而是把每份代码按顺序切成许多很短的片段，'
          + '相当于给代码取一串「指纹」；然后数两份代码里有多少片段是重复出现的——'
          + '重复的越多，相似度越高（0~100%）。'
          + '阈值就是一条分数线：相似度超过它的代码对才会列在下面。'
          + '例如填 0.6，就只列出相似度 60% 以上的那些。')),
        h('p', { class: 'mt8' },
          '推荐用法：阈值 0.75 以上基本可以认定是同一份代码改的；0.6~0.75 属于「值得看一眼」，'
          + '可能是同学之间讨论后写法趋同；低于 0.6 误报会明显变多。'),
      h('div', { class: 'conclusion' },
        h('b', {}, '看到高相似之后该怎么办？'),
        h('p', { class: 'mt8' },
          '相似度只是线索，不能直接判定抄袭。建议结合：提交时间是否接近、'
          + '变量命名习惯是否一致、是否同时出现同样的非必要写法（例如同一个多余的循环）。'
          + '必要时找两位同学口述思路，再决定是否按学术规范处理。'))),
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
