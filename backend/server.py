"""零依赖 HTTP 服务：静态资源 + REST API。

只使用 Python 标准库 ``http.server``，不需要 pip 安装任何东西：

    python run.py            # 启动，默认 http://127.0.0.1:8000

特性
----
* 多线程处理请求（``ThreadingHTTPServer``），SQLite 连接按线程隔离；
* 静态资源带缓存控制与正确的 MIME（含 ``.js`` 的 ES Module 支持）；
* 支持 ``Range`` 之外的简单断点不需要——前端是纯静态，够用；
* 统一异常捕获：未处理异常返回 500 + JSON，不把栈信息泄漏给前端。
"""

from __future__ import annotations

import json
import mimetypes
import os
import posixpath
import re
import sqlite3
import sys
import threading
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import api as API  # noqa: E402
from backend import db  # noqa: E402
from backend.auth import get_session  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(ROOT, "frontend")

_COMPILED: list[tuple[str, re.Pattern, callable, str]] = []


def compile_routes() -> None:
    """把 ``/api/xxx/{id}`` 形式的路径编译成正则，同时把字面量路由排到前面。"""
    _COMPILED.clear()
    items = []
    for method, path, fn, auth in API.ROUTES:
        pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", path)
        items.append((method, re.compile("^" + pattern + "$"), fn, auth))
    items.sort(key=lambda x: ("{" in x[0] and 0 or 0, x[1].pattern.count("(?P<")))
    _COMPILED.extend(items)


def _json_default(o):
    """兜底序列化：把 sqlite3.Row / set / 其它非 JSON 类型安全转换。"""
    if isinstance(o, sqlite3.Row):
        return dict(o)
    if isinstance(o, (set, frozenset, tuple)):
        return list(o)
    if isinstance(o, bytes):
        return o.decode("utf-8", "replace")
    return str(o)


MIME_OVERRIDE = {
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".webmanifest": "application/manifest+json",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "AJP/1.0"
    protocol_version = "HTTP/1.1"

    # ---------------- 基础响应 ----------------
    def _send(self, status: int, body: bytes, content_type: str, extra=None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        # 静态资源使用 no-cache（允许缓存但每次都要与服务器校验），
        # 这样开发时改完前端刷新即可生效，同时生产环境仍可命中协商缓存。
        self.send_header("Cache-Control", "no-store" if content_type.startswith("application/json")
                         else "no-cache")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=_json_default).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def log_message(self, fmt, *args):  # 降低噪音，只记录错误
        if str(args[1] if len(args) > 1 else "").startswith(("4", "5")):
            sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    # ---------------- 请求解析 ----------------
    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        ctype = (self.headers.get("Content-Type") or "").lower()
        if "json" in ctype or raw.strip().startswith((b"{", b"[")):
            try:
                return json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return {}
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw.decode("utf-8")).items()}

    def _token(self):
        auth = self.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return self.headers.get("X-Token") or None

    # ---------------- 分发 ----------------
    def _dispatch(self, method: str) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)
        if path.startswith("/api/"):
            self._api(method, path, parsed)
        elif method in ("GET", "HEAD"):
            self._static(path)
        else:
            self._json(405, {"ok": False, "error": "Method Not Allowed"})

    def _api(self, method, path, parsed):
        for m, rx, fn, auth in _COMPILED:
            if m != method:
                continue
            match = rx.match(path)
            if not match:
                continue
            token = self._token()
            session = get_session(token)
            if auth != "public" and not session:
                return self._json(401, {"ok": False, "error": "登录状态已失效，请重新登录"})
            if auth == "teacher" and session.get("role") not in ("teacher", "ta"):
                return self._json(403, {"ok": False, "error": "该操作仅教师/助教可用"})
            ctx = {
                "params": match.groupdict(),
                "query": {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()},
                "body": self._read_body() if method in ("POST", "PUT", "PATCH", "DELETE") else {},
                "user": session,
                "token": token,
            }
            try:
                status, payload = fn(ctx)
            except Exception as e:  # pragma: no cover
                traceback.print_exc()
                return self._json(500, {"ok": False, "error": "服务器内部错误：%s" % e})
            return self._json(status, payload)
        self._json(404, {"ok": False, "error": "接口不存在：" + path})

    def _static(self, path: str):
        if path in ("/", ""):
            path = "/index.html"
        # 防目录穿越
        safe = posixpath.normpath(path).lstrip("/")
        if safe.startswith("..") or ":" in safe:
            return self._json(400, {"ok": False, "error": "非法路径"})
        full = os.path.join(FRONTEND, safe.replace("/", os.sep))
        if not os.path.abspath(full).startswith(os.path.abspath(FRONTEND)):
            return self._json(403, {"ok": False, "error": "禁止访问"})
        if os.path.isdir(full):
            full = os.path.join(full, "index.html")
        if not os.path.exists(full):
            # SPA 兜底：未知路径一律返回首页（前端使用 hash 路由）
            if "." not in posixpath.basename(safe):
                return self._static("/index.html")
            return self._json(404, {"ok": False, "error": "文件不存在"})
        ext = os.path.splitext(full)[1].lower()
        ctype = MIME_OVERRIDE.get(ext) or mimetypes.guess_type(full)[0] or "application/octet-stream"
        try:
            st = os.stat(full)
            etag = '"%x-%x"' % (int(st.st_mtime), st.st_size)
            last_modified = self.date_time_string(int(st.st_mtime))
        except OSError:
            etag, last_modified = None, None
        # 协商缓存：浏览器改完代码刷新即可生效，生产环境也能省掉重复传输
        if etag and self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            return
        try:
            with open(full, "rb") as f:
                body = f.read()
        except OSError as e:
            return self._json(500, {"ok": False, "error": str(e)})
        self._send(200, body, ctype, {"ETag": etag, "Last-Modified": last_modified})

    # ---------------- HTTP 方法 ----------------
    def do_GET(self):
        self._dispatch("GET")

    def do_HEAD(self):
        self._dispatch("HEAD")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def do_OPTIONS(self):
        self._send(204, b"", "text/plain; charset=utf-8")


def serve(host: str = "127.0.0.1", port: int = 8000, seed_if_empty: bool = True) -> None:
    db.init_db()
    from backend import seed as seedmod

    if seed_if_empty and db.is_empty():
        print("检测到空数据库，正在生成演示数据 ...", flush=True)
        seedmod.seed(reset=True, verbose=True)
    compile_routes()
    local = "127.0.0.1" if host in ("0.0.0.0", "") else host
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    print("\n" + "=" * 62)
    print("  算法设计与分析课程评审平台  已启动")
    print("  本机访问 : http://%s:%d" % (local, port))
    if host in ("0.0.0.0", ""):
        import socket

        try:
            ip = socket.gethostbyname(socket.gethostname())
            print("  局域网访问: http://%s:%d" % (ip, port))
        except OSError:
            pass
    print("  演示账号 : teacher / 123456 （教师）  stu1 / 123456 （学生）")
    print("  按 Ctrl+C 停止服务")
    print("=" * 62 + "\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    port = int(os.environ.get("AJP_PORT") or (sys.argv[1] if len(sys.argv) > 1 else 8000))
    host = os.environ.get("AJP_HOST") or "127.0.0.1"
    serve(host, port)
