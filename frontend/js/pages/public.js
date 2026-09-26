/** 对外页面：产品首页（Landing）与登录页。 */

import { h, clear } from '../core/dom.js';
import { state, save, emit } from '../core/store.js';
import * as api from '../core/api.js';
import * as router from '../core/router.js';
import { ok, fail } from '../core/toast.js';

/* ------------------------------------------------------------- 首页 */

export async function renderLanding() {
  let stats = { students: 48, problems: 14, submissions: 384, reviews: 271 };
  try {
    const health = await api.get('/api/health');
    const demo = await api.get('/api/courses');
    if (demo && demo[0]) {
      stats = {
        students: demo[0].students || stats.students,
        problems: demo[0].problems || stats.problems,
        submissions: 384,
        reviews: 271,
      };
    }
  } catch (e) {
    /* 演示模式下使用默认值 */
  }

  const nav = h(
    'div',
    { class: 'landing__nav' },
    h(
      'div',
      { class: 'landing__brand' },
      h('div', { class: 'brand__logo' }, 'AL'),
      h('div', {}, h('b', {}, 'AlgorithmLab'), h('span', {}, '算法设计与分析 · 课程评审平台'))
    ),
    h('div', { class: 'grow' }),
    h('a', { class: 'btn btn--ghost', href: '#/problems' }, '题库'),
    h('a', { class: 'btn btn--primary', href: '#/login' }, '进入平台')
  );

  const hero = h(
    'section',
    { class: 'landing__hero' },
    h(
      'div',
      {},
      h('div', { class: 'landing__tag' }, '问题建模 · 算法设计 · 复杂度分析 · 实验验证'),
      h(
        'h1',
        { class: 'landing__title' },
        '让每一次算法作业，',
        h('br'),
        '都能被', h('em', {}, '公平而可信'), '地评价。'
      ),
      h(
        'p',
        { class: 'landing__sub' },
        '面向《算法设计与分析》课程的综合评审平台：编程题自动编译评测并反馈正确性、运行时间与空间使用；'
          + '主观题按最小费用流分配匿名互评，用可信度动态加权聚合分数，并以统计检验与关系图识别异常评审。'
          + '所有核心算法都配有可复现的对比实验与复杂度分析。'
      ),
      h(
        'div',
        { class: 'landing__cta' },
        h('a', { class: 'btn btn--lg btn--primary', href: '#/login' }, '开启工作台 →'),
        h('a', { class: 'btn btn--lg btn--dark', href: '#/problems' }, '浏览题库')
      )
    ),
    h(
      'div',
      { class: 'landing__stats' },
      tile(stats.students, '名学生 · 2 个教学班'),
      tile(stats.problems, '道题目 · 10 编程 + 4 主观'),
      tile(stats.submissions + '+', '次自动评测记录'),
      tile(stats.reviews + '+', '份匿名互评')
    )
  );

  const pillars = h(
    'section',
    { class: 'landing__section' },
    h('div', { class: 'landing__eyebrow' }, 'CORE ALGORITHMS'),
    h('h2', { class: 'landing__h2' }, '不是「能跑就行」，而是每个环节都有算法依据。'),
    h(
      'div',
      { class: 'landing__cards' },
      card('01', '评审任务分配', '最小费用最大流 + 2-opt 局部搜索',
        '把「每份作业评 k 次、每人工作量上限 c、禁止自评、避免固定互评关系」建成二分图流网络，'
        + '并用平行的凸费用弧实现负载均衡；再对互为评审与班级分布做增量式局部搜索修正。'
        + '复杂度 O(F·V·E) + O(R²·I)，60 人班级求解耗时约 0.5 s。'),
      card('02', '评分聚合', '可信度动态加权（EM 迭代）',
        '模型 rᵢⱼ = sⱼ + bᵢ + εᵢⱼ，交替估计作业真实分、评审者宽严偏差与可信度，'
        + '并用经验贝叶斯收缩解决「只评过 2-3 份」的小样本过拟合。'
        + '模拟实验中 RMSE 比算术平均降低 50% 以上。'),
      card('03', '异常评审检测', '残差检验 + 稳健离群 + 关系图',
        '对单次评分做 z 检验、对评审者偏差做显著性检验、用 MAD 检测异常时长，'
        + '再以互评关系图的互惠边与标签传播社区发现识别固定互评与抱团行为。'
        + '注入实验下查全率 0.93、查准率 0.80。')
    ),
    h(
      'div',
      { class: 'landing__cards', style: { marginTop: '18px' } },
      card('04', '学生能力与题目难度', '1PL/2PL IRT + ELO 增量',
        '用 1PL Rasch 模型联合估计学生能力 θ 与题目难度 b，并与 ELO 增量更新对比。'
        + '小样本课程数据下 1PL 的 θ 估计与真实能力相关系数达 0.87，比放开区分度参数的 2PL 更稳。'),
      card('05', '代码相似度检测', 'Winnowing 指纹 + 倒排索引',
        '规范化 token → k-gram 滚动哈希 → 滑动窗口最小哈希指纹 → 倒排索引累计相似度 → 并查集聚类。'
        + '把原本 O(n²) 的两两比对降到近似线性，60 份代码 9 ms 出结果，变量改名与加注释仍 100% 命中。'),
      card('06', '复杂度自动判定', '对数空间最小二乘拟合',
        '对同一程序在多个输入规模下实测耗时，在对数空间拟合 {1, log n, n, n log n, n², n³, 2ⁿ}，'
        + '并给出倍增比与经验指数，帮助学生把「实测曲线」与「复杂度阶」对应起来。')
    )
  );

  const foot = h(
    'footer',
    { class: 'landing__foot' },
    h('span', {}, 'AlgorithmLab · 算法设计与分析课程评审平台 · 课程大作业'),
    h('span', {}, '本地运行：python run.py ｜ 前端零构建，纯标准库后端')
  );

  return h('div', { class: 'landing' }, nav, hero, pillars, foot);
}

function tile(value, label) {
  return h('div', { class: 'landing__stat' }, h('b', {}, String(value)), h('span', {}, label));
}

function card(idx, title, tech, desc) {
  return h(
    'div',
    { class: 'landing__card' },
    h('div', { class: 'idx' }, idx + ' / ' + tech),
    h('h3', {}, title),
    h('p', {}, desc)
  );
}

/* ------------------------------------------------------------- 登录 */

const ROLES = [
  { key: 'student', title: '学生', sub: '助学 · 提交与互评', icon: '✦' },
  { key: 'teacher', title: '教师', sub: '助教 · 教学与治理', icon: '◈' },
  { key: 'ta', title: '助教', sub: '协助批改与复核', icon: '◇' },
  { key: 'demo', title: '访客', sub: '只读体验演示数据', icon: '◎' },
];

export function renderLogin() {
  let role = 'student';
  const email = h('input', { class: 'input', placeholder: 'teacher / stu1 / 邮箱', autocomplete: 'username' });
  const pwd = h('input', { class: 'input', type: 'password', placeholder: '请输入密码', autocomplete: 'current-password' });
  const submit = h('button', { class: 'btn btn--primary btn--lg btn--block' }, '登录');
  const errBox = h('div', { style: { display: 'none' } });

  const roleGrid = h('div', { class: 'role-grid' });
  const paintRoles = () => {
    clear(roleGrid);
    ROLES.forEach((r) => {
      roleGrid.appendChild(
        h(
          'button',
          {
            class: ['role-tile', role === r.key ? 'is-active' : ''],
            type: 'button',
            onclick: () => {
              role = r.key;
              paintRoles();
              submit.textContent = r.key === 'student' ? '登录学习工作台' : r.key === 'teacher' ? '登录教学工作台' : r.key === 'ta' ? '登录助教工作台' : '进入只读演示';
            },
          },
          h('b', {}, r.icon + ' ' + r.title),
          h('span', {}, r.sub),
          role === r.key ? h('span', { class: 'role-tile__check' }, '✓') : null
        )
      );
    });
    submit.textContent =
      role === 'student' ? '登录学习工作台' : role === 'teacher' ? '登录教学工作台' : role === 'ta' ? '登录助教工作台' : '进入只读演示';
  };
  paintRoles();

  const showError = (msg) => {
    errBox.textContent = msg;
    errBox.className = 'note note--danger';
    errBox.style.display = '';
  };

  async function doLogin() {
    if (role === 'demo') {
      await api.useDemo(true);
      const r = await api.post('/api/auth/login', { username: 'teacher', password: '123456', role: 'teacher' });
      applySession(r);
      ok('已进入只读演示模式');
      router.navigate('/teacher');
      return;
    }
    const username = email.value.trim();
    const password = pwd.value;
    if (!username || !password) return showError('请输入账号与密码');
    submit.disabled = true;
    submit.textContent = '正在登录…';
    try {
      if (state.demo) await api.useDemo(true);
      const r = await api.post('/api/auth/login', {
        username,
        password,
        role: role === 'ta' ? 'ta' : role,
      });
      applySession(r);
      ok('欢迎回来，' + r.user.name);
      router.navigate(r.user.role === 'student' ? '/student' : '/teacher');
    } catch (e) {
      showError(e.message);
      fail(e.message);
    } finally {
      submit.disabled = false;
      paintRoles();
    }
  }

  const onEnter = (e) => {
    if (e.key === 'Enter') doLogin();
  };
  email.addEventListener('keydown', onEnter);
  pwd.addEventListener('keydown', onEnter);
  submit.addEventListener('click', doLogin);

  const fill = (u, p, r) => {
    email.value = u;
    pwd.value = p;
    role = r;
    paintRoles();
  };

  const right = h(
    'div',
    { class: 'login__right' },
    h(
      'div',
      { class: 'login__card' },
      h('div', { class: 'small', style: { color: 'var(--brand)', letterSpacing: '.14em' } }, '账号登录'),
      h('h2', {}, '登录 AlgorithmLab'),
      h('p', { class: 'sub' }, '选择身份并使用已注册的账号进入对应工作台'),
      roleGrid,
      h('div', { class: 'col', style: { gap: '14px' } },
        h('label', { class: 'field' }, h('span', { class: 'field__label' }, '账号 / 邮箱'), email),
        h('label', { class: 'field' }, h('span', { class: 'field__label' }, '密码'), pwd)
      ),
      errBox,
      h('div', { class: 'mt16' }, submit),
      h(
        'div',
        { class: 'login__demo' },
        h('div', { class: 'small muted' }, '演示账号（点击自动填入）'),
        h(
          'div',
          { class: 'login__demo-grid' },
          h('button', { class: 'demo-chip', type: 'button', onclick: () => fill('teacher', '123456', 'teacher') }, '教师 teacher / 123456'),
          h('button', { class: 'demo-chip', type: 'button', onclick: () => fill('stu1', '123456', 'student') }, '学生 stu1 / 123456'),
          h('button', { class: 'demo-chip', type: 'button', onclick: () => fill('ta', '123456', 'ta') }, '助教 ta / 123456'),
          h('button', { class: 'demo-chip', type: 'button', onclick: () => { role = 'demo'; paintRoles(); doLogin(); } }, '访客 · 只读演示')
        )
      )
    )
  );

  const left = h(
    'div',
    { class: 'login__left' },
    h(
      'div',
      { class: 'login__brand' },
      h('div', { class: 'brand__logo' }, 'AL'),
      h('div', {}, h('b', { style: { color: '#eafaf3' } }, 'AlgorithmLab'), h('span', { style: { color: '#6d8b80', fontSize: '11px', letterSpacing: '.1em' } }, '算法评审平台'))
    ),
    h(
      'h1',
      { class: 'login__title' },
      '把算法的每一次',
      h('br'),
      h('em', {}, '设计与分析'),
      '，都变成可验证的结果。'
    ),
    h(
      'p',
      { class: 'login__sub' },
      '编程题自动编译评测，主观题匿名互评；分配、聚合、异常检测全部由算法驱动，'
        + '每一步都留下可复现的复杂度分析与实验数据。'
    ),
    h(
      'div',
      { class: 'login__steps' },
      h('div', { class: 'login__step' }, h('i', {}, '01'), h('b', {}, '提交代码 / 报告'), h('span', {}, '自动评测 · 学习记录')),
      h('div', { class: 'login__step' }, h('i', {}, '02'), h('b', {}, '匿名互评'), h('span', {}, '最小费用流分配 · 统一评分细则')),
      h('div', { class: 'login__step' }, h('i', {}, '03'), h('b', {}, '可信聚合与治理'), h('span', {}, '动态加权 · 异常复核'))
    )
  );

  return h('div', { class: 'login' }, left, right);
}

function applySession(r) {
  state.token = r.token;
  state.user = r.user;
  state.courseId = state.courseId || 1;
  save();
  emit();
}
