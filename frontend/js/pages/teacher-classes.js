/**
 * 教师端「班级管理」：新建 / 重命名 / 删除班级，以及班级成员的增删查看。
 *
 * 删除班级时可以选择「学生变为未分班」或「先转入另一个班级」，
 * 避免误删导致学生记录丢失。
 */

import { h, clear } from '../core/dom.js';
import { state } from '../core/store.js';
import * as api from '../core/api.js';
import * as router from '../core/router.js';
import { ok, fail, confirmDialog } from '../core/toast.js';
import * as U from '../core/ui.js';

export async function loadClasses() {
  const [classes, unassigned, courses] = await Promise.all([
    api.get('/api/classes'),
    api.get('/api/classes/unassigned').catch(() => []),
    api.get('/api/courses'),
  ]);
  const stats = await api.get('/api/submissions/stats/overview').catch(() => null);
  return { classes, unassigned, courses, stats };
}

export function renderClasses({ classes, unassigned, courses, stats }) {
  const courseId = state.courseId || (courses[0] && courses[0].id);
  const totalStudents = classes.reduce((a, c) => a + (c.member_count || 0), 0) + (unassigned || []).length;

  const refresh = () => router.resolve();

  const head = U.pageHeader('班级管理', {
    eyebrow: 'CLASSES',
    sub: '新建、重命名、删除班级，管理班级成员。',
    actions: U.btn('新建班级', { tone: 'primary', icon: U.icon.plus, onClick: () => openClassEditor(null, courseId, refresh) }),
  });

  const overview = h(
    'div',
    { class: 'stat-row mb16' },
    U.stat(classes.length, '班级数'),
    U.stat(totalStudents, '学生总数', { tone: 'blue' }),
    U.stat((unassigned || []).length, '未分班', { tone: unassigned && unassigned.length ? 'warn' : 'ok' }),
    U.stat(stats ? Math.round((stats.ac_rate || 0) * 100) + '%' : '—', '整体通过率', { tone: 'brand' })
  );

  const cards = classes.length
    ? h('div', { class: 'grid grid--auto' }, ...classes.map((c) => classCard(c, classes, courseId, refresh)))
    : U.empty('还没有班级', '点右上角「新建班级」创建第一个班级，然后把学生分配进去。');

  const unassignedBox = (unassigned || []).length
    ? U.card(
        U.cardHead('未分班学生', {
          sub: `${unassigned.length} 人`,
          actions: U.btn('批量分配', {
            tone: 'soft', size: 'sm',
            onClick: () => openAddStudents(null, classes, unassigned, refresh),
          }),
        }),
        h('div', { class: 'row row--wrap', style: { gap: '8px' } },
          ...unassigned.slice(0, 40).map((s) =>
            h('span', { class: 'badge' }, s.name + (s.student_no ? ' · ' + s.student_no : '')))),
        unassigned.length > 40 ? h('p', { class: 'small muted mt8' }, `还有 ${unassigned.length - 40} 人未显示`) : null
      )
    : null;

  return h('div', {}, head, overview, cards, unassignedBox ? h('div', { class: 'mt16' }, unassignedBox) : null);
}

function classCard(c, allClasses, courseId, refresh) {
  const rate = Math.round((c.ac_rate || 0) * 100);
  return h(
    'div',
    { class: 'card problem-card' },
    h(
      'div',
      { class: 'problem-card__top' },
      h('div', {}, h('div', { class: 'problem-card__title' }, c.name)),
      U.badge(`${c.member_count} 人`, c.member_count ? 'brand' : 'neutral')
    ),
    c.description ? h('div', { class: 'small muted' }, c.description) : null,
    h(
      'div',
      { class: 'problem-card__stats' },
      h('span', {}, `通过率 ${rate}%`),
      h('span', {}, `有提交 ${c.active_count} 人`),
      h('span', {}, `提交 ${c.total_submissions} 次`)
    ),
    U.meter(rate, { tone: rate >= 70 ? 'ok' : rate >= 40 ? 'brand' : 'warn', showValue: false }),
    h(
      'div',
      { class: 'problem-card__foot' },
      h(
        'button',
        {
          class: 'btn btn--plain btn--xs',
          title: '点击复制邀请码',
          onclick: async () => {
            if (!c.invite_code) return;
            try {
              await navigator.clipboard.writeText(c.invite_code);
              ok('邀请码已复制：' + c.invite_code);
            } catch (e) {
              fail('浏览器拒绝了剪贴板访问，请手动复制：' + c.invite_code);
            }
          },
        },
        '邀请码 ' + (c.invite_code || '—')
      ),
      h(
        'div',
        { class: 'row', style: { gap: '6px' } },
        U.btn('成员', { tone: 'soft', size: 'xs', onClick: () => openMembers(c, allClasses, refresh) }),
        U.btn('改名', { tone: 'plain', size: 'xs', onClick: () => openClassEditor(c, courseId, refresh) }),
        U.btn('删除', { tone: 'plain', size: 'xs', onClick: () => deleteClass(c, allClasses, refresh) })
      )
    )
  );
}

/* ------------------------------------------------------------ 新建 / 重命名 */

function openClassEditor(cls, courseId, onSaved) {
  const isEdit = !!cls;
  const draft = {
    name: cls ? cls.name : '',
    description: cls ? cls.description || '' : '',
    invite_code: cls ? cls.invite_code || '' : '',
  };
  U.modal(
    isEdit ? '编辑班级 · ' + cls.name : '新建班级',
    h(
      'div',
      { class: 'col', style: { gap: '14px' } },
      U.field('班级名称', h('input', {
        class: 'input', value: draft.name, placeholder: '例如：算法2026级3班',
        oninput: (e) => (draft.name = e.target.value),
      }), { required: true }),
      U.field('说明（可选）', h('input', {
        class: 'input', value: draft.description, placeholder: '例如：每周三下午 3-4 节',
        oninput: (e) => (draft.description = e.target.value),
      })),
      U.field('邀请码', h('input', {
        class: 'input', value: draft.invite_code, placeholder: '留空则自动生成',
        oninput: (e) => (draft.invite_code = e.target.value.toUpperCase()),
      }), { hint: '学生注册时填写该邀请码会自动加入本班' })
    ),
    {
      width: 520,
      actions: (close) => [
        U.btn('取消', { tone: 'ghost', onClick: close }),
        U.btn(isEdit ? '保存' : '创建', {
          tone: 'primary',
          onClick: async () => {
            if (!draft.name.trim()) return fail('请填写班级名称');
            try {
              if (isEdit) await api.put('/api/classes/' + cls.id, draft);
              else await api.post('/api/classes', { course_id: courseId, ...draft });
              ok(isEdit ? '班级已更新' : '班级已创建');
              close();
              onSaved();
            } catch (e) {
              fail(e.message);
            }
          },
        }),
      ],
    }
  );
}

/* ------------------------------------------------------------------ 删除 */

async function deleteClass(cls, allClasses, onDone) {
  const others = allClasses.filter((x) => x.id !== cls.id);
  let mode = 'unassign';
  let target = others.length ? others[0].id : 0;

  const targetSel = U.select(others.map((x) => ({ value: x.id, label: x.name })), {
    value: target, onchange: (e) => (target = Number(e.target.value)),
  });
  const targetBox = h('div', {}, U.field('转入班级', targetSel));
  targetBox.style.display = 'none';

  const radioUnassign = h('input', {
    type: 'radio', name: 'delmode', checked: true,
    onchange: () => { mode = 'unassign'; targetBox.style.display = 'none'; },
  });
  const radioMove = h('input', {
    type: 'radio', name: 'delmode',
    onchange: () => { mode = 'move'; targetBox.style.display = others.length ? '' : 'none'; },
  });

  U.modal(
    '删除班级 · ' + cls.name,
    h(
      'div',
      { class: 'col', style: { gap: '12px' } },
      U.note(
        `该班有 ${cls.member_count} 名学生。删除班级后，学生记录不会被删除，请选择他们的去向。`,
        'warn'
      ),
      h('label', { class: 'row', style: { gap: '8px', cursor: 'pointer' } }, radioUnassign,
        h('span', {}, '学生变为「未分班」')),
      others.length
        ? h('label', { class: 'row', style: { gap: '8px', cursor: 'pointer' } }, radioMove,
            h('span', {}, '先转移到其它班级'))
        : h('p', { class: 'small muted' }, '（没有其它班级可转移）'),
      targetBox
    ),
    {
      width: 520,
      actions: (close) => [
        U.btn('取消', { tone: 'ghost', onClick: close }),
        U.btn('确认删除', {
          tone: 'danger',
          onClick: async () => {
            if (mode === 'move' && !target) return fail('请选择目标班级');
            try {
              const q = mode === 'move' ? `?mode=move&target_id=${target}` : '';
              const r = await api.del(`/api/classes/${cls.id}${q}`);
              ok(`已删除「${cls.name}」，${r.students_affected} 名学生` + (mode === 'move' ? '已转入目标班级' : '变为未分班'));
              close();
              onDone();
            } catch (e) {
              fail(e.message);
            }
          },
        }),
      ],
    }
  );
}

/* ------------------------------------------------------------ 成员管理 */

async function openMembers(cls, allClasses, onChanged) {
  const data = await api.get(`/api/classes/${cls.id}/students`);
  const box = h('div');
  const drawer = U.drawer(
    `${cls.name} · ${data.students.length} 名学生`,
    box,
    { width: 680 }
  );

  const paint = () => {
    clear(box);
    box.appendChild(
      h(
        'div',
        { class: 'row mb16' },
        U.btn('添加学生', {
          tone: 'primary', size: 'sm', icon: U.icon.plus,
          onClick: async () => {
            const [unassigned, all] = await Promise.all([
              api.get('/api/classes/unassigned'),
              api.get('/api/classes'),
            ]);
            const others = all.filter((c) => c.id !== cls.id);
            const allStudents = await api.get('/api/users?role=student');
            const inOther = allStudents.filter((s) => !unassigned.some((u) => u.id === s.id));
            openAddStudents(cls, others, [...unassigned, ...inOther.filter((s) =>
              !data.students.some((d) => d.id === s.id))], async () => {
              drawer.close();
              await openMembers(cls, allClasses, onChanged);
            });
          },
        }),
        h('span', { class: 'small muted' }, '从其它班级或未分班学生中选择')
      )
    );
    box.appendChild(
      U.table(
        [
          { title: '学号', width: '110px', render: (s) => h('span', { class: 'mono small' }, s.student_no || '—') },
          { title: '姓名', render: (s) => h('b', {}, s.name) },
          { title: '提交', width: '80px', class: 'num', render: (s) => s.submissions },
          { title: '已解决', width: '90px', class: 'num', render: (s) => s.solved },
          { title: '最近登录', width: '150px', render: (s) => (s.last_login ? U.timeAgo(s.last_login) : '从未') },
          {
            title: '', width: '90px',
            render: (s) => U.btn('移出', {
              tone: 'plain', size: 'xs',
              onClick: async () => {
                try {
                  await api.del(`/api/classes/${cls.id}/students/${s.id}`);
                  ok(`${s.name} 已移出班级`);
                  data.students = data.students.filter((x) => x.id !== s.id);
                  paint();
                  onChanged();
                } catch (e) {
                  fail(e.message);
                }
              },
            }),
          },
        ],
        data.students,
        { dense: true, empty: '这个班还没有学生，点上方「添加学生」' }
      )
    );
  };
  paint();
}

function openAddStudents(targetClass, allClasses, candidates, onDone) {
  let classId = targetClass ? targetClass.id : (allClasses[0] && allClasses[0].id);
  const chosen = new Set();
  const listBox = h('div', { style: { maxHeight: '320px', overflowY: 'auto' } });

  const paint = () => {
    clear(listBox);
    if (!candidates.length) {
      listBox.appendChild(U.empty('没有可分配的学生', '所有学生都已在班级中。'));
      return;
    }
    candidates.forEach((s) =>
      listBox.appendChild(
        h('label', { class: 'list-row', style: { cursor: 'pointer', marginBottom: '6px' } },
          h('input', {
            type: 'checkbox',
            onchange: (e) => (e.target.checked ? chosen.add(s.id) : chosen.delete(s.id)),
          }),
          h('div', { class: 'list-row__main' },
            h('div', { class: 'list-row__title' }, s.name),
            h('div', { class: 'list-row__meta' },
              h('span', {}, s.student_no || '无学号'),
              h('span', {}, s.class_name || '未分班'))))
      )
    );
  };
  paint();

  U.modal(
    '添加学生到班级',
    h(
      'div',
      { class: 'col', style: { gap: '12px' } },
      U.field('目标班级', U.select(
        allClasses.map((c) => ({ value: c.id, label: `${c.name}（${c.member_count} 人）` })),
        { value: classId, onchange: (e) => (classId = Number(e.target.value)) }
      )),
      h('div', { class: 'row between' },
        h('span', { class: 'small muted' }, `可选学生 ${candidates.length} 人`),
        U.btn('全选', { tone: 'plain', size: 'xs', onClick: () => {
          candidates.forEach((s) => chosen.add(s.id));
          listBox.querySelectorAll('input[type=checkbox]').forEach((el) => (el.checked = true));
        } })),
      listBox
    ),
    {
      width: 620,
      actions: (close) => [
        U.btn('取消', { tone: 'ghost', onClick: close }),
        U.btn('加入班级', {
          tone: 'primary',
          onClick: async () => {
            if (!chosen.size) return fail('请至少选择一名学生');
            if (!classId) return fail('请选择目标班级');
            try {
              const r = await api.post(`/api/classes/${classId}/students`, { user_ids: [...chosen] });
              ok(`已把 ${r.added} 名学生加入班级`);
              close();
              onDone && onDone();
            } catch (e) {
              fail(e.message);
            }
          },
        }),
      ],
    }
  );
}
