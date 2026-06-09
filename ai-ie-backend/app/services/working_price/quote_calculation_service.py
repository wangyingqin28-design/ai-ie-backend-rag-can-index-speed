from decimal import Decimal
from datetime import datetime
from typing import List, Tuple, Dict, Any
from sqlalchemy.orm import Session
from fastapi import Request
from loguru import logger

from app.services.system_manage.base_sys_service import BaseService
from app.services.user.user_crud import get_gsId_by_userid
from app.services.working_price.bag_process_crud import XiangBaoGongXuCRUD
from app.services.system_manage.GongSiGongJia_crud import GongSiGongJiaCRUD
from app.models.orm_models import AIXiangBaoGongXu
from app.utils.database import SessionLocal
from app.utils.exceptions import AppException, ValidationException


class QuoteCalculationService(BaseService):
    """报价核算服务 - 负责工价计算、报价核算、处理工价变更"""

    async def get_current_quote(self, xbkhId: int, request: Request, user_id: int) -> dict:
        """获取款号当前总报价（SSE 初始数据）"""
        db = BaseService.get_db_session(request)
        try:
            gsId = get_gsId_by_userid(db, user_id)
            return await self._calculate_quote(db, gsId, xbkhId)
        finally:
            db.flush()

    async def recalculate_quote_for_xbkh(self, xbkhId: int, request: Request, user_id: int) -> dict:
        """重新计算并更新指定款号的报价（HTTP 请求）"""
        db = BaseService.get_db_session(request)
        try:
            gsId = get_gsId_by_userid(db, user_id)
            quote_data = await self._calculate_and_update(db, gsId, xbkhId, user_id)
            db.flush()
            return quote_data
        finally:
            db.flush()

    async def handle_gongjia_change(self, gs_id: int, xbgz_id: int, new_gongjia: Decimal) -> List[Tuple[int, dict]]:
        """
        处理工价变更（Kafka 消费者调用）
        返回 [(xbkh_id, quote_data), ...]
        """
        db = SessionLocal()
        try:
            # 查询受影响的款号
            xbkh_records = db.query(AIXiangBaoGongXu.xbkhId).filter(
                AIXiangBaoGongXu.gsId == gs_id,
                AIXiangBaoGongXu.xbgzId == xbgz_id,
                AIXiangBaoGongXu.del_flag == False
            ).distinct().all()
            xbkh_ids = [row[0] for row in xbkh_records]
            if not xbkh_ids:
                return []

            result = []
            for xbkh_id in xbkh_ids:
                quote_data = await self._calculate_and_update(db, gs_id, xbkh_id, user_id=0)
                result.append((xbkh_id, quote_data))
            db.commit()
            return result
        except Exception as e:
            db.rollback()
            logger.exception(f"处理工价变更失败: gsId={gs_id}, xbgzId={xbgz_id}")
            raise
        finally:
            db.close()

    async def _calculate_and_update(self, db: Session, gsId: int, xbkhId: int, user_id: int) -> dict:
        """核心计算逻辑：计算总报价并更新数据库中的工序工价"""
        crud = XiangBaoGongXuCRUD()
        processes = crud.get_processes_with_time(db=db, gsId=gsId, xbkhId=xbkhId)
        gongjia_map = GongSiGongJiaCRUD.get_gongjia_map(db, gsId)

        updates = []
        total_price = Decimal(0)
        for proc in processes:
            if proc["time"] is None:
                continue
            gongjia = gongjia_map.get(proc["xbgzId"])
            if gongjia is None:
                continue
            # 工时(秒) * (工价元/月) / (30天 * 86400秒)
            price = Decimal(str(proc["time"])) * (Decimal(str(gongjia)) / 30 / 86400)
            total_price += price
            updates.append({"xbgxId": proc["xbgxId"], "gongJia": price})

        if updates:
            crud.batch_update_gongjia(db=db, gsId=gsId, updates=updates, up_userid=user_id, xbkhId=xbkhId)

        difficulty = await self._get_difficulty_for_xbkh(db, xbkhId)
        final_price = total_price * Decimal(str(difficulty)) * Decimal(1+1/4)

        return {
            "xbkhId": xbkhId,
            "total_quote": float(final_price),
            "cost_price": float(total_price),
            "update_time": datetime.now().isoformat(),
            "details": {
                "total_gongjia": float(total_price),
                "difficulty": difficulty
            }
        }

    async def _calculate_quote(self, db: Session, gsId: int, xbkhId: int) -> dict:
        """仅计算总报价，不更新数据库（用于只读场景）"""
        crud = XiangBaoGongXuCRUD()
        processes = crud.get_processes_with_time(db=db, gsId=gsId, xbkhId=xbkhId)
        gongjia_map = GongSiGongJiaCRUD.get_gongjia_map(db, gsId)

        total_price = Decimal(0)
        for proc in processes:
            if proc["time"] is None:
                continue
            gongjia = gongjia_map.get(proc["xbgzId"])
            if gongjia is None:
                continue
            price = Decimal(str(proc["time"])) * (Decimal(str(gongjia)) / 30 / 86400)
            total_price += price

        difficulty = await self._get_difficulty_for_xbkh(db, xbkhId)
        final_price = total_price * Decimal(str(difficulty)) * Decimal(1+1/4)

        return {
            "xbkhId": xbkhId,
            "total_quote": float(final_price),
            "cost_price": float(total_price),
            "update_time": datetime.now().isoformat()
        }

    async def _get_difficulty_for_xbkh(self, db: Session, xbkhId: int) -> float:
        """获取款号的难度系数（根据实际业务实现）"""
        # TODO: 查询 AIXiangBaoCaiPian 表，计算平均/最大难度系数
        # 示例: 从裁片表取平均值
        # from app.models.orm_models import AIXiangBaoCaiPian
        # result = db.query(func.avg(AIXiangBaoCaiPian.nanDuXiShu)).filter(
        #     AIXiangBaoCaiPian.xbkhId == xbkhId,
        #     AIXiangBaoCaiPian.del_flag == False
        # ).scalar()
        # return float(result) if result else 1.0
        return 1.0

    async def calculate_gongjia_by_mode(
            self,
            xbkhId: int,
            mode: int,
            request: Request,
            user_id: int
    ) -> dict:
        """
        根据模式（区域工价或公司工价）重新计算并更新工序工价
        """
        db = BaseService.get_db_session(request)
        try:
            gsId = get_gsId_by_userid(db, user_id)
            crud = XiangBaoGongXuCRUD()
            processes = crud.get_processes_with_time(db=db, gsId=gsId, xbkhId=xbkhId)

            # 根据 mode 获取工价映射
            if mode == 0:
                # 区域工价：需要先获取款号的地区编码
                from app.services.dxf.dxf_crud import query_aiXiangBaoKuanHao_by_xbkhId
                kuanhao = query_aiXiangBaoKuanHao_by_xbkhId(db, xbkhId)
                if not kuanhao or not kuanhao.dqbmId:
                    raise ValidationException(message="该款号的地区编码为空，无法查询区域工价")
                from app.services.system_manage.QuYuGongJia_crud import QuYuGongJiaCRUD
                gongjia_map = QuYuGongJiaCRUD.get_quyu_gongjia_map(db, dqbmId=kuanhao.dqbmId)
            else:
                from app.services.system_manage.GongSiGongJia_crud import GongSiGongJiaCRUD
                gongjia_map = GongSiGongJiaCRUD.get_gongjia_map(db, gsId)

            updates = []
            total_price = Decimal(0)
            for proc in processes:
                if proc["time"] is None:
                    continue
                gongjia = gongjia_map.get(proc["xbgzId"])
                if gongjia is None:
                    continue
                price = Decimal(str(proc["time"])) * (Decimal(str(gongjia)) / 30 / 86400)
                total_price += price
                updates.append({"xbgxId": proc["xbgxId"], "gongJia": price})

            if not updates:
                raise AppException(code=500,message="没有有效的工价数据可更新")

            crud.batch_update_gongjia(db=db, gsId=gsId, updates=updates, up_userid=user_id, xbkhId=xbkhId)

            difficulty = await self._get_difficulty_for_xbkh(db, xbkhId)
            final_price = total_price * Decimal(str(difficulty))*Decimal(1+1/4)

            db.flush()
            return {
                "message": "工价计算并更新成功",
                "updated_count": len(updates),
                "total_processes": len(processes),
                "total_quote": float(final_price),
                "cost_price": float(total_price)
            }
        finally:
            db.flush()