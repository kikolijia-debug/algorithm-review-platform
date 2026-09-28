/** 基于 hash 的前端路由（静态托管、GitHub Pages 均可直接使用）。 */

const routes = [];
let notFound = null;
let beforeEach = null;
let current = null;
//: 浏览轨迹：用于「← 返回上一页」，比按层级猜更符合老师的使用直觉
let trail = [];
let lastPath = null;

export function register(pattern, handler, meta = {}) {
  const names = [];
  const rx = new RegExp(
    '^' +
      pattern
        .split('/')
        .map((seg) => {
          if (seg.startsWith(':')) {
            names.push(seg.slice(1));
            return '([^/]+)';
          }
          if (seg === '*') {
            names.push('rest');
            return '(.*)';
          }
          return seg.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        })
        .join('/') +
      '$'
  );
  routes.push({ pattern, rx, names, handler, meta });
}

export function setNotFound(fn) {
  notFound = fn;
}

export function setGuard(fn) {
  beforeEach = fn;
}

export function currentRoute() {
  return current;
}

export function navigate(path, { replace = false } = {}) {
  const target = '#' + path;
  if (location.hash === target) {
    resolve();
    return;
  }
  if (replace) location.replace(target);
  else location.hash = target;
}

function remember(p) {
  if (lastPath && lastPath !== p) {
    trail.push(lastPath);
    if (trail.length > 40) trail.shift();
  }
  lastPath = p;
}

export function path() {
  const raw = location.hash.replace(/^#/, '');
  return raw || '/';
}

export function resolve() {
  const [p, queryStr] = path().split('?');
  const query = Object.fromEntries(new URLSearchParams(queryStr || ''));
  for (const r of routes) {
    const m = r.rx.exec(p);
    if (m) {
      const params = {};
      r.names.forEach((n, i) => (params[n] = decodeURIComponent(m[i + 1])));
      const ctx = { path: p, params, query, meta: r.meta, render: r.handler };
      if (beforeEach && beforeEach(ctx) === false) return;
      current = ctx;
      remember(p);
      r.handler(ctx);
      window.scrollTo({ top: 0 });
      return;
    }
  }
  if (notFound) notFound({ path: p, query });
}

export function start() {
  window.addEventListener('hashchange', resolve);
  resolve();
}

/** 上一个访问过的页面（跳过与当前页相同的项）；没有轨迹时返回 fallback。 */
export function previousPath(fallback = null) {
  const now = path().split('?')[0];
  for (let i = trail.length - 1; i >= 0; i--) {
    if (trail[i] !== now) return trail[i];
  }
  return fallback;
}

/** 回到上一个访问过的页面（找不到轨迹时退到 fallback）。 */
export function back(fallback = null) {
  const target = previousPath(fallback);
  if (!target) return false;
  navigate(target, { replace: true });
  return true;
}
