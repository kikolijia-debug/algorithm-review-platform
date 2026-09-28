/**
 * 教师端「合并页」：把原来分散在多级菜单里的功能收进同一个页面的标签页，
 * 让菜单从 11 项精简到 6 项，教师用一个入口就能完成一类工作。
 *
 *   作业与题库   = 作业管理 + 题库管理
 *   班级与学生   = 班级管理 + 提交记录
 *   学情分析     = 学习过程分析 + 能力与难度估计
 *   评审管理     = 分配与评分 + 异常复核 + 代码相似度
 *
 * 原来的独立路由仍然保留，深链接不会失效。
 */

import { h, clear } from '../core/dom.js';
import * as U from '../core/ui.js';
import * as T from './teacher-core.js';
import * as TI from './teacher-insight.js';
import * as S from './student.js';
import * as TC from './teacher-classes.js';
import * as M from './materials.js';

/** 把一个页面的多个视图做成标签页；每个视图渲染完整的子页面。 */
function merged(tabs, container) {
  const pane = h('div');
  const show = (key) => {
    clear(pane);
    const tab = tabs.find((x) => x.key === key) || tabs[0];
    pane.appendChild(tab.render(container));
  };
  const bar = U.tabs(
    tabs.map((t) => ({ key: t.key, label: t.label, badge: t.badge })),
    { onChange: show }
  );
  show(tabs[0].key);
  return h('div', {}, bar, pane);
}

/** 并进别人的标签页时，去掉子页面自己的大标题，避免出现两层标题。 */
function bodyOnly(node) {
  const head = node.querySelector(':scope > .page-head');
  if (head) head.remove();
  return node;
}

/* ------------------------------------------------------ 作业与题库 */

export async function loadWork(ctx) {
  const [assignments, problems, materials] = await Promise.all([
    T.loadAssignments(),
    S.loadProblemList(ctx),
    M.loadMaterials(ctx),
  ]);
  return { assignments, problems, materials };
}

export function renderWork(d, container, ctx) {
  return merged(
    [
      { key: 'assignments', label: '作业', render: () => T.renderAssignments(d.assignments) },
      { key: 'problems', label: '题库', render: () => S.renderProblemList(d.problems, container, ctx) },
      { key: 'materials', label: '课件', render: () => bodyOnly(M.renderMaterials(d.materials, container, ctx)) },
    ],
    container
  );
}

/* ------------------------------------------------------ 班级与学生 */

export async function loadStudentsPage(ctx) {
  const [classes, submissions] = await Promise.all([
    TC.loadClasses(),
    T.loadTeacherSubmissions(ctx),
  ]);
  return { classes, submissions };
}

export function renderStudentsPage(d, container) {
  return merged(
    [
      { key: 'classes', label: '班级', render: () => TC.renderClasses(d.classes) },
      { key: 'submissions', label: '提交记录', render: () => T.renderTeacherSubmissions(d.submissions) },
    ],
    container
  );
}

/* -------------------------------------------------------- 学情分析 */

export async function loadAnalyticsAll(ctx) {
  const [analytics, ability] = await Promise.all([
    TI.loadAnalytics(ctx),
    TI.loadAbility(ctx),
  ]);
  return { analytics, ability };
}

export function renderAnalyticsAll(d, container) {
  // 直接把「能力与难度」并进学情分析自己的标签栏，避免两层标签
  return TI.renderAnalytics(d.analytics, container, [
    { key: 'ability', label: '能力与难度', render: () => bodyOnly(TI.renderAbility(d.ability)) },
  ]);
}

/* -------------------------------------------------------- 评审管理 */

export async function loadReviewsAll(ctx) {
  const [admin, anomalies, similarity] = await Promise.all([
    TI.loadReviewAdmin(ctx),
    TI.loadAnomalies(ctx),
    TI.loadSimilarity(ctx),
  ]);
  return { admin, anomalies, similarity };
}

export function renderReviewsAll(d, container, ctx) {
  const pending = (d.anomalies.data.counts || {}).open || 0;
  return TI.renderReviewAdmin(d.admin, container, [
    { key: 'anomalies', label: '异常复核', badge: pending || null,
      render: () => bodyOnly(TI.renderAnomalies(d.anomalies)) },
    { key: 'similarity', label: '代码相似度',
      render: () => bodyOnly(TI.renderSimilarity(d.similarity)) },
  ]);
}
