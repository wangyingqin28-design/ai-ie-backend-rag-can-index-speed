import decimal
import os
from datetime import datetime
from typing import Optional, List, Tuple

from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import and_, desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, aliased

from app.models import orm_models
from app.models.orm_models import AIGongSiGongJia
from app.utils.exceptions import (
    NotFoundException, ValidationException, AppException
)

load_dotenv()
GETSOFT_ID_STR = os.getenv("GETSOFT_ID")
GETSOFT_ID = int(GETSOFT_ID_STR)
from app.utils.snowflake_generator import SnowFlake
class GongSiGongJiaCRUD:
    """公司工价数据库操作类"""

    # ==========================================================================
    # 查询相关方法
    # ==========================================================================
    @staticmethod
    def get_by_id(
            db: Session,
            gsgjId: int,
            gsId:int,
    ) -> Optional[orm_models.AIGongSiGongJia]:
        """
        根据ID获取公司工价（包含用户信息）
        Args:
            db: 数据库会话
            gsgjId: 公司工价ID
            gsId:公司ID
        Returns:
            包含公司工价信息、工种名称、公司名称和用户名称的字典
        """
        try:
            if gsId == GETSOFT_ID:
                logger.info('本公司查询单条数据')
                query = db.query(orm_models.AIGongSiGongJia).filter(
                    orm_models.AIGongSiGongJia.gsgjId == gsgjId
                ).first()
                if query is None:
                    raise NotFoundException(
                        message="公司工价为空"
                    )
            else:
                logger.info('其他公司查询单条数据')
                query = db.query(orm_models.AIGongSiGongJia).filter(
                    orm_models.AIGongSiGongJia.gsId == gsId,
                    orm_models.AIGongSiGongJia.gsgjId == gsgjId
                ).first()
                if query is None:
                    raise NotFoundException(
                        message="公司工价为空"
                    )

            return query

        except NotFoundException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="查询单条公司工价操作失败",
                details={
                    "error": str(e),
                }
            )
    @staticmethod
    def search_admin(
            db: Session,
            gsId: int,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 20,
    ) -> Tuple[List[dict], int]:
        """
        搜索公司工价（返回数据列表和总数，不执行分页）
        """
        try:
            # 1. 先检查公司是否存在
            company = db.query(orm_models.AIGongSi).filter(
                orm_models.AIGongSi.gsId == gsId
            ).first()

            if not company:
                raise NotFoundException(
                    message="未找到公司"
                )

            # 2. 创建用户表的别名
            insert_user = aliased(orm_models.AIGongSiYongHu, name="insert_user")
            update_user = aliased(orm_models.AIGongSiYongHu, name="update_user")
            gongSi = aliased(orm_models.AIGongSi, name="gongSi")
            gongZhong = aliased(orm_models.AIXiangBaoGongZhong, name="gongZhong")
            query = db.query(
                orm_models.AIGongSiGongJia,
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name'),
                gongZhong.gongZhongMingCheng.label('gongZhong_name'),
                gongSi.gongSiQuanCheng.label('gongSi_name'),
            ).filter(
                orm_models.AIGongSiGongJia.del_flag == False)
            # 4. 左外连接创建用户表
            query = query.outerjoin(
                insert_user,
                orm_models.AIGongSiGongJia.in_userid == insert_user.gsyhId
            )
            # 5. 左外连接更新用户表
            query = query.outerjoin(
                update_user,
                orm_models.AIGongSiGongJia.up_userid == update_user.gsyhId
            )
            query = query.outerjoin(
                gongZhong,
                orm_models.AIGongSiGongJia.xbgzId == gongZhong.xbgzId
            )
            query = query.outerjoin(
                gongSi,
                orm_models.AIGongSiGongJia.gsId == gongSi.gsId
            )

            # 7. 关键词搜索 - 只在有关键词时才进行连接查询
            if keyword and keyword.strip():
                clean_keyword = keyword.strip()
                query = query.filter(
                    gongZhong.gongZhongMingCheng.like(f"%{clean_keyword}%")
                )

            # 8. 获取总数（在分页前）
            total = query.count()

            # 9. 排序和分页
            query = query.order_by(desc(orm_models.AIGongSiGongJia.up_time))
            offset = (page - 1) * page_size
            results = query.offset(offset).limit(page_size).all()

            # 10. 转换为字典
            result_list = []
            for record, insert_user_name, update_user_name, gongZhong_name,gongSi_name in results:
                item = {
                    "gsgjId": record.gsgjId,
                    "gsId": record.gsId,
                    "xbgzId": record.xbgzId,
                    "gongJia": float(record.gongJia) if record.gongJia is not None else 0.0,
                    "in_userid": record.in_userid,
                    "in_time": record.in_time.isoformat() if record.in_time else None,
                    "up_userid": record.up_userid,
                    "up_time": record.up_time.isoformat() if record.up_time else None,
                    "gongZhong": gongZhong_name if gongZhong_name else "工种未注册",
                    "in_username": insert_user_name if insert_user_name else "无注册",
                    "up_username": update_user_name if update_user_name else "无注册",
                    "gongSi":gongSi_name if gongSi_name else "公司无注册",
                }
                result_list.append(item)
            return result_list, total

        except NotFoundException:
            # 重新抛出业务异常
            raise
        except Exception as e:
            # 添加更详细的错误信息
            raise AppException(
                code=500,
                message="查询公司工价失败",
                details={
                    "error": str(e),
                    "keyword": keyword
                }
            )

    @staticmethod
    def search_user(
            db: Session,
            gsId: int,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 20,
    ) -> Tuple[List[dict], int]:
        """
        搜索公司工价（返回数据列表和总数，不执行分页）
        """
        try:
            # 1. 先检查公司是否存在
            company = db.query(orm_models.AIGongSi).filter(
                orm_models.AIGongSi.gsId == gsId
            ).first()
            if not company:
                raise NotFoundException(
                    message="未找到公司"
                )

            # 2. 创建用户表的别名
            insert_user = aliased(orm_models.AIGongSiYongHu, name="insert_user")
            update_user = aliased(orm_models.AIGongSiYongHu, name="update_user")
            gongZhong = aliased(orm_models.AIXiangBaoGongZhong, name="gongZhong")

            query = db.query(
                orm_models.AIGongSiGongJia,
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name'),
                gongZhong.gongZhongMingCheng.label('gongZhong_name'),
            ).filter(
                orm_models.AIGongSiGongJia.del_flag == False,
                orm_models.AIGongSiGongJia.gsId == gsId
            )

            # 4. 左外连接创建用户表
            query = query.outerjoin(
                insert_user,
                orm_models.AIGongSiGongJia.in_userid == insert_user.gsyhId
            )
            # 5. 左外连接更新用户表
            query = query.outerjoin(
                update_user,
                orm_models.AIGongSiGongJia.up_userid == update_user.gsyhId
            )
            query = query.outerjoin(
                gongZhong,
                orm_models.AIGongSiGongJia.xbgzId == gongZhong.xbgzId
            )

            # 7. 关键词搜索 - 只在有关键词时才进行连接查询
            if keyword and keyword.strip():
                clean_keyword = keyword.strip()
                query = query.filter(
                    gongZhong.gongZhongMingCheng.like(f"%{clean_keyword}%")
                )

            # 8. 获取总数（在分页前）
            total = query.count()

            # 9. 排序和分页
            query = query.order_by(desc(orm_models.AIGongSiGongJia.up_time))
            offset = (page - 1) * page_size
            results = query.offset(offset).limit(page_size).all()

            # 10. 转换为字典
            result_list = []

            for record, insert_user_name, update_user_name, gongZhong_name in results:
                item = {
                    "gsgjId": record.gsgjId,
                    "xbgzId": record.xbgzId,
                    "gongJia": float(record.gongJia) if record.gongJia is not None else 0.0,
                    "in_userid": record.in_userid,
                    "in_time": record.in_time.isoformat() if record.in_time else None,
                    "up_userid": record.up_userid,
                    "up_time": record.up_time.isoformat() if record.up_time else None,
                    "gongZhong": gongZhong_name,
                    "in_username": insert_user_name if insert_user_name else "无注册",
                    "up_username": update_user_name if update_user_name else "无注册",
                }
                result_list.append(item)

            return result_list, total

        except NotFoundException:
            # 重新抛出业务异常
            raise
        except Exception as e:
            # 添加更详细的错误信息
            raise AppException(
                code=500,
                message="查询公司工价操作失败",
                details={
                    "error": str(e),
                    "keyword": keyword
                }
            )
    @staticmethod
    def get_existing_by_record(
            db: Session,
            gsId: int,
            gsgjId: int,
            exclude_id: Optional[int] = None
    ) -> Optional[orm_models.AIGongSiGongJia]:
        """
        根据区域获取已存在的工价

        Args:
            db: 数据库会话
            gsId: 公司ID
            gsgjId:公司工价ID
            exclude_id: 要排除的ID

        Returns:
            已存在的公司ID对象或None
        """
        try:
            query = db.query(orm_models.AIGongSiGongJia).filter(
                and_(
                    orm_models.AIGongSiGongJia.gsId == gsId,
                    orm_models.AIGongSiGongJia.gsgjId == gsgjId
                )
            )
            if exclude_id:
                query = query.filter(orm_models.AIGongSiGongJia.gsgjId != exclude_id)
            return query.first()
        except Exception as e:
            raise AppException(
                code=500,
                message="查询同公司工种工价操作失败",
                details={
                    "error": str(e),
                }
            )

    # ==========================================================================
    # 创建、更新、删除方法
    # ==========================================================================

    @staticmethod
    def create(
            db: Session,
            gsId: int,
            user_id: int,
            gongJia: decimal.Decimal,
            xbgzId: int,
            gsgjId: Optional[int] = None,
    ) -> bool:
        """
        创建公司ID
        Args:
            db: 数据库会话
            gsId: 公司IDID
            user_id: 用户ID
            gongJia: 工价
            gsgjId: 推荐工种ID
            xbgzId:工种ID
        Returns:
            创建的公司ID对象
        """
        try:
            gongZhong = db.query(orm_models.AIXiangBaoGongZhong).filter(
                orm_models.AIXiangBaoGongZhong.xbgzId == xbgzId,
                orm_models.AIXiangBaoGongZhong.del_flag == False,
                orm_models.AIXiangBaoGongZhong.gsId == gsId
            ).first()
            if not gongZhong:
                raise ValidationException(
                    message="工种不存在或被删除",
                    details={"gsgjId": gsgjId}
                )
            gongSi = db.query(orm_models.AIGongSi).filter(
                orm_models.AIGongSi.gsId == gsId,
                orm_models.AIGongSi.del_flag == False
            ).first()
            if not gongSi:
                raise ValidationException(
                    message="公司不存在或被删除",
                    details={"gsId": gsId}
                )
            current_time = datetime.now()
            gsgjId=SnowFlake().generate_id()

            new_gongSiGongJia = orm_models.AIGongSiGongJia(
                gsgjId=gsgjId,
                gsId=gsId,
                gongJia=gongJia,
                xbgzId=xbgzId,
                in_userid=user_id,
                in_time=current_time,
                up_userid=user_id,
                up_time=current_time,
                del_flag=False,
            )

            db.add(new_gongSiGongJia)
            db.flush()
            return True
        except ValidationException as e:
            raise
        except NotFoundException as e:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="创建公司操作失败",
                details={
                    "error": str(e),
                    "gsId": gsId,
                    "user_id": user_id
                }
            )

    @staticmethod
    def update(
            db: Session,
            gsId: int,
            gsgjId: int,
            xbgzId: int,
            gongJia: decimal.Decimal,
            user_id: int
    ) -> bool:
        """
        更新标准公司工价信息

        Args:
            db: 数据库会话
            gsgjId: 公司工价ID
            xbgzId: 项目工种ID
            gongJia: 工价
            user_id: 用户ID

        Returns:
            更新后的公司工价对象
        """
        try:
            # 验证工种是否存在
            if gsId == GETSOFT_ID:
                logger.info('本公司更新单条数据')
                gongZhong = db.query(orm_models.AIXiangBaoGongZhong).filter(
                    orm_models.AIXiangBaoGongZhong.xbgzId == xbgzId,
                    orm_models.AIXiangBaoGongZhong.del_flag == False,
                    orm_models.AIXiangBaoGongZhong.gsId == GETSOFT_ID,
                ).first()
                if not gongZhong:
                    raise NotFoundException(
                        message="工种不存在或被删除",
                    )
                gsgj = db.query(orm_models.AIGongSiGongJia).filter(
                    orm_models.AIGongSiGongJia.gsgjId == gsgjId,
                    orm_models.AIGongSiGongJia.del_flag == False
                ).first()
                if not gsgj:
                    raise NotFoundException(
                        message="公司工价不存在或被删除"
                    )
            else:
                logger.info('其他公司更新单条数据')
                gongZhong = db.query(orm_models.AIXiangBaoGongZhong).filter(
                    orm_models.AIXiangBaoGongZhong.xbgzId == xbgzId,
                    orm_models.AIXiangBaoGongZhong.del_flag == False,
                    orm_models.AIXiangBaoGongZhong.gsId == gsId,
                ).first()
                if not gongZhong:
                    raise NotFoundException(
                        message="工种不存在或被删除",
                    )
                gsgj = db.query(orm_models.AIGongSiGongJia).filter(
                    orm_models.AIGongSiGongJia.gsgjId == gsgjId,
                    orm_models.AIGongSiGongJia.del_flag == False,
                    orm_models.AIGongSiGongJia.gsId == gsId,
                ).first()
                if not gsgj:
                    raise NotFoundException(
                        message="公司工价不存在或被删除"
                    )
            db.query(orm_models.AIGongSiGongJia).filter(
                orm_models.AIGongSiGongJia.gsgjId == gsgjId,
                orm_models.AIGongSiGongJia.del_flag == False
            ).update(
                    {
                    orm_models.AIGongSiGongJia.gongJia: gongJia,
                    orm_models.AIGongSiGongJia.xbgzId: xbgzId,
                    orm_models.AIGongSiGongJia.up_userid: user_id,
                    orm_models.AIGongSiGongJia.up_time: datetime.now().replace(microsecond=0)
                }
            )
            # 提交事务
            db.flush()

            # 重新查询更新后的记录返回
            db.query(orm_models.AIGongSiGongJia).filter(
                and_(
                    orm_models.AIGongSiGongJia.gsgjId == gsgjId,
                    orm_models.AIGongSiGongJia.del_flag == False,
                )
            ).first()

            return True

        except NotFoundException:
            raise
        except ValidationException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="更新公司工价操作失败",
                details={
                    "error": str(e)}
            )

    @staticmethod
    def restore(
            db: Session,
            gsgjId: int,
            user_id: int,
            gsId: int,
    ) -> bool:
        """
        恢复已删除的标准公司工价

        Args:
            gsId:公司ID
            db: 数据库会话
            gsgjId: 公司工价ID
            user_id: 用户ID

        Returns:
            True如果恢复成功
        """
        try:
            if gsId == GETSOFT_ID:
                logger.info('本公司恢复单条数据')
                biaoZhunGongXu = db.query(orm_models.AIGongSiGongJia).filter(
                    and_(
                        orm_models.AIGongSiGongJia.gsgjId == gsgjId,
                        orm_models.AIGongSiGongJia.del_flag == True
                    )
                ).first()
            else:
                logger.info('其他公司恢复单条数据')
                biaoZhunGongXu = db.query(orm_models.AIGongSiGongJia).filter(
                    and_(
                        orm_models.AIGongSiGongJia.gsgjId == gsgjId,
                        orm_models.AIGongSiGongJia.del_flag == True,
                        orm_models.AIGongSiGongJia.gsId == gsId
                    )
                ).first()

            if not biaoZhunGongXu:
                raise NotFoundException(
                    message="公司工价不存在或未被删除",
                    details={"gsgjId": gsgjId}
                )

            # 恢复删除标记
            biaoZhunGongXu.del_flag = False
            biaoZhunGongXu.up_userid = user_id
            biaoZhunGongXu.del_time = None
            biaoZhunGongXu.up_time = datetime.now().replace(microsecond=0)

            db.flush()
            return True
        except AppException:
            raise
        except SQLAlchemyError as e:
            raise AppException(
                code=500,
                message="恢复公司工价失败",
                details={"error": str(e)}
            )
        except Exception as e:
            raise AppException(
                code=500,
                message="恢复公司工价操作失败",
                details={"error": str(e)}
            )
    @staticmethod
    def batch_delete(
            db: Session,
            gsgjIds: List[int],
            gsId:int,
            user_id: int
    ) -> int:
        """
        批量软删除标准公司工价

        Args:
            gsId:公司ID
            db: 数据库会话
            gsgjIds: 公司工价ID列表
            user_id: 用户ID

        Returns:
            删除结果统计
        """
        try:
            current_time = datetime.now()
            # 1. 先查询所有要删除的记录
            if gsId == GETSOFT_ID:
                logger.info('本公司删除数据')
                logger.info(f'gsgjIds: {gsgjIds}')
                target_records = db.query(orm_models.AIGongSiGongJia).filter(
                    AIGongSiGongJia.gsgjId.in_(gsgjIds),
                    AIGongSiGongJia.del_flag == 0,
                ).all()
            else:
                logger.info('其他公司删除数据')
                target_records = db.query(orm_models.AIGongSiGongJia).filter(
                    AIGongSiGongJia.gsgjId.in_(gsgjIds),
                    AIGongSiGongJia.gsId == gsId,
                ).all()
            # 2. 检查是否存在
            if not target_records:
                # 所有ID都不存在
                raise ValidationException(
                    message="删除的公司工价不存在"
                )
            # 3. 分离已删除和未删除的记录
            already_deleted_ids = []
            to_delete_ids = []
            for record in target_records:
                if record.del_flag:
                    already_deleted_ids.append(record.gsgjId)
                else:
                    to_delete_ids.append(record.gsgjId)
            # 4. 检查是否有记录已被删除
            if already_deleted_ids:
                # 如果有部分记录已被删除，抛出异常
                raise ValidationException(
                    message=f"部分公司工价已被删除，无法重复删除，已删除的公司工价ID: {already_deleted_ids}"
                )
            # 5. 检查是否有不存在的ID（所有查询到的记录数小于传入的ID数）
            found_ids = [record.gsgjId for record in target_records]
            not_found_ids = [id for id in gsgjIds if id not in found_ids]
            if not_found_ids:
                raise ValidationException(
                    message=f"部分公司工价不存在，不存在的公司工价ID: {not_found_ids}"
                )
            # 6. 执行删除（更新del_flag为True）
            delete_count = db.query(orm_models.AIGongSiGongJia).filter(
                AIGongSiGongJia.gsgjId.in_(to_delete_ids),
                AIGongSiGongJia.del_flag == False
            ).update(
                {
                    AIGongSiGongJia.del_flag: True,
                    AIGongSiGongJia.up_userid: user_id,
                    AIGongSiGongJia.up_time: current_time.replace(microsecond=0),
                    AIGongSiGongJia.del_time: current_time.replace(microsecond=0)
                },
                synchronize_session=False
            )
            db.flush()
            return delete_count
        except ValidationException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="批量删除公司工价操作失败",
                details={"error": str(e)}
            )
    @staticmethod
    def get_gongjia_map(db: Session, gsId: int):
        """获取公司工价映射（xbgzId -> gongJia）"""
        records = db.query(orm_models.AIGongSiGongJia).filter(
            orm_models.AIGongSiGongJia.gsId == gsId,
            orm_models.AIGongSiGongJia.del_flag == False
        ).all()
        return {r.xbgzId: float(r.gongJia) for r in records if r.xbgzId and r.gongJia}


