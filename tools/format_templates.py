"""把题库里的 C++ 参考实现重新排版（换行 + 缩进），提升可读性。

这些模板既是题库的「参考程序」，也会作为演示数据里的学生提交出现在
代码互评页面上，所以必须排版清楚，而不是为了省行数挤在一行里。

用法：
    python tools/format_templates.py            # 预览（不改文件）
    python tools/format_templates.py --write    # 写回 backend/problem_bank.py

排版规则（保守，不改变语义）：
* 预处理器指令与注释整行保留；
* 块级 ``{`` 换行并缩进，``}`` 回退缩进；
* 括号深度为 0 的 ``;`` 换行（``for(...)`` 里的分号不受影响）；
* 赋值初始化 ``= {...}`` 视为表达式，不换行；
* 字符串/字符字面量原样保留。
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

INDENT = "    "
HDR_TEXT = "#include <bits/stdc++.h>\nusing namespace std;\n\n"


def reformat_cpp(src: str) -> str:
    out: list[str] = []
    indent = 0
    paren = 0
    stack: list[bool] = []          # True=语句块，False=初始化列表
    i, n = 0, len(src)
    at_line_start = True
    pending_space = False

    def last_char() -> str:
        for chunk in reversed(out):
            for c in reversed(chunk):
                if not c.isspace():
                    return c
        return ""

    def emit(text: str, *, space: bool = False) -> None:
        """写入一段文本；at_line_start 时先补缩进。"""
        nonlocal at_line_start, pending_space
        if at_line_start:
            out.append(INDENT * indent)
            at_line_start = False
            pending_space = False          # 换行已经吞掉了上一处空格
        if (space or pending_space) and last_char() not in ("", "(", "[", "{", ";", ",") \
                and text[:1] not in ")]};,":
            out.append(" ")
        out.append(text)
        pending_space = False

    def newline() -> None:
        nonlocal at_line_start, pending_space
        if not at_line_start:
            out.append("\n")
        at_line_start = True
        pending_space = False

    while i < n:
        ch = src[i]
        nxt = src[i + 1] if i + 1 < n else ""

        # 行首的预处理器指令：整行保留
        if ch == "#" and at_line_start:
            j = src.find("\n", i)
            j = n if j < 0 else j
            emit(src[i:j].rstrip())
            newline()
            i = j
            continue

        # 注释
        if ch == "/" and nxt == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            emit(src[i:j].strip(), space=not at_line_start)
            newline()
            i = j
            continue
        if ch == "/" and nxt == "*":
            j = src.find("*/", i)
            j = n if j < 0 else j + 2
            emit(src[i:j])
            i = j
            continue

        # 字符串 / 字符字面量：原样保留
        if ch in "\"'":
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == ch:
                    j += 1
                    break
                j += 1
            emit(src[i:j])
            i = j
            continue

        if ch in " \t\r\n":
            pending_space = True
            i += 1
            continue

        if ch in "([":
            paren += 1
            emit("(" if ch == "(" else "[")
            i += 1
            continue
        if ch in ")]":
            paren = max(0, paren - 1)
            emit(")" if ch == ")" else "]")
            i += 1
            continue

        if ch == "{":
            # `= {..}`（初始化列表）、`, {..}`（第二个初始化项）、`push({..})`
            # 都按表达式处理，不当作语句块换行
            is_block = last_char() not in ("=", ",", "(")
            stack.append(is_block)
            if is_block:
                emit("{", space=True)
                indent += 1
                newline()
            else:
                emit("{")
            i += 1
            continue

        if ch == "}":
            is_block = stack.pop() if stack else True
            if is_block:
                indent = max(0, indent - 1)
                newline()
                emit("}")
                newline()
                if indent == 0:            # 顶层函数之间空一行
                    out.append("\n")
                    at_line_start = True
            else:
                emit("}")
            i += 1
            continue

        if ch == ";":
            emit(";")
            if paren == 0:
                newline()
            i += 1
            continue

        if ch == ",":
            emit(", " if paren == 0 else ",")
            i += 1
            continue

        # 普通字符：需要时补一个空格
        emit(ch)
        i += 1

    text = "".join(out)
    text = text.replace("using namespace std;\n", "using namespace std;\n\n")
    text = re.sub(r"[ \t]+\n", "\n", text)          # 行尾空白
    text = re.sub(r"\n{3,}", "\n\n", text)          # 连续空行
    lines = [ln.rstrip() for ln in text.split("\n")]
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines) + "\n"


def build_cpp_block(templates: dict) -> str:
    """把排好版的模板拼成 problem_bank.py 里的 CPP 字典源码。"""
    chunks = ['HDR = "#include <bits/stdc++.h>\\nusing namespace std;\\n\\n"\n\n', "CPP = {\n"]
    for key, variants in templates.items():
        chunks.append(f'"{key}": {{\n')
        for tag, code in variants.items():
            body = "HDR + " if code.startswith("#include <bits/stdc++.h>") else ""
            if body:
                code = code[len(HDR_TEXT):].lstrip("\n")
            # 关键：模板里的反斜杠（printf("...\n") 之类）必须再转义一次，
            # 否则写回源码时会被 Python 当成转义符，变成真正的换行
            safe = code.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
            chunks.append(f'  "{tag}": {body}"""{safe}""",\n')
        chunks.append("},\n")
    chunks.append("}\n")
    return "".join(chunks)


def main() -> None:
    from backend import problem_bank as PB

    formatted = {}
    for key, variants in PB.CPP.items():
        formatted[key] = {tag: reformat_cpp(code) for tag, code in variants.items()}

    if "--write" not in sys.argv:
        demo = formatted["CUT"]["ok"]
        print("--- 预览：CUT/ok ---")
        print(demo)
        print("（预览模式，未修改文件；加 --write 写回）")
        return

    src = open(PB.__file__, encoding="utf-8").read()
    cpp_at = src.index("CPP = {")
    hdr_at = src.find('HDR = "#include', 0, cpp_at)
    start = hdr_at if hdr_at != -1 else cpp_at   # 连同 HDR 一起替换，保证可重复执行
    end = src.index("\nPY = {", start)
    block = build_cpp_block(formatted)
    new_src = src[:start] + block + src[end:]
    with open(PB.__file__, "w", encoding="utf-8") as f:
        f.write(new_src)
    print(f"已重排 {sum(len(v) for v in formatted.values())} 个 C++ 模板 -> {PB.__file__}")


if __name__ == "__main__":
    main()
