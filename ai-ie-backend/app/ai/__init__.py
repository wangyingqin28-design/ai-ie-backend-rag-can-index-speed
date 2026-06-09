"""AI capability package.

This package groups model configuration, prompts, LLM clients, memory,
RAG backends, and agent tooling.
"""

from .config import AIConfig
from .exceptions import MemoryAIError
from .llm import build_llm

__all__ = ["AIConfig", "MemoryAIError", "build_llm"]
