/**
 * 轻量代码编辑器：行号 + 语法高亮 + Tab 缩进 + 自动括号补全。
 *
 * 实现方式是经典的「透明 textarea 叠在高亮层上」：
 *  - textarea 负责输入、选区、撤销重做（保留浏览器原生体验）；
 *  - 下方的 <pre> 负责着色渲染，两者滚动位置实时同步。
 * 这样既没有引入 Monaco/CodeMirror 的体积，又能得到接近的观感。
 */

import { h, esc } from './dom.js';

const KEYWORDS = {
  cpp: `alignas alignof asm auto bool break case catch char class const constexpr continue decltype default delete do double else enum explicit export extern false float for friend goto if inline int long mutable namespace new noexcept nullptr operator private protected public register return short signed sizeof static struct switch template this throw true try typedef typename union unsigned using virtual void volatile while cin cout endl std vector string map set pair queue stack sort max min abs scanf printf size_t`,
  c: `auto break case char const continue default do double else enum extern float for goto if inline int long register return short signed sizeof static struct switch typedef union unsigned void volatile while printf scanf NULL`,
  python: `and as assert async await break class continue def del elif else except False finally for from global if import in is lambda None nonlocal not or pass raise return True try while with yield print range len int str float list dict set tuple input map sum min max abs sorted enumerate append split join self`,
  java: `abstract assert boolean break byte case catch char class const continue default do double else enum extends final finally float for goto if implements import instanceof int interface long native new package private protected public return short static strictfp super switch synchronized this throw throws transient try void volatile while String System out println Scanner`,
  text: ``,
};

const TYPES = {
  cpp: 'int|long|short|char|float|double|bool|void|size_t|string|vector|map|set|pair|queue|stack|priority_queue|unsigned|auto',
  c: 'int|long|short|char|float|double|void|size_t|FILE',
  python: 'int|float|str|bool|list|dict|set|tuple',
  java: 'int|long|short|char|float|double|boolean|void|String|Integer|Long|List|Map|Set',
  text: '',
};

function highlight(code, lang) {
  const kw = KEYWORDS[lang] || KEYWORDS.cpp;
  const types = TYPES[lang] || TYPES.cpp;
  const out = [];
  let i = 0;
  const push = (cls, text) => out.push(cls ? `<span class="tk-${cls}">${esc(text)}</span>` : esc(text));
  while (i < code.length) {
    const rest = code.slice(i);
    let m;
    if ((m = /^(#[^\n]*)/.exec(rest)) && lang !== 'python') { push('pre', m[1]); i += m[1].length; continue; }
    if ((m = /^(\/\/[^\n]*)/.exec(rest))) { push('com', m[1]); i += m[1].length; continue; }
    if ((m = /^(#[^\n]*)/.exec(rest)) && lang === 'python') { push('com', m[1]); i += m[1].length; continue; }
    if ((m = /^\/\*[\s\S]*?\*\//.exec(rest))) { push('com', m[1]); i += m[1].length; continue; }
    if ((m = /^("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)/.exec(rest))) { push('str', m[1]); i += m[1].length; continue; }
    if ((m = /^(\d+\.?\d*(?:[eE][+-]?\d+)?[fFlLuU]*)/.exec(rest))) { push('num', m[1]); i += m[1].length; continue; }
    if ((m = /^([A-Za-z_]\w*)/.exec(rest))) {
      const word = m[1];
      if (new RegExp('^(' + types + ')$').test(word)) push('type', word);
      else if (new RegExp('(^|\\s)(' + kw.split(/\s+/).join('|') + ')(\\s|$)').test(' ' + word + ' ')) push('kw', word);
      else if (code[i + word.length] === '(') push('fn', word);
      else push('', word);
      i += word.length;
      continue;
    }
    push('op', code[i]);
    i += 1;
  }
  return out.join('');
}

const INDENT = { cpp: '    ', c: '    ', java: '    ', python: '    ', text: '  ' };

export function codeEditor({
  value = '',
  language = 'cpp',
  height = 420,
  onChange,
  readOnly = false,
  minLines = 14,
} = {}) {
  let lang = language;
  const pre = h('pre', { class: 'editor__code', 'aria-hidden': 'true' });
  const gutter = h('div', { class: 'editor__gutter' });
  const ta = h('textarea', {
    class: 'editor__input',
    spellcheck: 'false',
    autocomplete: 'off',
    autocapitalize: 'off',
    readonly: readOnly || null,
    style: { height: '100%' },
  });
  const root = h(
    'div',
    { class: 'editor', style: { height: height + 'px' } },
    gutter,
    h('div', { class: 'editor__scroll' }, pre, ta)
  );

  function paint() {
    const code = ta.value;
    const lines = code.split('\n');
    pre.innerHTML = highlight(code, lang) + '\n';
    const need = Math.max(minLines, lines.length);
    const nums = [];
    for (let i = 1; i <= need; i++) nums.push(i);
    gutter.textContent = nums.join('\n');
  }

  ta.value = value;
  ta.addEventListener('input', () => {
    paint();
    onChange && onChange(ta.value);
  });
  ta.addEventListener('scroll', () => {
    pre.scrollTop = ta.scrollTop;
    pre.scrollLeft = ta.scrollLeft;
    gutter.scrollTop = ta.scrollTop;
  });
  ta.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const start = ta.selectionStart;
      const end = ta.selectionEnd;
      if (start === end) {
        const indent = INDENT[lang] || '  ';
        ta.value = ta.value.slice(0, start) + indent + ta.value.slice(end);
        ta.selectionStart = ta.selectionEnd = start + indent.length;
      } else {
        const before = ta.value.slice(0, start);
        const sel = ta.value.slice(start, end);
        const lineStart = before.lastIndexOf('\n') + 1;
        const block = ta.value.slice(lineStart, end);
        const unindent = e.shiftKey;
        const indent = INDENT[lang] || '  ';
        const replaced = block
          .split('\n')
          .map((l) => (unindent ? l.replace(new RegExp('^' + (indent === '    ' ? ' {1,4}' : ' {1,2}')), '') : indent + l))
          .join('\n');
        ta.value = ta.value.slice(0, lineStart) + replaced + ta.value.slice(end);
        ta.selectionStart = lineStart;
        ta.selectionEnd = lineStart + replaced.length;
      }
      paint();
      onChange && onChange(ta.value);
    } else if (e.key === 'Enter') {
      const start = ta.selectionStart;
      const line = ta.value.slice(ta.value.lastIndexOf('\n', start - 1) + 1, start);
      const indent = (line.match(/^\s*/) || [''])[0];
      const extra = /[{(\[:]\s*$/.test(line) ? (INDENT[lang] || '  ') : '';
      if (indent || extra) {
        e.preventDefault();
        const insert = '\n' + indent + extra;
        ta.value = ta.value.slice(0, start) + insert + ta.value.slice(ta.selectionEnd);
        ta.selectionStart = ta.selectionEnd = start + insert.length;
        paint();
        onChange && onChange(ta.value);
      }
    } else if (e.key === ')' || e.key === '}' || e.key === ']') {
      // 覆盖式输入：光标右侧就是配对的右括号时，直接跳过而不是重复插入
      if (ta.value[ta.selectionStart] === e.key && ta.selectionStart === ta.selectionEnd) {
        e.preventDefault();
        ta.selectionStart = ta.selectionEnd = ta.selectionStart + 1;
      }
    }
  });
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's' && document.activeElement === ta) {
      e.preventDefault();
      root.__save && root.__save();
    }
  });

  paint();
  requestAnimationFrame(paint);
  root.getValue = () => ta.value;
  root.setValue = (v) => {
    ta.value = v;
    paint();
  };
  root.setLanguage = (l) => {
    lang = l;
    paint();
  };
  root.focus = () => ta.focus();
  root.el = ta;
  return root;
}
