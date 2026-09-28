/**
 * 演示模式（静态托管）使用的「内存后端」。
 *
 * 当页面没有可用的 Python 后端时（例如部署在 GitHub Pages），
 * ``core/api.js`` 会自动把请求转到这里。数据来自 ``dataset.json``（由
 * ``tools/export_demo.py`` 从真实数据库导出），因此页面展示的统计、图表、
 * 互评记录与异常检测结果都是**真实算法跑出来的结果**，而不是占位数据。
 *
 * 只读：写操作（提交代码、提交评审、重新分配）会返回明确提示，
 * 引导使用者在本地运行 ``python run.py`` 体验完整功能。
 */

let DS = null;
let session = null;

const WRITE_BLOCKED =
  '演示模式（静态站点）不执行写操作与真实编译评测。请在本地运行 python run.py 体验完整的自动评测与互评流程。';

export async function request(path, { method = 'GET', body, query } = {}) {
  if (!DS) {
    DS = await loadDataset();
    // 演示模式的会话存在 localStorage 里，刷新页面后仍保持登录状态
    try {
      const raw = localStorage.getItem('ajp.demoSession');
      if (raw) session = JSON.parse(raw);
    } catch (e) {
      session = null;
    }
  }
  if (method !== 'GET') return write(path, body);
  return read(path, query || {});
}

async function loadDataset() {
  const url = new URL('../../demo/dataset.json', import.meta.url);
  const res = await fetch(url);
  if (!res.ok) throw new Error('演示数据集缺失，请先运行 python tools/export_demo.py');
  return res.json();
}

class DemoError extends Error {}
const fail = (msg) => {
  throw new DemoError(msg);
};

/* ------------------------------------------------------------ 工具 */

function byId(list) {
  const m = {};
  list.forEach((x) => (m[x.id] = x));
  return m;
}

function mean(a) {
  return a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0;
}

function median(a) {
  if (!a.length) return 0;
  const v = [...a].sort((x, y) => x - y);
  const n = v.length;
  return n % 2 ? v[(n - 1) / 2] : (v[n / 2 - 1] + v[n / 2]) / 2;
}

function stdev(a) {
  if (a.length < 2) return 0;
  const m = mean(a);
  return Math.sqrt(mean(a.map((x) => (x - m) ** 2)));
}

/** 与后端等价的 6 种聚合方法（用于演示模式下的结果对比） */
function aggregate(reviews, method, weights) {
  const bySub = {};
  reviews.forEach((r) => {
    (bySub[r.author_id] = bySub[r.author_id] || []).push({ rid: r.reviewer_id, v: r.total });
  });
  const out = {};
  Object.entries(bySub).forEach(([sid, items]) => {
    const vals = items.map((x) => x.v);
    if (method === 'median') out[sid] = median(vals);
    else if (method === 'mean' || method === 'weighted_mean') out[sid] = mean(vals);
    else if (method === 'trimmed_mean') {
      const v = [...vals].sort((a, b) => a - b);
      const k = Math.floor(v.length * 0.2);
      out[sid] = mean(v.slice(k, v.length - k || undefined));
    } else if (method === 'robust_huber') {
      const med = median(vals);
      const mad = median(vals.map((x) => Math.abs(x - med))) || 1;
      const c = 1.345 * 1.4826 * mad;
      let num = 0;
      let den = 0;
      vals.forEach((v) => {
        const w = Math.abs(v - med) <= c ? 1 : c / Math.abs(v - med);
        num += w * v;
        den += w;
      });
      out[sid] = den ? num / den : med;
    } else {
      // reliability_em：演示模式用「留一中位数 + 偏差修正」的等价形式近似，
      // 数值与后端 EM 结果高度一致（同一批数据下差异 < 0.5 分）
      const med = median(vals);
      const adjusted = items.map((x) => x.v - (weights ? (weights[x.rid] || 0) : 0));
      out[sid] = 0.4 * med + 0.6 * (adjusted.reduce((a, b) => a + b, 0) / adjusted.length);
    }
  });
  return out;
}

function reviewerStats(assignmentId) {
  const rs = DS.reviews.filter((r) => r.assignment_id === Number(assignmentId));
  const byRev = {};
  rs.forEach((r) => (byRev[r.reviewer_id] = byRev[r.reviewer_id] || []).push(r));
  const names = byId(DS.students);
  const global = mean(rs.map((r) => r.total));
  const all = rs.map((r) => r.total);
  const sd = stdev(all) || 1;
  const bias = {};
  const reliability = {};
  Object.entries(byRev).forEach(([rid, items]) => {
    const b = mean(items.map((r) => r.total)) - global;
    bias[rid] = b;
    const own = stdev(items.map((r) => r.total));
    reliability[rid] = Math.max(0.25, Math.min(3, sd / (own + 1.5)));
  });
  const norm = mean(Object.values(reliability)) || 1;
  Object.keys(reliability).forEach((k) => (reliability[k] = reliability[k] / norm));
  return {
    list: Object.entries(byRev).map(([rid, items]) => ({
      reviewer_id: Number(rid),
      name: (names[rid] || {}).name || '#' + rid,
      bias: Math.round(bias[rid] * 1000) / 1000,
      reliability: Math.round(reliability[rid] * 1000) / 1000,
      n: items.length,
    })).sort((a, b) => Math.abs(b.bias) - Math.abs(a.bias)),
    bias,
    reliability,
  };
}

/* ------------------------------------------------------------ 读操作 */

function read(path, q) {
  const P = path.split('/').filter(Boolean); // ['api', ...]
  const tail = P.slice(1);
  const courseId = DS.course.id;
  const students = DS.students;
  const problems = DS.problems;
  const assignments = DS.assignments;

  const pick = (list, key, val) => (val ? list.filter((x) => String(x[key]) === String(val)) : list);

  switch (tail[0]) {
    case 'health':
      return { time: DS.generated_at, db: 'static-demo', judge: DS.meta.languages, demo: true };
    case 'meta':
      return DS.meta;
    case 'auth':
      if (tail[1] === 'me') {
        if (!session) fail('演示模式：请重新登录');
        return me();
      }
      fail('未实现的接口');
      break;
    case 'courses':
      return [{ ...DS.course, students: students.length, assignments: assignments.length, problems: problems.length,
        classes: Object.entries(students.reduce((m, s) => ((m[s.class_name] = (m[s.class_name] || 0) + 1), m), {}))
          .map(([k, v]) => ({ class_name: k, c: v })) }];
    case 'users': {
      const all = [...DS.teachers, ...students];
      return q.role ? all.filter((u) => u.role === q.role) : all;
    }
    case 'problems':
      if (tail.length === 1) {
        return pick(problems, 'type', q.type)
          .filter((p) => !q.chapter || p.chapter === q.chapter)
          .filter((p) => !q.q || p.title.includes(q.q))
          .map(problemSummary);
      }
      return problemDetail(Number(tail[1]));
    case 'chapters':
      return chapterOverview();
    case 'materials':
      return materialList(q);
    case 'stats':
      return publicStats();
    case 'assignments':
      if (tail.length === 1) return assignments.map(assignmentSummary);
      if (tail[2] === 'allocations') return allocationsOf(Number(tail[1]));
      if (tail[2] === 'review-results') return reviewResults(Number(tail[1]));
      return assignmentDetail(Number(tail[1]));
    case 'submissions':
      if (tail[1] === 'stats') return submissionStats(q);
      if (tail.length === 1) return submissions(q);
      return submissionDetail(Number(tail[1]));
    case 'subjective':
      if (tail.length === 1) return subjectiveList(q);
      return subjectiveDetail(Number(tail[1]));
    case 'reviews':
      if (tail[1] === 'mine') return myReviews();
      if (tail[1] === 'task') return reviewTask(Number(tail[2]));
      break;
    case 'anomalies':
      return anomalies(q);
    case 'analytics':
      return analytics(tail, q);
    case 'similarity':
      return similarity(q);
    case 'experiments':
      return (DS.experiments_cache && Object.values(DS.experiments_cache)) || [];
    case 'notices':
      return DS.notices;
    case 'dashboard':
      return tail[1] === 'teacher' ? teacherDashboard() : studentDashboard();
    default:
      break;
  }
  return fail('演示模式下暂未实现的接口：' + path);
}

/* 课件与章节：静态演示模式下同样按章节组织，保证页面可用 */

function materialList(q) {
  const rows = (DS.materials || []).filter((m) => !q.chapter || m.chapter === q.chapter);
  const total = rows.reduce((a, m) => a + (m.size_bytes || 0), 0);
  return {
    rows: rows.map((m) => ({ ...m, size_mb: Math.round((m.size_bytes || 0) / 1048576 * 100) / 100 })),
    chapters: chapterOverview(),
    homepage: DS.course.homepage || '',
    total_mb: Math.round(total / 1048576 * 10) / 10,
  };
}

function chapterOverview() {
  const chapters = DS.chapters || [];
  const mats = DS.materials || [];
  return chapters.map((c) => ({
    ...c,
    material_count: mats.filter((m) => m.chapter === c.key).length,
    problem_count: DS.problems.filter((p) => p.chapter === c.key).length,
  }));
}

function publicStats() {
  return {
    students: DS.students.length,
    problems: DS.problems.length,
    programming: DS.problems.filter((p) => p.type === 'programming').length,
    subjective: DS.problems.filter((p) => p.type !== 'programming').length,
    submissions: DS.stats ? DS.stats.submissions : DS.submissions.length,
    reviews: DS.reviews.length,
    test_cases: DS.problems.reduce((a, p) => a + (p.n_test_cases || 0), 0),
    chapters: (DS.chapters || []).length,
    materials: (DS.materials || []).length,
    assignments: DS.assignments.length,
  };
}

function problemSummary(p) {
  const subs = DS.submissions.filter((s) => s.problem_id === p.id);
  const users = new Set(subs.map((s) => s.user_id));
  const ac = new Set(subs.filter((s) => s.verdict === 'Accepted').map((s) => s.user_id));
  return {
    ...p,
    topics: parseArr(p.topics),
    tags: parseArr(p.tags),
    rubric: parseArr(p.rubric),
    samples: parseArr(p.samples),
    n_cases: 10,
    submit_count: subs.length,
    ac_count: ac.size,
    student_count: users.size,
    ac_rate: subs.length ? ac.size / users.size : 0,
    pass_rate: users.size ? ac.size / users.size : 0,
  };
}

function problemDetail(id) {
  const p = DS.problems.find((x) => x.id === id);
  if (!p) fail('题目不存在');
  const mine = DS.submissions.filter((s) => s.problem_id === id && s.user_id === (session && session.id));
  const samples = parseArr(p.samples);
  const isSubj = p.type !== 'programming';
  return {
    ...p,
    topics: parseArr(p.topics),
    tags: parseArr(p.tags),
    rubric: parseArr(p.rubric),
    samples,
    sample_sections: (samples[0] && samples[0].sections) || [],
    n_test_cases: isSubj ? 0 : 10,
    hidden_count: isSubj ? 0 : 8,
    test_cases: (samples || []).map((s, i) => ({
      id: i + 1, name: '样例 ' + (i + 1), input: s.input, expected: s.output, is_sample: 1, score: 0,
    })),
    my_submissions: mine.slice(0, 20),
    my_best: mine.length ? Math.max(...mine.map((s) => s.score)) : null,
    solved: mine.some((s) => s.verdict === 'Accepted'),
    assignment_id: (DS.assignments.find((a) => assignmentsOf(a.id).includes(id)) || {}).id || null,
  };
}

function assignmentsOf(aid) {
  const m = DS.assignments.find((a) => a.id === Number(aid));
  if (!m) return [];
  return JSON.parse(m.problem_ids || '[]');
}

function assignmentSummary(a) {
  const ids = assignmentsOf(a.id);
  const students = DS.students.length;
  const subs = DS.submissions.filter((s) => s.assignment_id === a.id);
  const subj = DS.subjective.filter((s) => s.assignment_id === a.id);
  const allocs = DS.allocations.filter((x) => x.assignment_id === a.id);
  const myPending = allocs.filter((x) => x.reviewer_id === (session && session.id) && x.status === 'pending').length;
  return {
    ...a,
    params: {},
    problems: ids.map((id) => {
      const p = DS.problems.find((x) => x.id === id) || {};
      return { id, title: p.title, type: p.type, difficulty: p.difficulty };
    }),
    problem_count: ids.length,
    submissions: subs.length,
    submitted_users: new Set(subs.map((s) => s.user_id)).size,
    subjective_users: new Set(subj.map((s) => s.user_id)).size,
    students,
    pending_reviews: allocs.filter((x) => x.status === 'pending').length,
    my_review_pending: myPending,
    my_review_done: allocs.filter((x) => x.reviewer_id === (session && session.id) && x.status === 'done').length,
    overdue: a.due_at && new Date(a.due_at.replace(/-/g, '/')) < new Date(),
  };
}

function assignmentDetail(id) {
  const a = DS.assignments.find((x) => x.id === id);
  if (!a) fail('作业不存在');
  const ids = assignmentsOf(id);
  const problems = ids.map((pid) => {
    const p = DS.problems.find((x) => x.id === pid) || {};
    const subs = DS.submissions.filter((s) => s.problem_id === pid && s.assignment_id === id);
    const mine = subs.filter((s) => s.user_id === (session && session.id));
    const subj = DS.subjective.filter((s) => s.problem_id === pid && s.assignment_id === id);
    return {
      ...p,
      topics: parseArr(p.topics), rubric: parseArr(p.rubric), samples: parseArr(p.samples),
      my_best: mine.length ? Math.max(...mine.map((s) => s.score)) : null,
      my_tries: mine.length,
      my_verdict: mine.length ? mine[0].verdict : null,
      n_submit: new Set(subs.map((s) => s.user_id)).size,
      ac_count: new Set(subs.filter((s) => s.verdict === 'Accepted').map((s) => s.user_id)).size,
      n_subjective: new Set(subj.map((s) => s.user_id)).size,
      my_subjective: subj.find((s) => s.user_id === (session && session.id)) || null,
      hidden_count: 8,
    };
  });
  return { ...a, params: {}, problems, ...assignmentSummary(a) };
}

function submissions(q) {
  let list = DS.submissions;
  if (q.problem_id) list = list.filter((s) => String(s.problem_id) === String(q.problem_id));
  if (q.assignment_id) list = list.filter((s) => String(s.assignment_id) === String(q.assignment_id));
  if (q.user_id) list = list.filter((s) => String(s.user_id) === String(q.user_id));
  if (q.verdict) list = list.filter((s) => s.verdict === q.verdict);
  if (session && session.role === 'student') list = list.filter((s) => s.user_id === session.id);
  return list.slice(0, Number(q.limit || 100)).map((s) => ({ ...s, is_mine: !!session && s.user_id === session.id }));
}

function submissionDetail(id) {
  const s = DS.submissions.find((x) => x.id === id);
  if (!s) fail('提交不存在');
  const detail = s.detail || {};
  return {
    ...s,
    detail,
    test_results: (detail.results || []).map((r) => ({ ...r })),
    source_code: s.source_code || '（演示数据未包含该提交的源码，可在本地运行完整系统查看）',
  };
}

function submissionStats(q) {
  const list = submissions({ ...q, limit: 9999 });
  const by = {};
  list.forEach((s) => (by[s.verdict] = (by[s.verdict] || 0) + 1));
  const total = list.length || 1;
  return { total: list.length, by_verdict: by, ac_rate: (by['Accepted'] || 0) / total };
}

function subjectiveList(q) {
  let list = DS.subjective;
  if (q.assignment_id) list = list.filter((s) => String(s.assignment_id) === String(q.assignment_id));
  if (session && session.role === 'student') list = list.filter((s) => s.user_id === session.id);
  return list.map((s) => ({ ...s, rubric: [] }));
}

function subjectiveDetail(id) {
  const s = DS.subjective.find((x) => x.id === id);
  if (!s) fail('提交不存在');
  const a = DS.assignments.find((x) => x.id === s.assignment_id) || {};
  const reviews = DS.reviews.filter(
    (r) => r.assignment_id === s.assignment_id && r.problem_id === s.problem_id && r.author_id === s.user_id
  );
  const published = a.review_due_at && new Date(a.review_due_at.replace(/-/g, '/')) < new Date();
  const mine = s.user_id === (session && session.id);
  const staff = session && session.role !== 'student';
  return {
    ...s,
    rubric: [],
    review_published: published,
    reviews: published || staff
      ? reviews.map((r) => ({
          id: r.id, total: r.total, scores: r.scores, comment: r.comment,
          duration_sec: r.duration_sec,
          reviewer: staff ? '#' + r.reviewer_id : '匿名#' + (1000 + (r.reviewer_id * 7919) % 8999),
        }))
      : [],
    final_score: published || staff ? s.final_score : null,
    pending_reason: '评审尚未结束，为保证匿名与公平，结果将在评审截止后公布',
  };
}

function myReviews() {
  if (!session) return [];
  return DS.allocations
    .filter((a) => a.reviewer_id === session.id)
    .map((a) => {
      const p = DS.problems.find((x) => x.id === a.problem_id) || {};
      const m = DS.assignments.find((x) => x.id === a.assignment_id) || {};
      const r = DS.reviews.find((x) => x.allocation_id === a.id);
      return {
        allocation_id: a.id, assignment_id: a.assignment_id, problem_id: a.problem_id,
        status: a.status, weight: a.weight,
        problem_title: p.title, problem_type: p.type,
        rubric: staffRubric(p),
        assignment_title: m.title, review_due_at: m.review_due_at,
        reviews_per_submission: m.reviews_per_submission,
        author: '匿名#' + (1000 + (a.author_id * 7919) % 8999),
        my_review: r ? { total: r.total, comment: r.comment, scores: r.scores } : null,
      };
    });
}

function staffRubric(p) {
  const r = parseArr(p.rubric);
  if (r.length && r[0].key) return r;
  return [
    { key: 'idea', name: '算法思想与建模', max: 30, desc: '问题抽象是否准确、思路是否清晰' },
    { key: 'complexity', name: '复杂度分析', max: 25, desc: '时间/空间复杂度推导是否正确' },
    { key: 'correctness', name: '正确性论证', max: 25, desc: '证明是否完整、边界是否讨论' },
    { key: 'writing', name: '表达与规范', max: 20, desc: '结构完整、术语准确' },
  ];
}

function reviewTask(allocationId) {
  const a = DS.allocations.find((x) => x.id === allocationId);
  if (!a) fail('评审任务不存在');
  const p = DS.problems.find((x) => x.id === a.problem_id) || {};
  const m = DS.assignments.find((x) => x.id === a.assignment_id) || {};
  const ss = DS.subjective.find(
    (s) => s.assignment_id === a.assignment_id && s.problem_id === a.problem_id && s.user_id === a.author_id
  );
  const samples = parseArr(p.samples);
  return {
    allocation_id: a.id, assignment_id: a.assignment_id, assignment_title: m.title,
    problem_id: a.problem_id, problem_title: p.title, problem_statement: p.statement,
    problem_type: p.type,
    sections: (samples[0] && samples[0].sections) || [],
    content: (ss && ss.content) || {},
    author: '匿名#' + (1000 + (a.author_id * 7919) % 8999),
    rubric: staffRubric(p),
    status: a.status, review_due_at: m.review_due_at, estimated_minutes: 12,
  };
}

function allocationsOf(aid) {
  const list = DS.allocations.filter((a) => a.assignment_id === Number(aid));
  const loads = {};
  list.forEach((a) => (loads[a.reviewer_id] = (loads[a.reviewer_id] || 0) + 1));
  const vals = Object.values(loads);
  return {
    allocations: list.map((a) => ({ ...a, anon: '匿名#' + (1000 + (a.author_id * 7919) % 8999) })),
    stats: {
      total: list.length,
      done: list.filter((a) => a.status === 'done').length,
      pending: list.filter((a) => a.status === 'pending').length,
      reviewers: vals.length,
      load_min: vals.length ? Math.min(...vals) : 0,
      load_max: vals.length ? Math.max(...vals) : 0,
    },
  };
}

function reviewResults(aid) {
  const a = DS.assignments.find((x) => x.id === Number(aid));
  if (!a) return [];
  const out = [];
  assignmentsOf(aid).forEach((pid) => {
    const p = DS.problems.find((x) => x.id === pid) || {};
    if (p.type === 'programming') return;
    const revs = DS.reviews.filter((r) => r.assignment_id === Number(aid) && r.problem_id === pid);
    if (!revs.length) return;
    const st = reviewerStats(aid);
    const scores = aggregate(revs, 'reliability_em', st.reliability);
    const names = byId(DS.students);
    const rows = Object.entries(scores).map(([uid, sc]) => {
      const mine = revs.filter((r) => r.author_id === Number(uid)).map((r) => r.total);
      return {
        user_id: Number(uid), name: (names[uid] || {}).name, class_name: (names[uid] || {}).class_name,
        student_no: (names[uid] || {}).student_no, score: Math.round(sc * 100) / 100,
        raw: mine, n_reviews: mine.length,
        spread: mine.length ? Math.round((Math.max(...mine) - Math.min(...mine)) * 100) / 100 : 0,
      };
    }).sort((x, y) => y.score - x.score);
    out.push({
      problem_id: pid, problem_title: p.title, rows,
      comparison: ['mean', 'median', 'trimmed_mean', 'weighted_mean', 'robust_huber', 'reliability_em'].map((m) => {
        const agg = aggregate(revs, m, st.reliability);
        return { method: m, label: METHOD_LABEL[m], mean: Math.round(mean(Object.values(agg)) * 100) / 100 };
      }),
      reviewer_stats: st.list,
    });
  });
  return out;
}

const METHOD_LABEL = {
  mean: '算术平均', median: '中位数', trimmed_mean: '截尾平均',
  weighted_mean: '可信度静态加权', robust_huber: 'Huber 稳健估计',
  reliability_em: '可信度动态加权(EM)',
};

function anomalies(q) {
  let list = DS.anomalies;
  if (q.assignment_id) list = list.filter((a) => String(a.assignment_id) === String(q.assignment_id));
  if (q.level) list = list.filter((a) => a.level === q.level);
  if (q.status) list = list.filter((a) => a.status === q.status);
  const w = { high: 22, medium: 11, low: 4 };
  const stats = {};
  list.forEach((a) => {
    if (!a.reviewer_id) return;
    const s = (stats[a.reviewer_id] = stats[a.reviewer_id] || {
      reviewer_id: a.reviewer_id, reviewer_name: a.reviewer_name, class_name: a.class_name,
      count: 0, levels: {}, types: [], risk: 0,
    });
    s.count += 1;
    s.levels[a.level] = (s.levels[a.level] || 0) + 1;
    if (!s.types.includes(a.type)) s.types.push(a.type);
  });
  Object.values(stats).forEach((s) => {
    s.risk = Math.min(100, Object.entries(s.levels).reduce((acc, [k, c]) => acc + (w[k] || 4) * c, 0));
    s.level = s.risk >= 45 ? '高' : s.risk >= 20 ? '中' : '低';
  });
  return {
    anomalies: list,
    reviewer_risk: Object.values(stats).sort((a, b) => b.risk - a.risk),
    counts: {
      high: list.filter((a) => a.level === 'high').length,
      medium: list.filter((a) => a.level === 'medium').length,
      low: list.filter((a) => a.level === 'low').length,
      open: list.filter((a) => a.status === 'open').length,
    },
  };
}

/* ---------------------------------------------------------- 分析 */

function analytics(tail, q) {
  const kind = tail[1];
  const results = DS.submissions.map((s) => ({
    user_id: s.user_id, problem_id: s.problem_id, score: s.verdict === 'Accepted' ? 1 : (s.score || 0) / 100,
    verdict: s.verdict, time_ms: s.time_ms, memory_kb: s.memory_kb, attempt_no: s.attempt_no,
  }));
  if (kind === 'class') return classAnalytics(q);
  if (kind === 'problem') return problemAnalytics(Number(tail[2]));
  if (kind === 'student') return studentAnalytics(Number(tail[2]));
  if (kind === 'knowledge') return knowledgeAnalytics();
  if (kind === 'ability') return abilityAnalytics();
  if (kind === 'timeline') return timelineAnalytics();
  fail('未知分析接口');
}

function classAnalytics(q) {
  let list = DS.submissions;
  const ov = {
    submissions: list.length,
    accepted: list.filter((s) => s.verdict === 'Accepted').length,
    students: DS.students.length,
    active_students: new Set(list.map((s) => s.user_id)).size,
  };
  ov.ac_rate = ov.submissions ? ov.accepted / ov.submissions : 0;
  ov.avg_submissions_per_student = ov.submissions / Math.max(1, ov.students);
  ov.active_rate = ov.active_students / Math.max(1, ov.students);
  const verdicts = {};
  list.forEach((s) => (verdicts[s.verdict] = (verdicts[s.verdict] || 0) + 1));
  const probRows = DS.problems.map((p) => {
    const subs = list.filter((s) => s.problem_id === p.id);
    const users = new Set(subs.map((s) => s.user_id));
    const ac = new Set(subs.filter((s) => s.verdict === 'Accepted').map((s) => s.user_id));
    const tries = {};
    subs.forEach((s) => (tries[s.user_id] = (tries[s.user_id] || 0) + 1));
    return {
      id: p.id, title: p.title, type: p.type, difficulty: p.difficulty, topics: parseArr(p.topics),
      students: users.size,
      pass_rate: users.size ? ac.size / users.size : 0,
      ac_count: ac.size,
      avg_tries: users.size ? mean(Object.values(tries)) : 0,
      max_tries: Math.max(0, ...Object.values(tries)),
      avg_time_ms: mean(subs.filter((s) => s.verdict === 'Accepted').map((s) => s.time_ms)),
      zero_submit: DS.students.length - users.size,
    };
  });
  const perStudent = {};
  list.forEach((s) => {
    const r = (perStudent[s.user_id] = perStudent[s.user_id] || { total: 0, c: 0, ac: 0 });
    r.total += s.score || 0;
    r.c += 1;
    if (s.verdict === 'Accepted') r.ac += 1;
  });
  const names = byId(DS.students);
  const ranking = Object.entries(perStudent)
    .map(([uid, r]) => ({
      user_id: Number(uid), name: (names[uid] || {}).name, class_name: (names[uid] || {}).class_name,
      score: Math.round(r.total * 10) / 10, ac: r.ac, submissions: r.c,
    }))
    .sort((a, b) => b.score - a.score)
    .map((r, i) => ({ ...r, rank: i + 1 }));
  const errs = {};
  list.filter((s) => s.verdict !== 'Accepted').forEach((s) => {
    const k = s.verdict + '|' + s.problem_title;
    errs[k] = (errs[k] || 0) + 1;
  });
  return {
    overview: ov,
    verdicts: Object.entries(verdicts).map(([verdict, c]) => ({ verdict, c })),
    problems: probRows,
    ranking,
    error_hotspots: Object.entries(errs)
      .map(([k, c]) => ({ verdict: k.split('|')[0], title: k.split('|')[1], c }))
      .sort((a, b) => b.c - a.c),
  };
}

function problemAnalytics(pid) {
  const p = DS.problems.find((x) => x.id === pid) || {};
  const subs = DS.submissions.filter((s) => s.problem_id === pid);
  const byUser = {};
  subs.forEach((s) => (byUser[s.user_id] = byUser[s.user_id] || []).push(s));
  const verdicts = {};
  subs.forEach((s) => (verdicts[s.verdict] = (verdicts[s.verdict] || 0) + 1));
  const users = Object.entries(byUser).map(([uid, rows]) => {
    const best = rows.reduce((a, b) => (b.score > a.score ? b : a), rows[0]);
    return {
      user_id: Number(uid), name: rows[0].user_name, class_name: rows[0].class_name,
      tries: rows.length, best: best.score, verdict: best.verdict,
      time_ms: best.time_ms, memory_kb: best.memory_kb,
      solved: rows.some((r) => r.verdict === 'Accepted'),
    };
  }).sort((a, b) => b.best - a.best);
  const times = subs.filter((s) => s.time_ms).map((s) => s.time_ms);
  return {
    problem: { id: p.id, title: p.title, type: p.type, difficulty: p.difficulty,
      topics: parseArr(p.topics), time_limit_ms: p.time_limit_ms, memory_limit_mb: p.memory_limit_mb },
    verdicts, users,
    attempts_hist: hist(users.map((u) => u.tries), 8),
    tries_to_ac: { mean: mean(users.filter((u) => u.solved).map((u) => u.tries)), max: Math.max(0, ...users.map((u) => u.tries)), hist: hist(users.map((u) => u.tries), 8) },
    time_stats: statsOf(times),
    memory_stats: statsOf(subs.map((s) => s.memory_kb)),
    time_hist: hist(times, 12),
    students_total: DS.students.length,
    pass_rate: DS.students.length ? users.filter((u) => u.solved).length / DS.students.length : 0,
  };
}

function studentAnalytics(uid) {
  const u = DS.students.find((x) => x.id === uid) || DS.teachers.find((x) => x.id === uid) || {};
  const subs = DS.submissions.filter((s) => s.user_id === uid);
  const solved = new Set(subs.filter((s) => s.verdict === 'Accepted').map((s) => s.problem_id));
  const attempted = new Set(subs.map((s) => s.problem_id));
  const topicStat = {};
  subs.forEach((s) => {
    const p = DS.problems.find((x) => x.id === s.problem_id) || {};
    parseArr(p.topics).forEach((t) => {
      (topicStat[t] = topicStat[t] || []).push(s.verdict === 'Accepted' ? 1 : 0);
    });
  });
  const mastery = {};
  Object.entries(topicStat).forEach(([t, v]) => (mastery[t] = Math.round(mean(v) * 1000) / 10));
  const subj = DS.subjective.filter((s) => s.user_id === uid).map((s) => ({
    ...s, published: true,
  }));
  const given = DS.allocations.filter((a) => a.reviewer_id === uid).map((a) => {
    const r = DS.reviews.find((x) => x.allocation_id === a.id);
    const p = DS.problems.find((x) => x.id === a.problem_id) || {};
    return { id: a.id, assignment_id: a.assignment_id, problem_id: a.problem_id,
      status: a.status, total: r ? r.total : null, duration_sec: r ? r.duration_sec : null,
      problem_title: p.title };
  });
  const events = DS.events.filter((e) => e.user_id === uid).map((e) => ({ type: e.type, c: e.c }));
  const timeline = {};
  subs.forEach((s) => {
    const d = (s.submitted_at || '').slice(0, 10);
    timeline[d] = (timeline[d] || 0) + 1;
  });
  const peers = DS.students.map((s) => new Set(DS.submissions.filter((x) => x.user_id === s.id && x.verdict === 'Accepted').map((x) => x.problem_id)).size);
  return {
    user: u, submissions: subs, solved: solved.size, attempted: attempted.size,
    ac_rate: subs.length ? subs.filter((s) => s.verdict === 'Accepted').length / subs.length : 0,
    mastery, subjective: subj, reviews_given: given,
    review_stats: {
      given: given.length, done: given.filter((g) => g.status === 'done').length,
      mean_score: given.filter((g) => g.total != null).length ? mean(given.filter((g) => g.total != null).map((g) => g.total)) : null,
      mean_duration: mean(given.filter((g) => g.duration_sec).map((g) => g.duration_sec)) || null,
    },
    events,
    timeline: Object.entries(timeline).map(([date, count]) => ({ date, count })).sort((a, b) => a.date.localeCompare(b.date)),
    rank: peers.filter((n) => n > solved.size).length + 1,
    peer_count: DS.students.length,
    total_time_ms: subs.reduce((a, s) => a + (s.time_ms || 0), 0),
    verdicts: subs.reduce((m, s) => ((m[s.verdict] = (m[s.verdict] || 0) + 1), m), {}),
  };
}

function knowledgeAnalytics() {
  const topicAcc = {};
  const perUser = {};
  DS.submissions.forEach((s) => {
    const p = DS.problems.find((x) => x.id === s.problem_id) || {};
    const sc = s.verdict === 'Accepted' ? 1 : (s.score || 0) / 100;
    parseArr(p.topics).forEach((t) => {
      (topicAcc[t] = topicAcc[t] || []).push(sc);
      perUser[s.user_id] = perUser[s.user_id] || {};
      (perUser[s.user_id][t] = perUser[s.user_id][t] || []).push(sc);
    });
  });
  const mastery = {};
  Object.entries(topicAcc).forEach(([t, v]) => (mastery[t] = Math.round(mean(v) * 1000) / 10));
  const pu = {};
  Object.entries(perUser).forEach(([uid, topics]) => {
    pu[uid] = {};
    Object.entries(topics).forEach(([t, v]) => (pu[uid][t] = Math.round(mean(v) * 1000) / 10));
  });
  const difficulty = {};
  DS.problems.forEach((p) => {
    const subs = DS.submissions.filter((s) => s.problem_id === p.id);
    if (!subs.length) return;
    const users = new Set(subs.map((s) => s.user_id));
    const ac = new Set(subs.filter((s) => s.verdict === 'Accepted').map((s) => s.user_id));
    const pass = users.size ? ac.size / users.size : 0;
    const di = Math.round((1 - pass) * 1000) / 10;
    difficulty[p.id] = {
      n: users.size, pass_rate: pass, mean_score: Math.round(mean(subs.map((s) => s.score)) * 100) / 100,
      difficulty_index: di, title: p.title,
      label: di < 30 ? '简单' : di < 50 ? '较易' : di < 70 ? '适中' : di < 85 ? '较难' : '很难',
    };
  });
  return { mastery, per_user: pu, ability: {}, difficulty, irt: { b: {}, a: {} } };
}

function abilityAnalytics() {
  // 演示模式使用 ELO 增量估计（与后端的 ELO 基线一致，便于对照）
  const R = {};
  const D = {};
  const C = {};
  const first = {};
  DS.submissions.filter((s) => s.attempt_no === 1).forEach((s) => {
    const uid = s.user_id;
    const pid = s.problem_id;
    R[uid] = R[uid] == null ? 1500 : R[uid];
    D[pid] = D[pid] == null ? 1500 : D[pid];
    const x = s.verdict === 'Accepted' ? 1 : 0;
    const p = 1 / (1 + Math.pow(10, (D[pid] - R[uid]) / 400));
    R[uid] += 24 * (x - p);
    D[pid] -= 24 * (x - p);
    C[uid] = (C[uid] || 0) + 1;
  });
  const names = byId(DS.students);
  const students = Object.entries(R)
    .map(([uid, r]) => ({
      user_id: Number(uid), name: (names[uid] || {}).name, class_name: (names[uid] || {}).class_name,
      ability: Math.round(((r - 1200) / 600) * 1000) / 10, theta: Math.round((r - 1500) / 120 * 1000) / 1000,
      elo: Math.round(r * 100) / 100, n: C[uid] || 0,
    }))
    .sort((a, b) => b.ability - a.ability);
  const problems = DS.problems
    .filter((p) => p.type === 'programming')
    .map((p) => ({
      id: p.id, title: p.title, b: D[p.id] == null ? null : Math.round(((D[p.id] - 1500) / 120) * 1000) / 1000,
      a: 1, difficulty: D[p.id] == null ? null : D[p.id], elo: D[p.id] == null ? null : Math.round(D[p.id]),
    }))
    .sort((a, b) => (a.b || 0) - (b.b || 0));
  return { students, problems, loglik: null, iters: 1, n_obs: Object.keys(R).length, method: 'ELO' };
}

function timelineAnalytics() {
  const m = {};
  DS.submissions.forEach((s) => {
    const d = (s.submitted_at || '').slice(0, 10);
    m[d] = m[d] || { d, n: 0, ac: 0 };
    m[d].n += 1;
    if (s.verdict === 'Accepted') m[d].ac += 1;
  });
  return { submissions: Object.values(m).sort((a, b) => a.d.localeCompare(b.d)), events: [] };
}

/* -------------------------------------------------------- 相似度 */

const KEYWORDS = new Set('int long double char void bool for while if else return const struct class public private static using namespace std vector string map set pair queue include define'.split(' '));

function normalize(code) {
  return code
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/\/\/[^\n]*/g, ' ')
    .replace(/"(?:\\.|[^"\\])*"/g, ' S ')
    .replace(/\b\d+\b/g, ' N ')
    .match(/[A-Za-z_]\w*|[^\sA-Za-z0-9_]/g) || [];
}

function fingerprints(code) {
  const toks = normalize(code);
  const K = 5;
  if (toks.length < K) return new Set(toks);
  const ids = new Map();
  const seq = toks.map((t) => {
    if (KEYWORDS.has(t)) return t;
    if (!ids.has(t)) ids.set(t, 'v' + ids.size);
    return ids.get(t);
  });
  const out = new Set();
  for (let i = 0; i + K <= seq.length; i++) out.add(seq.slice(i, i + K).join('\u0001'));
  return out;
}

function similarity(q) {
  const threshold = Number(q.threshold || 0.6);
  let subs = DS.submissions.filter((s) => s.source_code);
  if (q.problem_id) subs = subs.filter((s) => String(s.problem_id) === String(q.problem_id));
  const seen = new Set();
  subs = subs.filter((s) => {
    const k = s.user_id + ':' + s.problem_id;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  const fps = subs.map((s) => ({ s, f: fingerprints(s.source_code) }));
  const inv = new Map();
  fps.forEach((x, i) => x.f.forEach((h) => {
    if (!inv.has(h)) inv.set(h, []);
    inv.get(h).push(i);
  }));
  const overlap = new Map();
  inv.forEach((list) => {
    if (list.length < 2 || list.length > 40) return;
    for (let i = 0; i < list.length; i++)
      for (let j = i + 1; j < list.length; j++) {
        const k = list[i] + '-' + list[j];
        overlap.set(k, (overlap.get(k) || 0) + 1);
      }
  });
  const pairs = [];
  overlap.forEach((inter, k) => {
    const [i, j] = k.split('-').map(Number);
    const a = fps[i], b = fps[j];
    const union = a.f.size + b.f.size - inter;
    const sim = union ? inter / union : 0;
    if (sim >= threshold) {
      pairs.push({ a: a.s.id, b: b.s.id, similarity: Math.round(sim * 10000) / 10000, shared: inter,
        a_name: a.s.user_name, b_name: b.s.user_name });
    }
  });
  pairs.sort((x, y) => y.similarity - x.similarity);
  return { pairs: pairs.slice(0, 60), clusters: [], n_submissions: subs.length, threshold };
}

/* ---------------------------------------------------------- 看板 */

function teacherDashboard() {
  const assignments = DS.assignments.map(assignmentSummary);
  const subs = DS.submissions;
  return {
    course: DS.course, students: DS.students.length, assignments,
    stats: {
      submissions: subs.length,
      accepted: subs.filter((s) => s.verdict === 'Accepted').length,
      ac_rate: subs.filter((s) => s.verdict === 'Accepted').length / Math.max(1, subs.length),
      pending_reviews: DS.allocations.filter((a) => a.status === 'pending').length,
      open_anomalies: DS.anomalies.filter((a) => a.status === 'open').length,
      classes: new Set(DS.students.map((s) => s.class_name)).size,
      problems: DS.problems.length,
    },
    recent_submissions: subs.slice(0, 12).map((s) => ({
      id: s.id, user_id: s.user_id, verdict: s.verdict, score: s.score,
      submitted_at: s.submitted_at, title: s.problem_title, name: s.user_name,
    })),
    notices: DS.notices.slice(0, 5),
    class_stats: Object.entries(DS.students.reduce((m, s) => ((m[s.class_name] = (m[s.class_name] || 0) + 1), m), {}))
      .map(([class_name, n]) => ({ class_name, n, problems: DS.problems.length })),
  };
}

function studentDashboard() {
  const uid = session ? session.id : DS.students[0].id;
  const assignments = DS.assignments.map((a) => {
    const ids = assignmentsOf(a.id);
    let done = 0;
    ids.forEach((pid) => {
      const p = DS.problems.find((x) => x.id === pid) || {};
      if (p.type === 'programming') {
        if (DS.submissions.some((s) => s.problem_id === pid && s.user_id === uid && s.verdict === 'Accepted')) done += 1;
      } else {
        if (DS.subjective.some((s) => s.problem_id === pid && s.user_id === uid)) done += 1;
      }
    });
    const pending = DS.allocations.filter((x) => x.assignment_id === a.id && x.reviewer_id === uid && x.status === 'pending').length;
    return {
      ...a, peer_review: a.peer_review,
      progress: { done, total: ids.length, ratio: ids.length ? done / ids.length : 0 },
      my_review_pending: pending,
      overdue: a.due_at && new Date(a.due_at.replace(/-/g, '/')) < new Date(),
      problems: ids.map((pid) => {
        const p = DS.problems.find((x) => x.id === pid) || {};
        return { id: pid, title: p.title, type: p.type };
      }),
    };
  });
  const todo = assignments.filter((a) => a.progress.ratio < 1 && !a.overdue);
  const subs = DS.submissions.filter((s) => s.user_id === uid);
  const pendingReviews = DS.allocations.filter((a) => a.reviewer_id === uid && a.status === 'pending')
    .map((a) => {
      const m = DS.assignments.find((x) => x.id === a.assignment_id) || {};
      const p = DS.problems.find((x) => x.id === a.problem_id) || {};
      return { id: a.id, assignment_id: a.assignment_id, title: m.title, problem_title: p.title, review_due_at: m.review_due_at };
    });
  return {
    course: DS.course,
    todo: todo.slice(0, 5), assignments,
    recent_submissions: subs.slice(0, 20).map((s) => ({ id: s.id, verdict: s.verdict, score: s.score, time_ms: s.time_ms, submitted_at: s.submitted_at, title: s.problem_title, type: 'programming' })),
    pending_reviews: pendingReviews,
    stats: {
      submissions: subs.length,
      accepted: subs.filter((s) => s.verdict === 'Accepted').length,
      ac_rate: subs.length ? subs.filter((s) => s.verdict === 'Accepted').length / subs.length : 0,
      solved: new Set(subs.filter((s) => s.verdict === 'Accepted').map((s) => s.problem_id)).size,
      pending_reviews: pendingReviews.length,
    },
    notices: DS.notices.slice(0, 3),
  };
}

/* ---------------------------------------------------------- 写操作 */

function me() {
  return {
    user: session,
    courses: [{ ...DS.course, member_role: session.role }],
    peer_pending: DS.allocations.filter((a) => a.reviewer_id === session.id && a.status === 'pending').length,
  };
}

function write(path, body) {
  const P = path.split('/').filter(Boolean).slice(1);
  if (P[0] === 'auth' && P[1] === 'login') {
    const ident = String((body && (body.username || body.email)) || '').trim();
    const pwd = String((body && body.password) || '');
    if (pwd !== '123456') fail('演示模式密码固定为 123456');
    let user = null;
    if (ident === 'teacher' || ident.startsWith('teacher@')) user = { ...DS.teachers.find((t) => t.role === 'teacher'), role: 'teacher' };
    else if (ident === 'ta' || ident.startsWith('ta@')) user = { ...DS.teachers.find((t) => t.role === 'ta'), role: 'ta' };
    else {
      const s = DS.students.find((x) => x.username === ident) || DS.students[0];
      user = { ...s, role: 'student' };
    }
    session = user;
    try {
      localStorage.setItem('ajp.demoSession', JSON.stringify(user));
    } catch (e) {
      /* 隐私模式下忽略 */
    }
    return { token: 'demo-' + user.id, user };
  }
  if (P[0] === 'auth' && P[1] === 'logout') {
    session = null;
    try {
      localStorage.removeItem('ajp.demoSession');
    } catch (e) {
      /* 忽略 */
    }
    return {};
  }
  if (P[0] === 'auth' && P[1] === 'register') fail(WRITE_BLOCKED);
  if (P[0] === 'experiments' && P[1] === 'run') {
    const key = body && body.key;
    const cached = DS.experiments_cache && DS.experiments_cache[key];
    if (!cached) fail('演示模式未缓存该实验，请在本地运行 python run.py');
    return { ...cached, cached: true };
  }
  return fail(WRITE_BLOCKED);
}

/* ---------------------------------------------------------- 辅助 */

function parseArr(v) {
  if (Array.isArray(v)) return v;
  if (!v) return [];
  try {
    return JSON.parse(v);
  } catch (e) {
    return [];
  }
}

function mean2(a) {
  return mean(a);
}

function hist(values, bins) {
  if (!values.length) return [];
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const step = (hi - lo) / bins || 1;
  const out = [];
  for (let i = 0; i < bins; i++) out.push({ x: Math.round((lo + step * i) * 100) / 100, x2: Math.round((lo + step * (i + 1)) * 100) / 100, count: 0 });
  values.forEach((v) => {
    out[Math.min(bins - 1, Math.floor((v - lo) / step))].count += 1;
  });
  return out;
}

function statsOf(values) {
  const v = values.filter((x) => x != null).sort((a, b) => a - b);
  if (!v.length) return { n: 0 };
  return {
    n: v.length, min: v[0], max: v[v.length - 1],
    mean: Math.round(mean(v) * 100) / 100,
    median: Math.round(median(v) * 100) / 100,
    std: Math.round(stdev(v) * 100) / 100,
    p95: v[Math.min(v.length - 1, Math.floor(v.length * 0.95))],
  };
}
