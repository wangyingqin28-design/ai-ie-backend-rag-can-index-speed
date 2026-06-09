import traceback
from typing import List, Dict, Any

from fastapi import APIRouter, Request, Query, Path, Body

from app.schemas.system_manage.XiangBaoGongZhong_schema import (
    XiangBaoGongZhongUpdateRequest,
    XiangBaoGongZhongBatchDeleteRequest, XiangBaoGongZhongSearchResponse
)
from app.schemas.system_manage.sys_schema import SearchRequest
from app.services.system_manage.DiQuBianMa_service import DiQuBianMaService
from app.services.system_manage.XiangBaoGongZhong_service import XiangBaoGongZhongService
from app.utils.exceptions import ValidationException, NotFoundException, AppException
from app.utils.response import Success

router = APIRouter(prefix="/sys",tags=["区域编码表"])

@router.get(
    "/DiQuBianMa/search_all/",
    summary="获取所有区域编码信息",
    description="返回区域编码数据，包含ID和名称"
)
async def get_all_diQuBianMa(request: Request):
    """
    获取所有工种信息

    - **返回格式**: [{"query.xbgzId": int, "query.gongZhongMingCheng": str}, ...]
    """
    try:

        result = DiQuBianMaService.search_all_DiQuBianMa(request=request)
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
            message="搜索区域数据失败 "
        )