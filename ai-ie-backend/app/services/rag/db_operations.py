import json
import re
from decimal import Decimal

from loguru import logger
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
from datetime import datetime
from fastapi import Request
from app.services.rag.public.process_production_steps import parse_process_json
from app.utils.snowflake_generator import snowflake
from app.utils.exceptions import AppException
from sqlalchemy import select, func, delete, update, case, text
from sqlalchemy.orm import Session

# 导入同步会话工厂
from app.utils.database import SessionLocal, get_db
from app.models.orm_models import AIliaotianjilu, AIXiangBaoGongXu, AIXiangBaoGongZhong,AIGongSiYongHu  # 导入预定义的ORM模型
from llama_index.core.base.llms.types import ChatMessage


@contextmanager
def get_db_session() -> Session:
    """同步数据库会话上下文管理器"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"数据库会话异常: {str(e)}")
        raise
    finally:
        session.close()


def gsId_db(request:Request,gsyhId: int) -> Optional[int]:
    """通过用户ID查询关联的公司ID（gsyhId = 公司用户ID字段）"""
    try:
            db=request.state.db
            # 核心修正：用用户ID匹配用户ID字段（gsyhId）
            query = db.query(AIGongSiYongHu).filter(
                AIGongSiYongHu.gsyhId == gsyhId  #
            ).first()
            gsyhid = query.gsId  # 直接取标量值

            if gsyhid is None:  #判断查询结果是否为None
                logger.warning(f"未找到用户关联的公司 | 用户ID={gsyhId}")
                return None

            logger.debug(f"用户ID={gsyhId} 关联公司ID={gsyhid}")
            return gsyhid

    except Exception as e:
        logger.error(f"查询公司ID失败 | 用户ID={gsyhId}: {str(e)}", exc_info=True)
        return None



def save_process_to_db(request:Request,json_text: str,xbkh: str,operator_id: Optional[int] = None) -> bool:
    """
    将解析的工序数据保存到数据库

    Args:
        json_text: JSON格式的工序数据字符串
        operator_id: 操作人员ID，用于记录创建人

    Returns:
        bool: 保存是否成功
    """
    db=request.state.db
    try:
        # 1.用户id转换为公司id
        gs_id=gsId_db(request,operator_id)
        # 2.解析JSON数据
        style_no_str, steps = parse_process_json(json_text,xbkh)
        # 3.将款号字符串转换为整数xbkhId
        try:
            xbkhId = int(style_no_str)
        except (ValueError, TypeError) as e:
            logger.error(f"款号转换失败 | 原始值={style_no_str}: {str(e)}")
            raise ValueError(f"无效的箱包款号: '{style_no_str}'，必须是整数")
        # 4.查询该款号下所有的旧工序
        old_processes = db.query(AIXiangBaoGongXu).filter(
            AIXiangBaoGongXu.xbkhId == xbkhId,
            AIXiangBaoGongXu.del_flag == False
        ).all()
        if old_processes:
            logger.info(f"检测到旧数据 | xbkhId={xbkhId} | 旧工序数量={len(old_processes)}，执行删除操作")
            for old_proc in old_processes:
                old_proc.del_flag = True
                old_proc.up_userid = operator_id
                old_proc.del_time = datetime.now()
        # 5.遍历工序列表，保存到数据库
        saved_count = 0
        for step in steps:
            try:
                #根据工种名称查找工种ID
                gongzhong_name = step["设备工具"]
                xbgzId = get_xbgz_id_by_name(db, gongzhong_name)

                #生成工序ID (雪花算法)
                xbgxId = snowflake.generate_id()
                time=datetime.now()
                #创建工序记录
                new_process = AIXiangBaoGongXu(
                    xbgxId=xbgxId,
                    xbkhId=xbkhId,  # 直接使用解析出的款号作为ID
                    del_flag=False,
                    gongXuMingCheng=step.get("工序名称", ""),
                    xbgzId=xbgzId,
                    in_userid=operator_id,
                    in_time=time,
                    up_userid=operator_id,
                    up_time=time,
                    gsId=gs_id,
                    status=0
                )

                #保存到数据库
                db.add(new_process)
                saved_count += 1

            except Exception as e:
                logger.error(f"保存单个工序失败 | 工序名称={step['工序名称']} | 错误={str(e)}")
                continue

        # 4. 提交事务
        db.commit()
        logger.info(f"工序数据保存成功 | xbkhId={xbkhId} | 总工序数={len(steps)} | 成功保存={saved_count}")
        return saved_count > 0

    except Exception as e:
        db.rollback()
        logger.exception(f"保存工序数据到数据库失败: {str(e)}")
        raise AppException(
            code=500,
            message="保存工序数据失败，请检查数据格式",
            details=f"保存工序数据到数据库失败: {str(e)}"
        )
    finally:
        db.close()


def get_xbgz_id_by_name(db: Session, gongzhong_name: str) -> Optional[int]:
    """
    根据工种名称查询工种ID
    """
    try:
        # 查询工种ID，只查找未删除的记录
        result = db.execute(
            select(AIXiangBaoGongZhong.xbgzId)
            .where(AIXiangBaoGongZhong.gongZhongMingCheng == gongzhong_name)
            .where(AIXiangBaoGongZhong.del_flag == False)
            .where()
        ).first()

        if result is None:
            return 1352208327770400
        return result[0]
    except Exception as e:
         raise AppException(
            code=500,
            message="数据库连接失败",
            details=f"数据库连接失败 | 工种名称={gongzhong_name}: {str(e)}"
        )


def extract_style_number(content: str) -> str | None:
    """
    仅从 JSON 数据中提取箱包款号
    目标格式：
    ```json
    [
      { "款号": "10086" },
      ...
    ]
    ```
    """
    if not content:
        return None

    try:
        # 1. 提取 JSON 代码块内容
        # 匹配 ```json 和 ``` 之间的内容，兼容前后的空白字符
        logger.info(content)
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        logger.info(json_match)
        json_str = ""
        if json_match:
            json_str = json_match.group(1)
            logger.info(json_str)
        else:
            # 如果没有 markdown 标记，尝试直接查找第一个 [ 和最后一个 ]
            start = content.find('[')
            end = content.rfind(']')
            if start != -1 and end != -1:
                json_str = content[start:end + 1]
            else:
                logger.warning("未在内容中找到 JSON 数组标记")
                return None

        # 2. 解析 JSON
        data_list = json.loads(json_str)

        # 3. 校验数据结构
        if not isinstance(data_list, list) or len(data_list) == 0:
            return None

        # 4. 获取第一个元素（通常是款号对象）
        first_item = data_list[0]

        if isinstance(first_item, dict):
            # 尝试获取常见的款号键名
            style_no = first_item.get("款号")
            if style_no:
                return str(style_no)
        return None

    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败: {str(e)}")
        return None
    except Exception as e:
        logger.exception(f"提取款号时发生未知错误: {str(e)}")
        return None


def get_existing_style_number(request: Request, session_id: str) -> str | None:
    """获取同一会话中已有的箱包款号"""
    try:
        db = request.state.db
        # 查询表
        existing_xbkh_id = db.query(AIliaotianjilu.xbkh_id).filter(
            AIliaotianjilu.sessionId == session_id,
            AIliaotianjilu.xbkh_id.isnot(None),
            AIliaotianjilu.xbkh_id != '',
            AIliaotianjilu.xbkh_id != '自由聊天',
            AIliaotianjilu.del_flag == False
        ).order_by(AIliaotianjilu.create_at.desc()).limit(1).scalar()

        if existing_xbkh_id:
            logger.debug(f"找到会话中已有款号 | session_id={session_id} | xbkh_id={existing_xbkh_id}")
            return existing_xbkh_id
        else:
            logger.debug(f"会话中没有找到有效款号 | session_id={session_id}")
            return None
    except Exception as e:
        raise AppException(
            code=500,
            message="请检查数据库连接",
            details=f"查询会话款号时出错 | session_id={session_id}: {str(e)}"
        )


def save_message(request: Request, session_id: str, role: str, content: str,
                 session_title: Optional[str] = None, gs_id: Optional[int] = None, xbkh: Optional[str] = None) -> bool:
    """保存消息到数据库"""
    try:
        allowed_roles = ['user', 'assistant']
        if role not in allowed_roles:
            logger.warning(f"不支持的角色类型 '{role}'，已转换为 'assistant' | session_id={session_id}")
            role = 'assistant'

        safe_content = content[:4000] if len(content) > 4000 else content

        # 提取标题
        title = (session_title.strip()[:255] if session_title and session_title.strip() else
                safe_content[:255] if safe_content.strip() else "未命名")

        # 提取款号逻辑
        # xbkh_id = extract_style_number(safe_content)
        xbkh_id = xbkh
        if xbkh_id is None:
            xbkh_id = get_existing_style_number(request, session_id)
        if xbkh_id is None:
            xbkh_id = "自由聊天"
            logger.debug(f"未找到款号信息，使用默认值 | session_id={session_id}")

        # 设置 zh_id
        zh_id_value = str(gs_id) if gs_id is not None else "0"
        if gs_id is None:
            logger.warning(f"保存消息未提供公司ID，使用默认值'0' | session_id={session_id}")

        db = request.state.db
        record_id = snowflake.generate_id()
        new_message = AIliaotianjilu(
            ltjlId=record_id,
            sessionId=session_id,
            message_role=role,
            message_content=safe_content,
            xbkh_id=xbkh_id,
            create_at=datetime.now(),
            del_flag=False,
            title=title,
            zh_id=zh_id_value
        )
        db.add(new_message)
        db.commit()
        logger.success(f"消息保存成功 | session_id={session_id} | record_id={record_id}")
        return True
    except Exception as e:
        logger.exception(f"数据库保存失败 | session_id={session_id}: {str(e)}")
        return False


def load_session_history(request: Request, session_id: str, current_gs_id: Optional[int] = None) -> List[ChatMessage]:
    """从数据库加载会话历史消息"""
    messages = []
    try:
        db = request.state.db
        # 查询表
        conversations = db.query(AIliaotianjilu).filter(
            AIliaotianjilu.sessionId == session_id,
            AIliaotianjilu.del_flag == False,
            AIliaotianjilu.message_role.in_(['user', 'assistant']),
            AIliaotianjilu.zh_id == str(current_gs_id)
        ).order_by(AIliaotianjilu.create_at.asc()).all()

        role_map = {'user': 'user', 'assistant': 'assistant'}
        for conv in conversations:
            mapped_role = role_map.get(conv.message_role, 'user')
            messages.append(
                ChatMessage(
                    role=mapped_role,
                    content=conv.message_content,
                    additional_kwargs={"timestamp": conv.create_at}
                )
            )

        logger.info(f"会话历史加载成功 | session_id={session_id} | message_count={len(messages)}")
        return messages
    except Exception as e:
        raise AppException(
            code=500,
            message="会话历史加载失败,请检查数据库",
            details=f"会话历史加载失败 | session_id={session_id}: {str(e)}"
        )


def check_session_exists(request: Request, session_id: str, current_gs_id: Optional[int] = None) -> bool:
    """检查会话是否存在于数据库中"""
    try:
        db = request.state.db
        # 查询表
        count = db.query(func.count(AIliaotianjilu.ltjlId)).filter(
            AIliaotianjilu.sessionId == session_id,
            AIliaotianjilu.del_flag == False,
            AIliaotianjilu.zh_id == str(current_gs_id)
        ).scalar() or 0
        exists = count > 0
        logger.debug(f"会话存在性检查 | session_id={session_id} | exists={exists} | message_count={count}")
        return exists
    except Exception as e:
        raise AppException(
            code=500,
            message="会话存在性检查异常",
            details=f"会话存在性检查异常 | session_id={session_id}: {str(e)}"
        )


def get_session_metadata(request: Request, session_id: str, current_gs_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """获取会话元数据（第一条消息和创建时间）"""
    try:
        db = request.state.db
        # 查询表
        row = db.query(
            AIliaotianjilu.create_at,
            AIliaotianjilu.message_content,
            AIliaotianjilu.title
        ).filter(
            AIliaotianjilu.sessionId == session_id,
            AIliaotianjilu.del_flag == False,
            AIliaotianjilu.zh_id == str(current_gs_id)
        ).order_by(AIliaotianjilu.create_at.asc()).first()

        if row:
            return {
                "created_at": row.create_at.timestamp(),
                "first_message": row.message_content,
                "title": row.title,
            }
        logger.warning(f"会话元数据不存在 | session_id={session_id}")
        return None
    except Exception as e:
        raise AppException(
            code=500,
            message="获取会话元数据失败,请检查数据库",
            details=f"获取会话元数据失败 | session_id={session_id}: {str(e)}"
        )


def get_recent_sessions(request: Request, xbkh_id:str,limit: int = 50, current_gs_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """获取最近的会话摘要（用于会话列表）"""
    sessions = []
    try:
        db = request.state.db
        # 查询表
        results = db.query(
            AIliaotianjilu.sessionId.label('session_id'),
            func.min(AIliaotianjilu.create_at).label('created_at'),
            func.max(AIliaotianjilu.create_at).label('last_active'),
            func.count().label('message_count'),
            func.max(AIliaotianjilu.title).label('title'),
            func.max(
                case(
                    (AIliaotianjilu.message_role == 'user', AIliaotianjilu.message_content),
                    else_=None
                )
            ).label('first_user_message')
        ).filter(
            AIliaotianjilu.message_role.in_(['user', 'assistant']),
            AIliaotianjilu.del_flag == False,
            AIliaotianjilu.zh_id == str(current_gs_id),
            AIliaotianjilu.xbkh_id == xbkh_id
        ).group_by(AIliaotianjilu.sessionId).order_by(
            func.max(AIliaotianjilu.create_at).desc()
        ).limit(limit).all()

        for row in results:
            sessions.append({
                "session_id": row.session_id,
                "title": row.title,
                "created_at": row.created_at.timestamp(),
                "last_active": row.last_active.timestamp(),
                "message_count": row.message_count
            })

        logger.info(f"最近会话获取成功 | requested_limit={limit} | actual_count={len(sessions)}")
        return sessions
    except Exception as e:
        raise AppException(
            code=500,
            message="获取会话失败，请检查数据库",
            details=f"获取最近会话失败: {str(e)}"
        )


def delete_session(request: Request, session_id: str, current_gs_id: Optional[int] = None) -> bool:
    """软删除指定会话（标记为已删除并记录删除时间）"""
    try:
        db = request.state.db
        # 检查存在性
        exist_count = db.query(func.count(AIliaotianjilu.ltjlId)).filter(
            AIliaotianjilu.sessionId == session_id,
            AIliaotianjilu.del_flag == False
        ).scalar() or 0

        if exist_count == 0:
            logger.warning(f"会话不存在或已删除 | session_id={session_id}")
            return False

        # 使用 update 语句
        from sqlalchemy import update
        current_time = datetime.now()
        stmt = update(AIliaotianjilu).where(
            AIliaotianjilu.sessionId == session_id,
            AIliaotianjilu.del_flag == False,
            AIliaotianjilu.zh_id == str(current_gs_id)
        ).values(
            del_flag=True,
            del_time=current_time
        )
        result = db.execute(stmt)
        deleted_count = result.rowcount

        logger.success(
            f"会话软删除成功 | session_id={session_id} | "
            f"deleted_messages={deleted_count} | "
            f"delete_time={current_time}"
        )
        return deleted_count > 0
    except Exception as e:
        raise AppException(
            code=500,
            message="会话软删除失败,请检查数据库",
            details=f"会话软删除失败 | session_id={session_id}: {str(e)}"
        )


def update_session_title(request: Request, session_id: str, new_title: str) -> bool:
    """修改指定会话下所有未删除消息的标题"""
    try:
        safe_title = (new_title.strip() or "未命名")[:255]
        db = request.state.db
        from sqlalchemy import update
        stmt = update(AIliaotianjilu).where(
            AIliaotianjilu.sessionId == session_id,
            AIliaotianjilu.del_flag == False
        ).values(title=safe_title)
        result = db.execute(stmt)
        return result.rowcount > 0
    except Exception as e:
        logger.exception(f"更新会话标题失败 | session_id={session_id}: {str(e)}")
        raise AppException(
            code=500,
            message="更新会话标题失败,请检查数据库连接",
            details=f"更新会话标题失败 | session_id={session_id}: {str(e)}"
        )

# def restore_session(session_id: str) -> bool:
#     """恢复已软删除的会话（可选功能）"""
#     try:
#         with get_db_session() as session:
#             # 恢复：更新del_flag和del_time
#             update_stmt = (
#                 update(AIliaotianjilu)
#                 .where(
#                     AIliaotianjilu.sessionId == session_id,
#                     AIliaotianjilu.del_flag == True  # 只更新已删除的记录
#                 )
#                 .values(
#                     del_flag=False,
#                     del_time=None
#                 )
#             )
#
#             result = session.execute(update_stmt)
#             restored_count = result.rowcount
#
#             if restored_count > 0:
#                 logger.success(
#                     f"会话恢复成功 | session_id={session_id} | "
#                     f"restored_messages={restored_count}"
#                 )
#             else:
#                 logger.warning(f"没有可恢复的会话记录 | session_id={session_id}")
#
#             return restored_count > 0
#     except Exception as e:
#         logger.exception(f"会话恢复失败 | session_id={session_id}: {str(e)}")
#         return False