/** 对外页面：产品首页（Landing）与登录页。 */

import { h, clear } from '../core/dom.js';
import { state, save, emit } from '../core/store.js';
import * as api from '../core/api.js';
import * as router from '../core/router.js';
import { ok, fail, toast } from '../core/toast.js';
import { logo } from '../core/ui.js';

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
      logo(38),
      h('div', {}, h('b', {}, '涅槃'), h('span', {}, '算法设计与分析 · 课程评审平台'))
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
      h('div', { class: 'landing__tag' }, h('span', { class: 'type-index' }, 'COURSE /'), '算法设计与分析'),
      h(
        'h1',
        { class: 'landing__title' },
        '课程作业，',
        h('br'),
        h('em', {}, '与同学一起评。')
      ),
      h(
        'p',
        { class: 'landing__sub' },
        '提交代码，查看测试结果；写下解题思路，交换评审意见。作业、课件和学习记录，都在这里。'
      ),
      h(
        'div',
        { class: 'landing__cta' },
        h('a', { class: 'btn btn--lg btn--primary', href: '#/login' }, '进入课程 →'),
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
    h('div', { class: 'landing__eyebrow' }, '课程工具'),
    h('h2', { class: 'landing__h2' }, '作答、互评与复习'),
    h(
      'div',
      { class: 'landing__cards' },
      card('01', '评审任务分配', '最小费用最大流 + 2-opt 局部搜索',
        '按教师设置的评审份数分配任务，避开自评，并尽量均衡每位同学的工作量。'),
      card('02', '评分聚合', '可信度动态加权（EM 迭代）',
        '汇总多位同学的评分，考虑打分习惯的差异。教师可以对照不同方法，查看每一条原始意见。'),
      card('03', '异常评审检测', '残差检验 + 稳健离群 + 关系图',
        '标记偏离较大的评分和异常互评关系，供教师复核。检测结果不直接认定违规。')
    ),
    h(
      'div',
      { class: 'landing__cards', style: { marginTop: '18px' } },
      card('04', '学生能力与题目难度', '1PL/2PL IRT + ELO 增量',
        '从提交记录中查看知识点掌握情况，对照班级平均，安排下一步练习。'),
      card('05', '代码相似度检测', 'Winnowing 指纹 + 倒排索引',
        '比较代码结构，列出相似片段，方便教师结合具体解法逐份查看。'),
      card('06', '复杂度自动判定', '对数空间最小二乘拟合',
        '换一组输入规模，观察运行时间的变化。在实验台中对照复杂度曲线与实测数据。')
    )
  );

  const foot = h(
    'footer',
    { class: 'landing__foot' },
    h('span', {}, '涅槃 · 算法设计与分析课程评审平台'),
    h('span', {}, '课程作业 · 代码评测 · 同伴互评')
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
    h('div', { class: 'idx' }, h('span', { class: 'type-index' }, idx), h('span', { class: 'landing__tech' }, tech)),
    h('h3', {}, title),
    h('p', {}, desc)
  );
}

/* ------------------------------------------------------------- 登录 */

const ROLES = [
  { key: 'student', title: '学生', sub: '作业与互评', icon: '✦' },
  { key: 'teacher', title: '教师', sub: '课程与评审管理', icon: '◈' },
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
      h('h2', {}, '登录课程'),
      h('p', { class: 'sub' }, '选择身份，输入账号和密码。'),
      roleGrid,
      h('div', { class: 'col', style: { gap: '14px' } },
        h('label', { class: 'field' }, h('span', { class: 'field__label' }, '账号 / 邮箱'), email),
        h('label', { class: 'field' }, h('span', { class: 'field__label' }, '密码'), pwd)
      ),
      errBox,
      h('div', { class: 'mt16' }, submit),
      h('div', { class: 'mt12', style: { textAlign: 'center' } },
        h('button', {
          class: 'btn btn--ghost btn--sm',
          onclick: () => router.navigate('/register'),
        }, '没有账号？去注册')),
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
      logo(38),
      h('div', {}, h('b', { style: { color: '#eafaf3' } }, '涅槃'), h('span', { style: { color: '#6d8b80', fontSize: '11px', letterSpacing: '.1em' } }, '算法评审平台'))
    ),
    h(
      'h1',
      { class: 'login__title' },
      '算法设计与分析',
      h('br'),
      h('em', {}, '课程工作台')
    ),
    h(
      'p',
      { class: 'login__sub' },
      '做作业、看课件，也看看同学的另一种解法。'
    ),
    h(
      'div',
      { class: 'login__steps' },
      h('div', { class: 'login__step' }, h('i', {}, '01'), h('b', {}, '作答'), h('span', {}, '提交代码与思路')),
      h('div', { class: 'login__step' }, h('i', {}, '02'), h('b', {}, '互评'), h('span', {}, '交流解法与建议')),
      h('div', { class: 'login__step' }, h('i', {}, '03'), h('b', {}, '回看'), h('span', {}, '查看成绩与反馈'))
    )
  );

  return h('div', { class: 'login' }, left, right);
}

function applySession(r) {
  state.token = r.token;
  state.user = r.user;
  if (r.course_id) state.courseId = r.course_id;
  save();
  emit();
}

/* --------------------------------------------------------- 注册 */

/**
 * 注册页：教师注册后自动获得一门自己的课程；学生填邀请码直接进班，
 * 不填邀请码则先进入「未加入课程」状态，登录后可以在学习动态里加入。
 */
export function renderRegister() {
  let role = 'student';
  const name = h('input', { class: 'input', placeholder: '真实姓名' });
  const username = h('input', { class: 'input', placeholder: '登录账号，至少 3 位' });
  const pwd = h('input', { class: 'input', type: 'password', placeholder: '密码，至少 6 位' });
  const email = h('input', { class: 'input', placeholder: '选填' });
  const extra = h('div');
  const errBox = h('div', { class: 'note note--danger', style: { display: 'none' } });

  const courseName = h('input', { class: 'input', value: '算法设计与分析' });
  const inviteCode = h('input', { class: 'input', placeholder: '老师给的课程 / 班级邀请码' });
  const studentNo = h('input', { class: 'input', placeholder: '选填' });

  const paintExtra = () => {
    clear(extra);
    if (role === 'student') {
      extra.appendChild(h('div', { class: 'col', style: { gap: '14px' } },
        h('label', { class: 'field' }, h('span', { class: 'field__label' }, '邀请码（选填）'), inviteCode),
        h('p', { class: 'small muted', style: { marginTop: '-4px' } },
          '填了邀请码会直接加入对应课程/班级；暂时没有可以先注册，登录后用邀请码加入。'),
        h('label', { class: 'field' }, h('span', { class: 'field__label' }, '学号（选填）'), studentNo)));
    } else {
      extra.appendChild(h('div', { class: 'col', style: { gap: '14px' } },
        h('label', { class: 'field' }, h('span', { class: 'field__label' }, '我的课程名称'), courseName),
        h('p', { class: 'small muted', style: { marginTop: '-4px' } },
          '注册后会为你创建这门课程并生成邀请码，学生凭邀请码加入。')));
    }
  };

  const roleGrid = h('div', { class: 'role-grid' },
    ...[
      { key: 'student', title: '学生', sub: '加入课程 · 提交与互评', icon: '✦' },
      { key: 'teacher', title: '教师', sub: '开课与布置作业', icon: '◈' },
    ].map((r) => h('button', {
      type: 'button',
      class: ['role-tile', role === r.key ? 'is-active' : ''],
      onclick: () => {
        role = r.key;
        Array.from(roleGrid.children).forEach((c) => c.classList.remove('is-active'));
        roleGrid.children[r.key === 'student' ? 0 : 1].classList.add('is-active');
        errBox.style.display = 'none';
        paintExtra();
      },
    }, h('b', {}, r.icon + ' ' + r.title), h('span', {}, r.sub))));
  paintExtra();

  const submit = h('button', { class: 'btn btn--primary btn--block' }, '注册并进入工作台');
  submit.onclick = async () => {
    const body = {
      role, name: name.value.trim(), username: username.value.trim(),
      password: pwd.value, email: email.value.trim() || null,
      invite_code: role === 'student' ? inviteCode.value.trim() : '',
      course_name: role === 'student' ? '' : courseName.value.trim(),
      student_no: role === 'student' ? studentNo.value.trim() : null,
    };
    if (!body.name || !body.username || !body.password) {
      errBox.textContent = '请填写姓名、账号与密码';
      errBox.style.display = '';
      return;
    }
    submit.disabled = true;
    submit.textContent = '正在创建账号…';
    try {
      const r = await api.post('/api/auth/register', body);
      applySession(r);
      if (r.need_course) {
        toast('账号已创建。请用老师给的邀请码加入课程。', 'warn', 6000);
      } else {
        ok('注册成功，欢迎 ' + r.user.name);
      }
      router.navigate(r.user.role === 'student' ? '/student' : '/teacher');
    } catch (e) {
      errBox.textContent = e.message;
      errBox.style.display = '';
    } finally {
      submit.disabled = false;
      submit.textContent = '注册并进入工作台';
    }
  };

  const right = h(
    'div',
    { class: 'login__right' },
    h(
      'div',
      { class: 'login__card' },
      h('div', { class: 'small', style: { color: 'var(--brand)', letterSpacing: '.14em' } }, '创建账号'),
      h('h2', {}, '注册涅槃'),
      h('p', { class: 'sub' }, '教师注册后自动创建自己的课程，学生凭邀请码加入班级'),
      roleGrid,
      h('div', { class: 'col', style: { gap: '14px' } },
        h('label', { class: 'field' }, h('span', { class: 'field__label' }, '姓名'), name),
        h('label', { class: 'field' }, h('span', { class: 'field__label' }, '登录账号'), username),
        h('label', { class: 'field' }, h('span', { class: 'field__label' }, '密码'), pwd),
        h('label', { class: 'field' }, h('span', { class: 'field__label' }, '邮箱（选填）'), email)),
      extra,
      errBox,
      h('div', { class: 'mt16' }, submit),
      h('div', { class: 'mt12' },
        h('button', {
          class: 'btn btn--ghost btn--block',
          onclick: () => router.navigate('/login'),
        }, '已有账号？返回登录'))
    )
  );

  const left = h(
    'div',
    { class: 'login__left' },
    h('div', { class: 'login__brand' },
      logo(38),
      h('div', {}, h('b', { style: { color: '#eafaf3' } }, '涅槃'),
        h('span', { style: { color: '#6d8b80', fontSize: '11px', letterSpacing: '.1em' } }, '算法评审平台'))),
    h('h1', { class: 'login__title' }, '把自己的班级', h('br'), h('em', {}, '搬进平台'), '，马上开课。'),
    h('p', { class: 'login__sub' },
      '教师：建课程 → 建班级 → 导入名单 → 出题布置作业；学生：凭邀请码加入 → 提交 → 互评。'),
    h('div', { class: 'login__steps' },
      h('div', { class: 'login__step' }, h('i', {}, '01'), h('b', {}, '建课'), h('span', {}, '自动生成邀请码')),
      h('div', { class: 'login__step' }, h('i', {}, '02'), h('b', {}, '导入'), h('span', {}, '批量建学生账号')),
      h('div', { class: 'login__step' }, h('i', {}, '03'), h('b', {}, '开课'), h('span', {}, '作业与互评')))
  );

  return h('div', { class: 'login' }, left, right);
}
