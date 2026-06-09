# -*- coding: utf-8 -*-
"""Qwen3.5 本地模型服务部署运行辅助。"""

# 修改日期：2026-06-03 10:20:00。
# 修改理由：按统一框架标准补齐模型拉取、GPU 档位识别、vLLM/SGLang 启动命令和服务健康检查，不把部署临时逻辑塞进 SQL_RAG/main.py。

# 导入 argparse，用于构建 model-service 子命令。
import argparse
# 导入 JSON，用于输出机器可读的部署摘要。
import json
# 导入 os，用于读取本地环境变量兜底值。
import os
# 导入 subprocess，用于探测 nvidia-smi 和生成可执行命令检查。
import subprocess
# 导入 sys，用于设置 Windows 终端 UTF-8 输出。
import sys
# 导入 urllib.error，用于区分模型服务健康检查异常。
import urllib.error
# 导入 urllib.request，用于访问 OpenAI-compatible /v1/models。
import urllib.request
# 导入 dataclass，用于承载模型服务健康状态。
from dataclasses import dataclass
# 导入 Path，用于定位配置文件和模型目录。
from pathlib import Path
# 导入 Any，用于标注 YAML 配置字典。
from typing import Any, Sequence

# 导入 PyYAML，用于读取 module_config 下的 YAML 标准配置。
import yaml

# 定位当前模型服务配置目录。
MODEL_SERVICE_DIR = Path(__file__).resolve().parent
# 定位 module_config 根目录。
MODULE_CONFIG_DIR = MODEL_SERVICE_DIR.parent
# 定位 SQL_RAG 根目录。
SQL_RAG_DIR = MODULE_CONFIG_DIR.parent

# Windows 终端默认 GBK 时可能无法打印模型名和中文提示，这里统一切到 UTF-8。
if hasattr(sys.stdout, "reconfigure"):
    # 只影响当前进程的标准输出编码。
    sys.stdout.reconfigure(encoding="utf-8")


@dataclass(frozen=True)
class ModelServiceHealth:
    # 记录健康检查是否整体可用。
    ready: bool
    # 记录模型服务地址。
    model_server: str
    # 记录期望模型名。
    expected_model: str
    # 记录服务端返回的模型列表。
    served_models: list[str]
    # 记录详细检查项。
    checks: dict[str, Any]


def _load_yaml_config(config_path: Path) -> dict[str, Any]:
    # 检查配置文件是否存在。
    if not config_path.exists():
        # 缺配置时直接抛出明确错误。
        raise FileNotFoundError(f"模型服务配置文件不存在：{config_path}")
    # 使用 UTF-8 读取 YAML 文本。
    text = config_path.read_text(encoding="utf-8")
    # 解析 YAML 文本。
    data = yaml.safe_load(text) or {}
    # YAML 顶层必须是字典。
    if not isinstance(data, dict):
        # 非字典配置无法承载模型服务字段。
        raise ValueError(f"模型服务配置必须是 YAML 对象：{config_path}")
    # 返回配置字典。
    return data


def _resolve_config_path(config_value: str) -> Path:
    # 把空配置解析为默认 vLLM 配置。
    raw_value = config_value or "qwen35_vllm.yaml"
    # 构造 Path 对象。
    candidate = Path(raw_value)
    # 绝对路径直接返回。
    if candidate.is_absolute():
        # 返回绝对配置路径。
        return candidate
    # 相对路径优先按模型服务配置目录解析。
    return MODEL_SERVICE_DIR / candidate


def _config_value(config: dict[str, Any], path: Sequence[str], default: Any = None) -> Any:
    # 从 YAML 字典按路径逐级读取。
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


def _normalize_url(url: str) -> str:
    # 去掉地址两侧空白。
    normalized = (url or "").strip()
    # 去掉尾部斜杠，方便拼接 /models。
    return normalized.rstrip("/")


def _run_nvidia_smi() -> dict[str, Any]:
    # 构造 nvidia-smi 查询命令。
    command = [
        "nvidia-smi",
        "--query-gpu=name,memory.total,driver_version,cuda_version",
        "--format=csv,noheader,nounits",
    ]
    # 捕获命令执行结果。
    try:
        # 调用 nvidia-smi 探测 NVIDIA GPU。
        completed = subprocess.run(command, text=True, capture_output=True, timeout=10)
    except FileNotFoundError:
        # 当前机器没有 nvidia-smi。
        return {"available": False, "reason": "nvidia-smi_not_found", "gpus": []}
    except subprocess.SubprocessError as exc:
        # nvidia-smi 执行超时或异常。
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}", "gpus": []}
    # 非 0 退出码表示驱动或命令不可用。
    if completed.returncode != 0:
        # 返回 stderr 便于定位驱动问题。
        return {"available": False, "reason": completed.stderr.strip() or completed.stdout.strip(), "gpus": []}
    # 准备 GPU 列表。
    gpus: list[dict[str, Any]] = []
    # 遍历 nvidia-smi 输出行。
    for line in completed.stdout.splitlines():
        # 去掉空白行。
        stripped = line.strip()
        # 跳过空行。
        if not stripped:
            # 继续下一行。
            continue
        # 按 CSV 解析字段。
        parts = [part.strip() for part in stripped.split(",")]
        # 字段不足时跳过异常行。
        if len(parts) < 4:
            # 继续下一行。
            continue
        # 读取显卡名称。
        name = parts[0]
        # 读取显存 MB。
        memory_mb = int(float(parts[1]))
        # 写入 GPU 信息。
        gpus.append(
            {
                "name": name,
                "memory_total_mb": memory_mb,
                "memory_total_gb": round(memory_mb / 1024, 2),
                "driver_version": parts[2],
                "cuda_version": parts[3],
            }
        )
    # 返回 NVIDIA GPU 探测结果。
    return {"available": bool(gpus), "reason": "", "gpus": gpus}


def detect_gpu_profile() -> dict[str, Any]:
    # 调用 nvidia-smi 探测 GPU。
    gpu_result = _run_nvidia_smi()
    # 没有 NVIDIA GPU 时返回 CPU/远程模型档位。
    if not gpu_result.get("available"):
        # 返回不可本地跑 vLLM 的明确结论。
        return {
            "tier": "no_cuda_gpu",
            "can_run_qwen35_35b": False,
            "recommended_action": "当前环境只适合运行 SQL_RAG 后端或调用远程 OpenAI-compatible Qwen 服务。",
            "gpu_probe": gpu_result,
        }
    # 读取最大单卡显存。
    max_vram_gb = max(float(gpu.get("memory_total_gb", 0.0)) for gpu in gpu_result["gpus"])
    # 读取 GPU 数量。
    gpu_count = len(gpu_result["gpus"])
    # 80GB 或多卡环境适合 Qwen3.5-35B-A3B 试点。
    if max_vram_gb >= 80 or gpu_count >= 2:
        # 返回生产试点档位。
        tier = "qwen35_35b_ready"
        # 返回可运行结论。
        can_run = True
        # 返回建议。
        action = "建议使用 Qwen/Qwen3.5-35B-A3B-FP8 + vLLM OpenAI-compatible 服务，先用 64K 上下文压测。"
    # 48GB 单卡可尝试 FP8 或更短上下文。
    elif max_vram_gb >= 48:
        # 返回边界试点档位。
        tier = "qwen35_35b_trial"
        # 返回可尝试结论。
        can_run = True
        # 返回建议。
        action = "可尝试 Qwen3.5-35B-A3B-FP8，建议降低 max_model_len 并做真实吞吐压测。"
    # 24GB 单卡不建议跑 35B。
    elif max_vram_gb >= 24:
        # 返回小模型档位。
        tier = "small_qwen_local_only"
        # 返回不可运行 35B 结论。
        can_run = False
        # 返回建议。
        action = "不建议跑 35B，建议 Qwen3.5-4B/9B 量化模型或把 35B 放到更大 GPU 机器。"
    # 更小显存只能跑轻量模型。
    else:
        # 返回轻量模型档位。
        tier = "lightweight_only"
        # 返回不可运行 35B 结论。
        can_run = False
        # 返回建议。
        action = "只建议跑 Qwen3.5-0.8B/2B 量化模型，业务脑生产模型需远程 GPU 服务。"
    # 返回完整档位信息。
    return {
        "tier": tier,
        "can_run_qwen35_35b": can_run,
        "recommended_action": action,
        "gpu_probe": gpu_result,
    }


def build_model_pull_command(config: dict[str, Any]) -> list[str]:
    # 读取模型来源。
    source = str(_config_value(config, ["model", "source"], "modelscope")).lower()
    # 读取模型 ID。
    model_id = str(_config_value(config, ["model", "id"], "Qwen/Qwen3.5-35B-A3B-FP8"))
    # 读取本地模型目录。
    local_dir = str(_config_value(config, ["model", "local_dir"], "D:/models/Qwen3.5-35B-A3B-FP8"))
    # 国内默认使用 ModelScope 官方 CLI。
    if source == "modelscope":
        # 返回 modelscope download 命令。
        return ["modelscope", "download", "--model", model_id, "--local_dir", local_dir]
    # HuggingFace 模式使用 huggingface-cli。
    if source == "huggingface":
        # 返回 huggingface-cli download 命令。
        return ["huggingface-cli", "download", model_id, "--local-dir", local_dir]
    # 其他来源暂不自动拼命令。
    raise ValueError(f"不支持的模型来源：{source}")


def build_vllm_serve_command(config: dict[str, Any]) -> list[str]:
    # 读取模型 ID。
    model_id = str(_config_value(config, ["model", "id"], "Qwen/Qwen3.5-35B-A3B-FP8"))
    # 读取服务 host。
    host = str(_config_value(config, ["server", "host"], "0.0.0.0"))
    # 读取服务端口。
    port = str(_config_value(config, ["server", "port"], 8000))
    # 读取最大上下文。
    max_model_len = str(_config_value(config, ["vllm", "max_model_len"], 65536))
    # 读取张量并行卡数。
    tensor_parallel_size = str(_config_value(config, ["vllm", "tensor_parallel_size"], 1))
    # 创建 vLLM 官方 serve 命令。
    command = [
        "vllm",
        "serve",
        model_id,
        "--host",
        host,
        "--port",
        port,
        "--max-model-len",
        max_model_len,
        "--tensor-parallel-size",
        tensor_parallel_size,
        "--reasoning-parser",
        str(_config_value(config, ["vllm", "reasoning_parser"], "qwen3")),
        "--enable-auto-tool-choice",
        "--tool-call-parser",
        str(_config_value(config, ["vllm", "tool_call_parser"], "qwen3_coder")),
    ]
    # Qwen 官方示例建议语言模型-only 路线时追加参数。
    if bool(_config_value(config, ["vllm", "language_model_only"], True)):
        # 追加 language-model-only 参数。
        command.append("--language-model-only")
    # 读取可选 GPU 显存利用率。
    gpu_memory_utilization = _config_value(config, ["vllm", "gpu_memory_utilization"], None)
    # 配置了显存利用率时追加参数。
    if gpu_memory_utilization is not None:
        # 追加显存利用率参数。
        command.extend(["--gpu-memory-utilization", str(gpu_memory_utilization)])
    # 返回 vLLM 启动命令。
    return command


def build_sglang_serve_command(config: dict[str, Any]) -> list[str]:
    # 读取模型 ID。
    model_id = str(_config_value(config, ["model", "id"], "Qwen/Qwen3.5-35B-A3B-FP8"))
    # 读取服务 host。
    host = str(_config_value(config, ["server", "host"], "0.0.0.0"))
    # 读取服务端口。
    port = str(_config_value(config, ["server", "port"], 8000))
    # 读取最大上下文。
    context_length = str(_config_value(config, ["sglang", "context_length"], 65536))
    # 读取张量并行卡数。
    tensor_parallel_size = str(_config_value(config, ["sglang", "tensor_parallel_size"], 1))
    # 返回 SGLang OpenAI-compatible 启动命令。
    return [
        "python",
        "-m",
        "sglang.launch_server",
        "--model-path",
        model_id,
        "--host",
        host,
        "--port",
        port,
        "--context-length",
        context_length,
        "--tp",
        tensor_parallel_size,
    ]


def build_serve_command(config: dict[str, Any]) -> list[str]:
    # 读取推理后端。
    backend = str(_config_value(config, ["runtime", "backend"], "vllm")).lower()
    # vLLM 后端生成 vLLM 命令。
    if backend == "vllm":
        # 返回 vLLM serve 命令。
        return build_vllm_serve_command(config)
    # SGLang 后端生成 SGLang 命令。
    if backend == "sglang":
        # 返回 SGLang launch_server 命令。
        return build_sglang_serve_command(config)
    # 其他后端暂不支持。
    raise ValueError(f"不支持的模型服务后端：{backend}")


def build_env_patch(config: dict[str, Any]) -> dict[str, str]:
    # 读取模型 ID。
    model_id = str(_config_value(config, ["model", "id"], "Qwen/Qwen3.5-35B-A3B-FP8"))
    # 读取服务端地址。
    model_server = str(_config_value(config, ["server", "openai_base_url"], "http://127.0.0.1:8000/v1"))
    # 读取 API key。
    api_key = str(_config_value(config, ["server", "api_key"], "EMPTY"))
    # 返回 SQL_RAG 需要写入 .env 的模型接入参数。
    return {
        "QWEN_AGENT_MODEL": model_id,
        "QWEN_AGENT_MODEL_SERVER": model_server,
        "QWEN_AGENT_API_KEY": api_key,
    }


def check_openai_compatible_models(model_server: str, api_key: str, timeout: float = 5.0) -> dict[str, Any]:
    # 标准化模型服务地址。
    base_url = _normalize_url(model_server)
    # 未配置服务地址时返回失败。
    if not base_url:
        # 返回未配置状态。
        return {"ready": False, "status": "not_configured", "models": [], "error": "model_server_empty"}
    # 拼接 /models endpoint。
    url = f"{base_url}/models"
    # 创建 HTTP 请求。
    request = urllib.request.Request(url)
    # 配置 API key 时带上 Authorization 头。
    if api_key:
        # 设置 Bearer token。
        request.add_header("Authorization", f"Bearer {api_key}")
    # 尝试访问模型服务。
    try:
        # 打开 HTTP 响应。
        with urllib.request.urlopen(request, timeout=timeout) as response:
            # 读取响应文本。
            body = response.read().decode("utf-8")
            # 解析 JSON。
            payload = json.loads(body)
    except urllib.error.URLError as exc:
        # 网络或服务不可达时返回失败。
        return {"ready": False, "status": "unreachable", "models": [], "error": str(exc)}
    except json.JSONDecodeError as exc:
        # 响应不是 JSON 时返回失败。
        return {"ready": False, "status": "invalid_json", "models": [], "error": str(exc)}
    # 提取 OpenAI-compatible 模型列表。
    models = [str(item.get("id", "")) for item in payload.get("data", []) if isinstance(item, dict)]
    # 返回模型服务健康状态。
    return {"ready": True, "status": "ok", "models": models, "error": ""}


def check_model_service_health(config: dict[str, Any]) -> ModelServiceHealth:
    # 读取期望模型名。
    expected_model = str(_config_value(config, ["model", "id"], "Qwen/Qwen3.5-35B-A3B-FP8"))
    # 读取服务地址。
    model_server = str(_config_value(config, ["server", "openai_base_url"], "http://127.0.0.1:8000/v1"))
    # 读取 API key。
    api_key = str(_config_value(config, ["server", "api_key"], "EMPTY"))
    # 检查 /v1/models。
    model_check = check_openai_compatible_models(model_server=model_server, api_key=api_key)
    # 读取服务端模型列表。
    served_models = list(model_check.get("models", []))
    # 如果服务端不返回模型列表，只要 /models 可达也认为模型服务基础可用。
    model_name_ok = expected_model in served_models or not served_models
    # 组合整体 ready 状态。
    ready = bool(model_check.get("ready")) and model_name_ok
    # 返回结构化健康对象。
    return ModelServiceHealth(
        ready=ready,
        model_server=model_server,
        expected_model=expected_model,
        served_models=served_models,
        checks={
            "openai_models_endpoint": model_check,
            "expected_model_visible": model_name_ok,
        },
    )


def _print_json(value: Any) -> None:
    # 用 UTF-8 JSON 打印值。
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _quote_command(command: list[str]) -> str:
    # Windows 和 Linux 都能读懂的简单命令展示格式。
    return " ".join(f'"{part}"' if " " in part else part for part in command)


def build_model_service_arg_parser() -> argparse.ArgumentParser:
    # 创建模型服务子命令解析器。
    parser = argparse.ArgumentParser(description="SQL_RAG Qwen3.5 本地模型服务部署辅助。")
    # 添加子命令集合。
    subparsers = parser.add_subparsers(dest="command", required=True)
    # 添加 GPU profile 命令。
    subparsers.add_parser("profile", help="检测当前机器是否适合跑 Qwen3.5-35B-A3B。")
    # 添加模型拉取命令输出。
    pull_parser = subparsers.add_parser("pull-command", help="输出 ModelScope/HuggingFace 模型拉取命令。")
    # 添加配置文件参数。
    pull_parser.add_argument("--config", default="qwen35_vllm.yaml", help="模型服务 YAML 配置文件。")
    # 添加是否执行拉取命令。
    pull_parser.add_argument("--execute", action="store_true", help="真实执行模型拉取命令。")
    # 添加启动命令输出。
    serve_parser = subparsers.add_parser("serve-command", help="输出 vLLM/SGLang OpenAI-compatible 启动命令。")
    # 添加配置文件参数。
    serve_parser.add_argument("--config", default="qwen35_vllm.yaml", help="模型服务 YAML 配置文件。")
    # 添加 env 输出命令。
    env_parser = subparsers.add_parser("env", help="输出 SQL_RAG 接入本地模型服务需要的 .env 片段。")
    # 添加配置文件参数。
    env_parser.add_argument("--config", default="qwen35_vllm.yaml", help="模型服务 YAML 配置文件。")
    # 添加健康检查命令。
    health_parser = subparsers.add_parser("health", help="检查 OpenAI-compatible 模型服务是否可用。")
    # 添加配置文件参数。
    health_parser.add_argument("--config", default="qwen35_vllm.yaml", help="模型服务 YAML 配置文件。")
    # 返回解析器。
    return parser


def run_model_service_cli(argv: Sequence[str], sql_rag_dir: Path = SQL_RAG_DIR) -> int:
    # 当前参数保留 sql_rag_dir，方便 main.py 统一传入根目录。
    _ = sql_rag_dir
    # 构建解析器。
    parser = build_model_service_arg_parser()
    # 解析命令行参数。
    args = parser.parse_args(list(argv))
    # profile 命令直接检测 GPU。
    if args.command == "profile":
        # 打印 GPU 档位。
        _print_json(detect_gpu_profile())
        # 返回成功。
        return 0
    # 后续命令都需要读取配置。
    config_path = _resolve_config_path(getattr(args, "config", "qwen35_vllm.yaml"))
    # 读取 YAML 配置。
    config = _load_yaml_config(config_path)
    # 输出模型拉取命令。
    if args.command == "pull-command":
        # 构建拉取命令。
        command = build_model_pull_command(config)
        # 执行模式下直接调用命令。
        if args.execute:
            # 执行拉取命令并把输出交给当前终端。
            completed = subprocess.run(command)
            # 返回真实命令退出码。
            return int(completed.returncode)
        # 打印命令摘要。
        _print_json({"config": str(config_path), "command": command, "command_text": _quote_command(command)})
        # 返回成功。
        return 0
    # 输出模型启动命令。
    if args.command == "serve-command":
        # 构建启动命令。
        command = build_serve_command(config)
        # 打印命令摘要。
        _print_json({"config": str(config_path), "command": command, "command_text": _quote_command(command)})
        # 返回成功。
        return 0
    # 输出 .env 片段。
    if args.command == "env":
        # 构建 .env 键值。
        env_patch = build_env_patch(config)
        # 打印 .env 片段。
        _print_json({"config": str(config_path), "env": env_patch})
        # 返回成功。
        return 0
    # 检查模型服务健康。
    if args.command == "health":
        # 构建健康检查。
        health = check_model_service_health(config)
        # 打印健康检查。
        _print_json(
            {
                "ready": health.ready,
                "model_server": health.model_server,
                "expected_model": health.expected_model,
                "served_models": health.served_models,
                "checks": health.checks,
            }
        )
        # 健康时返回 0。
        return 0 if health.ready else 2
    # 理论上不会走到这里。
    parser.error(f"未知模型服务命令：{args.command}")
    # 返回错误。
    return 2

