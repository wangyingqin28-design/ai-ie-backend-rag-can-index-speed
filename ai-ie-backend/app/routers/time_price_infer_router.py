# app/routers/working_price/bag_router.py
import asyncio
import json
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse
from app.services.working_time.inference_service import InferenceService
from app.services.working_price.quote_calculation_service import QuoteCalculationService
from app.services.working_price.sse_manager import sse_manager
from app.utils.response import Success
from app.utils.exceptions import ValidationException


router = APIRouter(prefix="/time_price", tags=["箱包工时推理与工价更新管理"])

# 实例化服务
inference_service = InferenceService()
quote_service = QuoteCalculationService()
def validate_user_id(user_id: int) -> int:
    if not (10**15 <= user_id <= 10**16 - 1):
        raise ValidationException(message="user_id 必须是16位正整数")
    return user_id

# ==================== AI 工时推断（非流式） ====================
@router.post("/infer-times/{xbkhId}")
async def infer_times(
    xbkhId: int,
    request: Request,
    user_id: int = Query(..., description="用户ID")
):
    """AI 推断工时并批量更新（非流式）"""
    user_id = validate_user_id(user_id)
    result = await inference_service.infer_and_update_times(xbkhId, request, user_id)
    return Success(data=result)


# ==================== AI 工时推断（SSE 流式） ====================
@router.post("/infer-times-stream/{xbkhId}")
async def infer_times_stream(
    xbkhId: int,
    request: Request,
    user_id: int = Query(..., description="用户ID")
):
    """SSE 流式版本：分批调用 AI 推断工时，实时推送进度"""
    user_id = validate_user_id(user_id)
    return StreamingResponse(
        inference_service.infer_and_update_times_sse(xbkhId, request, user_id),
        media_type="text/event-stream"
    )


# ==================== 工价计算（基于已有工时） ====================
@router.post("/calculate-gongjia/{xbkhId}")
async def calculate_gongjia(
    xbkhId: int,
    mode: int = Query(..., description="工价模式: 0=区域工价, 1=公司工价"),
    request: Request = None,
    user_id: int = Query(..., description="用户ID")
):
    """根据已有工时和工价（区域或公司）计算每个工序的工价并更新"""
    user_id = validate_user_id(user_id)
    result = await quote_service.calculate_gongjia_by_mode(xbkhId, mode, request, user_id)
    return Success(data=result)


# ==================== SSE 报价实时监听 ====================
@router.get("/sse/quote/{xbkhId}")
async def sse_quote(xbkhId: int, request: Request, user_id: int = Query(...)):
    # 可选的 user_id 校验（16位正整数）
    # user_id = validate_user_id(user_id)

    async def event_generator():
        queue = await sse_manager.connect(xbkhId)
        try:
            # 推送初始报价数据
            init_data = await quote_service.get_current_quote(xbkhId, request, user_id)
            yield f"data: {json.dumps({'type': 'init', 'data': init_data}, ensure_ascii=False)}\n\n"
            # 持续监听新消息
            while True:
                message = await queue.get()
                yield message
        finally:
            # 无论何种退出方式（正常、异常、取消）都会清理
            await sse_manager.disconnect(xbkhId, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")