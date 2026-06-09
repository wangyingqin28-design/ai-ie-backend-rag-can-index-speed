# -*- coding: utf-8 -*-
"""SQL_RAG 智能客服业务脑前端静态服务和后端代理。"""

# 导入 argparse，用于解析 WebUI 服务端口和后端地址。
import argparse
# 导入 json，用于输出启动摘要。
import json
# 导入 os，用于读取环境变量中的后端地址。
import os
# 导入 sys，用于设置 Windows 终端 UTF-8 输出。
import sys
# 导入 functools.partial，用于给 HTTP handler 固定静态目录。
from functools import partial
# 导入 Path，用于定位当前 agent_webUI 目录。
from pathlib import Path
# 导入标准库 HTTP 服务类，避免新增前端服务依赖。
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
# 导入类型标注。
from typing import Sequence
# 导入 urllib 错误类型，用于代理后端异常。
from urllib.error import HTTPError, URLError
# 导入 urllib 请求对象，用于转发 HTTP 请求到业务脑服务。
from urllib.request import Request, urlopen

# Windows 控制台默认编码可能不是 UTF-8，这里只调整当前进程输出。
if hasattr(sys.stdout, "reconfigure"):
    # 统一标准输出编码。
    sys.stdout.reconfigure(encoding="utf-8")

# 定位当前文件所在目录，也就是前端静态资源目录。
WEBUI_DIR = Path(__file__).resolve().parent
# 定义默认后端地址，优先读取环境变量，默认指向本机业务脑服务。
DEFAULT_BACKEND_URL = os.environ.get("SQL_RAG_BUSINESS_BRAIN_URL", "http://127.0.0.1:18180").rstrip("/")
# 定义前端代理前缀。
API_PREFIX = "/api"


class AgentWebUIRequestHandler(SimpleHTTPRequestHandler):
    """为 SQL_RAG agent_webUI 提供静态文件和 API 代理。"""

    # 保存后端业务脑地址。
    backend_url = DEFAULT_BACKEND_URL

    def do_GET(self) -> None:
        # GET 请求如果命中 /api 前缀，就代理到业务脑后端。
        if self.path.startswith(API_PREFIX):
            # 代理 GET 请求。
            self._proxy_request("GET")
            # 结束 GET 处理。
            return
        # 根路径直接返回 index.html。
        if self.path == "/":
            # 改写为首页文件。
            self.path = "/index.html"
        # 其他 GET 请求交给静态文件处理器。
        super().do_GET()

    def do_POST(self) -> None:
        # POST 请求如果命中 /api 前缀，就代理到业务脑后端。
        if self.path.startswith(API_PREFIX):
            # 代理 POST 请求。
            self._proxy_request("POST")
            # 结束 POST 处理。
            return
        # 非 API POST 不支持。
        self.send_error(404, "Not Found")

    def end_headers(self) -> None:
        # 禁止缓存前端文件，方便开发时刷新验证。
        self.send_header("Cache-Control", "no-store")
        # 调用父类写入剩余响应头。
        super().end_headers()

    def _proxy_request(self, method: str) -> None:
        # 把前端 /api 前缀剥离，得到后端真实路径。
        upstream_path = self.path[len(API_PREFIX):]
        # 拼接后端 URL。
        upstream_url = f"{self.backend_url}{upstream_path}"
        # 读取请求体长度。
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        # 按长度读取请求体。
        body = self.rfile.read(content_length) if content_length else None
        # 创建上游请求。
        request = Request(
            # 设置上游 URL。
            upstream_url,
            # 设置请求体。
            data=body,
            # 设置请求方法。
            method=method,
            # 透传 JSON Content-Type。
            headers={"Content-Type": self.headers.get("Content-Type", "application/json")},
        )
        # 尝试请求上游业务脑服务。
        try:
            # 发起上游请求并设置超时。
            with urlopen(request, timeout=900) as response:
                # 读取上游状态码。
                status = response.status
                # 读取上游 Content-Type。
                content_type = response.headers.get("Content-Type", "application/json; charset=utf-8")
                # 2026-06-04 17:14:18 新增原因：NDJSON 流式响应不能一次性 read，否则前端无法实时看到 trace。
                if "application/x-ndjson" in content_type:
                    # 2026-06-04 17:14:18 新增原因：写入流式响应状态码。
                    self.send_response(status)
                    # 2026-06-04 17:14:18 新增原因：写入流式响应类型。
                    self.send_header("Content-Type", content_type)
                    # 2026-06-04 17:14:18 新增原因：结束响应头，开始转发 body。
                    self.end_headers()
                    # 2026-06-04 17:14:18 新增原因：持续读取上游小块数据。
                    while True:
                        # 2026-06-04 17:14:18 新增原因：读取一块上游数据。
                        chunk = response.read(4096)
                        # 2026-06-04 17:14:18 新增原因：空块表示上游流结束。
                        if not chunk:
                            # 2026-06-04 17:14:18 新增原因：退出转发循环。
                            break
                        # 2026-06-04 17:14:18 新增原因：写入浏览器连接。
                        self.wfile.write(chunk)
                        # 2026-06-04 17:14:18 新增原因：flush 保证前端 reader 及时收到。
                        self.wfile.flush()
                    # 2026-06-04 17:14:18 新增原因：流式响应已完成。
                    return
                # 读取上游响应体。
                data = response.read()
                # 写回代理响应。
                self._write_response(status, content_type, data)
        # 捕获上游 HTTP 错误。
        except HTTPError as exc:
            # 读取错误响应体。
            data = exc.read()
            # 写回上游错误状态。
            self._write_response(exc.code, exc.headers.get("Content-Type", "application/json; charset=utf-8"), data)
        # 捕获网络错误。
        except URLError as exc:
            # 构造 JSON 错误。
            payload = json.dumps({"detail": f"后端业务脑连接失败：{exc.reason}"}, ensure_ascii=False).encode("utf-8")
            # 写回 502。
            self._write_response(502, "application/json; charset=utf-8", payload)
        # 捕获其他异常。
        except Exception as exc:
            # 构造 JSON 错误。
            payload = json.dumps({"detail": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False).encode("utf-8")
            # 写回 500。
            self._write_response(500, "application/json; charset=utf-8", payload)

    def _write_response(self, status: int, content_type: str, data: bytes) -> None:
        # 写入状态码。
        self.send_response(status)
        # 写入响应类型。
        self.send_header("Content-Type", content_type)
        # 写入响应长度。
        self.send_header("Content-Length", str(len(data)))
        # 结束响应头。
        self.end_headers()
        # 写入响应体。
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        # 使用更短的访问日志格式。
        sys.stdout.write("[agent_webUI] " + (format % args) + "\n")


def build_arg_parser() -> argparse.ArgumentParser:
    # 创建命令行解析器。
    parser = argparse.ArgumentParser(description="启动 SQL_RAG 智能客服业务脑前端 WebUI。")
    # 添加监听 host。
    parser.add_argument("--host", default="127.0.0.1", help="WebUI 监听地址。")
    # 添加监听端口。
    parser.add_argument("--port", type=int, default=18181, help="WebUI 监听端口。")
    # 添加后端业务脑地址。
    parser.add_argument("--backend-url", default=DEFAULT_BACKEND_URL, help="业务脑后端地址，例如 http://127.0.0.1:18180。")
    # 返回解析器。
    return parser


def run_agent_webui(argv: Sequence[str] | None = None) -> int:
    # 构建参数解析器。
    parser = build_arg_parser()
    # 解析命令行参数。
    args = parser.parse_args(list(argv) if argv is not None else None)
    # 更新 handler 后端地址。
    AgentWebUIRequestHandler.backend_url = str(args.backend_url).rstrip("/")
    # 绑定静态目录到 handler。
    handler = partial(AgentWebUIRequestHandler, directory=str(WEBUI_DIR))
    # 创建多线程 HTTP 服务。
    server = ThreadingHTTPServer((args.host, args.port), handler)
    # 构造启动摘要。
    summary = {
        "ready": True,
        "webui": f"http://{args.host}:{args.port}",
        "backend_url": AgentWebUIRequestHandler.backend_url,
        "static_dir": str(WEBUI_DIR),
    }
    # 打印启动摘要。
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    # 启动服务。
    try:
        # 阻塞处理请求。
        server.serve_forever()
    # 捕获 Ctrl+C。
    except KeyboardInterrupt:
        # 输出关闭提示。
        print("agent_webUI stopped.")
    # 正常关闭服务。
    finally:
        # 关闭 server socket。
        server.server_close()
    # 返回成功码。
    return 0


if __name__ == "__main__":
    # 允许直接通过 python webui_server.py 启动。
    raise SystemExit(run_agent_webui())
