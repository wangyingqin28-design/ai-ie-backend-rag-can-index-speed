# -*- coding: utf-8 -*-
"""Qwen3.5-2B 本机验证模型服务运行辅助。"""

# 修改日期：2026-06-03 11:30:00。
# 修改理由：保留 Qwen3.5-35B CUDA/vLLM 备用 runtime 的同时，为当前无 CUDA 机器补齐 Qwen3.5-2B GGUF + llama.cpp 本机验证服务。

# 导入 argparse，用于构建 Qwen3.5-2B 子命令。
import argparse
# 导入 JSON，用于输出机器可读部署摘要。
import json
# 导入 os，用于读取和合并环境变量。
import os
# 导入 re，用于匹配 llama.cpp Windows CPU 运行时资产。
import re
# 导入 shutil，用于查找本机可执行文件。
import shutil
# 导入 subprocess，用于启动和检查 llama-server 进程。
import subprocess
# 导入 sys，用于 Windows 终端 UTF-8 输出。
import sys
# 导入 time，用于启动服务后的轮询等待。
import time
# 导入 urllib.error，用于处理下载和健康检查异常。
import urllib.error
# 导入 urllib.request，用于直接下载 GitHub/Hugging Face 文件。
import urllib.request
# 导入 zipfile，用于解压 llama.cpp 便携运行时。
import zipfile
# 导入 dataclass，用于承载 Qwen3.5-2B 配置。
from dataclasses import dataclass
# 导入 Path，用于定位配置、模型和运行时路径。
from pathlib import Path
# 导入 Any 和 Sequence，用于配置和命令行类型标注。
from typing import Any, Sequence

# 导入 PyYAML，用于读取 Qwen3.5-2B YAML 配置。
import yaml

# 定位当前模型服务配置目录。
MODEL_SERVICE_DIR = Path(__file__).resolve().parent
# 定位 SQL_RAG 根目录。
SQL_RAG_DIR = MODEL_SERVICE_DIR.parents[1]

# Windows 终端默认 GBK 时可能无法打印模型名和中文提示，这里统一切到 UTF-8。
if hasattr(sys.stdout, "reconfigure"):
    # 只影响当前进程输出编码。
    sys.stdout.reconfigure(encoding="utf-8")


@dataclass(frozen=True)
class Qwen35TwoBConfig:
    # 保存模型服务后端名称。
    backend: str
    # 保存模型 ID。
    model_id: str
    # 保存 Hugging Face GGUF 仓库。
    gguf_repo: str
    # 保存 GGUF 文件名。
    gguf_file: str
    # 保存模型目录。
    model_dir: Path
    # 保存模型文件路径。
    model_path: Path
    # 保存 llama.cpp release API。
    release_api: str
    # 保存 llama.cpp asset 匹配正则。
    asset_pattern: str
    # 保存 llama.cpp 运行时目录。
    runtime_dir: Path
    # 保存 llama-server 可执行文件路径。
    server_exe: Path
    # 保存服务 host。
    host: str
    # 保存服务 port。
    port: int
    # 保存 OpenAI-compatible base URL。
    openai_base_url: str
    # 保存 API key。
    api_key: str
    # 保存上下文长度。
    context_size: int
    # 保存 CPU 线程数。
    threads: int
    # 保存 GPU offload 层数，当前机器默认 0。
    gpu_layers: int
    # 保存温度。
    temperature: float
    # 保存 top_p。
    top_p: float
    # 保存最大生成 token。
    predict: int
    # 保存业务脑 Qwen-Agent 单轮最大输出 token。
    agent_max_tokens: int
    # 保存业务脑 Qwen-Agent 温度。
    agent_temperature: float


def _print_json(value: Any) -> None:
    # 用 UTF-8 JSON 打印值，方便脚本和日志消费。
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _load_yaml(path: Path) -> dict[str, Any]:
    # 检查 YAML 文件是否存在。
    if not path.exists():
        # 缺失配置时抛出明确错误。
        raise FileNotFoundError(f"Qwen3.5-2B 配置文件不存在：{path}")
    # 读取 YAML 文本。
    text = path.read_text(encoding="utf-8")
    # 解析 YAML。
    data = yaml.safe_load(text) or {}
    # 顶层必须是字典。
    if not isinstance(data, dict):
        # 非字典配置无法继续处理。
        raise ValueError(f"Qwen3.5-2B 配置必须是 YAML 对象：{path}")
    # 返回配置字典。
    return data


def _config_value(config: dict[str, Any], path: Sequence[str], default: Any = None) -> Any:
    # 从 YAML 字典中逐级取值。
    current: Any = config
    # 遍历路径片段。
    for key in path:
        # 当前层不是字典时返回默认值。
        if not isinstance(current, dict):
            # 返回默认值。
            return default
        # 键不存在时返回默认值。
        if key not in current:
            # 返回默认值。
            return default
        # 进入下一层。
        current = current[key]
    # 返回最终值。
    return current


def _resolve_config_path(config_value: str) -> Path:
    # 未传配置时使用默认 Qwen3.5-2B 配置。
    raw_value = config_value or "qwen35_2b_llamacpp.yaml"
    # 创建 Path 对象。
    candidate = Path(raw_value)
    # 绝对路径直接返回。
    if candidate.is_absolute():
        # 返回绝对配置路径。
        return candidate
    # 相对路径按模型服务目录解析。
    return MODEL_SERVICE_DIR / candidate


def load_qwen35_2b_config(config_path: Path) -> Qwen35TwoBConfig:
    # 读取 YAML 配置字典。
    config = _load_yaml(config_path)
    # 构造 Qwen3.5-2B 配置对象。
    return Qwen35TwoBConfig(
        backend=str(_config_value(config, ["runtime", "backend"], "llamacpp")),
        model_id=str(_config_value(config, ["model", "id"], "Qwen3.5-2B-Q4_K_M")),
        gguf_repo=str(_config_value(config, ["model", "gguf_repo"], "bartowski/Qwen_Qwen3.5-2B-GGUF")),
        gguf_file=str(_config_value(config, ["model", "gguf_file"], "Qwen_Qwen3.5-2B-Q4_K_M.gguf")),
        model_dir=Path(str(_config_value(config, ["model", "model_dir"], MODEL_SERVICE_DIR / "models" / "qwen35_2b"))),
        model_path=Path(str(_config_value(config, ["model", "model_path"], MODEL_SERVICE_DIR / "models" / "qwen35_2b" / "Qwen_Qwen3.5-2B-Q4_K_M.gguf"))),
        release_api=str(_config_value(config, ["llamacpp", "release_api"], "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest")),
        asset_pattern=str(_config_value(config, ["llamacpp", "asset_pattern"], r"llama-.*-bin-win-cpu-x64\.zip")),
        runtime_dir=Path(str(_config_value(config, ["llamacpp", "runtime_dir"], MODEL_SERVICE_DIR / "runtimes" / "llama_cpp_win_cpu"))),
        server_exe=Path(str(_config_value(config, ["llamacpp", "server_exe"], MODEL_SERVICE_DIR / "runtimes" / "llama_cpp_win_cpu" / "llama-server.exe"))),
        host=str(_config_value(config, ["server", "host"], "127.0.0.1")),
        port=int(_config_value(config, ["server", "port"], 18000)),
        openai_base_url=str(_config_value(config, ["server", "openai_base_url"], "http://127.0.0.1:18000/v1")).rstrip("/"),
        api_key=str(_config_value(config, ["server", "api_key"], "EMPTY")),
        context_size=int(_config_value(config, ["generation", "context_size"], 8192)),
        threads=int(_config_value(config, ["generation", "threads"], 6)),
        gpu_layers=int(_config_value(config, ["generation", "gpu_layers"], 0)),
        temperature=float(_config_value(config, ["generation", "temperature"], 0.2)),
        top_p=float(_config_value(config, ["generation", "top_p"], 0.8)),
        predict=int(_config_value(config, ["generation", "predict"], 1024)),
        agent_max_tokens=int(_config_value(config, ["agent_env", "QWEN_AGENT_MAX_TOKENS"], 512)),
        agent_temperature=float(_config_value(config, ["agent_env", "QWEN_AGENT_TEMPERATURE"], 0.1)),
    )


def _download_file(url: str, target_path: Path, label: str) -> dict[str, Any]:
    # 创建目标目录。
    target_path.parent.mkdir(parents=True, exist_ok=True)
    # 已存在非空文件时直接复用。
    if target_path.exists() and target_path.stat().st_size > 0:
        # 返回已存在状态。
        return {"downloaded": False, "status": "exists", "label": label, "path": str(target_path), "bytes": target_path.stat().st_size}
    # 创建临时下载文件路径。
    temp_path = target_path.with_suffix(target_path.suffix + ".download")
    # 读取已经下载的临时文件大小，用于断点续传。
    resume_from = temp_path.stat().st_size if temp_path.exists() else 0
    # 创建请求头，避免部分站点拒绝默认 Python UA。
    headers = {"User-Agent": "SQL_RAG_Qwen35_2B_Local_Verifier"}
    # 如果已有临时文件，尝试使用 HTTP Range 从断点继续。
    if resume_from > 0:
        # 添加 Range 请求头。
        headers["Range"] = f"bytes={resume_from}-"
    # 创建下载请求。
    request = urllib.request.Request(url, headers=headers)
    # 打开远程响应。
    with urllib.request.urlopen(request, timeout=60) as response:
        # 读取 HTTP 状态码，206 表示服务端接受断点续传。
        status_code = getattr(response, "status", 200)
        # 如果服务端不接受 Range，就从头覆盖下载。
        append_mode = resume_from > 0 and status_code == 206
        # 根据是否断点续传选择写入模式。
        file_mode = "ab" if append_mode else "wb"
        # 打开本地临时文件。
        with temp_path.open(file_mode) as output:
            # 按块流式下载。
            while True:
                # 读取 8MB 数据块。
                chunk = response.read(8 * 1024 * 1024)
                # 空块表示下载结束。
                if not chunk:
                    # 跳出循环。
                    break
                # 写入本地文件。
                output.write(chunk)
    # 下载完成后原子替换目标文件。
    temp_path.replace(target_path)
    # 返回下载结果。
    return {
        "downloaded": True,
        "status": "ok",
        "label": label,
        "path": str(target_path),
        "bytes": target_path.stat().st_size,
        "resumed_from_bytes": resume_from if resume_from > 0 else 0,
    }


def _latest_llamacpp_asset(config: Qwen35TwoBConfig) -> dict[str, Any]:
    # 创建 GitHub release API 请求。
    request = urllib.request.Request(config.release_api, headers={"User-Agent": "SQL_RAG_Qwen35_2B_Local_Verifier"})
    # 读取 release JSON。
    with urllib.request.urlopen(request, timeout=30) as response:
        # 解析 release JSON。
        release = json.loads(response.read().decode("utf-8"))
    # 编译 asset 正则。
    pattern = re.compile(config.asset_pattern)
    # 遍历 release assets。
    for asset in release.get("assets", []):
        # 读取 asset 名称。
        name = str(asset.get("name", ""))
        # 名称匹配时返回下载信息。
        if pattern.fullmatch(name):
            # 返回 asset 信息。
            return {
                "release": release.get("tag_name", ""),
                "name": name,
                "url": asset.get("browser_download_url", ""),
                "size": asset.get("size", 0),
            }
    # 没找到资产时抛出明确错误。
    raise RuntimeError(f"未在 llama.cpp latest release 找到匹配资产：{config.asset_pattern}")


def ensure_llamacpp_runtime(config: Qwen35TwoBConfig) -> dict[str, Any]:
    # 如果 llama-server 已经存在，直接返回。
    if config.server_exe.exists():
        # 返回已存在状态。
        return {"ready": True, "downloaded": False, "server_exe": str(config.server_exe), "status": "exists"}
    # 查询最新 llama.cpp Windows CPU asset。
    asset = _latest_llamacpp_asset(config)
    # 构造 zip 下载路径。
    zip_path = config.runtime_dir.parent / asset["name"]
    # 下载 llama.cpp zip。
    download_result = _download_file(asset["url"], zip_path, "llama.cpp_windows_cpu_runtime")
    # 创建运行时目录。
    config.runtime_dir.mkdir(parents=True, exist_ok=True)
    # 解压 zip。
    with zipfile.ZipFile(zip_path, "r") as archive:
        # 解压全部文件到运行时目录。
        archive.extractall(config.runtime_dir)
    # 查找解压后的 llama-server.exe。
    candidates = list(config.runtime_dir.rglob("llama-server.exe"))
    # 如果没有找到，抛出明确错误。
    if not candidates:
        # 抛出运行时缺失错误。
        raise FileNotFoundError(f"llama.cpp 运行时已解压，但未找到 llama-server.exe：{config.runtime_dir}")
    # 如果配置里的 server_exe 不存在，把第一个候选复制到标准位置。
    if not config.server_exe.exists():
        # 创建父目录。
        config.server_exe.parent.mkdir(parents=True, exist_ok=True)
        # 复制候选 server 到标准路径。
        shutil.copy2(candidates[0], config.server_exe)
    # 返回运行时准备状态。
    return {
        "ready": config.server_exe.exists(),
        "downloaded": bool(download_result.get("downloaded")),
        "release": asset.get("release", ""),
        "asset": asset.get("name", ""),
        "server_exe": str(config.server_exe),
        "zip": str(zip_path),
    }


def qwen35_2b_model_url(config: Qwen35TwoBConfig) -> str:
    # 构造 Hugging Face resolve 下载地址。
    return f"https://huggingface.co/{config.gguf_repo}/resolve/main/{config.gguf_file}?download=true"


def ensure_qwen35_2b_model(config: Qwen35TwoBConfig) -> dict[str, Any]:
    # 创建模型目录。
    config.model_dir.mkdir(parents=True, exist_ok=True)
    # 构造模型下载地址。
    url = qwen35_2b_model_url(config)
    # 下载 GGUF 模型文件。
    result = _download_file(url, config.model_path, "qwen35_2b_gguf_q4_k_m")
    # 补充模型元数据。
    result["model_id"] = config.model_id
    # 补充仓库信息。
    result["repo"] = config.gguf_repo
    # 补充文件名。
    result["file"] = config.gguf_file
    # 返回模型准备状态。
    return result


def build_llamacpp_server_command(config: Qwen35TwoBConfig) -> list[str]:
    # 构建 llama-server OpenAI-compatible 启动命令。
    return [
        str(config.server_exe),
        "-m",
        str(config.model_path),
        "--host",
        config.host,
        "--port",
        str(config.port),
        "-c",
        str(config.context_size),
        "-t",
        str(config.threads),
        "-ngl",
        str(config.gpu_layers),
        "--temp",
        str(config.temperature),
        "--top-p",
        str(config.top_p),
        "-n",
        str(config.predict),
    ]


def _quote_command(command: list[str]) -> str:
    # 把命令转成可复制的展示字符串。
    return " ".join(f'"{part}"' if " " in part else part for part in command)


def check_qwen35_2b_health(config: Qwen35TwoBConfig, timeout: float = 5.0) -> dict[str, Any]:
    # 拼接 OpenAI-compatible /models 地址。
    url = f"{config.openai_base_url}/models"
    # 创建 HTTP 请求。
    request = urllib.request.Request(url)
    # 如果配置了 API key，则带上 Authorization。
    if config.api_key:
        # 添加 Bearer token。
        request.add_header("Authorization", f"Bearer {config.api_key}")
    # 访问模型服务。
    try:
        # 打开 HTTP 响应。
        with urllib.request.urlopen(request, timeout=timeout) as response:
            # 解析响应 JSON。
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        # 服务不可达时返回失败。
        return {"ready": False, "status": "unreachable", "model_server": config.openai_base_url, "error": str(exc)}
    except json.JSONDecodeError as exc:
        # 响应不是 JSON 时返回失败。
        return {"ready": False, "status": "invalid_json", "model_server": config.openai_base_url, "error": str(exc)}
    # 读取模型列表。
    models = [str(item.get("id", "")) for item in payload.get("data", []) if isinstance(item, dict)]
    # 返回健康状态。
    return {"ready": True, "status": "ok", "model_server": config.openai_base_url, "models": models}


def start_qwen35_2b_server(config: Qwen35TwoBConfig) -> dict[str, Any]:
    # 先检查模型服务是否已经可用。
    health = check_qwen35_2b_health(config, timeout=2.0)
    # 已经可用时直接返回。
    if health.get("ready"):
        # 返回已运行状态。
        return {"started": False, "status": "already_running", "health": health}
    # 检查 llama-server 是否存在。
    if not config.server_exe.exists():
        # 抛出运行时缺失错误。
        raise FileNotFoundError(f"缺少 llama-server.exe，请先执行 prepare：{config.server_exe}")
    # 检查模型文件是否存在。
    if not config.model_path.exists():
        # 抛出模型缺失错误。
        raise FileNotFoundError(f"缺少 Qwen3.5-2B GGUF 模型，请先执行 prepare：{config.model_path}")
    # 构建启动命令。
    command = build_llamacpp_server_command(config)
    # 构造环境变量。
    env = os.environ.copy()
    # 设置 llama.cpp 日志使用 UTF-8。
    env.setdefault("LLAMA_LOG_COLORS", "0")
    # 启动隐藏后台服务。
    process = subprocess.Popen(
        command,
        cwd=str(config.runtime_dir),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0,
    )
    # 轮询等待服务 ready。
    final_health: dict[str, Any] = {}
    # 最多等待 90 秒。
    for _ in range(90):
        # 等待 1 秒。
        time.sleep(1)
        # 检查健康状态。
        final_health = check_qwen35_2b_health(config, timeout=2.0)
        # 服务 ready 时停止等待。
        if final_health.get("ready"):
            # 跳出循环。
            break
        # 如果进程已经退出，停止等待。
        if process.poll() is not None:
            # 跳出循环。
            break
    # 返回启动结果。
    return {
        "started": process.poll() is None,
        "pid": process.pid,
        "command": command,
        "command_text": _quote_command(command),
        "health": final_health,
    }


def build_agent_env_patch(config: Qwen35TwoBConfig) -> dict[str, str]:
    # 返回接入现有 BusinessBrainRuntime 所需的 .env 片段。
    return {
        "QWEN_AGENT_MODEL": config.model_id,
        "QWEN_AGENT_MODEL_SERVER": config.openai_base_url,
        "QWEN_AGENT_API_KEY": config.api_key,
        "QWEN_AGENT_MAX_TOKENS": str(config.agent_max_tokens),
        "QWEN_AGENT_TEMPERATURE": str(config.agent_temperature),
    }


def _update_env_file(env_path: Path, updates: dict[str, str]) -> dict[str, Any]:
    # 如果 .env 存在则读取现有行。
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    # 记录已经更新过的 key。
    seen: set[str] = set()
    # 准备新行列表。
    new_lines: list[str] = []
    # 遍历原始行。
    for line in lines:
        # 跳过不含等号或注释行。
        if "=" not in line or line.strip().startswith("#"):
            # 原样保留。
            new_lines.append(line)
            # 继续下一行。
            continue
        # 读取 key。
        key = line.split("=", 1)[0].strip()
        # 如果 key 需要更新。
        if key in updates:
            # 写入新值。
            new_lines.append(f"{key}={updates[key]}")
            # 标记已处理。
            seen.add(key)
        else:
            # 原样保留其他配置。
            new_lines.append(line)
    # 追加原文件中没有的新 key。
    for key, value in updates.items():
        # 没处理过才追加。
        if key not in seen:
            # 添加配置行。
            new_lines.append(f"{key}={value}")
    # 写回 .env。
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    # 返回更新摘要。
    return {"env_path": str(env_path), "updated": updates}


def build_qwen35_2b_arg_parser() -> argparse.ArgumentParser:
    # 创建 Qwen3.5-2B 命令行解析器。
    parser = argparse.ArgumentParser(description="SQL_RAG Qwen3.5-2B 本机 GGUF 模型服务辅助。")
    # 添加全局配置参数。
    parser.add_argument("--config", default="qwen35_2b_llamacpp.yaml", help="Qwen3.5-2B YAML 配置文件。")
    # 创建子命令。
    subparsers = parser.add_subparsers(dest="command", required=True)
    # 添加 runtime 拉取命令。
    subparsers.add_parser("pull-runtime", help="下载并解压 llama.cpp Windows CPU 运行时。")
    # 添加模型拉取命令。
    subparsers.add_parser("pull-model", help="下载 Qwen3.5-2B Q4_K_M GGUF 模型。")
    # 添加完整准备命令。
    subparsers.add_parser("prepare", help="下载 llama.cpp 运行时和 Qwen3.5-2B GGUF 模型。")
    # 添加启动命令展示。
    subparsers.add_parser("serve-command", help="输出 llama-server 启动命令。")
    # 添加启动服务命令。
    subparsers.add_parser("start", help="启动 Qwen3.5-2B 本机 OpenAI-compatible 模型服务。")
    # 添加健康检查命令。
    subparsers.add_parser("health", help="检查 Qwen3.5-2B 本机模型服务。")
    # 添加 env 输出命令。
    subparsers.add_parser("env", help="输出接入业务脑所需 QWEN_AGENT_* 配置。")
    # 添加 env 应用命令。
    subparsers.add_parser("apply-env", help="把 Qwen3.5-2B 模型服务配置写入 SQL_RAG/.env。")
    # 返回解析器。
    return parser


def run_qwen35_2b_cli(argv: Sequence[str], sql_rag_dir: Path = SQL_RAG_DIR) -> int:
    # 构建命令行解析器。
    parser = build_qwen35_2b_arg_parser()
    # 解析参数。
    args = parser.parse_args(list(argv))
    # 解析配置路径。
    config_path = _resolve_config_path(args.config)
    # 读取配置对象。
    config = load_qwen35_2b_config(config_path)
    # 拉取 llama.cpp runtime。
    if args.command == "pull-runtime":
        # 执行 runtime 准备。
        _print_json(ensure_llamacpp_runtime(config))
        # 返回成功。
        return 0
    # 拉取 Qwen3.5-2B 模型。
    if args.command == "pull-model":
        # 执行模型下载。
        _print_json(ensure_qwen35_2b_model(config))
        # 返回成功。
        return 0
    # 完整准备 runtime 和模型。
    if args.command == "prepare":
        # 先准备 llama.cpp runtime。
        runtime_result = ensure_llamacpp_runtime(config)
        # 再准备模型文件。
        model_result = ensure_qwen35_2b_model(config)
        # 打印完整准备结果。
        _print_json({"runtime": runtime_result, "model": model_result})
        # 返回成功。
        return 0
    # 输出启动命令。
    if args.command == "serve-command":
        # 构建启动命令。
        command = build_llamacpp_server_command(config)
        # 打印命令。
        _print_json({"command": command, "command_text": _quote_command(command)})
        # 返回成功。
        return 0
    # 启动模型服务。
    if args.command == "start":
        # 启动 llama-server。
        result = start_qwen35_2b_server(config)
        # 打印启动结果。
        _print_json(result)
        # 服务 ready 时返回 0。
        return 0 if result.get("health", {}).get("ready") else 2
    # 健康检查。
    if args.command == "health":
        # 执行健康检查。
        result = check_qwen35_2b_health(config)
        # 打印健康检查。
        _print_json(result)
        # ready 时返回 0。
        return 0 if result.get("ready") else 2
    # 输出 env。
    if args.command == "env":
        # 打印 env 片段。
        _print_json({"env": build_agent_env_patch(config)})
        # 返回成功。
        return 0
    # 应用 env。
    if args.command == "apply-env":
        # 写入 SQL_RAG/.env。
        result = _update_env_file(sql_rag_dir / ".env", build_agent_env_patch(config))
        # 打印更新结果。
        _print_json(result)
        # 返回成功。
        return 0
    # 理论上不会走到这里。
    parser.error(f"未知 Qwen3.5-2B 命令：{args.command}")
    # 返回错误。
    return 2
