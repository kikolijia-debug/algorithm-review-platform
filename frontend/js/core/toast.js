/** 顶部/右下角轻提示与确认对话框。 */

import { h, clear } from './dom.js';

function layer() {
  return document.getElementById('toasts');
}

export function toast(message, type = 'info', ms = 2600) {
  const el = h('div', { class: ['toast', 'toast--' + type] }, message);
  layer().appendChild(el);
  requestAnimationFrame(() => el.classList.add('is-in'));
  setTimeout(() => {
    el.classList.remove('is-in');
    setTimeout(() => el.remove(), 260);
  }, ms);
  return el;
}

export const ok = (m) => toast(m, 'ok');
export const warn = (m) => toast(m, 'warn');
export const fail = (m) => toast(m, 'error', 4200);
export const info = (m) => toast(m, 'info');

export function confirmDialog({ title, message, confirmText = '确认', danger = false }) {
  return new Promise((resolve) => {
    const overlay = h('div', { class: 'overlay' });
    const box = h(
      'div',
      { class: 'dialog' },
      h('h3', { class: 'dialog__title' }, title),
      h('p', { class: 'dialog__body' }, message),
      h(
        'div',
        { class: 'dialog__actions' },
        h(
          'button',
          {
            class: 'btn btn--ghost',
            onclick: () => {
              overlay.remove();
              resolve(false);
            },
          },
          '取消'
        ),
        h(
          'button',
          {
            class: ['btn', danger ? 'btn--danger' : 'btn--primary'],
            onclick: () => {
              overlay.remove();
              resolve(true);
            },
          },
          confirmText
        )
      )
    );
    overlay.appendChild(box);
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        overlay.remove();
        resolve(false);
      }
    });
    document.getElementById('overlays').appendChild(overlay);
  });
}
