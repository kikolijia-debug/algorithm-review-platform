/** 学生端页面：学习动态、题库、提交记录、互评中心、主观题、学习报告。 */

import { h, clear, esc } from '../core/dom.js';
import { state, isTeacher } from '../core/store.js';
import * as api from '../core/api.js';
import * as router from '../core/router.js';
import { ok, fail, info, confirmDialog } from '../core/toast.js';
import * as U from '../core/ui.js';
import * as C from '../core/charts.js';
import { codeEditor } from '../core/editor.js';
import { PROBLEM_TYPE, VERDICT_MEANING, ASSIGNMENT_STATUS, METHOD_LABEL, masteryTone, difficultyLabel } from '../core/format.js';
import { openProblemEditor } from './problem-editor.js';

const uid = () => state.user.id;

/* ==================================================== 学习动态（工作台） */

export async function loadDashboard() {
  const [dash, knowledge, report] = await Promise.all([
    api.get('/api/dashboard/student'),
    api.get('/api/analytics/knowledge').catch(() => ({ mastery: {}, per_user: {} })),
    api.get(`/api/analytics/student/${uid()}`).catch(() => null),
  ]);
  return { dash, knowledge, report };
}

export function renderDashboard({ dash, knowledge, report }) {
  const st = dash.stats || {};
  const hour = new Date().getHours();
  const greet = hour < 6 ? '凌晨好' : hour < 12 ? '上午好' : hour < 14 ? '中午好' : hour < 18 ? '下午好' : '晚上好';
  const todo = dash.todo || [];
  const pending = dash.pending_reviews || [];

  const hero = h(
    'div',
    { class: 'hero' },
    h(
      'div',
      {},
      h('div', { class: 'hero__title' }, `${greet}，${state.user.name}`),
      h(
        'p',
        { class: 'hero__sub' },
        todo.length
          ? `今天有 ${todo.length} 项作业还在进行中，${pending.length} 份同学的主观题等你评审。`
          : `当前没有待办作业${pending.length ? `，但有 ${pending.length} 份互评任务待完成。` : '，可以自由安排复习计划。'}`
      ),
      h(
        'div',
        { class: 'row mt16' },
        h('a', { class: 'btn btn--primary btn--sm', href: '#/problems' }, '去题库练习'),
        pending.length ? h('a', { class: 'btn btn--dark btn--sm', href: '#/student/reviews' }, '开始互评') : null
      )
    ),
    h(
      'div',
      { class: 'hero__tiles' },
      tile(todo.length, '进行中作业'),
      tile(pending.length, '待互评'),
      tile(st.solved || 0, '已解决题目'),
      tile(Math.round((st.ac_rate || 0) * 100) + '%', '提交通过率')
    )
  );

  const todoCard = U.card(
    U.cardHead('今日学习重点', {
      sub: todo.length ? `${todo.length} 项作业未完成` : '暂无进行中的作业',
      actions: h('a', { class: 'btn btn--ghost btn--sm', href: '#/student/submissions' }, '查看全部提交'),
    }),
    todo.length
      ? h(
          'div',
          { class: 'col' },
          ...todo.map((a) =>
            h(
              'div',
              { class: 'list-row' },
              h(
                'div',
                { class: 'list-row__main' },
                h(
                  'div',
                  { class: 'list-row__title' },
                  a.title,
                  h('span', { class: 'badge badge--brand' }, ASSIGNMENT_STATUS[a.status] || a.status)
                ),
                h(
                  'div',
                  { class: 'list-row__meta' },
                  h('span', {}, `进度 ${a.progress.done}/${a.progress.total}`),
                  h('span', {}, a.due_at ? '截止 ' + U.fmtDate(a.due_at, { withTime: false }) : '未设截止'),
                  a.peer_review ? h('span', {}, `互评待办 ${a.my_review_pending || 0}`) : null
                ),
                U.progress(a.progress.ratio)
              ),
              h(
                'div',
                { class: 'list-row__side' },
                U.countdown(a.due_at),
                h('a', { class: 'btn btn--soft btn--sm', href: `#/student/assignment/${a.id}` }, '继续')
              )
            )
          )
        )
      : U.empty('暂无进行中的作业', '所有已发布作业都已完成，可以去题库自主练习。')
  );

  const recent = U.card(
    U.cardHead('最近提交', { sub: '含判定结果、运行时间与尝试次数' }),
    dash.recent_submissions.length
      ? h(
          'div',
          {},
          ...dash.recent_submissions.slice(0, 6).map((s) =>
            h(
              'div',
              { class: 'mini-row', style: { cursor: 'pointer' }, onclick: () => router.navigate('/student/submissions/' + s.id) },
              U.verdictBadge(s.verdict),
              h('span', { class: 'grow' }, s.title),
              h('span', { class: 'muted small' }, U.fmtTime(s.time_ms)),
              h('span', { class: 'mini-row__time' }, U.timeAgo(s.submitted_at))
            )
          )
        )
      : U.empty('还没有提交记录', '去题库挑一道题开始吧。')
  );

  const peerCard = U.card(
    U.cardHead('待完成的互评', {
      sub: pending.length ? `${pending.length} 份` : '全部完成',
      actions: h('a', { class: 'btn btn--ghost btn--sm', href: '#/student/reviews' }, '互评中心'),
    }),
    pending.length
      ? h(
          'div',
          {},
          ...pending.slice(0, 4).map((p) =>
            h(
              'div',
              { class: 'mini-row', style: { cursor: 'pointer' }, onclick: () => router.navigate('/student/reviews/' + p.id) },
              h('span', { class: 'anon-tag' }, '匿名'),
              h('span', { class: 'grow' }, p.problem_title),
              p.review_due_at ? U.countdown(p.review_due_at) : null
            )
          )
        )
      : U.empty('没有待完成的互评', '互评结果将在评审截止后公布。')
  );

  const perUser = (knowledge && knowledge.per_user) || {};
  const mine = perUser[uid()] || {};
  const radarLabels = Object.keys(mine);
  const radar = radarLabels.length
    ? C.radarChart(radarLabels, radarLabels.map((k) => mine[k]), { width: 340, height: 300 })
    : U.empty('暂无知识点数据', '完成几道题目后即可生成能力雷达图。');

  const verdictDonut = report && Object.keys(report.verdicts || {}).length
    ? C.donutChart(
        Object.entries(report.verdicts).map(([k, v]) => ({ label: k, value: v, color: verdictColor(k) })),
        { width: 240, height: 200, centerValue: (report.submissions || []).length, centerLabel: '次提交' }
      )
    : U.empty('暂无提交数据', '');

  const overview = U.card(
    U.cardHead('学习概览', { sub: '基于本课程全部提交记录实时计算' }),
    h(
      'div',
      { class: 'stat-row' },
      U.stat(st.submissions || 0, '总提交次数', { tone: 'brand' }),
      U.stat(st.accepted || 0, '通过次数', { tone: 'ok' }),
      U.stat(Math.round((st.ac_rate || 0) * 100) + '%', '提交通过率', { tone: 'blue' })
    ),
    h('div', { class: 'grid grid--2 mt16', style: { gap: '12px' } }, radar, verdictDonut)
  );

  const notices = U.card(
    U.cardHead('课程通知', { sub: '来自教师的最新消息' }),
    (dash.notices || []).length
      ? h(
          'div',
          {},
          ...dash.notices.map((n) =>
            h('div', { class: 'mini-row' },
              h('span', { class: 'grow' }, h('b', {}, n.title), h('div', { class: 'small muted' }, n.content)),
              h('span', { class: 'mini-row__time' }, U.timeAgo(n.created_at)))
          )
        )
      : U.empty('暂无通知', '')
  );

  return h(
    'div',
    { class: 'col', style: { gap: '16px' } },
    hero,
    h('div', { class: 'dash-grid' }, h('div', { class: 'col', style: { gap: '16px' } }, todoCard, recent), h('div', { class: 'col', style: { gap: '16px' } }, overview, peerCard, notices))
  );
}

function tile(v, l) {
  return h('div', { class: 'hero-tile' }, h('b', {}, String(v)), h('span', {}, l));
}

function verdictColor(v) {
  return (
    { Accepted: '#17a06a', 'Wrong Answer': '#c0503f', 'Time Limit Exceeded': '#c98a1f', 'Runtime Error': '#b45fa6', 'Compile Error': '#7b8f87' }[v] || '#5f7f93'
  );
}

/* ============================================================ 题库列表 */

export async function loadProblemList(ctx) {
  const [problems, courses] = await Promise.all([api.get('/api/problems', ctx.query), api.get('/api/courses')]);
  return { problems, courses };
}

export function renderProblemList({ problems, courses }, _container, ctx) {
  const teacher = isTeacher();
  let type = 'all';
  let keyword = '';
  const listBox = h('div', { class: 'grid grid--auto' });

  const paint = () => {
    clear(listBox);
    const filtered = problems.filter(
      (p) => (type === 'all' || (type === 'subjective' ? p.type !== 'programming' : p.type === type)) &&
        (!keyword || p.title.includes(keyword) || (p.topics || []).some((t) => t.includes(keyword)))
    );
    if (!filtered.length) {
      listBox.appendChild(U.empty('没有符合条件的题目', '换个关键词或类型试试。'));
      return;
    }
    filtered.forEach((p) => listBox.appendChild(problemCard(p, teacher)));
  };

  const filters = h(
    'div',
    { class: 'filterbar' },
    h(
      'div',
      { class: 'search-box' },
      h('span', { class: 'search-box__icon', html: U.icon.search }),
      h('input', {
        class: 'input search',
        placeholder: '搜索题目标题或知识点…',
        oninput: (e) => {
          keyword = e.target.value.trim();
          paint();
        },
      })
    ),
    U.segmented(
      [
        { key: 'all', label: '全部' },
        { key: 'programming', label: '编程题' },
        { key: 'subjective', label: '主观题' },
      ],
      { value: 'all', onChange: (k) => { type = k; paint(); } }
    ),
    h('div', { class: 'grow' }),
    teacher ? U.btn('新建题目', { tone: 'primary', icon: U.icon.plus, onClick: () => openProblemEditor(null, () => router.resolve()) }) : null
  );

  paint();
  return h(
    'div',
    {},
    U.pageHeader(teacher ? '题库管理' : '题库与作业', {
      eyebrow: 'PROBLEM BANK',
      sub: teacher
        ? '创建题目、配置测试数据与评分规则。'
        : '按知识点浏览题目，查看完成情况。',
    }),
    filters,
    listBox
  );
}

function problemCard(p, teacher) {
  const solved = p.my_verdict === 'Accepted' || p.pass_rate > 0;
  return h(
    'div',
    { class: 'card problem-card', onclick: () => router.navigate('/problem/' + p.id) },
    h(
      'div',
      { class: 'problem-card__top' },
      h('div', {}, h('div', { class: 'problem-card__title' }, p.title)),
      h(
        'div',
        { class: 'row', style: { gap: '6px' } },
        p.my_verdict ? U.verdictBadge(p.my_verdict) : null,
        U.badge(PROBLEM_TYPE[p.type] || p.type, p.type === 'programming' ? 'brand' : 'blue')
      )
    ),
    h('div', { class: 'problem-card__stats' },
      h('span', {}, `难度 ${'★'.repeat(Math.min(5, p.difficulty))}`),
      h('span', {}, `${p.ac_count || 0}/${p.student_count || 0} 人通过`),
      h('span', {}, `${p.submit_count || 0} 次提交`),
      p.type === 'programming' ? h('span', {}, `${p.n_cases} 个测试点`) : null
    ),
    U.tagList(p.topics, 'soft'),
    h(
      'div',
      { class: 'problem-card__foot' },
      p.type === 'programming'
        ? h('span', { class: 'small muted' }, `时限 ${p.time_limit_ms} ms · 内存 ${p.memory_limit_mb} MB`)
        : h('span', { class: 'small muted' }, '主观题 · 互评模式'),
      h('span', { class: 'row', style: { gap: '6px' } },
        p.pass_rate != null ? U.badge(`通过率 ${Math.round((p.pass_rate || 0) * 100)}%`, p.pass_rate > 0.6 ? 'ok' : 'warn') : null,
        h('span', { class: 'muted', html: U.icon.arrow }))
    )
  );
}

/* ============================================================ 我的提交 */

export async function loadSubmissions(ctx) {
  const [rows, problems] = await Promise.all([
    api.get('/api/submissions', { limit: 300, ...ctx.query }),
    api.get('/api/problems'),
  ]);
  return { rows, problems };
}

export function renderSubmissions({ rows, problems }) {
  let verdict = '';
  let keyword = '';
  const box = h('div');
  const paint = () => {
    const filtered = rows.filter(
      (r) => (!verdict || r.verdict === verdict) && (!keyword || r.problem_title.includes(keyword))
    );
    clear(box);
    box.appendChild(
      U.table(
        [
          { title: '题目', render: (r) => h('b', {}, r.problem_title) },
          { title: '判定', width: '110px', render: (r) => U.verdictBadge(r.verdict, { full: false }) },
          { title: '得分', width: '80px', class: 'num', render: (r) => (r.score == null ? '—' : r.score) },
          { title: '耗时', width: '100px', class: 'num', render: (r) => U.fmtTime(r.time_ms) },
          { title: '内存', width: '100px', class: 'num', render: (r) => U.fmtMem(r.memory_kb) },
          { title: '语言', width: '86px', render: (r) => U.badge(r.language, 'neutral') },
          { title: '第几次', width: '80px', class: 'num', render: (r) => r.attempt_no },
          { title: '提交时间', width: '150px', render: (r) => U.fmtDate(r.submitted_at) },
        ],
        filtered,
        { empty: '没有符合条件的提交记录', onRow: (r) => router.navigate('/student/submissions/' + r.id) }
      )
    );
  };
  paint();
  const stats = {
    total: rows.length,
    ac: rows.filter((r) => r.verdict === 'Accepted').length,
  };
  return h(
    'div',
    {},
    U.pageHeader('我的提交', {
      eyebrow: 'SUBMISSIONS',
      sub: '点击任意一行查看逐测试点详情。',
    }),
    h('div', { class: 'stat-row mb16' },
      U.stat(stats.total, '总提交次数'),
      U.stat(stats.ac, '通过次数', { tone: 'ok' }),
      U.stat(Math.round((stats.ac / Math.max(1, stats.total)) * 100) + '%', '通过率', { tone: 'blue' }),
      U.stat(new Set(rows.filter((r) => r.verdict === 'Accepted').map((r) => r.problem_id)).size, '已解决题目', { tone: 'warn' })),
    h('div', { class: 'filterbar' },
      h('div', { class: 'search-box' }, h('span', { class: 'search-box__icon', html: U.icon.search }),
        h('input', { class: 'input search', placeholder: '搜索题目…', oninput: (e) => { keyword = e.target.value.trim(); paint(); } })),
      U.select([{ value: '', label: '全部判定' }, ...Object.keys(VERDICT_MEANING).map((v) => ({ value: v, label: v }))],
        { onchange: (e) => { verdict = e.target.value; paint(); } })),
    box
  );
}

export async function loadSubmissionDetail(ctx) {
  const s = await api.get('/api/submissions/' + ctx.params.id);
  return { s };
}

export function renderSubmissionDetail({ s }) {
  const detail = s.detail || {};
  const results = (detail.results && detail.results.length ? detail.results : s.test_results) || [];
  const verdictTone =
    s.verdict === 'Accepted' ? 'ok' : s.verdict === 'Time Limit Exceeded' ? 'warn' : 'danger';
  return h(
    'div',
    {},
    U.pageHeader(s.problem_title, {
      eyebrow: 'SUBMISSION #' + s.id,
      sub: `${s.language} · 第 ${s.attempt_no} 次提交 · ${U.fmtDate(s.submitted_at, { withTime: true })}`,
      actions: h('a', { class: 'btn btn--ghost', href: '#/student/submissions' }, '返回列表'),
    }),
    h(
      'div',
      { class: 'result-panel' },
      h(
        'div',
        { class: 'result-panel__head' },
        h('div', { class: ['result-panel__verdict', 'result-panel__verdict--' + verdictTone] }, s.verdict),
        h('span', { class: 'muted small' }, VERDICT_MEANING[s.verdict] || ''),
        h(
          'div',
          { class: 'result-panel__metrics' },
          h('div', { class: 'result-metric' }, h('b', {}, s.score == null ? '—' : s.score), h('span', {}, '得分')),
          h('div', { class: 'result-metric' }, h('b', {}, U.fmtTime(s.time_ms)), h('span', {}, '最长用时')),
          h('div', { class: 'result-metric' }, h('b', {}, U.fmtMem(s.memory_kb)), h('span', {}, '峰值内存'))
        )
      ),
      detail.startup_overhead_ms != null
        ? h('div', { class: 'note small', style: { margin: '12px 14px 0' } },
            `评测耗时扣除进程启动开销 ${detail.startup_overhead_ms} ms；本次评测总耗时 ${detail.judge_ms} ms。`)
        : null,
      results.length
        ? h('div', {}, ...results.map((r) =>
            h('div', { class: 'case-line' },
              U.verdictBadge(r.verdict),
              h('span', { class: 'case-line__name' }, r.name || ('测试点 ' + r.test_case_id)),
              h('span', { class: 'case-line__io' }, `${U.fmtTime(r.time_ms)} · ${U.fmtMem(r.memory_kb)}`),
              r.message && r.verdict !== 'AC' && r.verdict !== 'Accepted' ? h('span', { class: 'small muted' }, r.message) : null)))
        : U.empty('没有测试点明细', '该记录为演示数据，可在教师端点击「重测」生成真实评测结果。')
    ),
    s.compile_message ? U.card(U.cardHead('编译信息'), U.codeBlock(s.compile_message, 'text')) : null,
    U.card(
      U.codePanel(s.source_code || '', s.language, {
        title: '源代码',
        sub: `${s.language} · ${(s.source_code || '').split('\n').length} 行`,
      }),
      (s.peer_reviews || []).length
        ? h('div', { class: 'mt16' },
            U.cardHead(`同学对我这份代码的评审（${s.peer_reviews.length} 份）`),
            h('div', { class: 'col' }, ...s.peer_reviews.map((r) =>
              h('div', { class: 'list-row', style: { display: 'block' } },
                h('div', { class: 'row', style: { marginBottom: '6px' } },
                  h('span', { class: 'anon-tag' }, r.reviewer),
                  U.badge(r.total + ' 分', 'brand'),
                  h('span', { class: 'muted small' }, `用时 ${Math.round(r.duration_sec || 0)} 秒`)),
                h('div', { style: { fontSize: '13px', color: 'var(--ink-2)' } }, r.comment)))))
        : s.peer_review_pending
          ? h('div', { class: 'mt16' }, U.note(s.peer_review_pending, 'warn'))
          : null
    )
  );
}

/* ============================================================ 互评中心 */

export async function loadReviews() {
  const rows = await api.get('/api/reviews/mine');
  return { rows };
}

export function renderReviews({ rows }) {
  const pending = rows.filter((r) => r.status === 'pending');
  const done = rows.filter((r) => r.status === 'done');
  const render = (list, isPending) =>
    list.length
      ? h('div', { class: 'grid grid--auto' }, ...list.map((r) =>
          h('div', { class: 'card problem-card' },
            h('div', { class: 'problem-card__top' },
              h('div', {}, h('div', { class: 'problem-card__title' }, r.problem_title)),
              isPending ? U.countdown(r.review_due_at) : U.badge('已完成', 'ok')),
            h('div', { class: 'small muted' }, r.assignment_title),
            h('div', { class: 'row', style: { gap: '8px', marginTop: '6px' } },
              h('span', { class: 'anon-tag' }, r.author),
              U.badge(PROBLEM_TYPE[r.problem_type] || r.problem_type, 'blue')),
            h('div', { class: 'problem-card__foot' },
              isPending
                ? h('span', { class: 'small muted' }, '按统一评分细则打分并给出文字意见')
                : h('span', { class: 'small muted' }, `你给出 ${r.my_review ? r.my_review.total : '—'} 分`),
              h('button', {
                class: ['btn', 'btn--sm', isPending ? 'btn--primary' : 'btn--ghost'],
                onclick: () => router.navigate('/student/reviews/' + r.allocation_id),
              }, isPending ? '开始评审' : '查看/修改')
            )
          )))
      : U.empty(isPending ? '没有待完成的互评' : '还没有已完成的互评', isPending ? '当老师开放互评后，这里会出现分配给你的任务。' : '');
  return h(
    'div',
    {},
    U.pageHeader('互评中心', {
      eyebrow: 'PEER REVIEW',
      sub: '按细则逐项打分，并写下具体意见。',
    }),
    U.note(
      '双方互相匿名，结果在评审截止后公布。异常评分会被标记并交教师复核。'
    ),
    h('div', { class: 'mt16' },
      h('h3', { class: 'mb8', style: { fontSize: '15px' } }, `待完成互评（${pending.length}）`),
      render(pending, true)),
    h('div', { class: 'mt24' },
      h('h3', { class: 'mb8', style: { fontSize: '15px' } }, `已完成（${done.length}）`),
      render(done, false))
  );
}

export async function loadReviewTask(ctx) {
  const task = await api.get('/api/reviews/task/' + ctx.params.id);
  return { task, startedAt: new Date().toISOString() };
}

export function renderReviewTask({ task, startedAt }) {
  const scores = {};
  let comment = task.my_review ? task.my_review.comment || '' : '';
  if (task.my_review) Object.assign(scores, task.my_review.scores || {});
  const totalBox = h('span', { class: 'rubric-item__score' }, '0');
  const sections = task.sections || [];
  const content = task.content || {};
  const isCode = task.kind === 'code';

  const recalc = () => {
    const total = Object.values(scores).reduce((a, b) => a + (Number(b) || 0), 0);
    totalBox.textContent = String(Math.round(total * 10) / 10);
    totalBox.style.color = total >= 85 ? 'var(--brand-2)' : total >= 60 ? 'var(--brand)' : 'var(--danger)';
  };

  const codeBody = h(
    'div',
    {},
    h(
      'div',
      { class: 'row row--wrap', style: { gap: '8px', marginBottom: '10px' } },
      h('span', { class: 'muted small' }, '自动评测'),
      U.verdictBadge(task.verdict || '—'),
      h('span', { class: 'small muted' },
        `机评分 ${task.auto_score == null ? '—' : task.auto_score}` +
        (task.passed != null ? ` · 通过 ${task.passed}/${task.total_cases}` : '') +
        (task.time_ms ? ` · 最长用时 ${U.fmtTime(task.time_ms)}` : '') +
        (task.memory_kb ? ` · 内存 ${U.fmtMem(task.memory_kb)}` : '')),
      task.attempt_no ? U.badge(`第 ${task.attempt_no} 次提交`, 'neutral') : null
    ),
    h('div', { class: 'row', style: { marginBottom: '8px' } },
      U.badge(task.language || 'cpp', 'neutral'),
      h('span', { class: 'small muted' },
        `共 ${(task.code || '').split('\n').length} 行 · 提交于 ${U.fmtDate(task.submitted_at)}`)),
    U.codePanel(task.code || '（该同学没有提交记录）', task.language || 'cpp', {
      title: '同学的代码',
      sub: `共 ${(task.code || '').split('\n').length} 行 · ${task.language || 'cpp'}`,
    }),
    U.note('请从正确性、效率与复杂度、代码清晰度、健壮性四个方面评价；'
      + '机评结果仅供参考，重点是代码本身的问题与改进空间。', 'ok')
  );

  const textBody = h(
    'div',
    { class: 'mt16' },
    sections.length
      ? sections.map((sec) =>
          h('section', { class: 'mt16' },
            h('h4', { style: { fontSize: '13.5px', color: 'var(--brand)' } }, sec.name),
            h('div', { class: 'prose', style: { fontSize: '13.5px', lineHeight: '1.95', whiteSpace: 'pre-wrap', color: 'var(--ink-2)' } },
              String(content[sec.key] || '（未作答）'))))
      : Object.entries(content).map(([k, v]) =>
          h('section', { class: 'mt16' }, h('h4', {}, k),
            h('div', { style: { whiteSpace: 'pre-wrap', fontSize: '13.5px' } }, String(v))))
  );

  const left = U.card(
    U.cardHead(task.problem_title, { sub: task.assignment_title }),
    h('div', { class: 'row', style: { marginBottom: '10px' } },
      h('span', { class: 'anon-tag' }, '作者 ' + task.author),
      U.badge(isCode ? '代码互评' : (PROBLEM_TYPE[task.problem_type] || task.problem_type),
              isCode ? 'brand' : 'blue'),
      h('span', { class: 'muted small' }, isCode ? '预计 8-12 分钟' : '预计阅读 8-12 分钟')),
    h('details', { open: !isCode },
      h('summary', { style: { cursor: 'pointer', fontSize: '13px', color: 'var(--brand)' } }, '查看题目要求'),
      h('div', { class: 'prose', style: { fontSize: '13px', whiteSpace: 'pre-wrap', marginTop: '8px', color: 'var(--ink-2)' } }, task.problem_statement || '')),
    isCode ? h('div', { class: 'mt16' }, codeBody) : textBody
  );

  const rubric = (task.rubric && task.rubric.length ? task.rubric : [
    { key: 'idea', name: '算法思想与建模', max: 30, desc: '问题抽象是否准确、思路是否清晰' },
    { key: 'complexity', name: '复杂度分析', max: 25, desc: '时间/空间复杂度推导是否正确' },
    { key: 'correctness', name: '正确性论证', max: 25, desc: '证明是否完整，边界是否讨论' },
    { key: 'writing', name: '表达与规范', max: 20, desc: '结构完整、术语准确' },
  ]).filter((r) => r && r.key);

  const right = U.card(
    U.cardHead('评分与意见', { sub: '按统一细则逐项给分', actions: h('span', { class: 'rubric-item__score' }, totalBox) }),
    h('div', {}, ...rubric.map((r) => {
      if (scores[r.key] == null) scores[r.key] = Math.round(r.max * 0.7);
      const val = h('span', { class: 'rubric-item__score' }, scores[r.key]);
      const range = h('input', {
        class: 'range', type: 'range', min: 0, max: r.max, step: 1, value: scores[r.key],
        oninput: (e) => {
          scores[r.key] = Number(e.target.value);
          val.textContent = e.target.value;
          recalc();
        },
      });
      return h('div', { class: 'rubric-item' },
        h('div', { class: 'rubric-item__head' }, h('span', { class: 'rubric-item__name' }, r.name), val),
        h('p', { class: 'rubric-item__desc' }, `${r.desc || ''}（满分 ${r.max}）`),
        range);
    })),
    U.field('文字意见', U.textarea({
      placeholder: '请指出做得好的地方，以及可以改进的具体位置（至少 20 字）',
      value: comment,
      oninput: (e) => { comment = e.target.value; },
      style: { minHeight: '120px' },
    }), { hint: '具体的修改建议会被汇总给作者，请保持客观、建设性' }),
    h('div', { class: 'row mt16' },
      U.btn('提交评审', {
        tone: 'primary', icon: U.icon.check,
        onClick: async (e) => {
          const total = Object.values(scores).reduce((a, b) => a + Number(b || 0), 0);
          if (Object.values(scores).every((v) => Number(v) === 0)) return fail('请先完成评分细则');
          if (comment.trim().length < 10) return fail('请给出至少 10 个字的文字意见');
          const btn = e.target.closest('button');
          btn.disabled = true;
          try {
            await api.post('/api/reviews/' + task.allocation_id, {
              scores,
              comment,
              duration_sec: Math.max(20, (Date.now() - new Date(startedAt).getTime()) / 1000),
              started_at: startedAt.replace('T', ' ').slice(0, 19),
            });
            ok(`评审已提交（${Math.round(total * 10) / 10} 分）`);
            router.navigate('/student/reviews');
          } catch (err) {
            fail(err.message);
            btn.disabled = false;
          }
        },
      }),
      U.btn('稍后再评', { tone: 'ghost', onClick: () => router.navigate('/student/reviews') })
    )
  );
  recalc();
  return h(
    'div',
    {},
    U.pageHeader('匿名互评', {
      eyebrow: 'REVIEW TASK #' + task.allocation_id,
      sub: '评审时长会被记录',
    }),
    h('div', { class: 'review-layout' }, left, right)
  );
}

/* ======================================================== 我的主观题 */

export async function loadSubjective() {
  const [rows, assignments] = await Promise.all([
    api.get('/api/subjective', { mine: 1 }),
    api.get('/api/assignments'),
  ]);
  const details = {};
  for (const r of rows.slice(0, 20)) {
    try {
      details[r.id] = await api.get('/api/subjective/' + r.id);
    } catch (e) {
      /* 单条失败不影响列表 */
    }
  }
  return { rows, assignments, details };
}

export function renderSubjective({ rows, assignments, details }) {
  const cards = rows.length
    ? rows.map((r) => {
        const d = details[r.id] || {};
        const published = d.review_published;
        const methods = d.methods || {};
        const comparison = Object.entries(methods).map(([k, v]) => ({
          label: METHOD_LABEL[k] || k,
          value: v == null ? null : Number(v),
        }));
        return h(
          'div',
          { class: 'card', style: { marginBottom: '16px' } },
          U.cardHead(r.problem_title, {
            sub: r.assignment_title,
            actions: [
              U.badge(r.status === 'done' ? '评审已完成' : '等待评审', r.status === 'done' ? 'ok' : 'warn'),
              d.final_score != null ? U.badge('最终 ' + d.final_score + ' 分', 'brand') : null,
            ],
          }),
          published
            ? h(
                'div',
                { class: 'grid grid--side', style: { gap: '16px' } },
                h(
                  'div',
                  {},
                  h('h4', { class: 'small muted', style: { marginBottom: '8px' } }, '各聚合方法下的得分'),
                  comparison.some((c) => c.value != null)
                    ? h(
                        'div',
                        { class: 'score-list' },
                        ...comparison.map((c) =>
                          h(
                            'div',
                            { class: 'score-item' },
                            h('span', { class: 'score-item__name' }, c.label),
                            U.meter(c.value == null ? 0 : c.value, { tone: c.label.includes('动态') ? 'brand' : 'ok' }),
                            h('span', { class: 'score-item__val' }, c.value == null ? '—' : c.value.toFixed(1))
                          )
                        )
                      )
                    : U.empty('暂无聚合结果', '教师执行评分聚合后显示')
                ),
                h(
                  'div',
                  {},
                  h('h4', { class: 'small muted', style: { marginBottom: '8px' } }, `评审意见（${(d.reviews || []).length} 份，匿名）`),
                  (d.reviews || []).length
                    ? h('div', { class: 'col' }, ...d.reviews.map((rv) =>
                        h('div', { class: 'list-row', style: { display: 'block' } },
                          h('div', { class: 'row', style: { marginBottom: '6px' } },
                            h('span', { class: 'anon-tag' }, rv.reviewer),
                            U.badge(rv.total + ' 分', 'brand'),
                            h('span', { class: 'muted small' }, `用时 ${Math.round(rv.duration_sec || 0)} 秒`)),
                          h('div', { style: { fontSize: '13px', color: 'var(--ink-2)' } }, rv.comment))))
                    : U.empty('暂无文字意见', '')
                )
              )
            : U.note(d.pending_reason || '评审尚未结束，结果将在评审截止后公布。', 'warn'),
          h('details', { class: 'mt12' },
            h('summary', { style: { cursor: 'pointer', fontSize: '13px', color: 'var(--brand)' } }, '查看我的作答'),
            h(
              'div',
              { class: 'mt12' },
              Object.entries((details[r.id] || {}).content || {}).map(([k, v]) =>
                h('section', { class: 'mt12' }, h('h4', { class: 'small', style: { color: 'var(--brand)' } }, k),
                  h('div', { style: { whiteSpace: 'pre-wrap', fontSize: '13px', color: 'var(--ink-2)' } }, String(v))))
            )
          )
        );
      })
    : U.empty('还没有提交过主观题', '去题库选择一道主观题开始作答吧。');
  return h(
    'div',
    {},
    U.pageHeader('我的主观题', {
      eyebrow: 'SUBJECTIVE WORK',
      sub: '提交记录与互评结果',
      actions: h('a', { class: 'btn btn--primary', href: '#/problems' }, '去作答'),
    }),
    cards
  );
}

/* ========================================================== 学习报告 */

export async function loadReport() {
  const [report, knowledge, ability] = await Promise.all([
    api.get(`/api/analytics/student/${uid()}`),
    api.get('/api/analytics/knowledge'),
    api.get('/api/analytics/ability').catch(() => null),
  ]);
  return { report, knowledge, ability };
}

export function renderReport({ report, knowledge, ability }) {
  const mastery = knowledge.mastery || {};
  const mine = (knowledge.per_user || {})[uid()] || {};
  const labels = Object.keys(mine);
  const classAvg = labels.map((k) => mastery[k] || 0);
  const timeline = report.timeline || [];
  const subs = report.submissions || [];
  const verdictCounts = report.verdicts || {};
  const radar = labels.length
    ? C.radarChart(labels, labels.map((k) => mine[k]), { compare: classAvg, width: 380, height: 320 })
    : U.empty('暂无知识点数据', '');
  const weak = Object.entries(mine).sort((a, b) => a[1] - b[1]).slice(0, 5);
  return h(
    'div',
    {},
    U.pageHeader('学习报告', {
      eyebrow: 'LEARNING REPORT',
      sub: `${report.user.name} · ${report.user.class_name || ''} · 班级排名 ${report.rank}/${report.peer_count}`,
      actions: h('button', { class: 'btn btn--ghost', onclick: () => window.print() }, '导出 / 打印'),
    }),
    h('div', { class: 'stat-row mb16' },
      U.stat(report.solved, '已解决题目', { tone: 'ok', hint: `共尝试 ${report.attempted} 题` }),
      U.stat(subs.length, '提交次数', { tone: 'brand' }),
      U.stat(Math.round(report.ac_rate * 100) + '%', '提交通过率', { tone: 'blue' }),
      U.stat(report.rank, '班级排名', { tone: 'warn', hint: `共 ${report.peer_count} 人` }),
      U.stat(U.fmtTime(report.total_time_ms), '累计运行时间', { tone: 'brand' })),
    h(
      'div',
      { class: 'grid grid--side' },
      h(
        'div',
        { class: 'col', style: { gap: '16px' } },
        U.card(
          U.cardHead('知识点掌握度', { sub: '实线为你本人，虚线为班级平均' }),
          radar
        ),
        U.card(
          U.cardHead('薄弱知识点', { sub: '按掌握度升序排列，建议优先复习' }),
          weak.length
            ? h('div', { class: 'score-list' }, ...weak.map(([k, v]) =>
                h('div', { class: 'score-item' },
                  h('span', { class: 'score-item__name', title: k }, k),
                  U.meter(v, { tone: masteryTone(v), label: '' }),
                  h('span', { class: ['score-item__val', 'tone-' + masteryTone(v)] }, String(v)))))
            : U.empty('暂无数据', '')
        ),
        U.card(
          U.cardHead('提交时间线', { sub: '每日提交次数与通过情况' }),
          timeline.length
            ? C.lineChart(
                [
                  { name: '提交次数', values: timeline.map((t) => t.count), color: '#3f8fd6' },
                  { name: '其中通过', values: timeline.map((t) => t.ac), color: '#17a06a' },
                ],
                { xLabels: timeline.map((t) => t.date.slice(5)), width: 680, height: 230 }
              )
            : U.empty('暂无提交记录', '')
        )
      ),
      h(
        'div',
        { class: 'col', style: { gap: '16px' } },
        U.card(
          U.cardHead('判定分布'),
          Object.keys(verdictCounts).length
            ? C.donutChart(
                Object.entries(verdictCounts).map(([k, v]) => ({ label: k, value: v, color: verdictColor(k) })),
                { width: 260, height: 200, centerValue: subs.length, centerLabel: '次提交' }
              )
            : U.empty('暂无数据', '')
        ),
        U.card(
          U.cardHead('互评参与情况', { sub: '我给你打分的记录不在此处展示（保证匿名）' }),
          U.kv([
            ['完成评审', `${report.review_stats.done} / ${report.review_stats.given}`],
            ['我给的平均分', report.review_stats.mean_score == null ? '—' : report.review_stats.mean_score],
            ['平均评审用时', report.review_stats.mean_duration == null ? '—' : Math.round(report.review_stats.mean_duration) + ' 秒'],
          ])
        ),
        U.card(
          U.cardHead('学习行为统计'),
          (report.events || []).length
            ? h('div', { class: 'score-list' }, ...report.events.map((e) =>
                h('div', { class: 'score-item' },
                  h('span', { class: 'score-item__name' }, eventLabel(e.type)),
                  h('span', {}, U.barMini(e.c, Math.max(...report.events.map((x) => x.c)))),
                  h('span', { class: 'score-item__val' }, e.c))))
            : U.empty('暂无行为数据', '')
        )
      )
    )
  );
}

function eventLabel(t) {
  return {
    login: '登录平台',
    view_problem: '查看题目',
    run_code: '运行调试',
    submit: '提交代码',
    view_solution: '查看题解',
    open_review: '打开互评任务',
    submit_review: '提交互评',
    submit_subjective: '提交主观题',
  }[t] || t;
}

/* ================================================ 题目详情（共用加载） */

export async function loadProblem(ctx) {
  const p = await api.get('/api/problems/' + ctx.params.id);
  return p;
}

/* ================================================ 学生端：作业详情 */

export async function loadStudentAssignment(ctx) {
  const [a, reviews] = await Promise.all([
    api.get('/api/assignments/' + ctx.params.id),
    api.get('/api/reviews/mine').catch(() => []),
  ]);
  return { a, mine: (reviews || []).filter((r) => String(r.assignment_id) === String(a.id)) };
}

export function renderStudentAssignment({ a, mine }) {
  const probs = a.problems || [];
  const isProg = (p) => p.type === 'programming';
  const solved = (p) => (isProg(p) ? p.my_verdict === 'Accepted' : !!p.my_subjective);
  const done = probs.filter(solved).length;
  const pending = mine.filter((r) => r.status === 'pending');

  return h(
    'div',
    {},
    U.pageHeader(a.title, {
      eyebrow: 'ASSIGNMENT',
      sub: a.description || '',
      actions: [
        a.overdue ? U.badge('已截止', 'neutral') : U.countdown(a.due_at),
        U.badge(`${done}/${probs.length} 已完成`, done === probs.length ? 'ok' : 'warn'),
        h('a', { class: 'btn btn--ghost btn--sm', href: '#/problems' }, '去题库'),
      ],
    }),
    U.card(
      U.cardHead('完成进度', { sub: `${done} / ${probs.length} 题` }),
      U.progress(probs.length ? done / probs.length : 0),
      h('div', { class: 'row row--wrap mt12', style: { gap: '16px' } },
        h('span', { class: 'small muted' }, a.due_at ? `截止 ${U.fmtDate(a.due_at)}` : '未设截止'),
        a.review_due_at ? h('span', { class: 'small muted' }, `互评截止 ${U.fmtDate(a.review_due_at)}`) : null,
        a.peer_review ? h('span', { class: 'small muted' }, `每份作业 ${a.reviews_per_submission} 份评审`) : null)
    ),
    h('div', { class: 'grid grid--auto mt16' },
      ...probs.map((p) =>
        h('div', { class: 'card problem-card' },
          h('div', { class: 'problem-card__top' },
            h('div', {}, h('div', { class: 'problem-card__title' }, p.title)),
            solved(p)
              ? U.badge('已完成', 'ok')
              : p.my_verdict
                ? U.verdictBadge(p.my_verdict)
                : U.badge('未提交', 'neutral')),
          h('div', { class: 'problem-card__stats' },
            h('span', {}, PROBLEM_TYPE[p.type] || p.type),
            isProg(p) ? h('span', {}, `已尝试 ${p.my_tries || 0} 次`) : null,
            isProg(p) ? h('span', {}, `最高 ${p.my_best == null ? '—' : p.my_best} 分`) : null,
            !isProg(p) && p.my_subjective ? h('span', {}, '已提交') : null),
          U.tagList(p.topics, 'soft'),
          h('div', { class: 'problem-card__foot' },
            h('span', { class: 'small muted' }, p.type === 'programming' ? '自动评测' : '互评'),
            h('a', { class: 'btn btn--soft btn--sm', href: `#/problem/${p.id}` },
              solved(p) ? '再看一遍' : '去完成'))
        ))),
    a.peer_review
      ? h('div', { class: 'mt16' },
          U.card(
            U.cardHead('我的互评任务', {
              sub: `待完成 ${pending.length} 份 / 共 ${mine.length} 份`,
              actions: h('a', { class: 'btn btn--primary btn--sm', href: '#/student/reviews' }, '进入互评中心'),
            }),
            pending.length
              ? h('div', { class: 'col' }, ...pending.slice(0, 5).map((r) =>
                  h('div', { class: 'list-row' },
                    h('span', { class: 'anon-tag' }, r.author || '匿名'),
                    h('div', { class: 'list-row__main' },
                      h('div', { class: 'list-row__title' }, r.problem_title)),
                    h('a', { class: 'btn btn--soft btn--xs', href: `#/student/reviews/${r.allocation_id}` }, '开始评审'))))
              : U.empty('互评已全部完成', '感谢参与，结果将在评审截止后公布。')
          )
        )
      : null
  );
}
