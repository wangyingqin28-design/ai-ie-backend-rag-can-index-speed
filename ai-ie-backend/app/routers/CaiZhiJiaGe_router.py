"""
材质价格管理路由
"""
import traceback
from fastapi import APIRouter, Request, Query, Path, Body

from app.config import settings
from app.schemas.system_manage.CaiZhiJiaGe_schema import (
    CaiZhiJiaGeCreateRequest,
    CaiZhiJiaGeUpdateRequest,
    CaiZhiJiaGeBatchDeleteRequest
)
from app.schemas.system_manage.sys_schema import SearchRequest
from app.services.system_manage.CaiZhiJiaGe_service import CaiZhiJiaGeService
from app.utils.exceptions import ValidationException, AppException
from app.utils.response import Success

router = APIRouter(prefix="/sys", tags=["材质价格管理"])


@router.post(
    "/CaiZhiJiaGe/create",
    summary="创建材质价格",
    description="创建新的材质价格记录"
)
async def create_CaiZhiJiaGe(
        request: Request,
        caiZhiJiaGe_data: CaiZhiJiaGeCreateRequest = Body(..., description="材质价格数据"),
):
    """
    创建新的材质价格

    - **材质价格** (czjg): 必填
    - **材质ID** (xbczId): 必填
    - **创建人ID** (in_userid): 必填

    返回创建的材质价格信息
    """
    try:
        # 调用服务层创建材质价格
        response_data = CaiZhiJiaGeService.create_caiZhiJiaGe(
            request=request,
            caiZhiJiaGe_data=caiZhiJiaGe_data.dict(exclude_none=True),
            user_id=caiZhiJiaGe_data.in_userid
        )

        # 返回成功响应
        return Success(
            msg="材质价格创建成功",
            data=response_data
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="创建材质价格失败",
            details={'error': str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


@router.post(
    "/CaiZhiJiaGe/search_admin/",
    summary="搜索材质价格（分页，管理员）",
    description="分页搜索材质价格，支持材质模糊搜索，用户Id必传",
)
async def search_CaiZhiJiaGe_admin(
        request: Request,
        searchRequest: SearchRequest = Body(..., description="请求分页搜索"),
):
    """
    分页搜索材质价格（管理员视图）
    - **search_keyword**: 搜索关键词（材质名称）
    - **page**: 页码（可选，默认为1）
    - **page_size**: 每页数量（可选，默认20，最大100）
    返回分页的材质价格列表，包含公司名称
    """
    try:
        # 调用服务层搜索材质价格（管理员）
        result = CaiZhiJiaGeService.search_caiZhiJiaGe_admin(
            request=request,
            page=searchRequest.page,
            keyword=searchRequest.search_keyword,
            page_size=searchRequest.page_size,
            userid=searchRequest.userid
        )

        return Success(
            msg="搜索成功",
            data=result
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="搜索材质价格失败",
            details={'error': str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


@router.post(
    "/CaiZhiJiaGe/search_user/",
    summary="搜索材质价格（分页，普通用户）",
    description="分页搜索材质价格，支持材质模糊搜索，用户Id必传",
)
async def search_CaiZhiJiaGe_user(
        request: Request,
        searchRequest: SearchRequest = Body(..., description="请求分页搜索"),
):
    """
    分页搜索材质价格（普通用户视图，仅显示本公司数据）
    - **search_keyword**: 搜索关键词（材质名称）
    - **page**: 页码（可选，默认为1）
    - **page_size**: 每页数量（可选，默认20，最大100）
    返回分页的材质价格列表，不包含公司名称
    """
    try:
        # 调用服务层搜索材质价格（普通用户）
        result = CaiZhiJiaGeService.search_caiZhiJiaGe_user(
            request=request,
            page=searchRequest.page,
            keyword=searchRequest.search_keyword,
            page_size=searchRequest.page_size,
            userid=searchRequest.userid
        )
        return Success(
            msg="搜索成功",
            data=result
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="搜索材质价格失败",
            details={'error': str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


@router.put(
    "/CaiZhiJiaGe/{czjgId}",
    summary="更新材质价格",
    description="更新材质价格信息，材质ID、用户ID必填"
)
async def update_CaiZhiJiaGe(
        request: Request,
        update_data: CaiZhiJiaGeUpdateRequest = Body(..., description="更新数据")
):
    """
    更新材质价格信息
    - **czjgId**: 材质价格ID（在请求体中）
    - **更新数据**: 需要更新的字段
    返回更新后的材质价格信息
    """
    try:
        # 调用服务层更新材质价格
        item = CaiZhiJiaGeService.update_caiZhiJiaGe(
            request=request,
            update_data=update_data,
            czjgId=update_data.czjgId,
            user_id=update_data.up_userid
        )
        return Success(
            msg="更新材质价格成功",
            data=item
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="更新材质价格失败",
            details={'error': str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


@router.post(
    "/CaiZhiJiaGe/restore/{czjgId}",
    summary="恢复删除的材质价格",
    description="恢复软删除材质价格（标记为未删除状态，清空删除时间）",
)
async def restore_caiZhiJiaGe(
        request: Request,
        user_id: int = Query(..., description="用户唯一标识"),
        czjgId: int = Path(..., description="材质价格ID"),
):
    try:
        # 参数校验
        if not czjgId or czjgId < 0:
            raise ValidationException(
                message="材质价格ID无效",
                details={"czjgId": czjgId}
            )
        if not (isinstance(czjgId, int) and len(str(czjgId)) == 16):
            raise ValidationException(
                message="材质价格ID必须为16位正整数",
                details={"czjgId": czjgId, "error": "ID长度非16位或非正整数"}
            )
        # userid检验
        if not (isinstance(user_id, int) and len(str(user_id)) == 16):
            raise ValidationException(
                message="操作人ID必须为16位正整数",
                details={"userid": user_id, "error": "ID长度非16位或非正整数"}
            )
        # 调用服务层恢复材质价格
        success = CaiZhiJiaGeService.restore_caiZhiJiaGe(
            request=request,
            czjgId=czjgId,
            user_id=user_id
        )
        return Success(
            msg="恢复材质价格成功",
            data={"restore": success}
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="恢复材质价格失败",
            details={'error': str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


@router.patch(
    "/CaiZhiJiaGe/deleteCaiZhiJiaGe/",
    summary="批量删除材质价格",
    description="批量软删除材质价格（标记为删除状态，记录删除时间）"
)
async def batch_delete_caiZhiJiaGe(
        request: Request,
        deleted_request: CaiZhiJiaGeBatchDeleteRequest = Body(..., description="批量删除请求体"),
):
    """
    批量删除材质价格
    """
    try:
        delete_count = CaiZhiJiaGeService.batch_delete_caiZhiJiaGe(
            request=request,
            czjg_ids=deleted_request.czjg_ids,
            user_id=deleted_request.del_userid
        )
        return Success(
            msg=f"成功删除{str(delete_count)}条记录",
            data={"delete": delete_count}
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="删除材质价格失败",
            details={'error': str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )