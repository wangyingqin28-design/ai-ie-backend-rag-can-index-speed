

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.ops import AsyncDatabaseOps, async_db_ops
from typing import Optional, List
from app.models.models import DocumentIndex, DocumentIndexStatus, DocumentIndexType, RuleType
from app.index.document_index_manager import all_index_types, document_index_manager
from app.utils.utils import random_id
from sqlalchemy import and_, select
from collections import defaultdict
from app.schemas.mssql_qdrant.constant import IndexAction
from app.tasks.reconciler import index_reconciler
from app.schemas.mssql_qdrant.view_models import DocumentIndexResponse
from app.utils.response import Success
from app.config import async_engine, get_async_session
from app.schemas.mssql_qdrant.view_models import RuleTypeResponse


logger = logging.getLogger(__name__)


class DocumentService:
    """Document service that handles business logic for documents"""

    def __init__(self, session: AsyncSession = None):
        # Use global db_ops instance by default, or create custom one with provided session
        if session is None:
            self.db_ops = async_db_ops  # Use global instance
        else:
            self.db_ops = AsyncDatabaseOps(session)  # Create custom instance for transaction control

    async def create_document(
        self, 
        user_id: int, 
        rule_type: int,
        rules: List[str],
        enterprise_id: Optional[int] = None,
        standard_id: Optional[int] = None,
        index_types: Optional[List[DocumentIndexType]] = None,
    ):  
        document_id = "doc" + random_id()
        upsert_id = document_id
        # 过滤空字符串和None值
        filtered_rules = [rule for rule in rules if rule and rule.strip()]
        if not index_types:
            index_types = all_index_types

        # Process all files in a single transaction for atomicity
        async def _create_documents_atomically(session):
            all_created_indexes = []
            for rule in filtered_rules:
                created_indexes = await document_index_manager.create_document_indexes(
                    session,
                    user_id,
                    rule_type,
                    rule,
                    upsert_id,
                    document_id,
                    enterprise_id,
                    standard_id,
                    index_types,
                )
                all_created_indexes.extend(created_indexes)

            return all_created_indexes

        # Execute the atomic operation
        created_documents = await self.db_ops.execute_with_transaction(_create_documents_atomically)
        logger.info(f"Marked created index for document {upsert_id} with index types {index_types}")
        
        created_documents_response = []
        if created_documents:
            # Trigger index coordination
            index_reconciler.task_scheduler.schedule_operate_index(upsert_id, index_types)
            logger.debug(f"Scheduled create index task for document {upsert_id} with index types {index_types}")
            
            for doc_index in created_documents:
                created_documents_response.append(DocumentIndexResponse.model_validate(doc_index).model_dump())


        return Success(data=created_documents_response)


    async def delete_document(
        self,
        user_id: int,
        ids: List[str],
        index_types: Optional[List[DocumentIndexType]] = None,
    ):
        upsert_id = "doc" + random_id()
        filtered_ids = [id for id in ids if id]
        if not index_types:
            index_types = all_index_types

        # Process all files in a single transaction for atomicity
        async def _delete_documents_atomically(session):
            all_deleted_ids = []
            for id in filtered_ids:
                deleted_ids = await document_index_manager.delete_document_indexes(
                    session,
                    user_id,
                    id,
                    upsert_id,
                    index_types,
                )
                all_deleted_ids.extend(deleted_ids)

            return all_deleted_ids

        # Execute the atomic operation
        deleted_ids = await self.db_ops.execute_with_transaction(_delete_documents_atomically)
        logger.debug(f"Marked deleted index for document {upsert_id} with index types {index_types}")

        if deleted_ids:
            # Trigger index coordination
            index_reconciler.task_scheduler.schedule_operate_index(upsert_id, index_types)
            logger.debug(f"Scheduled delete index task for document {upsert_id} with index types {index_types}")


        return Success(data=deleted_ids)


    async def update_document(
        self,
        user_id: int,
        id_rule_dict: dict[str, str],
        index_types: Optional[List[DocumentIndexType]] = None,
    ):
        upsert_id = "doc" + random_id()
        filtered_id_rule_dict = {id: rule for id, rule in id_rule_dict.items() if id}
        filtered_id_rule_dict = {id: rule for id, rule in filtered_id_rule_dict.items() if rule and rule.strip()}
        if not index_types:
            index_types = all_index_types
        
        # Process all files in a single transaction for atomicity
        async def _update_documents_atomically(session):
            all_updated_indexes = []
            for id, rule in filtered_id_rule_dict.items():
                updated_indexes = await document_index_manager.update_document_indexes(
                    session,
                    user_id,
                    id,
                    rule,
                    upsert_id,
                    index_types,
                )
                all_updated_indexes.extend(updated_indexes)

            return all_updated_indexes

        # Execute the atomic operation
        updated_indexes = await self.db_ops.execute_with_transaction(_update_documents_atomically)
        logger.debug(f"Marked updated index for document {upsert_id} with index types {index_types}")

        updated_documents_response = []
        if updated_indexes:
            # Trigger index coordination
            index_reconciler.task_scheduler.schedule_operate_index(upsert_id, index_types)
            logger.debug(f"Scheduled update index task for document {upsert_id} with index types {index_types}")
            
            for doc_index in updated_indexes:
                updated_documents_response.append(DocumentIndexResponse.model_validate(doc_index).model_dump())

        
        return Success(data=updated_documents_response)

    async def get_document_index_rule_type(
        self,
        user_id: int,
    ):  
        try:
            async for session in get_async_session():
                stmt = select(RuleType)
                result = await session.execute(stmt)
                document_rule_types = result.scalars().all()
                
                document_rule_types_response = []
                for rule_type in document_rule_types:
                    document_rule_types_response.append({
                        "id": rule_type.id,
                        "rule_type": rule_type.rule_type
                    })

            return Success(data=document_rule_types_response)
        except Exception as e:
            logger.error(f"Error in get_document_index_rule_type: {e}")
            raise e







# Create a global service instance for easy access
# This uses the global db_ops instance and doesn't require session management in views
document_service = DocumentService()




if __name__ == "__main__":
    async def main():
        await document_service.create_document(
        user_id=1,
        rule_type=1,
        rules=["rule11"],
    )
 
    # async def main():
    #     await document_service.update_document(
    #     user_id=2,
    #     id_rule_dict={
    #         "0697855d-4478-770d-8000-5b2482fa5108": "rule777",
    #         "0697855d-449b-7a16-8000-eda3bf7692e6": "rule888",
    #     },
    # )    

    # async def main():
    #     await document_service.delete_document(
    #     user_id=2,
    #     ids=["06978552-a542-76ef-8000-0d4c7c6b3dd5", "06978552-a56b-7b34-8000-19fca7f12074"],
    # )    

    import asyncio
    asyncio.run(main())

    # workflow_id = index_reconciler.task_scheduler.schedule_all_index_operation()
    # print(workflow_id)


    # from app.tasks.document import document_index_task
    # for document_id, upsert_indexes in doc_indexes.items():
    #     for inner_index_action, indexes in upsert_indexes.items():
    #         if indexes:
    #             document_index_task.operate_index(document_id, index_type, index_action)    
    