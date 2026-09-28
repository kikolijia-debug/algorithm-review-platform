/** 统一的后端调用封装。演示模式下自动改走内置数据引擎。 */

import { state } from './store.js';

const BASE = window.AJP_API_BASE || '';
let demoApi = null;

export async function useDemo(demo) {
  if (demo && !demoApi) {
    demoApi = await import('../demo/demo-api.js');
  }
  state.demo = demo;
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function qs(params) {
  if (!params) return '';
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue;
    usp.append(k, v);
  }
  const s = usp.toString();
  return s ? '?' + s : '';
}

export async function api(path, { method = 'GET', body, query } = {}) {
  if (state.demo) {
    return demoApi.request(path, { method, body, query });
  }
  const headers = { 'Content-Type': 'application/json' };
  if (state.token) headers.Authorization = 'Bearer ' + state.token;
  let res;
  try {
    res = await fetch(BASE + path + qs(query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (e) {
    throw new ApiError('无法连接后端服务，请确认已运行 python run.py', 0);
  }
  let payload = null;
  const txt = await res.text();
  try {
    payload = txt ? JSON.parse(txt) : {};
  } catch (e) {
    throw new ApiError('服务返回了非法数据', res.status);
  }
  if (!res.ok || payload.ok === false) {
    throw new ApiError(payload.error || '请求失败（' + res.status + '）', res.status);
  }
  return payload.data !== undefined ? payload.data : payload;
}

export const get = (path, query) => api(path, { query });
export const post = (path, body) => api(path, { method: 'POST', body });
export const put = (path, body) => api(path, { method: 'PUT', body });
export const del = (path) => api(path, { method: 'DELETE' });

/**
 * 静态资源的可访问地址。
 *
 * 后端返回的是站根路径（例如 `/courseware/ch05.pdf`），但站点可能部署在子路径下
 * （GitHub Pages 的 `/algorithm-review-platform/`），这里统一补上前缀。
 */
export function assetUrl(path) {
  if (!path) return path;
  if (/^https?:\/\//i.test(path)) return path;
  const base = BASE || '';
  return base + '/' + String(path).replace(/^\//, '');
}

/** 探测后端是否可用，用于决定是否进入演示模式 */
export async function probeBackend() {
  if (window.__AJP_DEMO__) return false;
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 2500);
    const r = await fetch(BASE + '/api/health', { signal: ctrl.signal });
    clearTimeout(timer);
    return r.ok;
  } catch (e) {
    return false;
  }
}
