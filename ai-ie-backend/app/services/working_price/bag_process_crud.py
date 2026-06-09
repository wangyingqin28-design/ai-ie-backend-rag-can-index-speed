# crud.py
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import os
from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import and_, desc, update
from sqlalchemy.orm import Session, aliased

from app.models import orm_models
from app.models.orm_models import AIXiangBaoGongXu
from app.utils.exceptions import (
    NotFoundException, ValidationException, AppException, DataUpdateFailedException
)
from app.utils.snowflake_generator import SnowFlake

load_dotenv()
GETSOFT_ID_STR = os.getenv("GETSOFT_ID")
GETSOFT_ID = int(GETSOFT_ID_STR)


class XiangBaoGongXuCRUD:
    """箱包工序数据库操作类"""

    def search(self, db: Session, gsId: int, xbkhId: int) -> List[Dict[str, Any]]:
        """
        查询指定款号下的所有工序（仅返回用于 AI 推断的必要字段，不返回工时）
        """
        try:
            insert_user = aliased(orm_models.AIGongSiYongHu, name="insert_user")
            update_user = aliased(orm_models.AIGongSiYongHu, name="update_user")
            gongSi = aliased(orm_models.AIGongSi, name="gongSi")

            query = db.query(
                orm_models.AIXiangBaoGongXu,
                orm_models.AIXiangBaoGongZhong.gongZhongMingCheng.label('gongzhong_name'),
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name'),
                gongSi.gongSiQuanCheng.label('gongsi_name')
            ).filter(orm_models.AIXiangBaoGongXu.del_flag == False)

            query = query.outerjoin(
                orm_models.AIXiangBaoGongZhong,
                orm_models.AIXiangBaoGongXu.xbgzId == orm_models.AIXiangBaoGongZhong.xbgzId
            ).outerjoin(
                insert_user,
                orm_models.AIXiangBaoGongXu.in_userid == insert_user.gsyhId
            ).outerjoin(
                update_user,
                orm_models.AIXiangBaoGongXu.up_userid == update_user.gsyhId
            ).outerjoin(
                gongSi,
                orm_models.AIXiangBaoGongXu.gsId == gongSi.gsId
            ).filter(orm_models.AIXiangBaoGongXu.xbkhId == xbkhId)

            # 添加公司权限过滤
            if gsId != GETSOFT_ID:
                query = query.filter(orm_models.AIXiangBaoGongXu.gsId == gsId)

            results = query.all()

            result_list = []
            for record, gongzhong_name, insert_user_name, update_user_name, gongsi_name in results:
                item = {
                    "xbgxId": record.xbgxId,
                    "gongXuMingCheng": record.gongXuMingCheng,
                    "GongZhong": gongzhong_name or "无工种",
                    # 不返回 time，因为当前一定为空
                }
                result_list.append(item)
            return result_list
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="查询工序失败,XiangbaoGongXu_crud.search",
                details={"error": str(e)}
            )

    def update_single_time(self, db: Session, gsId: int, xbgxId: int, time: float, up_userid: int) -> AIXiangBaoGongXu:
        """
        更新单个工序的工时（秒）- 保留单个更新，但批量更新将使用更高效的方法
        """
        try:
            # 构造查询条件：主键 + 公司权限
            if gsId == GETSOFT_ID:
                query_filter = and_(
                    AIXiangBaoGongXu.xbgxId == xbgxId,
                    AIXiangBaoGongXu.del_flag == False
                )
            else:
                query_filter = and_(
                    AIXiangBaoGongXu.xbgxId == xbgxId,
                    AIXiangBaoGongXu.del_flag == False,
                    AIXiangBaoGongXu.gsId == gsId
                )

            xiangBaoGongXu = db.query(AIXiangBaoGongXu).filter(query_filter).first()
            if not xiangBaoGongXu:
                raise NotFoundException(
                    message="工序不存在或已被删除",
                    details={"xbgxId": xbgxId}
                )

            # 更新工时
            xiangBaoGongXu.time = time
            xiangBaoGongXu.up_userid = up_userid
            xiangBaoGongXu.up_time = datetime.now()

            db.flush()
            return xiangBaoGongXu
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="更新工序工时失败",
                details={"error": str(e), "xbgxId": xbgxId}
            )

    def batch_update_times(self, db: Session, gsId: int, updates: List[Dict[str, Any]], up_userid: int):
        """
        批量更新多个工序的工时（高效方式）
        updates: [{"xbgxId": 1, "time": 120}, ...]
        """
        if not updates:
            return

        try:
            # 获取所有需要更新的 xbgxId 列表
            xbgx_ids = [upd["xbgxId"] for upd in updates]

            # 构造公司权限过滤条件
            if gsId == GETSOFT_ID:
                filter_condition = and_(
                    AIXiangBaoGongXu.xbgxId.in_(xbgx_ids),
                    AIXiangBaoGongXu.del_flag == False
                )
            else:
                filter_condition = and_(
                    AIXiangBaoGongXu.xbgxId.in_(xbgx_ids),
                    AIXiangBaoGongXu.del_flag == False,
                    AIXiangBaoGongXu.gsId == gsId
                )

            # 先查出所有需要更新的对象，确保存在且权限正确（可选，也可以直接 update）
            # 但为了安全，先查询验证权限，再批量更新
            existing = db.query(AIXiangBaoGongXu).filter(filter_condition).all()
            existing_ids = {e.xbgxId for e in existing}

            # 检查是否有不存在的或权限不足的
            missing = [upd["xbgxId"] for upd in updates if upd["xbgxId"] not in existing_ids]
            if missing:
                raise NotFoundException(
                    message="部分工序不存在或权限不足",
                    details={"missing_xbgxIds": missing}
                )

            # 构建批量更新数据（字典列表，包含主键和要更新的字段）
            bulk_update_data = []
            now = datetime.now()
            for upd in updates:
                # 如果时间不为空，且为正数
                if "time" in upd and upd["time"] is not None:
                    time_val = float(upd["time"])
                    if time_val >= 0:
                        bulk_update_data.append({
                            "xbgxId": upd["xbgxId"],
                            "time": time_val,
                            "up_userid": up_userid,
                            "up_time": now
                        })

            if not bulk_update_data:
                return

            # 使用 SQLAlchemy 的 bulk_update_mappings 进行高效更新
            # 注意：bulk_update_mappings 不会自动更新 `up_time` 和 `up_userid`，所以我们需要在映射中包含这些字段
            db.bulk_update_mappings(AIXiangBaoGongXu, bulk_update_data)
            db.flush()
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="批量更新工序工时失败",
                details={"error": str(e)}
            )

    def get_processes_with_time(self, db: Session, gsId: int, xbkhId: int) -> List[Dict[str, Any]]:
        """查询指定款号下的工序，返回包含 xbgxId, xbgzId, time 的列表"""
        try:
            query = db.query(AIXiangBaoGongXu).with_entities(
                AIXiangBaoGongXu.xbgxId,
                AIXiangBaoGongXu.xbgzId,
                AIXiangBaoGongXu.time
            ).filter(
                AIXiangBaoGongXu.del_flag == False,
                AIXiangBaoGongXu.xbkhId == xbkhId
            )
            if gsId != GETSOFT_ID:
                query = query.filter(AIXiangBaoGongXu.gsId == gsId)
            results = query.all()
            # 每个结果是 Row 对象，可以按属性访问
            return [
                {
                    "xbgxId": r.xbgxId,
                    "xbgzId": r.xbgzId,
                    "time": float(r.time) if r.time is not None else None
                }
                for r in results
            ]
        except Exception as e:
            raise AppException(code=500, message="查询工序失败", details={"error": str(e)})

    def batch_update_gongjia(self, db: Session, gsId: int, updates: List[Dict[str, Any]], up_userid: int,xbkhId: int):
        """
        批量更新工序的工价
        updates: [{"xbgxId": 1, "gongJia": 12.5}, ...]
        """
        if not updates:
            return
        try:
            xbgx_ids = [upd["xbgxId"] for upd in updates]
            # 增加 xbkhId 过滤
            filter_condition = and_(
                AIXiangBaoGongXu.xbgxId.in_(xbgx_ids),
                AIXiangBaoGongXu.xbkhId == xbkhId,
                AIXiangBaoGongXu.del_flag == False
            )
            if gsId != GETSOFT_ID:
                filter_condition = and_(
                    filter_condition,
                    AIXiangBaoGongXu.gsId == gsId
                )
            existing = db.query(AIXiangBaoGongXu).filter(filter_condition).all()
            existing_ids = {e.xbgxId for e in existing}
            missing = [upd["xbgxId"] for upd in updates if upd["xbgxId"] not in existing_ids]
            if missing:
                raise NotFoundException(message="部分工序不存在或权限不足", details={"missing_xbgxIds": missing})
            bulk_update_data = []
            now = datetime.now()
            for upd in updates:
                bulk_update_data.append({
                    "xbgxId": upd["xbgxId"],
                    "gongJia": upd["gongJia"],
                    "up_userid": up_userid,
                    "up_time": now
                })
            db.bulk_update_mappings(AIXiangBaoGongXu, bulk_update_data)
            db.flush()
        except Exception as e:
            raise AppException(code=500, message="批量更新工价失败", details={"error": str(e)})