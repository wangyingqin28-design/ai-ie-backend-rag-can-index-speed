## app/service/system_manage/XiangBaoCaiZhi_crud.py
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import redis
from loguru import logger
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session, aliased
from app.models import orm_models
from app.models.orm_models import AIXiangBaoCaiZhi
from app.schemas.system_manage.XiangBaoCaiZhi_schema import XiangBaoCaiZhiSearchResponse, \
    XiangBaoCaiZhiGetSearchResponse
from app.services.system_manage.base_sys_service import GETSOFT_ID
from app.utils.exceptions import (
    NotFoundException, ValidationException, AppException, DataUpdateFailedException,
)
# 项目Redis相关（已封装，直接导入）
from app.utils.redis.redis_sync_client import redis_get_sync, redis_set_sync, redis_delete_sync
from app.utils.redis.redis_utils import DEFAULT_DB
from app.utils.snowflake_generator import SnowFlake


class XiangBaoCaiZhiCRUD:
    """材质数据库操作类"""
    #=====================================================
    @staticmethod
    def get_by_id(
            db: Session,
            gsId:int,
            xbczId: int,
    ) -> Optional[XiangBaoCaiZhiSearchResponse]:
        """
        根据ID获取材质（包含用户信息）
        Args:
            db: 数据库会话
            gsId:int 公司ID
            xbczId: 材质ID
            include_deleted: 是否包含已删除的记录
        Returns:
            材质的Pydantic模型或None
        """
        try:
            if gsId == GETSOFT_ID:
                logger.info('本公司查询单条数据')
                query = db.query(orm_models.AIXiangBaoCaiZhi).filter(
                    orm_models.AIXiangBaoCaiZhi.xbczId == xbczId,
                ).first()
                if query is None:
                    raise NotFoundException(
                        message="箱包材质为空"
                    )

            else:
                logger.info('其他公司单条查询数据')
                query = db.query(orm_models.AIXiangBaoCaiZhi).filter(
                    orm_models.AIXiangBaoCaiZhi.gsId == gsId,
                    orm_models.AIXiangBaoCaiZhi.xbczId == xbczId,
                ).first()
                if query is None:
                    raise NotFoundException(
                        message="箱包材质为空"
                    )
            return query
        except NotFoundException:
            raise
        except Exception as e:
            raise DataUpdateFailedException(
                message="查询单条材质操作失败",
                details={
                    "error": str(e),
                    "xbczId": xbczId,
                }
            )
    @staticmethod
    def search_admin(
            db: Session,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 20,
    ) -> Tuple[List[XiangBaoCaiZhiSearchResponse], int]:
        """
        搜索材质（返回数据列表和总数，不执行分页）
        """
        try:
            # 创建用户表的别名
            insert_user = aliased(orm_models.AIGongSiYongHu, name="insert_user")
            update_user = aliased(orm_models.AIGongSiYongHu, name="update_user")
            leiXing =aliased(orm_models.AICaiZhiLeiXing,name="leiXing")
            gongSi = aliased(orm_models.AIGongSi, name="gongSi")

            # 构建查询
            query = db.query(
                orm_models.AIXiangBaoCaiZhi,
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name'),
                leiXing.leiXingMingCheng.label('leiXingMingCheng'),
                gongSi.gongSiQuanCheng.label('gongSi_name')
            )

            # 左外连接创建用户表
            query = query.outerjoin(
                insert_user,
                orm_models.AIXiangBaoCaiZhi.in_userid == insert_user.gsyhId
            )

            # 左外连接更新用户表
            query = query.outerjoin(
                update_user,
                orm_models.AIXiangBaoCaiZhi.up_userid == update_user.gsyhId
            )
            query = query.outerjoin(
                leiXing,
                orm_models.AIXiangBaoCaiZhi.czlxId == leiXing.czlxId
            )
            query = query.outerjoin(
                gongSi,
                orm_models.AIXiangBaoCaiZhi.gsId == gongSi.gsId
            )


            query = query.filter(
                orm_models.AIXiangBaoCaiZhi.del_flag == False,
                                 )

            # 关键词搜索
            if keyword and keyword.strip():
                clean_keyword = keyword.strip()
                query = query.filter(
                        orm_models.AIXiangBaoCaiZhi.caiZhiMingCheng.like(f"%{clean_keyword}%")
                )

            # 排序
            query = query.order_by(desc(orm_models.AIXiangBaoCaiZhi.up_time))

            # 获取总数
            total = query.count()

            # 分页
            offset = (page - 1) * page_size
            results = query.offset(offset).limit(page_size).all()

            # 转换为字典列表，然后转换为Pydantic模型
            result_list = []
            for record, insert_user_name, update_user_name ,leiXingMingCheng,gongSi_name in results:
                # 构建字典
                item_dict = {
                    "xbczId": record.xbczId,
                    "czlxId": record.czlxId,
                    "caiZhiMingCheng": record.caiZhiMingCheng,
                    "caiZhiLeiXing": leiXingMingCheng if leiXingMingCheng else "",
                    "caiZhiMiaoShu": record.caiZhiMiaoShu if record.caiZhiMiaoShu else "",
                    "in_userid": record.in_userid,
                    "in_time": record.in_time,
                    "up_userid": record.up_userid,
                    "up_time": record.up_time,
                    "del_flag": record.del_flag,
                    "in_username": insert_user_name if insert_user_name else "无注册",
                    "up_username": update_user_name if update_user_name else "无注册",
                    "gongSi":gongSi_name if gongSi_name else "公司无注册",
                }
                # 转换为Pydantic模型
                item_model = XiangBaoCaiZhiGetSearchResponse.parse_obj(item_dict)
                result_list.append(item_model)

            return result_list, total

        except Exception as e:
            raise DataUpdateFailedException(
                message="查询材质操作失败",
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
    ) -> Tuple[List[XiangBaoCaiZhiSearchResponse], int]:
        """
        搜索材质（返回数据列表和总数，不执行分页）
        """
        try:
            # 创建用户表的别名
            insert_user = aliased(orm_models.AIGongSiYongHu, name="insert_user")
            update_user = aliased(orm_models.AIGongSiYongHu, name="update_user")
            leiXing =aliased(orm_models.AICaiZhiLeiXing,name="leiXing")
            # 构建查询
            query = db.query(
                orm_models.AIXiangBaoCaiZhi,
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name'),
                leiXing.leiXingMingCheng.label('leiXingMingCheng'),
            )
            # 左外连接创建用户表
            query = query.outerjoin(
                insert_user,
                orm_models.AIXiangBaoCaiZhi.in_userid == insert_user.gsyhId
            )
            # 左外连接更新用户表
            query = query.outerjoin(
                update_user,
                orm_models.AIXiangBaoCaiZhi.up_userid == update_user.gsyhId
            )
            query = query.outerjoin(
                leiXing,
                orm_models.AIXiangBaoCaiZhi.czlxId == leiXing.czlxId
            )
            query = query.filter(
                orm_models.AIXiangBaoCaiZhi.del_flag == False,
                orm_models.AIXiangBaoCaiZhi.gsId ==gsId
                                 )
            # 关键词搜索
            if keyword and keyword.strip():
                clean_keyword = keyword.strip()
                query = query.filter(
                        orm_models.AIXiangBaoCaiZhi.caiZhiMingCheng.like(f"%{clean_keyword}%")
                )

            # 排序
            query = query.order_by(desc(orm_models.AIXiangBaoCaiZhi.up_time))

            # 获取总数
            total = query.count()

            # 分页
            offset = (page - 1) * page_size
            results = query.offset(offset).limit(page_size).all()

            # 转换为字典列表，然后转换为Pydantic模型
            result_list = []
            for record, insert_user_name, update_user_name ,leiXingMingCheng in results:
                # 构建字典
                item_dict = {
                    "xbczId": record.xbczId,
                    "czlxId": record.czlxId,
                    "caiZhiMingCheng": record.caiZhiMingCheng,
                    "caiZhiLeiXing": leiXingMingCheng if leiXingMingCheng else "",
                    "caiZhiMiaoShu": record.caiZhiMiaoShu if record.caiZhiMiaoShu else "",
                    "in_userid": record.in_userid,
                    "in_time": record.in_time,
                    "up_userid": record.up_userid,
                    "up_time": record.up_time,
                    "del_flag": record.del_flag,
                    "in_username": insert_user_name if insert_user_name else "无注册",
                    "up_username": update_user_name if update_user_name else "无注册",
                }
                # 转换为Pydantic模型
                item_model = XiangBaoCaiZhiSearchResponse.parse_obj(item_dict)
                result_list.append(item_model)

            return result_list, total

        except Exception as e:
            raise DataUpdateFailedException(
                message="查询材质操作失败",
                details={
                    "error": str(e),
                }
            )
    @staticmethod
    def get_existing_by_name(
            db: Session,
            gsId:int,
            caiZhiMingCheng: str,
            exclude_id: Optional[int] = None
    ) -> Optional[orm_models.AIXiangBaoCaiZhi]:
        """
        根据名称获取已存在的材质

        Args:
            db: 数据库会话
            caiZhiMingCheng: 材质名称
            exclude_id: 要排除的ID

        Returns:
            已存在的材质对象或None
        """
        try:
            query = db.query(orm_models.AIXiangBaoCaiZhi).filter(
                and_(
                    orm_models.AIXiangBaoCaiZhi.gsId == gsId,
                    orm_models.AIXiangBaoCaiZhi.caiZhiMingCheng == caiZhiMingCheng
                )
            )
            if exclude_id:
                query = query.filter(orm_models.AIXiangBaoCaiZhi.xbczId != exclude_id)

            return query.first()
        except Exception as e:
            raise DataUpdateFailedException(
                message="查询同名材质操作失败",
                details={"error": str(e),"caiZhiMingCheng":caiZhiMingCheng}
            )


    # ==========================================================================
    # 创建、更新、删除方法
    # ==========================================================================

    @staticmethod
    def create(
            db: Session,
            gsId:int,
            caiZhiMingCheng: str,
            czlxId: int,
            caiZhiMiaoShu:str,
            user_id:int,
    ) -> orm_models.AIXiangBaoCaiZhi:
        """
        创建标准材质

        Args:
            db: 数据库会话
            caiZhiMingCheng: 材质名称
            user_id: 用户ID
        Returns:
            创建的材质对象
        """
        try:
            new_xiangBaoCaiZhi = orm_models.AIXiangBaoCaiZhi(
                xbczId=SnowFlake().generate_id(),
                czlxId=czlxId,
                caiZhiMingCheng=caiZhiMingCheng,
                caiZhiMiaoShu=caiZhiMiaoShu,
                in_userid=user_id,
                up_userid=user_id,
                del_flag=False,
                in_time=datetime.now(),
                up_time=datetime.now(),
                gsId=gsId,
            )
            db.add(new_xiangBaoCaiZhi)
            db.flush()
            XiangBaoCaiZhiCRUD.refresh_search_all_cache()
            return new_xiangBaoCaiZhi
        except Exception as e:
            raise DataUpdateFailedException(
                message="创建材质操作失败",
                details={"error":str(e),"caiZhiMingCheng":caiZhiMingCheng, "user_id":user_id}
            )
    @staticmethod
    def update(
        db: Session,
        xbczId: int,
        update_data:Dict[str,Any],
        user_id:int,
        ) -> orm_models.AIXiangBaoCaiZhi:
        """
        更新材质信息

        Args:
            db: 数据库会话
            xbczId: 材质ID
            update_data: 更新数据
            user_id: 用户ID

        Returns:
            更新后的材质对象
        """
        try:
            # 获取材质
            xiangbaoCaiZhi = db.query(orm_models.AIXiangBaoCaiZhi).filter(
                and_(
                    orm_models.AIXiangBaoCaiZhi.xbczId == xbczId,
                    orm_models.AIXiangBaoCaiZhi.del_flag == False
                )
            ).first()

            if not xiangbaoCaiZhi:
                raise NotFoundException(
                    message="材质不存在或已被删除",
                    details={"xbczId": xbczId}
                )

            # 更新允许的字段
            allowed_fields = ['caiZhiMingCheng', 'caiZhiMiaoShu','czlxId']
            for field in allowed_fields:
                if field in update_data:
                    setattr(xiangbaoCaiZhi, field, update_data[field])

            # 更新操作信息
            xiangbaoCaiZhi.up_userid = user_id
            xiangbaoCaiZhi.up_time = datetime.now()

            db.flush()
            XiangBaoCaiZhiCRUD.refresh_search_all_cache()
            return xiangbaoCaiZhi
        except ValidationException:
            raise
        except NotFoundException:
            raise
        except Exception as e:
            raise DataUpdateFailedException(
                message="更新材质操作失败",
                details={
                    "error": str(e),
                }
            )
    @staticmethod
    def restore(
            db: Session,
            xbczId: int,
            user_id:int,
    ) ->bool:
        """
        恢复已删除的材质

        Args:
            db: 数据库会话
            xbczId: 材质ID
            user_id: 用户ID

        Returns:
            True如果恢复成功
        """
        try:
            xiangbaoCaiZhi = db.query(orm_models.AIXiangBaoCaiZhi).filter(
                and_(
                    orm_models.AIXiangBaoCaiZhi.xbczId == xbczId,
                    orm_models.AIXiangBaoCaiZhi.del_flag == True
                )
            ).first()

            if not xiangbaoCaiZhi:
                raise NotFoundException(
                    message="材质不存在或未被删除",
                    details={"xbczId": xbczId}
                )
            #恢复操作
            xiangbaoCaiZhi.del_flag = False
            xiangbaoCaiZhi.up_userid = user_id
            xiangbaoCaiZhi.del_time = None
            xiangbaoCaiZhi.up_time = datetime.now()

            db.flush()
            XiangBaoCaiZhiCRUD.refresh_search_all_cache()
            return True
        except AppException:
            raise
        except Exception as e:
            raise DataUpdateFailedException(
                message="恢复材质操作失败",
                details={"error": str(e), "xbczId": xbczId}
            )
    @staticmethod
    def batch_delete(
            db: Session,
            xbczIds:List[int],
            user_id:int,
    ) -> int:
        """
        批量软删除材质
        Args:
            db: 数据库会话
            xbczIds: 材质ID列表
            user_id: 用户ID
        Returns:
            删除结果统计
        """
        try:
            target_records=db.query(orm_models.AIXiangBaoCaiZhi).filter(
                AIXiangBaoCaiZhi.xbczId.in_(xbczIds)
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
                    already_deleted_ids.append(record.xbczId)
                else:
                    to_delete_ids.append(record.xbczId)
            # 4. 检查是否有记录已被删除
            if already_deleted_ids:
                # 如果有部分记录已被删除，抛出异常
                raise ValidationException(
                    message=f"部分材质已被删除，无法重复删除，已删除的材质ID: {already_deleted_ids}"
                )
            # 5. 检查是否有不存在的ID（所有查询到的记录数小于传入的ID数）
            found_ids = [record.xbczId for record in target_records]
            not_found_ids = [id for id in xbczIds if id not in found_ids]
            if not_found_ids:
                raise ValidationException(
                    message=f"部分材质不存在，不存在的材质ID: {not_found_ids}"
                )
            # 6. 执行删除（更新del_flag为True）
            delete_count = db.query(orm_models.AIXiangBaoCaiZhi).filter(
                AIXiangBaoCaiZhi.xbczId.in_(to_delete_ids),
                AIXiangBaoCaiZhi.del_flag == False
            ).update(
                {
                    AIXiangBaoCaiZhi.del_flag: True,
                    AIXiangBaoCaiZhi.up_userid: user_id,
                    AIXiangBaoCaiZhi.up_time: datetime.now().replace(microsecond=0),
                    AIXiangBaoCaiZhi.del_time: datetime.now().replace(microsecond=0)
                },
                synchronize_session=False
            )
            # 7. 提交事务（假设db是Session对象）
            db.flush()
            XiangBaoCaiZhiCRUD.refresh_search_all_cache()
            return delete_count
        except AppException:
            raise
        except Exception as e:
            raise DataUpdateFailedException(
                message="批量删除材质操作失败",
                details={"error": str(e)}
            )

    @staticmethod
    def search_all(
            db: Session,
            gsId:int,
            keywords: Optional[str] = None,  # 修正类型注解：str=None → Optional[str]=None
    ) -> List[Dict[str, Any]]:
        # 1. 关键词预处理：去空格、空字符串转None，兼容前端空输入（和部位逻辑一致）
        keywords = keywords.strip() if (keywords and isinstance(keywords, str)) else None
        result_data = []

        # 2. 定义材质专属缓存常量（就近维护，和部位命名规范一致）
        CACHE_KEY_XBCZ_SEARCH_ALL = "cache:aixiangbao:caizhi:search_all"  # cache:业务:材质:全查
        CACHE_EXPIRE_SECONDS = 3600  # 1小时过期，和部位保持一致，方便统一调整

        # 3. 优先从Redis取全量缓存：无论是否有关键词，都先走缓存（核心逻辑）
        try:
            cache_all_data = redis_get_sync(CACHE_KEY_XBCZ_SEARCH_ALL, db=DEFAULT_DB)
            if cache_all_data is not None and isinstance(cache_all_data, list):
                logger.debug(f"材质下拉栏：Redis缓存命中，全量数据共{len(cache_all_data)}条")
                # 3.1 无关键词：直接返回Redis全量数据
                if not keywords:
                    result_data = cache_all_data
                # 3.2 有关键词：内存模拟ilike做【大小写不敏感模糊匹配】（和数据库逻辑完全一致）
                else:
                    lower_keywords = keywords.lower()  # 统一转小写，实现大小写不敏感
                    result_data = [
                        item for item in cache_all_data
                        if lower_keywords in item.get("caiZhiMingCheng", "").lower()
                    ]
                logger.debug(f"材质下拉栏：Redis内存过滤完成，关键词[{keywords}]，匹配结果{len(result_data)}条")
                return result_data  # 缓存命中，直接返回，不走数据库
        except redis.RedisError as e:
            # Redis异常：仅记录日志，降级到数据库查询，不影响业务
            logger.warning(f"材质下拉栏：Redis缓存读取失败，降级数据库查询 | error={str(e)}")
        except Exception as e:
            # 缓存解析异常：同样降级数据库
            logger.warning(f"材质下拉栏：Redis缓存解析失败，降级数据库查询 | error={str(e)}")

        # 4. Redis缓存失效/故障 → 降级到数据库处理（保留你原有核心逻辑）
        try:
            # 基础查询：过滤未删除数据
            query = db.query(orm_models.AIXiangBaoCaiZhi).filter(
                orm_models.AIXiangBaoCaiZhi.del_flag == False,
                orm_models.AIXiangBaoCaiZhi.gsId == gsId
            )

            # 保留你原有ilike大小写不敏感匹配（兼容数据库侧直接过滤，备用）
            if keywords:
                query = query.filter(
                    orm_models.AIXiangBaoCaiZhi.caiZhiMingCheng.ilike(f"%{keywords}%")
                )

            # 执行查询并构建数据（和你原有代码完全一致）
            results = query.all()
            db_all_data = []
            for result in results:
                item = {
                    "xbczId": result.xbczId,
                    "caiZhiMingCheng": result.caiZhiMingCheng,
                }
                db_all_data.append(item)
            logger.debug(f"材质下拉栏：数据库查询成功，共{len(db_all_data)}条")

            # 5. 仅无关键词时，将数据库全量数据写入Redis（关键词结果不缓存，避免膨胀）
            if not keywords:
                try:
                    redis_set_sync(
                        key=CACHE_KEY_XBCZ_SEARCH_ALL,
                        value=db_all_data,
                        ex=CACHE_EXPIRE_SECONDS,
                        db=DEFAULT_DB
                    )
                    logger.debug("材质下拉栏：数据库全量数据写入Redis缓存成功")
                except redis.RedisError as e:
                    logger.warning(f"材质下拉栏：写入Redis缓存失败 | error={str(e)}")
            # 6. 赋值结果并返回（和你原有返回逻辑一致）
            result_data = db_all_data
            logger.debug(f"材质下拉栏：数据库查询后返回，关键词[{keywords}]，结果{len(result_data)}条")
            return result_data

        # 保留你原有异常处理逻辑，不做修改
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="查询材质操作失败：" + str(e)
            )

    # ------------------------------
    # 新增：材质缓存刷新方法（和部位一一对应）
    # ------------------------------
    @staticmethod
    def refresh_search_all_cache() -> bool:
        """
        刷新材质下拉栏缓存（删除Redis缓存Key）
        【使用场景】：材质数据新增/修改/删除接口执行成功后立即调用，保证数据一致性
        :return: 是否删除成功
        """
        CACHE_KEY_XBCZ_SEARCH_ALL = "cache:aixiangbao:caizhi:search_all"
        try:
            delete_count = redis_delete_sync(CACHE_KEY_XBCZ_SEARCH_ALL, db=DEFAULT_DB)
            logger.info(f"材质下拉栏缓存：手动刷新成功，删除Redis Key数量={delete_count}")
            return delete_count > 0
        except redis.RedisError as e:
            logger.error(f"材质下拉栏缓存：手动刷新失败 | error={str(e)}")
            return False
        except Exception as e:
            logger.error(f"材质下拉栏缓存：手动刷新异常 | error={str(e)}")
            return False




