"""
公司工价管理路由
"""
import traceback
from fastapi import APIRouter, Request, Query, Path, Body

from app.config import settings
from app.schemas.system_manage.GongSiGongJia_schema import (
    GongSiGongJiaCreateRequest,
    GongSiGongJiaUpdateRequest,
    GongSiGongJiaBatchDeleteRequest
)
from app.schemas.system_manage.sys_schema import SearchRequest
from app.services.system_manage.GongSiGongJia_service import GongSiGongJiaService
from app.utils.exceptions import ValidationException, NotFoundException, AppException,PermissionDeniedException
from app.utils.response import Success
router = APIRouter(prefix="/sys", tags=["公司工价管理"])


@router.post(
    "/GongSiGongJia/create",
    summary="创建公司工价",
    description="创建新的公司工价记录"
)
async def create_GongSiGongJia(
        request: Request,
        gongSiGongjia_data: GongSiGongJiaCreateRequest = Body(..., description="公司工价数据"),
):
    """
    创建新的公司工价

    - **公司工价公司ID** (gsId): 必填，最长255字符
    - **公司工价描述** (gongXuMiaoShu): 可选，最长255字符
    - **工种ID** (xbgzId): 
    - **工价ID** (gongJia): 

    返回创建的公司工价信息
    """
    try:
        # 调用服务层创建公司工价
        response_data = GongSiGongJiaService.create_gongSiGongjia(
            request=request,
            gongSiGongjia_data=gongSiGongjia_data.dict(exclude_none=True),
            user_id=gongSiGongjia_data.in_userid
        )

        # 返回成功响应
        return Success(
            msg="公司工价创建成功",
            data=response_data
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="创建公司工价失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )
@router.post(
    "/GongSiGongJia/search_admin/",
    summary="搜索标准公司工价（分页）",
    description="分页搜索标准公司工价，支持工种模糊搜索，用户Id必传",
)
async def search_GongSiGongJia_admin(
        request: Request,
        searchRequest: SearchRequest = Body(..., description="请求分页搜索"),
):
    """
    分页搜索标准公司工价
    - **keyword** 地区编码
    - **page**: 页码（可选，默认为1）
    - **page_size**: 每页数量（可选，默认20，最大100）
    返回分页的公司工价列表
    """
    try:

        # 调用服务层搜索公司工价
        result = GongSiGongJiaService.search_gongSiGongjia_admin(
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
            message="搜索公司工价失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )

@router.post(
    "/GongSiGongJia/search_user/",
    summary="搜索标准公司工价（分页）",
    description="分页搜索标准公司工价，支持工种模糊搜索，用户Id必传",
)
async def search_GongSiGongJia_user(
        request: Request,
        searchRequest: SearchRequest = Body(..., description="请求分页搜索"),
):
    """
    分页搜索标准公司工价
    - **keyword** 地区编码
    - **page**: 页码（可选，默认为1）
    - **page_size**: 每页数量（可选，默认20，最大100）
    返回分页的公司工价列表
    """
    try:

        # 调用服务层搜索公司工价
        result = GongSiGongJiaService.search_gongSiGongjia_user(
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
            message="搜索公司工价失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


@router.put(
    "/GongSiGongJia/{gsgjId}",
    summary="更新公司工价",
    description="更新公司工价信息,工种ID、用户ID必填"
)
async def update_GongSiGongJia(
        request: Request,
        update_data: GongSiGongJiaUpdateRequest = Body(..., description="更新数据")

):
    """
    更新公司工价信息
    - **gsgjId**: 公司工价ID（路径参数）
    - **更新数据**: 需要更新的字段
    返回更新后的公司工价信息
    """
    try:

        from app.services.system_manage.GongSiGongJia_service import GongSiGongJiaService
        # 调用服务层更新公司工价
        item = GongSiGongJiaService.update_gongSiGongjia(
            request=request,
            update_data=update_data,
            gsgjId=update_data.gsgjId,
            user_id=update_data.up_userid
        )
        return Success(
            msg="更新公司工价成功",
            data=item
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="更新公司工价失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


@router.post(
    "/GongSiGongJia/restore/{gsgjId}",
    summary="恢复删除的公司工价",
    description="恢复软删除公司工价（标记为未删除状态，清空删除人员）",
)
async def restore_gongSiGongjia(
        request: Request,
        user_id: int = Query(..., description="用户唯一标识"),
        gsgjId: int = Path(..., description="公司工价ID"),
):
    try:
        # 参数校验
        if not gsgjId or gsgjId < 0:
            raise ValidationException(
                message="公司工价ID无效",
                details={"gsgjId": gsgjId}
            )
        if not (isinstance(gsgjId, int) and len(str(gsgjId)) == 16):
            raise ValidationException(
                message="公司工价ID必须为16位正整数",
                details={"gsgjId": gsgjId, "error": "ID长度非16位或非正整数"}
            )
        # userid检验
        if not (isinstance(user_id, int) and len(str(user_id)) == 16):
            raise ValidationException(
                message="操作人ID必须为16位正整数",
                details={"userid": user_id, "error": "ID长度非16位或非正整数"}
            )
        from app.services.system_manage.GongSiGongJia_service import GongSiGongJiaService
        # 调用服务层恢复公司工价
        success = GongSiGongJiaService.restore_GongSiGongJia(
            request=request,
            gsgjId=gsgjId,
            user_id=user_id
        )
        return Success(
            msg="恢复公司工价成功",
            data={"restore": success}
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="恢复公司工价失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


@router.patch(
    "/GongSiGongJia/deleteGongSiGongJia/",
    summary="批量删除的公司工价",
    description="批量软删除公司工价（标记为删除状态，删除人员）"
)
async def Batch_delete_gongSiGongjia(
        request: Request,
        deleted_request: GongSiGongJiaBatchDeleteRequest = Body(..., description="批量删除请求体"),
):
    """
    批量删除公司工价
    """
    try:
        delete_count = GongSiGongJiaService.batch_delete_gongSiGongjia(
            request=request,
            gsgj_ids=deleted_request.gsgj_ids,
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
            message="删除公司工价失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


