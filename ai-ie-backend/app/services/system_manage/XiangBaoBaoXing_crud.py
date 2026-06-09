from datetime import datetime
from typing import Tuple, List, Optional, Any, Dict

import redis
from loguru import logger
from sqlalchemy import desc, and_
from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from app.models import orm_models
from app.models.orm_models import AIXiangBaoBaoXing
from app.schemas.system_manage.XiangBaoBaoXing_schema import XiangBaoBaoXingSearchResponse, \
    XiangBaoBaoXingGetSearchResponse
from app.services.system_manage.BiaoZhunGongXu_service import GETSOFT_ID
from app.utils.exceptions import AppException, DataUpdateFailedException, NotFoundException, ValidationException
# Redis封装（项目已存在，直接导入）
from app.utils.redis.redis_sync_client import redis_get_sync, redis_set_sync, redis_delete_sync
from app.utils.redis.redis_utils import PAGE_DROPDOWN
from app.utils.snowflake_generator import SnowFlake


class XiangBaoBaoXingCRUD:
    """
    箱包包型数据操作类
    """

    @staticmethod
    def search_admin(
            db: Session,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 20,
            parent_id: Optional[int] = None,
            fubxId: Optional[int] = None
    ) -> Tuple[List[XiangBaoBaoXingGetSearchResponse], int]:
        """
        搜索包型（使用自连接获取父级包型名称，外连接获取用户信息）

        参数:
            db: 数据库会话
            keyword: 搜索关键词
            page: 页码
            page_size: 每页数量
            parent_id: 父级等级筛选
            fbxId: 父级包型ID筛选

        返回:
            Tuple[包型列表, 总记录数]
        """
        try:
            # 创建父级表的别名（用于自连接）
            Parent = aliased(AIXiangBaoBaoXing, name="parent")

            # 创建用户表的别名
            insert_user = aliased(orm_models.AIGongSiYongHu, name="insert_user")
            update_user = aliased(orm_models.AIGongSiYongHu, name="update_user")
            gongSi = aliased(orm_models.AIGongSi, name="gongSi")

            # 构建查询
            query = db.query(
                AIXiangBaoBaoXing,
                func.coalesce(Parent.baoXingMingCheng, '').label("parent_bao_xing_ming_cheng"),
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name'),
                gongSi.gongSiQuanCheng.label('gongSi_name'),

            )

            # 左外连接：当前表的fbxId = 父级表的xbbxId
            query = query.outerjoin(
                Parent,
                AIXiangBaoBaoXing.fubxId == Parent.xbbxId,
            )

            # 左外连接创建用户表
            query = query.outerjoin(
                insert_user,
                AIXiangBaoBaoXing.in_userid == insert_user.gsyhId
            )

            # 左外连接更新用户表
            query = query.outerjoin(
                update_user,
                AIXiangBaoBaoXing.up_userid == update_user.gsyhId
            )
            query = query.outerjoin(
                gongSi,
                AIXiangBaoBaoXing.gsId == gongSi.gsId
            )

            # 只查询未删除的记录
            query = query.filter(AIXiangBaoBaoXing.del_flag == False)

            # 关键词搜索（包型名称）
            if keyword and keyword.strip():
                clean_keyword = keyword.strip()
                query = query.filter(
                    AIXiangBaoBaoXing.baoXingMingCheng.like(f"%{clean_keyword}%"),
                )

            # 父级等级筛选
            if parent_id is not None:
                query = query.filter(AIXiangBaoBaoXing.parent_id == parent_id)

            # 父级包型ID筛选
            if fubxId is not None and fubxId != 0:
                if fubxId == 0:
                    # 查询一级分类（父级ID为0）
                    query = query.filter(AIXiangBaoBaoXing.fubxId == 0)
                else:
                    # 查询指定父级下的子类
                    query = query.filter(AIXiangBaoBaoXing.fubxId == fubxId)

            # 排序：按更新时间降序，相同时间按创建时间降序
            query = query.order_by(
                desc(AIXiangBaoBaoXing.up_time),
                desc(AIXiangBaoBaoXing.in_time)
            )

            # 获取总数
            total = query.count()

            # 分页
            offset = (page - 1) * page_size
            results = query.offset(offset).limit(page_size).all()

            # 转换为响应模型
            search_items = []
            for result in results:
                # result是一个四元组：(主记录对象, 父级包型名称, 创建用户姓名, 更新用户姓名)
                bao_xing, parent_name, insert_user_name, update_user_name,gongSi_name = result

                # 构建字典
                item_dict = {
                    "xbbxId": bao_xing.xbbxId,
                    "baoXingMingCheng": bao_xing.baoXingMingCheng,
                    "parent_id": bao_xing.parent_id,
                    "fubxId": bao_xing.fubxId,
                    "baoXingMiaoShu": bao_xing.baoXingMiaoShu,
                    "parent_BaoXingMingCheng": parent_name if parent_name else "无",
                    "in_userid": bao_xing.in_userid,
                    "in_time": bao_xing.in_time,
                    "up_userid": bao_xing.up_userid,
                    "up_time": bao_xing.up_time,
                    "del_flag": bao_xing.del_flag,
                    "in_username": insert_user_name if insert_user_name else "无注册",
                    "up_username": update_user_name if update_user_name else "无注册",
                    "gongSi": gongSi_name if gongSi_name else "公司无注册"
                }

                # 构建搜索项
                search_item = XiangBaoBaoXingGetSearchResponse.parse_obj(item_dict)
                search_items.append(search_item)

            return search_items, total

        except Exception as e:
            raise AppException(
                code=500,
                message="查询包型失败, XiangBaoBaoXingCRUD.search",
                details={
                    "error": str(e),
                    "keyword": keyword,
                    "page": page,
                    "page_size": page_size
                }
            )
    @staticmethod
    def search_user(
            db: Session,
            gsId :int,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 20,
            parent_id: Optional[int] = None,
            fubxId: Optional[int] = None
    ) -> Tuple[List[XiangBaoBaoXingSearchResponse], int]:
        """
        搜索包型（使用自连接获取父级包型名称，外连接获取用户信息）

        参数:
            db: 数据库会话
            keyword: 搜索关键词
            page: 页码
            page_size: 每页数量
            parent_id: 父级等级筛选
            fbxId: 父级包型ID筛选

        返回:
            Tuple[包型列表, 总记录数]
        """
        try:
            # 创建父级表的别名（用于自连接）
            Parent = aliased(AIXiangBaoBaoXing, name="parent")

            # 创建用户表的别名
            insert_user = aliased(orm_models.AIGongSiYongHu, name="insert_user")
            update_user = aliased(orm_models.AIGongSiYongHu, name="update_user")
            gongSi = aliased(orm_models.AIGongSi, name="gongSi")

            # 构建查询
            query = db.query(
                AIXiangBaoBaoXing,
                func.coalesce(Parent.baoXingMingCheng, '').label("parent_bao_xing_ming_cheng"),
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name'),

            )

            # 左外连接：当前表的fbxId = 父级表的xbbxId
            query = query.outerjoin(
                Parent,
                AIXiangBaoBaoXing.fubxId == Parent.xbbxId,
            )

            # 左外连接创建用户表
            query = query.outerjoin(
                insert_user,
                AIXiangBaoBaoXing.in_userid == insert_user.gsyhId
            )

            # 左外连接更新用户表
            query = query.outerjoin(
                update_user,
                AIXiangBaoBaoXing.up_userid == update_user.gsyhId
            )

            # 只查询未删除的记录
            query = query.filter(AIXiangBaoBaoXing.del_flag == False,
                                 AIXiangBaoBaoXing.gsId == gsId)

            # 关键词搜索（包型名称）
            if keyword and keyword.strip():
                clean_keyword = keyword.strip()
                query = query.filter(
                    AIXiangBaoBaoXing.baoXingMingCheng.like(f"%{clean_keyword}%"),
                )

            # 父级等级筛选
            if parent_id is not None:
                query = query.filter(AIXiangBaoBaoXing.parent_id == parent_id)

            # 父级包型ID筛选
            if fubxId is not None and fubxId != 0:
                if fubxId == 0:
                    # 查询一级分类（父级ID为0）
                    query = query.filter(AIXiangBaoBaoXing.fubxId == 0)
                else:
                    # 查询指定父级下的子类
                    query = query.filter(AIXiangBaoBaoXing.fubxId == fubxId)

            # 排序：按更新时间降序，相同时间按创建时间降序
            query = query.order_by(
                desc(AIXiangBaoBaoXing.up_time),
                desc(AIXiangBaoBaoXing.in_time)
            )

            # 获取总数
            total = query.count()

            # 分页
            offset = (page - 1) * page_size
            results = query.offset(offset).limit(page_size).all()

            # 转换为响应模型
            search_items = []
            for result in results:
                # result是一个四元组：(主记录对象, 父级包型名称, 创建用户姓名, 更新用户姓名)
                bao_xing, parent_name, insert_user_name, update_user_name = result

                # 构建字典
                item_dict = {
                    "xbbxId": bao_xing.xbbxId,
                    "baoXingMingCheng": bao_xing.baoXingMingCheng,
                    "parent_id": bao_xing.parent_id,
                    "fubxId": bao_xing.fubxId,
                    "baoXingMiaoShu": bao_xing.baoXingMiaoShu,
                    "parent_BaoXingMingCheng": parent_name if parent_name else "无",
                    "in_userid": bao_xing.in_userid,
                    "in_time": bao_xing.in_time,
                    "up_userid": bao_xing.up_userid,
                    "up_time": bao_xing.up_time,
                    "del_flag": bao_xing.del_flag,
                    "in_username": insert_user_name if insert_user_name else "无注册",
                    "up_username": update_user_name if update_user_name else "无注册",
                }

                # 构建搜索项
                search_item = XiangBaoBaoXingSearchResponse.parse_obj(item_dict)
                search_items.append(search_item)

            return search_items, total

        except Exception as e:
            raise AppException(
                code=500,
                message="查询包型失败, XiangBaoBaoXingCRUD.search",
                details={
                    "error": str(e),
                    "keyword": keyword,
                    "page": page,
                    "page_size": page_size
                }
            )
    # ==========================================================================
    # 创建、更新、删除方法
    # ==========================================================================

    @staticmethod
    def create(
            db: Session,
            gsId:int,
            baoXingMingCheng: str,
            baoXingMiaoShu: str,
            parent_id: int,
            fubxId: int,
            user_id:int,
    ) -> orm_models.AIXiangBaoBaoXing:
        """
        创建标准包型

        Args:
            db: 数据库会话
            baoXingMingCheng: 包型名称
            user_id: 用户ID
        Returns:
            创建的包型对象
        """
        try:
            new_xiangBaoBaoXing = orm_models.AIXiangBaoBaoXing(
                xbbxId=SnowFlake().generate_id(),
                baoXingMingCheng=baoXingMingCheng,
                baoXingMiaoShu=baoXingMiaoShu,
                parent_id=parent_id,
                fubxId=fubxId,
                in_userid=user_id,
                up_userid=user_id,
                del_flag=False,
                in_time=datetime.now(),
                up_time=datetime.now(),
                gsId=gsId
            )
            db.add(new_xiangBaoBaoXing)
            db.flush()
            XiangBaoBaoXingCRUD.refresh_search_all_cache(gsId)
            return new_xiangBaoBaoXing
        except Exception as e:
            raise DataUpdateFailedException(
                message="创建包型失败XiangBaoBaoXing_crud.create",
                details={"error":str(e),"baoXingMingCheng":baoXingMingCheng, "user_id":user_id}
            )
    @staticmethod
    def get_existing_by_name(
            db: Session,
            gsId:int,
            baoXingMingCheng: str,
            exclude_id: Optional[int] = None
    ) -> Optional[orm_models.AIXiangBaoBaoXing]:
        """
        根据名称获取已存在的包型

        Args:
            db: 数据库会话
            baoXingMingCheng: 包型名称
            exclude_id: 要排除的ID

        Returns:
            已存在的包型对象或None
        """
        try:
            query = db.query(orm_models.AIXiangBaoBaoXing).filter(
                    orm_models.AIXiangBaoBaoXing.baoXingMingCheng == baoXingMingCheng,
                    orm_models.AIXiangBaoBaoXing.gsId == gsId,
            )

            if exclude_id:
                query = query.filter(orm_models.AIXiangBaoBaoXing.xbbxId != exclude_id)

            return query.first()
        except Exception as e:
            raise DataUpdateFailedException(
                message="查询同名包型失败，XiangBaoBaoXing_crud.get_existing_by_name",
                details={"error": str(e),"baoXingMingCheng":baoXingMingCheng, "exclude_id": exclude_id}
            )
    @staticmethod
    def update(
        db: Session,
        xbbxId: int,
        gsId: int,
        update_data:Dict[str,Any],
        ):
        """
        更新包型信息

        Args:
            db: 数据库会话
            xbbxId: 包型ID
            update_data: 更新数据
            user_id: 用户ID

        Returns:
            更新后的包型对象
        """
        data = update_data['up_userid']
        try:
            if gsId == GETSOFT_ID:
                # 获取包型
                xiangbaoBaoXing = db.query(orm_models.AIXiangBaoBaoXing).filter(
                    and_(
                        orm_models.AIXiangBaoBaoXing.xbbxId == xbbxId,
                        orm_models.AIXiangBaoBaoXing.del_flag == False
                    )
                ).first()
            else:
                xiangbaoBaoXing = db.query(orm_models.AIXiangBaoBaoXing).filter(
                    orm_models.AIXiangBaoBaoXing.gsId == gsId,
                    orm_models.AIXiangBaoBaoXing.xbbxId == xbbxId,
                    orm_models.AIXiangBaoBaoXing.del_flag == False
                ).first()

            if not xiangbaoBaoXing:
                raise NotFoundException(
                    message="包型不存在或已被删除"
                )


            # 更新允许的字段
            allowed_fields = ['baoXingMingCheng','fubxId','parent_id','baoXingMiaoShu']
            for field in allowed_fields:
                if field in update_data:
                    setattr(xiangbaoBaoXing, field, update_data[field])

            # 更新操作信息

            xiangbaoBaoXing.up_userid = data
            xiangbaoBaoXing.up_time = datetime.now()

            db.flush()
            XiangBaoBaoXingCRUD.refresh_search_all_cache(gsId)
            return xiangbaoBaoXing
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="更新包型操作失败",
                details={
                    "error": str(e),
                    "xbbxId": xbbxId,
                    "user_id": data,
                    "update_data": update_data
                }
            )

    @staticmethod
    def get_by_id(
            db: Session,
            gsId:int,
            xbbxId: int,
            include_deleted: bool = False,
    ):
        """
        根据ID获取包型（包含用户信息和父级包型名称）

        Args:
            db: 数据库会话
            xbbxId: 包型ID
            include_deleted: 是否包含已删除的记录

        Returns:
            包型的Pydantic模型或None
        """
        try:
            if gsId == GETSOFT_ID:
                logger.info('本公司查询单条数据')
                query = db.query(orm_models.AIXiangBaoBaoXing).filter(
                    orm_models.AIXiangBaoBaoXing.xbbxId == xbbxId
                ).first()
            else:
                logger.info('其他公司单条查询')
                query = db.query(orm_models.AIXiangBaoBaoXing).filter(
                    orm_models.AIXiangBaoBaoXing.gsId == gsId,
                    orm_models.AIXiangBaoBaoXing.xbbxId == xbbxId
                ).first()
            if query is None:
                raise NotFoundException(
                    message="箱包包型数据为空"
                )
            return query
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="查询单条包型操作失败",
                details={
                    "error": str(e),
                }
            )

    @staticmethod
    def batch_delete(
            db: Session,
            gsId:int,
            xbbxIds: List[int],
            user_id: int,
    ) -> int:
        """
        批量软删除包型

        Args:
            db: 数据库会话
            xbbxIds: 包型ID列表，确保非空且唯一
            user_id: 用户ID

        Returns:
            成功删除的记录数

        Raises:
            NotFoundException: 所有包型都不存在时抛出
            ValidationException: 存在已删除、被引用或部分不存在的包型时抛出
            DataUpdateFailedException: 数据库操作失败时抛出
        """
        # 去重并转换为集合以提高查询效率
        unique_ids = set(xbbxIds)
        try:
            if gsId == GETSOFT_ID:
                target_records = db.query(AIXiangBaoBaoXing).filter(
                    AIXiangBaoBaoXing.xbbxId.in_(unique_ids)
                ).with_for_update().all()  #  锁住待操作父记录
            else:
                target_records = db.query(AIXiangBaoBaoXing).filter(
                    AIXiangBaoBaoXing.gsId == gsId,
                    AIXiangBaoBaoXing.xbbxId.in_(unique_ids)
                ).with_for_update().all()  #  锁住待操作父记录

            # 2. 检查是否存在任何记录
            if not target_records:
                raise NotFoundException(message="指定的包型不存在")

            # 3. 分类处理记录
            found_ids = {record.xbbxId for record in target_records}
            not_found_ids = unique_ids - found_ids
            already_deleted_ids = set()
            valid_to_delete_ids = set()

            for record in target_records:
                if record.del_flag:
                    already_deleted_ids.add(record.xbbxId)
                else:
                    valid_to_delete_ids.add(record.xbbxId)

            # 4. 收集所有错误信息
            error_messages = []

            if not_found_ids:
                error_messages.append(f"部分包型不存在，ID: {sorted(not_found_ids)}")

            if already_deleted_ids:
                error_messages.append(f"部分包型已被删除，ID: {sorted(already_deleted_ids)}")

            # 5. 检查是否有子包型引用（只检查有效待删除的记录）
            if valid_to_delete_ids:
                child_records = db.query(AIXiangBaoBaoXing).filter(
                    AIXiangBaoBaoXing.fubxId.in_(valid_to_delete_ids),
                    AIXiangBaoBaoXing.del_flag == False
                ).all()

                if child_records:
                    # 找出被哪些包型引用
                    referenced_parent_ids = {str(record.fubxId) for record in child_records}
                    child_ids = {str(record.xbbxId) for record in child_records}
                    error_messages.append(
                        f"包型ID {', '.join(sorted(referenced_parent_ids))} 被其他包型引用，"
                        f"引用包型ID: {', '.join(sorted(child_ids))}"
                    )
            # 6. 如果有任何错误，抛出异常
            if error_messages:
                raise ValidationException(
                    message="；".join(error_messages)
                )
            update_filter = [
                AIXiangBaoBaoXing.xbbxId.in_(valid_to_delete_ids),
                AIXiangBaoBaoXing.del_flag == False
            ]
            if gsId != GETSOFT_ID:  #  补全租户隔离条件
                update_filter.insert(0, AIXiangBaoBaoXing.gsId == gsId)
            # 7. 执行软删除
            now = datetime.now().replace(microsecond=0)
            delete_count = db.query(AIXiangBaoBaoXing).filter(
                *update_filter
            ).update(
                {
                    AIXiangBaoBaoXing.del_flag: True,
                    AIXiangBaoBaoXing.up_userid: user_id,
                    AIXiangBaoBaoXing.up_time: now,
                    AIXiangBaoBaoXing.del_time: now
                },
                synchronize_session=False
            )

            # 8. 提交事务
            db.flush()
            return delete_count

        except ValidationException:
            # 重新抛出ValidationException
            raise
        except NotFoundException:
            # 重新抛出NotFoundException
            raise
        except Exception as e:
            # 回滚事务并抛出数据库异常
            raise DataUpdateFailedException(
                message="批量删除包型操作失败",
                details={
                    "error": str(e),
                }
            )
    @staticmethod
    def restore(
            db: Session,
            xbbxId: int,
            user_id:int,
    ) ->bool:
        """
        恢复已删除的包型

        Args:
            db: 数据库会话
            xbbxId: 包型ID
            user_id: 用户ID

        Returns:
            True如果恢复成功
        """
        try:
            xiangbaoBaoXing = db.query(orm_models.AIXiangBaoBaoXing).filter(
                and_(
                    orm_models.AIXiangBaoBaoXing.xbbxId == xbbxId,
                    orm_models.AIXiangBaoBaoXing.del_flag == True
                )
            ).first()

            if not xiangbaoBaoXing:
                raise NotFoundException(
                    message="包型不存在或未被删除",
                    details={"xbbxId": xbbxId}
                )
            #恢复操作
            xiangbaoBaoXing.del_flag = False
            xiangbaoBaoXing.up_userid = user_id
            xiangbaoBaoXing.del_time = None
            xiangbaoBaoXing.up_time = datetime.now()

            db.flush()
            return True
        except ValidationException as e:
            raise
        except NotFoundException as e:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="恢复包型操作失败",
                details={"error": str(e), "xbbxId": xbbxId}
            )

    @staticmethod
    def search_all(
            db: Session,
            gsId:int,
            keywords: Optional[str] = None,  # 统一修正为Optional[str]，规范类型注解
    ) -> List[Dict[str, Any]]:
        # 1. 关键词统一预处理：去空格、空字符串转None，兼容前端空输入（和部位/材质完全一致）
        keywords = keywords.strip() if (keywords and isinstance(keywords, str)) else None
        result_data = []

        # 2. 包型专属缓存常量（遵循统一命名规范：cache:业务模块:包型:全查）
        CACHE_KEY_XBBX_SEARCH_ALL = f"sys:gsId:{gsId}:AIXiangBaoBaoXing"
        CACHE_EXPIRE_SECONDS = 3600  # 统一1小时过期，和其他下拉栏保持一致

        # 3. 核心逻辑：优先从Redis取全量缓存，命中则内存过滤（不走数据库）
        try:
            cache_all_data = redis_get_sync(CACHE_KEY_XBBX_SEARCH_ALL, db=PAGE_DROPDOWN)
            if cache_all_data is not None and isinstance(cache_all_data, list):
                logger.debug(f"包型下拉栏：Redis缓存命中，全量数据共{len(cache_all_data)}条")
                # 无关键词：直接返回Redis全量数据
                if not keywords:
                    result_data = cache_all_data
                # 有关键词：内存模拟ilike做【大小写不敏感模糊匹配】（和数据库逻辑完全一致）
                else:
                    lower_key = keywords.lower()
                    result_data = [
                        item for item in cache_all_data
                        if lower_key in item.get("baoXingMingCheng", "").lower()
                    ]
                logger.debug(f"包型下拉栏：Redis内存过滤完成，关键词[{keywords}]，匹配结果{len(result_data)}条")
                return result_data  # 缓存命中直接返回，无需走数据库
        except redis.RedisError as e:
            logger.warning(f"包型下拉栏：Redis缓存读取失败，降级为数据库查询 | error={str(e)}")
        except Exception as e:
            logger.warning(f"包型下拉栏：Redis缓存解析失败，降级为数据库查询 | error={str(e)}")

        # 4. Redis失效/故障 → 降级到数据库处理（完全保留你原有核心代码）
        try:
            logger.info(f'gsId:{gsId}, keywords:{keywords}')
            # 基础查询：过滤未删除数据（你的原有代码）
            query = db.query(orm_models.AIXiangBaoBaoXing).filter(
                orm_models.AIXiangBaoBaoXing.del_flag == False,
                orm_models.AIXiangBaoBaoXing.gsId == gsId,
            )

            # 添加关键词过滤（保留你原有ilike大小写不敏感，你的代码不变）
            if keywords:
                query = query.filter(
                    orm_models.AIXiangBaoBaoXing.baoXingMingCheng.ilike(f"%{keywords}%")
                )

            # 执行查询+构建响应数据（完全保留你的原有代码，字段不变）
            results = query.all()
            db_all_data = []
            for result in results:
                item = {
                    "xbbxId": result.xbbxId,
                    "baoXingMingCheng": result.baoXingMingCheng,
                }
                db_all_data.append(item)
            logger.debug(f"包型下拉栏：数据库查询成功，共{len(db_all_data)}条")

            # 5. 仅无关键词时写入Redis缓存（关键词结果不缓存，避免Redis膨胀，和其他下拉栏一致）
            if not keywords:
                try:
                    redis_set_sync(
                        key=CACHE_KEY_XBBX_SEARCH_ALL,
                        value=db_all_data,
                        ex=CACHE_EXPIRE_SECONDS,
                        db=PAGE_DROPDOWN
                    )
                    logger.debug("包型下拉栏：数据库全量数据写入Redis缓存成功")
                except redis.RedisError as e:
                    logger.warning(f"包型下拉栏：写入Redis缓存失败 | error={str(e)}")

            # 赋值结果并返回
            result_data = db_all_data
            return result_data

        # 完全保留你原有异常处理逻辑，一行不改
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="查询包型操作失败：" + str(e)
            )

    # ------------------------------
    # 新增：包型专属缓存刷新方法
    # ------------------------------
    @staticmethod
    def refresh_search_all_cache(gsId:int) -> bool:
        """
        刷新包型下拉栏缓存（删除Redis缓存Key）
        【必用场景】：包型数据新增/修改/删除接口执行成功后立即调用，保证缓存和数据库数据一致
        :return: 是否删除成功
        """
        CACHE_KEY_XBBX_SEARCH_ALL = f"sys:gsId:{gsId}:AIXiangBaoBaoXing"
        try:
            delete_count = redis_delete_sync(CACHE_KEY_XBBX_SEARCH_ALL, db=PAGE_DROPDOWN)
            logger.info(f"包型下拉栏缓存：手动刷新成功，删除Redis Key数量={delete_count}")
            return delete_count > 0
        except redis.RedisError as e:
            logger.error(f"包型下拉栏缓存：手动刷新失败 | error={str(e)}")
            return False
        except Exception as e:
            logger.error(f"包型下拉栏缓存：手动刷新异常 | error={str(e)}")
            return False


