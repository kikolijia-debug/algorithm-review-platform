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
  const [dash, chapters] = await Promise.all([
    api.get('/api/dashboard/teacher'),
    api.get('/api/chapters').catch(() => []),
  ]);
  return { dash, chapters };
}

/**
 * 教学看板只做「入口」：不放统计图表与列表，
 * 数据一律去对应的功能页看，避免同一份数据在多处出现、口径不一致。
 */
export function renderTeacherDashboard({ dash, chapters }) {
  const course = (dash && dash.course) || {};
  const st = (dash && dash.stats) || {};
  const nChapters = (chapters || []).length;
  const pendingAlloc = (dash && dash.assignments || []).filter((a) => a.need_confirm).length;
  // 顶栏徽章与这里用同一个口径（refreshBadges 已经取过一次）
  const anomalies = state.openAnomalies || st.open_anomalies || 0;
  // 新注册的教师还没有课程：给出创建引导，而不是显示别人的数据
  if (!course.id) {
    return h('div', { class: 'launch' },
      h('div', { class: 'launch__head' },
        h('div', { class: 'launch__title' }, '教学看板'),
        h('div', { class: 'launch__sub' }, '你还没有课程，先建一门课就能开始了')),
      U.card(
        U.cardHead('创建第一门课程', { sub: '创建后系统会生成课程邀请码，学生凭邀请码加入' }),
        h('div', { class: 'col', style: { gap: '12px', maxWidth: '460px' } },
          U.field('课程名称', h('input', { class: 'input', id: 'new-course-name', value: '算法设计与分析' })),
          U.field('学期（选填）', h('input', { class: 'input', id: 'new-course-term', placeholder: '例如 2026 秋季' })),
          U.btn('创建课程', {
            tone: 'primary',
            onClick: async () => {
              const nm = (document.getElementById('new-course-name').value || '').trim();
              const term = (document.getElementById('new-course-term').value || '').trim();
              if (!nm) return fail('请填写课程名称');
              try {
                const c = await api.post('/api/courses', { name: nm, term });
                state.courseId = c.id;
                ok('课程已创建，邀请码：' + c.invite_code);
                router.resolve();
              } catch (e) { fail(e.message); }
            },
          }),
          U.note('建好课程后，去「班级与学生」新建班级、批量导入学生名单，'
            + '再到「作业与题库」出题、布置作业。', 'ok')))
    );
  }

  // 只保留「图标 + 名称 + 一行提示」，点击即进入对应工作台
  const entries = [
    { title: '作业与题库', icon: 'book', hint: '布置作业 · 按章节出题', href: '#/teacher/work' },
    { title: '班级与学生', icon: 'users', hint: '班级概览 · 成员管理', href: '#/teacher/students' },
    { title: '学情分析', icon: 'chart', hint: '通过率 · 成绩 · 知识点', href: '#/teacher/analytics' },
    {
      title: '评审管理', icon: 'shield', hint: '分配确认 · 评分复核', href: '#/teacher/reviews',
      badge: anomalies, extra: pendingAlloc,
    },
    { title: '算法实验台', icon: 'spark', hint: '方法对比 · 复杂度实测', href: '#/teacher/experiments' },
    { title: '课程资源', icon: 'doc', hint: `${nChapters} 个章节课件`, href: '#/materials' },
  ];

  return h(
    'div',
    { class: 'launch' },
    h('div', { class: 'launch__head' },
      h('div', { class: 'launch__title' }, '教学看板'),
      h('div', { class: 'launch__sub' }, (course.name || '算法设计与分析') + ' · 选择下面任意一个入口')),
    h('div', { class: 'launch__grid' },
      ...entries.map((e) =>
        h('a', { class: 'launch__item', href: e.href, title: e.hint },
          h('span', { class: 'launch__icon', html: U.icon[e.icon] }),
          h('span', { class: 'launch__name' }, e.title),
          h('span', { class: 'launch__hint' }, e.hint),
          (e.badge || e.extra)
            ? h('span', { class: 'launch__dot', title: '有待处理事项' },
                (e.badge || 0) + (e.extra || 0) > 99 ? '99+' : String((e.badge || 0) + (e.extra || 0)))
            : null)))
  );
}

/* ======================================================== 作业管理 */

export async function loadAssignments() {
  const [assignments, problems, courses, chapters] = await Promise.all([
    api.get('/api/assignments'),
    api.get('/api/problems'),
    api.get('/api/courses'),
    api.get('/api/chapters').catch(() => []),
  ]);
  return { assignments, problems, courses, chapters };
}

export function renderAssignments({ assignments, problems, courses, chapters }) {
  const rows = assignments.map((a) => ({
    ...a,
    done: Math.max(a.submitted_users || 0, a.subjective_users || 0),
    students: a.students || 0,
    rate: Math.min(1, Math.max(a.submitted_users || 0, a.subjective_users || 0) / Math.max(1, a.students || 1)),
  }));
  const doneAll = rows.filter((a) => !a.overdue && a.status !== 'closed');
  return h(
    'div',
    {},
    U.pageHeader('作业管理', {
      eyebrow: 'ASSIGNMENTS',
      sub: '创建作业、配置题目与评分规则、设置互评与截止时间；作业完成情况在这里统一查看。',
      actions: U.btn('布置新作业', { tone: 'primary', icon: U.icon.plus, onClick: () => createAssignment(problems, courses, () => router.resolve(), null, chapters) }),
    }),
    h(
      'div',
      { class: 'stat-row mb16' },
      U.stat(rows.length, '作业总数'),
      U.stat(doneAll.length, '进行中', { tone: 'brand' }),
      U.stat(rows.filter((a) => a.peer_review).length, '含互评', { tone: 'blue' }),
      U.stat(rows.filter((a) => a.pending_reviews).length, '待评未完成', {
        tone: rows.some((a) => a.pending_reviews) ? 'warn' : 'ok',
      })
    ),
    U.card(
      rows.length
        ? h('div', { class: 'assign-list' }, ...rows.map((a) => assignmentRow(a, problems, chapters)))
        : U.empty('还没有创建作业', '点右上角「布置新作业」创建第一次作业。')
    )
  );
}

/** 作业列表里的一行：标题 + 关键信息 + 完成情况，避免宽表格带来的挤压与截断 */
function assignmentRow(a, problems, chapters) {
  const typeBadge = a.peer_review
    ? U.badge('匿名互评', 'warn')
    : U.badge('自动评测', 'brand');
  const statusBadge = U.badge(
    ASSIGNMENT_STATUS[a.status] || a.status,
    a.status === 'reviewing' ? 'blue' : a.overdue ? 'neutral' : 'brand'
  );
  const bits = [
    `${a.problem_count} 道题`,
    a.due_at ? `截止 ${U.fmtDate(a.due_at, { withTime: false })}` : '未设截止',
    a.review_due_at ? `互评截止 ${U.fmtDate(a.review_due_at, { withTime: false })}` : null,
  ].filter(Boolean);

  return h('div', { class: 'assign-row' },
    h('div', { class: 'assign-row__main' },
      h('div', { class: 'assign-row__title' }, h('b', {}, a.title), typeBadge, statusBadge),
      h('div', { class: 'assign-row__meta' }, ...bits.map((t) => h('span', {}, t))),
      a.description ? h('div', { class: 'assign-row__desc wrap-any' }, a.description) : null,
      h('div', { class: 'assign-row__progress' },
        U.progress(a.rate, { tone: a.rate >= 0.8 ? 'ok' : a.rate >= 0.5 ? 'brand' : 'warn' }),
        h('span', { class: 'small muted' },
          `提交 ${a.done}/${a.students} 人`
          + ` · 通过 ${a.accepted_users || 0} 人`
          + (a.avg_score === null || a.avg_score === undefined ? '' : ` · 均分 ${a.avg_score}`)
          + (a.peer_review
              ? (a.need_confirm ? ' · 互评待确认发布' : ` · 互评 ${a.review_done || 0}/${a.review_total || 0}`)
              : '')))),
    h('div', { class: 'assign-row__side' },
      h('a', { class: 'btn btn--soft btn--sm', href: `#/teacher/assignment/${a.id}` }, '进入作业'),
      h('button', {
        class: 'btn btn--plain btn--xs',
        onclick: () => editAssignment(a, problems, () => router.resolve(), chapters),
      }, '编辑设置'))
  );
}

function createAssignment(problems, courses, onSaved, existing, chapters) {
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
  const listBox = h('div', { class: 'pick-list' });
  // 选题按课程章节分组：先选章节，再在章节内挑题目
  let pickChapter = 'all';
  let pickKeyword = '';
  const chapterLabel = new Map((chapters || []).map((c) => [c.key, c.label]));
  const countLabel = h('div', { class: 'small muted' },
    `已选 ${chosen.size} 道；编程题走自动评测，主观题进入互评流程`);
  const paintList = () => {
    clear(listBox);
    const visible = problems.filter((p) =>
      (pickChapter === 'all' || p.chapter === pickChapter) &&
      (!pickKeyword || p.title.includes(pickKeyword)));
    if (!visible.length) {
      listBox.appendChild(U.empty('没有符合条件的题目', '换个章节或关键词试试。'));
      return;
    }
    // 按章节分组展示，组内保持题库顺序
    const groups = [];
    const index = new Map();
    visible.forEach((p) => {
      const key = p.chapter || 'other';
      if (!index.has(key)) {
        index.set(key, groups.length);
        groups.push({ key, items: [] });
      }
      groups[index.get(key)].items.push(p);
    });
    const ordered = groups.slice().sort((a, b) => {
      const ai = (chapters || []).findIndex((c) => c.key === a.key);
      const bi = (chapters || []).findIndex((c) => c.key === b.key);
      return (ai < 0 ? 999 : ai) - (bi < 0 ? 999 : bi);
    });
    ordered.forEach((g) => {
      const label = chapterLabel.get(g.key) || '拓展（未对应课件章节）';
      listBox.appendChild(h('div', { class: 'pick-group' },
        h('div', { class: 'pick-group__head' }, label,
          h('span', { class: 'small muted' }, ` · ${g.items.length} 题`)),
        ...g.items.map((p) =>
          h('label', { class: 'list-row pick-row' },
            h('input', {
              type: 'checkbox', checked: chosen.has(p.id),
              onchange: (e) => {
                if (e.target.checked) chosen.add(p.id); else chosen.delete(p.id);
                countLabel.textContent = `已选 ${chosen.size} 道；编程题走自动评测，主观题进入互评流程`;
              },
            }),
            h('div', { class: 'list-row__main' },
              h('div', { class: 'list-row__title' }, p.title),
              h('div', { class: 'list-row__meta' },
                h('span', {}, PROBLEM_TYPE[p.type]),
                h('span', {}, '难度 ' + p.difficulty),
                (p.topics || []).length ? h('span', {}, p.topics.slice(0, 2).join(' / ')) : null)),
            U.badge(p.type === 'programming' ? '编程' : '主观',
              p.type === 'programming' ? 'brand' : 'blue')))
      ));
    });
  };
  paintList();
  const pickBar = h(
    'div',
    { class: 'filterbar', style: { marginBottom: '8px' } },
    U.select(
      [{ value: 'all', label: '全部章节' }].concat(
        (chapters || []).map((c) => ({ value: c.key, label: c.label }))
      ),
      { value: pickChapter, onchange: (e) => { pickChapter = e.target.value; paintList(); } }
    ),
    h('div', { class: 'search-box' },
      h('span', { class: 'search-box__icon', html: U.icon.search }),
      h('input', {
        class: 'input search', placeholder: '搜索题目…',
        oninput: (e) => { pickKeyword = e.target.value.trim(); paintList(); },
      })),
    h('div', { class: 'grow' }),
    countLabel
  );

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
    h('div', { class: 'mt16' },
      U.field('选择题目（按课程章节）', h('div', {}, pickBar, listBox))),
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

function editAssignment(a, problems, onSaved, chapters) {
  createAssignment(problems, [], onSaved, a, chapters);
}

/* ======================================================== 作业详情 */

export async function loadAssignmentDetail(ctx) {
  const id = ctx.params.id;
  const [a, progress] = await Promise.all([
    api.get('/api/assignments/' + id),
    api.get(`/api/assignments/${id}/progress`).catch(() => null),
  ]);
  const [allocs, results] = await Promise.all([
    a.peer_review ? api.get(`/api/assignments/${id}/allocations`).catch(() => null) : null,
    a.peer_review ? api.get(`/api/assignments/${id}/review-results`).catch(() => null) : null,
  ]);
  return { a, progress, allocs, results };
}

export function renderAssignmentDetail({ a, progress, allocs, results }) {
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
      ],
    }),
    a.peer_review && a.allocation_status === 'draft'
      ? U.alertRow('high', '本轮互评分配待你确认',
          '分配结果已生成但尚未发布，学生此刻看不到评审任务。确认没问题后请到「评审管理 → 分配管理」点击「确认并发布」；'
          + '需要换人也可以在那里逐个调整。',
          h('a', { class: 'btn btn--soft btn--xs', href: `#/teacher/reviews?assignment_id=${a.id}` }, '去确认'))
      : null,
    progress
      ? studentProgressBlock(a, progress, subjProblems)
      : U.empty('暂无完成情况', '该作业还没有学生数据。'),
    results && results.length
      ? h('div', { class: 'mt16' }, ...results.map((r) =>
          U.card(
            U.cardHead(r.problem_title + ' · 互评结果', {
              sub: `共 ${r.rows.length} 份提交 · 点「评审明细」可看每位评审者给的分与文字意见`,
              actions: h('a', { class: 'btn btn--ghost btn--sm', href: '#/teacher/reviews' }, '评审过程管理'),
            }),
            U.table(
              [
                { title: '学生', render: (x) => h('div', {}, h('b', {}, x.name), h('div', { class: 'small muted' }, x.student_no || '')) },
                { title: '最终分', width: '90px', class: 'num', render: (x) => h('b', { style: { color: 'var(--brand)' } }, x.score) },
                { title: '各评审给分', render: (x) => h('div', { class: 'small mono' }, (x.raw || []).map((v) => v.toFixed(0)).join(' / ') || '—') },
                { title: '极差', width: '80px', class: 'num', render: (x) => x.spread },
                { title: '评审人数', width: '90px', class: 'num', render: (x) => x.n_reviews },
                {
                  title: '', width: '96px',
                  render: (x) => h('button', {
                    class: 'btn btn--plain btn--xs',
                    onclick: () => openReviewDetail(x, r.problem_title),
                  }, '评审明细'),
                },
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

/**
 * 单个作业里的「全班完成情况」：一行一位学生，一列一道题。
 * 点某一行的「查看具体提交」可以看到这名学生每道题的提交、判定、得分与源码。
 */
function studentProgressBlock(a, progress, subjProblems) {
  const problems = progress.problems || [];
  const st = progress.stats || {};
  let onlyMissing = false;
  const box = h('div');

  const paint = () => {
    clear(box);
    const rows = (progress.students || []).filter(
      (r) => !onlyMissing || r.submitted_problems < problems.length);
    box.appendChild(
      U.card(
        U.cardHead('全班完成情况', {
          sub: `满分 ${progress.full_score} 分 · 每道题满分 100 分 · 得分取该生每题的最高分`,
          actions: h('label', { class: 'switch switch--sm' },
            h('input', {
              type: 'checkbox', checked: onlyMissing,
              onchange: (e) => { onlyMissing = e.target.checked; paint(); },
            }),
            h('span', { class: 'switch__track' }),
            h('span', { class: 'small' }, '只看未交齐')),
        }),
        h('div', { class: 'stat-row mb16' },
          U.stat(st.students || 0, '学生人数'),
          U.stat(st.submitted_all || 0, '全部题目已交', { tone: 'ok' }),
          U.stat((st.students || 0) - (st.submitted_all || 0), '存在缺交', {
            tone: (st.students || 0) - (st.submitted_all || 0) ? 'warn' : 'ok',
          }),
          U.stat(st.avg_score == null ? '—' : st.avg_score, '平均得分', { tone: 'brand' }),
          U.stat(progress.full_score, '满分', { tone: 'blue' })),
        U.table(
          [
            { title: '#', width: '46px', render: (r) => r.rank },
            {
              title: '学生',
              render: (r) => h('div', {},
                h('b', {}, r.name),
                h('div', { class: 'small muted' }, [r.class_name, r.student_no].filter(Boolean).join(' · '))),
            },
            {
              title: '完成情况', width: '190px',
              render: (r) => h('div', {},
                U.progress(r.submitted_problems / Math.max(1, problems.length), {
                  tone: r.submitted_problems === problems.length ? 'ok' : 'warn',
                }),
                h('span', { class: 'small muted' }, `${r.submitted_problems}/${problems.length} 题已交`)),
            },
            {
              title: '通过题数', width: '100px', class: 'num',
              render: (r) => h('span', { class: r.solved_problems ? '' : 'muted' },
                `${r.solved_problems}/${problems.length}`),
            },
            {
              title: '得分', width: '110px', class: 'num',
              render: (r) => h('div', {},
                h('b', { style: { color: 'var(--brand)' } }, r.score),
                h('div', { class: 'small muted' }, Math.round(r.score_rate * 100) + '%')),
            },
            { title: '提交次数', width: '90px', class: 'num', render: (r) => r.tries },
            {
              title: '逐题状态', render: (r) => h('div', { class: 'cell-dots' },
                ...problems.map((p) => {
                  const c = r.cells[String(p.id)] || {};
                  const tone = !c.submitted ? 'none'
                    : c.type === 'programming' ? (c.solved ? 'ok' : (c.verdict ? 'bad' : 'mid'))
                    : 'mid';
                  const label = !c.submitted ? '未提交'
                    : c.type === 'programming' ? (c.solved ? '已通过 ' + c.best : (c.verdict || '已提交') + ' ' + (c.best ?? ''))
                    : '已提交 · 互评 ' + (c.review_score == null ? '未出分' : c.review_score);
                  return h('span', {
                    class: 'cell-dot cell-dot--' + tone,
                    title: p.title + '：' + label + (c.tries ? `（共提交 ${c.tries} 次）` : ''),
                  }, c.submitted ? (c.type === 'programming' ? (c.solved ? '✓' : '×') : '文') : '–');
                })),
            },
            {
              title: '', width: '120px',
              render: (r) => h('button', {
                class: 'btn btn--soft btn--xs',
                onclick: () => openStudentSubmission(r, problems, a),
              }, '查看具体提交'),
            },
          ],
          rows,
          { dense: true, empty: '没有符合条件的学生' }
        )
      )
    );
  };
  paint();
  return h('div', { class: 'mb16' }, box);
}

async function openStudentSubmission(row, problems, a) {
  const body = h('div', {}, U.loading('正在读取该同学的提交…'));
  const drawer = U.drawer(`${row.name} · ${a.title}`, body, { width: 780 });
  const lines = [];
  problems.forEach((p) => {
    const c = row.cells[String(p.id)] || {};
    lines.push(
      h('div', { class: 'sub-line' },
        h('div', { class: 'sub-line__head' },
          h('b', {}, p.title),
          p.type === 'programming' ? U.badge('编程题', 'brand') : U.badge('主观题', 'blue'),
          c.submitted
            ? (c.solved ? U.badge('已通过', 'ok')
              : c.type === 'programming' ? U.verdictBadge(c.verdict) : U.badge('已提交', 'warn'))
            : U.badge('未提交', 'neutral')),
        h('div', { class: 'sub-line__meta' },
          h('span', {}, `提交 ${c.tries || 0} 次`),
          c.best != null ? h('span', {}, `最高分 ${c.best}`) : null,
          c.time_ms ? h('span', {}, `用时 ${U.fmtTime(c.time_ms)}`) : null,
          c.memory_kb ? h('span', {}, `内存 ${U.fmtMem(c.memory_kb)}`) : null,
          c.language ? h('span', {}, c.language) : null,
          c.submitted_at ? h('span', {}, U.fmtDate(c.submitted_at)) : null,
          c.review_score != null ? h('span', {}, `互评得分 ${c.review_score}`) : null),
        h('div', { class: 'row mt8', style: { gap: '8px' } },
          c.submission_id
            ? U.btn('查看代码与逐测试点', {
                tone: 'soft', size: 'xs',
                onClick: () => openSubmissionDrawer(c.submission_id),
              })
            : null,
          p.type !== 'programming'
            ? U.btn('查看主观题作答', {
                tone: 'soft', size: 'xs',
                onClick: () => openSubjectiveDrawer(row.user_id, p.id),
              })
            : null,
          !c.submitted ? h('span', { class: 'small muted' }, '该同学没有提交这道题') : null)
      )
    );
  });
  clear(body).appendChild(h('div', {},
    h('div', { class: 'row mb16', style: { gap: '8px', flexWrap: 'wrap' } },
      U.badge(`完成 ${row.submitted_problems}/${problems.length} 题`, 'brand'),
      U.badge(`通过 ${row.solved_problems} 题`, 'ok'),
      U.badge(`得分 ${row.score} / ${(problems.length * 100)}`, 'blue'),
      U.badge(`提交 ${row.tries} 次`, 'neutral')),
    h('div', { class: 'col', style: { gap: '10px' } }, ...lines)));
  return drawer;
}

async function openSubjectiveDrawer(userId, problemId) {
  try {
    const rows = await api.get('/api/subjective', { problem_id: problemId });
    const mine = (rows || []).find((r) => r.user_id === userId);
    if (!mine) return fail('没有找到这道题的主观题作答');
    const detail = await api.get('/api/subjective/' + mine.id);
    const content = detail.content || {};
    const rubric = detail.rubric || [];
    const sections = (rubric[0] && rubric[0].sections) || [];
    U.drawer(`${detail.user_name || ''} · ${detail.problem_title}`, h('div', {},
      h('div', { class: 'row mb16', style: { gap: '8px' } },
        U.badge(detail.status === 'done' ? '已完成互评' : '等待互评', detail.status === 'done' ? 'ok' : 'warn'),
        detail.final_score != null ? U.badge('互评得分 ' + detail.final_score, 'brand') : null),
      h('div', { class: 'col', style: { gap: '14px' } },
        ...(sections.length
          ? sections.map((s) => h('div', {},
              h('h4', { class: 'small' }, s.name),
              h('div', { class: 'conclusion' }, content[s.key] || '（未作答）')))
          : Object.entries(content).map(([k, v]) => h('div', {},
              h('h4', { class: 'small' }, k),
              h('div', { class: 'conclusion' }, String(v))))))
    ), { width: 720 });
  } catch (e) {
    fail(e.message);
  }
}

/** 某份互评结果里，谁评的、给了几分、写了什么意见 */
function openReviewDetail(row, problemTitle) {
  const details = row.details || [];
  U.drawer(`${row.name} · ${problemTitle} 的评审明细`, h('div', {},
    h('div', { class: 'row mb16', style: { gap: '8px', flexWrap: 'wrap' } },
      U.badge(`最终得分 ${row.score}`, 'brand'),
      U.badge(`${details.length} 位评审者`, 'blue'),
      row.spread > 20 ? U.badge(`极差 ${row.spread}（分歧较大）`, 'warn') : U.badge(`极差 ${row.spread}`, 'neutral')),
    details.length
      ? h('div', { class: 'col', style: { gap: '10px' } }, ...details.map((d) =>
          h('div', { class: 'sub-line' },
            h('div', { class: 'sub-line__head' },
              h('b', {}, d.reviewer_name || ('#' + d.reviewer_id)),
              h('span', { class: 'small muted' }, d.reviewer_class || ''),
              U.badge('给分 ' + (d.total == null ? '—' : d.total), (d.total || 0) > row.score + 10 ? 'warn' : 'brand')),
            h('div', { class: 'sub-line__meta' },
              Object.entries(d.scores || {}).map(([k, v]) => h('span', {}, `${k} ${v}`)),
              d.duration_sec ? h('span', {}, `用时 ${Math.round(d.duration_sec)} 秒`) : null,
              d.submitted_at ? h('span', {}, U.fmtDate(d.submitted_at)) : null),
            d.comment ? h('div', { class: 'conclusion mt8' }, d.comment) : null))
        )
      : U.empty('这位同学的作业还没有收到评审', '')));
}

export async function openSubmissionDrawerById(id) {
  return openSubmissionDrawer(id);
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
      sub: '提交记录、判定分布与运行资源；支持筛选、查看源码与重测。',
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
