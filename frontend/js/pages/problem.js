/**
 * 题目详情页（学生/教师共用）：
 *  - 编程题：左侧题面与样例，右侧代码编辑器 + 运行/提交 + 逐测试点评测结果；
 *  - 主观题：左侧题面，右侧分节作答编辑器 + 提交状态与互评结果。
 */

import { h, clear } from '../core/dom.js';
import { state, isTeacher } from '../core/store.js';
import * as api from '../core/api.js';
import * as router from '../core/router.js';
import { ok, fail, info } from '../core/toast.js';
import * as U from '../core/ui.js';
import * as C from '../core/charts.js';
import { codeEditor } from '../core/editor.js';
import { PROBLEM_TYPE, VERDICT_MEANING, METHOD_LABEL } from '../core/format.js';

const TEMPLATES = {
  cpp: `#include <bits/stdc++.h>
using namespace std;

int main() {
    // 在此实现你的算法

    return 0;
}
`,
  c: `#include <stdio.h>

int main() {
    // 在此实现你的算法

    return 0;
}
`,
  python: `import sys

def main():
    data = sys.stdin.read().split()
    # 在此实现你的算法

main()
`,
  java: `import java.util.*;

public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        // 在此实现你的算法
    }
}
`,
};

export function renderProblem({ problem, meta }, container) {
  const isProg = problem.type === 'programming';
  const head = U.pageHeader(problem.title, {
    eyebrow: 'PROBLEM #' + problem.id,
    sub: `${PROBLEM_TYPE[problem.type] || problem.type} · 难度 ${'★'.repeat(Math.min(5, problem.difficulty))}`,
    actions: [
      U.badge(problem.solved ? '已解决' : '未解决', problem.solved ? 'ok' : 'neutral'),
      h('a', { class: 'btn btn--ghost btn--sm', href: '#/problems' }, '返回题库'),
      isTeacher() ? U.btn('编辑', { tone: 'soft', size: 'sm', onClick: () => import('./problem-editor.js').then((m) => m.openProblemEditor(problem, () => router.resolve())) }) : null,
    ],
  });

  const statement = h(
    'div',
    { class: 'card statement' },
    h('h1', {}, problem.title),
    h('div', { class: 'row row--wrap mb16' },
      U.badge(PROBLEM_TYPE[problem.type] || problem.type, 'brand'),
      U.badge('难度 ' + '★'.repeat(Math.min(5, problem.difficulty)), 'neutral'),
      ...(problem.topics || []).map((t) => U.badge(t, 'blue'))),
    section('题目描述', problem.statement),
    problem.input_format ? section('输入格式', problem.input_format) : null,
    problem.output_format ? section('输出格式', problem.output_format) : null,
    problem.constraints ? section('数据范围与提示', problem.constraints) : null,
    isProg && (problem.test_cases || []).length
      ? h('section', {},
          h('h4', {}, '样例'),
          ...(problem.test_cases || []).map((c, i) =>
            h('div', { class: 'sample' },
              h('div', { class: 'sample__head' }, h('span', {}, c.name || '样例 ' + (i + 1)), h('span', {}, `分值 ${c.score || 0}`)),
              h('div', { class: 'sample__body' },
                h('div', { class: 'sample__col' }, String(c.input || '').slice(0, 2000)),
                h('div', { class: 'sample__col' }, String(c.expected || '').slice(0, 2000))))))
      : null,
    isProg
      ? h('section', {},
          h('h4', {}, '评测信息'),
          U.kv([
            ['时间限制', problem.time_limit_ms + ' ms'],
            ['空间限制', problem.memory_limit_mb + ' MB'],
            ['测试点', `${problem.n_test_cases} 个（其中样例 ${(problem.test_cases || []).length} 个）`],
            ['我的提交', `${(problem.my_submissions || []).length} 次${problem.my_best != null ? `，最高 ${problem.my_best} 分` : ''}`],
          ]))
      : null
  );

  const right = isProg ? programmingPane(problem, meta) : subjectivePane(problem);
  return h('div', {}, head, h('div', { class: 'problem-layout' }, statement, right));
}

function section(title, body) {
  return h('section', {}, h('h4', {}, title), h('div', { class: 'prose' }, body || '—'));
}

/* --------------------------------------------------------- 编程题面板 */

function programmingPane(problem, meta) {
  const langs = (meta.languages || []).filter((l) => l.available);
  let lang = langs[0] ? langs[0].key : 'cpp';
  let lastResult = null;

  const editor = codeEditor({ value: TEMPLATES[lang], language: lang, height: 400 });
  const resultBox = h('div', {});

  const submitBtn = U.btn('提交评测', { tone: 'primary', icon: U.icon.send, onClick: () => doSubmit() });
  const runBtn = U.btn('运行样例', { tone: 'ghost', icon: U.icon.play, onClick: () => doRun() });
  const status = h('div', { class: 'editor-status' });

  function setStatus(text) {
    clear(status);
    if (text) status.appendChild(h('span', { class: 'row', style: { gap: '6px' } }, h('span', { class: 'spinner' }), text));
  }

  async function doRun() {
    runBtn.disabled = true;
    setStatus('正在编译并运行样例…');
    try {
      const r = await api.post('/api/run', {
        problem_id: problem.id, language: lang, source_code: editor.getValue(),
      });
      lastResult = r;
      renderResult(resultBox, r, { preview: true });
    } catch (e) {
      fail(e.message);
    } finally {
      runBtn.disabled = false;
      setStatus('');
    }
  }

  async function doSubmit() {
    submitBtn.disabled = true;
    setStatus('正在评测全部测试点…');
    try {
      const r = await api.post('/api/submissions', {
        problem_id: problem.id, language: lang, source_code: editor.getValue(),
        assignment_id: problem.assignment_id || null,
      });
      lastResult = r;
      renderResult(resultBox, r, {});
      if (r.verdict === 'Accepted') ok(`恭喜！全部 ${r.total_cases} 个测试点通过`);
      else fail(`${r.verdict}：${VERDICT_MEANING[r.verdict] || ''}`);
    } catch (e) {
      fail(e.message);
    } finally {
      submitBtn.disabled = false;
      setStatus('');
    }
  }

  const langBar = U.segmented(
    langs.map((l) => ({ key: l.key, label: l.name })),
    {
      value: lang,
      onChange: (k) => {
        lang = k;
        editor.setLanguage(k);
        if (!editor.getValue().trim() || Object.values(TEMPLATES).some((t) => t === editor.getValue())) {
          editor.setValue(TEMPLATES[k] || '');
        }
      },
    }
  );

  const saved = localStorage.getItem('ajp.code.' + problem.id);
  if (saved) editor.setValue(saved);
  editor.addEventListener('input', () => {});
  const persist = () => localStorage.setItem('ajp.code.' + problem.id, editor.getValue());
  editor.el && editor.el.addEventListener('input', persist);

  return h(
    'div',
    { class: 'col', style: { gap: '14px' } },
    U.card(
      h(
        'div',
        { class: 'editor-toolbar' },
        langBar,
        h('div', { class: 'grow' }),
        U.btn('重置模板', { tone: 'plain', size: 'sm', onClick: () => editor.setValue(TEMPLATES[lang] || '') }),
        runBtn,
        submitBtn
      ),
      editor,
      status,
      h('div', { class: 'editor-status' },
        h('span', {}, `时限 ${problem.time_limit_ms} ms`),
        h('span', {}, `空间 ${problem.memory_limit_mb} MB`),
        h('span', {}, '代码会自动保存在本地浏览器'))
    ),
    resultBox,
    (problem.my_submissions || []).length
      ? U.card(
          U.cardHead('我的历史提交', { sub: `共 ${problem.my_submissions.length} 条` }),
          U.table(
            [
              { title: '时间', render: (s) => U.fmtDate(s.submitted_at) },
              { title: '判定', render: (s) => U.verdictBadge(s.verdict) },
              { title: '得分', class: 'num', render: (s) => (s.score == null ? '—' : s.score) },
              { title: '耗时', class: 'num', render: (s) => U.fmtTime(s.time_ms) },
              { title: '', render: (s) => h('a', { class: 'btn btn--plain btn--xs', href: `#/student/submissions/${s.id}` }, '详情') },
            ],
            problem.my_submissions,
            { dense: true }
          )
        )
      : null
  );
}

function renderResult(box, r, { preview }) {
  clear(box);
  const tone = r.verdict === 'Accepted' ? 'ok' : r.verdict === 'Time Limit Exceeded' ? 'warn' : 'danger';
  const results = r.results || [];
  box.appendChild(
    U.card(
      h(
        'div',
        { class: 'row', style: { marginBottom: '10px' } },
        h('span', { class: ['result-panel__verdict', 'result-panel__verdict--' + tone] }, r.verdict),
        h('span', { class: 'muted small' }, preview ? '样例运行结果（不计入成绩）' : VERDICT_MEANING[r.verdict] || ''),
        h('div', { class: 'grow' }),
        h('span', { class: 'small muted' }, `通过与总数 ${r.passed || 0}/${r.total_cases || results.length}`)
      ),
      h(
        'div',
        { class: 'stat-row mb12' },
        U.stat(U.fmtTime(r.time_ms), '最长用时', { tone: 'brand' }),
        U.stat(U.fmtMem(r.memory_kb), '峰值内存', { tone: 'blue' }),
        U.stat(r.score == null ? '—' : r.score, '得分', { tone: tone === 'ok' ? 'ok' : 'warn' })
      ),
      r.compile_message ? U.note('编译告警：' + r.compile_message.slice(0, 300), 'warn') : null,
      (r.warnings || []).length
        ? U.note('静态检查提示：代码中出现了 ' + r.warnings.join('、') + '。教学环境仅做资源限制，生产环境的评测沙箱应使用容器隔离。', 'warn')
        : null,
      results.length
        ? h('div', { class: 'mt12' }, ...results.map((c) =>
            h('div', { class: 'case-line' },
              U.verdictBadge(c.verdict),
              h('span', { class: 'case-line__name' }, c.name),
              h('span', { class: 'case-line__io' }, `${U.fmtTime(c.time_ms)} · ${U.fmtMem(c.memory_kb)}`))))
        : null,
      results.some((c) => c.verdict !== 'AC')
        ? h('details', { class: 'mt12' },
            h('summary', { style: { cursor: 'pointer', fontSize: '13px', color: 'var(--brand)' } }, '查看第一个失败测试点的输入/输出对比'),
            (() => {
              const c = results.find((x) => x.verdict !== 'AC');
              const tc = (c && (c.expected || c.actual)) ? c : null;
              return tc
                ? h('div', { class: 'sample mt8' },
                    h('div', { class: 'sample__head' }, h('span', {}, c.name), h('span', {}, c.message || '')),
                    h('div', { class: 'sample__body' },
                      h('div', { class: 'sample__col' }, '期望输出：\n' + String(c.expected || '').slice(0, 800)),
                      h('div', { class: 'sample__col' }, '实际输出：\n' + String(c.actual || '').slice(0, 800))))
                : U.note('该判定与输出无关（例如超时或运行错误），请关注上方的提示。');
            })())
        : null
    )
  );
}

/* --------------------------------------------------------- 主观题面板 */

function subjectivePane(problem) {
  const sections = (problem.samples && problem.samples[0] && problem.samples[0].sections) || [];
  const existing = problem.my_subjective;
  const inputs = {};
  const editorBox = h('div', { class: 'col', style: { gap: '12px' } });
  const fields = sections.length
    ? sections
    : [
        { key: 'answer', name: '作答内容', hint: '请完整写出算法思路、复杂度分析与正确性论证' },
      ];
  fields.forEach((sec) =>
    editorBox.appendChild(
      U.field(sec.name, U.textarea({
        placeholder: sec.hint || '请分点作答…',
        style: { minHeight: '150px' },
        oninput: (e) => (inputs[sec.key] = e.target.value),
      }), { hint: sec.hint })
    )
  );

  const submit = U.btn(existing ? '更新提交' : '提交作业', {
    tone: 'primary',
    icon: U.icon.send,
    onClick: async () => {
      const content = {};
      fields.forEach((f) => (content[f.key] = inputs[f.key] || ''));
      const total = Object.values(content).join('').length;
      if (total < 120) return fail('作答内容过短，请至少写 120 个字符（包含思路、复杂度与正确性说明）');
      submit.disabled = true;
      try {
        await api.post('/api/subjective', {
          assignment_id: problem.assignment_id || (problem.assignment_ids || [])[0],
          problem_id: problem.id,
          content,
        });
        ok('已提交，系统将在互评阶段匿名分配给你的同学');
        router.resolve();
      } catch (e) {
        fail(e.message);
      } finally {
        submit.disabled = false;
      }
    },
  });

  const tips = U.card(
    U.cardHead('评分维度', { sub: '互评者会按这些维度逐项打分' }),
    rubricItems(problem).length
      ? h('div', { class: 'score-list' }, ...rubricItems(problem).map((r) =>
          h('div', { class: 'rubric-item' },
            h('div', { class: 'rubric-item__head' },
              h('span', { class: 'rubric-item__name' }, r.name),
              h('span', { class: 'rubric-item__score' }, r.max + ' 分')),
            h('p', { class: 'rubric-item__desc' }, r.desc || ''))))
      : U.note('教师尚未配置评分细则，将使用平台默认细则（思路 30 / 复杂度 25 / 正确性 25 / 表达 20）。')
  );

  return h(
    'div',
    { class: 'col', style: { gap: '14px' } },
    U.card(
      U.cardHead(existing ? '修改作答' : '在线作答', {
        sub: '提交后会被匿名分配给其他同学评审，请务必写清推导过程',
        actions: existing ? U.badge('已提交 · ' + (existing.status === 'done' ? '评审已完成' : '评审中'), existing.status === 'done' ? 'ok' : 'warn') : null,
      }),
      editorBox,
      h('div', { class: 'row mt16' },
        submit,
        h('span', { class: 'small muted' }, '建议 400-1200 字，包含伪代码与复杂度推导'))
    ),
    tips
  );
}

/** 题目的 rubric 字段对主观题存的是「分节定义」，需要兼容两种结构。 */
function rubricItems(problem) {
  const raw = problem.rubric || [];
  if (raw.length && raw[0] && raw[0].key) return raw;
  return [
    { key: 'idea', name: '算法思想与建模', max: 30, desc: '问题抽象是否准确、思路是否清晰' },
    { key: 'complexity', name: '复杂度分析', max: 25, desc: '时间/空间复杂度推导是否正确' },
    { key: 'correctness', name: '正确性论证', max: 25, desc: '证明是否完整、边界是否讨论' },
    { key: 'writing', name: '表达与规范', max: 20, desc: '结构完整、术语准确' },
  ];
}
