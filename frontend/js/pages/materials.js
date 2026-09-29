/**
 * 课程资源（课件库）：按授课章节浏览课件，教师可上传 / 改归属 / 删除。
 *
 * 数据来自 /api/materials（课件列表 + 章节统计）与 /api/chapters。
 * 课件 PDF 由后端直接作为静态资源下发，点击即可在新标签页打开或下载。
 */

import { h, clear } from '../core/dom.js';
import { state, isTeacher } from '../core/store.js';
import * as api from '../core/api.js';
import * as router from '../core/router.js';
import { ok, fail, confirmDialog } from '../core/toast.js';
import * as U from '../core/ui.js';

/** 课件是静态资源，子路径部署（GitHub Pages）时也要能正确打开 */
const fileUrl = (m) => api.assetUrl(m.url);

export async function loadMaterials(ctx) {
  const courseId = (ctx && ctx.query && ctx.query.course_id) || state.courseId || undefined;
  const data = await api.get('/api/materials', courseId ? { course_id: courseId } : {});
  return data;
}

function chapterGroups(data) {
  const chapters = data.chapters || [];
  const rows = data.rows || [];
  const byChapter = new Map();
  rows.forEach((m) => {
    const key = m.chapter || 'other';
    if (!byChapter.has(key)) byChapter.set(key, []);
    byChapter.get(key).push(m);
  });
  // 以章节表为准排序，未知章节兜底放最后
  const groups = chapters
    .map((c) => ({ ...c, files: byChapter.get(c.key) || [] }))
    .filter((c) => c.files.length);
  const known = new Set(chapters.map((c) => c.key));
  byChapter.forEach((files, key) => {
    if (!known.has(key)) groups.push({ key, label: '未归类', files });
  });
  return groups;
}

export function renderMaterials(data, container, ctx) {
  const groups = chapterGroups(data);
  const teacher = isTeacher();
  const totalFiles = (data.rows || []).length;

  const head = U.pageHeader('课程资源', {
    eyebrow: 'COURSEWARE',
    sub: `${groups.length} 个章节 · ${totalFiles} 份课件 · ${data.total_mb || 0} MB`,
    actions: h(
      'div',
      { class: 'row', style: { gap: '8px' } },
      data.homepage
        ? h('a', { class: 'btn btn--ghost btn--sm', href: data.homepage, target: '_blank', rel: 'noopener' }, '课程网站')
        : null,
      teacher
        ? U.btn('上传课件', {
            tone: 'primary',
            icon: U.icon.plus,
            onClick: () => openUpload(data.chapters || [], () => router.resolve()),
          })
        : null
    ),
  });

  const body = groups.length
    ? h('div', { class: 'col', style: { gap: '16px' } },
        ...groups.map((g) => chapterCard(g, teacher, data.chapters || [], () => router.resolve())))
    : U.empty('还没有课件', teacher ? '点右上角「上传课件」把讲义放进来。' : '教师上传后会显示在这里。');

  return h(
    'div',
    {},
    head,
    teacher
      ? U.note('教师可以直接在这里维护课件：上传新讲义、替换旧文件、改标题与所属章节、'
          + '用上下箭头调整同一章内的顺序，删除则会连服务器上的文件一起移除。', 'ok')
      : null,
    h('div', { class: 'mt12' }, body)
  );
}

function chapterCard(group, teacher, chapters, refresh) {
  const problems = group.problem_count || 0;
  return U.card(
    U.cardHead(group.label || group.name || group.chapter, {
      sub: `${group.files.length} 份课件${problems ? ` · 对应 ${problems} 道题` : ''}`,
      actions: group.key
        ? h('a', {
            class: 'btn btn--ghost btn--xs',
            href: `#/problems?chapter=${group.key}`,
          }, '查看本章题目')
        : null,
    }),
    group.summary ? h('p', { class: 'small muted', style: { marginTop: '-4px' } }, group.summary) : null,
    h('div', { class: 'col', style: { gap: '8px', marginTop: '10px' } },
      ...group.files.map((m) =>
        h(
          'div',
          { class: 'list-row' },
          h(
            'div',
            { class: 'list-row__main' },
            h('div', { class: 'list-row__title' },
              h('a', { href: fileUrl(m), target: '_blank', rel: 'noopener' }, m.title),
              U.badge('PDF', 'soft')),
            h('div', { class: 'list-row__meta' },
              h('span', {}, `${m.pages || '—'} 页`),
              h('span', {}, `${m.size_mb} MB`),
              m.topics && m.topics.length ? h('span', {}, m.topics.slice(0, 3).join(' / ')) : null)
          ),
          h(
            'div',
            { class: 'list-row__side row', style: { gap: '6px' } },
            h('a', { class: 'btn btn--soft btn--xs', href: fileUrl(m), target: '_blank', rel: 'noopener' }, '打开'),
            h('a', { class: 'btn btn--plain btn--xs', href: fileUrl(m), download: m.filename }, '下载'),
            teacher
              ? U.btn('', {
                  tone: 'plain', size: 'xs', icon: U.icon.up, title: '与上一份课件交换位置',
                  onClick: () => moveMaterial(m, 'up', refresh),
                })
              : null,
            teacher
              ? U.btn('', {
                  tone: 'plain', size: 'xs', icon: U.icon.down, title: '与下一份课件交换位置',
                  onClick: () => moveMaterial(m, 'down', refresh),
                })
              : null,
            teacher
              ? U.btn('替换', { tone: 'plain', size: 'xs', onClick: () => openReplace(m, refresh) })
              : null,
            teacher
              ? U.btn('编辑', { tone: 'plain', size: 'xs', onClick: () => openEdit(m, chapters, refresh) })
              : null,
            teacher
              ? U.btn('删除', {
                  tone: 'plain',
                  size: 'xs',
                  onClick: async () => {
                    if (!(await confirmDialog({
                      title: '删除课件',
                      message: `确定删除「${m.title}」吗？文件会一并从服务器移除。`,
                      confirmText: '删除',
                    }))) return;
                    try {
                      await api.del('/api/materials/' + m.id);
                      ok('已删除');
                      refresh();
                    } catch (e) {
                      fail(e.message);
                    }
                  },
                })
              : null
          )
        )
      )
    )
  );
}

/* ------------------------------------------------------------ 排序 / 替换 */

async function moveMaterial(m, direction, refresh) {
  try {
    await api.put('/api/materials/' + m.id, { move: direction });
    refresh();
  } catch (e) {
    fail(e.message);
  }
}

function openReplace(m, refresh) {
  const fileInput = h('input', { type: 'file', class: 'input', accept: '.pdf,.ppt,.pptx,.doc,.docx,.zip,.md,.txt' });
  U.modal('替换课件文件 · ' + m.title, h('div', { class: 'col', style: { gap: '14px' } },
    U.note(`当前文件：${m.filename}（${m.size_mb} MB）。替换后标题、章节与顺序都不变，旧文件会从服务器删除。`, 'warn'),
    U.field('新的课件文件', fileInput, { required: true, hint: '支持 pdf / ppt(x) / doc(x) / zip / md / txt，单文件不超过 60 MB' })
  ), {
    width: 560,
    actions: (close) => [
      U.btn('取消', { tone: 'ghost', onClick: close }),
      U.btn('替换', {
        tone: 'primary',
        onClick: async () => {
          const file = fileInput.files && fileInput.files[0];
          if (!file) return fail('请选择要替换成的文件');
          if (file.size > 60 * 1024 * 1024) return fail('文件超过 60 MB');
          try {
            const dataUrl = await readAsDataURL(file);
            await api.post('/api/materials/' + m.id + '/file', {
              filename: file.name,
              content: String(dataUrl).split(',')[1] || '',
            });
            ok('课件已替换');
            close();
            refresh();
          } catch (e) {
            fail(e.message || '替换失败');
          }
        },
      }),
    ],
  });
}

/* ------------------------------------------------------------ 上传 / 编辑 */

function chapterOptions(chapters) {
  return chapters.map((c) => ({ value: c.key, label: c.label }));
}

function openUpload(chapters, refresh) {
  const fileInput = h('input', { type: 'file', class: 'input', accept: '.pdf,.ppt,.pptx,.doc,.docx,.zip,.md,.txt' });
  const titleInput = h('input', { class: 'input', placeholder: '例如：Chapter 5 动态规划' });
  const chapterSelect = U.select(chapterOptions(chapters), {});
  const summaryInput = h('textarea', { class: 'input input--area', placeholder: '可选：本章要点' });

  U.modal('上传课件', h('div', { class: 'col', style: { gap: '14px' } },
    U.field('课件文件', fileInput, { required: true, hint: '支持 pdf / ppt(x) / doc(x) / zip / md / txt，单文件不超过 60 MB' }),
    U.field('标题', titleInput, { required: true }),
    U.field('归属章节', chapterSelect),
    U.field('章节要点', summaryInput)
  ), {
    width: 620,
    actions: (close) => [
      U.btn('取消', { tone: 'ghost', onClick: close }),
      U.btn('上传', {
        tone: 'primary',
        onClick: async () => {
          const file = fileInput.files && fileInput.files[0];
          if (!file) return fail('请选择要上传的文件');
          if (file.size > 60 * 1024 * 1024) return fail('文件超过 60 MB');
          const title = titleInput.value.trim() || file.name;
          try {
            const dataUrl = await readAsDataURL(file);
            const base64 = String(dataUrl).split(',')[1] || '';
            await api.post('/api/materials', {
              course_id: state.courseId,
              chapter: chapterSelect.value,
              title,
              filename: file.name,
              summary: summaryInput.value.trim(),
              content: base64,
            });
            ok('课件已上传');
            close();
            refresh();
          } catch (e) {
            fail(e.message || '上传失败');
          }
        },
      }),
    ],
  });
}

function readAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error('文件读取失败'));
    reader.readAsDataURL(file);
  });
}

function openEdit(m, chapters, refresh) {
  const titleInput = h('input', { class: 'input', value: m.title });
  const chapterSelect = U.select(
    [{ value: '', label: '未归类' }].concat(
      (chapters || []).map((c) => ({ value: c.key, label: c.label }))
    ),
    { value: m.chapter || '' }
  );
  const summaryInput = h('textarea', { class: 'input input--area', value: m.summary || '' });

  U.modal('编辑课件', h('div', { class: 'col', style: { gap: '14px' } },
    U.field('标题', titleInput, { required: true }),
    U.field('归属章节', chapterSelect, { hint: '章节决定它在课件库与选题器里的分组' }),
    U.field('章节要点', summaryInput)
  ), {
    width: 560,
    actions: (close) => [
      U.btn('取消', { tone: 'ghost', onClick: close }),
      U.btn('保存', {
        tone: 'primary',
        onClick: async () => {
          if (!titleInput.value.trim()) return fail('请填写标题');
          try {
            await api.put('/api/materials/' + m.id, {
              title: titleInput.value.trim(),
              chapter: chapterSelect.value,
              summary: summaryInput.value.trim(),
            });
            ok('已保存');
            close();
            refresh();
          } catch (e) {
            fail(e.message);
          }
        },
      }),
    ],
  });
}
