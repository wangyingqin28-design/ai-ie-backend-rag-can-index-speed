"""
材质类型管理路由
"""
import traceback
from typing import List, Dict, Any
from fastapi import APIRouter, Request, Query, Path, Body
from app.schemas.system_manage.CaiZhiLeiXing_schema import (
    CaiZhiLeiXingCreateRequest,
    CaiZhiLeiXingUpdateRequest,
    CaiZhiLeiXingBatchDeleteRequest
)
from app.schemas.system_manage.sys_schema import SearchRequest
from app.services.system_manage.CaiZhiLeiXing_service import CaiZhiLeiXingService
from app.utils.exceptions import ValidationException, NotFoundException, AppException
from app.utils.response import Success

router = APIRouter(prefix="/sys", tags=["箱包材质类型管理"])

@router.post(
    "/CaiZhiLeiXing/create",
    summary="创建材质类型",
    description="创建新的材质类型种类"
)
async def create_caiZhiLeiXing(
        request: Request,
        caiZhiLeiXing_data: CaiZhiLeiXingCreateRequest = Body(..., description="材质类型数据"),
):
    """
    创建新的材质类型

    - **材质类型名称** (caiZhiMingCheng): 必填，最长255字符

    返回创建的材质类型信息
    """
    try:
        # 调用服务层创建材质类型
        response_data = CaiZhiLeiXingService.create_caiZhiLeiXing(
            request=request,
            caiZhiLeiXing_data=caiZhiLeiXing_data,
        )
        return Success(
            msg="材质类型创建成功",
            data=response_data
        )
    except ValidationException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except NotFoundException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except Exception as e:
        traceback.print_exc()
        raise AppException(
            code=500,
            message="创建材质类型失败,服务器内部错误 ",
            details=(str(e))
        )
@router.post(
    "/CaiZhiLeiXing/search/",
    summary="搜索材质类型（分页）",
    description="分页搜索材质类型，支持材质类型名称模糊搜索",
)
async def search_caiZhiLeiXing(
        request: Request,
        searchRequest: SearchRequest = Body(..., description="请求分页搜索"),
):
    """
    分页搜索标材质类型
    - **keyword**: 搜索关键词（可选，默认为空）
    - **page**: 页码（可选，默认为1）
    - **page_size**: 每页数量（可选，默认20，最大100）
    返回分页的材质类型列表
    """
    try:
        # 参数校验
        if searchRequest.page < 1:
            raise ValidationException(
                message="页码必须大于0",
                details={"page": searchRequest.page}
            )

        if searchRequest.page_size < 1 or searchRequest.page_size > 100:
            raise ValidationException(
                message="每页数量必须在1-100之间",
                details={"page_size": searchRequest.page_size}
            )
        # 调用服务层搜索材质类型
        from app.services.system_manage.CaiZhiLeiXing_service import CaiZhiLeiXingService
        result = CaiZhiLeiXingService.search_CaiZhiLeiXing(
            request=request,
            keyword=searchRequest.search_keyword,
            page=searchRequest.page,
            page_size=searchRequest.page_size
        )
        return Success(
            msg="搜索成功",
            data=result
        )
    except ValidationException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except NotFoundException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except Exception as e:
        traceback.print_exc()
        raise AppException(
            code=500,
            message="搜索材质类型失败，服务器内部错误",
            details=(str(e))
        )


@router.put(
    "/CaiZhiLeiXing/{czlxId}",
    summary="更新材质类型",
    description="更新材质类型信息，ID必填，其他选填"
)
async def update_caiZhiLeiXing(
        request: Request,
        update_data: CaiZhiLeiXingUpdateRequest = Body(..., description="更新数据")

):
    """
    更新材质类型信息
    - **czlxId**: 材质类型ID（路径参数）
    - **更新数据**: 需要更新的字段
    返回更新后的材质类型信息
    """
    update_dict = update_data.dict(exclude_none=True)
    try:
        from app.services.system_manage.CaiZhiLeiXing_service import CaiZhiLeiXingService
        # 调用服务层更新材质类型
        item = CaiZhiLeiXingService.update_caiZhiLeiXing(
            request=request,
            czlxId=update_data.czlxId,
            user_id=update_data.up_userid,
            update_data=update_data
        )
        return Success(
            msg="更新材质类型成功",
            data=item
        )
    except ValidationException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except NotFoundException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except Exception as e:
        # 未知异常记录日志并返回500错误
        traceback.print_exc()
        raise AppException(
            code=500,
            message="更新材质类型失败",
            details=(str(e))
        )


@router.post(
    "/CaiZhiLeiXing/restore/{czlxId}",
    summary="恢复删除的材质类型",
    description="恢复软删除材质类型（标记为未删除状态，清空删除人员）"
)
async def restore_caiZhiLeiXing(
        request: Request,
        user_id: int = Query(..., description="用户唯一标识"),
        czlxId: int = Path(..., description="材质类型ID"),
):
    try:
        # 参数校验
        if not czlxId or czlxId < 0:
            raise ValidationException(
                message="材质类型ID无效",
                details={"材质类型ID": czlxId}
            )
        if not (isinstance(czlxId, int) and len(str(czlxId)) == 16):
            raise ValidationException(
                message="材质类型ID必须为16位正整数",
                details={"材质类型ID": czlxId, "error": "ID长度非16位或非正整数"}
            )
        # userid检验
        if not (isinstance(user_id, int) and len(str(user_id)) == 16):
            raise ValidationException(
                message="操作人ID必须为16位正整数",
                details={"操作人ID": user_id, "error": "ID长度非16位或非正整数"}
            )
        from app.services.system_manage.CaiZhiLeiXing_service import CaiZhiLeiXingService
        # 调用服务层恢复材质类型
        success = CaiZhiLeiXingService.restore_caiZhiLeiXing(
            request=request,
            czlxId=czlxId,
            user_id=user_id
        )

        return Success(
            msg="恢复材质类型成功",
            data={"restore": success}
        )
    except ValidationException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except NotFoundException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except Exception as e:
        # 未知异常记录日志并返回500错误
        traceback.print_exc()
        raise AppException(
            code=500,
            message="恢复材质类型失败 ",
            details=(str(e))
        )


@router.patch(
    "/CaiZhiLeiXing/delete/",
    summary="批量删除的材质类型",
    description="批量软删除材质类型（标记为删除状态，删除人员）"
)
async def Batch_delete_caiZhiLeiXing(
        request: Request,
        deleted_request: CaiZhiLeiXingBatchDeleteRequest = Body(..., description="批量删除请求体"),
):
    """
    批量删除材质类型
    """
    try:
        delete_count = CaiZhiLeiXingService.batch_delete_caiZhiLeiXing(
            request=request,
            czlx_ids=deleted_request.czlx_ids,
            user_id=deleted_request.del_userid
        )
        return Success(
            msg=f"成功删除{str(delete_count)}条记录",
            data={"delete": delete_count}
        )
    except ValidationException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except NotFoundException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except Exception as e:
        traceback.print_exc()
        raise AppException(
            code=500,
            message="批量删除材质类型失败 ",
            details=(str(e))
        )


@router.get(
    "/CaiZhiLeiXing/search_all/",
    response_model=List[Dict[str, Any]],
    summary="获取所有材质类型信息",
    description="返回材质类型数据，包含ID和名称"
)
async def get_all_caiZhiLeiXing(request: Request,keywords:str=None):

    """
    获取所有材质类型信息

    - **返回格式**: [{"query.czlxId": int, "query.caiZhiMingCheng": str}, ...]
    """
    try:

        results = CaiZhiLeiXingService.search_all_caiZhiLeiXing(request=request,keywords=keywords)
        return Success(
            msg="搜索成功",
            data={"results": results}
        )
    except ValidationException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except NotFoundException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except Exception as e:
        traceback.print_exc()
        raise AppException(
            code=500,
            message="搜索材质类型失败",
            details={"error": str(e)}
        )




