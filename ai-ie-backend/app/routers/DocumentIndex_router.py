import traceback

from fastapi import APIRouter, Request, Body

from app.config import settings
from app.schemas.system_manage.DocumentIndex_schema import DocumentIndexDetailsSearchResponse
from app.schemas.system_manage.sys_schema import SearchRequest
from app.services.system_manage.DocumentIndex_service import DocumentIndexService
from app.utils.exceptions import AppException
from app.utils.response import Success

router = APIRouter(prefix="/sys", tags=["箱包规则管理"])

@router.get(
    "/XiangBaoGuiZe/{id}",
    summary="根据ID获取规则",
    description="根据ID获取单个规则详情"
)
async def get_documentIndex_by_id(
    request: Request,
    id: str,  # 路径参数
    userid: int,
):
    """
    根据ID获取规则详情

    - **id**: 规则ID

    返回详情
    """
    try:
        documentIndex = DocumentIndexService.get_documentIndex_by_id(
            id=id,
            request=request,userid=userid)
        response_data = DocumentIndexDetailsSearchResponse.model_validate(documentIndex).model_dump()

        return Success(
            msg="获取规则成功",
            data=response_data
        )
    except AppException:
        raise
    except Exception as e:
        raise AppException(
            code=500,
            message="获取单个规则失败",
            details={'error': str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )

@router.post(
    "/XiangBaoGuiZe/search_user/",
    summary="搜索标准公司规则（分页）-用户界面",
    description="分页搜索标准公司规则，支持规则内容模糊搜索，公司Id必传",
)
async def search_GongSiGongJia_user(
        request: Request,
        searchRequest: SearchRequest = Body(..., description="请求分页搜索"),
):
    """
    分页搜索标准公司工价
    - **keyword** 规则内容关键词
    - **page**: 页码（可选，默认为1）
    - **page_size**: 每页数量（可选，默认20，最大100）
    返回分页的公司工价列表
    """
    try:
        # 调用服务层搜索公司工价
        result = DocumentIndexService.search_documentIndex_user(
            request=request,
            page=searchRequest.page,
            keyword=searchRequest.search_keyword,
            page_size=searchRequest.page_size,
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
            message="获取规则失败",
            details={'error': str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )
@router.post(
    "/XiangBaoGuiZe/search_admin/",
    summary="搜索标准公司规则（分页）-后台管理界面",
    description="分页搜索标准公司规则，支持规则内容模糊搜索，公司Id必传",
)
async def search_GongSiGongJia_admin(
        request: Request,
        searchRequest: SearchRequest = Body(..., description="请求分页搜索"),
):
    """
    分页搜索标准公司工价
    - **keyword** 规则内容关键词
    - **page**: 页码（可选，默认为1）
    - **page_size**: 每页数量（可选，默认20，最大100）
    返回分页的公司工价列表
    """
    try:
        # 调用服务层搜索公司工价
        result = DocumentIndexService.search_documentIndex_admin(
            request=request,
            page=searchRequest.page,
            keyword=searchRequest.search_keyword,
            page_size=searchRequest.page_size,
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
            message="获取规则失败",
            details={'error': str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )
