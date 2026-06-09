## app/service/system_manage/XiangBaoGongZhong_crud.py
import os
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import redis
from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session, aliased
from app.models import orm_models
from app.models.orm_models import AIXiangBaoGongZhong, AIBiaoZhunGongXu, AIQuYuGongJia, AIGongSiGongJia
from app.utils.exceptions import (
    NotFoundException, ValidationException, AppException, DataUpdateFailedException,
)
from app.utils.redis.redis_sync_client import redis_get_sync, redis_set_sync, redis_delete_sync
from app.utils.redis.redis_utils import PAGE_DROPDOWN
from app.utils.snowflake_generator import SnowFlake

load_dotenv()
GETSOFT_ID_STR = os.getenv("GETSOFT_ID")
GETSOFT_ID = int(GETSOFT_ID_STR)

class XiangBaoGongZhongCRUD:
    """工种数据库操作类"""
    #=====================================================

    @staticmethod
    def get_by_id(
            db: Session,
            xbgzId: int,
            gsId:int,
    ) -> Optional[orm_models.AIXiangBaoGongZhong]:
        """
        根据ID获取工种（包含用户信息）

        Args:
            db: 数据库会话
            xbgzId: 工种ID
            include_deleted: 是否包含已删除的记录

        Returns:
            工种的Pydantic模型或None
        """
        try:
            if gsId == GETSOFT_ID:
                logger.info('本公司查询单条数据')
                query = db.query(orm_models.AIXiangBaoGongZhong).filter(
                    orm_models.AIXiangBaoGongZhong.xbgzId == xbgzId,
                ).first()
                if query is None:
                    raise NotFoundException(
                        message=f"单条记录不存在"
                    )
                return query
            else:
                logger.info('其他公司查询单条数据')
                logger.info(f'xbgzId:{xbgzId}, gsId:{gsId}')
                query = db.query(orm_models.AIXiangBaoGongZhong).filter(
                    orm_models.AIXiangBaoGongZhong.xbgzId == xbgzId,
                    orm_models.AIXiangBaoGongZhong.gsId == gsId,
                ).first()
                if query is None:
                    raise NotFoundException(
                        message=f"单条记录不存在"
                    )

            return query
        except NotFoundException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="查询单条工种信息操作失败",
                details={
                    "error": str(e)
                }
            )
    @staticmethod
    def search_admin(
            db: Session,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 20,
    ) -> Tuple[List[dict], int]:
        """
        搜索工种（返回数据列表和总数，不执行分页）
        """
        try:
            # 创建用户表的别名
            insert_user = aliased(orm_models.AIGongSiYongHu, name="insert_user")
            update_user = aliased(orm_models.AIGongSiYongHu, name="update_user")
            gongSi = aliased(orm_models.AIGongSi,name="gongSi")
            query = db.query(
                orm_models.AIXiangBaoGongZhong,
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name'),
                gongSi.gongSiQuanCheng.label('gongSi_name')
            ).filter(orm_models.AIXiangBaoGongZhong.del_flag == False)
            # 左外连接创建用户表
            query = query.outerjoin(
                insert_user,
                orm_models.AIXiangBaoGongZhong.in_userid == insert_user.gsyhId
            )
            # 左外连接更新用户表
            query = query.outerjoin(
                update_user,
                orm_models.AIXiangBaoGongZhong.up_userid == update_user.gsyhId
            )
            query = query.outerjoin(
                gongSi,
                orm_models.AIXiangBaoGongZhong.gsId == gongSi.gsId
            )
            # 关键词搜索
            if keyword and keyword.strip():
                clean_keyword = keyword.strip()
                query = query.filter(
                    orm_models.AIXiangBaoGongZhong.gongZhongMingCheng.like(f"%{clean_keyword}%")
                )
            # 排序
            query = query.order_by(desc(orm_models.AIXiangBaoGongZhong.up_time))
            # 获取总数
            total = query.count()
            # 分页
            offset = (page - 1) * page_size
            results = query.offset(offset).limit(page_size).all()
            # 转换为字典列表，然后转换为Pydantic模型
            result_list = []
            for record,insert_user_name,update_user_name ,gongSi_name in results:
                item = {
                    "xbgzId": record.xbgzId,
                    "gongZhongMingCheng": record.gongZhongMingCheng,
                    "in_userid": record.in_userid,
                    "in_time": record.in_time,
                    "up_userid": record.up_userid,
                    "up_time": record.up_time,
                    "del_flag": record.del_flag,
                    "in_username": insert_user_name if insert_user_name else "无注册",
                    "up_username": update_user_name if update_user_name else "无注册",
                    "gongSi":gongSi_name or "公司未注册"
                }
                result_list.append(item)
            return result_list, total
        except Exception as e:
            raise AppException(
                code=500,
                message="搜索工种操作失败",
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
    ) -> Tuple[List[dict], int]:
        """
        搜索工种（返回数据列表和总数，不执行分页）
        """
        try:
            # 创建用户表的别名
            insert_user = aliased(orm_models.AIGongSiYongHu, name="insert_user")
            update_user = aliased(orm_models.AIGongSiYongHu, name="update_user")
            gongSi = aliased(orm_models.AIGongSi,name="gongSi")
            # 根据不同公司类型构建查询
            # 构建查询
            query = db.query(
                    orm_models.AIXiangBaoGongZhong,
                    insert_user.yongHuXingMing.label('insert_user_name'),
                    update_user.yongHuXingMing.label('update_user_name'),
                ).filter(
                    orm_models.AIXiangBaoGongZhong.del_flag == False,
                    orm_models.AIXiangBaoGongZhong.gsId == gsId,
            )
            # 左外连接创建用户表
            query = query.outerjoin(
                insert_user,
                orm_models.AIXiangBaoGongZhong.in_userid == insert_user.gsyhId
            )
            # 左外连接更新用户表
            query = query.outerjoin(
                update_user,
                orm_models.AIXiangBaoGongZhong.up_userid == update_user.gsyhId
            )
            # 关键词搜索
            if keyword and keyword.strip():
                clean_keyword = keyword.strip()
                query = query.filter(
                    orm_models.AIXiangBaoGongZhong.gongZhongMingCheng.like(f"%{clean_keyword}%")
                )
            # 排序
            query = query.order_by(desc(orm_models.AIXiangBaoGongZhong.up_time))
            # 获取总数
            total = query.count()
            # 分页
            offset = (page - 1) * page_size
            results = query.offset(offset).limit(page_size).all()
            # 转换为字典列表，然后转换为Pydantic模型
            result_list = []
            for record, insert_user_name, update_user_name in results:
                    # 构建字典
                item = {
                    "xbgzId": record.xbgzId,
                    "gongZhongMingCheng": record.gongZhongMingCheng,
                    "in_userid": record.in_userid,
                    "in_time": record.in_time,
                    "up_userid": record.up_userid,
                    "up_time": record.up_time,
                    "del_flag": record.del_flag,
                    "in_username": insert_user_name if insert_user_name else "无注册",
                    "up_username": update_user_name if update_user_name else "无注册"
                }
                result_list.append(item)
            return result_list, total
        except Exception as e:
            raise AppException(
                code=500,
                message="查询工种操作失败",
                details={
                    "error": str(e),
                }
            )
    @staticmethod
    def get_existing_by_name(
            db: Session,
            gongZhongMingCheng: str,
            gsId:int,
            exclude_id: Optional[int] = None
    ) -> Optional[orm_models.AIXiangBaoGongZhong]:
        """
        根据名称获取已存在的工种
        Args:
            db: 数据库会话
            gongZhongMingCheng: 工种名称
            exclude_id: 要排除的ID
        Returns:
            已存在的工种对象或None
        """
        try:
            if gsId == GETSOFT_ID:
                logger.info('本公司查询同名工种')
                query = db.query(orm_models.AIXiangBaoGongZhong).filter(
                    and_(
                        orm_models.AIXiangBaoGongZhong.gongZhongMingCheng == gongZhongMingCheng,
                        orm_models.AIXiangBaoGongZhong.gsId == GETSOFT_ID
                    )
                )
            else:
                logger.info('其他公司查询同名工种')
                query = db.query(orm_models.AIXiangBaoGongZhong).filter(
                    orm_models.AIXiangBaoGongZhong.gongZhongMingCheng == gongZhongMingCheng,
                    orm_models.AIXiangBaoGongZhong.gsId == gsId)
            if exclude_id:
                query = query.filter(orm_models.AIXiangBaoGongZhong.xbgzId != exclude_id)
            return query.first()
        except Exception as e:
            raise AppException(
                code=500,
                message="查询同名工种操作失败",
                details={"error": str(e)}
            )
    # ==========================================================================
    # 创建、更新、删除方法
    # ==========================================================================
    @staticmethod
    def create(
            db: Session,
            gongZhongMingCheng: str,
            user_id:int,
            gsId:int,
    ) -> orm_models.AIXiangBaoGongZhong:
        """
        创建标准工种
        Args:
            db: 数据库会话
            gongZhongMingCheng: 工种名称
            user_id: 用户ID
        Returns:
            创建的工种对象
        """
        try:
            new_xiangBaoGongZhong = orm_models.AIXiangBaoGongZhong(
                xbgzId=SnowFlake().generate_id(),
                gongZhongMingCheng=gongZhongMingCheng,
                in_userid=user_id,
                up_userid=user_id,
                del_flag=False,
                in_time=datetime.now(),
                up_time=datetime.now(),
                gsId=gsId,
            )
            db.add(new_xiangBaoGongZhong)
            db.flush()
            XiangBaoGongZhongCRUD.refresh_search_all_cache(gsId=gsId)
            return new_xiangBaoGongZhong
        except Exception as e:
            raise AppException(
                code=500,
                message="创建工种操作失败",
                details={"error":str(e)}
            )
    @staticmethod
    def update(
        db: Session,
        xbgzId: int,
        gsId:int,
        update_data:Dict[str,Any],
        up_userid:int,
        ) -> orm_models.AIXiangBaoGongZhong:
        """
        更新工种信息
        Args:
            db: 数据库会话
            xbgzId: 工种ID
            update_data: 更新数据
            user_id: 用户ID
        Returns:
            更新后的工种对象
        """
        try:
            if gsId == GETSOFT_ID:
                logger.info('本公司更新单条数据')
                # 获取工种
                query_filter=and_(
                        orm_models.AIXiangBaoGongZhong.xbgzId == xbgzId,
                        orm_models.AIXiangBaoGongZhong.del_flag == False,
                        orm_models.AIXiangBaoGongZhong.gsId == GETSOFT_ID
                )
            else:
                logger.info('其他公司更新单条数据')
                query_filter =and_(
                    orm_models.AIXiangBaoGongZhong.gsId == gsId,
                    orm_models.AIXiangBaoGongZhong.del_flag == False,
                    orm_models.AIXiangBaoGongZhong.xbgzId == xbgzId,
                )
            xiangBaoGongZhong = db.query(orm_models.AIXiangBaoGongZhong).filter(query_filter).first()
            if not xiangBaoGongZhong:
                    raise NotFoundException(
                        message="工种不存在或已被删除",
                        details={"xbgzId": xbgzId}
                    )
            # 更新允许的字段
            allowed_fields = ['gongZhongMingCheng', 'gongXuMiaoShu']
            for field in allowed_fields:
                if field in update_data:
                    setattr(xiangBaoGongZhong, field, update_data[field])
            # 更新操作信息
            xiangBaoGongZhong.up_userid = up_userid
            xiangBaoGongZhong.up_time = datetime.now()
            db.flush()
            XiangBaoGongZhongCRUD.refresh_search_all_cache(gsId)
            return xiangBaoGongZhong
        except ValidationException:
            raise
        except NotFoundException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="更新工种操作失败",
                details={
                    "error": str(e)
                }
            )
    @staticmethod
    def restore(
            db: Session,
            xbgzId: int,
            user_id:int,
            gsId:int,
    ) ->bool:
        """
        恢复已删除的工种

        Args:
            db: 数据库会话
            xbgzId: 工种ID
            user_id: 用户ID

        Returns:
            True如果恢复成功
        """
        try:
            xiangbaoGongZhong = db.query(orm_models.AIXiangBaoGongZhong).filter(
                and_(
                    orm_models.AIXiangBaoGongZhong.xbgzId == xbgzId,
                    orm_models.AIXiangBaoGongZhong.del_flag == True
                )
            ).first()

            if not xiangbaoGongZhong:
                raise NotFoundException(
                    message="工种不存在或未被删除",
                    details={"xbgzId": xbgzId}
                )
            #恢复操作
            xiangbaoGongZhong.del_flag = False
            xiangbaoGongZhong.up_userid = user_id
            xiangbaoGongZhong.del_time = None
            xiangbaoGongZhong.up_time = datetime.now().replace(microsecond=0)

            db.flush()
            XiangBaoGongZhongCRUD.refresh_search_all_cache(gsId=gsId)
            return True
        except ValidationException:
            raise
        except NotFoundException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="恢复工种操作失败",
                details={"error": str(e), "xbgzId": xbgzId}
            )
    @staticmethod
    def batch_delete(
            db: Session,
            xbgzIds:List[int],
            gsId:int,
            user_id:int,
    ) -> int:
        """
        批量软删除工种

        Args:
            db: 数据库会话
            xbgzIds: 工种ID列表
            user_id: 用户ID

        Returns:
            删除结果统计
        """
        try:
            if gsId == GETSOFT_ID:
                logger.info('本公司删除数据')
                biaoZhunGongXu_records = db.query(orm_models.AIBiaoZhunGongXu).filter(
                    AIBiaoZhunGongXu.xbgzId.in_(xbgzIds)
                ).first()
                if biaoZhunGongXu_records:
                    raise ValidationException(
                        message="删除的工种被标准工种引用"
                    )
                quYuGongJia_records = db.query(orm_models.AIQuYuGongJia).filter(
                    AIQuYuGongJia.xbgzId.in_(xbgzIds)
                ).first()
                if quYuGongJia_records:
                    raise ValidationException(
                        message="删除的工种被区域工价引用"
                    )
                gongSiYuGongJia_records = db.query(orm_models.AIGongSiGongJia).filter(
                    AIGongSiGongJia.xbgzId.in_(xbgzIds)
                ).first()
                if gongSiYuGongJia_records:
                    raise ValidationException(
                        message="删除的工种被公司工价引用"
                    )

                target_records=db.query(orm_models.AIXiangBaoGongZhong).filter(
                    AIXiangBaoGongZhong.xbgzId.in_(xbgzIds),
                    AIXiangBaoGongZhong.del_flag == False
                ).all()
            else:
                logger.info('其他公司删除数据')
                biaoZhunGongXu_records = db.query(orm_models.AIBiaoZhunGongXu).filter(
                    AIBiaoZhunGongXu.xbgzId.in_(xbgzIds),
                    AIBiaoZhunGongXu.gsId == gsId,
                ).first()
                if biaoZhunGongXu_records:
                    raise ValidationException(
                        message="删除的工种被标准工种引用"
                    )
                quYuGongJia_records = db.query(orm_models.AIQuYuGongJia).filter(
                    AIQuYuGongJia.xbgzId.in_(xbgzIds),
                ).first()
                if quYuGongJia_records:
                    raise ValidationException(
                        message="删除的工种被区域工价引用"
                    )
                gongSiYuGongJia_records = db.query(orm_models.AIGongSiGongJia).filter(
                    AIGongSiGongJia.xbgzId.in_(xbgzIds),
                    AIGongSiGongJia.gsId == gsId
                ).first()
                if gongSiYuGongJia_records:
                    raise ValidationException(
                        message="删除的工种被公司工价引用"
                    )
                target_records = db.query(orm_models.AIXiangBaoGongZhong).filter(
                    AIXiangBaoGongZhong.xbgzId.in_(xbgzIds),
                    AIXiangBaoGongZhong.del_flag == False,
                    AIXiangBaoGongZhong.gsId == gsId
                ).all()
            if not target_records:
                raise NotFoundException(
                    message="删除的工种不存在"
                )
            #分离已删除和未删除的记录
            already_deleted_ids = []
            to_delete_ids = []
            for record in target_records:
                if record.del_flag == True:
                    already_deleted_ids.append(record.xbgzId)
                else:
                    to_delete_ids.append(record.xbgzId)
            # 4. 检查是否有记录已被删除
            if already_deleted_ids:
                # 如果有部分记录已被删除，抛出异常
                raise ValidationException(
                    message=f"部分工种已被删除，无法重复删除，已删除的工种ID: {already_deleted_ids}"
                )
            # 5. 检查是否有不存在的ID（所有查询到的记录数小于传入的ID数）
            found_ids = [record.xbgzId for record in target_records]
            not_found_ids = [id for id in xbgzIds if id not in found_ids]
            if not_found_ids:
                raise ValidationException(
                    message=f"部分工种不存在，不存在的工种ID: {not_found_ids}"
                )
            # 6. 执行删除（更新del_flag为True）
            if gsId == GETSOFT_ID:
                delete_count = db.query(orm_models.AIXiangBaoGongZhong).filter(
                    AIXiangBaoGongZhong.xbgzId.in_(to_delete_ids),
                    AIXiangBaoGongZhong.del_flag == False,
                ).update(
                    {
                        AIXiangBaoGongZhong.del_flag: True,
                        AIXiangBaoGongZhong.up_userid: user_id,
                        AIXiangBaoGongZhong.up_time: datetime.now().replace(microsecond=0),
                        AIXiangBaoGongZhong.del_time: datetime.now().replace(microsecond=0)
                    },
                    synchronize_session=False
                )
            else:
                delete_count = db.query(orm_models.AIXiangBaoGongZhong).filter(
                    AIXiangBaoGongZhong.del_flag == False,
                    AIXiangBaoGongZhong.xbgzId.in_(to_delete_ids),
                    AIXiangBaoGongZhong.gsId == gsId,
                ).update(
                    {
                        AIXiangBaoGongZhong.del_flag: True,
                        AIXiangBaoGongZhong.up_userid: user_id,
                        AIXiangBaoGongZhong.up_time: datetime.now().replace(microsecond=0),
                        AIXiangBaoGongZhong.del_time: datetime.now().replace(microsecond=0)
                    },
                    synchronize_session=False
                )
            # 7. 提交事务（假设db是Session对象）
            db.flush()
            XiangBaoGongZhongCRUD.refresh_search_all_cache(gsId=gsId)
            return delete_count
        except AppException:
            # 重新抛出ValidationException，不需要包装
            raise
        except Exception as e:
            raise DataUpdateFailedException(
                message="批量删除工种操作失败",
                details={"error": str(e)}
            )

    @staticmethod
    def search_all(
            db: Session,
            gsId: int,
            keywords: Optional[str] = None,  # 统一修正为Optional[str]，规范类型注解
    ) -> List[Dict[str, Any]]:
        # 1. 关键词统一预处理：去空格、空字符串转None，兼容前端空输入（和所有下拉栏一致）
        keywords = keywords.strip() if (keywords and isinstance(keywords, str)) else None
        result_data = []

        # 2. 工种专属缓存常量（遵循统一命名规范：cache:业务模块:工种拼音:全查）
        CACHE_KEY_XBGZ_SEARCH_ALL = f"sys:gsId:{gsId}:AIXiangBaoGongZhong"
        CACHE_EXPIRE_SECONDS = 3600  # 全局统一1小时过期，和其他下拉栏保持一致

        # 3. 核心逻辑：优先从Redis取全量缓存，命中则内存过滤（不走数据库，极致响应）
        try:
            cache_all_data = redis_get_sync(CACHE_KEY_XBGZ_SEARCH_ALL, PAGE_DROPDOWN)
            if cache_all_data is not None and isinstance(cache_all_data, list):
                logger.debug(f"工种下拉栏：Redis缓存命中，全量数据共{len(cache_all_data)}条")
                # 无关键词：直接返回Redis全量数据
                if not keywords:
                    result_data = cache_all_data
                # 有关键词：内存模拟ilike做大小写不敏感模糊匹配（和数据库逻辑完全一致）
                else:
                    lower_key = keywords.lower()
                    result_data = [
                        item for item in cache_all_data
                        if lower_key in item.get("gongZhongMingCheng", "").lower()
                    ]
                logger.debug(f"工种下拉栏：Redis内存过滤完成，关键词[{keywords}]，匹配结果{len(result_data)}条")
                return result_data  # 缓存命中直接返回，无需走数据库
        except redis.RedisError as e:
            logger.warning(f"工种下拉栏：Redis缓存读取失败，降级为数据库查询 | error={str(e)}")
        except Exception as e:
            logger.warning(f"工种下拉栏：Redis缓存解析失败，降级为数据库查询 | error={str(e)}")

        # 4. Redis失效/故障 → 降级到数据库处理（完全保留你原有核心代码，仅少量调整）
        try:
            query = db.query(orm_models.AIXiangBaoGongZhong).filter(
                orm_models.AIXiangBaoGongZhong.del_flag == False,
                orm_models.AIXiangBaoGongZhong.gsId == gsId,
            )
            # 添加关键词过滤（保留你原有ilike大小写不敏感，代码不变）
            if keywords:
                query = query.filter(
                    orm_models.AIXiangBaoGongZhong.gongZhongMingCheng.ilike(f"%{keywords}%")
                )

            # 执行查询+构建响应数据（完全保留你的原有代码，字段不变）
            results = query.all()
            db_all_data = []
            for result in results:
                item = {
                    "xbgzId": result.xbgzId,
                    "gongZhongMingCheng": result.gongZhongMingCheng,
                }
                db_all_data.append(item)
            logger.debug(f"工种下拉栏：数据库查询成功，共{len(db_all_data)}条")

            # 5. 仅无关键词时写入Redis缓存（关键词结果不缓存，避免Redis膨胀，和所有下拉栏一致）
            if not keywords:
                try:
                    redis_set_sync(
                        key=CACHE_KEY_XBGZ_SEARCH_ALL,
                        value=db_all_data,
                        ex=CACHE_EXPIRE_SECONDS,
                        db=PAGE_DROPDOWN
                    )
                    logger.debug("工种下拉栏：数据库全量数据写入Redis缓存成功")
                except redis.RedisError as e:
                    logger.warning(f"工种下拉栏：写入Redis缓存失败 | error={str(e)}")

            # 赋值结果并返回
            result_data = db_all_data
            return result_data

        # 完全保留你原有异常处理逻辑，**修正了错误的异常消息**（材质→工种）
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="查询工种操作失败：" + str(e)
            )
    # ------------------------------
    # 新增：工种专属缓存刷新方法（命名/逻辑和所有下拉栏完全一致）
    # ------------------------------
    @staticmethod
    def refresh_search_all_cache(gsId:int) -> bool:
        """
        刷新工种下拉栏缓存（删除Redis缓存Key）
        【必用场景】：工种数据新增/修改/删除接口执行成功后立即调用，保证缓存和数据库数据一致
        :return: 是否删除成功
        """
        CACHE_KEY_XBGZ_SEARCH_ALL = f"sys:gsId:{gsId}:AIXiangBaoGongZhong"
        try:
            delete_count = redis_delete_sync(CACHE_KEY_XBGZ_SEARCH_ALL,PAGE_DROPDOWN)
            logger.info(f"工种下拉栏缓存：手动刷新成功，删除Redis Key数量={delete_count}")
            return delete_count > 0
        except redis.RedisError as e:
            logger.error(f"工种下拉栏缓存：手动刷新失败 | error={str(e)}")
            return False
        except Exception as e:
            logger.error(f"工种下拉栏缓存：手动刷新异常 | error={str(e)}")
            return False



