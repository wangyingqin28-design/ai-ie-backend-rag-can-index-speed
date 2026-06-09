# app/crud/caoZuoRiZhi_crud.py
import json
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy import desc, and_
from sqlalchemy.orm import Session
from app.models.orm_models import AICaoZuoRiZhi
from app.utils.exceptions import (
    NotFoundException, AppException
)
from app.utils.snowflake_generator import SnowFlake
class CaoZuoRiZhiCRUD:
    """操作日志数据库操作类"""
    # ==========================================================================
    # 查询相关方法
    # ==========================================================================
    @staticmethod
    def get_by_id(
            db: Session,
            czrzId: int
    ) -> AICaoZuoRiZhi:
        """
        根据ID获取操作日志
        """
        try:
            log = db.query(AICaoZuoRiZhi).filter(
                AICaoZuoRiZhi.czrzId == czrzId
            ).first()
            if not log:
                raise NotFoundException(
                    message="操作日志不存在",
                    details={"czrzId": czrzId}
                )
            return log
        except NotFoundException as e:
            raise e
        except Exception as e:
            traceback.print_exc()
            raise AppException(
                code=500,
                message="查询操作日志失败",
                details={"error": str(e), "czrzId": czrzId}
            )
    @staticmethod
    def search(
            db: Session,
            biaoMing: Optional[str] = None,
            page: int = 1,
            page_size: int = 20
    ) -> Tuple[List[AICaoZuoRiZhi], int]:
        """
        搜索操作日志
        """
        try:
            query = db.query(AICaoZuoRiZhi)
            if biaoMing:
                query=query.filter(AICaoZuoRiZhi.biaoMing.like(f"%{biaoMing}%"))
            # 获取总数
            total = query.count()
            # 排序和分页
            query = query.order_by(desc(AICaoZuoRiZhi.in_time))
            offset = (page - 1) * page_size
            results = query.offset(offset).limit(page_size).all()
            return results, total
        except Exception as e:
            traceback.print_exc()
            raise AppException(
                code=500,
                message="搜索操作日志失败",
                details={"error": str(e)}
            )
    # ==========================================================================
    # 创建方法
    # ==========================================================================
    @staticmethod
    def create(
            db: Session,
            biaoMing: str,
            caoZuoZhuJian: int,
            caoZuoLeiXing: int ,
            liShiShuJu: Dict[str, Any],
            in_userid: Optional[int] = None
    ) -> bool:
        """
        创建操作日志记录
        Args:
            db: 数据库会话
            biaoMing: 表名
            caoZuoZhuJian: 操作行数据的主键（int格式）
            caoZuoLeiXing: 操作类型 (1:修改, 2:删除)
            liShiShuJu: 历史数据（字典格式）
            in_userid: 操作人ID
        Returns:
            返回是否创建成功
        """
        try:
            # 序列化历史数据
            liShiShuJu_str = None
            liShiShuJu_str = json.dumps(
                liShiShuJu,
                ensure_ascii=False)
            if len(liShiShuJu_str) > 255:
                raise AppException(
                    code=500,
                    message="保存的历史数据大于255上限"
                )
            # 创建日志记录
            current_time = datetime.now()
            new_log = AICaoZuoRiZhi(
                czrzId=SnowFlake().generate_id(),
                biaoMing=biaoMing,
                caoZuoZhuJian=caoZuoZhuJian,
                caoZuoLeiXing=caoZuoLeiXing,
                liShiShuJu=liShiShuJu_str,
                in_userid=in_userid,
                in_time=current_time
            )
            db.add(new_log)
            db.flush()
            return True
        except AppException:
            raise
        except Exception as e:
            traceback.print_exc()
            raise AppException(
                code=500,
                message="创建操作日志失败",
                details={
                    "error": str(e),
                    "biaoMing": biaoMing,
                    "caoZuoZhuJian": caoZuoZhuJian
                }
            )
    # ==========================================================================
    # 恢复相关方法
    # ==========================================================================
    @staticmethod
    def parse_history_data(liShiShuJu: Optional[str]) -> Dict[str, Any]:
        """
        解析历史数据字符串
        """
        if not liShiShuJu:
            return {}
        try:
            return json.loads(liShiShuJu)
        except json.JSONDecodeError:
            return {"raw": liShiShuJu}
