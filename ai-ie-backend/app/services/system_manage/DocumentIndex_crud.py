from typing import Optional, List, Tuple

from sqlalchemy import desc
from sqlalchemy.orm import Session, aliased

from app.models import orm_models, models
from app.utils.exceptions import (
    NotFoundException, AppException
)


class DocumentIndexCRUD:
    """箱包规则操作类"""
    #=============================================================
    @staticmethod
    def get_by_id_user(
            db: Session,
            gsId:int,
            id: str,  # 修正为字符串类型
    ) -> dict:
        """
        根据ID获取规则详情（包含用户信息）

        Args:
            db: 数据库会话
            id: 规则ID (字符串类型)

        Returns:
            包含详情的字典
        """
        try:
            # 创建用户表的别名
            insert_user = aliased(orm_models.AIGongSiYongHu)
            update_user = aliased(orm_models.AIGongSiYongHu)

            # 构建查询
            query = db.query(
                models.DocumentIndex,
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name')
            ).outerjoin(
                insert_user,
                models.DocumentIndex.user_id == insert_user.gsyhId
            ).outerjoin(
                update_user,
                models.DocumentIndex.update_user_id == update_user.gsyhId
            ).filter(models.DocumentIndex.id == id,
                     models.DocumentIndex.enterprise_id == gsId)

            result = query.first()

            if not result:
                raise NotFoundException(f"ID为 {id} 的规则不存在")

            record, insert_user_name, update_user_name = result

            # 正确处理枚举类型，转换为值或名称
            status_value = record.status.value if hasattr(record.status, 'value') else str(record.status)

            item = {
                "id": record.id,
                "rule_type": record.rule_type,
                "rule": record.rule,
                "status": status_value,
                "insert_user_name": insert_user_name,  # 添加查询到的用户名
                "update_user_name": update_user_name  # 添加查询到的用户名
            }
            return item
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="规则获取失败",
                details={"error": str(e)}
            )
    #=============================================================
    @staticmethod
    def get_by_id_admin(
            db: Session,
            id: str,  # 修正为字符串类型
    ) -> dict:
        """
        根据ID获取规则详情（包含用户信息）

        Args:
            db: 数据库会话
            id: 规则ID (字符串类型)

        Returns:
            包含详情的字典
        """
        try:
            # 创建用户表的别名
            insert_user = aliased(orm_models.AIGongSiYongHu)
            update_user = aliased(orm_models.AIGongSiYongHu)

            # 构建查询
            query = db.query(
                models.DocumentIndex,
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name')
            ).outerjoin(
                insert_user,
                models.DocumentIndex.user_id == insert_user.gsyhId
            ).outerjoin(
                update_user,
                models.DocumentIndex.update_user_id == update_user.gsyhId
            ).filter(models.DocumentIndex.id == id)

            result = query.first()

            if not result:
                raise NotFoundException(f"ID为 {id} 的规则不存在")

            record, insert_user_name, update_user_name = result

            # 正确处理枚举类型，转换为值或名称
            status_value = record.status.value if hasattr(record.status, 'value') else str(record.status)

            item = {
                "id": record.id,
                "rule_type": record.rule_type,
                "rule": record.rule,
                "status": status_value,
                "insert_user_name": insert_user_name,  # 添加查询到的用户名
                "update_user_name": update_user_name  # 添加查询到的用户名
            }
            return item
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="规则获取失败",
                details={"error": str(e)}
            )

    #=============================================================
    @staticmethod
    def search_user(
            db: Session,
            enterprise_id: int,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 10,
    ) -> Tuple[List[dict], int]:
        """
        搜索公司箱包规则（返回分页数据列表和总数）
        """
        try:
            # 1. 检查公司是否存在
            company = db.query(orm_models.AIGongSi).filter(
                orm_models.AIGongSi.gsId == enterprise_id
            ).first()

            if not company:
                raise NotFoundException(
                    message="未找到公司",
                    details={"公司ID": enterprise_id}
                )
            company = db.query(models.DocumentIndex).filter(
                models.DocumentIndex.enterprise_id == enterprise_id
            ).first()
            if not company:
                raise NotFoundException(
                    message="未找到公司",
                    details={"公司ID": enterprise_id}
                )

            # 2. 创建用户表的别名
            insert_user = aliased(orm_models.AIGongSiYongHu)
            update_user = aliased(orm_models.AIGongSiYongHu)
            rule_type = aliased(models.RuleType)

            # 3. 构建基础查询，过滤软删除记录
            query = (db.query(
                models.DocumentIndex,
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name'),
                rule_type.rule_type.label('rule_type_name'),
            ).outerjoin(
                insert_user,
                models.DocumentIndex.user_id == insert_user.gsyhId
            ).outerjoin(
                update_user,
                models.DocumentIndex.update_user_id == update_user.gsyhId
            ).outerjoin(
                rule_type,
                models.DocumentIndex.rule_type == rule_type.id
            ).
            filter(
                models.DocumentIndex.enterprise_id == enterprise_id,
                models.DocumentIndex.gmt_deleted.is_(None)
            )
            )


            # 4. 关键词搜索
            if keyword and keyword.strip():
                clean_keyword = keyword.strip()
                query = query.filter(
                    models.DocumentIndex.rule.ilike(f"%{clean_keyword}%")
                )

            # 5. 获取总数（在应用排序和分页前）
            total = query.count()

            # 6. 排序和分页
            query = query.order_by(desc(models.DocumentIndex.gmt_updated))

            # 验证分页参数

            offset = (page - 1) * page_size
            results = query.offset(offset).limit(page_size).all()

            # 7. 转换为字典
            result_list = []
            for record, insert_user_name, update_user_name,rule_type_name in results:
                # 处理枚举类型
                status_value = record.status.value if hasattr(record.status, 'value') else str(record.status)

                item = {
                    "id": record.id,
                    "rule_type": record.rule_type,
                    "rule_type_name":rule_type_name or "未分类",
                    "rule": record.rule,
                    "status": status_value,
                    "user_id": record.user_id,
                    "gmt_created": record.gmt_created.isoformat() if record.gmt_created else None,
                    "update_user_id": record.update_user_id,
                    "gmt_updated": record.gmt_updated.isoformat() if record.gmt_updated else None,
                    "in_user_name": insert_user_name or "无注册",
                    "up_user_name": update_user_name or "无注册",
                }
                result_list.append(item)

            return result_list, total

        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="查询箱包规则失败",
                details={
                    "error": str(e),
                    "operation": "DocumentIndex_crud.search"
                }
            )
    @staticmethod
    def search_admin(
            db: Session,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 10,
    ) -> Tuple[List[dict], int]:
        """
        搜索公司箱包规则（返回分页数据列表和总数）
        """
        try:
            # 2. 创建用户表的别名
            insert_user = aliased(orm_models.AIGongSiYongHu,name='insert_user')
            update_user = aliased(orm_models.AIGongSiYongHu,name='update_user')
            rule_type = aliased(models.RuleType,name='rule_type')
            gongSi = aliased(orm_models.AIGongSi,name='gongSi')

            # 3. 构建基础查询，过滤软删除记录
            query = (db.query(
                models.DocumentIndex,
                insert_user.yongHuXingMing.label('insert_user_name'),
                update_user.yongHuXingMing.label('update_user_name'),
                rule_type.rule_type.label('rule_type_name'),
                gongSi.gongSiQuanCheng.label('gongSi_name'),

            ).outerjoin(
                insert_user,
                models.DocumentIndex.user_id == insert_user.gsyhId
            ).outerjoin(
                update_user,
                models.DocumentIndex.update_user_id == update_user.gsyhId
            ).outerjoin(
                rule_type,
                models.DocumentIndex.rule_type == rule_type.id
            ).outerjoin(
                gongSi,
                models.DocumentIndex.enterprise_id == gongSi.gsId
            ).
            filter(
                models.DocumentIndex.gmt_deleted.is_(None)
            )
            )


            # 4. 关键词搜索
            if keyword and keyword.strip():
                clean_keyword = keyword.strip()
                query = query.filter(
                    models.DocumentIndex.rule.ilike(f"%{clean_keyword}%")
                )

            # 5. 获取总数（在应用排序和分页前）
            total = query.count()

            # 6. 排序和分页
            query = query.order_by(desc(models.DocumentIndex.gmt_updated))

            # 验证分页参数

            offset = (page - 1) * page_size
            results = query.offset(offset).limit(page_size).all()

            # 7. 转换为字典
            result_list = []
            for record, insert_user_name, update_user_name,rule_type_name,gongSi_name in results:
                # 处理枚举类型
                status_value = record.status.value if hasattr(record.status, 'value') else str(record.status)

                item = {
                    "id": record.id,
                    "rule_type": record.rule_type,
                    "rule_type_name":rule_type_name or "未分类",
                    "rule": record.rule,
                    "status": status_value,
                    "user_id": record.user_id,
                    "gmt_created": record.gmt_created.isoformat() if record.gmt_created else None,
                    "update_user_id": record.update_user_id,
                    "gmt_updated": record.gmt_updated.isoformat() if record.gmt_updated else None,
                    "in_user_name": insert_user_name or "无注册",
                    "up_user_name": update_user_name or "无注册",
                    "gongSi":gongSi_name if gongSi_name else "公司无注册",
                }
                result_list.append(item)

            return result_list, total

        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="查询箱包规则失败",
                details={
                    "error": str(e),
                    "operation": "DocumentIndex_crud.search"
                }
            )