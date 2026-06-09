

import logging
from app.config import get_sync_session, get_async_session
from sqlalchemy import and_, select, update
from app.models.models import DocumentIndex, DocumentIndexStatus, DocumentIndexType
from collections import defaultdict
from app.schemas.mssql_qdrant.constant import IndexAction
from app.index.vector_index import vector_indexer
from app.schemas.mssql_qdrant.utils import generateCollectionCreate
from sqlalchemy.orm import Session
import datetime
from typing import Optional
from app.tasks.scheduler import TaskScheduler, create_task_scheduler
from app.index.document_index_manager import document_index_manager, all_index_types

logger = logging.getLogger(__name__)



class DocumentIndexReconciler:

    def __init__(self, task_scheduler: Optional[TaskScheduler] = None, scheduler_type: str = "celery"):
        self.task_scheduler = task_scheduler or create_task_scheduler(scheduler_type)
    
    # 先写 sql 把所有需要协调的索引找出来，然后分类协调
    def schedule_all_index_operation(self,) -> None:
        """Schedule all index operation"""
        
        '''
        1、未向量化【创建、修改、删除】
        1.1、创建索引：
        创建时间 = 更新时间
        协调时间 is None
        删除时间 is None
        版本 = 1
        遵守的版本 = 0
        状态 = DocumentIndexStatus.PENDING
        文档id = 更新插入id
        
        1.2、修改索引：
        创建时间 != 更新时间
        删除时间 is None
        版本 > 1
        版本 > 遵守的版本
        状态 = DocumentIndexStatus.PENDING
        文档id != 更新插入id
        
        1.3、删除索引：
        创建时间 != 更新时间
        删除时间 is None
        状态 = DocumentIndexStatus.DELETING
        文档id != 更新插入id


        2、宣称向量化【创建、修改、删除】
        2.1、宣称创建索引：
        创建时间 != 更新时间
        协调时间 = 更新时间
        删除时间 is None
        版本 = 1
        遵守的版本 = 0
        状态 = DocumentIndexStatus.CREATING
        文档id = 更新插入id        
        
        2.2、宣称修改索引：
        创建时间 != 更新时间
        协调时间 = 更新时间
        删除时间 is None
        版本 > 1
        版本 > 遵守的版本
        状态 = DocumentIndexStatus.CREATING
        文档id != 更新插入id
        
        2.3、宣称删除索引：
        创建时间 != 更新时间
        协调时间 = 更新时间
        删除时间 is None
        状态 = DocumentIndexStatus.DELETION_IN_PROGRESS
        文档id != 更新插入id


        3、证明向量化成功
        3.1、证明创建索引：
        创建时间 != 更新时间
        协调时间 = 更新时间
        删除时间 is None
        版本 = 1
        遵守的版本 = 1
        状态 = DocumentIndexStatus.ACTIVE
        文档id = 更新插入id
        
        3.2、证明修改索引：
        创建时间 != 更新时间
        协调时间 = 更新时间
        删除时间 is None
        版本 > 1
        版本 = 遵守的版本
        状态 = DocumentIndexStatus.ACTIVE
        文档id != 更新插入id
        
        3.3、证明删除索引：
        创建时间 != 更新时间
        协调时间 = 更新时间
        删除时间 = 协调时间
        状态 = DocumentIndexStatus.DELETION_IN_PROGRESS
        文档id != 更新插入id


        4、向量化失败
        4.1、失败创建索引：
        状态 = DocumentIndexStatus.FAILED_CREATING

        4.2、失败修改索引：
        状态 = DocumentIndexStatus.FAILED_UPDATING

        4.3、失败删除索引：
        状态 = DocumentIndexStatus.FAILED_DELETING


        '''

        pass


    # The entire coordination method is carried out as a task.
    def reconcile_document_indexes_by_upsert_id(self, upsert_id: str, index_action: Optional[IndexAction] = None) -> None:
        """Reconcile document indexes by upsert id"""

        for session in get_sync_session():
            operations: dict = self.get_document_indexes_by_upsert_id(session, upsert_id, index_action)
            
        collection = generateCollectionCreate(DocumentIndex.__tablename__)
        for upsert_id, operation in operations.items():
            doc_parts = {upsert_id: operation}
            if operation[IndexAction.CREATE]:
                vector_indexer.create_index(
                    document_id=upsert_id,
                    doc_parts=doc_parts,
                    collection=collection
                )
            if operation[IndexAction.UPDATE]:
                vector_indexer.update_index(
                    document_id=upsert_id,
                    doc_parts=doc_parts,
                    collection=collection
                )
            if operation[IndexAction.DELETE]:
                vector_indexer.delete_index(
                    document_id=upsert_id,
                    doc_parts=doc_parts,
                    collection=collection
                )

    def get_document_indexes_by_upsert_id(self, session: Session, upsert_id: str, index_action: Optional[IndexAction] = None) -> dict[str, dict[IndexAction, list[DocumentIndex]]]:
        """Get document indexes by upsert id"""       

        stmt = select(DocumentIndex).where(
            and_(DocumentIndex.upsert_id == upsert_id,
                 DocumentIndex.gmt_deleted.is_(None),
            )
        )
        result = session.execute(stmt)
        doc_indexes = result.scalars().all()
        logger.info(f"Found {len(doc_indexes)} document indexes for upsert_id {upsert_id}")

        operations = defaultdict(lambda: {IndexAction.CREATE: [], IndexAction.UPDATE: [], IndexAction.DELETE: []})
        if not doc_indexes:
            return operations
            
        if index_action:
            for doc_index in doc_indexes:
                operations[doc_index.upsert_id][index_action].append(doc_index)

            return operations
            
        for doc_index in doc_indexes:
            if (doc_index.status == DocumentIndexStatus.PENDING and
                doc_index.version == 1 and 
                doc_index.version > doc_index.observed_version):
                operations[doc_index.upsert_id][IndexAction.CREATE].append(doc_index)

            elif (doc_index.status == DocumentIndexStatus.PENDING and
                doc_index.version > 1 and 
                doc_index.version > doc_index.observed_version):
                operations[doc_index.upsert_id][IndexAction.UPDATE].append(doc_index)

            elif doc_index.status == DocumentIndexStatus.DELETING and doc_index.gmt_deleted is None:
                operations[doc_index.upsert_id][IndexAction.DELETE].append(doc_index)    

        return operations

    def claim_document_indexes(self, session: Session,index_type: IndexAction, indexes_to_claim: list[DocumentIndex], ctx_ids: Optional[list] = None) -> None:
        """Claim document indexes by index type"""

        try:
            if index_type in [IndexAction.CREATE, IndexAction.UPDATE, ]:
                target_state = DocumentIndexStatus.CREATING
                gmt_updated = datetime.datetime.now()
                gmt_last_reconciled = gmt_updated
                for doc in indexes_to_claim:
                    doc.status = target_state
                    doc.gmt_updated = gmt_updated
                    doc.gmt_last_reconciled = gmt_last_reconciled
            elif index_type == IndexAction.DELETE:
                target_state = DocumentIndexStatus.DELETION_IN_PROGRESS
                gmt_updated = datetime.datetime.now()
                gmt_last_reconciled = gmt_updated
                stmt = (
                    update(DocumentIndex)
                    .where(DocumentIndex.id.in_(ctx_ids))
                    .values(status=target_state, gmt_updated=gmt_updated, gmt_last_reconciled=gmt_last_reconciled)
                )
                session.execute(stmt)

            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to claim indexes")
            raise e

    def confirm_document_indexes(self, session: Session, index_type: IndexAction, ctx_ids: list[str]) -> None:
        """Confirm document indexes by index type"""

        try:
            gmt_updated = datetime.datetime.now()
            gmt_last_reconciled = gmt_updated           
            if index_type in [IndexAction.CREATE, IndexAction.UPDATE, ]:
                target_state = DocumentIndexStatus.ACTIVE
                stmt = (
                    update(DocumentIndex)
                    .where(DocumentIndex.id.in_(ctx_ids))
                    .values(status=target_state, observed_version=DocumentIndex.version, gmt_updated=gmt_updated, gmt_last_reconciled=gmt_last_reconciled)
                )
                session.execute(stmt)
                session.commit()
            elif index_type == IndexAction.DELETE:
                stmt = (
                    update(DocumentIndex)
                    .where(DocumentIndex.id.in_(ctx_ids))
                    .values(gmt_updated=gmt_updated, gmt_last_reconciled=gmt_last_reconciled, gmt_deleted=gmt_updated)
                )
                session.execute(stmt)
                session.commit()

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to confirm indexes")
            raise e

    def handle_failed_document_indexes(self, index_type: IndexAction, upsert_id: str ,error_message: str) -> None:
        """Handle failed document indexes by upsert id"""

        try:
            for session in get_sync_session():
                try:
                    operations: dict = self.get_document_indexes_by_upsert_id(session, upsert_id)
                    for upsert_id, operation in operations.items():
                        if index_type in [IndexAction.CREATE]:
                            for doc_index in operation[index_type]:
                                doc_index.status = DocumentIndexStatus.FAILED_CREATING
                                doc_index.error_message = error_message
                                gmt_updated = datetime.datetime.now()
                                doc_index.gmt_updated = gmt_updated
                                doc_index.gmt_last_reconciled = gmt_updated
                            session.commit()
                        elif index_type in [IndexAction.UPDATE]:
                            for doc_index in operation[index_type]:
                                doc_index.status = DocumentIndexStatus.FAILED_UPDATING
                                doc_index.error_message = error_message
                                gmt_updated = datetime.datetime.now()
                                doc_index.gmt_updated = gmt_updated
                                doc_index.gmt_last_reconciled = gmt_updated
                            session.commit()
                        elif index_type in [IndexAction.DELETE]:
                            for doc_index in operation[index_type]:
                                doc_index.status = DocumentIndexStatus.FAILED_DELETING
                                doc_index.error_message = error_message
                                gmt_updated = datetime.datetime.now()
                                doc_index.gmt_updated = gmt_updated
                                doc_index.gmt_last_reconciled = gmt_updated
                            session.commit()
                except Exception as e:
                    session.rollback()
                    logger.error(f"Failed to handle failed indexes for document_id {upsert_id}: {e}")

        except Exception as e:
            logger.error(f"Failed to handle failed indexes for document_id {upsert_id}: {e}")
                    
    def deduplicate_indexes(self, create_failed_indexes, create_pending_overtime_indexes, create_creating_overtime_indexes,
                           update_failed_indexes, update_pending_overtime_indexes, update_creating_overtime_indexes,
                           delete_failed_indexes, delete_deleting_overtime_indexes, delete_deletion_in_progress_overtime_indexes) -> dict[IndexAction, list[tuple[str, dict[IndexAction, list[DocumentIndex]]]]]:
        """
        将9个查询结果全局去重，同一个id只能保留在一个操作类型中
        返回: dict，键为 upsert_id，值为 id去重后根据 upsert_id分组的操作类型字典
        """
        
        # 定义操作类型分组
        operation_groups = {
            IndexAction.DELETE: [delete_failed_indexes, delete_deleting_overtime_indexes, delete_deletion_in_progress_overtime_indexes],
            IndexAction.UPDATE: [update_failed_indexes, update_pending_overtime_indexes, update_creating_overtime_indexes],
            IndexAction.CREATE: [create_failed_indexes, create_pending_overtime_indexes, create_creating_overtime_indexes],
        }
        
        # 第一步：收集所有索引，建立全局id到记录的映射，保留每个id最新gmt_updated的记录
        global_id_dict = {}
        for operation_type, index_lists in operation_groups.items():
            for index_list in index_lists:
                for index in index_list:
                    index_id = index.id
                    if index_id not in global_id_dict or index.gmt_updated > global_id_dict[index_id]['record'].gmt_updated:
                        global_id_dict[index_id] = {
                            'operation_type': operation_type,
                            'record': index
                        }
        
        # 第二步：根据全局最优结果，将记录分配到对应的操作类型
        global_id_group_deduplicate: dict[IndexAction, list[DocumentIndex]] = {
            IndexAction.CREATE: [],
            IndexAction.UPDATE: [],
            IndexAction.DELETE: []
        }
        for id_data in global_id_dict.values():
            operation_type = id_data['operation_type']
            record = id_data['record']
            global_id_group_deduplicate[operation_type].append(record)
        
        # 第三步：value列表根据 upsert_id分组
        parallel_result: dict[IndexAction, list[tuple[str, dict[IndexAction, list[DocumentIndex]]]]] = {
            IndexAction.CREATE: [],
            IndexAction.UPDATE: [],
            IndexAction.DELETE: []
        }
        for operation_type, index_list in global_id_group_deduplicate.items():
            operations = defaultdict(lambda: {IndexAction.CREATE: [], IndexAction.UPDATE: [], IndexAction.DELETE: []})
            for index in index_list:
                index_dict = index.to_dict()
                operations[index.upsert_id][operation_type].append(index_dict)
            parallel_result[operation_type].extend( (upsert_id,operation) for upsert_id, operation in operations.items() )

        return parallel_result
    

    def get_indexes_needing_reconciliation(self) -> dict[IndexAction, list[tuple[str, dict[IndexAction, list[DocumentIndex]]]]]:
        """Reconcile all document indexes"""

        for session in get_sync_session():
            index_query_result:list[list] = document_index_manager.get_document_indexes(session)
        
        parallel_result: dict[IndexAction, list[tuple[str, dict[IndexAction, list[DocumentIndex]]]]] = self.deduplicate_indexes(*index_query_result)

        return parallel_result

    def get_all_index_types(self) -> list[DocumentIndexType]:
        """Get all index types"""

        return all_index_types
    



# Globa instances
index_reconciler = DocumentIndexReconciler()



if __name__ == "__main__":
    # index_reconciler_task = index_reconciler.reconcile_document_indexes_by_upsert_id('doc1a2051006477da8b')

    parallel_result = index_reconciler.get_indexes_needing_reconciliation()
    print(type(parallel_result[IndexAction.CREATE]))
    print(parallel_result)

    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print(datetime.timedelta(minutes=1))
    pass



