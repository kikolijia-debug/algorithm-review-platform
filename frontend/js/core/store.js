/** 全局状态：会话、课程、元信息、主题。带 localStorage 持久化与简单订阅。 */

const KEY = 'ajp.state.v1';

const listeners = new Set();

export const state = {
  token: null,
  user: null,
  courses: [],
  courseId: null,
  meta: null,
  theme: 'light',
  sidebarCollapsed: false,
  peerPending: 0,
  noticeUnread: 0,
  demo: false,
};

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function emit() {
  for (const fn of listeners) {
    try {
      fn(state);
    } catch (e) {
      console.error(e);
    }
  }
}

export function load() {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) Object.assign(state, JSON.parse(raw));
  } catch (e) {
    /* 忽略损坏的本地状态 */
  }
  return state;
}

export function save() {
  try {
    localStorage.setItem(
      KEY,
      JSON.stringify({
        token: state.token,
        user: state.user,
        courseId: state.courseId,
        theme: state.theme,
        sidebarCollapsed: state.sidebarCollapsed,
      })
    );
  } catch (e) {
    /* 隐私模式下 localStorage 可能不可用 */
  }
}

export function setTheme(theme) {
  state.theme = theme;
  document.documentElement.dataset.theme = theme;
  save();
  emit();
}

export function reset() {
  state.token = null;
  state.user = null;
  state.courses = [];
  state.courseId = null;
  state.peerPending = 0;
  state.noticeUnread = 0;
  save();
  emit();
}

export function isTeacher() {
  return state.user && (state.user.role === 'teacher' || state.user.role === 'ta');
}
