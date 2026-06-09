import traceback

from fastapi import APIRouter, Request, Body

from app.config import settings
from app.schemas.system_manage.LiShiGongJia_schema import LiShiGongJiaRequest
from app.services.system_manage.LiShiGongJia_service import LiShiGongJiaService
from app.utils.exceptions import ValidationException, NotFoundException, AppException, PermissionDeniedException
from app.utils.response import Success

router = APIRouter(prefix="/LiShiGongJia",tags=["历史工价管理"])
@router.post(
    "/LiShiGongJia/search_admin/",
    summary="搜索标准历史工价（分页）",
    description="分页搜索标准历史工价,关键词为区域工价或公司工价的主键,关键词必填",
)
async def search_LiShiGongJia_admin(
        request: Request,
        searchRequest: LiShiGongJiaRequest = Body(..., description="请求分页搜索"),
):
    """
    分页搜索标准历史工价
    - **keyword** 工价ID
    - **page**: 页码（可选，默认为1）
    - **page_size**: 每页数量（可选，默认20，最大100）
    - **userid**:用户ID
    - **gjId**:工价ID
    返回分页的历史工价列表
    """
    try:
        # 调用服务层搜索历史工价
        from app.services.system_manage.LiShiGongJia_service import LiShiGongJiaService
        result = LiShiGongJiaService.search_LiShiGongjia_admin(
            request=request,
            page=searchRequest.page,
            gjId=searchRequest.gjId,
            page_size=searchRequest.page_size,
            userid=searchRequest.userid,
        )
        # 直接返回result，它会自动被LiShiGongJiaResponse验证
        return Success(msg="搜索成功",data=result)
    except ValidationException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except NotFoundException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except PermissionDeniedException as e:
        raise e
    except Exception as e:
        # 未知异常记录日志并返回500错误
        raise AppException(
            code=500,
            message="搜索历史工价失败 ",
            details={"error": str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )
@router.post(
    "/LiShiGongJia/search_user/",
    summary="搜索标准历史工价（分页）",
    description="分页搜索标准历史工价,关键词为区域工价或公司工价的主键,关键词必填",
)
async def search_LiShiGongJia_user(
        request: Request,
        searchRequest: LiShiGongJiaRequest = Body(..., description="请求分页搜索"),
):
    """
    分页搜索标准历史工价
    - **keyword** 工价ID
    - **page**: 页码（可选，默认为1）
    - **page_size**: 每页数量（可选，默认20，最大100）
    返回分页的历史工价列表
    """
    try:
        # 调用服务层搜索历史工价
        result = LiShiGongJiaService.search_LiShiGongjia_user(
            request=request,
            page=searchRequest.page,
            gjId=searchRequest.gjId,
            page_size=searchRequest.page_size,
            userid=searchRequest.userid,
        )

        # 直接返回result，它会自动被LiShiGongJiaResponse验证
        return Success(msg="搜索成功",data=result)
    except ValidationException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except NotFoundException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except PermissionDeniedException as e:
        raise e
    except Exception as e:
        # 未知异常记录日志并返回500错误
        raise AppException(
            code=500,
            message="搜索历史工价失败 ",
            details={"error": str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )

