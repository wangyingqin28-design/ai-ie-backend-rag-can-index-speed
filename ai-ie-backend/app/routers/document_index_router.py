

from typing import Annotated
from fastapi import APIRouter, Request, Body
from app.schemas.mssql_qdrant.view_models import DocumentCreateRequest, DocumentUpdateRequest, DocumentDeleteRequest
from app.services.index.document_index_service import document_service
from app.utils.response import Success
# from app.utils.auth.jwt_utils import DB_DEPENDENCY
from app.utils.exceptions import AppException



router = APIRouter(prefix="/index", tags=["索引管理"])



@router.post("/document/create", summary="创建文档索引")
async def create_document(
    request: Request,
    doc_create: DocumentCreateRequest = Body(..., description="创建文档索引请求参数")
):
    """
    创建文档索引
    
    参数:
    - user_id: 用户ID
    - rule_type: 规则类型
    - rules: 规则列表
    - enterprise_id: 企业ID (可选)
    - standard_id: 标准ID (可选)
    - index_types: 索引类型列表 (可选,默认所有类型)
    
    返回:
    - 创建成功的文档索引列表
    """

    try:
        result = await document_service.create_document(
            user_id=doc_create.user_id,
            rule_type=doc_create.rule_type,
            rules=doc_create.rules,
            enterprise_id=doc_create.enterprise_id,
            standard_id=doc_create.standard_id,
            index_types=doc_create.index_types,
        )
    except Exception as e:
        raise AppException(code=500, message=f'创建规则索引失败: {str(e)}')
    return result


@router.post("/document/update", summary="更新文档索引")
async def update_document(
    request: Request,
    doc_update: DocumentUpdateRequest = Body(..., description="更新文档索引请求参数")
):
    """
    更新文档索引
    
    参数:
    - user_id: 用户ID
    - id_rule_dict: 文档ID和规则的映射字典 {id: rule}
    - index_types: 索引类型列表 (可选,默认所有类型)
    
    返回:
    - 更新成功的文档索引列表
    """

    try:
        result = await document_service.update_document(
            user_id=doc_update.user_id,
            id_rule_dict=doc_update.id_rule_dict,
            index_types=doc_update.index_types,
        )
    except Exception as e:
        raise AppException(code=500, message=f'更新规则索引失败: {str(e)}')
    return result


@router.post("/document/delete", summary="删除文档索引")
async def delete_document(
    request: Request,
    doc_delete: DocumentDeleteRequest = Body(..., description="删除文档索引请求参数")
):
    """
    删除文档索引
    
    参数:
    - user_id: 用户ID
    - ids: 文档ID列表
    - index_types: 索引类型列表 (可选,默认所有类型)
    
    返回:
    - 删除成功的文档ID列表
    """

    try:
        result = await document_service.delete_document(
            user_id=doc_delete.user_id,
            ids=doc_delete.ids,
            index_types=doc_delete.index_types,
        )
    except Exception as e:
        return AppException(code=500, message='删除规则索引失败')
    return result


@router.get("/document/rule-types", summary="获取文档索引规则类型列表")
async def get_document_index_rule_type(
    request: Request,
    user_id: int
):
    """
    获取文档索引规则类型列表
    
    参数:
    - user_id: 用户ID
    
    返回:
    - 规则类型列表,包含 id 和 rule_type
    """
    try:
        result = await document_service.get_document_index_rule_type(
            user_id=user_id,
        )
    except Exception as e:
        raise AppException(code=500, message=f'获取规则类型列表失败: {str(e)}')
    return result

