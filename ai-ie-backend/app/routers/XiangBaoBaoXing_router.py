"""
包型管理路由
"""
import traceback

from fastapi import APIRouter, Request, Body, Query, Path

from app.config import settings
from app.schemas.system_manage.XiangBaoBaoXing_schema import (
    XiangBaoBaoXingSearchRequest, XiangBaoBaoXingCreateRequest, XiangBaoBaoXingUpdateRequest,
    XiangBaoBaoXingBatchDeleteRequest
)
from app.services.system_manage.XiangBaoBaoXing_service import XiangBaoBaoXingService
from app.utils.exceptions import ValidationException, AppException
from app.utils.response import Success

router = APIRouter(prefix="/sys", tags=["箱包包型管理"])

@router.post(
    "/BaoXing/create",
    summary="创建包型",
    description="创建新的包型种类"
)
async def create_xiangBaoBaoXing(
        request: Request,
        xiangBaoBaoXing_data: XiangBaoBaoXingCreateRequest = Body(..., description="包型数据"),
):
    """
    创建新的包型

    - **包型名称** (baoXingMingCheng): 必填，最长255字符

    返回创建的包型信息
    """
    try:
        # 调用服务层创建包型
        response_data = XiangBaoBaoXingService.create_xiangBaoBaoXing(
            request=request,
            xiangBaoBaoXing_data=xiangBaoBaoXing_data,
        )
        return Success(
            msg="包型创建成功",
            data=response_data
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="创建包型失败",
            details={'error': str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )

@router.post(
    "/BaoXing/search_admin/",
    summary="搜索包型（分页）-后台管理界面",
    description="分页搜索包型，支持包型名称模糊搜索,可含父类包型筛选、包型等级筛选,父类ID为0或者为null默认不做筛选，包型等级不填则填null，注：包型等级ID默认为0是有筛选的",
)
async def search_xiangBaoBaoXing_admin(
        request: Request,
        searchRequest: XiangBaoBaoXingSearchRequest = Body(..., description="请求分页搜索"),
):
    """
    分页搜索标包型
    - **keyword**: 搜索关键词包型名称（可选，默认为空）
    - **page**: 页码（可选，默认为1）
    - **page_size**: 每页数量（可选，默认20，最大100）
    - **parent_id**: 包型等级
    - **fubxId**: 父级包型ID(可选)
    返回分页的包型列表
    """
    try:
        # 调用服务层搜索包型
        result = XiangBaoBaoXingService.search_XiangBaoBaoXing_admin(
            request=request,
            keyword=searchRequest.search_keyword,
            page=searchRequest.page,
            page_size=searchRequest.page_size,
            parent_id=searchRequest.parent_id,
            fubxId=searchRequest.fubxId,
            userid=searchRequest.userid,
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
            message="更新包型失败",
            details={'error': str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )
@router.post(
    "/BaoXing/search_user/",
    summary="搜索包型（分页）-用户界面",
    description="分页搜索包型，支持包型名称模糊搜索,可含父类包型筛选、包型等级筛选,父类ID为0或者为null默认不做筛选，包型等级不填则填null，注：包型等级ID默认为0是有筛选的",
)
async def search_xiangBaoBaoXing_user(
        request: Request,
        searchRequest: XiangBaoBaoXingSearchRequest = Body(..., description="请求分页搜索"),
):
    """
    分页搜索标包型
    - **keyword**: 搜索关键词包型名称（可选，默认为空）
    - **page**: 页码（可选，默认为1）
    - **page_size**: 每页数量（可选，默认20，最大100）
    - **parent_id**: 包型等级
    - **fubxId**: 父级包型ID(可选)
    返回分页的包型列表
    """
    try:
        # 调用服务层搜索包型
        result = XiangBaoBaoXingService.search_XiangBaoBaoXing_user(
            request=request,
            keyword=searchRequest.search_keyword,
            page=searchRequest.page,
            page_size=searchRequest.page_size,
            parent_id=searchRequest.parent_id,
            fubxId=searchRequest.fubxId,
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
            message="更新包型失败",
            details={'error': str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


@router.put(
    "/BaoXing",
    summary="更新包型",
    description="更新包型信息，包型ID、用户ID必填"
)
async def update_xiangBaoBaoXing(
        request: Request,
        update_data: XiangBaoBaoXingUpdateRequest = Body(..., description="更新数据")
):
    """
    更新包型信息

    - **更新数据**: 需要更新的字段，必须包含xbbxId

    返回更新后的包型信息
    """
    try:

        item = XiangBaoBaoXingService.update_xiangBaoBaoXing(
            request=request,
            xbbxId=update_data.xbbxId,
            update_data=update_data
        )

        return Success(
            msg="更新包型成功",
            data=item
        )

    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="更新包型失败",
            details={
                'error': str(e),
                "traceback": traceback.format_exc().split("\n") if settings.debug else None
            }
        )
@router.patch(
    "/BaoXing/delete/",
    summary="批量删除的包型",
    description="批量软删除包型（标记为删除状态，删除人员）"
)
async def Batch_delete_xiangBaoBaoXing(
        request: Request,
        deleted_request: XiangBaoBaoXingBatchDeleteRequest = Body(..., description="批量删除请求体"),
):
    """
    批量删除包型
    """
    try:
        delete_count = XiangBaoBaoXingService.batch_delete_xiangBaoBaoXing(
            request=request,
            xbbx_ids=deleted_request.xbbx_ids,
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
            message="删除包型失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )
@router.post(
    "/BaoXing/restore/{xbbxId}",
    summary="恢复删除的包型",
    description="恢复软删除包型（标记为未删除状态，清空删除人员）"
)
async def restore_xiangBaoBaoXing(
        request: Request,
        user_id: int = Query(..., description="用户唯一标识"),
        xbbxId: int = Path(..., description="包型ID"),
):
    try:
        # 参数校验
        if not xbbxId or xbbxId < 0:
            raise ValidationException(
                message="包型ID无效",
                details={"xbbxId": xbbxId}
            )
        if not (isinstance(xbbxId, int) and len(str(xbbxId)) == 16):
            raise ValidationException(
                message="包型ID必须为16位正整数",
                details={"xbbxId": xbbxId, "error": "ID长度非16位或非正整数"}
            )
        # userid检验
        if not (isinstance(user_id, int) and len(str(user_id)) == 16):
            raise ValidationException(
                message="操作人ID必须为16位正整数",
                details={"userid": user_id, "error": "ID长度非16位或非正整数"}
            )
        # 调用服务层恢复包型
        success = XiangBaoBaoXingService.restore_xiangBaoBaoXing(
            request=request,
            xbbxId=xbbxId,
            user_id=user_id
        )
        return Success(
            msg="恢复包型成功",
            data={"restore": success}
        )
    except AppException as e:
        raise e
    except Exception as e:
        # 未知异常记录日志并返回500错误
        raise AppException(
            code=500,
            message="恢复包型失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )
@router.post(
    "/BaoXing/search_all/",
    summary="搜索所有的包型",
    description="搜索所有包型供下拉栏选择"
)
async def get_xiangBaoBaoXing_search_all(
    request: Request,
    userid:int,
    keywords: str = None  # 添加默认值
):
    if userid < 0 or len(str(userid)) != 16:
        raise ValidationException(
            message="userid必须为16位正整数"
        )
    try:
        results = XiangBaoBaoXingService.search_all_xiangBaoBaoXing(
            request=request,
            keywords=keywords,
            userid=userid,
        )
        return Success(
            msg="搜索成功",
            data={"results": results}
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="搜索包型失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )