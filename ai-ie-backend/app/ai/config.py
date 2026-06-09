
from dataclasses import dataclass
from typing import Optional
@dataclass
class AIConfig:
    """Runtime settings for model calls, embeddings, rerank, and memory behavior."""

    model: str
    api_key: str
    base_url: str

    embedding_model: str = "BAAI/bge-m3"
    embedding_api_key: Optional[str] = None
    embedding_base_url: Optional[str] = None
    embedding_dim: int = 1024

    rerank_model: Optional[str] = "BAAI/bge-reranker-v2-m3"
    rerank_api_key: Optional[str] = None
    rerank_base_url: Optional[str] = None

    context_window: int = 128000
    timeout: float = 120.0
    is_chat_model: bool = True

    memory_token_limit: int = 3000
    history_token_limit: int = 6000

    system_prompt: Optional[str] = None
    default_session_title: str = "新对话"

    #vlm
    LLM_MODEL = "Qwen/Qwen3.5-397B-A17B"
    VISION_MODEL = "Qwen/Qwen3.5-397B-A17B"
    EMBEDDING_MODEL = "Qwen/Qwen3-VL-Embedding-8B"
    DEFAULT_FOLDER = "D:/huangjing/Llamalndex/image"

    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls"}
    TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json"}
    SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS | TEXT_EXTENSIONS

