"""自动评测引擎：编译、运行、限时限内存、判定与复杂度曲线拟合。

支持语言：C++17、C11、Python 3（自动探测本机编译器，缺失时给出明确提示）。

判定流程
--------
1. 写入独立临时工作目录（每次提交一个目录，互不干扰）；
2. 编译（C / C++）并限制编译时间；编译失败 ⇒ ``CE``；
3. 逐个测试点运行：写入输入、启动子进程、读取输出；
4. 超时则杀死整个进程树 ⇒ ``TLE``；非零退出码 ⇒ ``RE``；
   输出与期望不符（按 token 归一化比较）⇒ ``WA``；
   峰值内存超过限制 ⇒ ``MLE``；输出过大 ⇒ ``OLE``；
5. 汇总得分：按测试点权重加权求和，全部通过 ⇒ ``Accepted``。

资源限制
--------
* **时间**：Python 用 ``subprocess`` 超时 + 墙钟计时，超时后 ``taskkill``/``killpg``
  杀死进程树（防止子进程逃逸）；
* **内存**：Windows 通过 ``GetProcessMemoryInfo``（psapi）读取峰值工作集，
  Linux/macOS 通过 ``resource.getrusage(RUSAGE_CHILDREN).ru_maxrss`` 估算；
  取不到时返回 0，并在结果里标注 ``memory_estimated = False``。

注意：这是一个**教学用**沙箱，隔离强度弱于 OJ 生产环境（未使用容器/seccomp）。
生产部署时应替换为 cgroup / namespace 隔离。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from .algo.complexity import fit_complexity

IS_WIN = os.name == "nt"

# Windows：让子进程崩溃时直接退出，不弹「程序已停止工作」对话框。
# 否则一个空指针解引用会把进程挂住，被评测引擎误判成 TLE（Linux 上则是正常的 RE）。
if IS_WIN:  # pragma: no cover - 平台相关
    try:
        import ctypes

        ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)
    except Exception:
        pass

#: 判定结果的标准全称（与前端展示、数据库记录保持一致）
VERDICT_FULL = {
    "AC": "Accepted",
    "WA": "Wrong Answer",
    "TLE": "Time Limit Exceeded",
    "RE": "Runtime Error",
    "CE": "Compile Error",
    "MLE": "Memory Limit Exceeded",
    "OLE": "Output Limit Exceeded",
}


def full_verdict(code: str) -> str:
    return VERDICT_FULL.get(code, code)

# ---------------------------------------------------------------------------
# 语言配置
# ---------------------------------------------------------------------------


def _which(*names: str) -> str | None:
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


_CPP_STD_CACHE: dict[str, str] = {}


def cpp_std_flag() -> str:
    """探测本机 g++ 支持的最高 C++ 标准（c++17 → c++14 → c++11）。

    很多教学机房里装的是较老的 MinGW（如 TDM-GCC 4.9.2），只支持到 C++11，
    因此不能硬编码 ``-std=c++17``。
    """
    gpp = _which("g++")
    if not gpp:
        return "-std=c++11"
    if gpp in _CPP_STD_CACHE:
        return _CPP_STD_CACHE[gpp]
    probe = tempfile.mkdtemp(prefix="ajp_probe_")
    try:
        src = os.path.join(probe, "t.cpp")
        with open(src, "w", encoding="utf-8") as f:
            f.write("int main(){return 0;}\n")
        for std in ("c++17", "c++14", "c++11"):
            r = run_process(
                [gpp, "-std=" + std, "-fsyntax-only", src], probe, timeout_s=15.0
            )
            if r.get("returncode") == 0:
                _CPP_STD_CACHE[gpp] = "-std=" + std
                return _CPP_STD_CACHE[gpp]
    finally:
        shutil.rmtree(probe, ignore_errors=True)
    _CPP_STD_CACHE[gpp] = "-std=c++11"
    return _CPP_STD_CACHE[gpp]


LANGUAGES = {
    "cpp": {
        "name": "C++",
        "source": "main.cpp",
        "compile": lambda exe: [_which("g++"), "-O2", cpp_std_flag(), "-o", exe, "main.cpp"],
        "run": lambda exe, mem_mb=256: [exe],
        "available": lambda: _which("g++") is not None,
        "setup": None,
        "mem_multiplier": 1.0,
    },
    "c": {
        "name": "C11",
        "source": "main.c",
        "compile": lambda exe: [_which("gcc"), "-O2", "-std=c11", "-o", exe, "main.c", "-lm"],
        "run": lambda exe, mem_mb=256: [exe],
        "available": lambda: _which("gcc") is not None,
        "setup": None,
        "mem_multiplier": 1.0,
    },
    "python": {
        "name": "Python 3",
        "source": "main.py",
        "compile": None,
        "run": lambda exe, mem_mb=256: [sys.executable, "main.py"],
        "available": lambda: True,
        "setup": None,
        "mem_multiplier": 1.0,
    },
}


def available_languages() -> list[dict]:
    out = []
    for key, cfg in LANGUAGES.items():
        try:
            ok = bool(cfg["available"]())
        except Exception:
            ok = False
        out.append({"key": key, "name": cfg["name"], "available": ok})
    return out


# ---------------------------------------------------------------------------
# 进程启动开销补偿
# ---------------------------------------------------------------------------

_STARTUP_CACHE: dict[str, float] = {}

_TRIVIAL = {
    "cpp": ("main.cpp", "int main(){return 0;}\n"),
    "c": ("main.c", "int main(){return 0;}\n"),
    "python": ("main.py", "pass\n"),
}


def startup_overhead_ms(lang: str) -> float:
    """测量「空程序」的墙钟耗时（进程创建 + 运行时初始化）。

    直接使用 ``subprocess`` 的墙钟时间会把进程启动开销算进学生程序的运行时间：
    在 Windows 上 C++ 约 20 ms、Python 解释器约 40 ms。本函数在首次评测时
    编译并运行一个空程序 3 次取中位数，作为基线从显示耗时中扣除（下限 0.3 ms），
    使不同语言之间的时间比较更公平，也让复杂度拟合曲线更接近真实增长趋势。
    """
    if lang in _STARTUP_CACHE:
        return _STARTUP_CACHE[lang]
    cfg = LANGUAGES.get(lang)
    if not cfg or lang not in _TRIVIAL:
        _STARTUP_CACHE[lang] = 0.0
        return 0.0
    name, src = _TRIVIAL[lang]
    workdir = tempfile.mkdtemp(prefix="ajp_base_")
    try:
        with open(os.path.join(workdir, name), "w", encoding="utf-8") as f:
            f.write(src)
        exe = os.path.join(workdir, "prog.exe" if IS_WIN else "prog")
        if cfg["compile"] is not None:
            cr = run_process(cfg["compile"](exe), workdir, timeout_s=25.0)
            if cr.get("returncode") != 0:
                _STARTUP_CACHE[lang] = 0.0
                return 0.0
        ts = []
        # 预热一次：首次启动新编译出的可执行文件会触发杀毒软件扫描，
        # 墙钟时间可能高达 100 ms 以上，必须先跑一次把它排除在基线之外。
        run_process(cfg["run"](exe), workdir, timeout_s=5.0)
        for _ in range(3):
            r = run_process(cfg["run"](exe), workdir, timeout_s=5.0)
            ts.append(r.get("time_ms") or 0.0)
        ts.sort()
        _STARTUP_CACHE[lang] = round(ts[1], 3)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return _STARTUP_CACHE[lang]


# ---------------------------------------------------------------------------
# 进程执行与资源计量
# ---------------------------------------------------------------------------


def _creationflags():
    if not IS_WIN:
        return 0
    return subprocess.CREATE_NO_WINDOW


def _kill_tree(proc: subprocess.Popen) -> None:
    try:
        if IS_WIN:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                creationflags=_creationflags(),
            )
        else:
            import signal

            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _preexec():
    if IS_WIN:
        return None
    def _fn():
        os.setsid()
    return _fn


def run_process(
    cmd: list[str],
    cwd: str,
    stdin_data: str = "",
    timeout_s: float = 2.0,
    max_output: int = 1 << 20,
) -> dict:
    """运行子进程并测量墙钟时间与峰值内存（按平台选择实现）。"""
    if IS_WIN:
        return _run_process_windows(cmd, cwd, stdin_data, timeout_s, max_output)
    return _run_process_posix(cmd, cwd, stdin_data, timeout_s, max_output)


def _result(ok, timeout, rc, out, err, elapsed_ms, mem_kb, estimated, error=None):
    d = {
        "ok": ok,
        "timeout": timeout,
        "returncode": rc,
        "stdout": out,
        "stderr": err,
        "time_ms": round(elapsed_ms, 3),
        "memory_kb": mem_kb,
        "memory_estimated": estimated,
    }
    if error is not None:
        d["error"] = error
    return d


def _run_process_posix(cmd, cwd, stdin_data, timeout_s, max_output):
    """POSIX 实现：用 ``os.wait4`` 取得**该子进程自己**的 rusage。

    为什么不能用 ``resource.getrusage(RUSAGE_CHILDREN)``：它返回的是「本进程所有
    已回收子进程的历史最大值」，会把之前编译阶段 g++（峰值可达 180 MB+）的占用
    算到每一个学生程序头上，导致所有提交都被误判成 MLE。

    输入/输出走临时文件而不是管道，既避免了大输入下的死锁，也让计时/回收逻辑更简单。
    """
    workdir = tempfile.mkdtemp(prefix="ajp_io_")
    in_p = os.path.join(workdir, "stdin.txt")
    out_p = os.path.join(workdir, "stdout.txt")
    err_p = os.path.join(workdir, "stderr.txt")
    try:
        with open(in_p, "w", encoding="utf-8", errors="replace") as fi:
            fi.write(stdin_data or "")
        with open(in_p, "r", encoding="utf-8", errors="replace") as fi, \
                open(out_p, "wb") as fo, open(err_p, "wb") as fe:
            t0 = time.perf_counter()
            try:
                proc = subprocess.Popen(
                    cmd, cwd=cwd, stdin=fi, stdout=fo, stderr=fe,
                    preexec_fn=os.setsid if hasattr(os, "setsid") else None,
                )
            except FileNotFoundError as e:
                return _result(False, False, None, "", "", 0, 0, True, f"命令不存在: {e}")
            except Exception as e:  # pragma: no cover
                return _result(False, False, None, "", "", 0, 0, True, str(e))

            box: dict = {}

            def _waiter():
                try:
                    _pid, status, ru = os.wait4(proc.pid, 0)
                    box["status"] = status
                    box["ru"] = ru
                except (ChildProcessError, OSError):
                    pass

            th = threading.Thread(target=_waiter, daemon=True)
            th.start()
            th.join(timeout_s)
            timed_out = th.is_alive()
            if timed_out:
                _kill_tree(proc)
                th.join(3.0)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

        ru = box.get("ru")
        if ru is not None:
            mem_kb = float(ru.ru_maxrss) / 1024.0 if sys.platform == "darwin" else float(ru.ru_maxrss)
            estimated = False
            rc = os.waitstatus_to_exitcode(box["status"]) if "status" in box else proc.returncode
        else:
            mem_kb, estimated, rc = 0.0, True, proc.returncode
        proc.returncode = rc
        out = _read_capped(out_p, max_output)
        err = _read_capped(err_p, 64 * 1024)
        return _result(not timed_out, timed_out, rc, out, err, elapsed_ms, mem_kb, estimated)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _read_capped(path: str, limit: int) -> str:
    try:
        with open(path, "rb") as f:
            data = f.read(limit)
        return data.decode("utf-8", "replace")
    except OSError:
        return ""


def _run_process_windows(cmd, cwd, stdin_data, timeout_s, max_output):
    """Windows 实现：``communicate`` + ``GetProcessMemoryInfo`` 读峰值工作集。"""
    t0 = time.perf_counter()
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_creationflags(),
            preexec_fn=_preexec(),
        )
    except FileNotFoundError as e:
        return _result(False, False, None, "", "", 0, 0, True, f"命令不存在: {e}")
    except Exception as e:  # pragma: no cover
        return _result(False, False, None, "", "", 0, 0, True, str(e))

    timeout = False
    try:
        out, err = proc.communicate(input=stdin_data, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timeout = True
        _kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=2)
        except Exception:
            out, err = "", ""
    except Exception as e:  # pragma: no cover
        _kill_tree(proc)
        return _result(False, False, None, "", "", 0, 0, True, str(e))

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    mem_kb, estimated = peak_memory_kb(proc.pid)
    return _result(
        not timeout, timeout, proc.returncode,
        (out or "")[:max_output], (err or "")[: 64 * 1024],
        elapsed_ms, mem_kb, estimated,
    )


def peak_memory_kb(pid: int) -> tuple[float, bool]:
    """Windows 专用：读取指定进程的峰值工作集，返回 ``(KB, 是否为估算值)``。

    POSIX 平台不要用这个函数：那里的正确做法是在 ``_run_process_posix`` 中
    用 ``os.wait4`` 取**该子进程自己**的 ``ru_maxrss``。用
    ``getrusage(RUSAGE_CHILDREN)`` 会把编译器等高内存子进程的历史峰值算进来，
    导致所有提交被误判为超内存。
    """
    if IS_WIN:
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not h:
                return 0.0, True
            try:
                counters = PROCESS_MEMORY_COUNTERS()
                counters.cb = ctypes.sizeof(counters)
                if psapi.GetProcessMemoryInfo(h, ctypes.byref(counters), counters.cb):
                    return counters.PeakWorkingSetSize / 1024.0, False
            finally:
                k32.CloseHandle(h)
        except Exception:
            pass
        return 0.0, True
    return 0.0, True


# ---------------------------------------------------------------------------
# 输出比较
# ---------------------------------------------------------------------------


def code_metrics(code: str, language: str = "cpp") -> dict:
    """代码规模统计：互评时给对方一个客观的「代码画像」。

    统计总行数、有效代码行、注释行、空白行、最长行与平均行长。
    注释按语言区分（Python 用 ``#``，C/C++ 用 ``//`` 与 ``/* */``），
    只做单行判断（不解析块注释嵌套），够用且不会误报太多。
    """
    lines = (code or "").split("\n")
    if lines and lines[-1] == "":
        lines.pop()                      # 结尾换行不算一行
    blank = comment = 0
    max_len = 0
    max_no = 0
    total_len = 0
    in_block = False
    for i, raw in enumerate(lines, 1):
        s = raw.strip()
        length = len(raw)
        total_len += length
        if length > max_len:
            max_len, max_no = length, i
        if not s:
            blank += 1
            continue
        if language == "python":
            if s.startswith("#"):
                comment += 1
            continue
        if in_block:
            comment += 1
            if "*/" in s:
                in_block = False
            continue
        if s.startswith("//"):
            comment += 1
        elif s.startswith("/*"):
            comment += 1
            if "*/" not in s:
                in_block = True
    n = len(lines)
    return {
        "lines": n,
        "code_lines": max(0, n - blank - comment),
        "comment_lines": comment,
        "blank_lines": blank,
        "max_line_len": max_len,
        "max_line_no": max_no,
        "avg_line_len": round(total_len / n, 1) if n else 0,
    }


def outputs_match(expected: str, actual: str) -> bool:
    """按 token 比较，忽略行尾空白与多余空行（OJ 通用做法）。"""
    if expected is None:
        return True
    e = expected.split()
    a = actual.split()
    if len(e) != len(a):
        return False
    for x, y in zip(e, a):
        if x == y:
            continue
        # 数值比较：容忍 1e-6 相对误差与 -0.0
        try:
            fx, fy = float(x), float(y)
            if abs(fx - fy) <= 1e-6 * max(1.0, abs(fx)):
                continue
        except ValueError:
            pass
        return False
    return True


# ---------------------------------------------------------------------------
# 评测主流程
# ---------------------------------------------------------------------------


def judge_submission(
    source_code: str,
    language: str,
    test_cases: list[dict],
    time_limit_ms: int = 1000,
    memory_limit_mb: int = 256,
    total_score: float = 100.0,
) -> dict:
    """评测一份代码，返回完整结果字典。

    ``test_cases``: ``[{"id":..,"name":..,"input":..,"expected":..,"score":..}, ...]``
    """
    lang = (language or "cpp").lower()
    if lang not in LANGUAGES:
        return {"verdict": full_verdict("CE"), "code": "CE",
                "message": f"不支持的语言：{language}", "score": 0, "results": []}
    cfg = LANGUAGES[lang]
    if not cfg["available"]():
        return {
            "verdict": full_verdict("CE"),
            "code": "CE",
            "message": f"本机未检测到 {cfg['name']} 编译器，无法评测该语言",
            "score": 0,
            "results": [],
        }

    workdir = tempfile.mkdtemp(prefix="ajp_judge_")
    try:
        with open(os.path.join(workdir, cfg["source"]), "w", encoding="utf-8") as f:
            f.write(source_code)
        exe = os.path.join(workdir, "prog.exe" if IS_WIN else "prog")
        compile_message = ""
        if cfg["compile"] is not None:
            cmd = cfg["compile"](exe)
            if not cmd or not cmd[0]:
                return {"verdict": full_verdict("CE"), "code": "CE", "message": "编译器不可用",
                        "score": 0, "results": []}
            cr = run_process(cmd, workdir, timeout_s=25.0)
            if cr.get("returncode") != 0:
                return {
                    "verdict": full_verdict("CE"),
                    "code": "CE",
                    "message": (cr.get("stderr") or cr.get("error") or "编译失败")[:4000],
                    "score": 0,
                    "results": [],
                    "time_ms": cr.get("time_ms", 0),
                }
            compile_message = (cr.get("stderr") or "").strip()

        mult = float(cfg.get("mem_multiplier", 1.0))
        mem_limit_mb = memory_limit_mb * mult
        run_cmd = cfg["run"](exe, mem_limit_mb)
        timeout_s = max(0.5, time_limit_ms / 1000.0)
        base_ms = startup_overhead_ms(lang)
        # 预热：把「首次启动磁盘扫描」的开销排除在计时之外
        run_process(run_cmd, workdir, stdin_data="", timeout_s=min(2.0, timeout_s))
        results = []
        total = 0.0
        max_score = sum(float(tc.get("score") or 0) for tc in test_cases) or 1.0
        worst = "AC"
        order = {"AC": 0, "WA": 1, "OLE": 2, "MLE": 3, "RE": 4, "TLE": 5, "CE": 6}
        max_time = 0.0
        max_wall = 0.0
        max_mem = 0.0
        for tc in test_cases:
            r = run_process(
                run_cmd,
                workdir,
                stdin_data=tc.get("input") or "",
                timeout_s=timeout_s,
                max_output=1 << 20,
            )
            if r.get("timeout"):
                verdict = "TLE"
                msg = f"超过时间限制 {time_limit_ms} ms"
            elif not r.get("ok"):
                verdict = "RE"
                msg = r.get("error") or "运行错误"
            elif r.get("returncode") != 0:
                verdict = "RE"
                msg = (r.get("stderr") or "").strip()[:500] or f"退出码 {r.get('returncode')}"
            elif len(r.get("stdout") or "") >= (1 << 20):
                verdict = "OLE"
                msg = "输出超过 1 MB"
            elif mem_limit_mb and r.get("memory_kb", 0) > mem_limit_mb * 1024:
                verdict = "MLE"
                msg = f"内存超过 {mem_limit_mb:.0f} MB"
            elif not outputs_match(tc.get("expected"), r.get("stdout") or ""):
                verdict = "WA"
                msg = "输出与期望不一致"
            else:
                verdict = "AC"
                msg = "通过"
                total += float(tc.get("score") or 0)
            max_mem = max(max_mem, r.get("memory_kb") or 0)
            raw_ms = r.get("time_ms") or 0.0
            eff_ms = max(0.3, raw_ms - base_ms)
            max_time = max(max_time, eff_ms)
            max_wall = max(max_wall, raw_ms)
            if order.get(verdict, 9) > order.get(worst, 0):
                worst = verdict
            results.append(
                {
                    "test_case_id": tc.get("id"),
                    "name": tc.get("name"),
                    "verdict": verdict,
                    "time_ms": round(eff_ms, 3),
                    "wall_ms": round(raw_ms, 3),
                    "memory_kb": round(r.get("memory_kb") or 0, 1),
                    "message": msg,
                    "stderr": (r.get("stderr") or "")[:600],
                    "actual": (r.get("stdout") or "")[:2000],
                    "expected": (tc.get("expected") or "")[:2000],
                }
            )
            if verdict == "TLE":
                break  # 已经超时，后续测试点无意义
        score = round(total / max_score * total_score, 2)
        return {
            "verdict": full_verdict(worst),
            "code": worst,
            "score": score,
            "time_ms": round(max_time, 3),
            "wall_ms": round(max_wall, 3),
            "memory_kb": round(max_mem, 1),
            "startup_overhead_ms": round(base_ms, 3),
            "compile_message": compile_message,
            "results": results,
            "passed": sum(1 for r in results if r["verdict"] == "AC"),
            "total_cases": len(test_cases),
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 复杂度实验：同一份代码在多个输入规模下运行，拟合渐进复杂度
# ---------------------------------------------------------------------------


def measure_complexity(
    source_code: str,
    language: str,
    cases_by_size: list[tuple[int, str]],
    time_limit_ms: int = 20000,
) -> dict:
    """``cases_by_size``: ``[(n, input_text), ...]``，按 n 升序。

    返回 ``fit_complexity`` 的结果，附带每个规模的实测耗时。

    计时细节：先做一次预热运行（排除首次启动的磁盘扫描开销），再从每个规模的
    实测墙钟时间中扣除「空程序基线」（``startup_overhead_ms``），
    并取 3 次运行的中位数，最后按 n 升序依次测量。
    """
    lang = (language or "cpp").lower()
    if lang not in LANGUAGES or not LANGUAGES[lang]["available"]():
        return {"ok": False, "reason": "语言不可用"}
    cfg = LANGUAGES[lang]
    workdir = tempfile.mkdtemp(prefix="ajp_cplx_")
    try:
        with open(os.path.join(workdir, cfg["source"]), "w", encoding="utf-8") as f:
            f.write(source_code)
        exe = os.path.join(workdir, "prog.exe" if IS_WIN else "prog")
        if cfg["compile"] is not None:
            cr = run_process(cfg["compile"](exe), workdir, timeout_s=25.0)
            if cr.get("returncode") != 0:
                return {"ok": False, "reason": "编译失败", "message": (cr.get("stderr") or "")[:2000]}
        base_ms = startup_overhead_ms(lang)
        # 预热：先跑一次最大规模的输入，让 CPU 频率与文件缓存进入稳态
        biggest = max(cases_by_size, key=lambda x: x[0])
        run_process(cfg["run"](exe), workdir, stdin_data=biggest[1],
                    timeout_s=min(30.0, time_limit_ms / 1000.0))
        points = []
        for n, inp in sorted(cases_by_size, key=lambda x: x[0]):
            # 每个规模测 5 次取中位数，降低调度抖动
            ts = []
            for _ in range(5):
                r = run_process(
                    cfg["run"](exe), workdir, stdin_data=inp, timeout_s=time_limit_ms / 1000.0
                )
                if r.get("timeout"):
                    ts.append(time_limit_ms / 1000.0)
                    break
                ts.append(max(0.05, (r.get("time_ms") or 0.0) - base_ms))
            ts.sort()
            points.append({"n": n, "time_ms": round(ts[len(ts) // 2], 4)})
            if points[-1]["time_ms"] >= time_limit_ms:
                break
        fit = fit_complexity(points)
        fit["measurements"] = points
        fit["startup_overhead_ms"] = round(base_ms, 3)
        return fit
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 静态安全检查（提示性质，不是强制沙箱）
# ---------------------------------------------------------------------------

FORBIDDEN = {
    "python": ["import os", "import sys\nos", "subprocess", "socket", "shutil.rmtree", "__import__", "eval(", "exec("],
    "cpp": ["system(", "fork(", "socket(", "popen(", "execv"],
}


def static_check(code: str, language: str) -> list[str]:
    """返回可疑片段提示列表（教学演示用；真正的安全依赖资源限制与沙箱）。"""
    lang = "python" if (language or "").lower().startswith("py") else "cpp"
    hits = []
    for kw in FORBIDDEN.get(lang, []):
        if kw in code:
            hits.append(kw)
    return hits
