# app/api/v1/endpoints/caoZuoRiZhi.py
from typing import Any
from fastapi import APIRouter, Request
from app.schemas.system_manage.CaoZuoRiZhi_schema import (
    CaoZuoRiZhiCreateRequest,
    CaoZuoRiZhiSearchRequest,
    CaoZuoRiZhiResponse,
    CaoZuoRiZhiRecoverResponse,
    CaoZuoRiZhiSearchResponse
)
import traceback
from app.services.system_manage.CaoZuoRiZhi_service import CaoZuoRiZhiService
from app.utils.exceptions import AppException,NotFoundException,ValidationException
from app.utils.response import Success
router = APIRouter(prefix="/sys",tags=["操作日志管理"])
@router.post("/CaoZuoRiZhi/search",summary="搜索日志",description="搜索日志")
async def search_cao_zuo_ri_zhi(
    request: Request,
    search_request: CaoZuoRiZhiSearchRequest
):
    """
    搜索操作日志
    """
    try:
        response = CaoZuoRiZhiService.search_caoZuoRiZhi(request, search_request)
        return Success(
            msg="搜索成功",
            data=response)
    except NotFoundException as e:
        raise e
    except ValidationException as e:
        raise e
    except Exception as e:
        traceback.print_exc()
        raise AppException(
            code=500,
            message="服务器内部错误",
            details={"error": str(e)}
        )

@router.post("/CaoZuoRiZhi/{czrzId}/recover",summary="恢复数据",description="恢复数据")
async def recover_data(
    request: Request,
    czrzId: int
):
    """
    执行数据恢复
    """
    return CaoZuoRiZhiService.recover_data(request, czrzId)

@router.get("/CaoZuoRiZhi/{czrzId}/",summary="根据ID搜索单个日志",description="根据ID搜索单个日志")
async def get_czrzId(
        request: Request,
        czrzId: int
):
    """
    根据ID搜索单个日志
    """
    try:
        CaoZuoRiZhiService.get_caoZuoRiZhi_by_id(
            request, czrzId)
    except NotFoundException as e:
        raise e
    except ValidationException as e:
        raise e
    except Exception as e:
        traceback.print_exc()
        raise AppException(
            code=500,
            message="服务器内部错误",
            details={"error": str(e)}
        )