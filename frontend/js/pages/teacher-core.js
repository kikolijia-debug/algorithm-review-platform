/** 教师端核心页面：教学看板、作业管理、作业详情、提交与评测。 */

import { h, clear } from '../core/dom.js';
import { state } from '../core/store.js';
import * as api from '../core/api.js';
import * as router from '../core/router.js';
import { ok, fail, info, confirmDialog } from '../core/toast.js';
import * as U from '../core/ui.js';
import * as C from '../core/charts.js';
import { PROBLEM_TYPE, ASSIGNMENT_STATUS, VERDICT_MEANING, ALLOC_LABEL, METHOD_LABEL } from '../core/format.js';
import { openProblemEditor, deleteProblem } from './problem-editor.js';

/* ======================================================== 教学看板 */

export async function loadTeacherDashboard() {
  const [dash, klass] = await Promise.all([
    api.get('/api/dashboard/teacher'),
    api.get('/api/analytics/class').catch(() => null),
  ]);
  return { dash, klass };
}

export function renderTeacherDashboard({ dash, klass }) {
  const st = dash.stats || {};
  const assignments = dash.assignments || [];
  const active = assignments.filter((a) => !a.overdue && a.status !== 'closed');
  const needAttention = assignments.filter((a) => a.pending_reviews > 0 || a.status === 'reviewing');

  const hero = h(
    'div',
    { class: 'hero' },
    h(
      'div',
      {},
      h('div', { class: 'hero__title' }, '教学看板'),
      h('p', { class: 'hero__sub' },
        `${dash.course.name} · ${dash.students} 名学生 · ${st.problems} 道题目 · `
        + `累计 ${st.submissions} 次自动评测，整体通过率 ${Math.round((st.ac_rate || 0) * 100)}%`),
      h('div', { class: 'row mt16' },
        h('a', { class: 'btn btn--primary btn--sm', href: '#/teacher/assignments' }, '布置作业'),
        h('a', { class: 'btn btn--dark btn--sm', href: '#/teacher/analytics' }, '查看学情分析'),
        st.open_anomalies ? h('a', { class: 'btn btn--dark btn--sm', href: '#/teacher/anomalies' }, `复核异常评审 (${st.open_anomalies})`) : null)
    ),
    h(
      'div',
      { class: 'hero__tiles' },
      h('div', { class: 'hero-tile' }, h('b', {}, dash.students), h('span', {}, '学生成员')),
      h('div', { class: 'hero-tile' }, h('b', {}, active.length), h('span', {}, '进行中作业')),
      h('div', { class: 'hero-tile' }, h('b', {}, st.pending_reviews), h('span', {}, '待完成互评')),
      h('div', { class: 'hero-tile' }, h('b', {}, st.open_anomalies), h('span', {}, '待处理异常'))
    )
  );

  const progressCard = U.card(
    U.cardHead('作业进度', { sub: `${assignments.length} 次作业`, actions: h('a', { class: 'btn btn--ghost btn--sm', href: '#/teacher/assignments' }, '全部') }),
    assignments.length
      ? h('div', { class: 'col' }, ...assignments.slice(0, 6).map((a) => {
          const total = a.submitted_users + a.subjective_users;
          const done = Math.max(a.submitted_users, a.subjective_users);
          return h('div', { class: 'list-row' },
            h('div', { class: 'list-row__main' },
              h('div', { class: 'list-row__title' }, a.title,
                U.badge(ASSIGNMENT_STATUS[a.status] || a.status, a.status === 'reviewing' ? 'blue' : a.overdue ? 'neutral' : 'brand'),
                a.peer_review ? U.badge('互评', 'warn') : null),
              h('div', { class: 'list-row__meta' },
                h('span', {}, `${done}/${dash.students} 人已交`),
                h('span', {}, a.due_at ? '截止 ' + U.fmtDate(a.due_at, { withTime: false }) : '未设截止'),
                a.pending_reviews ? h('span', { style: { color: 'var(--amber)' } }, `待评 ${a.pending_reviews}`) : null),
              U.progress(done / Math.max(1, dash.students))),
            h('div', { class: 'list-row__side' },
              h('a', { class: 'btn btn--soft btn--sm', href: `#/teacher/assignment/${a.id}` }, '详情')));
        }))
      : U.empty('还没有作业', '点击右上角「布置作业」创建第一次作业。')
  );

  const attention = U.card(
    U.cardHead('需要你关注', { sub: '截止、互评与异常' }),
    h('div', { class: 'col', style: { gap: '10px' } },
      st.pending_reviews
        ? U.alertRow('medium', `${st.pending_reviews} 份互评尚未完成`, '可在「评审过程管理」中查看每位评审者的进度，并发送提醒或重新分配。',
            h('a', { class: 'btn btn--soft btn--xs', href: '#/teacher/reviews' }, '去处理'))
        : null,
      st.open_anomalies
        ? U.alertRow('high', `${st.open_anomalies} 条异常评审待复核`, '包括长期偏高/偏低、单次显著偏离、异常评审时长与固定互评关系。',
            h('a', { class: 'btn btn--soft btn--xs', href: '#/teacher/anomalies' }, '去复核'))
        : null,
      needAttention.length
        ? U.alertRow('low', `${needAttention.length} 次作业处于互评或未截止状态`, '互评截止后结果会自动公布给学生。')
        : null,
      (!st.pending_reviews && !st.open_anomalies)
        ? U.empty('暂无需要处理的事项', '当前所有互评均已完成，异常检测未发现高风险评审。')
        : null
    )
  );

  const recent = U.card(
    U.cardHead('最近提交动态'),
    (dash.recent_submissions || []).length
      ? h('div', {}, ...dash.recent_submissions.slice(0, 8).map((s) =>
          h('div', { class: 'mini-row', style: { cursor: 'pointer' }, onclick: () => router.navigate('/student/submissions/' + s.id) },
            U.verdictBadge(s.verdict),
            h('span', {}, s.name),
            h('span', { class: 'muted small grow' }, s.title),
            h('span', { class: 'mini-row__time' }, U.timeAgo(s.submitted_at)))))
      : U.empty('暂无提交', '')
  );

  const quiz = klass
    ? U.card(
        U.cardHead('班级学情速览', { sub: '按题目通过率排序' }),
        h('div', { class: 'score-list' }, ...(klass.problems || []).slice(0, 8).map((p) =>
          h('div', { class: 'score-item' },
            h('span', { class: 'score-item__name', title: p.title }, p.title),
            U.meter(Math.round(p.pass_rate * 100), { tone: p.pass_rate > 0.7 ? 'ok' : p.pass_rate > 0.4 ? 'brand' : 'warn' }),
            h('span', { class: 'score-item__val' }, Math.round(p.pass_rate * 100) + '%'))))
      )
    : null;

  const classCard = U.card(
    U.cardHead('教学班', { sub: `${(dash.class_stats || []).length} 个班级` }),
    (dash.class_stats || []).length
      ? h('div', { class: 'col', style: { gap: '10px' } }, ...dash.class_stats.map((c) =>
          h('div', { class: 'list-row' },
            h('span', {}, U.icon.users),
            h('div', { class: 'list-row__main' },
              h('div', { class: 'list-row__title' }, c.class_name || '未分班'),
              h('div', { class: 'list-row__meta' }, h('span', {}, `${c.n} 名学生`))),
            U.badge('邀请码 ' + (dash.course.invite_code || '—'), 'brand'))))
      : U.empty('暂无班级', '')
  );

  const noticeBox = U.card(
    U.cardHead('课程通知', { actions: U.btn('发布通知', { tone: 'soft', size: 'sm', onClick: () => publishNotice() }) }),
    (dash.notices || []).length
      ? h('div', {}, ...dash.notices.map((n) =>
          h('div', { class: 'mini-row' }, h('span', { class: 'grow' }, h('b', {}, n.title), h('div', { class: 'small muted' }, n.content)),
            h('span', { class: 'mini-row__time' }, U.timeAgo(n.created_at)))))
      : U.empty('暂无通知', '发布通知后学生会立即看到。')
  );

  return h(
    'div',
    { class: 'col', style: { gap: '16px' } },
    hero,
    h('div', { class: 'dash-grid' },
      h('div', { class: 'col', style: { gap: '16px' } }, progressCard, recent),
      h('div', { class: 'col', style: { gap: '16px' } }, attention, classCard, quiz, noticeBox))
  );
}

async function publishNotice() {
  const title = h('input', { class: 'input', placeholder: '通知标题' });
  const content = h('textarea', { class: 'input input--area', placeholder: '通知内容' });
  U.modal('发布课程通知', h('div', { class: 'col', style: { gap: '14px' } },
    U.field('标题', title, { required: true }),
    U.field('内容', content, { required: true })), {
    width: 560,
    actions: (close) => [
      U.btn('取消', { tone: 'ghost', onClick: close }),
      U.btn('发布', {
        tone: 'primary',
        onClick: async () => {
          if (!title.value.trim() || !content.value.trim()) return fail('请填写标题与内容');
          try {
            await api.post('/api/notices', { course_id: state.courseId, title: title.value, content: content.value });
            ok('通知已发布');
            close();
            router.resolve();
          } catch (e) { fail(e.message); }
        },
      }),
    ],
  });
}

/* ======================================================== 作业管理 */

export async function loadAssignments() {
  const [assignments, problems, courses] = await Promise.all([
    api.get('/api/assignments'),
    api.get('/api/problems'),
    api.get('/api/courses'),
  ]);
  return { assignments, problems, courses };
}

export function renderAssignments({ assignments, problems, courses }) {
  const rows = assignments.map((a) => ({
    ...a,
    done: Math.max(a.submitted_users || 0, a.subjective_users || 0),
    students: a.students || 0,
  }));
  return h(
    'div',
    {},
    U.pageHeader('作业管理', {
      eyebrow: 'ASSIGNMENTS',
      sub: '创建作业、配置题目与评分规则、设置互评人数与截止时间；支持发布、延长截止与一键重测。',
      actions: U.btn('布置新作业', { tone: 'primary', icon: U.icon.plus, onClick: () => createAssignment(problems, courses, () => router.resolve()) }),
    }),
    U.card(
      U.table(
        [
          { title: '作业', render: (a) => h('div', {}, h('b', {}, a.title), h('div', { class: 'small muted' }, a.description || '')) },
          { title: '类型', width: '110px', render: (a) => (a.peer_review ? U.badge('互评主观题', 'warn') : U.badge('编程评测', 'brand')) },
          { title: '题目', width: '70px', class: 'num', render: (a) => a.problem_count },
          { title: '提交进度', width: '170px', render: (a) => h('div', {}, U.progress(a.done / Math.max(1, a.students)), h('span', { class: 'small muted' }, `${a.done}/${a.students} 人`)) },
          { title: '截止', width: '140px', render: (a) => (a.due_at ? U.fmtDate(a.due_at, { withTime: false }) : '未设') },
          { title: '状态', width: '110px', render: (a) => U.badge(ASSIGNMENT_STATUS[a.status] || a.status, a.status === 'reviewing' ? 'blue' : a.overdue ? 'neutral' : 'brand') },
          { title: '', width: '140px', render: (a) => h('div', { class: 'row', style: { gap: '6px' } },
              h('a', { class: 'btn btn--soft btn--xs', href: `#/teacher/assignment/${a.id}` }, '详情'),
              h('button', { class: 'btn btn--plain btn--xs', onclick: () => editAssignment(a, problems, () => router.resolve()) }, '编辑')) },
        ],
        rows,
        { empty: '还没有创建作业' }
      )
    )
  );
}

function createAssignment(problems, courses, onSaved, existing) {
  const draft = existing
    ? { ...existing, problem_ids: (existing.problems || []).map((p) => p.id) }
    : {
        course_id: state.courseId || (courses[0] && courses[0].id),
        title: '', description: '', type: 'programming', peer_review: 0,
        start_at: new Date().toISOString().slice(0, 19).replace('T', ' '),
        due_at: '', review_due_at: '', reviews_per_submission: 3, max_load: 4,
        aggregation_method: 'reliability_em', allocate_method: 'mcmf', status: 'published',
        problem_ids: [],
      };
  const chosen = new Set(draft.problem_ids || []);
  const listBox = h('div', { style: { maxHeight: '280px', overflowY: 'auto', border: '1px solid var(--line)', borderRadius: '12px', padding: '8px' } });
  const paintList = () => {
    clear(listBox);
    problems.forEach((p) => {
      listBox.appendChild(
        h('label', { class: 'list-row', style: { cursor: 'pointer', marginBottom: '6px' } },
          h('input', { type: 'checkbox', checked: chosen.has(p.id), onchange: (e) => { e.target.checked ? chosen.add(p.id) : chosen.delete(p.id); } }),
          h('div', { class: 'list-row__main' },
            h('div', { class: 'list-row__title' }, p.title),
            h('div', { class: 'list-row__meta' }, h('span', {}, PROBLEM_TYPE[p.type]), h('span', {}, '难度 ' + p.difficulty))),
          U.badge(p.type === 'programming' ? '编程' : '主观', p.type === 'programming' ? 'brand' : 'blue')))
    });
  };
  paintList();

  const peerSwitch = h('input', { type: 'checkbox', checked: !!draft.peer_review, onchange: (e) => { draft.peer_review = e.target.checked ? 1 : 0; togglePeer(); } });
  const peerBox = h('div', {});
  function togglePeer() {
    clear(peerBox);
    if (!draft.peer_review) return;
    peerBox.appendChild(
      h('div', { class: 'form-grid form-grid--3 mt12' },
        U.field('每份作业评审数 k', h('input', { class: 'input', type: 'number', min: 1, max: 6, value: draft.reviews_per_submission, oninput: (e) => (draft.reviews_per_submission = Number(e.target.value)) })),
        U.field('每人最多评审数 c', h('input', { class: 'input', type: 'number', min: 1, max: 10, value: draft.max_load, oninput: (e) => (draft.max_load = Number(e.target.value)) })),
        U.field('分配算法', U.select([
          { value: 'mcmf', label: '最小费用流（推荐）' },
          { value: 'greedy', label: '贪心负载均衡' },
          { value: 'random', label: '随机（基线）' },
        ], { value: draft.allocate_method, onchange: (e) => (draft.allocate_method = e.target.value) })),
        U.field('聚合方法', U.select(
          Object.entries(METHOD_LABEL).map(([k, v]) => ({ value: k, label: v })),
          { value: draft.aggregation_method, onchange: (e) => (draft.aggregation_method = e.target.value) }), { hint: '推荐「可信度动态加权(EM)」' }),
        U.field('互评截止时间', h('input', { class: 'input', type: 'datetime-local', value: (draft.review_due_at || '').replace(' ', 'T').slice(0, 16), oninput: (e) => (draft.review_due_at = e.target.value.replace('T', ' ') + ':00') })),
        U.note('分配与聚合都可以在「评审过程管理」中随时重新执行，并用实验台对比不同方法的效果。', 'ok'))
    );
  }
  togglePeer();

  const body = h(
    'div',
    {},
    h('div', { class: 'form-grid' },
      U.field('作业标题', h('input', { class: 'input', value: draft.title, oninput: (e) => (draft.title = e.target.value) }), { required: true }),
      U.field('作业类型', U.select([
        { value: 'programming', label: '编程评测' },
        { value: 'subjective', label: '主观题' },
        { value: 'mixed', label: '混合' },
      ], { value: draft.type, onchange: (e) => (draft.type = e.target.value) })),
      U.field('开放时间', h('input', { class: 'input', type: 'datetime-local', value: (draft.start_at || '').replace(' ', 'T').slice(0, 16), oninput: (e) => (draft.start_at = e.target.value.replace('T', ' ') + ':00') })),
      U.field('截止时间', h('input', { class: 'input', type: 'datetime-local', value: (draft.due_at || '').replace(' ', 'T').slice(0, 16), oninput: (e) => (draft.due_at = e.target.value.replace('T', ' ') + ':00') })),
      U.field('状态', U.select([
        { value: 'draft', label: '草稿' },
        { value: 'published', label: '进行中' },
        { value: 'reviewing', label: '互评中' },
        { value: 'closed', label: '已结束' },
      ], { value: draft.status, onchange: (e) => (draft.status = e.target.value) }))),
    h('div', { class: 'mt16' }, U.field('作业说明', U.textarea({ value: draft.description, style: { minHeight: '80px' }, oninput: (e) => (draft.description = e.target.value) }))),
    h('div', { class: 'mt16' }, h('label', { class: 'switch' }, peerSwitch, h('span', { class: 'switch__track' }), h('span', {}, '启用匿名互评（主观题）'))),
    peerBox,
    h('div', { class: 'mt16' }, U.field('选择题目', listBox, { hint: `已选 ${chosen.size} 道；编程题走自动评测，主观题进入互评流程` })),
  );

  U.modal(existing ? '编辑作业 · ' + draft.title : '布置新作业', body, {
    width: 860,
    actions: (close) => [
      U.btn('取消', { tone: 'ghost', onClick: close }),
      U.btn(existing ? '保存修改' : '创建作业', {
        tone: 'primary',
        onClick: async () => {
          if (!draft.title.trim()) return fail('请填写作业标题');
          if (!chosen.size) return fail('请至少选择一道题目');
          const payload = { ...draft, problem_ids: [...chosen] };
          try {
            if (existing) await api.put('/api/assignments/' + existing.id, payload);
            else await api.post('/api/assignments', payload);
            ok(existing ? '作业已更新' : '作业已创建');
            close();
            onSaved && onSaved();
          } catch (e) { fail(e.message); }
        },
      }),
    ],
  });
}

function editAssignment(a, problems, onSaved) {
  createAssignment(problems, [], onSaved, a);
}

/* ======================================================== 作业详情 */

export async function loadAssignmentDetail(ctx) {
  const id = ctx.params.id;
  const a = await api.get('/api/assignments/' + id);
  const [subs, allocs, results] = await Promise.all([
    api.get('/api/submissions', { assignment_id: id, limit: 500 }),
    a.peer_review ? api.get(`/api/assignments/${id}/allocations`).catch(() => null) : null,
    a.peer_review ? api.get(`/api/assignments/${id}/review-results`).catch(() => null) : null,
  ]);
  return { a, subs, allocs, results };
}

export function renderAssignmentDetail({ a, subs, allocs, results }) {
  const progProblems = a.problems.filter((p) => p.type === 'programming');
  const subjProblems = a.problems.filter((p) => p.type !== 'programming');
  return h(
    'div',
    {},
    U.pageHeader(a.title, {
      eyebrow: 'ASSIGNMENT #' + a.id,
      sub: `${a.description || ''}`,
      actions: [
        U.badge(ASSIGNMENT_STATUS[a.status] || a.status, a.status === 'reviewing' ? 'blue' : 'brand'),
        a.peer_review ? U.badge('匿名互评 · 每份 ' + a.reviews_per_submission + ' 份', 'warn') : null,
        U.btn('重测全部提交', {
          tone: 'ghost', size: 'sm', icon: U.icon.refresh,
          onClick: async () => {
            const yes = await confirmDialog({ title: '重测全部提交', message: '将对本次作业的前 80 条提交重新编译评测（可能耗时 1-2 分钟），已记录的成绩会被覆盖。', confirmText: '开始重测' });
            if (!yes) return;
            info('正在重测，请稍候…');
            try {
              const r = await api.post(`/api/assignments/${a.id}/rejudge`);
              ok(`重测完成：${r.rejudged} 条，判定变化 ${r.changes.length} 条`);
              router.resolve();
            } catch (e) { fail(e.message); }
          },
        }),
        h('a', { class: 'btn btn--ghost btn--sm', href: '#/teacher/assignments' }, '返回列表'),
      ],
    }),
    h('div', { class: 'stat-row mb16' },
      U.stat(a.problems.length, '题目数'),
      U.stat(subs.length, '提交总数', { tone: 'blue' }),
      U.stat(new Set(subs.map((s) => s.user_id)).size, '参与人数', { tone: 'ok' }),
      U.stat(a.due_at ? U.fmtDate(a.due_at, { withTime: false }) : '未设', '截止日期', { tone: 'warn' }),
      allocs ? U.stat(`${allocs.stats.done}/${allocs.stats.total}`, '互评完成', { tone: 'brand' }) : null),
    h('div', { class: 'grid grid--2 mb16' },
      ...a.problems.map((p) => {
        const isProg = p.type === 'programming';
        const mine = subs.filter((s) => s.problem_id === p.id);
        const pass = mine.filter((s) => s.verdict === 'Accepted').length;
        return U.card(
          U.cardHead(p.title, {
            sub: PROBLEM_TYPE[p.type] || p.type,
            actions: [
              U.badge(isProg ? '编程题' : '主观题', isProg ? 'brand' : 'blue'),
              h('button', { class: 'btn btn--plain btn--xs', onclick: () => router.navigate('/problem/' + p.id) }, '查看'),
            ],
          }),
          isProg
            ? h('div', {},
                h('div', { class: 'stat-row', style: { gridTemplateColumns: 'repeat(3,1fr)' } },
                  U.stat(`${p.ac_count}/${p.n_submit}`, '通过人数', { tone: 'ok' }),
                  U.stat(mine.length, '提交次数', { tone: 'blue' }),
                  U.stat(p.hidden_count + ' + 样例', '测试点', { tone: 'brand' })),
                h('div', { class: 'mt12' }, U.progress(p.ac_count / Math.max(1, a.submitted_users || 1))))
            : h('div', { class: 'stat-row', style: { gridTemplateColumns: 'repeat(2,1fr)' } },
                U.stat(p.n_subjective || 0, '已提交人数', { tone: 'blue' }),
                U.stat((p.rubric || []).filter((r) => r.key).length || 4, '评分维度', { tone: 'brand' }))
        );
      })),
    progProblems.length
      ? U.card(
          U.cardHead('提交记录', { sub: `${subs.length} 条（点击查看逐测试点与源码）` }),
          U.table(
            [
              { title: '学生', render: (s) => h('div', {}, h('b', {}, s.user_name), h('div', { class: 'small muted' }, s.class_name || '')) },
              { title: '题目', render: (s) => s.problem_title },
              { title: '判定', width: '110px', render: (s) => U.verdictBadge(s.verdict) },
              { title: '得分', width: '80px', class: 'num', render: (s) => s.score },
              { title: '耗时', width: '100px', class: 'num', render: (s) => U.fmtTime(s.time_ms) },
              { title: '内存', width: '100px', class: 'num', render: (s) => U.fmtMem(s.memory_kb) },
              { title: '语言', width: '80px', render: (s) => U.badge(s.language, 'neutral') },
              { title: '时间', width: '140px', render: (s) => U.fmtDate(s.submitted_at) },
            ],
            subs.slice(0, 200),
            { dense: true, empty: '暂无提交', onRow: (s) => openSubmissionDrawer(s.id) }
          )
        )
      : null,
    results && results.length
      ? h('div', { class: 'mt16' }, ...results.map((r) =>
          U.card(
            U.cardHead(r.problem_title + ' · 互评结果', {
              sub: `共 ${r.rows.length} 份提交`,
              actions: h('a', { class: 'btn btn--ghost btn--sm', href: '#/teacher/reviews' }, '评审过程管理'),
            }),
            U.table(
              [
                { title: '学生', render: (x) => h('div', {}, h('b', {}, x.name), h('div', { class: 'small muted' }, x.student_no || '')) },
                { title: '最终分', width: '90px', class: 'num', render: (x) => h('b', { style: { color: 'var(--brand)' } }, x.score) },
                { title: '原始评分', render: (x) => h('div', { class: 'small mono' }, x.raw.join(' / ')) },
                { title: '极差', width: '80px', class: 'num', render: (x) => x.spread },
                { title: '评审数', width: '80px', class: 'num', render: (x) => x.n_reviews },
              ],
              r.rows,
              { dense: true }
            ),
            h('div', { class: 'mt16' }, U.cardHead('聚合方法对比', { sub: '同一批评审在不同聚合方法下的差异' }),
              U.table(
                [
                  { title: '方法', render: (x) => x.label },
                  { title: 'RMSE（对真值）', class: 'num', render: (x) => (x.rmse == null ? '—' : x.rmse) },
                  { title: '留一稳定性 MAD', class: 'num', render: (x) => x.stability_mad },
                  { title: '与平均分的秩相关', class: 'num', render: (x) => x.rank_corr_vs_mean },
                ],
                r.comparison, { dense: true }))
          )))
      : null
  );
}

async function openSubmissionDrawer(id) {
  const s = await api.get('/api/submissions/' + id);
  const results = (s.detail && s.detail.results) || s.test_results || [];
  const drawer = U.drawer(
    `${s.user_name} · ${s.problem_title}`,
    h(
      'div',
      {},
      h('div', { class: 'row mb16' },
        U.verdictBadge(s.verdict, { full: true }),
        h('span', { class: 'grow' }),
        h('span', { class: 'muted small' }, `第 ${s.attempt_no} 次 · ${U.fmtDate(s.submitted_at)}`)),
      h('div', { class: 'stat-row mb16' },
        U.stat(s.score, '得分'),
        U.stat(U.fmtTime(s.time_ms), '最长用时', { tone: 'blue' }),
        U.stat(U.fmtMem(s.memory_kb), '峰值内存', { tone: 'warn' })),
      results.length
        ? h('div', { class: 'mb16' }, ...results.map((c) =>
            h('div', { class: 'case-line' }, U.verdictBadge(c.verdict),
              h('span', { class: 'case-line__name' }, c.name),
              h('span', { class: 'case-line__io' }, U.fmtTime(c.time_ms)))))
        : null,
      s.compile_message ? U.note(s.compile_message.slice(0, 600), 'warn') : null,
      h('h4', { class: 'small muted mt16 mb8' }, '源代码'),
      U.codeBlock(s.source_code, s.language),
      h('div', { class: 'row mt16' },
        U.btn('重测这份提交', {
          tone: 'primary', size: 'sm', icon: U.icon.refresh,
          onClick: async () => {
            try {
              const r = await api.post(`/api/submissions/${id}/rejudge`);
              ok(`重测完成：${r.verdict}` + (r.passed != null ? `（${r.passed}/${r.total_cases}）` : ''));
              drawer.close();
              router.resolve();
            } catch (e) { fail(e.message); }
          },
        }),
        U.btn('关闭', { tone: 'ghost', size: 'sm', onClick: () => drawer.close() }))
    ),
    { width: 620 }
  );
}

/* ==================================================== 提交与评测 */

export async function loadTeacherSubmissions(ctx) {
  const [rows, problems, courses] = await Promise.all([
    api.get('/api/submissions', { limit: 400, ...ctx.query }),
    api.get('/api/problems'),
    api.get('/api/courses'),
  ]);
  const stats = await api.get('/api/submissions/stats/overview', { course_id: courses[0] && courses[0].id });
  return { rows, problems, stats };
}

export function renderTeacherSubmissions({ rows, problems, stats }) {
  let verdict = '';
  let problemId = '';
  let keyword = '';
  const box = h('div');
  const distribution = Object.entries(stats.by_verdict || {});
  const paint = () => {
    const filtered = rows.filter((r) =>
      (!verdict || r.verdict === verdict) &&
      (!problemId || String(r.problem_id) === String(problemId)) &&
      (!keyword || (r.user_name || '').includes(keyword) || (r.problem_title || '').includes(keyword)));
    clear(box);
    box.appendChild(
      U.table(
        [
          { title: '学生', render: (r) => h('div', {}, h('b', {}, r.user_name), h('div', { class: 'small muted' }, r.class_name || '')) },
          { title: '题目', render: (r) => r.problem_title },
          { title: '判定', width: '110px', render: (r) => U.verdictBadge(r.verdict) },
          { title: '得分', width: '80px', class: 'num', render: (r) => r.score },
          { title: '耗时', width: '100px', class: 'num', render: (r) => U.fmtTime(r.time_ms) },
          { title: '内存', width: '100px', class: 'num', render: (r) => U.fmtMem(r.memory_kb) },
          { title: '语言', width: '80px', render: (r) => U.badge(r.language, 'neutral') },
          { title: '次数', width: '64px', class: 'num', render: (r) => r.attempt_no },
          { title: '时间', width: '140px', render: (r) => U.fmtDate(r.submitted_at) },
        ],
        filtered.slice(0, 250),
        { dense: true, empty: '没有符合条件的提交', onRow: (r) => openSubmissionDrawer(r.id) }
      )
    );
  };
  paint();
  return h(
    'div',
    {},
    U.pageHeader('提交与评测', {
      eyebrow: 'SUBMISSIONS',
      sub: '查看全班提交记录、判定分布与运行资源使用；支持按题目/判定筛选、查看源码与重新评测。',
      actions: h('a', { class: 'btn btn--ghost', href: '#/teacher/similarity' }, '代码相似度检测'),
    }),
    h('div', { class: 'dash-grid mb16' },
      U.card(
        U.cardHead('判定分布', { sub: `共 ${stats.total} 次提交，通过率 ${Math.round((stats.ac_rate || 0) * 100)}%` }),
        distribution.length
          ? C.donutChart(
              distribution.map(([k, v]) => ({ label: k, value: v, color: verdictColor(k) })),
              { width: 300, height: 210, centerValue: stats.total, centerLabel: '次提交' })
          : U.empty('暂无数据', '')
      ),
      U.card(
        U.cardHead('常见错误', { sub: '按题目与判定类型统计' }),
        h('div', { class: 'score-list' }, ...distribution.map(([k, v]) =>
          h('div', { class: 'score-item' },
            h('span', { class: 'score-item__name' }, k),
            U.meter(Math.round((v / Math.max(1, stats.total)) * 100), { tone: k === 'Accepted' ? 'ok' : 'warn' }),
            h('span', { class: 'score-item__val' }, v))))
      )
    ),
    h('div', { class: 'filterbar' },
      h('div', { class: 'search-box' }, h('span', { class: 'search-box__icon', html: U.icon.search }),
        h('input', { class: 'input search', placeholder: '搜索学生或题目…', oninput: (e) => { keyword = e.target.value.trim(); paint(); } })),
      U.select([{ value: '', label: '全部题目' }, ...problems.map((p) => ({ value: p.id, label: p.title }))],
        { onchange: (e) => { problemId = e.target.value; paint(); } }),
      U.select([{ value: '', label: '全部判定' }, ...Object.keys(VERDICT_MEANING).map((v) => ({ value: v, label: v }))],
        { onchange: (e) => { verdict = e.target.value; paint(); } })
    ),
    box
  );
}

function verdictColor(v) {
  return { Accepted: '#17a06a', 'Wrong Answer': '#c0503f', 'Time Limit Exceeded': '#c98a1f', 'Runtime Error': '#b45fa6', 'Compile Error': '#7b8f87' }[v] || '#5f7f93';
}
