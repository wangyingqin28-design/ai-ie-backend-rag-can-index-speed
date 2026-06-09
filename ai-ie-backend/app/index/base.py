

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class IndexType(Enum):
    """Index type enumeration"""

    VECTOR = "VECTOR"
    FULLTEXT = "FULLTEXT"
    GRAPH = "GRAPH"
    SUMMARY = "SUMMARY"
    VISION = "VISION"


class IndexStatus(Enum):
    """Index status enumeration"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class IndexResult:
    """Standard index operation result"""

    success: bool
    index_type: IndexType
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "index_type": self.index_type.value,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }


class BaseIndexer(ABC):
    """Abstract base class for all indexers"""

    def __init__(self, index_type: IndexType):
        self.index_type = index_type

    @abstractmethod
    def create_index(self, document_id: int, doc_parts: dict, collection, **kwargs) -> IndexResult:
        """
        Create index for document

        Args:
            document_id: Document ID
            doc_parts: IndexAction dict, key is IndexAction, value is list of doc_part
            collection: Collection object
            **kwargs: Additional parameters

        Returns:
            IndexResult: Result of index creation
        """
        pass

    @abstractmethod
    def update_index(self, document_id: int, doc_parts: dict, collection, **kwargs) -> IndexResult:
        """
        Update existing index for document

        Args:
            document_id: Document ID
            doc_parts: IndexAction dict, key is IndexAction, value is list of doc_part
            collection: Collection object
            **kwargs: Additional parameters

        Returns:
            IndexResult: Result of index update
        """
        pass

    @abstractmethod
    def delete_index(self, document_id: int, collection, **kwargs) -> IndexResult:
        """
        Delete index for document

        Args:
            document_id: Document ID
            collection: Collection object
            **kwargs: Additional parameters

        Returns:
            IndexResult: Result of index deletion
        """
        pass

    @abstractmethod
    def is_enabled(self, collection) -> bool:
        """
        Check if this index type is enabled for the collection

        Args:
            collection: Collection object

        Returns:
            bool: True if enabled
        """
        pass


