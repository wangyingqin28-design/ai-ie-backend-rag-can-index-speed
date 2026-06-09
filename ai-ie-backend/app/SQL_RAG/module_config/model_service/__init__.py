# -*- coding: utf-8 -*-
"""Qwen3.5 本地模型服务部署配置和检查入口。"""

# 修改日期：2026-06-03 10:20:00。
# 修改理由：为新显卡环境准备模型拉取、启动命令生成和 OpenAI-compatible 健康检查逻辑。

# 导入模型服务命令行运行入口。
from .model_service_runtime import run_model_service_cli
# 导入 Qwen3.5-2B 本机验证模型运行入口。
from .qwen35_2b_runtime import run_qwen35_2b_cli

# 声明对外导出的稳定入口。
__all__ = ["run_model_service_cli", "run_qwen35_2b_cli"]
