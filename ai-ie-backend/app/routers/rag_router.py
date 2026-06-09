# app/routers/rag_routes.py
import io
import json
import re
from typing import Optional, Annotated
from fastapi.responses import Response
import pypandoc
from fastapi import APIRouter, HTTPException, status, Request, Depends, Path, Body
import time
from loguru import logger
import asyncio  # 新增导入
from urllib.parse import quote


from fastapi.responses import StreamingResponse
from app.services.gongyiguihua.price_service import price_calculatio, is_valid_process_format, ai_response_price
from app.utils.exceptions import AppException, NotFoundException
from app.services.rag.public.process_production_steps import parse_process_json,generate_excel
# 导入全局状态和依赖
from app.services.rag.RAG import global_state,chat_manager
from app.services.rag.db_operations import (
    save_message,
    delete_session,
    get_recent_sessions, check_session_exists, load_session_history, save_process_to_db, extract_style_number,
    update_session_title, gsId_db
)
from app.services.rag.bm25index.bm25_index import build_index
from app.utils.response import Success
from app.services.rag.dxf_tiqu import fetch_cai_pian_gong_yi_data
from app.schemas.rag.api_schemas import ChatRequest,  SessionListResponse, TitleUpdateRequest, \
    ExcelRequest, ChatHistoryResponse, ChatMessageResponse

from app.services.dxf.dxf_crud import query_aiXiangBaoKuanHao_by_xbkhId


# 创建路由
router = APIRouter(prefix="/ai", tags=["ai聊天会话"])

@router.get("/sqlserve/{xbkh_id}",summary="根据箱包款式ID获取裁片名称和对应工艺描述")
async def get_cai_pian_gong_yi(
        request: Request,
        xbkh_id: int = Path(..., description="箱包款式ID，必须是正整数", ge=1),

):
    """
    根据箱包款式ID获取裁片名称和对应工艺描述

    参数:
        xbkh_id (int): 箱包款式ID，必须是正整数
        db (Session): 数据库会话，由依赖注入提供

    返回:
        list: 格式为 [
            {"款号": "xxx"},
            {"裁片名称": "裁片1", "部位工艺": ["工艺1", "工艺2", ...]},
            {"裁片名称": "裁片2", "部位工艺": ["工艺3", ...]},
            ...
        ]
    """
    try:
        # 调用业务逻辑方法获取数据
        result = fetch_cai_pian_gong_yi_data(request, xbkh_id)
        vales = str(result)+",任务：请根据上述描述，严格依据箱包工艺规则库，生成标准的六大流程工序表"
        # logger.info(f"成功获取 {len(result) - 1} 个裁片的工艺信息 | xbkh_id={xbkh_id}")
        return Success(
            data=vales,
            msg=f"返回裁片{xbkh_id}信息成功,获取{len(result) - 1} 个裁片的工艺信息"
        )

    except Exception as e:
        # logger.exception(f"获取裁片工艺信息失败 | xbkh_id={xbkh_id}: {str(e)}")
        print(f"处理请求时出错: {e}")
        raise AppException(
            code=500,
            message=f"服务器内部错误: {str(e)}",
            details={"获取裁片工艺信息失败"}
        )


# @router.post("/api/save-process", summary="保存工序数据到数据库")
# async def save_process_endpoint( text: str ,
#     operator_id: int):
#     """保存工序数据到数据库的API端点"""
#     try:
#
#         if not text.strip():
#             raise AppException(details="工序内容不能为空",message="工序内容不能为空",code=500)
#
#         # 保存到数据库
#         success = save_process_to_db(text, operator_id)
#
#         if success:
#             return {"success": True, "message": "工序数据保存成功"}
#         else:
#             raise HTTPException(status_code=400, detail="未保存任何有效工序")
#
#     except ValueError as ve:
#         raise AppException(status_code=400, details=f"数据验证失败: {str(ve)}",message="数据验证失败",code=500)
#     except Exception as e:
#         raise AppException(status_code=500, details="服务器内部错误",message=f"保存工序数据失败: {str(e)}",code=500)

@router.post("/api/create/{folder_name}/{collection_name}")
def api_build_index(folder_name: Annotated[str, Path(description="数据本地地址")],
    collection_name: Annotated[str, Path(description="Qdrant 集合名称 (例如: llama2_paper)")]):
    """
    根据路径中的文件夹名构建索引
    调用方式: POST /build_index/data
    """
    try:
        # 直接调用核心函数
        doc_count = build_index(folder_name,collection_name)
        return {
            "msg": "索引构建成功",
            "folder": folder_name,
            "collection": collection_name
        }

    except Exception as e:
        # 捕获错误并返回 500
        raise AppException(
            code=500,
            message=f"生成集合失败",
            details=f"生成集合失败: {str(e)}"
        )

@router.post("/api/generate-excel",summary='生成Excel文件')
async def generate_excel_endpoint( request: Request,text: str ,
    person_name: str , current_user: int,xbkh_id: str):
    """生成Excel文件的API端点 - 专门处理表单数据格式"""
    # data=await request.json()
    # json_text = data.get("text","")
    # person_name = data.get("person_name","")
    # if not json_text.strip():
    #     # logger.warning("生成Excel请求: 空内容")
    #     raise AppException(details="生成Excel请求: 空内容",message="请输入工序内容",code=500)

    try:

        style_no,steps = parse_process_json(text,xbkh_id)
        # 保存工序到数据库中
        success = save_process_to_db(request,text, xbkh_id,current_user)

        if not steps:
            # logger.warning(f"生成Excel失败: 未找到有效工序 | content_preview={text[:50]}...")
            raise AppException(details=f"生成Excel失败: 未找到有效工序 | content_preview={text[:50]}...",message="未找到有效工序，请检查格式",code=500)

        success = save_process_to_db(request,text, xbkh_id,current_user)

        excel_data = generate_excel(style_no, steps, person_name)
        # 清理文件名，移除非法字符
        safe_style_no = re.sub(r'[\\/*?:"<>|]', '', style_no)
        filename = f"箱包工序表_{safe_style_no}.xlsx"
        encoded_filename = quote(filename.encode('utf-8'))

        headers = {
            'Content-Disposition': (
            f"attachment; filename*=UTF-8''{encoded_filename}; "  # RFC 5987 标准
            f'filename="{encoded_filename}"'  # 兼容旧浏览器
            ),
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }

        return StreamingResponse(
            io.BytesIO(excel_data),
            headers=headers,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        # raise HTTPException(status_code=500, detail=f"生成Excel失败: {str(e)}")
        raise AppException(
            code=500,
            message=f"请确认输入的格式",
            details=f"生成Excel失败: {str(e)}"
        )
@router.post("/chat/new")
async def create_new_session(
    current_user: int,
    request: Request,
):
    """
    创建一个新会话，标题自动生成为"新对话"
    """
    current_gs_id = gsId_db(request, current_user)

    session = chat_manager.get_or_create_session(
        request,
        session_id=None,        # 强制创建全新会话
        current_gs_id=current_gs_id
    )

    return {
        "session_id": session["session_id"],
        "title": session["title"],         # 即 "新对话"
        "created_at": session["created_at"]
    }
@router.post("/chat")
async def chat_endpoint(
        current_user: int,
        request: Request,
        message: str,
        session_id: Optional[str] = None,
        xbkh_id: Optional[str] = None
):
    """
    处理聊天请求
    """

    # 1. 前置校验
    if not global_state.vector_index:
        raise AppException(
            status_code=503,
            message="服务未初始化",
            details="知识库未初始化，请稍后再试",
            code=500
        )

    current_gs_id = gsId_db(request, current_user)

    #  2. 会话管理
    session = chat_manager.get_or_create_session(request, session_id, current_user)
    session_id = session["session_id"]

    if session["query_engine"] is None:
        chat_manager.initialize_query_engine(session_id)

    session["last_active"] = time.time()

    # 3. 保存用户消息
    try:
        await asyncio.to_thread(
            save_message,
            request,
            session_id,
            "user",
            message,
            session_title=session["title"],
            gs_id=current_gs_id,
            xbkh=xbkh_id
        )
    except Exception as e:
        pass

    #定义“异步生成器”函数
    async def event_generator():

        #  初始化流式响应对象
        streaming_response = await asyncio.to_thread(
            session["query_engine"].stream_chat,
            message
        )
        # 将 AI 生成的 Token 逐个发送给前端
        try:
            # streaming_response.response_gen 是一个生成器
            for token in streaming_response.response_gen:
                # 使用 Server-Sent Events (SSE) 格式
                # 前端通过 data 字段接收
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            # 发送结束信号
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

            # 4. 保存 AI 最终完整回答
            final_response_text = str(streaming_response)  # 获取完整文本
            logger.info(final_response_text)#打印文本用于测试
            try:
                await asyncio.to_thread(
                    save_message,
                    request,
                    session_id,
                    "assistant",
                    final_response_text,
                    session_title=session["title"],
                    gs_id=current_gs_id,
                    xbkh=xbkh_id
                )
            except Exception as save_err:
                # 记录日志，但不影响前端显示
                print(f"保存消息失败: {save_err}")

        except Exception as e:
            # 如果出错，发送错误信息并结束
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")



@router.get("/sessions", response_model=SessionListResponse,summary='获取用户的列表')
async def get_sessions(request: Request,current_user: int,xbkh_id: str):
    """获取用户的所有会话列表"""
    try:
        # 使用线程执行同步数据库操作
        user_sessions = await asyncio.to_thread(get_recent_sessions, request,xbkh_id,limit=50,current_gs_id=gsId_db(request,current_user))
        data_response=SessionListResponse(sessions=user_sessions)
        return Success(
            data=data_response,
            msg="成功获取用户列表"
        )
    except Exception as e:
        # logger.exception(f"获取会话列表失败: {str(e)}")
        raise AppException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details="获取会话列表失败",
            message="请检查代码",
            code=500
        )


@router.get(
    "/chat-history/{session_id}",
    response_model=ChatHistoryResponse,
    summary="获取会话聊天记录",
    description="根据会话ID获取完整的聊天历史记录，包括用户和AI的对话内容"
)
async def get_chat_history(request:Request,session_id: str,current_user: int):
    """
    获取指定会话的聊天历史记录

    - session_id: 会话的唯一标识符
    - 返回包含会话ID、消息列表和总消息数的结构化数据
    """
    try:
        current_gs_id = gsId_db(request,current_user)
        # 检查会话是否存在
        if not check_session_exists(request,session_id,current_gs_id):
            raise HTTPException(
                status_code=404,
                detail=f"会话ID {session_id} 不存在或已被删除"
            )

        # 加载会话历史
        chat_messages = load_session_history(request,session_id,current_gs_id)

        # 转换消息格式
        formatted_messages = [
            ChatMessageResponse(
                role=msg.role,
                content=msg.content
            )
            for msg in chat_messages
        ]

        data_response= ChatHistoryResponse(
            session_id=session_id,
            messages=formatted_messages,
            total_count=len(formatted_messages)
        )
        return Success(
            data=data_response,
            msg="返回信息成功"
        )

    except Exception as e:
        raise AppException(
            status_code=500,
            message="获取聊天记录失败",
            details=f"获取聊天历史时出错: {str(e)}",
            code=500
        )

@router.put("/sessions/{session_id}",summary='删除指定会话')
async def delete_session_endpoint(request:Request,session_id: str,current_user: int):
    """删除指定会话"""
    try:
        current_gs_id = gsId_db(request,current_user)
        # 1. 逻辑删除 - 使用线程执行同步操作
        success = await asyncio.to_thread(delete_session, request,session_id,current_gs_id)
        if not success:
            # logger.error(f"从数据库删除会话失败 | session_id={session_id}")
            raise AppException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                details=f"删除会话失败 | session_id={session_id}",
                message="删除会话失败",
                code=403
            )

        # 2. 从内存中清除
        if session_id in chat_manager.sessions:
            del chat_manager.sessions[session_id]
        if session_id in chat_manager.session_metadata:
            del chat_manager.session_metadata[session_id]
        if session_id in chat_manager.global_chat_store.store:
            del chat_manager.global_chat_store.store[session_id]

        return Success(
            data=True,
            msg="会话删除成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise AppException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=f"删除会话时出错 | session_id={session_id}: {str(e)}",
            message=f"删除会话失败: {str(e)}",
            code=404
        )


@router.post("/sessions/{session_id}/title",summary='更新会话标题')
async def update_title(request:Request,session_id: str, title_request: TitleUpdateRequest):
    """更新会话标题"""
    # 直接调用核心函数（无额外逻辑）
    if update_session_title(request,session_id, title_request.new_title):
        return {
            "success": True,
            "message": "标题更新成功",
            "session_id": session_id
        }

    # 无有效记录可更新（会话不存在/所有消息已删除）
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="会话不存在或无可更新的消息"
    )