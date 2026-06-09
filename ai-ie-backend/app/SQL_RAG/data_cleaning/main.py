# -*- coding: utf-8 -*-
"""兼容旧路径的 SQL_RAG 主入口转发器。"""

# 修改日期：2026-06-02 10:42:00。
# 修改理由：主接口汇总入口已上移到 SQL_RAG/main.py；保留本文件只为兼容旧命令，避免历史脚本直接运行时失效。

# 导入 importlib.util，用于按文件路径加载根目录 main.py。
import importlib.util
# 导入 Path，用于定位 SQL_RAG 根目录。
from pathlib import Path
# 导入 Sequence，用于标注命令行参数类型。
from typing import Sequence

# 定位 SQL_RAG 根目录。
SQL_RAG_DIR = Path(__file__).resolve().parents[1]
# 定位新的根目录主入口文件。
ROOT_MAIN_PATH = SQL_RAG_DIR / "main.py"
# 创建根目录主入口模块加载规格。
ROOT_MAIN_SPEC = importlib.util.spec_from_file_location("sql_rag_root_main", ROOT_MAIN_PATH)
# 主入口规格不存在时直接报错。
if ROOT_MAIN_SPEC is None or ROOT_MAIN_SPEC.loader is None:
    # 抛出明确错误，避免静默失败。
    raise RuntimeError(f"无法加载 SQL_RAG 根目录主入口：{ROOT_MAIN_PATH}")
# 根据加载规格创建模块对象。
ROOT_MAIN_MODULE = importlib.util.module_from_spec(ROOT_MAIN_SPEC)
# 执行根目录主入口模块。
ROOT_MAIN_SPEC.loader.exec_module(ROOT_MAIN_MODULE)


def main(argv: Sequence[str] | None = None) -> int:
    # 转发到 SQL_RAG/main.py 的 main 函数。
    return ROOT_MAIN_MODULE.main(argv)


# 保持旧路径直接运行能力。
if __name__ == "__main__":
    # 把根目录 main 的退出码交给系统进程。
    raise SystemExit(main())

