import decimal
import traceback
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import and_, desc,func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, aliased

from app.models import orm_models
from app.models.orm_models import AIQuYuGongJia
from app.schemas.system_manage.QuYuGongJia_schema import QuYuGongJiaSearchResponse
from app.utils.exceptions import (
    NotFoundException, ValidationException, AppException, DataUpdateFailedException
)
from app.utils.snowflake_generator import SnowFlake


class QuYuGongJiaCRUD:
    """区域工价数据库操作类"""
    # ==========================================================================
    # 查询相关方法
    # ==========================================================================
    @staticmethod
    def get_by_id(
            db: Session,
            qygjId: int,
            include_deleted: bool = False
    ) -> Optional[QuYuGongJiaSearchResponse]:
        """
        根据ID获取区域工价（包含用户信息）

        Args:
            db: 数据库会话
            qygjId: 区域工价ID
            include_deleted: 是否包含已删除的记录

        Returns:
            区域工价的Pydantic模型或None
        """
        try:
            # 创建用户表的别名
            insert_user = aliased(orm_models.AIGongSiYongHu, name="insert_user")
            update_user = aliased(orm_models.AIGongSiYongHu, name="update_user")

            # 构建查询
            query = db.query(
                orm_models.AIQuYuGongJia,
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name')
            )

            # 左外连接创建用户表
            query = query.outerjoin(
                insert_user,
                orm_models.AIQuYuGongJia.in_userid == insert_user.gsyhId
            )

            # 左外连接更新用户表
            query = query.outerjoin(
                update_user,
                orm_models.AIQuYuGongJia.up_userid == update_user.gsyhId
            )

            # 预加载工种关系
            query = query.options(
                joinedload(orm_models.AIQuYuGongJia.xbgz)
            )

            # 根据ID过滤
            query = query.filter(orm_models.AIQuYuGongJia.qygjId == qygjId)

            if not include_deleted:
                query = query.filter(orm_models.AIQuYuGongJia.del_flag == False)

            # 执行查询（只调用一次）
            result = query.first()

            if not result:
                raise NotFoundException(
                    message="区域工价不存在",
                    details={"qygjId": qygjId}
                )

            # 解包结果
            record, insert_user_name, update_user_name = result

            # 检查是否已删除
            if not include_deleted and record.del_flag:
                raise NotFoundException(
                    message="区域工价已被删除",
                    details={"qygjId": qygjId}
                )

            # 构建字典
            item_dict = {
                "qygjId": record.qygjId,
                "dqbmId": record.dqbmId,
                "gongJia": record.gongJia if record.gongJia else 0,
                "xbgzId": record.xbgzId,
                "in_userid": record.in_userid,
                "in_time": record.in_time,
                "up_userid": record.up_userid,
                "up_time": record.up_time,
                "del_flag": record.del_flag,
                "GongZhong": record.xbgz.gongZhongMingCheng if record.xbgz else "无工种对应",
                "in_username": insert_user_name if insert_user_name else "无注册",
                "up_username": update_user_name if update_user_name else "无注册"
            }

            # 转换为Pydantic模型
            return QuYuGongJiaSearchResponse.parse_obj(item_dict)

        except ValidationException as e:
            raise
        except NotFoundException as e:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="查询区域工价操作失败",
                details={
                    "error": str(e),
                }
            )
    @staticmethod
    def search(
            db: Session,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 20,
            include_deleted: bool = False
    ) -> Tuple[List[dict], int]:
        """
        搜索区域工价（返回数据列表和总数，不执行分页）
        """
        try:
            # 创建用户表的别名
            insert_user = aliased(orm_models.AIGongSiYongHu, name="insert_user")
            update_user = aliased(orm_models.AIGongSiYongHu, name="update_user")

            # 创建地区编码表的别名
            di_qu = aliased(orm_models.AIDiQuBianMa, name="di_qu")
            # 创建上级地区表的别名
            di_qu_city = aliased(orm_models.AIDiQuBianMa, name="di_qu_city")  # 市级
            di_qu_province = aliased(orm_models.AIDiQuBianMa, name="di_qu_province")  # 省级

            # 构建查询
            query = db.query(
                orm_models.AIQuYuGongJia,
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name'),
                di_qu.diQuMingCheng.label('district_name'),  # 区/县级名称
                di_qu_city.diQuMingCheng.label('city_name'),  # 市级名称
                di_qu_province.diQuMingCheng.label('province_name')  # 省级名称
            )

            # 左外连接创建用户表
            query = query.outerjoin(
                insert_user,
                orm_models.AIQuYuGongJia.in_userid == insert_user.gsyhId
            )

            # 左外连接更新用户表
            query = query.outerjoin(
                update_user,
                orm_models.AIQuYuGongJia.up_userid == update_user.gsyhId
            )

            # 左外连接地区编码表，关联字段为dqbmId
            query = query.outerjoin(
                di_qu,
                orm_models.AIQuYuGongJia.dqbmId == di_qu.dqbmId
            )

            # 左外连接市级地区表 - 使用 SQL Server 的 SUBSTRING 函数
            # 市级编码是前4位 + '00'
            city_code = func.CONCAT(func.SUBSTRING(orm_models.AIQuYuGongJia.dqbmId, 1, 4), '00')
            query = query.outerjoin(
                di_qu_city,
                di_qu_city.dqbmId == city_code
            )

            # 左外连接省级地区表 - 使用 SQL Server 的 SUBSTRING 函数
            # 省级编码是前2位 + '0000'
            province_code = func.CONCAT(func.SUBSTRING(orm_models.AIQuYuGongJia.dqbmId, 1, 2), '0000')
            query = query.outerjoin(
                di_qu_province,
                di_qu_province.dqbmId == province_code
            )

            # 使用 joinedload 预加载工种关系
            query = query.options(
                joinedload(orm_models.AIQuYuGongJia.xbgz)
            )

            # 根据include_deleted参数决定是否包含已删除数据
            if not include_deleted:
                query = query.filter(orm_models.AIQuYuGongJia.del_flag == False)

            # 关键词搜索
            if keyword and keyword.strip():
                clean_keyword = keyword.strip()
                # 搜索区域编码、地区名称或工种名称
                query = query.filter(
                    (
                            orm_models.AIQuYuGongJia.dqbmId.like(f"{clean_keyword}%")
                    )
                )

            # 排序
            query = query.order_by(desc(orm_models.AIQuYuGongJia.up_time))

            # 获取总数
            total = query.count()

            # 分页
            offset = (page - 1) * page_size
            results = query.offset(offset).limit(page_size).all()

            # 转换为字典
            result_list = []
            for record, insert_user_name, update_user_name, district_name, city_name, province_name in results:
                # 清理和标准化地区名称
                province = province_name.strip() if province_name else ""
                city = city_name.strip() if city_name else ""
                district = district_name.strip() if district_name else ""

                # 构建完整的地区名称（去重处理）
                region_parts = []

                # 添加省级名称
                if province:
                    region_parts.append(province)

                # 添加市级名称（如果不为空且不与省级重复）
                if city and city != province:
                    region_parts.append(city)

                # 添加区/县级名称（如果不为空且不与市级重复）
                if district and district != city:
                    region_parts.append(district)

                # 生成最终的地区名称
                if region_parts:
                    # 使用"/"连接各级行政区名称
                    di_qu_ming_cheng = "".join(region_parts)
                elif province or city or district:
                    # 如果只有一个层级，直接使用
                    di_qu_ming_cheng = province or city or district
                else:
                    di_qu_ming_cheng = "无地区信息"

                item = {
                    "qygjId": record.qygjId,
                    "dqbmId": record.dqbmId,  # 只保留地区编码
                    "diQuMingCheng": di_qu_ming_cheng,  # 合并的省市区名称
                    "gongJia": record.gongJia if record.gongJia else 0,
                    "xbgzId": record.xbgzId,
                    "in_userid": record.in_userid,
                    "in_time": record.in_time,
                    "up_userid": record.up_userid,
                    "up_time": record.up_time,
                    "GongZhong": record.xbgz.gongZhongMingCheng if record.xbgz else "无工种对应",
                    "in_username": insert_user_name if insert_user_name else "无注册",
                    "up_username": update_user_name if update_user_name else "无注册",
                    "del_flag": record.del_flag
                }
                result_list.append(item)

            return result_list, total
        except AppException:
            raise
        except Exception as e:
            # 处理异常
            raise AppException(
                code=500,
                message="区域工价分页搜索操作异常",
                details={"error": str(e)}
            )
    @staticmethod
    def get_existing_by_record(
            db: Session,
            dqbmId: str,
            xbgzId: int,
            exclude_id: Optional[int] = None
    ) -> Optional[orm_models.AIQuYuGongJia]:
        """
        根据区域获取已存在的工价

        Args:
            db: 数据库会话
            dqbmId: 地区编码
            exclude_id: 要排除的ID

        Returns:
            已存在的区域编码对象或None
        """
        try:
            query = db.query(orm_models.AIQuYuGongJia).filter(
                and_(
                    orm_models.AIQuYuGongJia.dqbmId == dqbmId,
                    orm_models.AIQuYuGongJia.xbgzId == xbgzId
                )
            )

            if exclude_id:
                query = query.filter(orm_models.AIQuYuGongJia.qygjId != exclude_id)

            return query.first()

        except Exception as e:
            raise AppException(
                code=500,
                message="查询同地区工种工价操作失败",
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
            dqbmId: str,
            user_id: int,
            gongJia: decimal.Decimal,
            xbgzId: Optional[int] = None,
    ) -> orm_models.AIQuYuGongJia:
        """
        创建区域编码

        Args:
            db: 数据库会话
            dqbmId: 区域编码ID
            user_id: 用户ID
            gongJia: 工价
            xbgzId: 推荐工种ID

        Returns:
            创建的区域编码对象
        """
        try:
            gongZhong = db.query(orm_models.AIXiangBaoGongZhong).filter(
                orm_models.AIXiangBaoGongZhong.xbgzId == xbgzId,
                orm_models.AIXiangBaoGongZhong.del_flag == False
            ).first()
            if not gongZhong:
                raise ValidationException(
                    message="工种不存在或被删除",
                    details={"xbgzId": xbgzId}
                )
            current_time = datetime.now()

            new_quYuGongJia = orm_models.AIQuYuGongJia(
                qygjId=SnowFlake().generate_id(),
                dqbmId=dqbmId,
                gongJia=gongJia,
                xbgzId=xbgzId,
                in_userid=user_id,
                in_time=current_time,
                up_userid=user_id,
                up_time=current_time,
                del_flag=False,
            )

            db.add(new_quYuGongJia)
            db.flush()

            return new_quYuGongJia
        except AppException:
            raise
        except Exception as e:
            raise DataUpdateFailedException(
                message="创建区域编码操作失败",
                details={
                    "error": str(e),
                }
            )
    @staticmethod
    def update(
            db: Session,
            qygjId: int,
            gongJia: decimal.Decimal,
            update_data: Dict[str, Any],
            user_id: int
    ) -> orm_models.AIQuYuGongJia:
        """
        更新标准区域工价信息

        Args:
            db: 数据库会话
            qygjId: 区域工价ID
            update_data: 更新数据
            user_id: 用户ID

        Returns:
            更新后的区域工价对象
        """
        try:
            # 获取区域工价
            quYuGongJia = db.query(orm_models.AIQuYuGongJia).filter(
                and_(
                    orm_models.AIQuYuGongJia.qygjId == qygjId,
                    orm_models.AIQuYuGongJia.del_flag == False
                )
            ).first()

            if not quYuGongJia:
                raise NotFoundException(
                    message="区域工价不存在或已被删除",
                    details={"qygjId": qygjId}
                )
            gongZhong = db.query(orm_models.AIXiangBaoGongZhong).filter(
                    orm_models.AIXiangBaoGongZhong.xbgzId == update_data["xbgzId"],
                    orm_models.AIXiangBaoGongZhong.del_flag == False
            ).first()
            if not gongZhong:
                raise ValidationException(
                    message="工种不存在或被删除",
                    details={"xbgzId":update_data["xbgzId"]}
                )

            # 更新允许的字段
            allowed_fields = ['xbgzId', 'gongJia', 'dqbmId']
            for field in allowed_fields:
                if field in update_data:
                    setattr(quYuGongJia, field, update_data[field])

            # 更新操作信息
            quYuGongJia.up_userid = user_id
            quYuGongJia.up_time = datetime.now()

            db.flush()
            return quYuGongJia
        except NotFoundException as e:
            raise
        except ValidationException as e:
            raise

        except Exception as e:
            raise AppException(
                code=500,
                message="更新区域工价失败",
                details={
                    "error": str(e),
                    "qygjId": qygjId,
                    "user_id": user_id,
                    "gongJia": gongJia,
                    "update_data": update_data
                }
            )

    @staticmethod
    def restore(
            db: Session,
            qygjId: int,
            user_id: int
    ) -> bool:
        """
        恢复已删除的标准区域工价

        Args:
            db: 数据库会话
            qygjId: 区域工价ID
            user_id: 用户ID

        Returns:
            True如果恢复成功
        """
        try:
            biaoZhunGongXu = db.query(orm_models.AIQuYuGongJia).filter(
                and_(
                    orm_models.AIQuYuGongJia.qygjId == qygjId,
                    orm_models.AIQuYuGongJia.del_flag == True
                )
            ).first()

            if not biaoZhunGongXu:
                raise NotFoundException(
                    message="区域工价不存在或未被删除",
                    details={"qygjId": qygjId}
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
        except Exception as e:
            raise AppException(
                code=500,
                message="恢复区域工价操作失败",
                details={"error": str(e)}
            )
    @staticmethod
    def batch_delete(
            db: Session,
            qygjIds: List[int],
            user_id: int
) -> int:
        """
        批量软删除标准区域工价

        Args:
            db: 数据库会话
            qygjIds: 区域工价ID列表
            user_id: 用户ID

        Returns:
            删除结果统计
        """
        try:
            current_time = datetime.now()

            # 1. 先查询所有要删除的记录
            target_records = db.query(orm_models.AIQuYuGongJia).filter(
                AIQuYuGongJia.qygjId.in_(qygjIds)
            ).all()
            # 2. 检查是否存在
            if not target_records:
                # 所有ID都不存在
                raise ValidationException(
                    message="删除的区域工价不存在"
                )
            # 3. 分离已删除和未删除的记录
            already_deleted_ids = []
            to_delete_ids = []
            for record in target_records:
                if record.del_flag == True:
                    already_deleted_ids.append(record.qygjId)
                else:
                    to_delete_ids.append(record.qygjId)
            # 4. 检查是否有记录已被删除
            if already_deleted_ids:
                # 如果有部分记录已被删除，抛出异常
                raise ValidationException(
                    message=f"部分区域工价已被删除，无法重复删除，已删除的区域工价ID: {already_deleted_ids}"
                )
            # 5. 检查是否有不存在的ID（所有查询到的记录数小于传入的ID数）
            found_ids = [record.qygjId for record in target_records]
            not_found_ids = [id for id in qygjIds if id not in found_ids]
            if not_found_ids:
                raise ValidationException(
                    message=f"部分区域工价不存在，不存在的区域工价ID: {not_found_ids}"
                )
            # 6. 执行删除（更新del_flag为True）
            delete_count = db.query(orm_models.AIQuYuGongJia).filter(
                AIQuYuGongJia.qygjId.in_(to_delete_ids),
                AIQuYuGongJia.del_flag == False
            ).update(
                {
                    AIQuYuGongJia.del_flag: True,
                    AIQuYuGongJia.up_userid: user_id,
                    AIQuYuGongJia.up_time: current_time.replace(microsecond=0),
                    AIQuYuGongJia.del_time: current_time.replace(microsecond=0)
                },
                synchronize_session=False
            )
            # 7. 提交事务（假设db是Session对象）
            db.commit()
            return delete_count
        except ValidationException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="批量删除区域工价操作失败",
                details={"error": str(e)}
            )
    def get_quyu_gongjia_map(self, db: Session, dqbmId: str):
        """根据地区编码获取工价映射 (xbgzId -> gongJia)"""
        try:
            records = db.query(orm_models.AIQuYuGongJia).filter(
                orm_models.AIQuYuGongJia.dqbmId == dqbmId,
                orm_models.AIQuYuGongJia.del_flag == False
            ).all()
            return {
                rec.xbgzId: float(rec.gongJia) for rec in records
                if rec.xbgzId is not None and rec.gongJia is not None
            }
        except Exception as e:
            raise AppException(code=500, message="查询区域工价失败", details={"error": str(e)})

    
