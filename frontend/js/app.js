/**
 * 应用入口：外壳布局（侧栏 + 顶栏）+ 路由注册 + 登录守卫。
 */

import { h, clear } from './core/dom.js';
import { state, load, save, setTheme, reset, isTeacher, emit } from './core/store.js';
import * as api from './core/api.js';
import * as router from './core/router.js';
import { toast, fail, confirmDialog } from './core/toast.js';
import { avatar, icon, loading, empty } from './core/ui.js';

import { renderLanding, renderLogin } from './pages/public.js';
import { renderProblem } from './pages/problem.js';
import * as S from './pages/student.js';
import * as T from './pages/teacher-core.js';
import * as TI from './pages/teacher-insight.js';

/* --------------------------------------------------------------- 导航表 */

const NAV = {
  student: [
    {
      group: '工作区',
      items: [
        { label: '学习动态', path: '/student', icon: icon.spark },
        { label: '题库与作业', path: '/problems', icon: icon.book },
        { label: '我的提交', path: '/student/submissions', icon: icon.code },
        { label: '互评中心', path: '/student/reviews', icon: icon.users, badge: 'peerPending' },
        { label: '我的主观题', path: '/student/subjective', icon: icon.check },
        { label: '学习报告', path: '/student/report', icon: icon.chart },
      ],
    },
  ],
  teacher: [
    {
      group: '教学',
      items: [
        { label: '教学看板', path: '/teacher', icon: icon.spark },
        { label: '作业管理', path: '/teacher/assignments', icon: icon.book },
        { label: '题库管理', path: '/problems', icon: icon.code },
        { label: '提交与评测', path: '/teacher/submissions', icon: icon.chart },
      ],
    },
    {
      group: '学习分析',
      items: [
        { label: '学习过程分析', path: '/teacher/analytics', icon: icon.chart },
        { label: '能力与难度估计', path: '/teacher/ability', icon: icon.users },
      ],
    },
    {
      group: '互评治理',
      items: [
        { label: '评审过程管理', path: '/teacher/reviews', icon: icon.users },
        { label: '异常评审检测', path: '/teacher/anomalies', icon: icon.shield, badge: 'openAnomalies' },
        { label: '代码相似度检测', path: '/teacher/similarity', icon: icon.search },
      ],
    },
    {
      group: '算法实验',
      items: [{ label: '算法实验台', path: '/teacher/experiments', icon: icon.spark }],
    },
  ],
};

/* --------------------------------------------------------------- 外壳 */

function sidebar() {
  const role = isTeacher() ? 'teacher' : 'student';
  const groups = NAV[role];
  const nav = h('nav', { class: 'sidebar__nav' });
  groups.forEach((g) => {
    nav.appendChild(h('div', { class: 'sidebar__group-title' }, g.group));
    g.items.forEach((it) => {
      const active = currentPath().startsWith(it.path) && !(it.path === '/problems' && currentPath().startsWith('/teacher'));
      const badgeVal = it.badge ? state[it.badge] : 0;
      nav.appendChild(
        h(
          'a',
          { class: ['nav__item', active ? 'is-active' : ''], href: '#' + it.path },
          h('span', { class: 'nav__icon', html: it.icon }),
          h('span', { class: 'sidebar__label' }, it.label),
          badgeVal ? h('span', { class: 'nav__badge' }, badgeVal > 99 ? '99+' : badgeVal) : null
        )
      );
    });
  });
  const user = state.user || {};
  return h(
    'aside',
    { class: 'sidebar' },
    h(
      'div',
      { class: 'brand' },
      h('div', { class: 'brand__logo' }, 'AL'),
      h('div', { class: 'brand__text' }, h('b', {}, 'AlgorithmLab'), h('span', {}, '算法评审平台'))
    ),
    h(
      'div',
      { class: 'scene' },
      h('span', { html: icon.spark }),
      h('span', {}, '当前场景 '),
      h('b', {}, isTeacher() ? '教学' : '学习')
    ),
    nav,
    h(
      'div',
      { class: 'sidebar__foot' },
      h(
        'div',
        { class: 'sidebar__user' },
        avatar(user, 26),
        h('div', { class: 'sidebar__label' },
          h('div', {}, user.name || '未登录'),
          h('div', { class: 'small' }, (user.class_name || '') + (user.student_no ? ' · ' + user.student_no : '')))
      )
    )
  );
}

function topbar() {
  const crumbs = [];
  const p = currentPath();
  const map = {
    '/student': ['学习动态'],
    '/problems': ['题库与作业'],
    '/problem': ['题库与作业', '题目详情'],
    '/student/submissions': ['学习动态', '我的提交'],
    '/student/reviews': ['学习动态', '互评中心'],
    '/student/subjective': ['学习动态', '我的主观题'],
    '/student/report': ['学习动态', '学习报告'],
    '/teacher': ['教学看板'],
    '/teacher/assignments': ['教学', '作业管理'],
    '/teacher/assignment': ['教学', '作业管理', '作业详情'],
    '/teacher/submissions': ['教学', '提交与评测'],
    '/teacher/analytics': ['学习分析', '学习过程分析'],
    '/teacher/ability': ['学习分析', '能力与难度估计'],
    '/teacher/reviews': ['互评治理', '评审过程管理'],
    '/teacher/anomalies': ['互评治理', '异常评审检测'],
    '/teacher/similarity': ['互评治理', '代码相似度检测'],
    '/teacher/experiments': ['算法实验', '算法实验台'],
  };
  const key = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => p.startsWith(k));
  (map[key] || ['AlgorithmLab']).forEach((c, i, arr) => {
    if (i) crumbs.push(h('span', {}, '/'));
    crumbs.push(i === arr.length - 1 ? h('b', {}, c) : h('span', {}, c));
  });
  const openAnomalies = state.openAnomalies || 0;
  return h(
    'header',
    { class: 'topbar' },
    h('button', { class: 'icon-btn nav-toggle', title: '菜单', onclick: () => document.querySelector('.shell').classList.toggle('nav-open') }, '☰'),
    h('div', { class: 'topbar__crumbs' }, ...crumbs),
    h('div', { class: 'topbar__spacer' }),
    h(
      'button',
      {
        class: 'icon-btn',
        title: '切换主题',
        onclick: () => setTheme(state.theme === 'dark' ? 'light' : 'dark'),
        html: state.theme === 'dark' ? icon.sun : icon.moon,
      }
    ),
    isTeacher() && openAnomalies
      ? h('button', { class: 'icon-btn', title: '待处理异常', onclick: () => router.navigate('/teacher/anomalies') },
          h('span', { html: icon.bell }),
          h('span', { class: 'icon-btn__dot' }, openAnomalies > 9 ? '9+' : openAnomalies))
      : null,
    h(
      'div',
      { class: 'user-chip', onclick: openUserMenu },
      avatar(state.user, 30),
      h(
        'div',
        { class: 'user-chip__meta' },
        h('b', {}, state.user.name),
        h('span', {}, state.user.role === 'student' ? '学生' : state.user.role === 'ta' ? '助教' : '教师')
      ),
      h('span', { class: 'muted', html: icon.down })
    )
  );
}

function openUserMenu(e) {
  e.stopPropagation();
  const menu = h(
    'div',
    {
      class: 'dialog',
      style: {
        position: 'fixed', top: '58px', right: '18px', width: '240px', padding: '10px',
      },
    },
    h('div', { class: 'small muted', style: { padding: '6px 10px' } },
      (state.user.email || state.user.username || '') + ' · ' + (state.user.class_name || '教师')),
    h('button', { class: 'btn btn--ghost btn--block', style: { marginTop: '6px' }, onclick: () => { menu.remove(); router.navigate('/student'); } }, '我的工作台'),
    h('button', { class: 'btn btn--ghost btn--block', style: { marginTop: '6px' }, onclick: () => { menu.remove(); router.navigate('/'); } }, '返回首页'),
    h('button', {
      class: 'btn btn--danger btn--block',
      style: { marginTop: '6px' },
      onclick: async () => {
        menu.remove();
        if (await confirmDialog({ title: '退出登录', message: '确定要退出当前账号吗？', confirmText: '退出' })) {
          try { await api.post('/api/auth/logout'); } catch (err) { /* 忽略网络错误 */ }
          reset();
          router.navigate('/login');
        }
      },
    }, '退出登录')
  );
  document.body.appendChild(menu);
  setTimeout(() => document.addEventListener('click', () => menu.remove(), { once: true }), 0);
}

export function currentPath() {
  return (location.hash.replace(/^#/, '') || '/').split('?')[0];
}

let shellEls = null;

export function renderShell(activePath) {
  const app = document.getElementById('app');
  const scroller = shellEls && shellEls.content;
  const shell = h('div', { class: ['shell', state.sidebarCollapsed ? 'is-collapsed' : ''] });
  const content = h('main', { class: 'content' });
  shell.appendChild(sidebar());
  shell.appendChild(h('div', { class: 'main' }, topbar(), content));
  clear(app).appendChild(shell);
  shellEls = { shell, content };
  return content;
}

/** 页面渲染器：自动插入加载态 -> 渲染 -> 错误兜底 */
export async function withPage(loader, render, { title } = {}) {
  const content = renderShell();
  content.appendChild(loading());
  try {
    const data = await loader();
    clear(content);
    content.appendChild(render(data, content));
    refreshBadges();
  } catch (e) {
    clear(content);
    content.appendChild(
      empty(
        '加载失败',
        e.message || '请稍后重试',
        h('button', { class: 'btn btn--primary', onclick: () => router.resolve() }, '重新加载')
      )
    );
    console.error(e);
  }
}

export async function refreshBadges() {
  try {
    if (!state.token) return;
    const me = await api.get('/api/auth/me');
    state.peerPending = me.peer_pending || 0;
    if (isTeacher()) {
      const an = await api.get('/api/anomalies', { status: 'open' });
      state.openAnomalies = (an.counts && an.counts.open) || 0;
    }
    // 只在徽章数字变化时重绘侧栏，避免打断用户操作
    const nav = document.querySelector('.sidebar__nav');
    if (nav && shellEls) {
      const fresh = sidebar().querySelector('.sidebar__nav');
      nav.replaceWith(fresh);
    }
  } catch (e) {
    /* 徽章失败不影响主流程 */
  }
}

/* --------------------------------------------------------------- 路由 */

function guard(ctx) {
  const isPublic = ['/', '/login'].includes(ctx.path);
  if (!state.token && !isPublic) {
    router.navigate('/login');
    return false;
  }
  if (state.token && isPublic && ctx.path === '/login') {
    router.navigate(isTeacher() ? '/teacher' : '/student');
    return false;
  }
  return true;
}

function registerRoutes() {
  router.register('/', async () => {
    const app = document.getElementById('app');
    clear(app).appendChild(await renderLanding());
  });
  router.register('/login', async () => {
    const app = document.getElementById('app');
    clear(app).appendChild(renderLogin());
  });

  // 路由包装：把 ctx（含 params / query）透传给 loader 与 render，
  // 否则像「按 assignment_id 过滤」这类页面拿不到查询参数。
  const P = (path, loader, render) =>
    router.register(path, (ctx) => withPage(() => loader(ctx), (data, container) => render(data, container, ctx)));

  // 学生端
  P('/student', S.loadDashboard, S.renderDashboard);
  P('/student/submissions', S.loadSubmissions, S.renderSubmissions);
  P('/student/submissions/:id', S.loadSubmissionDetail, S.renderSubmissionDetail);
  P('/student/reviews', S.loadReviews, S.renderReviews);
  P('/student/reviews/:id', S.loadReviewTask, S.renderReviewTask);
  P('/student/subjective', S.loadSubjective, S.renderSubjective);
  P('/student/report', S.loadReport, S.renderReport);

  // 共用
  P('/problems', (ctx) => S.loadProblemList(ctx), (d, c) => S.renderProblemList(d, c, router.currentRoute()));
  P('/problem/:id', (ctx) => Promise.all([S.loadProblem(ctx), api.get('/api/meta')]), (d, c) =>
    renderProblem({ problem: d[0], meta: d[1] }, c)
  );

  // 教师端
  P('/teacher', T.loadTeacherDashboard, T.renderTeacherDashboard);
  P('/teacher/assignments', T.loadAssignments, T.renderAssignments);
  P('/teacher/assignment/:id', T.loadAssignmentDetail, T.renderAssignmentDetail);
  P('/teacher/submissions', T.loadTeacherSubmissions, T.renderTeacherSubmissions);
  P('/teacher/analytics', TI.loadAnalytics, TI.renderAnalytics);
  P('/teacher/ability', TI.loadAbility, TI.renderAbility);
  P('/teacher/reviews', TI.loadReviewAdmin, TI.renderReviewAdmin);
  P('/teacher/anomalies', TI.loadAnomalies, TI.renderAnomalies);
  P('/teacher/similarity', TI.loadSimilarity, TI.renderSimilarity);
  P('/teacher/experiments', TI.loadExperiments, TI.renderExperiments);

  router.setGuard(guard);
  router.setNotFound(() => {
    if (!state.token) {
      router.navigate('/login');
      return;
    }
    const content = renderShell();
    content.appendChild(
      empty('页面不存在', '请检查地址，或从左侧导航重新进入。', h('button', { class: 'btn btn--primary', onclick: () => router.navigate('/') }, '返回首页'))
    );
  });
}

/* --------------------------------------------------------------- 启动 */

async function boot() {
  load();
  document.documentElement.dataset.theme = state.theme || 'light';
  const alive = await api.probeBackend();
  if (!alive) {
    await api.useDemo(true);
    document.body.dataset.demo = '1';
  }
  if (state.token) {
    try {
      const me = await api.get('/api/auth/me');
      state.user = me.user;
      state.courses = me.courses || [];
      state.peerPending = me.peer_pending || 0;
      state.courseId = state.courseId || (state.courses[0] && state.courses[0].id) || null;
      save();
    } catch (e) {
      // 令牌失效（或演示模式下会话未恢复）时统一退回登录页
      reset();
    }
  }
  registerRoutes();
  router.start();
  if (state.demo) {
    setTimeout(
      () => toast('未检测到后端服务，已切换到「内置演示数据」模式（只读），运行 python run.py 可体验完整评测功能', 'warn', 6500),
      600
    );
  }
}

window.addEventListener('error', (e) => {
  console.error(e.error || e.message);
});
window.addEventListener('unhandledrejection', (e) => {
  console.error(e.reason);
});

boot();
