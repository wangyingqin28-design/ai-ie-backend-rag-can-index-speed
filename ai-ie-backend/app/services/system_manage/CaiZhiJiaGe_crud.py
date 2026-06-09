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
from app.utils.exceptions import (
    NotFoundException, ValidationException, AppException
)
from app.utils.snowflake_generator import SnowFlake

load_dotenv()
GETSOFT_ID_STR = os.getenv("GETSOFT_ID")
GETSOFT_ID = int(GETSOFT_ID_STR)


class CaiZhiJiaGeCRUD:
    """材质价格数据库操作类"""

    # ==========================================================================
    # 查询相关方法
    # ==========================================================================
    @staticmethod
    def get_by_id(
            db: Session,
            czjgId: int,
            gsId: int,
    ) -> Optional[orm_models.AICaiZhiJiaGe]:
        """
        根据ID获取材质价格
        Args:
            db: 数据库会话
            czjgId: 材质价格ID
            gsId: 公司ID
        Returns:
            材质价格对象
        """
        try:
            if gsId == GETSOFT_ID:
                logger.info('本公司查询单条数据')
                query = db.query(orm_models.AICaiZhiJiaGe).filter(
                    orm_models.AICaiZhiJiaGe.czjgId == czjgId
                ).first()
                if query is None:
                    raise NotFoundException(
                        message="材质价格为空"
                    )
            else:
                logger.info('其他公司查询单条数据')
                query = db.query(orm_models.AICaiZhiJiaGe).filter(
                    orm_models.AICaiZhiJiaGe.gsId == gsId,
                    orm_models.AICaiZhiJiaGe.czjgId == czjgId
                ).first()
                if query is None:
                    raise NotFoundException(
                        message="材质价格为空"
                    )
            return query
        except NotFoundException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="查询单条材质价格操作失败",
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
        管理员搜索材质价格（返回数据列表和总数）
        """
        try:
            # 检查公司是否存在
            company = db.query(orm_models.AIGongSi).filter(
                orm_models.AIGongSi.gsId == gsId
            ).first()
            if not company:
                raise NotFoundException(
                    message="未找到公司"
                )

            # 别名
            insert_user = aliased(orm_models.AIGongSiYongHu, name="insert_user")
            update_user = aliased(orm_models.AIGongSiYongHu, name="update_user")
            gongSi = aliased(orm_models.AIGongSi, name="gongSi")
            caiZhi = aliased(orm_models.AIXiangBaoCaiZhi, name="caiZhi")

            query = db.query(
                orm_models.AICaiZhiJiaGe,
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name'),
                caiZhi.caiZhiMingCheng.label('caiZhi_name'),
                gongSi.gongSiQuanCheng.label('gongSi_name'),
            ).filter(orm_models.AICaiZhiJiaGe.del_flag == False)

            # 左连接
            query = query.outerjoin(
                insert_user,
                orm_models.AICaiZhiJiaGe.in_userid == insert_user.gsyhId
            )
            query = query.outerjoin(
                update_user,
                orm_models.AICaiZhiJiaGe.up_userid == update_user.gsyhId
            )
            query = query.outerjoin(
                caiZhi,
                orm_models.AICaiZhiJiaGe.xbczId == caiZhi.xbczId
            )
            query = query.outerjoin(
                gongSi,
                orm_models.AICaiZhiJiaGe.gsId == gongSi.gsId
            )

            # 关键词搜索
            if keyword and keyword.strip():
                clean_keyword = keyword.strip()
                query = query.filter(
                    caiZhi.caiZhiMingCheng.like(f"%{clean_keyword}%")
                )

            total = query.count()
            query = query.order_by(desc(orm_models.AICaiZhiJiaGe.up_time))
            offset = (page - 1) * page_size
            results = query.offset(offset).limit(page_size).all()

            result_list = []
            for record, insert_user_name, update_user_name, caiZhi_name, gongSi_name in results:
                item = {
                    "czjgId": record.czjgId,
                    "gsId": record.gsId,
                    "xbczId": record.xbczId,
                    "czjg": float(record.czjg) if record.czjg is not None else 0.0,
                    "in_userid": record.in_userid,
                    "in_time": record.in_time.isoformat() if record.in_time else None,
                    "up_userid": record.up_userid,
                    "up_time": record.up_time.isoformat() if record.up_time else None,
                    "caiZhi": caiZhi_name if caiZhi_name else "材质未注册",
                    "in_username": insert_user_name if insert_user_name else "无注册",
                    "up_username": update_user_name if update_user_name else "无注册",
                    "gongSi": gongSi_name if gongSi_name else "公司无注册",
                }
                result_list.append(item)
            return result_list, total

        except NotFoundException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="查询材质价格失败",
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
        普通用户搜索材质价格（仅本公司数据）
        """
        try:
            # 检查公司
            company = db.query(orm_models.AIGongSi).filter(
                orm_models.AIGongSi.gsId == gsId
            ).first()
            if not company:
                raise NotFoundException(
                    message="未找到公司"
                )

            insert_user = aliased(orm_models.AIGongSiYongHu, name="insert_user")
            update_user = aliased(orm_models.AIGongSiYongHu, name="update_user")
            caiZhi = aliased(orm_models.AIXiangBaoCaiZhi, name="caiZhi")

            query = db.query(
                orm_models.AICaiZhiJiaGe,
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name'),
                caiZhi.caiZhiMingCheng.label('caiZhi_name'),
            ).filter(
                orm_models.AICaiZhiJiaGe.del_flag == False,
                orm_models.AICaiZhiJiaGe.gsId == gsId
            )

            query = query.outerjoin(
                insert_user,
                orm_models.AICaiZhiJiaGe.in_userid == insert_user.gsyhId
            )
            query = query.outerjoin(
                update_user,
                orm_models.AICaiZhiJiaGe.up_userid == update_user.gsyhId
            )
            query = query.outerjoin(
                caiZhi,
                orm_models.AICaiZhiJiaGe.xbczId == caiZhi.xbczId
            )

            if keyword and keyword.strip():
                clean_keyword = keyword.strip()
                query = query.filter(
                    caiZhi.caiZhiMingCheng.like(f"%{clean_keyword}%")
                )

            total = query.count()
            query = query.order_by(desc(orm_models.AICaiZhiJiaGe.up_time))
            offset = (page - 1) * page_size
            results = query.offset(offset).limit(page_size).all()

            result_list = []
            for record, insert_user_name, update_user_name, caiZhi_name in results:
                item = {
                    "czjgId": record.czjgId,
                    "xbczId": record.xbczId,
                    "czjg": float(record.czjg) if record.czjg is not None else 0.0,
                    "in_userid": record.in_userid,
                    "in_time": record.in_time.isoformat() if record.in_time else None,
                    "up_userid": record.up_userid,
                    "up_time": record.up_time.isoformat() if record.up_time else None,
                    "caiZhi": caiZhi_name,
                    "in_username": insert_user_name if insert_user_name else "无注册",
                    "up_username": update_user_name if update_user_name else "无注册",
                }
                result_list.append(item)

            return result_list, total

        except NotFoundException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="查询材质价格操作失败",
                details={
                    "error": str(e),
                    "keyword": keyword
                }
            )

    @staticmethod
    def get_existing_by_record(
            db: Session,
            gsId: int,
            xbczId: int,
            exclude_id: Optional[int] = None
    ) -> Optional[orm_models.AICaiZhiJiaGe]:
        """
        根据公司ID和材质ID获取已存在的记录
        """
        try:
            query = db.query(orm_models.AICaiZhiJiaGe).filter(
                and_(
                    orm_models.AICaiZhiJiaGe.gsId == gsId,
                    orm_models.AICaiZhiJiaGe.xbczId == xbczId,
                    orm_models.AICaiZhiJiaGe.del_flag == False
                )
            )
            if exclude_id:
                query = query.filter(orm_models.AICaiZhiJiaGe.czjgId != exclude_id)
            return query.first()
        except Exception as e:
            raise AppException(
                code=500,
                message="查询同公司材质价格操作失败",
                details={"error": str(e)}
            )

    # ==========================================================================
    # 创建、更新、删除方法
    # ==========================================================================
    @staticmethod
    def create(
            db: Session,
            gsId: int,
            user_id: int,
            czjg: decimal.Decimal,
            xbczId: int,
            czjgId: Optional[int] = None,
    ) -> bool:
        """
        创建材质价格
        """
        try:
            # 验证材质是否存在且未删除
            caiZhi = db.query(orm_models.AIXiangBaoCaiZhi).filter(
                orm_models.AIXiangBaoCaiZhi.xbczId == xbczId,
                orm_models.AIXiangBaoCaiZhi.del_flag == False,
                orm_models.AIXiangBaoCaiZhi.gsId == gsId
            ).first()
            if not caiZhi:
                raise ValidationException(
                    message="材质不存在或被删除",
                    details={"xbczId": xbczId}
                )

            # 验证公司是否存在且未删除
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
            czjgId = SnowFlake().generate_id()

            new_caiZhiJiaGe = orm_models.AICaiZhiJiaGe(
                czjgId=czjgId,
                gsId=gsId,
                czjg=czjg,
                xbczId=xbczId,
                in_userid=user_id,
                in_time=current_time,
                up_userid=user_id,
                up_time=current_time,
                del_flag=False,
            )

            db.add(new_caiZhiJiaGe)
            db.flush()
            return True
        except ValidationException as e:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="创建材质价格操作失败",
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
            czjgId: int,
            xbczId: int,
            czjg: decimal.Decimal,
            user_id: int
    ) -> bool:
        """
        更新材质价格
        """
        try:
            # 验证材质是否存在
            if gsId == GETSOFT_ID:
                logger.info('本公司更新单条数据')
                caiZhi = db.query(orm_models.AIXiangBaoCaiZhi).filter(
                    orm_models.AIXiangBaoCaiZhi.xbczId == xbczId,
                    orm_models.AIXiangBaoCaiZhi.del_flag == False,
                    orm_models.AIXiangBaoCaiZhi.gsId == GETSOFT_ID,
                ).first()
                if not caiZhi:
                    raise NotFoundException(
                        message="材质不存在或被删除",
                    )
                czjgRecord = db.query(orm_models.AICaiZhiJiaGe).filter(
                    orm_models.AICaiZhiJiaGe.czjgId == czjgId,
                    orm_models.AICaiZhiJiaGe.del_flag == False
                ).first()
                if not czjgRecord:
                    raise NotFoundException(
                        message="材质价格不存在或被删除"
                    )
            else:
                logger.info('其他公司更新单条数据')
                caiZhi = db.query(orm_models.AIXiangBaoCaiZhi).filter(
                    orm_models.AIXiangBaoCaiZhi.xbczId == xbczId,
                    orm_models.AIXiangBaoCaiZhi.del_flag == False,
                    orm_models.AIXiangBaoCaiZhi.gsId == gsId,
                ).first()
                if not caiZhi:
                    raise NotFoundException(
                        message="材质不存在或被删除",
                    )
                czjgRecord = db.query(orm_models.AICaiZhiJiaGe).filter(
                    orm_models.AICaiZhiJiaGe.czjgId == czjgId,
                    orm_models.AICaiZhiJiaGe.del_flag == False,
                    orm_models.AICaiZhiJiaGe.gsId == gsId,
                ).first()
                if not czjgRecord:
                    raise NotFoundException(
                        message="材质价格不存在或被删除"
                    )

            db.query(orm_models.AICaiZhiJiaGe).filter(
                orm_models.AICaiZhiJiaGe.czjgId == czjgId,
                orm_models.AICaiZhiJiaGe.del_flag == False
            ).update(
                {
                    orm_models.AICaiZhiJiaGe.czjg: czjg,
                    orm_models.AICaiZhiJiaGe.xbczId: xbczId,
                    orm_models.AICaiZhiJiaGe.up_userid: user_id,
                    orm_models.AICaiZhiJiaGe.up_time: datetime.now().replace(microsecond=0)
                }
            )
            db.flush()
            return True

        except NotFoundException:
            raise
        except ValidationException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="更新材质价格操作失败",
                details={"error": str(e)}
            )

    @staticmethod
    def restore(
            db: Session,
            czjgId: int,
            user_id: int,
            gsId: int,
    ) -> bool:
        """
        恢复已删除的材质价格
        """
        try:
            if gsId == GETSOFT_ID:
                logger.info('本公司恢复单条数据')
                record = db.query(orm_models.AICaiZhiJiaGe).filter(
                    and_(
                        orm_models.AICaiZhiJiaGe.czjgId == czjgId,
                        orm_models.AICaiZhiJiaGe.del_flag == True
                    )
                ).first()
            else:
                logger.info('其他公司恢复单条数据')
                record = db.query(orm_models.AICaiZhiJiaGe).filter(
                    and_(
                        orm_models.AICaiZhiJiaGe.czjgId == czjgId,
                        orm_models.AICaiZhiJiaGe.del_flag == True,
                        orm_models.AICaiZhiJiaGe.gsId == gsId
                    )
                ).first()

            if not record:
                raise NotFoundException(
                    message="材质价格不存在或未被删除",
                    details={"czjgId": czjgId}
                )

            record.del_flag = False
            record.up_userid = user_id
            record.up_time = datetime.now().replace(microsecond=0)
            record.del_time = None

            db.flush()
            return True
        except AppException:
            raise
        except SQLAlchemyError as e:
            raise AppException(
                code=500,
                message="恢复材质价格失败",
                details={"error": str(e)}
            )
        except Exception as e:
            raise AppException(
                code=500,
                message="恢复材质价格操作失败",
                details={"error": str(e)}
            )

    @staticmethod
    def batch_delete(
            db: Session,
            czjgIds: List[int],
            gsId: int,
            user_id: int
    ) -> int:
        """
        批量软删除材质价格
        """
        try:
            current_time = datetime.now()
            if gsId == GETSOFT_ID:
                logger.info('本公司删除数据')
                target_records = db.query(orm_models.AICaiZhiJiaGe).filter(
                    orm_models.AICaiZhiJiaGe.czjgId.in_(czjgIds),
                    orm_models.AICaiZhiJiaGe.del_flag == 0,
                ).all()
            else:
                logger.info('其他公司删除数据')
                target_records = db.query(orm_models.AICaiZhiJiaGe).filter(
                    orm_models.AICaiZhiJiaGe.czjgId.in_(czjgIds),
                    orm_models.AICaiZhiJiaGe.gsId == gsId,
                ).all()

            if not target_records:
                raise ValidationException(
                    message="删除的材质价格不存在"
                )

            already_deleted_ids = []
            to_delete_ids = []
            for record in target_records:
                if record.del_flag:
                    already_deleted_ids.append(record.czjgId)
                else:
                    to_delete_ids.append(record.czjgId)

            if already_deleted_ids:
                raise ValidationException(
                    message=f"部分材质价格已被删除，无法重复删除，已删除的材质价格ID: {already_deleted_ids}"
                )

            found_ids = [record.czjgId for record in target_records]
            not_found_ids = [id for id in czjgIds if id not in found_ids]
            if not_found_ids:
                raise ValidationException(
                    message=f"部分材质价格不存在，不存在的材质价格ID: {not_found_ids}"
                )

            delete_count = db.query(orm_models.AICaiZhiJiaGe).filter(
                orm_models.AICaiZhiJiaGe.czjgId.in_(to_delete_ids),
                orm_models.AICaiZhiJiaGe.del_flag == False
            ).update(
                {
                    orm_models.AICaiZhiJiaGe.del_flag: True,
                    orm_models.AICaiZhiJiaGe.up_userid: user_id,
                    orm_models.AICaiZhiJiaGe.up_time: current_time.replace(microsecond=0),
                    orm_models.AICaiZhiJiaGe.del_time: current_time.replace(microsecond=0),
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
                message="批量删除材质价格操作失败",
                details={"error": str(e)}
            )

    @staticmethod
    def get_caizhi_map(db: Session, gsId: int):
        """获取材质价格映射（xbczId -> czjg）"""
        records = db.query(orm_models.AICaiZhiJiaGe).filter(
            orm_models.AICaiZhiJiaGe.gsId == gsId,
            orm_models.AICaiZhiJiaGe.del_flag == False
        ).all()
        return {r.xbczId: float(r.czjg) for r in records if r.xbczId and r.czjg}

