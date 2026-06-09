# -*- coding: utf-8 -*-
"""通用工具函数。"""

# 修改日期：2026-06-01 13:29:35。
# 修改理由：补齐多文档全局融合需要的归一化哈希和向量相似度工具。

# 导入哈希库，用于生成文档和分块的稳定 ID。
import hashlib
# 导入正则库，用于归一化问题、答案和实体文本。
import re
# 导入时间工具，用于生成统一时间字符串。
from datetime import datetime, timezone
# 导入路径类型，保证 Windows 路径处理稳定。
from pathlib import Path
# 导入任意类型标注，避免工具函数耦合具体业务模型。
from typing import Any


def now_iso() -> str:
    # 用 UTC 时间生成 ISO 字符串，避免不同机器时区导致结果不一致。
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_text(text: str) -> str:
    # 把文本按 UTF-8 编码后计算 SHA256。
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_for_hash(text: str) -> str:
    # 把文本转成小写，兼容英文、数字和中文混排场景。
    lowered = text.lower()
    # 去掉 Markdown 标记和常见中文标点。
    no_punctuation = re.sub(r"[`*_#>\[\]（）(){}:：;；,，.。!！?？\"'“”‘’、\\/\-|]+", "", lowered)
    # 压缩所有空白，避免换行差异影响同义问题识别。
    compact = re.sub(r"\s+", "", no_punctuation)
    # 返回归一化文本。
    return compact


def cosine_similarity(left: list[float], right: list[float]) -> float:
    # 任意一边为空向量时相似度为 0。
    if not left or not right:
        # 返回 0。
        return 0.0
    # 只比较两边共同长度，避免模型维度变化时报错。
    length = min(len(left), len(right))
    # 计算点积。
    dot = sum(left[index] * right[index] for index in range(length))
    # 计算左向量范数。
    left_norm = sum(left[index] * left[index] for index in range(length)) ** 0.5
    # 计算右向量范数。
    right_norm = sum(right[index] * right[index] for index in range(length)) ** 0.5
    # 范数为 0 时不能相除。
    if left_norm == 0 or right_norm == 0:
        # 返回 0。
        return 0.0
    # 返回余弦相似度。
    return round(dot / (left_norm * right_norm), 6)


def stable_id(prefix: str, *parts: object, length: int = 24) -> str:
    # 把所有业务字段拼成一个稳定字符串。
    raw = "|".join(str(part) for part in parts)
    # 用前缀加短哈希组成数据库友好的主键。
    return f"{prefix}_{sha256_text(raw)[:length]}"


def read_text_auto(path: Path) -> str:
    # 优先用 UTF-8-SIG 读取，兼容带 BOM 的 Markdown。
    try:
        # 返回 UTF-8 读取结果。
        return path.read_text(encoding="utf-8-sig")
    # 捕获编码错误后回退到中文 Windows 常见编码。
    except UnicodeDecodeError:
        # 用 GB18030 尽量保住中文内容。
        return path.read_text(encoding="gb18030", errors="replace")


def parse_env_file(path: Path) -> dict[str, str]:
    # 创建环境变量字典。
    values: dict[str, str] = {}
    # 文件不存在时返回空字典。
    if not path.exists():
        # 返回空配置。
        return values
    # 逐行读取 env 文件。
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        # 跳过空行、注释行和非 key=value 行。
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            # 继续下一行。
            continue
        # 只按第一个等号切分，避免密码中出现等号时被截断。
        key, value = line.split("=", 1)
        # 写入去空白后的 key 和 value。
        values[key.strip()] = value.strip()
    # 返回解析后的环境配置。
    return values


def unique_keep_order(values: list[str] | tuple[str, ...]) -> list[str]:
    # 用集合记录已经出现的值。
    seen: set[str] = set()
    # 用列表保持原始顺序。
    result: list[str] = []
    # 逐个处理输入值。
    for value in values:
        # 去掉实体左右空白。
        clean = value.strip()
        # 跳过空值和重复值。
        if not clean or clean in seen:
            # 继续下一项。
            continue
        # 标记该值已经出现。
        seen.add(clean)
        # 保留第一次出现的值。
        result.append(clean)
    # 返回去重后的列表。
    return result


def json_safe_value(value: Any) -> Any:
    # 基础类型可以直接 JSON 序列化。
    if value is None or isinstance(value, (str, int, float, bool)):
        # 直接返回基础类型。
        return value
    # 列表和元组递归清洗。
    if isinstance(value, (list, tuple)):
        # 返回清洗后的列表。
        return [json_safe_value(item) for item in value]
    # 字典递归清洗 key 和 value。
    if isinstance(value, dict):
        # 返回字符串 key 的字典。
        return {str(key): json_safe_value(item) for key, item in value.items()}
    # 其他类型退化为字符串。
    return str(value)
