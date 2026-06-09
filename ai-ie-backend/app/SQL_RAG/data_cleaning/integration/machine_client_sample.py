# -*- coding: utf-8 -*-
"""其他机台连接服务器读写 RAG 数据的测试样例。"""

# 修改日期：2026-06-01 10:14:00。
# 修改理由：给外部机台提供最小可运行 HTTP 读写样例，验证只要拿到接口地址和库名即可连接。
# 修改日期：2026-06-01 11:07:00。
# 修改理由：补齐完整增删改查测试，外部机台可以安全地在测试表验证读写能力。

# 导入命令行参数库。
import argparse
# 导入 JSON 库。
import json
# 导入 URL 编码工具。
from urllib.parse import urlencode
# 导入 HTTP 请求工具。
from urllib.request import Request, urlopen


def request_json(method: str, url: str, payload: dict | None = None) -> dict:
    # 把 payload 编码成 JSON bytes。
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    # 创建 HTTP 请求。
    request = Request(url=url, data=data, method=method)
    # 设置 JSON 请求头。
    request.add_header("Content-Type", "application/json")
    # 打开 HTTP 连接。
    with urlopen(request, timeout=20) as response:
        # 读取响应 bytes。
        body = response.read()
    # 解析 JSON 响应。
    return json.loads(body.decode("utf-8"))


def main() -> int:
    # 创建命令行解析器。
    parser = argparse.ArgumentParser(description="其他机台 HTTP 读写 RAG 开放接口测试样例")
    # 配置服务器接口根地址。
    parser.add_argument("--base-url", default="http://127.0.0.1:18080", help="服务器开放接口根地址")
    # 配置机台 ID。
    parser.add_argument("--machine-id", default="machine-demo-001", help="当前机台 ID")
    # 解析命令行参数。
    args = parser.parse_args()
    # 请求健康检查接口。
    health = request_json("GET", f"{args.base_url}/health")
    # 写入机台测试数据。
    write_result = request_json(
        "POST",
        f"{args.base_url}/machine-test/write",
        {"machine_id": args.machine_id, "payload": {"event": "connect_read_write_test", "database_name": health["database_name"]}},
    )
    # 读取新增测试记录 ID。
    inserted_id = write_result["inserted_id"]
    # 更新机台测试数据。
    update_result = request_json(
        "PATCH",
        f"{args.base_url}/machine-test/{inserted_id}",
        {"payload": {"event": "connect_read_write_update_test", "database_name": health["database_name"], "updated": True}},
    )
    # 读取当前机台写入的数据。
    read_result = request_json("GET", f"{args.base_url}/machine-test/read?{urlencode({'machine_id': args.machine_id})}")
    # 读取前 3 条 RAG chunk。
    chunk_result = request_json("GET", f"{args.base_url}/chunks?{urlencode({'limit': 3})}")
    # 删除机台测试数据。
    delete_result = request_json("DELETE", f"{args.base_url}/machine-test/{inserted_id}")
    # 打印测试结果。
    print(
        json.dumps(
            {"health": health, "write": write_result, "update": update_result, "read": read_result, "delete": delete_result, "chunks": chunk_result},
            ensure_ascii=False,
            indent=2,
        )
    )
    # 返回成功退出码。
    return 0


# 保持脚本直接运行能力。
if __name__ == "__main__":
    # 把 main 返回码交给进程。
    raise SystemExit(main())
