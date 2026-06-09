import decimal
from typing import Optional, List, Dict, Any
from fastapi import Request
from app.models import orm_models
from app.schemas.system_manage.QuYuGongJia_schema import QuYuGongJiaResponseBase, QuYuGongJiaSearchResponse
from app.schemas.system_manage.QuYuGongJia_schema import QuYuGongJiaUpdateRequest
from app.services.system_manage.LiShiGongJia_crud import LiShiGongJiaCRUD
from app.services.system_manage.QuYuGongJia_crud import QuYuGongJiaCRUD
from app.services.system_manage.base_sys_service import BaseService
from app.services.user.user_crud import get_gsId_by_userid
from app.utils.exceptions import NotFoundException, ValidationException, AppException, DataUpdateFailedException

class QuYuGongJiaService(BaseService):
    """区域工价相关业务"""
    # ==========================================================================
    # ==========================================================================
    # ==========================================================================
    @classmethod
    def search_quYuGongJia(
            cls,
            request: Request,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 20
    ) -> Dict[str, Any]:
        """搜索区域工价"""
        try:
            # 标记为只读接口
            cls.mark_read_only(request)
            # 获取数据库会话
            db = cls.get_db_session(request)

            # 清理关键词
            clean_keyword = keyword.strip() if keyword else ""

            # 调用CRUD层进行搜索（返回results和total）
            results, total = QuYuGongJiaCRUD.search(
                db=db,
                keyword=clean_keyword,  # 添加关键词参数
                page=page,
                page_size=page_size,
            )

            # 将字典列表转换为Pydantic模型列表
            try:
                response_items = []
                for item_dict in results:
                    # 使用parse_obj从字典创建Pydantic模型
                    item_model = QuYuGongJiaSearchResponse.parse_obj(item_dict)
                    response_items.append(item_model)
            except Exception as e:
                raise AppException(
                    code=500,
                    message="转换出错，请检查格式",
                    details={"error": str(e)}
                )

            result = cls.paginate_results(response_items, total, page, page_size)

            # 添加搜索关键词字段
            result["search_keyword"] = clean_keyword

            return result

        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="搜索区域工价失败,服务错误",
                details={"error": str(e)}
            )
    # ==========================================================================
    @classmethod
    def create_quYuGongJia(
            cls,
            request: Request,
            quYuGongJia_data: Dict[str, Any],
            user_id: int
    ) -> orm_models.AIQuYuGongJia:
        """
        创建标准区域工价
        """
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)
            qygjId = quYuGongJia_data.get("qygjId")
            dqbmId = quYuGongJia_data.get('dqbmId')
            xbgzId = quYuGongJia_data.get('xbgzId')
            gongJia = quYuGongJia_data.get('gongJia')
            gsId = get_gsId_by_userid(db, user_id)
            #  检查地区编码是否重复
            existing = QuYuGongJiaCRUD.get_existing_by_record(db, dqbmId,xbgzId)
            if existing:
                raise ValidationException(
                    message=f"地区编码与工种定义的区域工价已存在",
                    details={
                        "冲突的地区编码":dqbmId,
                        "冲突的工种":xbgzId,
                        "存在的区域工价": existing.qygjId
                    }
                )

            # 4. 创建新区域工价
            new_quYuGongJia = QuYuGongJiaCRUD.create(
                db=db,
                dqbmId=dqbmId,
                user_id=user_id,
                gongJia=gongJia,
                xbgzId=xbgzId
            )

            response_data = QuYuGongJiaResponseBase.model_validate(new_quYuGongJia).dict()
            LiShiGongJiaCRUD.create(db=db,gjId=qygjId,is_gongSi_gongJia=False,user_id=user_id,gongJia=gongJia,bianGengYuanYin="初始值",gsId=gsId)

            return response_data
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="创建区域工价失败，服务错误",
                details={"error":str(e)}
            )
    # ==========================================================================
    @classmethod
    def update_quYuGongJia(
            cls,
            request: Request,
            qygjId: int,
            user_id: int,
            update_data: QuYuGongJiaUpdateRequest
    ) -> orm_models.AIQuYuGongJia:
        """
        更新区域工价信息
        """
        try:

            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, user_id)
            # 2. 检查是否要更新地区编码，并验证是否重复
            quYuGongJia = QuYuGongJiaCRUD.get_by_id(db, qygjId, include_deleted=False)
            update_dict = update_data.model_dump(exclude_unset=True)  # 先转换为字典
            new_dqbmId = update_dict.get('dqbmId')
            xbgzId = update_dict.get('xbgzId')
            gongJia = update_dict.get('gongJia')
            bianGengYuanYin = update_dict.get('bianGengYuanYin')
            if new_dqbmId and new_dqbmId != quYuGongJia.dqbmId:
                existing = QuYuGongJiaCRUD.get_existing_by_record(
                    db, new_dqbmId,xbgzId, exclude_id=qygjId
                )
                if existing:
                    raise ValidationException(
                        message=f"地区编码与工种定义的区域工价已存在",
                        details={
                            "冲突的地区编码": new_dqbmId,
                            "冲突的工种": xbgzId,
                            "存在的区域工价": existing.qygjId
                        }
                    )
            # 4. 调用CRUD层更新
            updated_quYuGongJia = QuYuGongJiaCRUD.update(
                db=db,
                qygjId=qygjId,
                update_data=update_dict,
                user_id=user_id,
                gongJia=gongJia
            )

            try:
                item = QuYuGongJiaResponseBase.model_validate(updated_quYuGongJia).dict()
            except Exception as e:
                raise AppException(
                    code=500,
                    message="转换出错"
                )

            LiShiGongJiaCRUD.create(db=db,gjId=qygjId,is_gongSi_gongJia=False,user_id=user_id,gongJia=gongJia,bianGengYuanYin=bianGengYuanYin,gsId=gsId)
            return item

        except AppException:
            raise
        except Exception as e:
            # 未知异常记录日志并返回500错误
            raise AppException(
                code=500,
                message="更新区域工价失败，服务错误",
                details={"error": str(e)}
            )
        
    # ==========================================================================
    # ==========================================================================
    @classmethod
    def restore_QuYuGongJia(
            cls,
            request: Request,
            qygjId: int,
            user_id: int
    ) -> bool:
        """
        恢复已删除的区域工价
        """
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)

            # 调用CRUD层进行恢复
            success = QuYuGongJiaCRUD.restore(db, qygjId, user_id)

            if success:
                return True

            return False
        except AppException:
            raise
        except Exception as e:
            # 未知异常记录日志并返回500错误
            raise AppException(
                code=500,
                message="恢复区域工价失败，服务错误",
                details={"error": str(e)}
            )
    # ==========================================================================
    @classmethod
    def batch_delete_quYuGongJia(
            cls,
            request: Request,
            qygj_ids: List[int],
            user_id: int
    ) -> int:
        """
        批量软删除标准区域工价
        """
        try:
            # 参数校验
            if not qygj_ids:
                raise ValidationException(
                    message="区域工价ID列表不能为空",
                    details={"qygj_ids": qygj_ids}
                )
            # 获取数据库会话
            db = cls.get_db_session(request)
            # 调用CRUD层进行批量删除
            result = QuYuGongJiaCRUD.batch_delete(db, qygj_ids, user_id)
            return result

        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="批量删除服务失败，服务错误",
                details={"error": str(e)}
            )
    #===========================================================================

