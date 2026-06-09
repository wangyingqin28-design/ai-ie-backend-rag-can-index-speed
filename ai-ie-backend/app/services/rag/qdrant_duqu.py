import json
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core.schema import TextNode

class CustomQdrantVectorStore(QdrantVectorStore):
    """专为 _node_content 嵌套结构定制：提取 JSON 内的 text 字段"""

    def _build_node_from_payload(self, payload: dict, score: float = None) -> TextNode:
        # 1. 优先解析 _node_content 中的 text（您的实际数据位置）
        text = ""
        if node_content := payload.get("_node_content"):
            try:
                # _node_content 是 JSON 字符串 → 解析 → 取 text
                text = json.loads(node_content).get("text", "")
            except (json.JSONDecodeError, TypeError):
                pass  # 解析失败则跳过

        # 2. 回退：若无 _node_content，尝试顶层 text 字段（兼容旧数据）
        if not text:
            text = payload.get("text", "")

        # 3. 构建干净 metadata（移除大字段避免污染）
        metadata = {
            k: v for k, v in payload.items()
            if k not in ["_node_content", "vector"]  # 排除冗余字段
        }

        # 4. 创建节点（用 payload 顶层 id 作为唯一标识）
        node = TextNode(
            text=text,
            metadata=metadata,
            id_=str(payload.get("id", payload.get("id_", "unknown")))
        )
        if score is not None:
            node.score = score
        return node