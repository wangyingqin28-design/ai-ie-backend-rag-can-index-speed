
import logging
from app.models.models import DocumentIndex, DocumentIndexStatus, DocumentIndexType
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from app.utils.utils import calculate_file_hash
from sqlalchemy import and_, select
import datetime
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


all_index_types = [
    DocumentIndexType.VECTOR,
]

class DocumentIndexManager:
    """Simple manager for document index specs (frontend chain)"""

    async def create_document_indexes(
        self, session: AsyncSession,
        user_id: int, 
        rule_type: int,
        rule: str,
        upsert_id: str,
        document_id: str,
        enterprise_id: Optional[int] = None,
        standard_id: Optional[int] = None,
        index_types: Optional[List[DocumentIndexType]] = None,
    ):
        content_hash = calculate_file_hash(rule.encode())

        created_indexes = []
        for index_type in index_types:
            stmt =  select(DocumentIndex).where(
                and_(DocumentIndex.user_id == user_id,
                     DocumentIndex.index_type == index_type,
                     DocumentIndex.content_hash == content_hash,
                     DocumentIndex.gmt_deleted.is_(None),
                )
            )

            result = await session.execute(stmt)
            existing_index = result.scalars().first()
            if existing_index:
                created_indexes.append(existing_index)
                continue
            else:
                index = DocumentIndex(
                    user_id=user_id,
                    update_user_id=user_id,
                    rule_type=rule_type,
                    enterprise_id=enterprise_id,
                    standard_id=standard_id,
                    rule=rule,
                    upsert_id=upsert_id,
                    document_id=document_id,
                    index_type=index_type,
                    status=DocumentIndexStatus.PENDING,
                    version=1,
                    observed_version=0,
                    content_hash=content_hash,
                )
                session.add(index)
                created_indexes.append(index)


        return created_indexes


    async def delete_document_indexes(
        self, session: AsyncSession, 
        user_id: int,
        id: str, 
        upsert_id: str,
        index_types: Optional[List[DocumentIndexType]] = None
    ):  
        deleted_ids = []    
        for index_type in index_types:
            stmt =  select(DocumentIndex).where(
                and_(DocumentIndex.id == id,
                     DocumentIndex.index_type == index_type,
                )
            )
            result = await session.execute(stmt)
            doc_index = result.scalar_one_or_none()

            if doc_index:
                # Mark for deletion
                doc_index.update_user_id = user_id
                doc_index.upsert_id = upsert_id
                doc_index.status = DocumentIndexStatus.DELETING
                doc_index.gmt_updated = datetime.datetime.now()
                deleted_ids.append(doc_index.id)
        
        return deleted_ids


    async def update_document_indexes(
        self, session: AsyncSession, 
        user_id: int,
        id: str, 
        rule: str,
        upsert_id: str,
        index_types: Optional[List[DocumentIndexType]] = None,
    ):
        content_hash = calculate_file_hash(rule.encode())    

        updated_indexes = []
        for index_type in index_types:
            stmt =  select(DocumentIndex).where(
                and_(DocumentIndex.id == id,
                     DocumentIndex.index_type == index_type,
                     DocumentIndex.status.not_in([DocumentIndexStatus.DELETING, DocumentIndexStatus.DELETION_IN_PROGRESS]),
                )
            )
            result = await session.execute(stmt)
            existing_index = result.scalar_one_or_none()
            if existing_index:
                if existing_index.content_hash == content_hash:
                    updated_indexes.append(existing_index)
                    continue
                else:
                    existing_index.update_user_id = user_id
                    existing_index.rule = rule
                    existing_index.upsert_id = upsert_id
                    existing_index.status = DocumentIndexStatus.PENDING
                    existing_index.version = existing_index.version + 1
                    existing_index.gmt_updated = datetime.datetime.now()                    
                    existing_index.content_hash = content_hash  
                updated_indexes.append(existing_index)


        return updated_indexes
    

    def get_document_indexes(self, session: Session) -> list[list]:
        create_failed_stmt =  select(DocumentIndex).where(
            and_(DocumentIndex.document_id == DocumentIndex.upsert_id,
                 DocumentIndex.version == 1,
                 DocumentIndex.observed_version == 0,
                 DocumentIndex.status == DocumentIndexStatus.FAILED_CREATING,
                 DocumentIndex.gmt_deleted.is_(None),
                 DocumentIndex.gmt_created != DocumentIndex.gmt_updated,
            )
        )
        create_pending_overtime_stmt =  select(DocumentIndex).where(
            and_(DocumentIndex.document_id == DocumentIndex.upsert_id,
                 DocumentIndex.version == 1,
                 DocumentIndex.observed_version == 0,
                 DocumentIndex.status == DocumentIndexStatus.PENDING,
                 DocumentIndex.gmt_deleted.is_(None),
                 DocumentIndex.gmt_created == DocumentIndex.gmt_updated,
                 DocumentIndex.gmt_updated < datetime.datetime.now() - datetime.timedelta(minutes=1),
            )
        )
        create_creating_overtime_stmt =  select(DocumentIndex).where(
            and_(DocumentIndex.document_id == DocumentIndex.upsert_id,
                 DocumentIndex.version == 1,
                 DocumentIndex.observed_version == 0,
                 DocumentIndex.status == DocumentIndexStatus.CREATING,
                 DocumentIndex.gmt_deleted.is_(None),
                 DocumentIndex.gmt_created != DocumentIndex.gmt_updated,
                 DocumentIndex.gmt_updated < datetime.datetime.now() - datetime.timedelta(minutes=3),
            )
        )


        update_failed_stmt =  select(DocumentIndex).where(
            and_(DocumentIndex.document_id != DocumentIndex.upsert_id,
                 DocumentIndex.version > 1,
                 DocumentIndex.status == DocumentIndexStatus.FAILED_UPDATING,
                 DocumentIndex.gmt_deleted.is_(None),
                 DocumentIndex.gmt_created != DocumentIndex.gmt_updated,
            )
        )
        update_pending_overtime_stmt =  select(DocumentIndex).where(
            and_(DocumentIndex.document_id != DocumentIndex.upsert_id,
                 DocumentIndex.version > 1,
                 DocumentIndex.status == DocumentIndexStatus.PENDING,
                 DocumentIndex.gmt_deleted.is_(None),
                 DocumentIndex.gmt_created != DocumentIndex.gmt_updated,
                 DocumentIndex.gmt_updated < datetime.datetime.now() - datetime.timedelta(minutes=1),
            )
        )
        update_creating_overtime_stmt =  select(DocumentIndex).where(
            and_(DocumentIndex.document_id != DocumentIndex.upsert_id,
                 DocumentIndex.version > 1,
                 DocumentIndex.status == DocumentIndexStatus.CREATING,
                 DocumentIndex.gmt_deleted.is_(None),
                 DocumentIndex.gmt_created != DocumentIndex.gmt_updated,
                 DocumentIndex.gmt_updated < datetime.datetime.now() - datetime.timedelta(minutes=3),
            )
        )


        delete_failed_stmt =  select(DocumentIndex).where(
            and_(DocumentIndex.document_id != DocumentIndex.upsert_id,
                 DocumentIndex.status == DocumentIndexStatus.FAILED_DELETING,
                 DocumentIndex.gmt_deleted.is_(None),
                 DocumentIndex.gmt_created != DocumentIndex.gmt_updated,
            )
        )
        delete_deleting_overtime_stmt =  select(DocumentIndex).where(
            and_(DocumentIndex.document_id != DocumentIndex.upsert_id,
                 DocumentIndex.status == DocumentIndexStatus.DELETING,
                 DocumentIndex.gmt_deleted.is_(None),
                 DocumentIndex.gmt_created != DocumentIndex.gmt_updated,
                 DocumentIndex.gmt_updated < datetime.datetime.now() - datetime.timedelta(minutes=1),
            )
        )
        delete_deletion_in_progress_overtime_stmt =  select(DocumentIndex).where(
            and_(DocumentIndex.document_id != DocumentIndex.upsert_id,
                 DocumentIndex.status == DocumentIndexStatus.DELETION_IN_PROGRESS,
                 DocumentIndex.gmt_deleted.is_(None),
                 DocumentIndex.gmt_created != DocumentIndex.gmt_updated,
                 DocumentIndex.gmt_updated < datetime.datetime.now() - datetime.timedelta(minutes=3),
            )
        )


        create_failed_stmt_result = session.execute(create_failed_stmt)
        create_failed_indexes = create_failed_stmt_result.scalars().all()
        
        create_pending_overtime_stmt_result = session.execute(create_pending_overtime_stmt)
        create_pending_overtime_indexes = create_pending_overtime_stmt_result.scalars().all()
        
        create_creating_overtime_stmt_result = session.execute(create_creating_overtime_stmt)
        create_creating_overtime_indexes = create_creating_overtime_stmt_result.scalars().all()
        
        update_failed_stmt_result = session.execute(update_failed_stmt)
        update_failed_indexes = update_failed_stmt_result.scalars().all()
        
        update_pending_overtime_stmt_result = session.execute(update_pending_overtime_stmt)
        update_pending_overtime_indexes = update_pending_overtime_stmt_result.scalars().all()
        
        update_creating_overtime_stmt_result = session.execute(update_creating_overtime_stmt)
        update_creating_overtime_indexes = update_creating_overtime_stmt_result.scalars().all()
        
        delete_failed_stmt_result = session.execute(delete_failed_stmt)
        delete_failed_indexes = delete_failed_stmt_result.scalars().all()
        
        delete_deleting_overtime_stmt_result = session.execute(delete_deleting_overtime_stmt)
        delete_deleting_overtime_indexes = delete_deleting_overtime_stmt_result.scalars().all()
        
        delete_deletion_in_progress_overtime_stmt_result = session.execute(delete_deletion_in_progress_overtime_stmt)
        delete_deletion_in_progress_overtime_indexes = delete_deletion_in_progress_overtime_stmt_result.scalars().all()
         
        result = [
            create_failed_indexes, create_pending_overtime_indexes, create_creating_overtime_indexes,
            update_failed_indexes, update_pending_overtime_indexes, update_creating_overtime_indexes,
            delete_failed_indexes, delete_deleting_overtime_indexes, delete_deletion_in_progress_overtime_indexes
        ]

        return result



# Global instance
document_index_manager = DocumentIndexManager()


if __name__ == "__main__":
    from app.config import get_sync_session, get_async_session
    for session in get_sync_session():
        index_query_result:list[list] = document_index_manager.get_document_indexes(session)
    print(index_query_result)

    from app.tasks.document import document_index_task
    for document_id, upsert_indexes in doc_indexes.items():
        for inner_index_action, indexes in upsert_indexes.items():
            if indexes:
                document_index_task.operate_index(document_id, index_type, index_action)    