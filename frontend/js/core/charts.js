/**
 * 纯 SVG 图表库（无第三方依赖，约 400 行覆盖全部可视化需求）。
 *
 * 之所以自己写而不是引入 ECharts：项目要求「零构建、零依赖、可直接静态托管」，
 * 同时图表风格需要与整体设计令牌严格一致（统一色板、圆角、网格线样式）。
 */

import { h } from './dom.js';

export const PALETTE = ['#0f6b4f', '#17a06a', '#0e9c8c', '#3f8fd6', '#c98a1f', '#b45fa6', '#c0503f', '#5f7f93'];

const NS = 'http://www.w3.org/2000/svg';

function s(tag, attrs = {}, ...kids) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'text') el.textContent = v;
    else el.setAttribute(k, String(v));
  }
  kids.flat().forEach((kid) => kid && el.appendChild(kid));
  return el;
}

function svgWrap(width, height, children, { class: cls = '', responsive = true } = {}) {
  const svg = s(
    'svg',
    {
      viewBox: `0 0 ${width} ${height}`,
      width: responsive ? '100%' : width,
      height: responsive ? undefined : height,
      preserveAspectRatio: responsive ? 'xMidYMid meet' : undefined,
      class: 'chart ' + cls,
      style: responsive ? `max-height:${height}px` : null,
    },
    ...children
  );
  return h('div', { class: 'chart-wrap' }, svg);
}

function niceMax(v) {
  if (v <= 0) return 1;
  const exp = Math.floor(Math.log10(v));
  const base = Math.pow(10, exp);
  const n = v / base;
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10;
  return step * base;
}

function shortNum(v) {
  if (Math.abs(v) >= 10000) return (v / 1000).toFixed(0) + 'k';
  if (Math.abs(v) >= 1000) return (v / 1000).toFixed(1) + 'k';
  return String(Math.round(v * 100) / 100);
}

/* ------------------------------------------------------------- 柱状图 */

export function barChart(data, opts = {}) {
  const {
    width = 640, height = 240, tone = 'brand', color, valueKey = 'value', labelKey = 'label',
    max, horizontal = false, showValue = true, unit = '', stacked = null, colors = PALETTE,
  } = opts;
  const pad = horizontal ? { l: 96, r: 48, t: 12, b: 24 } : { l: 44, r: 14, t: 18, b: 44 };
  const W = width - pad.l - pad.r;
  const H = height - pad.t - pad.b;
  const keys = stacked || null;
  const totals = data.map((d) =>
    keys ? keys.reduce((acc, k) => acc + (Number(d[k]) || 0), 0) : Number(d[valueKey]) || 0
  );
  const mx = niceMax(max || Math.max(1, ...totals));
  const n = data.length || 1;

  const kids = [];
  // 网格与刻度
  const ticks = 4;
  for (let i = 0; i <= ticks; i++) {
    const v = (mx / ticks) * i;
    if (horizontal) {
      const x = pad.l + (v / mx) * W;
      kids.push(s('line', { x1: x, y1: pad.t, x2: x, y2: pad.t + H, class: 'grid' }));
      kids.push(s('text', { x, y: pad.t + H + 16, class: 'axis', 'text-anchor': 'middle', text: shortNum(v) }));
    } else {
      const y = pad.t + H - (v / mx) * H;
      kids.push(s('line', { x1: pad.l, y1: y, x2: pad.l + W, y2: y, class: 'grid' }));
      kids.push(s('text', { x: pad.l - 8, y: y + 4, class: 'axis', 'text-anchor': 'end', text: shortNum(v) }));
    }
  }

  data.forEach((d, i) => {
    const total = totals[i];
    if (horizontal) {
      const bh = (H / n) * 0.62;
      const y = pad.t + (H / n) * (i + 0.5) - bh / 2;
      let offset = 0;
      const parts = keys || [valueKey];
      parts.forEach((k, ki) => {
        const v = Number(d[k]) || 0;
        const wpx = (v / mx) * W;
        const x0 = pad.l + offset;
        offset += wpx;
        kids.push(
          s('rect', {
            x: x0, y, width: Math.max(0, wpx - 1), height: bh,
            rx: 3, fill: color || colors[ki % colors.length], class: 'bar',
          }, s('title', { text: `${d[labelKey]} · ${k}: ${v}` }))
        );
      });
      kids.push(s('text', { x: pad.l - 10, y: y + bh / 2 + 4, class: 'axis axis--label', 'text-anchor': 'end', text: d[labelKey] }));
      if (showValue) {
        kids.push(s('text', { x: pad.l + (total / mx) * W + 6, y: y + bh / 2 + 4, class: 'axis axis--value', text: shortNum(total) + unit }));
      }
    } else {
      const bw = (W / n) * 0.58;
      const cx = pad.l + (W / n) * (i + 0.5);
      const parts = keys || [valueKey];
      let acc = 0;
      parts.forEach((k, ki) => {
        const v = Number(d[k]) || 0;
        const bh = (v / mx) * H;
        const y = pad.t + H - bh - (acc / mx) * H;
        acc += v;
        kids.push(
          s('rect', {
            x: cx - bw / 2, y, width: bw, height: Math.max(0, bh),
            rx: 3, fill: color || colors[ki % colors.length], class: 'bar',
          }, s('title', { text: `${d[labelKey]} · ${k}: ${v}` }))
        );
      });
      if (showValue && total > 0) {
        kids.push(s('text', { x: cx, y: pad.t + H - (total / mx) * H - 6, class: 'axis axis--value', 'text-anchor': 'middle', text: shortNum(total) + unit }));
      }
      const lbl = String(d[labelKey]);
      kids.push(s('text', {
        x: cx, y: pad.t + H + 18, class: 'axis axis--label', 'text-anchor': 'middle',
        text: lbl.length > 6 ? lbl.slice(0, 6) + '…' : lbl,
      }, s('title', { text: lbl })));
    }
  });
  kids.push(s('line', { x1: pad.l, y1: pad.t + H, x2: pad.l + W, y2: pad.t + H, class: 'axis-line' }));
  return svgWrap(width, height, kids);
}

/* ------------------------------------------------------------- 折线图 */

export function lineChart(series, opts = {}) {
  const { width = 640, height = 260, xLabels = [], colors = PALETTE, yUnit = '', area = true, points = true } = opts;
  const pad = { l: 48, r: 16, t: 18, b: 40 };
  const W = width - pad.l - pad.r;
  const H = height - pad.t - pad.b;
  const all = series.flatMap((sr) => sr.values.filter((v) => v != null));
  const mx = niceMax(Math.max(1, ...all));
  const n = Math.max(1, (series[0] || { values: [] }).values.length - 1);
  const X = (i) => pad.l + (W / n) * i;
  const Y = (v) => pad.t + H - (v / mx) * H;

  const kids = [];
  for (let i = 0; i <= 4; i++) {
    const v = (mx / 4) * i;
    kids.push(s('line', { x1: pad.l, y1: Y(v), x2: pad.l + W, y2: Y(v), class: 'grid' }));
    kids.push(s('text', { x: pad.l - 8, y: Y(v) + 4, class: 'axis', 'text-anchor': 'end', text: shortNum(v) }));
  }
  const step = Math.max(1, Math.ceil(xLabels.length / 8));
  xLabels.forEach((lb, i) => {
    if (i % step) return;
    kids.push(s('text', { x: X(i), y: pad.t + H + 18, class: 'axis', 'text-anchor': 'middle', text: lb }));
  });
  series.forEach((sr, si) => {
    const color = sr.color || colors[si % colors.length];
    const path = sr.values
      .map((v, i) => `${i ? 'L' : 'M'}${X(i)},${Y(v == null ? 0 : v)}`)
      .join(' ');
    if (area) {
      kids.push(s('path', { d: `${path} L${X(sr.values.length - 1)},${pad.t + H} L${X(0)},${pad.t + H} Z`, fill: color, opacity: 0.1 }));
    }
    kids.push(s('path', { d: path, fill: 'none', stroke: color, 'stroke-width': 2.4, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
    if (points) {
      sr.values.forEach((v, i) => {
        if (v == null) return;
        kids.push(s('circle', { cx: X(i), cy: Y(v), r: 3, fill: '#fff', stroke: color, 'stroke-width': 2 },
          s('title', { text: `${sr.name} · ${xLabels[i] || ''}: ${v}${yUnit}` })));
      });
    }
  });
  kids.push(s('line', { x1: pad.l, y1: pad.t + H, x2: pad.l + W, y2: pad.t + H, class: 'axis-line' }));
  const wrap = svgWrap(width, height, kids);
  if (series.length > 1) {
    wrap.appendChild(
      h('div', { class: 'legend' },
        ...series.map((sr, i) => h('span', { class: 'legend__item' },
          h('i', { class: 'legend__dot', style: { background: sr.color || colors[i % colors.length] } }),
          sr.name)))
    );
  }
  return wrap;
}

/* --------------------------------------------------------------- 雷达 */

export function radarChart(labels, values, opts = {}) {
  const { width = 360, height = 320, max = 100, color = '#0f6b4f', compare = null, compareColor = '#c98a1f' } = opts;
  const cx = width / 2;
  const cy = height / 2 + 6;
  const R = Math.min(width, height) / 2 - 52;
  const n = labels.length || 1;
  const angle = (i) => (Math.PI * 2 * i) / n - Math.PI / 2;
  const pt = (i, v) => [cx + Math.cos(angle(i)) * R * (v / max), cy + Math.sin(angle(i)) * R * (v / max)];
  const kids = [];
  for (let ring = 1; ring <= 4; ring++) {
    const r = (R * ring) / 4;
    const d = labels.map((_l, i) => {
      const x = cx + Math.cos(angle(i)) * r;
      const y = cy + Math.sin(angle(i)) * r;
      return `${i ? 'L' : 'M'}${x},${y}`;
    }).join(' ') + ' Z';
    kids.push(s('path', { d, fill: 'none', stroke: '#e2ebe7', 'stroke-width': 1 }));
  }
  labels.forEach((_l, i) => {
    const [x, y] = pt(i, max);
    kids.push(s('line', { x1: cx, y1: cy, x2: x, y2: y, stroke: '#e6edea', 'stroke-width': 1 }));
  });
  if (compare) {
    const d = compare.map((v, i) => {
      const [x, y] = pt(i, Math.max(0, Math.min(max, v || 0)));
      return `${i ? 'L' : 'M'}${x},${y}`;
    }).join(' ') + ' Z';
    kids.push(s('path', { d, fill: compareColor, opacity: 0.12, stroke: compareColor, 'stroke-width': 1.6, 'stroke-dasharray': '4 3' }));
  }
  const d = values.map((v, i) => {
    const [x, y] = pt(i, Math.max(0, Math.min(max, v || 0)));
    return `${i ? 'L' : 'M'}${x},${y}`;
  }).join(' ') + ' Z';
  kids.push(s('path', { d, fill: color, opacity: 0.2, stroke: color, 'stroke-width': 2.2, 'stroke-linejoin': 'round' }));
  values.forEach((v, i) => {
    const [x, y] = pt(i, Math.max(0, Math.min(max, v || 0)));
    kids.push(s('circle', { cx: x, cy: y, r: 3.4, fill: '#fff', stroke: color, 'stroke-width': 2 }, s('title', { text: `${labels[i]}: ${v}` })));
  });
  labels.forEach((l, i) => {
    const a = angle(i);
    const x = cx + Math.cos(a) * (R + 26);
    const y = cy + Math.sin(a) * (R + 22);
    const anchor = Math.abs(Math.cos(a)) < 0.3 ? 'middle' : Math.cos(a) > 0 ? 'start' : 'end';
    kids.push(s('text', { x, y: y + 4, class: 'axis axis--radar', 'text-anchor': anchor, text: l.length > 8 ? l.slice(0, 8) : l },
      s('title', { text: l })));
  });
  return svgWrap(width, height, kids);
}

/* --------------------------------------------------------------- 环形 */

export function donutChart(segments, opts = {}) {
  const { width = 260, height = 220, thickness = 26, centerLabel, centerValue, colors = PALETTE, donut = true } = opts;
  const cx = width / 2;
  const cy = height / 2;
  const R = Math.min(width, height) / 2 - 16;
  const total = segments.reduce((acc, sg) => acc + (sg.value || 0), 0) || 1;
  let acc = 0;
  const kids = [];
  const arc = (from, to, r0, r1) => {
    const a0 = (from / total) * Math.PI * 2 - Math.PI / 2;
    const a1 = (to / total) * Math.PI * 2 - Math.PI / 2;
    const large = to - from > total / 2 ? 1 : 0;
    const x0 = cx + Math.cos(a0) * r0, y0 = cy + Math.sin(a0) * r0;
    const x1 = cx + Math.cos(a1) * r0, y1 = cy + Math.sin(a1) * r0;
    const x2 = cx + Math.cos(a1) * r1, y2 = cy + Math.sin(a1) * r1;
    const x3 = cx + Math.cos(a0) * r1, y3 = cy + Math.sin(a0) * r1;
    if (!donut) {
      return `M${cx},${cy} L${x0},${y0} A${r0},${r0} 0 ${large} 1 ${x1},${y1} Z`;
    }
    return `M${x0},${y0} A${r0},${r0} 0 ${large} 1 ${x1},${y1} L${x2},${y2} A${r1},${r1} 0 ${large} 0 ${x3},${y3} Z`;
  };
  const r1 = R;
  const r0 = donut ? R - thickness : 0;
  segments.forEach((sg, i) => {
    if (!sg.value) return;
    const from = acc;
    acc += sg.value;
    if (acc - from >= total - 0.0001 && segments.length === 1) {
      kids.push(s('circle', { cx, cy, r: (r0 + r1) / 2, fill: 'none', stroke: sg.color || colors[i % colors.length], 'stroke-width': r1 - r0 }));
      return;
    }
    kids.push(s('path', {
      d: arc(from, acc, r0, r1),
      fill: sg.color || colors[i % colors.length],
      class: 'donut-seg',
    }, s('title', { text: `${sg.label}: ${sg.value} (${((sg.value / total) * 100).toFixed(1)}%)` })));
  });
  if (centerLabel || centerValue != null) {
    kids.push(s('text', { x: cx, y: cy + (centerLabel ? -2 : 6), class: 'donut-value', 'text-anchor': 'middle', text: centerValue }));
    if (centerLabel) kids.push(s('text', { x: cx, y: cy + 18, class: 'donut-label', 'text-anchor': 'middle', text: centerLabel }));
  }
  const wrap = svgWrap(width, height, kids);
  if (opts.showLegend !== false) {
    wrap.appendChild(
      h('div', { class: 'legend legend--col' },
        ...segments.map((sg, i) => h('span', { class: 'legend__item' },
          h('i', { class: 'legend__dot', style: { background: sg.color || colors[i % colors.length] } }),
          h('span', {}, sg.label),
          h('b', {}, shortNum(sg.value)))))
    );
  }
  return wrap;
}

export function gauge(value, opts = {}) {
  const { size = 160, thickness = 14, max = 100, label = '', tone = '#0f6b4f' } = opts;
  const r = size / 2 - thickness / 2 - 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, value / max));
  const svg = s('svg', { viewBox: `0 0 ${size} ${size}`, width: size, height: size, class: 'chart' },
    s('circle', { cx: size / 2, cy: size / 2, r, fill: 'none', stroke: '#e8efec', 'stroke-width': thickness }),
    s('circle', {
      cx: size / 2, cy: size / 2, r, fill: 'none', stroke: tone, 'stroke-width': thickness,
      'stroke-linecap': 'round', 'stroke-dasharray': `${c * pct} ${c}`,
      transform: `rotate(-90 ${size / 2} ${size / 2})`,
    }),
    s('text', { x: size / 2, y: size / 2 + 2, class: 'donut-value', 'text-anchor': 'middle', text: String(Math.round(value)) }),
    s('text', { x: size / 2, y: size / 2 + 22, class: 'donut-label', 'text-anchor': 'middle', text: label })
  );
  return h('div', { class: 'chart-wrap chart-wrap--center' }, svg);
}

/* ------------------------------------------------------------- 散点图 */

export function scatterChart(points, opts = {}) {
  const { width = 560, height = 300, xLabel = 'x', yLabel = 'y', color = '#0f6b4f', trend = false, rKey = null } = opts;
  const pad = { l: 48, r: 18, t: 18, b: 40 };
  const W = width - pad.l - pad.r;
  const H = height - pad.t - pad.b;
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const xmin = Math.min(...xs, 0), xmax = Math.max(...xs, 1);
  const ymin = Math.min(...ys, 0), ymax = niceMax(Math.max(...ys, 1));
  const X = (v) => pad.l + ((v - xmin) / (xmax - xmin || 1)) * W;
  const Y = (v) => pad.t + H - ((v - ymin) / (ymax - ymin || 1)) * H;
  const kids = [];
  for (let i = 0; i <= 4; i++) {
    const v = ymin + ((ymax - ymin) / 4) * i;
    kids.push(s('line', { x1: pad.l, y1: Y(v), x2: pad.l + W, y2: Y(v), class: 'grid' }));
    kids.push(s('text', { x: pad.l - 8, y: Y(v) + 4, class: 'axis', 'text-anchor': 'end', text: shortNum(v) }));
  }
  for (let i = 0; i <= 4; i++) {
    const v = xmin + ((xmax - xmin) / 4) * i;
    kids.push(s('text', { x: X(v), y: pad.t + H + 18, class: 'axis', 'text-anchor': 'middle', text: shortNum(v) }));
  }
  points.forEach((p) => {
    kids.push(s('circle', {
      cx: X(p.x), cy: Y(p.y), r: rKey ? Math.max(3, Math.min(14, p[rKey] || 4)) : 4.5,
      fill: p.color || color, opacity: 0.75,
    }, s('title', { text: `${p.label || ''} (${shortNum(p.x)}, ${shortNum(p.y)})` })));
  });
  if (trend && points.length > 2) {
    const n = points.length;
    const mx = xs.reduce((a, b) => a + b, 0) / n;
    const my = ys.reduce((a, b) => a + b, 0) / n;
    const den = xs.reduce((a, b) => a + (b - mx) ** 2, 0) || 1;
    const slope = xs.reduce((a, b, i) => a + (b - mx) * (ys[i] - my), 0) / den;
    const b0 = my - slope * mx;
    kids.push(s('line', {
      x1: X(xmin), y1: Y(b0 + slope * xmin), x2: X(xmax), y2: Y(b0 + slope * xmax),
      stroke: '#c98a1f', 'stroke-width': 2, 'stroke-dasharray': '6 4',
    }));
  }
  kids.push(s('line', { x1: pad.l, y1: pad.t + H, x2: pad.l + W, y2: pad.t + H, class: 'axis-line' }));
  kids.push(s('text', { x: pad.l + W / 2, y: height - 6, class: 'axis axis--title', 'text-anchor': 'middle', text: xLabel }));
  kids.push(s('text', { x: 12, y: pad.t + H / 2, class: 'axis axis--title', 'text-anchor': 'middle', transform: `rotate(-90 12 ${pad.t + H / 2})`, text: yLabel }));
  return svgWrap(width, height, kids);
}

/* ------------------------------------------------------------ 网络图 */

export function networkGraph(nodes, edges, opts = {}) {
  const { width = 520, height = 420, colors = PALETTE, focus = [] } = opts;
  const cx = width / 2, cy = height / 2, R = Math.min(width, height) / 2 - 34;
  const pos = {};
  nodes.forEach((nd, i) => {
    const a = (Math.PI * 2 * i) / Math.max(1, nodes.length) - Math.PI / 2;
    pos[nd.id] = [cx + Math.cos(a) * R, cy + Math.sin(a) * R];
  });
  const kids = [];
  const maxW = Math.max(1, ...edges.map((e) => e.weight || 1));
  edges.forEach((e) => {
    const p1 = pos[e.source], p2 = pos[e.target];
    if (!p1 || !p2) return;
    const hot = focus.includes(e.source) && focus.includes(e.target);
    kids.push(s('line', {
      x1: p1[0], y1: p1[1], x2: p2[0], y2: p2[1],
      stroke: hot ? '#c0503f' : '#9dbab0',
      'stroke-width': hot ? 2.4 : 0.6 + ((e.weight || 1) / maxW) * 1.4,
      opacity: hot ? 0.95 : 0.5,
    }, s('title', { text: `${e.source} → ${e.target}（${e.weight}）` })));
  });
  const deg = {};
  edges.forEach((e) => {
    deg[e.source] = (deg[e.source] || 0) + 1;
    deg[e.target] = (deg[e.target] || 0) + 1;
  });
  nodes.forEach((nd, i) => {
    const [x, y] = pos[nd.id];
    const r = 5 + Math.min(9, (deg[nd.id] || 0) * 1.1);
    const hot = focus.includes(nd.id);
    kids.push(s('circle', { cx: x, cy: y, r, fill: hot ? '#c0503f' : colors[i % colors.length], opacity: 0.9 },
      s('title', { text: `${nd.label || nd.id}（度 ${deg[nd.id] || 0}）` })));
  });
  return svgWrap(width, height, kids);
}

/* ------------------------------------------------------------ 热力图 */

export function heatmap(matrix, opts = {}) {
  const { width = 560, height = 260, xLabels = [], yLabels = [], max = null, color = '#0f6b4f' } = opts;
  const pad = { l: 92, r: 12, t: 24, b: 30 };
  const W = width - pad.l - pad.r;
  const H = height - pad.t - pad.b;
  const rows = matrix.length || 1;
  const cols = (matrix[0] || []).length || 1;
  const mx = max || Math.max(1, ...matrix.flat());
  const kids = [];
  matrix.forEach((row, i) => {
    row.forEach((v, j) => {
      const x = pad.l + (W / cols) * j;
      const y = pad.t + (H / rows) * i;
      const t = Math.max(0, Math.min(1, v / mx));
      kids.push(s('rect', {
        x: x + 1, y: y + 1, width: W / cols - 2, height: H / rows - 2, rx: 3,
        fill: color, opacity: 0.08 + t * 0.85,
      }, s('title', { text: `${yLabels[i] || i} · ${xLabels[j] || j}: ${v}` })));
      if (v > 0) {
        kids.push(s('text', {
          x: x + W / cols / 2, y: y + H / rows / 2 + 4,
          class: 'axis axis--cell', 'text-anchor': 'middle',
          fill: t > 0.55 ? '#fff' : '#3c5148', text: shortNum(v),
        }));
      }
    });
  });
  yLabels.forEach((l, i) => kids.push(s('text', {
    x: pad.l - 8, y: pad.t + (H / rows) * (i + 0.5) + 4, class: 'axis', 'text-anchor': 'end',
    text: l.length > 9 ? l.slice(0, 9) + '…' : l,
  }, s('title', { text: l }))));
  xLabels.forEach((l, j) => kids.push(s('text', {
    x: pad.l + (W / cols) * (j + 0.5), y: pad.t + H + 16, class: 'axis', 'text-anchor': 'middle',
    text: l.length > 6 ? l.slice(0, 6) + '…' : l,
  }, s('title', { text: l }))));
  return svgWrap(width, height, kids);
}

/* ------------------------------------------------------ 分配关系弧线图 */

export function bipartiteGraph(allocations, opts = {}) {
  const { width = 900, height = 380, authorLabel = (a) => '#' + a, reviewerLabel = (r) => '#' + r } = opts;
  const authors = [...new Set(allocations.map((a) => a.author))].sort((a, b) => a - b);
  const reviewers = [...new Set(allocations.map((a) => a.reviewer))].sort((a, b) => a - b);
  const pad = 40;
  const W = width - pad * 2;
  const yA = {};
  const yR = {};
  authors.forEach((a, i) => (yA[a] = pad + ((height - pad * 2) / Math.max(1, authors.length - 1 || 1)) * i));
  reviewers.forEach((r, i) => (yR[r] = pad + ((height - pad * 2) / Math.max(1, reviewers.length - 1 || 1)) * i));
  const kids = [];
  allocations.forEach((al) => {
    const y1 = yA[al.author], y2 = yR[al.reviewer];
    if (y1 == null || y2 == null) return;
    kids.push(s('path', {
      d: `M${pad + 14},${y1} C${width / 2},${y1} ${width / 2},${y2} ${width - pad - 14},${y2}`,
      fill: 'none', stroke: al.color || '#8fb3a6', 'stroke-width': al.hot ? 2 : 0.9,
      opacity: al.hot ? 0.95 : 0.35,
    }, s('title', { text: `${authorLabel(al.author)} → ${reviewerLabel(al.reviewer)}` })));
  });
  authors.forEach((a) => {
    kids.push(s('circle', { cx: pad + 8, cy: yA[a], r: 4.5, fill: '#0f6b4f' }, s('title', { text: authorLabel(a) })));
  });
  reviewers.forEach((r) => {
    kids.push(s('circle', { cx: width - pad - 8, cy: yR[r], r: 4.5, fill: '#3f8fd6' }, s('title', { text: reviewerLabel(r) })));
  });
  kids.push(s('text', { x: pad, y: 16, class: 'axis axis--title', text: '作业（作者）' }));
  kids.push(s('text', { x: width - pad, y: 16, class: 'axis axis--title', 'text-anchor': 'end', text: '评审者' }));
  return svgWrap(width, height, kids);
}

/* --------------------------------------------------------- 复杂度曲线 */

export function complexityChart(points, opts = {}) {
  const { width = 620, height = 300 } = opts;
  const pad = { l: 62, r: 18, t: 18, b: 44 };
  const W = width - pad.l - pad.r;
  const H = height - pad.t - pad.b;
  const xs = points.map((p) => p.n);
  const ys = points.map((p) => Math.max(p.time_ms, 0.01));
  const logX = (v) => pad.l + ((Math.log10(v) - Math.log10(Math.min(...xs))) / (Math.log10(Math.max(...xs)) - Math.log10(Math.min(...xs)) || 1)) * W;
  const logY = (v) => pad.t + H - ((Math.log10(v) - Math.log10(Math.min(...ys))) / (Math.log10(Math.max(...ys)) - Math.log10(Math.min(...ys)) || 1)) * H;
  const kids = [];
  for (let i = 0; i <= 4; i++) {
    const y = pad.t + (H / 4) * i;
    const v = Math.pow(10, Math.log10(Math.max(...ys)) - ((Math.log10(Math.max(...ys)) - Math.log10(Math.min(...ys))) / 4) * i);
    kids.push(s('line', { x1: pad.l, y1: y, x2: pad.l + W, y2: y, class: 'grid' }));
    kids.push(s('text', { x: pad.l - 8, y: y + 4, class: 'axis', 'text-anchor': 'end', text: v >= 1 ? shortNum(v) + 'ms' : v.toFixed(2) + 'ms' }));
  }
  const d = points.map((p, i) => `${i ? 'L' : 'M'}${logX(p.n)},${logY(Math.max(p.time_ms, 0.01))}`).join(' ');
  kids.push(s('path', { d, fill: 'none', stroke: '#0f6b4f', 'stroke-width': 2.6, 'stroke-linejoin': 'round' }));
  points.forEach((p) => {
    kids.push(s('circle', { cx: logX(p.n), cy: logY(Math.max(p.time_ms, 0.01)), r: 4.5, fill: '#fff', stroke: '#0f6b4f', 'stroke-width': 2.2 },
      s('title', { text: `n=${p.n}: ${p.time_ms} ms` })));
    kids.push(s('text', { x: logX(p.n), y: pad.t + H + 18, class: 'axis', 'text-anchor': 'middle', text: shortNum(p.n) }));
  });
  kids.push(s('text', { x: pad.l + W / 2, y: height - 6, class: 'axis axis--title', 'text-anchor': 'middle', text: '输入规模 n（对数轴）' }));
  kids.push(s('text', { x: 14, y: pad.t + H / 2, class: 'axis axis--title', 'text-anchor': 'middle', transform: `rotate(-90 14 ${pad.t + H / 2})`, text: '用时（对数轴）' }));
  return svgWrap(width, height, kids);
}
