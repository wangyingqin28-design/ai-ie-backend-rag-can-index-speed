# 在 router 文件中添加以下内容
from pydantic import BaseModel
from fastapi import Depends, APIRouter, Request, Query, Path, Body
from app.services.working_price.bag_process_service import XiangBaoGongXuService
from app.utils.response import Success
from fastapi.responses import StreamingResponse
router = APIRouter(prefix="/working_price", tags=["箱包工时工价推理管理"])

# 定义请求体（若使用 POST JSON）
@router.post("/infer-times/{xbkhId}")
async def infer_times(
    xbkhId: int,
    request: Request,
    user_id: int,
):
    service = XiangBaoGongXuService()
    result = await service.infer_and_update_times(xbkhId, request, user_id)
    return Success(data=result)

@router.post("/calculate-gongjia/{xbkhId}")
async def calculate_gongjia(
    xbkhId: int,
    mode: int,
    request: Request,
    user_id: int,
):
    service = XiangBaoGongXuService()
    result = await service.calculate_and_update_gongjia(mode, xbkhId, request, user_id)
    return Success(data=result)
@router.post("/infer-times-stream/{xbkhId}")
async def infer_times_stream(
    xbkhId: int,
    request: Request,
    user_id: int,
):
    service = XiangBaoGongXuService()
    return StreamingResponse(
        service.infer_and_update_times_sse(xbkhId, request, user_id),
        media_type="text/event-stream"
    )