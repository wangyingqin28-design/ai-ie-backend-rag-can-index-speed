"""
标准工序管理路由
"""
import traceback

from fastapi import APIRouter, Request, Query, Path, Body
from loguru import logger

from app.config import settings
from app.schemas.system_manage.BiaoZhunGongXu_schema import (
    BiaoZhunGongXuCreateRequest,
    BiaoZhunGongXuUpdateRequest,
    BiaoZhunGongXuBatchDeleteRequest
)
from app.schemas.system_manage.sys_schema import SearchRequest
from app.services.system_manage.BiaoZhunGongXu_service import BiaoZhunGongXuService
from app.utils.exceptions import ValidationException, NotFoundException, AppException, PermissionDeniedException
from app.utils.response import Success

router = APIRouter(prefix="/sys", tags=["标准工序管理"])


@router.post(
    "/BiaoZhunGongXu/create",
    summary="创建标准工序",
    description="创建新的标准工序记录，工序名称，工种ID不能为空，其中工种ID必须要在工种表里存在,用户ID必须为16位正整数"
)
async def create_BiaoZhunGongXu(
        request: Request,
        biaoZhunGongXu_data: BiaoZhunGongXuCreateRequest = Body(..., description="工序数据"),
):
    """
    创建新的标准工序
    返回创建的标准工序信息
    """
    try:
        from app.services.system_manage.BiaoZhunGongXu_service import BiaoZhunGongXuService
        # 调用服务层创建工序
        response_data = BiaoZhunGongXuService.create_biaoZhunGongXu(
            request=request,
            biaoZhunGongXu_data=biaoZhunGongXu_data.dict(exclude_none=True),
            user_id=biaoZhunGongXu_data.in_userid
        )

        # 返回成功响应
        return Success(
            msg="标准工序创建成功",
            data=response_data
        )

    except AppException as e:
        raise e
    except Exception as e:
        # 未知异常记录日志并返回500错误
        raise AppException(
            code=500,
            message="创建工序失败 ",
            details={"error": str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )
@router.post(
    "/BiaoZhunGongXu/search_admin/",
    summary="搜索标准工序（分页）-后台管理界面",
    description="分页搜索标准工序，支持工序名称模糊搜索，页码必须大于0，每页数量必须在1-100之间",
)
async def search_BiaoZhunGongXu_admin(
        request: Request,
        searchRequest: SearchRequest = Body(..., description="请求分页搜索"),
):
    """
    分页搜索标准工序
    - **keyword**: 搜索关键词（可选，默认为空）
    - **page**: 页码（可选，默认为1）
    - **page_size**: 每页数量（可选，默认20，最大100）
    返回分页的工序列表
    """
    try:
        # 调用服务层搜索工序
        result = BiaoZhunGongXuService.search_biaoZhunGongXu_admin(
            request=request,
            keyword=searchRequest.search_keyword,
            page=searchRequest.page,
            page_size=searchRequest.page_size,
            userid = searchRequest.userid
        )
        return Success(
            msg="搜索成功",
            data=result
        )
    except AppException as e:
        raise e
    except Exception as e:
        # 未知异常记录日志并返回500错误
        raise AppException(
            code=500,
            message="搜索工序失败 ",
            details={"error":str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


@router.post(
    "/BiaoZhunGongXu/search_user/",
    summary="搜索标准工序（分页）-用户界面",
    description="分页搜索标准工序，支持工序名称模糊搜索，页码必须大于0，每页数量必须在1-100之间",
)
async def search_BiaoZhunGongXu_user(
        request: Request,
        searchRequest: SearchRequest = Body(..., description="请求分页搜索"),
):
    """
    分页搜索标准工序
    - **keyword**: 搜索关键词（可选，默认为空）
    - **page**: 页码（可选，默认为1）
    - **page_size**: 每页数量（可选，默认20，最大100）
    返回分页的工序列表
    """
    try:
        # 调用服务层搜索工序
        result = BiaoZhunGongXuService.search_biaoZhunGongXu_user(
            request=request,
            keyword=searchRequest.search_keyword,
            page=searchRequest.page,
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
        # 未知异常记录日志并返回500错误
        traceback.print_exc()
        raise AppException(
            code=500,
            message="搜索工序失败 ",
            details={"error": str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


@router.put(
    "/BiaoZhunGongXu/{bzgxId}",
    summary="更新标准工序",
    description="更新标准工序信息,更新数据不能为空，操作人员ID必须为16位正整数，工种ID（必填），工序名称与工序描述选填，工序名称不为空"
)
async def update_BiaoZhunGongXu(
        request: Request,
        update_data: BiaoZhunGongXuUpdateRequest = Body(..., description="更新数据")

):
    """
    更新标准工序信息
    - **bzgxId**: 标准工序ID（路径参数）
    - **更新数据**: 需要更新的字段
    返回更新后的工序信息
    """
    try:
        print(update_data)
        # 调用服务层更新工序
        item = BiaoZhunGongXuService.update_biaoZhunGongXu(
            request=request,
            update_data=update_data,
            bzgxId=update_data.bzgxId,
            user_id=update_data.up_userid,

        )

        return Success(
            msg="更新工序成功",
            data=item
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="更新工序失败 ",
            details={"error":str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )
@router.post(
    "/BiaoZhunGongXu/restore/{bzgxId}",
    summary="恢复删除的标准工序",
    description="恢复软删除标准工序（标记为未删除状态，清空删除人员）"
)
async def restore_biaoZhunGongXu(
        request: Request,
        user_id: int = Query(..., description="用户唯一标识"),
        bzgxId: int = Path(..., description="标准工序ID"),
):
    try:
        # 参数校验
        if not bzgxId or bzgxId < 0:
            raise ValidationException(
                message="工序ID无效",
                details={"bzgxId": bzgxId}
            )
        if not (isinstance(bzgxId, int) and len(str(bzgxId)) == 16):
            raise ValidationException(
                message="标准工序ID必须为16位正整数",
                details={"bzgxId": bzgxId, "error": "ID长度非16位或非正整数"}
            )
        # userid检验
        if not (isinstance(user_id, int) and len(str(user_id)) == 16):
            raise ValidationException(
                message="操作人ID必须为16位正整数",
                details={"userid": user_id, "error": "ID长度非16位或非正整数"}
            )
        from app.services.system_manage.BiaoZhunGongXu_service import BiaoZhunGongXuService
        # 调用服务层恢复工序
        success = BiaoZhunGongXuService.restore_biaoZhunGongXu(
            request=request,
            bzgxId=bzgxId,
            user_id=user_id
        )
        return Success(
            msg="恢复工序成功",
            data={"restore": success}
        )
    except AppException as e:
        raise e
    except Exception as e:
        # 未知异常记录日志并返回500错误
        raise AppException(
            code=500,
            message="恢复工序失败",
            details={"error":str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None}
        )
@router.patch(
    "/BiaoZhunGongXu/delete/",
    summary="批量删除的标准工序",
    description="批量软删除标准工序（标记为删除状态，删除人员）"
)
async def Batch_delete_biaoZhunGongXu(
        request: Request,
        deleted_request: BiaoZhunGongXuBatchDeleteRequest = Body(..., description="批量删除请求体"),
):
    """
    批量删除标准工序
    """
    try:
        delete_count = BiaoZhunGongXuService.batch_delete_biaoZhunGongXu(
            request=request,
            bzgxIds=deleted_request.bzgx_ids,
            user_id=deleted_request.del_userid
        )
        return Success(
            msg=f"成功删除{str(delete_count)}条记录",
            data={"delete": delete_count}
        )
    except AppException as e:
        raise e
    except Exception as e:
        # 未知异常记录日志并返回500错误
        raise AppException(
            code=500,
            message="删除工序失败",
            details={"error":str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None}
        )