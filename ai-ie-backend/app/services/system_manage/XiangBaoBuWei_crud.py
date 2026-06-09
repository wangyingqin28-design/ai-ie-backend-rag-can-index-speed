## app/service/system_manage/XiangBaoBuWei_crud.py
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from app.services.system_manage.BiaoZhunGongXu_service import GETSOFT_ID
from app.utils.redis.redis_sync_client import redis_delete_sync
from loguru import logger
import redis
from sqlalchemy import and_, desc, update
from sqlalchemy.orm import Session,aliased
from app.models import orm_models
from app.models.orm_models import AIXiangBaoBuWei
from app.schemas.system_manage.XiangBaoBuWei_schema import XiangBaoBuWeiSearchResponse, XiangBaoBuWeiGetSearchResponse
from app.utils.exceptions import (
    NotFoundException, ValidationException, AppException, DataUpdateFailedException,
)
from app.utils.snowflake_generator import SnowFlake
# 导入Redis相关方法和常量
from app.utils.redis.redis_sync_client import (
    redis_get_sync,
    redis_set_sync
)
from app.utils.redis.redis_utils import PAGE_DROPDOWN


class XiangBaoBuWeiCRUD:
    """部位数据库操作类"""
    #=====================================================
    @staticmethod
    def get_by_id(
            db: Session,
            gsId:int,
            xbbwId: int,
            include_deleted: bool = False,
    ) -> Optional[XiangBaoBuWeiSearchResponse]:
        """
        根据ID获取部位（包含用户信息）

        Args:
            db: 数据库会话
            xbbwId: 部位ID
            include_deleted: 是否包含已删除的记录

        Returns:
            部位的Pydantic模型或None
        """
        try:
            if gsId == GETSOFT_ID:
                logger.info('本公司查询单条数据')
                query = db.query(orm_models.AIXiangBaoBuWei).filter(
                    orm_models.AIXiangBaoBuWei.xbbwId == xbbwId,
                ).first()
            else:
                logger.info('其他公司单条查询')
                query = db.query(orm_models.AIXiangBaoBuWei).filter(
                    orm_models.AIXiangBaoBuWei.gsId == gsId,
                    orm_models.AIXiangBaoBuWei.xbbwId == xbbwId,
                ).first()
            if query is None:
                raise NotFoundException(
                    message="箱包部位数据为空"
                )

            return query
        except ValidationException:
            raise
        except NotFoundException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="查询部位操作失败",
                details={
                    "error": str(e),
                }
            )
    @staticmethod
    def search_user(
            db: Session,
            gsId:int,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 20,
    ) -> Tuple[List[XiangBaoBuWeiSearchResponse], int]:
        """
        搜索部位（返回数据列表和总数，不执行分页）
        """
        try:
            # 创建用户表的别名
            insert_user = aliased(orm_models.AIGongSiYongHu, name="insert_user")
            update_user = aliased(orm_models.AIGongSiYongHu, name="update_user")

            # 构建查询
            query = db.query(
                orm_models.AIXiangBaoBuWei,
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name'),
            )

            # 左外连接创建用户表
            query = query.outerjoin(
                insert_user,
                orm_models.AIXiangBaoBuWei.in_userid == insert_user.gsyhId
            )

            # 左外连接更新用户表
            query = query.outerjoin(
                update_user,
                orm_models.AIXiangBaoBuWei.up_userid == update_user.gsyhId
            )

            query = query.filter(
                orm_models.AIXiangBaoBuWei.del_flag == False,
                orm_models.AIXiangBaoBuWei.gsId == gsId,
            )

            # 关键词搜索
            if keyword and keyword.strip():
                clean_keyword = keyword.strip()
                query = query.filter(
                    orm_models.AIXiangBaoBuWei.buWeiMingCheng.like(f"%{clean_keyword}%")
                )

            # 排序
            query = query.order_by(desc(orm_models.AIXiangBaoBuWei.up_time))

            # 获取总数
            total = query.count()

            # 分页
            offset = (page - 1) * page_size
            results = query.offset(offset).limit(page_size).all()

            # 转换为字典列表，然后转换为Pydantic模型
            result_list = []
            for record, insert_user_name, update_user_name in results:
                # 构建字典
                item_dict = {
                    "xbbwId": record.xbbwId,
                    "buWeiMingCheng": record.buWeiMingCheng,
                    "in_userid": record.in_userid,
                    "in_time": record.in_time,
                    "up_userid": record.up_userid,
                    "up_time": record.up_time,
                    "del_flag": record.del_flag,
                    "in_username": insert_user_name if insert_user_name else "无注册",
                    "up_username": update_user_name if update_user_name else "无注册"
                }
                # 转换为Pydantic模型
                item_model = XiangBaoBuWeiSearchResponse.parse_obj(item_dict)
                result_list.append(item_model)

            return result_list, total

        except Exception as e:
            raise AppException(
                code=500,
                message="查询部位操作失败",
                details={
                    "error": str(e),
                }
            )
    @staticmethod
    def search_admin(
            db: Session,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 20,
    ) -> Tuple[List[XiangBaoBuWeiSearchResponse], int]:
        """
        搜索部位（返回数据列表和总数，不执行分页）
        """
        try:
            # 创建用户表的别名
            insert_user = aliased(orm_models.AIGongSiYongHu, name="insert_user")
            update_user = aliased(orm_models.AIGongSiYongHu, name="update_user")
            gongSi = aliased(orm_models.AIGongSi,name='gongSi')

            # 构建查询
            query = db.query(
                orm_models.AIXiangBaoBuWei,
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name'),
                gongSi.gongSiQuanCheng.label('gongSi_name'),
            )

            # 左外连接创建用户表
            query = query.outerjoin(
                insert_user,
                orm_models.AIXiangBaoBuWei.in_userid == insert_user.gsyhId
            )

            # 左外连接更新用户表
            query = query.outerjoin(
                update_user,
                orm_models.AIXiangBaoBuWei.up_userid == update_user.gsyhId
            )
            query = query.outerjoin(
                gongSi,
                orm_models.AIXiangBaoBuWei.gsId == gongSi.gsId
            )

            query = query.filter(
                orm_models.AIXiangBaoBuWei.del_flag == False,
            )

            # 关键词搜索
            if keyword and keyword.strip():
                clean_keyword = keyword.strip()
                query = query.filter(
                    orm_models.AIXiangBaoBuWei.buWeiMingCheng.like(f"%{clean_keyword}%")
                )

            # 排序
            query = query.order_by(desc(orm_models.AIXiangBaoBuWei.up_time))

            # 获取总数
            total = query.count()

            # 分页
            offset = (page - 1) * page_size
            results = query.offset(offset).limit(page_size).all()

            # 转换为字典列表，然后转换为Pydantic模型
            result_list = []
            for record, insert_user_name, update_user_name,gongSi_name in results:
                # 构建字典
                item_dict = {
                    "xbbwId": record.xbbwId,
                    "buWeiMingCheng": record.buWeiMingCheng,
                    "in_userid": record.in_userid,
                    "in_time": record.in_time,
                    "up_userid": record.up_userid,
                    "up_time": record.up_time,
                    "del_flag": record.del_flag,
                    "in_username": insert_user_name if insert_user_name else "无注册",
                    "up_username": update_user_name if update_user_name else "无注册",
                    "gongSi": gongSi_name if gongSi_name else "公司无注册",
                }
                # 转换为Pydantic模型
                item_model = XiangBaoBuWeiGetSearchResponse.parse_obj(item_dict)
                result_list.append(item_model)

            return result_list, total

        except Exception as e:
            raise AppException(
                code=500,
                message="查询部位操作失败",
                details={
                    "error": str(e),
                }
            )
    @classmethod
    def check_name_exist(
            db: Session,
            gsId:int,
            buWeiMingCheng: str,
            exclude_id: Optional[int] = None
    ) -> bool:
        """
        检查部位名称是否已存在

        Args:
            db: 数据库会话
            buWeiMingCheng: 部位名称
            exclude_id: 要排除的ID（用于更新时检查）

        Returns:
            True如果名称已存在，否则False
        """
        try:
            query = db.query(orm_models.AIXiangBaoBuWei).filter(
                and_(
                    orm_models.AIXiangBaoBuWei.buWeiMingCheng == buWeiMingCheng,
                    orm_models.AIXiangBaoBuWei.gsId == gsId,
                )
            )
            if exclude_id:
                query = query.filter(orm_models.AIXiangBaoBuWei.xbbwId == exclude_id)

            return query.first() is not None

        except Exception as e:
            raise DataUpdateFailedException(
                message="检查部位名称失败，XiangBaoBuWei_crud.check_name_exist",
                details={
                    "error": str(e),
                    "buWeiMingCheng": buWeiMingCheng,
                }
            )

    @staticmethod
    def get_existing_by_name(
            db: Session,
            gsId:int,
            buWeiMingCheng: str,
            exclude_id: Optional[int] = None
    ) -> Optional[orm_models.AIXiangBaoBuWei]:
        """
        根据名称获取已存在的部位

        Args:
            db: 数据库会话
            buWeiMingCheng: 部位名称
            exclude_id: 要排除的ID

        Returns:
            已存在的部位对象或None
        """
        try:
            query = db.query(orm_models.AIXiangBaoBuWei).filter(
                    orm_models.AIXiangBaoBuWei.buWeiMingCheng == buWeiMingCheng,
                    orm_models.AIXiangBaoBuWei.gsId == gsId,

            )

            if exclude_id:
                query = query.filter(orm_models.AIXiangBaoBuWei.xbbwId != exclude_id)

            return query.first()
        except Exception as e:
            raise DataUpdateFailedException(
                message="查询同名部位失败，XiangBaoBuWei_crud.get_existing_by_name",
                details={"error": str(e),"buWeiMingCheng":buWeiMingCheng, "exclude_id": exclude_id}
            )


    # ==========================================================================
    # 创建、更新、删除方法
    # ==========================================================================

    @staticmethod
    def create(
            db: Session,
            buWeiMingCheng: str,
            user_id:int,
            gsId:int,
    ) -> orm_models.AIXiangBaoBuWei:
        """
        创建标准部位

        Args:
            db: 数据库会话
            buWeiMingCheng: 部位名称
            user_id: 用户ID
        Returns:
            创建的部位对象
        """
        try:
            new_xiangBaoBuWei = orm_models.AIXiangBaoBuWei(
                xbbwId=SnowFlake().generate_id(),
                buWeiMingCheng=buWeiMingCheng,
                in_userid=user_id,
                up_userid=user_id,
                del_flag=False,
                in_time=datetime.now(),
                up_time=datetime.now(),
                gsId=gsId,
            )
            db.add(new_xiangBaoBuWei)
            db.flush()
            XiangBaoBuWeiCRUD.refresh_search_all_cache(gsId)
            return new_xiangBaoBuWei
        except Exception as e:
            raise DataUpdateFailedException(
                message="创建部位失败XiangBaoBuWei_crud.create",
                details={"error":str(e),"buWeiMingCheng":buWeiMingCheng, "user_id":user_id}
            )
    @staticmethod
    def update(
        db: Session,
        xbbwId: int,
        update_data:Dict[str,Any],
        user_id:int,
        gsId:int,
        ) -> orm_models.AIXiangBaoBuWei:
        """
        更新部位信息

        Args:
            db: 数据库会话
            xbbwId: 部位ID
            update_data: 更新数据
            user_id: 用户ID

        Returns:
            更新后的部位对象
        """
        try:
            # 获取部位
            xiangbaoBuWei = db.query(orm_models.AIXiangBaoBuWei).filter(
                and_(
                    orm_models.AIXiangBaoBuWei.xbbwId == xbbwId,
                    orm_models.AIXiangBaoBuWei.del_flag == False,
                    orm_models.AIXiangBaoBuWei.gsId == gsId,
                )
            ).first()

            if not xiangbaoBuWei:
                raise NotFoundException(
                    message="部位不存在或已被删除",
                    details={"xbbwId": xbbwId}
                )

            # 更新允许的字段
            allowed_fields = ['buWeiMingCheng']
            for field in allowed_fields:
                if field in update_data:
                    setattr(xiangbaoBuWei, field, update_data[field])

            # 更新操作信息
            xiangbaoBuWei.up_userid = user_id
            xiangbaoBuWei.up_time = datetime.now()

            db.flush()
            XiangBaoBuWeiCRUD.refresh_search_all_cache(gsId)
            return xiangbaoBuWei
        except ValidationException:
            raise
        except NotFoundException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="更新部位失败",
                details={
                    "error": str(e),
                }
            )

    @staticmethod
    def restore(
            db: Session,
            xbbwId: int,
            user_id: int,
            gsId: int,
    ) -> bool:
        """
        恢复已删除的部位
        """
        try:
            # 构建基础过滤条件
            filter_conditions = [
                orm_models.AIXiangBaoBuWei.xbbwId == xbbwId,
                orm_models.AIXiangBaoBuWei.del_flag == True
            ]

            # 如果不是 GETSOFT_ID，添加 gsId 条件
            if gsId != GETSOFT_ID:
                filter_conditions.append(orm_models.AIXiangBaoBuWei.gsId == gsId)

            # 直接使用 update 语句
            update_stmt = (
                update(orm_models.AIXiangBaoBuWei)
                .where(and_(*filter_conditions))
                .values(
                    del_flag=False,
                    up_userid=user_id,
                    del_time=None,
                    up_time=datetime.now()
                )
            )

            result = db.execute(update_stmt)
            db.flush()

            if result.rowcount == 0:
                raise NotFoundException(
                    message="部位不存在或未被删除",
                    details={"xbbwId": xbbwId, "gsId": gsId}
                )

            XiangBaoBuWeiCRUD.refresh_search_all_cache(gsId)
            return True
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="恢复部位操作失败",
                details={"error": str(e)}
            )
    @staticmethod
    def batch_delete(
            db: Session,
            xbbwIds:List[int],
            user_id:int,
            gsId:int,
    ) -> int:
        """
        批量软删除部位

        Args:
            db: 数据库会话
            xbbwIds: 部位ID列表
            user_id: 用户ID

        Returns:
            删除结果统计
        """
        try:
            if gsId == GETSOFT_ID:
                target_records=db.query(orm_models.AIXiangBaoBuWei).filter(
                    AIXiangBaoBuWei.xbbwId.in_(xbbwIds)
                ).all()
            else:
                target_records=db.query(orm_models.AIXiangBaoBuWei).filter(
                    AIXiangBaoBuWei.xbbwId.in_(xbbwIds),
                    AIXiangBaoBuWei.gsId == gsId,
                ).all()
            if not target_records:
                raise NotFoundException(
                    message="删除的部位不存在"
                )


            #分离已删除和未删除的记录
            already_deleted_ids = []
            to_delete_ids = []
            for record in target_records:
                if record.del_flag == True:
                    already_deleted_ids.append(record.xbbwId)
                else:
                    to_delete_ids.append(record.xbbwId)
            # 4. 检查是否有记录已被删除
            if already_deleted_ids:
                # 如果有部分记录已被删除，抛出异常
                raise ValidationException(
                    message=f"部分部位已被删除，无法重复删除，已删除的部位ID: {already_deleted_ids}"
                )
            # 5. 检查是否有不存在的ID（所有查询到的记录数小于传入的ID数）
            found_ids = [record.xbbwId for record in target_records]
            not_found_ids = [id for id in xbbwIds if id not in found_ids]
            if not_found_ids:
                raise ValidationException(
                    message=f"部分部位不存在，不存在的部位ID: {not_found_ids}"
                )
            # 6. 执行删除（更新del_flag为True）
            delete_count = db.query(orm_models.AIXiangBaoBuWei).filter(
                AIXiangBaoBuWei.xbbwId.in_(to_delete_ids),
                AIXiangBaoBuWei.del_flag == False
            ).update(
                {
                    AIXiangBaoBuWei.del_flag: True,
                    AIXiangBaoBuWei.up_userid: user_id,
                    AIXiangBaoBuWei.up_time: datetime.now().replace(microsecond=0),
                    AIXiangBaoBuWei.del_time: datetime.now().replace(microsecond=0)
                },
                synchronize_session=False
            )
            # 7. 提交事务（假设db是Session对象）
            db.commit()
            XiangBaoBuWeiCRUD.refresh_search_all_cache(gsId)
            return delete_count
        except AppException:
            # 重新抛出ValidationException，不需要包装
            raise
        except Exception as e:
            raise DataUpdateFailedException(
                message="批量删除部位失败：XiangbaoBuWei_crud.batch_delete",
                details={"error": str(e), "xbbwIds": xbbwIds}
            )

    @staticmethod
    def search_all(
            db: Session,
            gsId:int,
            keywords: Optional[str] = None  # 可选关键词参数，兼容原有调用
    ) -> List[Dict[str, Any]]:
        # 1. 关键词预处理：去空格、空字符串转None，避免无效过滤
        keywords = keywords.strip() if (keywords and isinstance(keywords, str)) else None
        # 定义最终返回的数据集
        result_data = []
        CACHE_KEY_XBBW_SEARCH_ALL = f"sys:gsId:{gsId}:AIXiangBaoBuWei"
        CACHE_EXPIRE_SECONDS = 3600  # 统一1小时过期，和其他下拉栏保持一致

        # 2. 优先从Redis获取全量缓存数据（核心：无论是否有搜索词，都先取缓存）
        try:

            cache_all_data = redis_get_sync(CACHE_KEY_XBBW_SEARCH_ALL, db=PAGE_DROPDOWN)
            if cache_all_data is not None and isinstance(cache_all_data, list):
                logger.debug(f"部位下拉栏：Redis缓存命中，全量数据共{len(cache_all_data)}条")
                # 2.1 无关键词：直接返回Redis全量数据
                if not keywords:
                    result_data = cache_all_data
                # 2.2 有关键词：在内存中对Redis全量数据做模糊过滤（核心优化）
                else:
                    result_data = [
                        item for item in cache_all_data
                        if keywords in item.get("buWeiMingCheng", "")  # 按部位名称模糊匹配
                    ]
                logger.debug(f"部位下拉栏：Redis缓存内存过滤完成，关键词[{keywords}]，匹配结果{len(result_data)}条")
                # 缓存命中+内存过滤完成，直接返回（无需走数据库）
                return result_data
        except redis.RedisError as e:
            logger.warning(f"部位下拉栏：Redis缓存读取失败，降级为数据库查询 | error={str(e)}")
        except Exception as e:
            logger.warning(f"部位下拉栏：Redis缓存解析失败，降级为数据库查询 | error={str(e)}")

        # 3. Redis缓存失效/故障 → 降级到数据库处理（全查后内存过滤，保持逻辑一致性）
        try:
            # 3.1 数据库全查（仅查一次，避免多次数据库操作）
            querys = db.query(orm_models.AIXiangBaoBuWei).filter(
                orm_models.AIXiangBaoBuWei.del_flag == False,
                orm_models.AIXiangBaoBuWei.gsId==gsId
            ).all()
            db_all_data = []
            for query in querys:
                db_all_data.append({
                    "xbbwId": query.xbbwId,
                    "buWeiMingCheng": query.buWeiMingCheng
                })
            logger.debug(f"部位下拉栏：数据库全查成功，共{len(db_all_data)}条")
            if not keywords:
                try:
                    redis_set_sync(
                        key=CACHE_KEY_XBBW_SEARCH_ALL,
                        value=db_all_data,
                        ex=CACHE_EXPIRE_SECONDS,
                        db=PAGE_DROPDOWN
                    )
                    logger.debug("部位下拉栏：数据库全量数据写入Redis缓存成功")
                except redis.RedisError as e:
                    logger.warning(f"部位下拉栏：写入Redis缓存失败 | error={str(e)}")

            # 3.3 对数据库全查结果做内存过滤（和Redis侧逻辑完全一致）
            if not keywords:
                result_data = db_all_data
            else:
                result_data = [
                    item for item in db_all_data
                    if keywords in item.get("buWeiMingCheng", "")
                ]
            logger.debug(f"部位下拉栏：数据库全查后内存过滤完成，关键词[{keywords}]，匹配结果{len(result_data)}条")

            return result_data
        except Exception as e:
            # 异常信息差异化，包含关键词，方便排查
            msg = f"按关键词[{keywords}]模糊查询部位失败" if keywords else "查询部位全量数据失败"
            raise DataUpdateFailedException(
                message=f"{msg},XiangBaoBuWei_crud.search_all",
                details={"error": str(e), "keywords": keywords}
            )
    @staticmethod
    def refresh_search_all_cache(gsId:int) -> Optional[bool]:
        """
        刷新部位下拉栏缓存（删除Redis缓存Key，下次查询会重新从数据库拉取并缓存）
        :return: 是否删除成功
        """
        try:
            CACHE_KEY_XBBW_SEARCH_ALL = f"sys:gsId:{gsId}:AIXiangBaoBuWei"  # 缓存Key，命名规范：cache:业务模块:表名:功能
            delete_count = redis_delete_sync(CACHE_KEY_XBBW_SEARCH_ALL,db=PAGE_DROPDOWN)
            logger.info(f"部位下拉栏缓存：手动刷新成功，删除Redis Key数量={delete_count}")
            return delete_count > 0
        except redis.RedisError as e:
            logger.error(f"部位下拉栏缓存：手动刷新失败 | error={str(e)}")
        except Exception as e:
            logger.error(f"部位下拉栏缓存：手动刷新异常 | error={str(e)}")
            return False






