


import logging
from app.models.models import DocumentIndexType
from typing import Optional
from app.index.document_index_manager import all_index_types 



logger = logging.getLogger(__name__)

class DocumentIndexTask:
    """Document index task"""

    def operate_index(self, document_id: str, index_type: str, index_action: Optional[str] = None):
        if index_type == DocumentIndexType.VECTOR:
            from app.tasks.reconciler import index_reconciler
            index_reconciler.reconcile_document_indexes_by_upsert_id(document_id, index_action)
        else:
            raise ValueError(f"Unknown index type: {index_type}")
        


document_index_task = DocumentIndexTask()

