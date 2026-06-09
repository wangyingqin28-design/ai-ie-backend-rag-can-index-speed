

import logging
from app.llm.embed.base_embedding import get_collection_embedding_service_sync
from app.config import get_vector_db_connector
from app.utils.utils import (
    generate_vector_db_collection_name,
)






logger = logging.getLogger(__name__)



class CollectionTask:
    """Collection workflow orchestrator"""


    def _initialize_vector_databases(self, collection_id: str, collection) -> None:
        """Initialize vector database collections"""
        # Get embedding service
        _, vector_size = get_collection_embedding_service_sync(collection)

        # Create main vector database collection
        vector_db_conn = get_vector_db_connector(
            collection=generate_vector_db_collection_name(collection_id=collection_id)
        )
        vector_db_conn.connector.create_collection(vector_size=vector_size)

        logger.debug(f"Initialized vector databases for collection {collection_id}")


    def _delete_vector_databases(self, collection_id: str) -> None:
        """Delete vector database collections"""
        # Delete main vector database collection
        vector_db_conn = get_vector_db_connector(
            collection=generate_vector_db_collection_name(collection_id=collection_id)
        )
        vector_db_conn.connector.delete_collection()

        logger.debug(f"Deleted vector database collections for collection {collection_id}")

    


collection_task = CollectionTask()

















