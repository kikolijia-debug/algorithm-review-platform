/** 题目编辑器（教师端弹窗）：元数据 + 测试数据 + 评分细则 + 参考程序。 */

import { h, clear } from '../core/dom.js';
import * as api from '../core/api.js';
import { ok, fail, confirmDialog } from '../core/toast.js';
import * as U from '../core/ui.js';
import { codeEditor } from '../core/editor.js';

const TOPIC_POOL = [
  '算法基础与复杂度分析', '分治与递归', '图搜索与遍历', '贪心算法', '动态规划',
  '图优化算法', '高级数据结构', '字符串匹配', '二分与三分', '算法正确性证明',
  '复杂度实验方法', '近似与随机算法',
];

export async function openProblemEditor(problem, onSaved) {
  // 有 id 才是「改题目」；智能出题给的草稿没有 id，按新建处理
  const isEdit = !!(problem && problem.id);
  const isDraft = !isEdit && !!(problem && problem.solution);
  const draft = problem
    ? JSON.parse(JSON.stringify(problem))
    : {
        title: '', type: 'programming', difficulty: 3, topics: [], tags: [],
        statement: '', input_format: '', output_format: '', constraints: '',
        time_limit_ms: 1000, memory_limit_mb: 256, score: 100,
        samples: [], test_cases: [], rubric: [],
      };

  let cases = (draft.test_cases || []).map((c) => ({
    name: c.name || '',
    input: c.input || '',
    expected: c.expected || c.output || '',
    is_sample: !!c.is_sample,
    score: c.score == null ? 10 : c.score,
  }));
  if (!cases.length) cases = [{ name: '样例 1', input: '', expected: '', is_sample: true, score: 0 }];

  const caseBox = h('div', { class: 'case-editor' });
  const paintCases = () => {
    clear(caseBox);
    cases.forEach((c, i) => {
      const row = h(
        'div',
        { class: 'case-editor__row' },
        h('input', { class: 'input', value: c.name, placeholder: '名称', oninput: (e) => (c.name = e.target.value) }),
        h('textarea', { class: 'input input--area input--mono', placeholder: '输入数据', value: c.input, oninput: (e) => (c.input = e.target.value) }),
        h('textarea', { class: 'input input--area input--mono', placeholder: '期望输出', value: c.expected, oninput: (e) => (c.expected = e.target.value) }),
        h('div', {},
          h('input', { class: 'input', type: 'number', value: c.score, title: '分值', oninput: (e) => (c.score = Number(e.target.value)) }),
          h('label', { class: 'checkbox small', style: { marginTop: '6px' } },
            h('input', { type: 'checkbox', checked: c.is_sample, onchange: (e) => (c.is_sample = e.target.checked) }), '样例')),
        h('button', {
          class: 'btn btn--plain', title: '删除该测试点', html: U.icon.trash,
          onclick: () => { cases.splice(i, 1); paintCases(); },
        })
      );
      caseBox.appendChild(row);
    });
    if (!cases.length) caseBox.appendChild(U.note('还没有测试点，点击下方「添加测试点」。', 'warn'));
  };
  paintCases();

  const topicBox = h('div', { class: 'row row--wrap', style: { gap: '6px' } });
  const paintTopics = () => {
    clear(topicBox);
    TOPIC_POOL.forEach((t) => {
      const on = draft.topics.includes(t);
      topicBox.appendChild(
        h('button', {
          class: ['tag', on ? 'tag--soft' : ''],
          style: { cursor: 'pointer', border: '1px solid var(--line)' },
          type: 'button',
          onclick: () => {
            draft.topics = on ? draft.topics.filter((x) => x !== t) : [...draft.topics, t];
            paintTopics();
          },
        }, t)
      );
    });
  };
  paintTopics();

  const rubric = (draft.rubric && draft.rubric.length ? draft.rubric : [
    { key: 'idea', name: '算法思想与建模', max: 30, desc: '问题抽象是否准确、思路是否清晰' },
    { key: 'complexity', name: '复杂度分析', max: 25, desc: '时间/空间复杂度推导是否正确' },
    { key: 'correctness', name: '正确性论证', max: 25, desc: '证明是否完整，边界是否讨论' },
    { key: 'writing', name: '表达与规范', max: 20, desc: '结构完整、术语准确' },
  ]);

  const body = h(
    'div',
    {},
    h(
      'div',
      { class: 'form-grid' },
      U.field('题目标题', h('input', { class: 'input', value: draft.title, oninput: (e) => (draft.title = e.target.value) }), { required: true }),
      U.field('题目类型', U.select(
        [
          { value: 'programming', label: '编程题（自动评测）' },
          { value: 'analysis', label: '算法分析题（互评）' },
          { value: 'proof', label: '证明题（互评）' },
          { value: 'open', label: '开放性问答题（互评）' },
        ],
        { value: draft.type, onchange: (e) => { draft.type = e.target.value; paintSections(); } }
      )),
      U.field('难度（1-5）', h('input', { class: 'input', type: 'number', min: 1, max: 5, value: draft.difficulty, oninput: (e) => (draft.difficulty = Number(e.target.value)) })),
      U.field('总分', h('input', { class: 'input', type: 'number', value: draft.score, oninput: (e) => (draft.score = Number(e.target.value)) })),
      U.field('时间限制 (ms)', h('input', { class: 'input', type: 'number', value: draft.time_limit_ms, oninput: (e) => (draft.time_limit_ms = Number(e.target.value)) })),
      U.field('空间限制 (MB)', h('input', { class: 'input', type: 'number', value: draft.memory_limit_mb, oninput: (e) => (draft.memory_limit_mb = Number(e.target.value)) }))
    ),
    h('div', { class: 'mt16' }, U.field('知识点', topicBox)),
    h('div', { class: 'mt16' }, U.field('题目描述', U.textarea({
      value: draft.statement, style: { minHeight: '140px' }, oninput: (e) => (draft.statement = e.target.value),
      placeholder: '请写清输入、输出、约束条件与样例，并说明需要学生完成的算法分析内容。',
    }))),
    h(
      'div',
      { class: 'form-grid mt16' },
      U.field('输入格式', U.textarea({ value: draft.input_format, style: { minHeight: '80px' }, oninput: (e) => (draft.input_format = e.target.value) })),
      U.field('输出格式', U.textarea({ value: draft.output_format, style: { minHeight: '80px' }, oninput: (e) => (draft.output_format = e.target.value) }))
    ),
    h('div', { class: 'mt16' }, U.field('约束与提示', U.textarea({ value: draft.constraints, style: { minHeight: '80px' }, oninput: (e) => (draft.constraints = e.target.value) }))),
    h('section', { class: 'mt24', id: 'editor-programming' }, ...programmingSection()),
    draft.solution
      ? h('details', { class: 'mt24' },
          h('summary', { style: { cursor: 'pointer', fontSize: '13.5px', color: 'var(--brand)', fontWeight: 600 } },
            '参考程序（生成测试数据时用的就是它）'),
          h('div', { class: 'mt12' }, U.codeBlock(draft.solution, 'python', { maxHeight: 320 })))
      : null,
    h('section', { class: 'mt24', id: 'editor-rubric' }, ...rubricSection())
  );

  function programmingSection() {
    if (draft.type !== 'programming') return [];
    return [
      h('h3', { style: { fontSize: '15px', marginBottom: '8px' } }, '测试数据'),
      U.note('样例对学生可见（通常不计分），其余测试点隐藏。大测试点能区分复杂度是否达标。'),
      h('div', { class: 'mt12' }, caseBox),
      h('div', { class: 'row mt12' },
        U.btn('添加测试点', { tone: 'ghost', size: 'sm', icon: U.icon.plus, onClick: () => { cases.push({ name: '测试点 ' + (cases.length + 1), input: '', expected: '', is_sample: false, score: 10 }); paintCases(); } }),
        h('span', { class: 'small muted' }, `当前 ${cases.length} 个测试点，其中样例 ${cases.filter((c) => c.is_sample).length} 个`))
    ];
  }

  function rubricSection() {
    if (draft.type === 'programming') return [];
    return [
      h('h3', { style: { fontSize: '15px', marginBottom: '8px' } }, '互评评分细则'),
      U.note('每个维度独立打分，总和为这份评审的总分。', 'ok'),
      h('div', { class: 'mt12' }, ...rubric.map((r, i) =>
        h('div', { class: 'form-grid form-grid--3', style: { marginBottom: '10px' } },
          h('input', { class: 'input', value: r.name, placeholder: '维度名称', oninput: (e) => (r.name = e.target.value) }),
          h('input', { class: 'input', type: 'number', value: r.max, placeholder: '满分', oninput: (e) => (r.max = Number(e.target.value)) }),
          h('input', { class: 'input', value: r.desc || '', placeholder: '评分说明', oninput: (e) => (r.desc = e.target.value) }))))
    ];
  }

  function paintSections() {
    const prog = document.getElementById('editor-programming');
    const rub = document.getElementById('editor-rubric');
    if (prog) { clear(prog); programmingSection().forEach((n) => prog.appendChild(n)); }
    if (rub) { clear(rub); rubricSection().forEach((n) => rub.appendChild(n)); }
  }

  const m = U.modal(isEdit ? '编辑题目 · ' + draft.title : (isDraft ? '智能出题 · 确认后入库' : '新建题目'), body, {
    width: 900,
    actions: (close) => [
      U.btn('取消', { tone: 'ghost', onClick: close }),
      U.btn(isEdit ? '保存修改' : '创建题目', {
        tone: 'primary',
        onClick: async () => {
          if (!draft.title.trim()) return fail('请填写题目标题');
          if (draft.type === 'programming' && !cases.some((c) => c.expected)) return fail('编程题至少需要一个带期望输出的测试点');
          const payload = {
            ...draft,
            test_cases: draft.type === 'programming' ? cases : [],
            rubric: draft.type === 'programming' ? [] : rubric,
          };
          try {
            if (isEdit) await api.put('/api/problems/' + draft.id, payload);
            else await api.post('/api/problems', payload);
            ok(isEdit ? '题目已更新' : '题目已创建');
            close();
            onSaved && onSaved();
          } catch (e) {
            fail(e.message);
          }
        },
      }),
    ],
  });
  return m;
}

/** 删除题目（带二次确认） */
export async function deleteProblem(problem, onDone) {
  const yes = await confirmDialog({
    title: '删除题目',
    message: `确定删除《${problem.title}》吗？该题的所有测试数据与提交记录都会被一并删除，且不可恢复。`,
    confirmText: '删除',
    danger: true,
  });
  if (!yes) return;
  try {
    await api.del('/api/problems/' + problem.id);
    ok('题目已删除');
    onDone && onDone();
  } catch (e) {
    fail(e.message);
  }
}
