import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.ops import AsyncDatabaseOps, async_db_ops
from typing import Optional, List
from app.models.models import DocumentIndex, DocumentIndexStatus, DocumentIndexType
from app.index.document_index_manager import document_index_manager
from app.utils.utils import random_id
from app.tasks.collection import collection_task
from app.schemas.mssql_qdrant import view_models
from app.schemas.mssql_qdrant.utils import generateCollectionCreate


logger = logging.getLogger(__name__)


class CollectionService:
    """Collection service that handles business logic for collections"""

    def __init__(self, session: AsyncSession = None):
        # Use global db_ops instance by default, or create custom one with provided session
        if session is None:
            self.db_ops = async_db_ops  # Use global instance
        else:
            self.db_ops = AsyncDatabaseOps(session)  # Create custom instance for transaction control


    async def create_collection(self, collection_id: str):
        """Create a new collection"""
        collection = generateCollectionCreate(collection_id)
        await collection_task._initialize_vector_databases(collection_id=collection.id, collection=collection)        
        
    async def delete_collection(self, collection_id: str):
        """Delete a collection"""
        await collection_task._delete_vector_databases(collection_id=collection_id)






    






# Create a global service instance for easy access
# This uses the global db_ops instance and doesn't require session management in views
collection_service = CollectionService()