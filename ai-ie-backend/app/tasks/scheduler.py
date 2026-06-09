

import logging
from abc import ABC, abstractmethod
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


class TaskResult:
    """Represents the result of a task execution"""

    def __init__(self, task_id: str, success: bool = True, error: str = None, data: Any = None):
        self.task_id = task_id
        self.success = success
        self.error = error
        self.data = data


class TaskScheduler(ABC):
    """Abstract base class for task schedulers"""

    @abstractmethod
    def schedule_create_index(self, document_id: str, index_types: List[str], context: dict = None, **kwargs) -> str:
        """
        Schedule single index creation task

        Args:
            document_id: Document ID to process
            index_types: List of index types (vector, fulltext, graph)
            context: Task context including version info
            **kwargs: Additional arguments

        Returns:
            Task ID for tracking
        """
        pass

    @abstractmethod
    def schedule_update_index(self, document_id: str, index_types: List[str], context: dict = None, **kwargs) -> str:
        """
        Schedule single index update task

        Args:
            document_id: Document ID to process
            index_types: List of index types (vector, fulltext, graph)
            context: Task context including version info
            **kwargs: Additional arguments

        Returns:
            Task ID for tracking
        """
        pass

    @abstractmethod
    def schedule_delete_index(self, document_id: str, index_types: List[str], context: dict = None, **kwargs) -> str:
        """
        Schedule single index deletion task

        Args:
            document_id: Document ID to process
            index_types: List of index types (vector, fulltext, graph)
            context: Task context including version info
            **kwargs: Additional arguments

        Returns:
            Task ID for tracking
        """
        pass

    @abstractmethod
    def get_task_status(self, task_id: str) -> Optional[TaskResult]:
        """
        Get task execution status

        Args:
            task_id: Task ID to check

        Returns:
            TaskResult or None if task not found
        """
        pass


def create_task_scheduler(scheduler_type: str):
    if scheduler_type == "celery":
        return CeleryTaskScheduler()
    else:
        raise Exception("unknown task scheduler type: %s" % scheduler_type)


class CeleryTaskScheduler(TaskScheduler):
    """Celery implementation of TaskScheduler - Direct workflow execution"""

    def schedule_operate_index(self, document_id: str, index_types: Optional[List[str]] = None, index_action: Optional[str] = None, context: dict = None, **kwargs) -> str:
        """Schedule index operation workflow"""

        from config.celery_tasks import operate_index_workflow
        try:
            # Execute workflow and return AsyncResult ID (not calling .get())
            workflow_result = operate_index_workflow(document_id, index_types, index_action)
            # Use .id instead of .get('workflow_id')
            workflow_id = workflow_result.id
            logger.debug(f"Successfully scheduled index operation workflow for document {document_id} with workflow ID {workflow_id} and index types {index_types}")
            
            return workflow_id
        except Exception as e:
            logger.error(f"Failed to schedule index operation workflow for document {document_id}: {str(e)} with index types {index_types}")
            
    def schedule_all_index_operation(self, context: dict = None, **kwargs) -> str:
        """Schedule all index operation workflow"""

        from config.celery_tasks import reconcile_index_workflow
        try:
            workflow_result = reconcile_index_workflow()
            workflow_id = workflow_result.id
            logger.debug(f"Successfully scheduled all index operation workflow with workflow ID {workflow_id}")
            
            return workflow_id
        except Exception as e:
            logger.error(f"Failed to schedule all index operation workflow: {str(e)}")
            
        

    def schedule_create_index(self, document_id: str, index_types: List[str], context: dict = None, **kwargs) -> str:
        """Schedule index creation workflow"""
        raise NotImplementedError("Celery task scheduler is not implemented")

    def schedule_update_index(self, document_id: str, index_types: List[str], context: dict = None, **kwargs) -> str:
        """Schedule index update workflow"""
        raise NotImplementedError("Celery task scheduler is not implemented")

    def schedule_delete_index(self, document_id: str, index_types: List[str], **kwargs) -> str:
        """Schedule index deletion workflow"""
        raise NotImplementedError("Celery task scheduler is not implemented")

    def get_task_status(self, task_id: str) -> Optional[TaskResult]:
        """Get workflow status using Celery AsyncResult (non-blocking)"""
        try:
            from celery.result import AsyncResult

            from config.celery import app

            # Get AsyncResult without calling .get()
            workflow_result = AsyncResult(task_id, app=app)

            # Check status without blocking
            if workflow_result.state == "PENDING":
                return TaskResult(task_id, success=False, error="Workflow is pending")
            elif workflow_result.state == "STARTED":
                return TaskResult(task_id, success=False, error="Workflow is running")
            elif workflow_result.state == "SUCCESS":
                return TaskResult(task_id, success=True, data=workflow_result.result)
            elif workflow_result.state == "FAILURE":
                return TaskResult(task_id, success=False, error=str(workflow_result.info))
            else:
                return TaskResult(task_id, success=False, error=f"Unknown state: {workflow_result.state}")

        except Exception as e:
            logger.error(f"Failed to get workflow status for {task_id}: {str(e)}")
            return TaskResult(task_id, success=False, error=str(e))


class PrefectTaskScheduler(TaskScheduler):
    """Prefect implementation of TaskScheduler - Direct workflow execution"""

    def schedule_create_index(self, document_id: str, index_types: List[str], context: dict = None, **kwargs) -> str:
        """Schedule index creation workflow"""
        raise NotImplementedError("Prefect task scheduler is not implemented")

    def schedule_update_index(self, document_id: str, index_types: List[str], context: dict = None, **kwargs) -> str:
        """Schedule index update workflow"""
        raise NotImplementedError("Prefect task scheduler is not implemented")

    def schedule_delete_index(self, document_id: str, index_types: List[str], context: dict = None, **kwargs) -> str:
        """Schedule index deletion workflow"""
        raise NotImplementedError("Prefect task scheduler is not implemented")

    def get_task_status(self, task_id: str) -> Optional[TaskResult]:
        """Get workflow status using Prefect AsyncResult (non-blocking)"""
        raise NotImplementedError("Prefect task scheduler is not implemented")


