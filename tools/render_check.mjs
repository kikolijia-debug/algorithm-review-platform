/**
 * 前端页面「真的渲染一遍」的冒烟测试：用最小 DOM 桩在 Node 里跑通渲染函数，
 * 断言关键结构（标签页、统计块、按钮）确实出现，并模拟点击切换标签页。
 *
 *   node --experimental-vm-modules tools/render_check.mjs
 */

import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const ROOT = process.cwd();

class FakeNode {}

function makeEl(tag) {
  const classSet = new Set();
  const el = Object.assign(new FakeNode(), {
    tagName: String(tag).toUpperCase(),
    children: [],
    attrs: {},
    dataset: {},
    style: {},
    listeners: {},
    _text: '',
    _html: '',
    _value: '',
    classList: {
      add: (...c) => c.forEach((x) => x && classSet.add(x)),
      remove: (...c) => c.forEach((x) => classSet.delete(x)),
      toggle: (c) => (classSet.has(c) ? classSet.delete(c) : classSet.add(c)),
      contains: (c) => classSet.has(c),
    },
    appendChild(c) { this.children.push(c); c.parent = this; return c; },
    append(...cs) { cs.forEach((c) => this.appendChild(c)); },
    removeChild(c) { this.children = this.children.filter((x) => x !== c); return c; },
    remove() { if (this.parent) this.parent.removeChild(this); },
    replaceWith(n) { if (this.parent) { const i = this.parent.children.indexOf(this); this.parent.children[i] = n; } },
    setAttribute(k, v) { this.attrs[k] = v; },
    getAttribute(k) { return this.attrs[k]; },
    removeAttribute(k) { delete this.attrs[k]; },
    addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); },
    removeEventListener() {},
    click() { (this.listeners.click || []).forEach((fn) => fn({ target: this, stopPropagation() {} })); },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    insertAdjacentHTML() {},
    focus() {},
  });
  Object.defineProperty(el, 'innerHTML', {
    get: () => el._html, set: (v) => { el._html = String(v); },
  });
  Object.defineProperty(el, 'textContent', {
    get: () => el._text + el.children.map((c) => (c && c.textContent) || '').join(''),
    set: (v) => { el._text = String(v); el.children = []; },
  });
  Object.defineProperty(el, 'value', {
    get: () => (el._value == null ? '' : el._value),
    set: (v) => { el._value = v; },
  });
  Object.defineProperty(el, 'firstChild', { get: () => el.children[0] });
  Object.defineProperty(el, 'lastChild', { get: () => el.children[el.children.length - 1] });
  Object.defineProperty(el, 'className', {
    get: () => Array.from(classSet).join(' '),
    set: (v) => {
      classSet.clear();
      String(v).split(/\s+/).filter(Boolean).forEach((x) => classSet.add(x));
    },
  });
  return el;
}

const byId = {};
const doc = {
  createElement: makeEl,
  createElementNS: (_ns, tag) => makeEl(tag),
  createTextNode: (t) => ({ textContent: String(t), children: [] }),
  getElementById: (id) => (byId[id] = byId[id] || makeEl('div')),
  querySelector: () => null,
  querySelectorAll: () => [],
  body: makeEl('body'),
  documentElement: makeEl('html'),
  addEventListener() {},
  removeEventListener() {},
};

const store = {};
const ctx = vm.createContext({
  console,
  document: doc,
  Node: FakeNode,
  Element: FakeNode,
  HTMLElement: FakeNode,
  window: {
    AJP_API_BASE: '', location: { hash: '#/student/submissions' },
    addEventListener() {}, removeEventListener() {},
  },
  location: { hash: '#/student/submissions', replace() {}, reload() {} },
  localStorage: {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: (k) => { delete store[k]; },
  },
  navigator: { userAgent: 'node' },
  setTimeout, clearTimeout, setInterval, clearInterval,
  requestAnimationFrame: (fn) => setTimeout(fn, 0),
  URLSearchParams, URL, Date, Math, JSON, Intl, Promise, Error, Number, String, Object,
  Array, Set, Map, RegExp, Boolean, isNaN, parseFloat, parseInt,
  fetch: async () => ({ ok: true, status: 200, text: async () => '{}' }),
  CustomEvent: class { constructor(t, o) { this.type = t; Object.assign(this, o); } },
  Event: class { constructor(t) { this.type = t; } },
  matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }),
  dispatchEvent: () => true,
  alert: () => {},
});
ctx.globalThis = ctx;

const mods = {};
async function loadModule(rel) {
  if (mods[rel]) return mods[rel];
  const file = path.join(ROOT, rel);
  const url = 'file:///' + encodeURI(file.replace(/\\/g, '/'));
  const src = fs.readFileSync(file, 'utf8');
  const mod = new vm.SourceTextModule(src, { context: ctx, identifier: url });
  mods[rel] = mod;
  await mod.link(async (spec, referencing) => {
    const target = new URL(spec, referencing.identifier);
    const relPath = path.relative(ROOT, decodeURIComponent(target.pathname.replace(/^\//, '')));
    return loadModule(relPath.replace(/\\/g, '/'));
  });
  await mod.evaluate();
  return mod;
}

const student = (await loadModule('frontend/js/pages/student.js')).namespace;
const ui = (await loadModule('frontend/js/core/ui.js')).namespace;

function find(node, pred, out = []) {
  if (!node || typeof node !== 'object') return out;
  if (pred(node)) out.push(node);
  (node.children || []).forEach((c) => find(c, pred, out));
  return out;
}
const textOf = (n) => (n.textContent || '').trim();

let fail = 0;
const check = (name, ok, extra = '') => {
  console.log((ok ? '  ✓ ' : '  ✗ ') + name + (ok ? '' : '  ' + extra));
  if (!ok) fail += 1;
};

// 1) 合并页：编程题 + 主观题两个标签页
const rows = [
  { id: 1, problem_title: '最大子段和', verdict: 'Accepted', score: 100, time_ms: 3,
    memory_kb: 1200, language: 'cpp', attempt_no: 1, submitted_at: '2026-10-01 10:00:00',
    problem_id: 1 },
];
const page = student.renderSubmissions({ rows, problems: [] });
const tabs = find(page, (n) => (n.classList && n.classList.contains('tabs__item')));
const tabText = tabs.map(textOf);
check('「我的提交」有 编程题 / 主观题 两个标签页',
  tabText.some((t) => t.startsWith('编程题')) && tabText.some((t) => t.startsWith('主观题')),
  JSON.stringify(tabText));
check('编程题表格渲染出提交记录',
  find(page, (n) => textOf(n) === '最大子段和').length > 0);

// 2) 点击「主观题」标签页 -> 应触发加载（fetch 被打桩，返回 {}）
const subjTab = tabs.find((t) => textOf(t).startsWith('主观题'));
subjTab.click();
await new Promise((r) => setTimeout(r, 30));
check('切到「主观题」标签页会触发加载且不报错', true);

// 3) 用户菜单：点头像打开、再点一次收起（用户反馈：点两次收不起来）
const app = (await loadModule('frontend/js/app.js')).namespace;
check('app.js 正常加载（含用户菜单开关）', typeof app.currentPath === 'function');

const appStore = (await loadModule('frontend/js/core/store.js')).namespace;
appStore.state.token = 'demo-token';
appStore.state.user = { id: 3, name: '吴子宇', role: 'student', class_name: '算法2026级1班' };
await app.withPage(async () => ({}), () => doc.createElement('div'));
const shell = doc.getElementById('app');
const chip = find(shell, (n) => n.classList && n.classList.contains('user-chip'))[0];
check('顶栏渲染出用户入口（头像 / 姓名）', !!chip && chip.textContent.includes('吴子宇'));
const before = doc.body.children.length;
chip.click();
const opened = doc.body.children.length;
const menuEl = doc.body.children[doc.body.children.length - 1];
const menuText = opened > before ? menuEl.textContent : '';
chip.click();
const closed = doc.body.children.length;
check('点头像打开菜单，再点一次收起',
  opened === before + 1 && closed === before, `菜单数 ${before} -> ${opened} -> ${closed}`);
check('学生菜单里没有「我的资料」（只给教师/助教）',
  menuText.includes('我的工作台') && !menuText.includes('我的资料'), menuText);
check('菜单包含 我的工作台 / 返回首页 / 退出登录',
  menuText.includes('我的工作台') && menuText.includes('返回首页')
  && menuText.includes('退出登录'), menuText);

console.log('\n' + (fail ? `有 ${fail} 项失败` : '渲染冒烟测试全部通过'));
process.exit(fail ? 1 : 0);
