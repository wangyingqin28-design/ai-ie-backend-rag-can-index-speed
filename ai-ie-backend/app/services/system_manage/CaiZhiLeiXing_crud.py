from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import and_, or_, desc
from sqlalchemy.orm import Session, aliased
from app.models import orm_models
from app.models.orm_models import AICaiZhiLeiXing
from app.schemas.system_manage.CaiZhiLeiXing_schema import CaiZhiLeiXingSearchResponse
from app.services.system_manage.BiaoZhunGongXu_service import GETSOFT_ID
from app.utils.exceptions import (
    NotFoundException, ValidationException, AppException, DataUpdateFailedException,
)
from app.utils.snowflake_generator import SnowFlake
from loguru import logger
import redis
# Redis封装（项目已存在，直接导入）
from app.utils.redis.redis_sync_client import redis_get_sync, redis_set_sync, redis_delete_sync
from app.utils.redis.redis_utils import PAGE_DROPDOWN


class CaiZhiLeiXingCRUD:
    @staticmethod
    def get_existing_by_name(
            db: Session,
            leiXingMingCheng: str,
            exclude_id: Optional[int] = None
    ) -> Optional[orm_models.AICaiZhiLeiXing]:
        """
        根据名称获取已存在的材质

        Args:
            db: 数据库会话
            leiXingMingCheng: 材质名称
            exclude_id: 要排除的ID

        Returns:
            已存在的材质对象或None
        """
        try:
            query = db.query(orm_models.AICaiZhiLeiXing).filter(
                and_(
                    orm_models.AICaiZhiLeiXing.leiXingMingCheng == leiXingMingCheng
                )
            )

            if exclude_id:
                query = query.filter(orm_models.AICaiZhiLeiXing.xbczId != exclude_id)

            return query.first()
        except Exception as e:
            raise DataUpdateFailedException(
                message="查询同名材质失败，CaiZhiLeiXing_crud.get_existing_by_name",
                details={"error": str(e),"leiXingMingCheng":leiXingMingCheng, "exclude_id": exclude_id}
            )
    @staticmethod
    def get_by_id(
            db: Session,
            czlxId: int,
            include_deleted: bool = False,
    ) -> Optional[CaiZhiLeiXingSearchResponse]:
        """
        根据ID获取材质（包含用户信息）

        Args:
            db: 数据库会话
            czlxId: 材质ID
            include_deleted: 是否包含已删除的记录

        Returns:
            材质的Pydantic模型或None
        """
        try:
            # 创建用户表的别名
            insert_user = aliased(orm_models.AIGongSiYongHu, name="insert_user")
            update_user = aliased(orm_models.AIGongSiYongHu, name="update_user")

            # 构建查询
            query = db.query(
                orm_models.AICaiZhiLeiXing,
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name')
            )

            # 左外连接创建用户表
            query = query.outerjoin(
                insert_user,
                orm_models.AICaiZhiLeiXing.in_userid == insert_user.gsyhId
            )

            # 左外连接更新用户表
            query = query.outerjoin(
                update_user,
                orm_models.AICaiZhiLeiXing.up_userid == update_user.gsyhId
            )


            # 根据search方法，使用的是czlxId，这里需要根据实际数据库字段调整
            query = query.filter(orm_models.AICaiZhiLeiXing.czlxId == czlxId)
            # 或者：query = query.filter(orm_models.AICaiZhiLeiXing.czlxId == czlxId)  # 如果主键字段是czlxId

            if not include_deleted:
                query = query.filter(orm_models.AICaiZhiLeiXing.del_flag == False)

            # 执行查询（只调用一次）
            result = query.first()

            if not result:
                raise NotFoundException(
                    message="材质不存在",
                    details={"czlxId": czlxId}
                )

            # 解包结果
            record, insert_user_name, update_user_name = result

            # 检查是否已删除
            if not include_deleted and record.del_flag:
                raise NotFoundException(
                    message="材质已被删除",
                    details={"czlxId": czlxId}
                )

            # 构建字典
            item_dict = {
                "czlxId": record.czlxId,  # 根据实际字段名调整
                "leiXingMingCheng": record.leiXingMingCheng,
                "in_userid": record.in_userid,
                "in_time": record.in_time,
                "up_userid": record.up_userid,
                "up_time": record.up_time,
                "del_flag": record.del_flag,
                "in_username": insert_user_name if insert_user_name else "无注册",
                "up_username": update_user_name if update_user_name else "无注册"
            }

            # 转换为Pydantic模型
            return CaiZhiLeiXingSearchResponse.parse_obj(item_dict)

        except ValidationException as e:
            raise
        except NotFoundException as e:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="查询材质失败,CaiZhiLeiXing_crud.get_by_id",
                details={
                    "error": str(e),
                    "czlxId": czlxId,
                    "include_deleted": include_deleted
                }
            )
    @staticmethod
    def search(
            db: Session,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 20,
    ) -> Tuple[List[CaiZhiLeiXingSearchResponse], int]:
        """
        搜索材质（返回数据列表和总数，不执行分页）
        """
        try:
            # 创建用户表的别名
            insert_user = aliased(orm_models.AIGongSiYongHu, name="insert_user")
            update_user = aliased(orm_models.AIGongSiYongHu, name="update_user")

            # 构建查询
            query = db.query(
                orm_models.AICaiZhiLeiXing,
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name')
            )

            # 左外连接创建用户表
            query = query.outerjoin(
                insert_user,
                orm_models.AICaiZhiLeiXing.in_userid == insert_user.gsyhId
            )

            # 左外连接更新用户表
            query = query.outerjoin(
                update_user,
                orm_models.AICaiZhiLeiXing.up_userid == update_user.gsyhId
            )

            query = query.filter(orm_models.AICaiZhiLeiXing.del_flag == False)

            # 关键词搜索
            if keyword and keyword.strip():
                clean_keyword = keyword.strip()
                query = query.filter(
                    or_(
                        orm_models.AICaiZhiLeiXing.leiXingMingCheng.like(f"%{clean_keyword}%"),
                    )
                )

            # 排序
            query = query.order_by(desc(orm_models.AICaiZhiLeiXing.up_time))

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
                    "czlxId": record.czlxId,
                    "leiXingMingCheng": record.leiXingMingCheng,
                    "in_userid": record.in_userid,
                    "in_time": record.in_time,
                    "up_userid": record.up_userid,
                    "up_time": record.up_time,
                    "del_flag": record.del_flag,
                    "in_username": insert_user_name if insert_user_name else "无注册",
                    "up_username": update_user_name if update_user_name else "无注册"
                }
                # 转换为Pydantic模型
                item_model = CaiZhiLeiXingSearchResponse.parse_obj(item_dict)
                result_list.append(item_model)

            return result_list, total

        except Exception as e:
            raise AppException(
                code=500,
                message="查询材质类型失败,CaiZhiLeiXing_crud.search",
                details={
                    "error": str(e),
                }
            )
    @staticmethod
    def create(
            db: Session,
            leiXingMingCheng: str,
            user_id:int,
    ) -> orm_models.AICaiZhiLeiXing:
        """
        创建标准材质

        Args:
            db: 数据库会话
            leiXingMingCheng: 材质名称
            user_id: 用户ID
        Returns:
            创建的材质对象
        """
        try:
            new_caiZhiLeiXing = orm_models.AICaiZhiLeiXing(
                czlxId=SnowFlake().generate_id(),
                leiXingMingCheng=leiXingMingCheng,
                in_userid=user_id,
                up_userid=user_id,
                del_flag=False,
                in_time=datetime.now(),
                up_time=datetime.now(),
            )
            db.add(new_caiZhiLeiXing)
            db.flush()
            CaiZhiLeiXingCRUD.refresh_search_all_cache()
            return new_caiZhiLeiXing
        except Exception as e:
            raise DataUpdateFailedException(
                message="创建材质失败caiZhiLeiXing_crud.create",
                details={"error":str(e),"caiZhileiXing":leiXingMingCheng, "user_id":user_id}
            )
    @staticmethod
    def update(
        db: Session,
        czlxId: int,
        update_data:Dict[str,Any],
        user_id:int,
        ) -> orm_models.AICaiZhiLeiXing:
        """
        更新材质信息

        Args:
            db: 数据库会话
            czlxId: 材质ID
            update_data: 更新数据
            user_id: 用户ID

        Returns:
            更新后的材质对象
        """
        try:
            # 获取材质
            caiZhiLeiXing = db.query(orm_models.AICaiZhiLeiXing).filter(
                and_(
                    orm_models.AICaiZhiLeiXing.czlxId == czlxId,
                    orm_models.AICaiZhiLeiXing.del_flag == False
                )
            ).first()

            if not caiZhiLeiXing:
                raise NotFoundException(
                    message="材质类型不存在或已被删除",
                    details={"czlxId": czlxId}
                )

            # 更新允许的字段
            allowed_fields = ['leiXingMingCheng']
            for field in allowed_fields:
                if field in update_data:
                    setattr(caiZhiLeiXing, field, update_data[field])

            # 更新操作信息
            caiZhiLeiXing.up_userid = user_id
            caiZhiLeiXing.up_time = datetime.now()

            db.flush()
            CaiZhiLeiXingCRUD.refresh_search_all_cache()
            return caiZhiLeiXing
        except ValidationException as e:
            raise
        except NotFoundException as e:
            raise

        except Exception as e:
            raise AppException(
                code=500,
                message="更新材质类型失败",
                details={
                    "error": str(e),
                    "czlxId": czlxId,
                    "user_id": user_id,
                    "update_data": update_data
                }
            )
    @staticmethod
    def restore(
            db: Session,
            czlxId: int,
            user_id:int,
    ) ->bool:
        """
        恢复已删除的材质

        Args:
            db: 数据库会话
            czlxId: 材质ID
            user_id: 用户ID

        Returns:
            True如果恢复成功
        """
        try:
            caiZhiLeiXing = db.query(orm_models.AICaiZhiLeiXing).filter(
                and_(
                    orm_models.AICaiZhiLeiXing.czlxId == czlxId,
                    orm_models.AICaiZhiLeiXing.del_flag == True
                )
            ).first()

            if not caiZhiLeiXing:
                raise NotFoundException(
                    message="材质不存在或未被删除",
                    details={"czlxId": czlxId}
                )
            #恢复操作
            caiZhiLeiXing.del_flag = False
            caiZhiLeiXing.up_userid = user_id
            caiZhiLeiXing.del_time = None
            caiZhiLeiXing.up_time = datetime.now()

            db.flush()
            CaiZhiLeiXingCRUD.refresh_search_all_cache()
            return True
        except ValidationException as e:
            raise
        except NotFoundException as e:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="恢复材质类型失败：CaiZhiLeiXing_crud.restore",
                details={"error": str(e), "czlxId": czlxId}
            )
    @staticmethod
    def batch_delete(
            db: Session,
            czlxIds:List[int],
            user_id:int,
    ) -> int:
        """
        批量软删除材质

        Args:
            db: 数据库会话
            czlxIds: 材质ID列表
            user_id: 用户ID

        Returns:
            删除结果统计
        """
        try:
            target_records=db.query(orm_models.AICaiZhiLeiXing).filter(
                AICaiZhiLeiXing.czlxId.in_(czlxIds)
            ).all()
            if not target_records:
                raise NotFoundException(
                    message="删除的材质不存在"
                )


            #分离已删除和未删除的记录
            already_deleted_ids = []
            to_delete_ids = []
            for record in target_records:
                if record.del_flag == True:
                    already_deleted_ids.append(record.czlxId)
                else:
                    to_delete_ids.append(record.czlxId)
            # 4. 检查是否有记录已被删除
            if already_deleted_ids:
                # 如果有部分记录已被删除，抛出异常
                raise ValidationException(
                    message=f"部分材质已被删除，无法重复删除，已删除的材质ID: {already_deleted_ids}"
                )
            # 5. 检查是否有不存在的ID（所有查询到的记录数小于传入的ID数）
            found_ids = [record.czlxId for record in target_records]
            not_found_ids = [id for id in czlxIds if id not in found_ids]
            if not_found_ids:
                raise ValidationException(
                    message=f"部分材质不存在，不存在的材质ID: {not_found_ids}"
                )
            # 6. 执行删除（更新del_flag为True）
            delete_count = db.query(orm_models.AICaiZhiLeiXing).filter(
                AICaiZhiLeiXing.czlxId.in_(to_delete_ids),
                AICaiZhiLeiXing.del_flag == False
            ).update(
                {
                    AICaiZhiLeiXing.del_flag: True,
                    AICaiZhiLeiXing.up_userid: user_id,
                    AICaiZhiLeiXing.up_time: datetime.now().replace(microsecond=0),
                    AICaiZhiLeiXing.del_time: datetime.now().replace(microsecond=0)
                },
                synchronize_session=False
            )
            # 7. 提交事务（假设db是Session对象）
            db.commit()
            CaiZhiLeiXingCRUD.refresh_search_all_cache()
            return delete_count
        except AppException:
            # 重新抛出ValidationException，不需要包装
            raise
        except Exception as e:
            raise DataUpdateFailedException(
                message="批量删除材质失败：CaiZhiLeiXing_crud.batch_delete",
                details={"error": str(e), "czlxIds": czlxIds}
            )

    @staticmethod
    def search_all(
            db: Session,
            keywords: Optional[str] = None,  # 修正：统一为Optional[str]规范注解
    ) -> List[Dict[str, Any]]:
        # 1. 关键词统一预处理：去空格、空字符串转None，兼容前端空输入（所有下拉栏一致）
        keywords = keywords.strip() if (keywords and isinstance(keywords, str)) else None
        result_data = []
        gsId = GETSOFT_ID
        # 2. 材质类型专属缓存常量（统一命名规范：cache:业务模块:材质类型拼音:search_all）
        CACHE_KEY_CZLX_SEARCH_ALL = f"sys:gsId:{gsId}:AICaiZhiLeiXing"
        CACHE_EXPIRE_SECONDS = 3600  # 全局统一1小时过期，和其他下拉栏保持一致

        # 3. 核心逻辑：Redis优先取全量缓存+内存过滤，命中则直接返回（不走数据库）
        try:
            cache_all_data = redis_get_sync(CACHE_KEY_CZLX_SEARCH_ALL, db=PAGE_DROPDOWN)
            if cache_all_data is not None and isinstance(cache_all_data, list):
                logger.debug(f"材质类型下拉栏：Redis缓存命中，全量数据共{len(cache_all_data)}条")
                # 无关键词：直接返回Redis全量数据
                if not keywords:
                    result_data = cache_all_data
                # 有关键词：内存模拟ilike做大小写不敏感模糊匹配（和数据库逻辑完全一致）
                else:
                    lower_key = keywords.lower()
                    result_data = [
                        item for item in cache_all_data
                        if lower_key in item.get("caiZhiLeiXing", "").lower()  # 匹配返回的caiZhiLeiXing字段
                    ]
                logger.debug(f"材质类型下拉栏：Redis内存过滤完成，关键词[{keywords}]，匹配结果{len(result_data)}条")
                return result_data
        except redis.RedisError as e:
            logger.warning(f"材质类型下拉栏：Redis缓存读取失败，降级为数据库查询 | error={str(e)}")
        except Exception as e:
            logger.warning(f"材质类型下拉栏：Redis缓存解析失败，降级为数据库查询 | error={str(e)}")

        # 4. Redis失效/故障 → 降级数据库处理（完全保留你原有核心查询逻辑）
        try:
            # 基础查询：过滤软删除数据（你的原有代码）
            query = db.query(orm_models.AICaiZhiLeiXing).filter(
                orm_models.AICaiZhiLeiXing.del_flag == False
            )

            # 关键词过滤：保留原有ilike大小写不敏感（你的原有代码）
            if keywords:
                query = query.filter(
                    orm_models.AICaiZhiLeiXing.leiXingMingCheng.ilike(f"%{keywords}%")
                )

            # 执行查询+构建响应数据（完全保留你的字段映射：leiXingMingCheng→caiZhiLeiXing）
            results = query.all()
            db_all_data = []
            for result in results:
                item = {
                    "czlxId": result.czlxId,
                    "caiZhiLeiXing": result.leiXingMingCheng,  # 保留你原有字段映射关系
                }
                db_all_data.append(item)
            logger.debug(f"材质类型下拉栏：数据库查询成功，共{len(db_all_data)}条")

            # 5. 仅无关键词时写入Redis缓存（关键词结果不缓存，避免Redis膨胀，所有下拉栏一致）
            if not keywords:
                try:
                    redis_set_sync(
                        key=CACHE_KEY_CZLX_SEARCH_ALL,
                        value=db_all_data,
                        ex=CACHE_EXPIRE_SECONDS,
                        db=PAGE_DROPDOWN
                    )
                    logger.debug("材质类型下拉栏：数据库全量数据写入Redis缓存成功")
                except redis.RedisError as e:
                    logger.warning(f"材质类型下拉栏：写入Redis缓存失败 | error={str(e)}")

            result_data = db_all_data
            return result_data

        # 保留原有异常逻辑，**修正2处错误**：材质→材质类型 + 规范异常描述
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="查询材质类型操作失败：" + str(e)
            )

    # ------------------------------
    # 新增：材质类型专属缓存刷新方法（命名/逻辑和所有下拉栏完全一致）
    # ------------------------------
    @staticmethod
    def refresh_search_all_cache() -> bool:
        """
        刷新材质类型下拉栏缓存（删除Redis缓存Key）
        【必用场景】：材质类型数据新增/修改/删除接口执行成功后立即调用，保证缓存与数据库一致
        :return: 是否删除成功
        """
        gsId = GETSOFT_ID
        CACHE_KEY_CZLX_SEARCH_ALL = f"sys:gsId:{gsId}:AICaiZhiLeiXing"
        try:
            delete_count = redis_delete_sync(CACHE_KEY_CZLX_SEARCH_ALL, db=PAGE_DROPDOWN)
            logger.info(f"材质类型下拉栏缓存：手动刷新成功，删除Redis Key数量={delete_count}")
            return delete_count > 0
        except redis.RedisError as e:
            logger.error(f"材质类型下拉栏缓存：手动刷新失败 | error={str(e)}")
            return False
        except Exception as e:
            logger.error(f"材质类型下拉栏缓存：手动刷新异常 | error={str(e)}")
            return False