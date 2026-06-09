"""
区域工价管理路由
"""
import traceback

from fastapi import APIRouter, Request, Query, Path, Body

from app.config import settings
from app.schemas.system_manage.QuYuGongJia_schema import (
    QuYuGongJiaResponseBase,
    QuYuGongJiaCreateRequest,
    QuYuGongJiaUpdateRequest,
    QuYuGongJiaBatchDeleteRequest
)
from app.schemas.system_manage.sys_schema import SearchRequest
from app.services.system_manage.QuYuGongJia_service import QuYuGongJiaService
from app.utils.exceptions import ValidationException, NotFoundException, AppException
from app.utils.response import Success

router = APIRouter(prefix="/sys", tags=["区域工价管理"])

@router.post(
    "/QuYuGongJia/create",
    summary="创建区域工价",
    description="创建新的区域工价记录"
)
async def create_QuYuGongJia(
        request: Request,
        quYuGongJia_data: QuYuGongJiaCreateRequest = Body(..., description="区域工价数据"),
):
    """
    创建新的区域工价

    - **区域工价地域编码** (dqbmId): 必填，最长255字符
    - **区域工价描述** (gongXuMiaoShu): 可选，最长255字符
    - **工种ID** (xbgzId): 
    - **工价ID** (gongJia): 

    返回创建的区域工价信息
    """
    try:
        from app.services.system_manage.QuYuGongJia_service import QuYuGongJiaService
        # 调用服务层创建区域工价
        response_data = QuYuGongJiaService.create_quYuGongJia(
            request=request,
            quYuGongJia_data=quYuGongJia_data.dict(exclude_none=True),
            user_id=quYuGongJia_data.in_userid
        )

        # 返回成功响应
        return Success(
            msg="区域工价创建成功",
            data=response_data
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="创建区域工价失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )
@router.post(
    "/QuYuGongJia/search/",
    summary="搜索标准区域工价（分页）",
    description="分页搜索标准区域工价，支持地域编码模糊搜索",
)
async def search_QuYuGongJia(
        request: Request,
        searchRequest: SearchRequest = Body(..., description="请求分页搜索"),
):
    """
    分页搜索标准区域工价
    - **keyword** 地区编码
    - **page**: 页码（可选，默认为1）
    - **page_size**: 每页数量（可选，默认20，最大100）
    - **关键词不填**
    返回分页的区域工价列表
    """
    try:
        # 调用服务层搜索区域工价
        from app.services.system_manage.QuYuGongJia_service import QuYuGongJiaService
        result = QuYuGongJiaService.search_quYuGongJia(
            request=request,
            page=searchRequest.page,
            keyword=searchRequest.search_keyword,
            page_size=searchRequest.page_size,
        )

        # 直接返回result，它会自动被QuYuGongJiaResponse验证
        return Success(
            msg="搜索成功",
            data=result
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="搜索区域工价失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )
    
@router.put(
    "/QuYuGongJia/{qygjId}",
    summary="更新区域工价",
    description="更新区域工价信息,基本为必填字段"
)
async def update_QuYuGongJia(
        request: Request,
        update_data: QuYuGongJiaUpdateRequest = Body(..., description="更新数据")

):
    """
    更新区域工价信息
    - **qygjId**: 区域工价ID（路径参数）
    - **更新数据**: 需要更新的字段
    返回更新后的区域工价信息
    """
    try:
        # 调用服务层更新区域工价
        item = QuYuGongJiaService.update_quYuGongJia(
            request=request,
            update_data=update_data,
            qygjId=update_data.qygjId,
            user_id=update_data.up_userid
        )
        return Success(
            msg="更新区域工价成功",
            data=item
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="更新区域工价失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )
    

@router.post(
    "/QuYuGongJia/restore/{qygjId}",
    summary="恢复删除的区域工价",
    description="恢复软删除区域工价（标记为未删除状态，清空删除人员）"
)
async def restore_quYuGongJia(
        request: Request,
        user_id: int = Query(..., description="用户唯一标识"),
        qygjId: int = Path(..., description="区域工价ID"),
):
    try:
        # 参数校验
        if not qygjId or qygjId < 0:
            raise ValidationException(
                message="区域工价ID无效",
                details={"qygjId": qygjId}
            )
        if not (isinstance(qygjId, int) and len(str(qygjId)) == 16):
            raise ValidationException(
                message="区域工价ID必须为16位正整数",
                details={"qygjId": qygjId, "error": "ID长度非16位或非正整数"}
            )
        # userid检验
        if not (isinstance(user_id, int) and len(str(user_id)) == 16):
            raise ValidationException(
                message="操作人ID必须为16位正整数",
                details={"userid": user_id, "error": "ID长度非16位或非正整数"}
            )
        # 调用服务层恢复区域工价
        success = QuYuGongJiaService.restore_QuYuGongJia(
            request=request,
            qygjId=qygjId,
            user_id=user_id
        )

        return Success(
            msg="恢复区域工价成功",
            data={"restore": success}
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="恢复区域工价失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )





@router.patch(
    "/QuYuGongJia/deleteQuYuGongJia/",
    summary="批量删除的区域工价",
    description="批量软删除区域工价（标记为删除状态，删除人员）"
)
async def Batch_delete_quYuGongJia(
        request: Request,
        deleted_request: QuYuGongJiaBatchDeleteRequest = Body(..., description="批量删除请求体"),
):
    """
    批量删除区域工价
    """
    try:
        delete_count = QuYuGongJiaService.batch_delete_quYuGongJia(
            request=request,
            qygj_ids=deleted_request.qygj_ids,
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
            message="删除区域工价失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


