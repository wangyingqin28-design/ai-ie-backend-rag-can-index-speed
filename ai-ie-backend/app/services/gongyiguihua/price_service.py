# app/services/gongyiguihua/price/cost_calculation_handler.py
import re
from typing import Any, Dict
import json
from fastapi import Request

from app.services.dxf.dxf_crud import query_aiXiangBaoKuanHao_by_xbkhId
from app.services.gongyiguihua.price.data_preprocessor import process_rag_response
from app.services.gongyiguihua.price.calculate_cost import calculate_labor_cost
from app.services.rag.db_operations import  extract_style_number
from app.utils.exceptions import (
    NotFoundException,
    LaborCostCalculationException,
    AppException,
    RagResponsePreprocessingException,
    DataUpdateFailedException,
)
from app.utils.response import Success


async def price_calculatio(ai_response_text: str, xbkh_id: int, request: Request, retrieved_session_id: str = "") -> Dict[str, Any]:
    """
    执行工价计算的完整流程：预处理 RAG 响应 -> 计算工价 -> 保存结果。
    Args:
        ai_response_text (str): 来自 RAG 服务的原始响应文本。
        xbkh_id (int): 款号 ID。
        request (Request): FastAPI 请求对象。
        retrieved_session_id (str): 用于保存结果的会话 ID。
    Returns:
        Dict[str, Any]: 计算得出的工价信息。
    """
    # 3. 预处理 RAG 响应数据
    try:
        preprocessed_operations_json = process_rag_response(ai_response_text)

        if not preprocessed_operations_json:
            raise NotFoundException(
                message="预处理RAG响应数据返回的列表为空",
                details={
                    "RAG响应返回内容：": ai_response_text,
                }
            )
    except AppException:
        raise
    except Exception as e:
        raise RagResponsePreprocessingException(
            message=f"预处理 RAG 响应数据时发生未知错误: {str(e)}",
            details={
                "raw_error": str(e),
                "error_type": type(e).__name__,
                "RAG响应返回内容": ai_response_text,
            },
        )

    # 4. 计算工价
    try:
        labor_cost = calculate_labor_cost(preprocessed_operations_json, xbkh_id, request)
    except AppException:
        raise
    except Exception as e:
        raise LaborCostCalculationException(
            message=f"计算工价时发生未知错误: {str(e)}",
            details={
                "raw_error": str(e),
                "error_type": type(e).__name__,
                "打工价输入内容：": preprocessed_operations_json,
            },
        )

    # 5. 将计算结果保存到数据库
    try:
        if retrieved_session_id:
            labor_cost_json = json.dumps(labor_cost, ensure_ascii=False)
            #save_message(session_id=retrieved_session_id, role='assistant', content=labor_cost_json)

    except Exception as e:
        # 确保在异常发生时，labor_cost_json 是可用的，即使它可能未定义
        labor_cost_json_to_log = json.dumps(labor_cost, ensure_ascii=False) if 'labor_cost' in locals() else "N/A"
        raise DataUpdateFailedException(
            message="工价计算结果保存到数据库失败",
            details={"error": str(e), "retrieved_session_id": retrieved_session_id, "工价计算结果": labor_cost_json_to_log}
        )


    return labor_cost




def is_valid_process_format(response_text: str) -> bool:
    """
    判断response_text是否符合预期的工序列表格式
    Args:
        response_text: AI返回的文本
    """
    # 检查是否包含"款号"字样
    if not re.search(r'款号[：:]?\s*\d+', response_text):
        return False

    # 检查是否包含"工序"相关的关键词
    if not re.search(r'(组装工序列表|工序列表|工序详情|制作工序)', response_text):
        return False

    # 检查是否包含编号的工序项目（如"1. 工序名称-工种"格式）
    process_pattern = r'\d+\.\s*[^\n-]+[-–—]\s*(台面|平车|高车|套结车|锁边车|车缝|手工|烫金|印花|绣花|拉链)'
    if not re.findall(process_pattern, response_text):
        return False

    # 额外检查是否有至少3个以上编号的工序（确保不是偶然匹配）
    numbered_processes = re.findall(r'\d+\.', response_text)
    if len(numbered_processes) < 3:
        return False

    return True




# ========== 对ai的响应进行工价计算  rag_router.py ==========
async def ai_response_price(
    response_text: str,
    session_id: str,
    request: Request
) -> Success:

    # 1. 检查response_text是否符合预期的工序格式
    if is_valid_process_format(response_text):
        # 2. 提取款号
        try:
            xbkh_id = extract_style_number(response_text)
            if not xbkh_id :
                raise NotFoundException(
                    message=f"提取的款号为空",
                    details={"xbkhId": xbkh_id, }
                )
        except Exception as e:
            #logger.warning(f"会话{session_id}：提取款号失败 - {str(e)}")
            raise NotFoundException(
                message=f"款号提取失败：{str(e)}",
                details={"xbkhId": xbkh_id, "response_text": response_text}
            )

        retrieved_session_id = session_id

        # 3. 检查款号是否存在于数据库中
        try:
            db = request.state.db
            # 调用方法检查款号是否存在
            query_aiXiangBaoKuanHao_by_xbkhId(db, xbkh_id)

            # 4. 调用工价计算核心逻辑
            labor_cost_result = await price_calculatio(
                ai_response_text=response_text,
                xbkh_id=xbkh_id,
                request=request,
                retrieved_session_id=retrieved_session_id
            )

            # 5. 将字典转换为 JSON 字符串
            labor_cost_json = json.dumps(labor_cost_result, ensure_ascii=False)

            # 6. 返回工价计算结果
            return Success(
                data={
                    "response": labor_cost_json,
                    "session_id": session_id,
                },
                msg="AI响应成功"
            )
        except NotFoundException:
            # 款号不存在，跳过工价计算，直接返回原始AI响应
            return Success(
                data={
                    "response": response_text,
                    "session_id": session_id,
                },
                msg="自由聊天（无打工价）响应成功"
            )
    else:
        # 格式不符合，直接返回原始AI响应
        return Success(
            data={
                "response": response_text,
                "session_id": session_id,
            },
            msg="自由聊天（无打工价）响应成功"
        )