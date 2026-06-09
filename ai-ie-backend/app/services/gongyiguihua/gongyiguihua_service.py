# 工艺规划服务层
from typing import Any, Dict,Optional
import json
from fastapi import Request
from app.services.rag.dxf_tiqu import fetch_cai_pian_gong_yi_data
from app.utils.exceptions import ServiceCallException,  AppException
from app.routers.rag_router import chat_endpoint
from app.routers.rag_router import ChatRequest

class PriceService:

    # 根据款号ID获取工序信息并计算工价
    async def get_work_processing(self, khid: int, request: Request,userid:Optional[int] = None) -> Dict[str, Any]:

        db = request.state.db

        # 1.从数据库获取裁片、工艺数据
        result = fetch_cai_pian_gong_yi_data(request,khid)
        if not result:
            raise ValueError("未找到该款号的裁片信息")
        message_content = json.dumps(result,ensure_ascii=False)

        # 2.调用RAG服务拆解工序列表
        try:
            if userid is None:
                current_user=1329287864148999
            else:
                current_user=int(userid)
            chat_response_data = await chat_endpoint(current_user=current_user,request=request, message=message_content, session_id=None)

            # RAG 返回的是 sucess类型  复杂
            raw_content_dict = chat_response_data.__dict__.get('body')

            json_str = raw_content_dict.decode('utf-8')
            content_dict = json.loads(json_str)
            inner_data = content_dict.get('data')
            if inner_data is None:
                raise ValueError("RAG响应JSON中未找到data字段")

            # if isinstance(inner_data, dict):
            #     ai_response_text = inner_data.get('response', '')
            # elif hasattr(inner_data, 'response'):
            #     ai_response_text = inner_data.response
            # else:
            #     print(f"警告: 内部数据格式未知: {type(inner_data)}")
            #     ai_response_text = ''

            #print("---------- 获取到的工序表结果 (gongyiguihua_service) ----------")
            #print(ai_response_text)

            return inner_data

            # if isinstance(ai_response_text, str):
            #     try:
            #         return json.loads(ai_response_text)
            #     except json.JSONDecodeError:
            #         raise ValueError(f"AI大模型返回的结果不是有效的JSON格式: {ai_response_text}")
            # else:
            #     return ai_response_text


        except AppException as e:
            raise e
        except Exception as e:
            raise ServiceCallException(
                message=f"调用RAG服务失败: {str(e)}",
                details={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                }
            )

