import decimal
from datetime import datetime
from typing import Optional, List, Tuple

from sqlalchemy import desc
from sqlalchemy.orm import Session, aliased

from app.models import orm_models
from app.utils.exceptions import (
    NotFoundException, ValidationException, AppException
)
from app.utils.snowflake_generator import SnowFlake


class LiShiGongJiaCRUD:
    """历史工价数据库操作类"""

    @staticmethod
    def search_admin(
            db: Session,
            gjId: int,
            page: int = 1,
            page_size: int = 20,
    ) -> Tuple[List[dict], int]:
        """
        搜索历史工价（返回数据列表和总数，不执行分页）
        """
        try:
            # 创建用户表的别名（只需要连接创建用户）
            insert_user = aliased(orm_models.AIGongSiYongHu, name="insert_user")


            # 构建查询
            query = db.query(
                orm_models.AILiShiGongJia,
                insert_user.yongHuXingMing.label('insert_user_name')
            )

            # 左外连接创建用户表
            query = query.outerjoin(
                insert_user,
                orm_models.AILiShiGongJia.in_userid == insert_user.gsyhId
            )

            # 关键词搜索 - 按工价ID搜索
            query = query.filter(
                orm_models.AILiShiGongJia.gjId == gjId,
            )
            # 排序
            query = query.order_by(desc(orm_models.AILiShiGongJia.in_time))

            # 获取总数
            total = query.count()

            # 分页
            offset = (page - 1) * page_size
            results = query.offset(offset).limit(page_size).all()

            # 转换为字典
            result_list = []
            for record, insert_user_name in results:
                item = {
                    "lsgjId": record.lsgjId,
                    "is_gongSi_gongJia": record.is_gongSi_gongJia,
                    "gongJia": record.gongJia,
                    "gjId": record.gjId if record.gjId else 0,
                    "bianGengYuanYin": record.bianGengYuanYin,
                    "in_userid": record.in_userid,
                    "in_time": record.in_time,
                    "in_username": insert_user_name if insert_user_name else "无注册"
                }
                result_list.append(item)
            return result_list, total
        except Exception as e:
            raise AppException(
                code=500,
                message="查询历史工价失败",
                details={
                    "error": str(e),
                }
            )
    @staticmethod
    def search_user(
            db: Session,
            gjId: int,
            gsId:int,
            page: int = 1,
            page_size: int = 20,
    ) -> Tuple[List[dict], int]:
        """
        搜索历史工价（返回数据列表和总数，不执行分页）
        """
        try:
            # 创建用户表的别名（只需要连接创建用户）
            insert_user = aliased(orm_models.AIGongSiYongHu, name="insert_user")


            # 构建查询
            query = db.query(
                orm_models.AILiShiGongJia,
                insert_user.yongHuXingMing.label('insert_user_name')
            )

            # 左外连接创建用户表
            query = query.outerjoin(
                insert_user,
                orm_models.AILiShiGongJia.in_userid == insert_user.gsyhId
            )

            # 关键词搜索 - 按工价ID搜索
            query = query.filter(
                orm_models.AILiShiGongJia.gjId == gjId,
                orm_models.AILiShiGongJia.gsId == gsId,
            )

            # 排序
            query = query.order_by(desc(orm_models.AILiShiGongJia.in_time))

            # 获取总数
            total = query.count()

            # 分页
            offset = (page - 1) * page_size
            results = query.offset(offset).limit(page_size).all()

            # 转换为字典
            result_list = []
            for record, insert_user_name in results:
                item = {
                    "lsgjId": record.lsgjId,
                    "is_gongSi_gongJia": record.is_gongSi_gongJia,
                    "gongJia": record.gongJia,
                    "gjId": record.gjId if record.gjId else 0,
                    "bianGengYuanYin": record.bianGengYuanYin,
                    "in_userid": record.in_userid,
                    "in_time": record.in_time,
                    "in_username": insert_user_name if insert_user_name else "无注册"
                }
                result_list.append(item)
            return result_list, total
        except Exception as e:
            raise AppException(
                code=500,
                message="查询历史工价失败",
                details={
                    "error": str(e),
                }
            )
    @staticmethod
    def create(
            db: Session,
            gsId: int,
            gjId: int,
            is_gongSi_gongJia: bool,
            user_id: int,
            gongJia: decimal.Decimal,
            bianGengYuanYin: Optional[str] = None,
    ) -> orm_models.AILiShiGongJia:
        """
        创建公司ID

        Args:
            db: 数据库会话
            gsId: 公司IDID
            user_id: 用户ID
            gongJia: 工价
            xbgzId: 推荐工种ID

        Returns:
            创建的公司ID对象
        """
        try:
            current_time = datetime.now()

            new_gongSiGongJia = orm_models.AILiShiGongJia(
                lsgjId=SnowFlake().generate_id(),
                gjId=gjId,
                is_gongSi_gongJia=is_gongSi_gongJia,
                gongJia=gongJia,
                bianGengYuanYin=bianGengYuanYin,
                in_userid=user_id,
                in_time=current_time,
                gsId=gsId,
            )

            db.add(new_gongSiGongJia)
            db.flush()

            return new_gongSiGongJia
        except Exception as e:
            raise AppException(
                code=500,
                message="创建历史工价操作失败",
                details={
                    "error": str(e),
                }
            )