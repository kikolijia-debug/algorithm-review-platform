/**
 * 智能出题（教师端弹窗）。
 *
 * 教师选「章节 + 难度」→ 后端现场生成一道编程题：
 * 题面、输入输出格式、约束都按实际数据规模写成，测试数据的期望输出
 * 由模板自带的参考程序算出，所以生成完就能直接评测。
 *
 * 生成结果先给教师看（含「和题库已有题目是否重复」的检查结论），确认后才入库。
 */

import { h, clear, inlineMd } from '../core/dom.js';
import * as api from '../core/api.js';
import { ok, fail, info } from '../core/toast.js';
import * as U from '../core/ui.js';
import { PROBLEM_TYPE } from '../core/format.js';

const DIFF_LABEL = ['', '入门', '基础', '中等', '较难', '挑战'];

export async function openProblemGenerator({ chapters = [], chapter, onSaved } = {}) {
  let templates = [];
  try {
    templates = await api.get('/api/problems/templates');
  } catch (e) {
    /* 拉不到模板清单不影响出题，只是少一句提示 */
  }

  let difficulty = 3;
  const avoid = [];              // 本次会话里已经生成过的题（点「换一题」不再重复）
  let draft = null;
  let report = null;

  const chapterSelect = U.select(
    [{ value: '', label: '不限章节（按难度挑）' }].concat(
      (chapters || []).map((c) => ({ value: c.key, label: c.label }))
    ),
    { value: chapter || '' }
  );

  const diffBox = U.segmented(
    [1, 2, 3, 4, 5].map((d) => ({ key: String(d), label: `${d} ${DIFF_LABEL[d]}` })),
    { value: '3', onChange: (k) => { difficulty = Number(k); paintHint(); } }
  );

  const hintBox = h('div', { class: 'small muted mt8' });
  const resultBox = h('div', { class: 'mt16' });
  const runBtn = U.btn('开始生成', { tone: 'primary', icon: U.icon.spark, onClick: () => run(false) });
  const againBtn = U.btn('换一题', { tone: 'ghost', size: 'sm', icon: U.icon.refresh, onClick: () => run(true) });
  againBtn.style.display = 'none';

  function paintHint() {
    clear(hintBox);
    const key = chapterSelect.value;
    const pool = (templates || []).filter(
      (t) => (!key || t.chapter === key) && t.level[0] <= difficulty && difficulty <= t.level[1]
    );
    if (!templates.length) return;
    hintBox.appendChild(
      h('span', {},
        pool.length
          ? `该范围有 ${pool.length} 类模板可用：${pool.map((t) => t.name).join('、')}`
          : '该范围没有完全匹配的模板，系统会按最接近的难度生成。')
    );
  }
  chapterSelect.addEventListener('change', paintHint);

  async function run(again) {
    runBtn.disabled = true;
    againBtn.disabled = true;
    const label = runBtn.textContent;
    runBtn.textContent = '生成中…';
    info('正在生成题目与测试数据…');
    try {
      const r = await api.post('/api/problems/generate', {
        chapter: chapterSelect.value || undefined,
        difficulty,
        avoid,
        widen: true,
      });
      draft = r.draft;
      report = r.report;
      avoid.push(draft.gen_key);
      paintResult();
      againBtn.style.display = '';
      if (again) ok('已换一道新题');
    } catch (e) {
      fail(e.message);
    } finally {
      runBtn.disabled = false;
      againBtn.disabled = false;
      runBtn.textContent = label;
    }
  }

  function simTone(v) {
    return v >= 0.62 ? 'warn' : v >= 0.4 ? 'blue' : 'ok';
  }

  function paintResult() {
    clear(resultBox);
    if (!draft) return;
    const d = draft;
    const samples = (d.samples || []).slice(0, 2);
    const nCases = (d.test_cases || []).length;
    const sim = report ? report.max_similarity : 0;

    resultBox.appendChild(
      U.card(
        U.cardHead(d.title, {
          sub: `${PROBLEM_TYPE[d.type] || d.type} · 难度 ${d.difficulty} · ${d.gen_source || ''}`,
          actions: h('span', { class: 'row', style: { gap: '6px' } },
            U.badge(`${(d.chapter || '').replace('ch', 'Chapter ')}`, 'soft'),
            U.badge(`${nCases} 个测试点`, 'blue')),
        }),
        h('div', { class: 'row row--wrap', style: { gap: '6px', marginBottom: '10px' } },
          (d.topics || []).map((t) => U.badge(t, 'soft'))),
        h('div', { class: 'conclusion', style: { whiteSpace: 'pre-wrap' }, html: inlineMd(d.statement) }),
        h('div', { class: 'grid grid--2 mt12' },
          h('div', {}, h('b', { class: 'small' }, '输入格式'), h('p', { class: 'small' }, d.input_format)),
          h('div', {}, h('b', { class: 'small' }, '输出格式'), h('p', { class: 'small' }, d.output_format))),
        h('div', { class: 'small muted mt8', style: { whiteSpace: 'pre-wrap' }, html: inlineMd(d.constraints) }),
        h('h4', { class: 'small muted mt16 mb8' }, `样例（共 ${nCases} 个测试点，其中样例 ${samples.length} 个）`),
        ...samples.map((s, i) => h('div', { class: 'sample mt8' },
          h('div', { class: 'sample__head' }, h('span', {}, '样例 ' + (i + 1)), h('span', {}, '对学生可见')),
          h('div', { class: 'sample__body' },
            h('div', { class: 'sample__col' }, String(s.input || '').slice(0, 800)),
            h('div', { class: 'sample__col' }, String(s.output || '').slice(0, 800))))),
        U.note(
          report && report.reused
            ? `与题库已有题目《${report.closest_title || '—'}》的题面相似度 ${(sim * 100).toFixed(0)}%，`
              + '这是目前最不相似的一道，建议换个章节或难度再生成一次。'
            : `重复检查通过：与题库现有题目最高相似度 ${(sim * 100).toFixed(0)}%`
              + (report && report.closest_title ? `（最接近《${report.closest_title}》）` : '')
              + `，生成耗时 ${report ? report.elapsed_ms : '—'} ms。`,
          report && report.reused ? 'warn' : 'ok'
        ),
        h('details', { class: 'mt12' },
          h('summary', { style: { cursor: 'pointer', fontSize: '13px', color: 'var(--brand)' } },
            '查看参考程序（Python，生成测试数据用的就是它）'),
          h('div', { class: 'mt8' }, U.codeBlock(d.solution, 'python', { maxHeight: 320 })))
      )
    );

    const saveBtn = U.btn('直接入库', {
      tone: 'soft',
      onClick: async (e) => {
        const btn = e.target.closest('button');
        btn.disabled = true;
        try {
          await api.post('/api/problems', d);
          ok('题目已加入题库');
          close();
          onSaved && onSaved();
        } catch (err) {
          fail(err.message);
          btn.disabled = false;
        }
      },
    });
    const editBtn = U.btn('采用并编辑', {
      tone: 'primary',
      onClick: async () => {
        const m = await import('./problem-editor.js');
        m.openProblemEditor(d, () => { close(); onSaved && onSaved(); });
      },
    });
    resultBox.appendChild(h('div', { class: 'row mt12', style: { gap: '8px' } }, editBtn, saveBtn));
  }

  paintHint();
  const modal = U.modal('智能出题', h('div', {},
    U.note('选一个章节和难度，系统会现场生成一道可以直接评测的编程题：'
      + '题面按实际数据规模生成，测试数据的期望输出由参考程序算出；'
      + '生成后还会和题库里已有题目做比对，避免重复。', 'info'),
    h('div', { class: 'form-grid mt16' },
      U.field('章节 / 知识点', chapterSelect),
      U.field('难度', diffBox)),
    hintBox,
    h('div', { class: 'row mt16', style: { gap: '8px' } }, runBtn, againBtn),
    resultBox
  ), { width: 900 });
  const close = modal.close;
  return modal;
}
