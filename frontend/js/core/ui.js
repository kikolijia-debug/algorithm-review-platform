/**
 * 组件库：卡片、统计块、表格、徽章、按钮、标签页、弹窗、抽屉、提示等。
 * 全部为纯函数返回 DOM 节点，风格由 css/app.css 中的设计令牌统一控制。
 */

import { h, esc, clear } from './dom.js';

/* ------------------------------------------------------------------ 基础 */

/**
 * 平台标识「涅槃」：一只向上展翼的凤凰（原创几何图形，非赛事官方 logo）。
 * 直接内联 SVG，缩放不糊，也方便在深浅两种底色上使用。
 * 每次调用生成一组唯一的渐变 id，避免同一页多个标识互相抢 id。
 */
let logoSeq = 0;

/** 生成标识的 SVG 源码；prefix 用于隔离渐变 id */
export function logoSvg(prefix = 'nv') {
  return `<svg viewBox="0 0 48 48" width="100%" height="100%" role="img" aria-label="涅槃 Nirvana">
  <defs>
    <linearGradient id="${prefix}-badge" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0b3a2d"/><stop offset=".55" stop-color="#12684c"/><stop offset="1" stop-color="#1eb27c"/>
    </linearGradient>
    <linearGradient id="${prefix}-feather" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffffff"/><stop offset=".55" stop-color="#dffbee"/><stop offset="1" stop-color="#9ff0cd"/>
    </linearGradient>
    <linearGradient id="${prefix}-ember" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffe6b0"/><stop offset="1" stop-color="#dc9c33"/>
    </linearGradient>
  </defs>
  <rect width="48" height="48" rx="13" fill="url(#${prefix}-badge)"/>
  <rect x=".6" y=".6" width="46.8" height="46.8" rx="12.6" fill="none" stroke="#fff" stroke-opacity=".15" stroke-width="1.2"/>
  <g fill="url(#${prefix}-feather)">
    <path d="M22.6 27.8L3.4 5.4l3.0 12.2 2.0 8.2z"/>
    <path d="M22.6 27.8L12.2 8.4l1.4 10.4 1.0 6.6z"/>
    <path d="M25.4 27.8L44.6 5.4l-3.0 12.2-2.0 8.2z"/>
    <path d="M25.4 27.8L35.8 8.4l-1.4 10.4-1.0 6.6z"/>
    <path d="M24 12.2c2.6 5.6 3.9 10.5 3.9 14.7 0 5.2-1.3 9.8-3.9 13.9-2.6-4.1-3.9-8.7-3.9-13.9 0-4.2 1.3-9.1 3.9-14.7z"/>
  </g>
  <path d="M24 4.6l1.8 4.1-1.8 3.5-1.8-3.5z" fill="url(#${prefix}-ember)"/>
  <path d="M24 18.4l2.2 5.4-2.2 5.9-2.2-5.9z" fill="url(#${prefix}-ember)"/>
</svg>`;
}

/** 标识图标（方形），用于侧栏、落地页与登录页 */
export function logo(size = 34) {
  return h('span', {
    class: 'logo-mark',
    style: { width: size + 'px', height: size + 'px' },
    html: logoSvg('nv' + ++logoSeq),
  });
}

export function card(...children) {
  return h('section', { class: 'card' }, ...children);
}

export function cardHead(title, { sub, actions, icon } = {}) {
  return h(
    'header',
    { class: 'card__head' },
    h(
      'div',
      { class: 'card__title-wrap' },
      icon ? h('span', { class: 'card__icon', html: icon }) : null,
      h(
        'div',
        {},
        h('h3', { class: 'card__title' }, title),
        sub ? h('p', { class: 'card__sub' }, sub) : null
      )
    ),
    actions ? h('div', { class: 'card__actions' }, ...(Array.isArray(actions) ? actions : [actions])) : null
  );
}

export function pageHeader(title, { eyebrow, sub, actions } = {}) {
  return h(
    'header',
    { class: 'page-head' },
    h(
      'div',
      {},
      eyebrow ? h('div', { class: 'page-head__eyebrow' }, eyebrow) : null,
      h('h1', { class: 'page-head__title' }, title),
      sub ? h('p', { class: 'page-head__sub' }, sub) : null
    ),
    actions ? h('div', { class: 'page-head__actions' }, ...(Array.isArray(actions) ? actions : [actions])) : null
  );
}

export function btn(label, { tone = 'primary', size, onClick, icon, disabled, type = 'button', title } = {}) {
  return h(
    'button',
    {
      class: ['btn', 'btn--' + tone, size ? 'btn--' + size : ''],
      onclick: onClick,
      disabled,
      type,
      title,
    },
    icon ? h('span', { class: 'btn__icon', html: icon }) : null,
    label ? h('span', {}, label) : null
  );
}

export const icon = {
  check: '<svg viewBox="0 0 16 16" width="14" height="14"><path d="M3 8.5l3.2 3L13 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  x: '<svg viewBox="0 0 16 16" width="14" height="14"><path d="M4 4l8 8M12 4l-8 8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  play: '<svg viewBox="0 0 16 16" width="14" height="14"><path d="M4 3l9 5-9 5z" fill="currentColor"/></svg>',
  send: '<svg viewBox="0 0 16 16" width="14" height="14"><path d="M2 8l12-6-4 12-2.4-4.6z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>',
  refresh: '<svg viewBox="0 0 16 16" width="14" height="14"><path d="M13 8a5 5 0 1 1-1.6-3.7M13 2v3.2h-3.2" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
  plus: '<svg viewBox="0 0 16 16" width="14" height="14"><path d="M8 3v10M3 8h10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  chart: '<svg viewBox="0 0 16 16" width="14" height="14"><path d="M2 13h12M4 13V7M8 13V3M12 13v-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
  shield: '<svg viewBox="0 0 16 16" width="14" height="14"><path d="M8 1.5l5.5 2v4.2c0 3.2-2.2 5.6-5.5 6.8-3.3-1.2-5.5-3.6-5.5-6.8V3.5z" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M5.6 8l1.7 1.7 3.1-3.4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
  code: '<svg viewBox="0 0 16 16" width="14" height="14"><path d="M5.5 5L2.5 8l3 3M10.5 5l3 3-3 3" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  users: '<svg viewBox="0 0 16 16" width="14" height="14"><circle cx="6" cy="5.5" r="2.3" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M1.8 13c.4-2.2 2.2-3.4 4.2-3.4S9.8 10.8 10.2 13" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M10.5 4.2a2.1 2.1 0 0 1 0 3.6M12 13h2.4c-.2-1.4-.9-2.4-2-3" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>',
  time: '<svg viewBox="0 0 16 16" width="14" height="14"><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M8 4.6V8l2.4 1.6" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
  book: '<svg viewBox="0 0 16 16" width="14" height="14"><path d="M3 2.5h4.2c.9 0 1.3.5 1.3 1.2v9.8c0-.7-.4-1.2-1.3-1.2H3zM13 2.5H8.8c-.9 0-1.3.5-1.3 1.2v9.8c0-.7.4-1.2 1.3-1.2H13z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>',
  doc: '<svg viewBox="0 0 16 16" width="14" height="14"><path d="M4 1.8h5l3 3v9.4H4z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M9 1.8v3h3" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M6 8.2h4M6 10.6h4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
  search: '<svg viewBox="0 0 16 16" width="14" height="14"><circle cx="7" cy="7" r="4.3" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M10.4 10.4L14 14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
  down: '<svg viewBox="0 0 16 16" width="14" height="14"><path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  arrow: '<svg viewBox="0 0 16 16" width="14" height="14"><path d="M3 8h9M8.5 4.5L12 8l-3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  spark: '<svg viewBox="0 0 16 16" width="14" height="14"><path d="M8 1.5l1.6 4.4L14 7.5l-4.4 1.6L8 13.5 6.4 9.1 2 7.5l4.4-1.6z" fill="currentColor"/></svg>',
  warn: '<svg viewBox="0 0 16 16" width="14" height="14"><path d="M8 2l6 11H2z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M8 6.4v3M8 11.2v.6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
  trash: '<svg viewBox="0 0 16 16" width="14" height="14"><path d="M3 4.5h10M6.4 4.5V3h3.2v1.5M4.6 4.5l.7 9h5.4l.7-9" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>',
  moon: '<svg viewBox="0 0 16 16" width="15" height="15"><path d="M13 9.6A5.6 5.6 0 0 1 6.4 3 5.7 5.7 0 1 0 13 9.6z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>',
  sun: '<svg viewBox="0 0 16 16" width="15" height="15"><circle cx="8" cy="8" r="3.2" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M8 1.6v1.6M8 12.8v1.6M1.6 8h1.6M12.8 8h1.6M3.5 3.5l1.1 1.1M11.4 11.4l1.1 1.1M12.5 3.5l-1.1 1.1M4.6 11.4l-1.1 1.1" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>',
  bell: '<svg viewBox="0 0 16 16" width="15" height="15"><path d="M4 7a4 4 0 1 1 8 0c0 3 1.2 3.8 1.2 3.8H2.8S4 10 4 7z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M6.6 12.6a1.5 1.5 0 0 0 2.8 0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
};

export function badge(label, tone = 'neutral', { dot = false } = {}) {
  return h(
    'span',
    { class: ['badge', 'badge--' + tone] },
    dot ? h('i', { class: 'badge__dot' }) : null,
    label
  );
}

const VERDICT_TONE = {
  Accepted: 'ok',
  'Wrong Answer': 'danger',
  'Time Limit Exceeded': 'warn',
  'Runtime Error': 'danger',
  'Compile Error': 'neutral',
  'Memory Limit Exceeded': 'warn',
  'Output Limit Exceeded': 'warn',
  AC: 'ok',
  WA: 'danger',
  TLE: 'warn',
  RE: 'danger',
  CE: 'neutral',
  MLE: 'warn',
  OLE: 'warn',
};

const VERDICT_SHORT = {
  Accepted: 'AC',
  'Wrong Answer': 'WA',
  'Time Limit Exceeded': 'TLE',
  'Runtime Error': 'RE',
  'Compile Error': 'CE',
  'Memory Limit Exceeded': 'MLE',
  'Output Limit Exceeded': 'OLE',
};

export function verdictBadge(v, { full = false } = {}) {
  const tone = VERDICT_TONE[v] || 'neutral';
  const label = full ? v : VERDICT_SHORT[v] || v || '—';
  return h('span', { class: ['verdict', 'verdict--' + tone], title: v || '' }, label);
}

export function stat(value, label, { tone = 'brand', hint, icon: ic } = {}) {
  return h(
    'div',
    { class: ['stat', 'stat--' + tone] },
    h(
      'div',
      { class: 'stat__top' },
      h('span', { class: 'stat__value' }, value),
      ic ? h('span', { class: 'stat__icon', html: ic }) : null
    ),
    h('div', { class: 'stat__label' }, label),
    hint ? h('div', { class: 'stat__hint' }, hint) : null
  );
}

export function statRow(items) {
  return h('div', { class: 'stat-row' }, ...items.map((it) => stat(it.value, it.label, it)));
}

export function meter(value, { max = 100, tone = 'brand', label, showValue = true } = {}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return h(
    'div',
    { class: 'meter' },
    h(
      'div',
      { class: 'meter__head' },
      h('span', { class: 'meter__label' }, label || ''),
      showValue ? h('span', { class: 'meter__value' }, `${Math.round(value * 10) / 10}`) : null
    ),
    h('div', { class: 'meter__track' }, h('div', { class: ['meter__fill', 'meter__fill--' + tone], style: { width: pct + '%' } }))
  );
}

export function progress(ratio, { tone = 'brand', showPct = true } = {}) {
  const pct = Math.max(0, Math.min(1, ratio || 0)) * 100;
  return h(
    'div',
    { class: 'progress' },
    h('div', { class: 'progress__track' }, h('div', { class: ['progress__fill', 'progress__fill--' + tone], style: { width: pct + '%' } })),
    showPct ? h('span', { class: 'progress__pct' }, Math.round(pct) + '%') : null
  );
}

/* ------------------------------------------------------------------ 表格 */

export function table(columns, rows, { empty = '暂无数据', rowKey, onRow, dense = false, className = '' } = {}) {
  const thead = h(
    'thead',
    {},
    h(
      'tr',
      {},
      ...columns.map((c) =>
        h('th', { class: c.class || '', style: c.width ? { width: c.width } : null }, c.title)
      )
    )
  );
  const tbody = h('tbody');
  if (!rows.length) {
    tbody.appendChild(
      h(
        'tr',
        {},
        h('td', { class: 'table__empty', colspan: columns.length }, empty)
      )
    );
  }
  rows.forEach((row, idx) => {
    const tr = h(
      'tr',
      {
        class: onRow ? 'is-clickable' : '',
        onclick: onRow ? () => onRow(row, idx) : null,
      },
      ...columns.map((c) => {
        const v = c.render ? c.render(row, idx) : row[c.key];
        const td = h('td', { class: c.class || '' }, v == null ? '—' : v);
        return td;
      })
    );
    if (rowKey) tr.dataset.key = row[rowKey];
    tbody.appendChild(tr);
  });
  return h('div', { class: ['table-wrap', dense ? 'table-wrap--dense' : '', className] }, h('table', { class: 'table' }, thead, tbody));
}

/* ------------------------------------------------------------ 标签页等 */

export function tabs(items, { value, onChange } = {}) {
  const root = h('div', { class: 'tabs' });
  let active = value || items[0].key;
  const renderAll = () => {
    clear(root);
    items.forEach((it) => {
      root.appendChild(
        h(
          'button',
          {
            class: ['tabs__item', it.key === active ? 'is-active' : ''],
            onclick: () => {
              active = it.key;
              renderAll();
              onChange && onChange(it.key);
            },
          },
          it.label,
          it.badge != null ? h('span', { class: 'tabs__badge' }, it.badge) : null
        )
      );
    });
  };
  renderAll();
  root.setValue = (k) => {
    active = k;
    renderAll();
  };
  return root;
}

export function segmented(items, { value, onChange } = {}) {
  const root = h('div', { class: 'segmented' });
  let active = value || items[0].key;
  const renderAll = () => {
    clear(root);
    items.forEach((it) => {
      root.appendChild(
        h(
          'button',
          {
            class: ['segmented__item', it.key === active ? 'is-active' : ''],
            onclick: () => {
              active = it.key;
              renderAll();
              onChange && onChange(it.key);
            },
          },
          it.label
        )
      );
    });
  };
  renderAll();
  return root;
}

export function field(label, control, { hint, required } = {}) {
  return h(
    'label',
    { class: 'field' },
    h('span', { class: 'field__label' }, label, required ? h('i', { class: 'field__req' }, '*') : null),
    control,
    hint ? h('span', { class: 'field__hint' }, hint) : null
  );
}

export function input(props = {}) {
  return h('input', { class: 'input', ...props });
}

export function select(options, props = {}) {
  const el = h('select', { class: 'input', ...props });
  options.forEach((o) => {
    const opt = h('option', { value: o.value }, o.label);
    if (String(o.value) === String(props.value)) opt.selected = true;
    el.appendChild(opt);
  });
  return el;
}

export function textarea(props = {}) {
  return h('textarea', { class: 'input input--area', ...props });
}

export function checkbox(label, props = {}) {
  const id = 'cb' + Math.random().toString(36).slice(2, 8);
  return h(
    'label',
    { class: 'checkbox', for: id },
    h('input', { type: 'checkbox', id, ...props }),
    h('span', {}, label)
  );
}

/* --------------------------------------------------------------- 弹层 */

export function modal(title, content, { actions, width = 720, onClose } = {}) {
  const overlay = h('div', { class: 'overlay' });
  const close = () => {
    overlay.remove();
    onClose && onClose();
  };
  const box = h(
    'div',
    { class: 'modal', style: { maxWidth: width + 'px' } },
    h(
      'header',
      { class: 'modal__head' },
      h('h3', {}, title),
      h('button', { class: 'modal__close', onclick: close, html: icon.x })
    ),
    h('div', { class: 'modal__body' }, content),
    actions ? h('footer', { class: 'modal__foot' }, ...actions(close)) : null
  );
  overlay.appendChild(box);
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) close();
  });
  document.getElementById('overlays').appendChild(overlay);
  return { close, box };
}

export function drawer(title, content, { width = 560, onClose } = {}) {
  const overlay = h('div', { class: 'overlay overlay--right' });
  const close = () => {
    overlay.remove();
    onClose && onClose();
  };
  const box = h(
    'div',
    // 用 min() 限制在视口内：窄窗口下抽屉不会溢出屏幕导致按钮点不到
    { class: 'drawer', style: { width: `min(${width}px, 96vw)` } },
    h(
      'header',
      { class: 'drawer__head' },
      h('h3', {}, title),
      h('button', { class: 'modal__close', onclick: close, html: icon.x })
    ),
    h('div', { class: 'drawer__body' }, content)
  );
  overlay.appendChild(box);
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) close();
  });
  document.getElementById('overlays').appendChild(overlay);
  requestAnimationFrame(() => box.classList.add('is-open'));
  return { close, box };
}

/* ------------------------------------------------------------ 状态块 */

export function empty(title, sub, action) {
  return h(
    'div',
    { class: 'empty' },
    h('div', { class: 'empty__mark' }, '∅'),
    h('strong', {}, title),
    sub ? h('p', {}, sub) : null,
    action || null
  );
}

export function loading(text = '加载中…') {
  return h(
    'div',
    { class: 'loading' },
    h('span', { class: 'spinner' }),
    h('span', {}, text)
  );
}

export function skeleton(rows = 4) {
  const root = h('div', { class: 'skeleton' });
  for (let i = 0; i < rows; i++) root.appendChild(h('div', { class: 'skeleton__line' }));
  return root;
}

export function kv(pairs) {
  return h(
    'dl',
    { class: 'kv' },
    ...pairs.flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, v == null ? '—' : v)])
  );
}

export function note(text, tone = 'info') {
  return h('div', { class: ['note', 'note--' + tone] }, text);
}

/**
 * 代码展示块：带行号，长行可自动换行（阅读代码时比横向滚动友好）。
 * ``lineNumbers`` 用于编译信息之类的短文本时关掉。
 */
export function codeBlock(code, lang = '', { lineNumbers = true, wrap = true, maxHeight } = {}) {
  const text = String(code == null ? '' : code).replace(/\n+$/, '');
  const lines = text.split('\n');
  return h(
    'pre',
    {
      class: ['code-block', wrap ? 'is-wrap' : '', lineNumbers ? 'has-gutter' : ''],
      style: maxHeight ? { maxHeight: maxHeight + 'px', overflowY: 'auto' } : null,
    },
    lineNumbers
      ? h('span', { class: 'code-block__gutter', 'aria-hidden': 'true' },
          lines.map((_l, i) => i + 1).join('\n'))
      : null,
    h('code', { class: 'code-block__body lang-' + lang }, text)
  );
}

/** 代码面板：标题栏 + 换行开关 + 代码块，用于评审/提交详情里阅读代码。 */
export function codePanel(code, lang = 'cpp', { title = '源代码', sub } = {}) {
  let wrap = true;
  const box = h('div');
  const paint = () => {
    clear(box);
    box.appendChild(codeBlock(code, lang, { wrap }));
  };
  paint();
  return h(
    'div',
    {},
    h(
      'div',
      { class: 'row between', style: { marginBottom: '8px' } },
      h('div', {}, h('b', { style: { fontSize: '13.5px' } }, title),
        sub ? h('span', { class: 'small muted', style: { marginLeft: '8px' } }, sub) : null),
      btn(wrap ? '关闭自动换行' : '自动换行', {
        tone: 'plain', size: 'xs',
        onClick: (e) => {
          wrap = !wrap;
          e.target.closest('button').textContent = wrap ? '关闭自动换行' : '自动换行';
          paint();
        },
      })
    ),
    box
  );
}

export function tagList(tags, tone = 'soft') {
  if (!tags || !tags.length) return h('span', { class: 'muted' }, '—');
  return h('span', { class: 'tag-list' }, ...tags.map((t) => h('span', { class: ['tag', 'tag--' + tone] }, t)));
}

export function diffStat(a, b, { unit = '', digits = 1, invert = false } = {}) {
  if (a == null || b == null || b === 0) return h('span', { class: 'muted' }, '—');
  const d = ((a - b) / b) * 100;
  const good = invert ? d < 0 : d > 0;
  return h(
    'span',
    { class: ['diff', good ? 'diff--up' : 'diff--down'] },
    (d > 0 ? '+' : '') + d.toFixed(digits) + '%'
  );
}

export function fmt(n, digits = 0) {
  if (n == null || Number.isNaN(n)) return '—';
  return Number(n).toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function fmtTime(ms) {
  if (ms == null) return '—';
  if (ms < 1) return ms.toFixed(2) + ' ms';
  if (ms < 1000) return ms.toFixed(1) + ' ms';
  return (ms / 1000).toFixed(2) + ' s';
}

export function fmtMem(kb) {
  if (kb == null || kb === 0) return '—';
  if (kb < 1024) return kb.toFixed(0) + ' KB';
  return (kb / 1024).toFixed(1) + ' MB';
}

export function fmtDate(s, { withTime = true } = {}) {
  if (!s) return '—';
  const d = new Date(String(s).replace(/-/g, '/'));
  if (Number.isNaN(d.getTime())) return s;
  const pad = (x) => String(x).padStart(2, '0');
  const base = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  return withTime ? `${base} ${pad(d.getHours())}:${pad(d.getMinutes())}` : base;
}

export function timeAgo(s) {
  if (!s) return '—';
  const d = new Date(String(s).replace(/-/g, '/'));
  if (Number.isNaN(d.getTime())) return s;
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return '刚刚';
  if (diff < 3600) return Math.floor(diff / 60) + ' 分钟前';
  if (diff < 86400) return Math.floor(diff / 3600) + ' 小时前';
  if (diff < 86400 * 30) return Math.floor(diff / 86400) + ' 天前';
  return fmtDate(s, { withTime: false });
}

export function countdown(due) {
  if (!due) return h('span', { class: 'muted' }, '未设截止');
  const d = new Date(String(due).replace(/-/g, '/'));
  const diff = d.getTime() - Date.now();
  if (diff < 0) return h('span', { class: 'badge badge--danger' }, '已截止');
  const days = Math.floor(diff / 86400000);
  const hours = Math.floor((diff % 86400000) / 3600000);
  if (days >= 1) return h('span', { class: 'badge badge--warn' }, `剩 ${days} 天 ${hours} 时`);
  return h('span', { class: 'badge badge--warn' }, `剩 ${hours} 小时`);
}

export function avatar(user, size = 32) {
  const name = user && user.name ? user.name : '?';
  return h(
    'span',
    {
      class: 'avatar',
      style: { width: size + 'px', height: size + 'px', fontSize: size * 0.42 + 'px' },
      title: name,
    },
    name.slice(0, 1)
  );
}

export function barMini(value, max, tone = 'brand') {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return h(
    'span',
    { class: 'bar-mini' },
    h('i', { class: ['bar-mini__fill', 'bar-mini__fill--' + tone], style: { width: pct + '%' } })
  );
}

export function alertRow(level, title, detail, actions) {
  return h(
    'div',
    { class: ['alert-row', 'alert-row--' + level] },
    h('span', { class: 'alert-row__mark' }),
    h(
      'div',
      { class: 'alert-row__body' },
      h('strong', {}, title),
      detail ? h('p', {}, detail) : null
    ),
    actions ? h('div', { class: 'alert-row__actions' }, ...(Array.isArray(actions) ? actions : [actions])) : null
  );
}
