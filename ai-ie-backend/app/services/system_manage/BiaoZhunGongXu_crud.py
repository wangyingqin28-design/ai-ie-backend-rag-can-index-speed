# app/service/system_manage/BiaoZhunGongXu_crud.py
import os
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import and_, desc, update
from sqlalchemy.orm import Session, aliased

from app.models import orm_models
from app.models.orm_models import AIBiaoZhunGongXu
from app.utils.exceptions import (
    NotFoundException, ValidationException, AppException, DataUpdateFailedException
)
from app.utils.snowflake_generator import SnowFlake

load_dotenv()
GETSOFT_ID_STR = os.getenv("GETSOFT_ID")
GETSOFT_ID = int(GETSOFT_ID_STR)

class BiaoZhunGongXuCRUD:
    """标准工序数据库操作类"""

    # ==========================================================================
    # 查询相关方法
    # ==========================================================================
    @staticmethod
    def get_by_id(
            db: Session,
            bzgxId: int,
            gsId: int,
    )-> type[AIBiaoZhunGongXu]:
        """
        根据ID获取标准工序（返回Pydantic模型）

        Args:
            db: 数据库会话
            bzgxId: 工序ID
        Returns:
            工序的Pydantic模型
        """
        try:
            if gsId == GETSOFT_ID:
                query = db.query(orm_models.AIBiaoZhunGongXu).filter(
                    orm_models.AIBiaoZhunGongXu.bzgxId == bzgxId,
                    orm_models.AIBiaoZhunGongXu.gsId == GETSOFT_ID,
                    orm_models.AIBiaoZhunGongXu.del_flag == False,
                ).first()
            else:
                query = db.query(orm_models.AIBiaoZhunGongXu).filter(
                    orm_models.AIBiaoZhunGongXu.gsId == gsId,
                    orm_models.AIBiaoZhunGongXu.bzgxId == bzgxId,
                    orm_models.AIBiaoZhunGongXu.del_flag == False,
                ).first()
            if query is None:
                raise NotFoundException(
                    message="未找到相关工序"
                )
            return query
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="查询工序失败,BiaoZhunGongXu_crud.get_by_id",
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
        搜索工序（返回数据列表和总数，不执行分页）
        """
        try:
            # 创建别名
            insert_user = aliased(orm_models.AIGongSiYongHu, name="insert_user")
            update_user = aliased(orm_models.AIGongSiYongHu, name="update_user")
            gongSi = aliased(orm_models.AIGongSi, name="gongSi")

                # 通用公司：查询所有，需要公司信息
            query = db.query(
                orm_models.AIBiaoZhunGongXu,
                orm_models.AIXiangBaoGongZhong.gongZhongMingCheng.label('gongzhong_name'),
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name'),
                gongSi.gongSiQuanCheng.label('gongsi_name')  # 添加公司名称
                ).filter(orm_models.AIBiaoZhunGongXu.del_flag == False)
            # 共通连接逻辑
            # 连接工种表
            query = query.outerjoin(
                orm_models.AIXiangBaoGongZhong,
                orm_models.AIBiaoZhunGongXu.xbgzId == orm_models.AIXiangBaoGongZhong.xbgzId
            )

            # 连接用户表
            query = query.outerjoin(
                insert_user,
                orm_models.AIBiaoZhunGongXu.in_userid == insert_user.gsyhId
            )
            query = query.outerjoin(
                update_user,
                orm_models.AIBiaoZhunGongXu.up_userid == update_user.gsyhId
            )

            # 只有通用公司才连接公司表
            query = query.outerjoin(
                    gongSi,
                    orm_models.AIBiaoZhunGongXu.gsId == gongSi.gsId
            )
            # 关键词搜索
            if keyword and keyword.strip():
                clean_keyword = keyword.strip()
                query = query.filter(
                    orm_models.AIBiaoZhunGongXu.gongXuMingCheng.ilike(f"%{clean_keyword}%")
                )
            # 排序
            query = query.order_by(desc(orm_models.AIBiaoZhunGongXu.up_time))
            # 获取总数
            total = query.count()
            # 分页
            offset = (page - 1) * page_size
            results = query.offset(offset).limit(page_size).all()
            # 转换为字典
            result_list = []
                # 通用公司：解包5个字段
            for record, gongzhong_name, insert_user_name, update_user_name, gongsi_name in results:
                item = {
                    "bzgxId": record.bzgxId,
                    "gongXuMingCheng": record.gongXuMingCheng,
                    "gongXuMiaoShu": record.gongXuMiaoShu or "",
                    "xbgzId": record.xbgzId,
                    "in_userid": record.in_userid,
                    "in_time": record.in_time,
                    "up_userid": record.up_userid,
                    "up_time": record.up_time,
                    "GongZhong": gongzhong_name or "无工种",
                    "in_username": insert_user_name or "无注册",
                    "up_username": update_user_name or "无注册",
                    "gongSi": gongsi_name or "公司未注册",
                    "gsId":record.gsId,
                }
                result_list.append(item)
            return result_list, total
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="查询工序失败,BiaoZhunGongXu_crud.search",
                details={"error": str(e)}
            )
    @staticmethod
    def search_user(
            db:Session,
            gsId:int,
            keyword:Optional[str] ,
            page:int,
            page_size:int,
    ) -> Tuple[List[dict], int]:
        try:
            # 创建别名
            insert_user = aliased(orm_models.AIGongSiYongHu, name="insert_user")
            update_user = aliased(orm_models.AIGongSiYongHu, name="update_user")
            query = db.query(
                orm_models.AIBiaoZhunGongXu,
                orm_models.AIXiangBaoGongZhong.gongZhongMingCheng.label('gongzhong_name'),
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name'),
                ).filter(orm_models.AIBiaoZhunGongXu.del_flag == False,
                         orm_models.AIBiaoZhunGongXu.gsId==gsId,
                         )
            if query is None:
                logger.info(f'查询没数据')
            # 共通连接逻辑
            # 连接工种表
            query = query.outerjoin(
                orm_models.AIXiangBaoGongZhong,
                and_(
                orm_models.AIBiaoZhunGongXu.xbgzId == orm_models.AIXiangBaoGongZhong.xbgzId,
                orm_models.AIXiangBaoGongZhong.gsId == gsId,
                )

            )

            # 连接用户表
            query = query.outerjoin(
                insert_user,
                and_(
                orm_models.AIBiaoZhunGongXu.in_userid == insert_user.gsyhId,
                insert_user.gsId == gsId
                )
            )
            query = query.outerjoin(
                update_user,
                and_(
                orm_models.AIBiaoZhunGongXu.up_userid == update_user.gsyhId,
                update_user.gsId == gsId
                )
            )
            # 关键词搜索
            if keyword and keyword.strip():
                clean_keyword = keyword.strip()
                query = query.filter(
                    orm_models.AIBiaoZhunGongXu.gongXuMingCheng.ilike(f"%{clean_keyword}%")
                )
            # 排序
            query = query.order_by(desc(orm_models.AIBiaoZhunGongXu.up_time))
            # 获取总数
            total = query.count()
            # 分页
            offset = (page - 1) * page_size
            results = query.offset(offset).limit(page_size).all()
            # 转换为字典
            result_list = []
            for record, gongzhong_name, insert_user_name, update_user_name, in results:
                item = {
                    "bzgxId": record.bzgxId,
                    "gongXuMingCheng": record.gongXuMingCheng,
                    "gongXuMiaoShu": record.gongXuMiaoShu or "",
                    "xbgzId": record.xbgzId,
                    "in_userid": record.in_userid,
                    "in_time": record.in_time,
                    "up_userid": record.up_userid,
                    "up_time": record.up_time,
                    "GongZhong": gongzhong_name or "无工种",
                    "in_username": insert_user_name or "无注册",
                    "up_username": update_user_name or "无注册",
                }
                result_list.append(item)
            return result_list, total
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="查询工序失败,BiaoZhunGongXu_crud.search",
                details={"error": str(e)}
            )


    @staticmethod
    def get_existing_by_name(
            db: Session,
            gongXuMingCheng: str,
            gsId:int,
            exclude_id: Optional[int] = None
    ) -> Optional[orm_models.AIBiaoZhunGongXu]:
        """
        根据名称获取已存在的工序

        Args:
            db: 数据库会话
            gongXuMingCheng: 工序名称
            exclude_id: 要排除的ID

        Returns:
            已存在的工序对象或None
        """
        try:
            if gsId != GETSOFT_ID:
                query = db.query(orm_models.AIBiaoZhunGongXu).filter(
                    and_(
                        orm_models.AIBiaoZhunGongXu.gongXuMingCheng == gongXuMingCheng,
                        orm_models.AIBiaoZhunGongXu.gsId == gsId
                    )
                )
            else:
                query = db.query(orm_models.AIBiaoZhunGongXu).filter(
                    orm_models.AIBiaoZhunGongXu.gongXuMingCheng == gongXuMingCheng,
                    orm_models.AIBiaoZhunGongXu.gsId == GETSOFT_ID
                )

            if exclude_id:
                query = query.filter(orm_models.AIBiaoZhunGongXu.bzgxId != exclude_id)

            return query.first()
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="查询同名工序失败,BiaoZhunGongXu_crud.get_existing_by_name",
                details={
                    "error": str(e),
                    "gongXuMingCheng": gongXuMingCheng,
                }
            )

    # ==========================================================================
    # 创建、更新、删除方法
    # ==========================================================================

    @staticmethod
    def create(
            db: Session,
            gongXuMingCheng: str,
            user_id: int,
            gsId: int,
            gongXuMiaoShu: Optional[str] = None,
            xbgzId: Optional[int] = None,
    ) -> orm_models.AIBiaoZhunGongXu:
        """
        创建标准工序

        Args:
            db: 数据库会话
            gongXuMingCheng: 工序名称
            user_id: 用户ID
            gongXuMiaoShu: 工序描述
            xbgzId: 推荐工种ID
            extra_fields: 其他字段

        Returns:
            创建的工序对象
        """
        try:
            if gsId == GETSOFT_ID:
                gongZhong = db.query(orm_models.AIXiangBaoGongZhong).filter(
                        orm_models.AIXiangBaoGongZhong.xbgzId == xbgzId,
                        orm_models.AIXiangBaoGongZhong.del_flag == False
                ).first()
            else:
                gongZhong =db.query(orm_models.AIXiangBaoGongZhong).filter(
                orm_models.AIBiaoZhunGongXu.xbgzId == xbgzId,
                orm_models.AIXiangBaoGongZhong.del_flag == False,
                orm_models.AIXiangBaoGongZhong.gsId == gsId,
            )
            if not gongZhong:
                raise ValidationException(
                    message="工种不存在或被删除",
                    details={"xbgzId":xbgzId}
                )
            current_time = datetime.now()

            new_biaoZhunGongXu = orm_models.AIBiaoZhunGongXu(
                bzgxId=SnowFlake().generate_id(),
                gongXuMingCheng=gongXuMingCheng,
                gongXuMiaoShu=gongXuMiaoShu,
                xbgzId=xbgzId,
                in_userid=user_id,
                in_time=current_time,
                up_userid=user_id,
                up_time=current_time,
                del_flag=False,
                gsId=gsId,
            )

            db.add(new_biaoZhunGongXu)
            db.flush()

            return new_biaoZhunGongXu
        except AppException:
            raise
        except Exception as e:
            raise DataUpdateFailedException(
                message="创建工序失败,BiaoZhunGongXu_crud.create",
                details={
                    "error": str(e)
                }
            )

    @staticmethod
    def update(
            db: Session,
            gsId: int,
            update_dict: Dict[str, Any],
    ) -> orm_models.AIBiaoZhunGongXu:
        """
        更新标准工序信息

        Args:
            db: 数据库会话
            bzgxId: 工序ID
            update_data: 更新数据
            user_id: 用户ID

        Returns:
            更新后的工序对象
        """
        try:
            if gsId == GETSOFT_ID:
                # 通用公司可以查询所有工序
                query_filter = and_(
                    orm_models.AIBiaoZhunGongXu.bzgxId == update_dict['bzgxId'],
                    orm_models.AIBiaoZhunGongXu.del_flag == False
                )
            else:
                # 非通用公司：不能操作通用公司的工序
                query_filter = and_(
                    orm_models.AIBiaoZhunGongXu.bzgxId == update_dict['bzgxId'],
                    orm_models.AIBiaoZhunGongXu.del_flag == False,
                    orm_models.AIBiaoZhunGongXu.gsId == gsId  # 只查询本公司的
                )

            biaoZhunGongXu = db.query(orm_models.AIBiaoZhunGongXu).filter(query_filter).first()

            if not biaoZhunGongXu:
                raise NotFoundException(
                    message="工序不存在或已被删除",
                    details={"bzgxId": update_dict['bzgxId']}
                )
            # 单独处理xbgzId，因为它是选填，且需要验证

            if 'xbgzId' in update_dict:
                xbgzId = update_dict.pop('xbgzId')
                # 从update_data中取出，并删除，这样后面的更新循环就不会处理它了
                # 如果xbgzId是空字符串或None，则清空
                if xbgzId is None or xbgzId == "":
                    biaoZhunGongXu.xbgzId = None
                else:
                    # 验证工种是否存在
                    gongZhong = db.query(orm_models.AIXiangBaoGongZhong).filter(
                        orm_models.AIXiangBaoGongZhong.xbgzId == xbgzId,
                        orm_models.AIXiangBaoGongZhong.del_flag == False
                    ).first()
                    if not gongZhong:
                        raise ValidationException(
                            message="工种不存在或被删除",
                        )
                    biaoZhunGongXu.xbgzId = xbgzId

            # 更新允许的字段（此时update_data中已经没有xbgzId了）
            allowed_fields = ['gongXuMingCheng', 'gongXuMiaoShu']  # 注意：这里去掉了xbgzId
            for field in allowed_fields:
                if field in update_dict:
                    setattr(biaoZhunGongXu, field, update_dict[field])

            # 更新操作信息
            biaoZhunGongXu.up_userid = update_dict['up_userid']  # 注意：这里使用字典方式访问
            biaoZhunGongXu.up_time = datetime.now()

            db.flush()
            return biaoZhunGongXu
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="更新工序失败",
                details={
                    "error": str(e),
                }
            )

    @staticmethod
    def restore(
            db: Session,
            bzgxId: int,
            user_id: int,
            gsId:int
    ) -> bool:
        """
        恢复已删除的标准工序

        Args:
            db: 数据库会话
            bzgxId: 工序ID
            user_id: 用户ID

        Returns:
            True如果恢复成功
            """

        try:
            # 准备更新的数据 - 键必须是 ORM 模型的列对象，而不是字符串
            update_data = {
                orm_models.AIBiaoZhunGongXu.del_flag: False,
                orm_models.AIBiaoZhunGongXu.up_userid: user_id,
                orm_models.AIBiaoZhunGongXu.del_time: None,
                orm_models.AIBiaoZhunGongXu.up_time: datetime.now().replace(microsecond=0)
            }

            if gsId == GETSOFT_ID:
                stmt = update(orm_models.AIBiaoZhunGongXu).where(
                    and_(
                        orm_models.AIBiaoZhunGongXu.bzgxId == bzgxId,
                        orm_models.AIBiaoZhunGongXu.del_flag == True
                    )
                ).values(update_data)  # 直接传入字典，不要使用 ** 解包
            else:
                stmt = update(orm_models.AIBiaoZhunGongXu).where(
                    and_(
                        orm_models.AIBiaoZhunGongXu.bzgxId == bzgxId,
                        orm_models.AIBiaoZhunGongXu.del_flag == True,
                        orm_models.AIBiaoZhunGongXu.gsId == gsId
                    )
                ).values(update_data)  # 直接传入字典，不要使用 ** 解包

            result = db.execute(stmt)

            if result.rowcount == 0:
                raise NotFoundException(
                    message="工序不存在或未被删除 (更新时未找到符合条件的记录)",
                    details={"bzgxId": bzgxId}
                )

            return True
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="恢复工序失败",
                details={"error": str(e), "bzgxId": bzgxId}
            )

    @staticmethod
    def batch_delete(
            db: Session,
            bzgxIds: List[int],
            user_id: int,
            gsId: int
) -> int:
        """
        批量软删除标准工序

        Args:
            db: 数据库会话
            bzgxIds: 工序ID列表
            user_id: 用户ID

        Returns:
            删除结果统计
        """
        try:
            current_time = datetime.now()

            # 1. 先查询所有要删除的记录
            if gsId == GETSOFT_ID:
                target_records = db.query(orm_models.AIBiaoZhunGongXu).filter(
                    AIBiaoZhunGongXu.bzgxId.in_(bzgxIds),
                    AIBiaoZhunGongXu.del_flag == False
                ).all()
            else:
                target_records = db.query(orm_models.AIBiaoZhunGongXu).filter(
                    AIBiaoZhunGongXu.bzgxId.in_(bzgxIds),
                    AIBiaoZhunGongXu.del_flag == False,
                    AIBiaoZhunGongXu.gsId == gsId
                ).all()
            # 2. 检查是否存在
            if not target_records:
                # 所有ID都不存在
                raise ValidationException(
                    message="删除的工序中不存在"
                )
            # 3. 分离已删除和未删除的记录
            already_deleted_ids = []
            to_delete_ids = []
            for record in target_records:
                if record.del_flag == True:
                    already_deleted_ids.append(record.bzgxId)
                else:
                    to_delete_ids.append(record.bzgxId)
            # 4. 检查是否有记录已被删除
            if already_deleted_ids:
                # 如果有部分记录已被删除，抛出异常
                raise ValidationException(
                    message=f"部分工序已被删除，无法重复删除，已删除的工序ID: {already_deleted_ids}"
                )
            # 5. 检查是否有不存在的ID（所有查询到的记录数小于传入的ID数）
            found_ids = [record.bzgxId for record in target_records]
            not_found_ids = [id for id in bzgxIds if id not in found_ids]
            if not_found_ids:
                raise ValidationException(
                    message=f"部分工序不存在，不存在的工序ID: {not_found_ids}"
                )
            # 6. 执行删除（更新del_flag为True）
            delete_count = db.query(orm_models.AIBiaoZhunGongXu).filter(
                AIBiaoZhunGongXu.bzgxId.in_(to_delete_ids),
                AIBiaoZhunGongXu.del_flag == False,
                AIBiaoZhunGongXu.gsId == gsId
            ).update(
                {
                    AIBiaoZhunGongXu.del_flag: True,
                    AIBiaoZhunGongXu.up_userid: user_id,
                    AIBiaoZhunGongXu.up_time: current_time.replace(microsecond=0),
                    AIBiaoZhunGongXu.del_time: current_time.replace(microsecond=0)
                },
                synchronize_session=False
            )
            # 7. 提交事务（假设db是Session对象）
            db.flush()
            return delete_count
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="批量删除工序失败：BiaoZhunGongXu_crud.batch_delete",
                details={"error": str(e)}
            )