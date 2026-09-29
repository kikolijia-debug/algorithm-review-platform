/**
 * 极简 DOM 构建工具（hyperscript 风格）。
 *
 * 不引入任何框架，用 40 行代码换来与 React 接近的开发体验：
 *   h('div', { class: 'card' }, h('h3', {}, '标题'), '正文')
 */

export function h(tag, props, ...children) {
  const el = document.createElement(tag);
  apply(el, props);
  append(el, children);
  return el;
}

export function frag(...children) {
  const f = document.createDocumentFragment();
  append(f, children);
  return f;
}

export function text(value) {
  return document.createTextNode(value == null ? '' : String(value));
}

export function apply(el, props) {
  if (!props) return el;
  for (const [key, value] of Object.entries(props)) {
    if (value == null || value === false) continue;
    if (key === 'class' || key === 'className') {
      if (Array.isArray(value)) el.className = value.filter(Boolean).join(' ');
      else el.className = String(value);
    } else if (key === 'style' && typeof value === 'object') {
      for (const [k, v] of Object.entries(value)) {
        if (v == null) continue;
        if (k.startsWith('--')) el.style.setProperty(k, String(v));
        else el.style[k] = typeof v === 'number' ? v + 'px' : String(v);
      }
    } else if (key === 'html') {
      el.innerHTML = String(value);
    } else if (key === 'text') {
      el.textContent = String(value);
    } else if (key === 'dataset' && typeof value === 'object') {
      Object.assign(el.dataset, value);
    } else if (key.startsWith('on') && typeof value === 'function') {
      el.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key === 'ref' && typeof value === 'function') {
      value(el);
    } else if (key === 'value' && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT')) {
      el.value = value;
    } else if (key === 'checked' || key === 'disabled' || key === 'selected' || key === 'multiple') {
      el[key] = Boolean(value);
    } else {
      el.setAttribute(key, String(value));
    }
  }
  return el;
}

export function append(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    el.appendChild(child instanceof Node ? child : text(child));
  }
  return el;
}

export function clear(el) {
  while (el.firstChild) el.removeChild(el.firstChild);
  return el;
}

export function qs(sel, root = document) {
  return root.querySelector(sel);
}

export function qsa(sel, root = document) {
  return Array.from(root.querySelectorAll(sel));
}

export function on(el, event, handler, opts) {
  el.addEventListener(event, handler, opts);
  return () => el.removeEventListener(event, handler, opts);
}

/** 转义 HTML，避免 XSS（所有用户输入渲染到 innerHTML 前必须过这里） */
export function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * 题面里的一点点行内格式：支持 ``**重点**`` 加粗。
 * 先转义再替换，保证注入不进来（题库里很多题面都用了这种写法）。
 */
export function inlineMd(s) {
  return esc(s).replace(/\*\*([^*\n]+)\*\*/g, '<b>$1</b>');
}
