/** 对外页面：产品首页（Landing）与登录页。 */

import { h, clear } from '../core/dom.js';
import { state, save, emit } from '../core/store.js';
import * as api from '../core/api.js';
import * as router from '../core/router.js';
import { ok, fail } from '../core/toast.js';

/* ------------------------------------------------------------- 首页 */

export async function renderLanding() {
  let stats = { students: 48, problems: 29, submissions: 678, reviews: 300 };
  try {
    const real = await api.get('/api/stats/public');
    if (real) {
      stats = {
        students: real.students || stats.students,
        problems: real.problems || stats.problems,
        submissions: real.submissions || 0,
        reviews: real.reviews || 0,
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
        '《算法设计与分析》课程评审平台。编程题自动编译评测，主观题匿名互评，'
          + '分配、聚合与异常检测都由算法完成，并配有可复现的对比实验。'
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
      tile(stats.students, '名学生'),
      tile(stats.problems, '道题目'),
      tile(stats.submissions + '+', '次评测'),
      tile(stats.reviews + '+', '份互评')
    )
  );

  const pillars = h(
    'section',
    { class: 'landing__section' },
    h('div', { class: 'landing__eyebrow' }, 'CORE ALGORITHMS'),
    h('h2', { class: 'landing__h2' }, '六个核心算法，都拿实验数据说话。'),
    h(
      'div',
      { class: 'landing__cards' },
      card('01', '评审任务分配', '最小费用最大流 + 2-opt 局部搜索',
        '「每人评 k 份、工作量上限 c、禁止自评」建成流网络，用平行凸费用弧做负载均衡，'
        + '再局部搜索消除互为评审。60 人班级约 0.5 s，负载基尼系数为 0。'),
      card('02', '评分聚合', '可信度动态加权（EM 迭代）',
        '交替估计作业真实分 sⱼ、评审者偏差 bᵢ 与可信度 wᵢ，'
        + '用收缩抑制小样本过拟合。注入恶意评审的实验中 RMSE 比算术平均低 53.8%。'),
      card('03', '异常评审检测', '残差检验 + 稳健离群 + 关系图',
        '残差 z 检验、偏差显著性检验、MAD 时长检测，'
        + '再用关系图的互惠边与社区发现识别固定互评。查全率 0.93，查准率 0.80。')
    ),
    h(
      'div',
      { class: 'landing__cards', style: { marginTop: '18px' } },
      card('04', '学生能力与题目难度', '1PL/2PL IRT + ELO 增量',
        '1PL Rasch 联合估计能力 θ 与难度 b，与 ELO 对照。'
        + '本课程规模下 1PL 的 θ 与真值相关系数 0.87，优于放开区分度的 2PL（0.81）。'),
      card('05', '代码相似度检测', 'Winnowing 指纹 + 倒排索引',
        'token 规范化 → 滚动哈希 → 窗口最小哈希指纹 → 倒排索引 → 并查集聚类。'
        + '60 份代码 9 ms，变量改名、加注释仍能命中。'),
      card('06', '复杂度自动判定', '对数空间最小二乘拟合',
        '多规模实测耗时，在对数空间拟合 {1, log n, n, n log n, n², n³, 2ⁿ}，'
        + '并给出倍增比与经验指数。实测：双重循环→O(n²)，归并→O(n log n)。')
    )
  );

  const foot = h(
    'footer',
    { class: 'landing__foot' },
    h('span', {}, 'AlgorithmLab · 算法设计与分析课程评审平台'),
    h('span', {}, 'python run.py 即可本地运行')
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
      '把每一次',
      h('br'),
      h('em', {}, '算法设计与分析'),
      '，变成可验证的结果。'
    ),
    h(
      'p',
      { class: 'login__sub' },
      '编程题自动评测，主观题匿名互评。分配、聚合、异常检测都由算法完成。'
    ),
    h(
      'div',
      { class: 'login__steps' },
      h('div', { class: 'login__step' }, h('i', {}, '01'), h('b', {}, '提交'), h('span', {}, '自动评测')),
      h('div', { class: 'login__step' }, h('i', {}, '02'), h('b', {}, '互评'), h('span', {}, '匿名分配')),
      h('div', { class: 'login__step' }, h('i', {}, '03'), h('b', {}, '结果'), h('span', {}, '动态加权'))
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
