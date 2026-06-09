


import json
import logging
from contextlib import asynccontextmanager
from typing import Any, List
from typing import Optional
from celery import Task, chain, chord, current_app, group
from config.celery import app
from app.tasks.reconciler import index_reconciler
from app.tasks.document import document_index_task

logger = logging.getLogger()





# ========== Workflow Entry Point Functions ==========

def operate_index_workflow(
    document_id: str,
    index_types: List[str],
    index_action: Optional[str] = None,
    context: dict = None,
):
    """Operate index workflow"""
    return group(
        operate_index_task.s(document_id, index_type, index_action)
        for index_type in index_types
    ).apply_async()


def reconcile_index_workflow():
    """Reconcile index workflow"""
    return chain(
        get_indexes_needing_reconciliation_task.s(),
        reconcile_index_action_workflow_task.s()
    ).apply_async()



# ========== Dynamic Workflow Orchestration Tasks ==========


@current_app.task(bind=True)
def reconcile_index_workflow_task(self):
    """Reconcile index workflow task"""

    return chain(
        get_indexes_needing_reconciliation_task.s(),
        reconcile_index_action_workflow_task.s()
    ).apply_async()


@current_app.task(bind=True)
def reconcile_index_action_workflow_task(self, parallel_result: dict[str, list[tuple[str, dict[str, list]]]]):
    """Reconcile index workflow task"""

    '''
    group(
        # CREATE INDEX TASKS
        group(operate_index_task.s(...), group(operate_index_task.s(...)),
        # UPDATE INDEX TASKS
        group(operate_index_task.s(...), group(operate_index_task.s(...)),
        # DELETE INDEX TASKS
        group(operate_index_task.s(...), group(operate_index_task.s(...)),  
    )
    '''
    index_action_tasks = group(
        group(
            operate_index_task.s(upsert_id, index_type, index_action)
            for upsert_id, _ in doc_indexes
            for index_type in index_reconciler.get_all_index_types()
        )
        for index_action, doc_indexes in parallel_result.items()
    )
    
    index_action_tasks.apply_async()



    


# ========== Core Document Processing Tasks ==========  

@current_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def operate_index_task(self, document_id: str, index_type: str, index_action: Optional[str] = None):
    """Operate index task"""

    document_index_task.operate_index(document_id, index_type, index_action)

@current_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def get_indexes_needing_reconciliation_task(self):
    """Get indexes needing reconciliation task"""

    try:
        parallel_result = index_reconciler.get_indexes_needing_reconciliation()
        logger.info("Successfully get indexes needing reconciliation")
        return parallel_result
    except Exception as e:
        logger.error(f"Failed to get indexes needing reconciliation: {str(e)}")
        raise 







