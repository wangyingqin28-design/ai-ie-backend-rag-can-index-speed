import decimal
from typing import Dict, Any, Optional
from fastapi import Request
from sqlalchemy.orm import Session

from app.schemas.system_manage.LiShiGongJia_schema import LiShiGongJiaSearchResponse
from app.services.system_manage.BiaoZhunGongXu_service import GETSOFT_ID
from app.services.system_manage.LiShiGongJia_crud import LiShiGongJiaCRUD
from app.services.system_manage.base_sys_service import BaseService
from app.services.user.user_crud import get_gsId_by_userid
from app.utils.exceptions import AppException,PermissionDeniedException
from app.services.system_manage.base_sys_service import GETSOFT_ID

class LiShiGongJiaService(BaseService):
    """历史工价相关业务"""

    @classmethod
    def search_LiShiGongjia_user(
            cls,
            userid:int,
            request: Request,
            gjId:int,
            page: int = 1,
            page_size: int = 20
    ) -> Dict[str, Any]:
        """搜索历史工价"""
        try:
            # 标记为只读接口
            cls.mark_read_only(request)
            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, userid)
            # 调用CRUD层进行搜索（返回results和total）
            results, total = LiShiGongJiaCRUD.search_user(
                db=db,
                gjId=gjId,
                page=page,
                page_size=page_size,
                gsId=gsId
            )
            try:
                # 将字典列表转换为Pydantic模型列表
                response_items = []
                for item_dict in results:  # item_dict 是字典
                    # 使用model_validate从字典创建Pydantic模型
                    item_model = LiShiGongJiaSearchResponse.model_validate(item_dict)
                    response_items.append(item_model)
            except Exception as e:
                raise AppException(
                    code=500,
                    message="转换出错，请检查格式",
                    details={"error": str(e)}
                )
            result = cls.paginate_results(response_items, total, page, page_size)
            return result
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="搜索历史工价失败",
                details={"error": str(e)}
            )
    @classmethod
    def search_LiShiGongjia_admin(
            cls,
            userid:int,
            request: Request,
            gjId:int,
            page: int = 1,
            page_size: int = 20
    ) -> Dict[str, Any]:
        """搜索历史工价"""
        try:
            # 标记为只读接口
            cls.mark_read_only(request)
            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, userid)
            if gsId != GETSOFT_ID:
                raise PermissionDeniedException(
                    message="非本公司所属用户"
                )
            # 调用CRUD层进行搜索（返回results和total）
            results, total = LiShiGongJiaCRUD.search_admin(
                db=db,
                gjId=gjId,
                page=page,
                page_size=page_size,
            )
            try:
                # 将字典列表转换为Pydantic模型列表
                response_items = []
                for item_dict in results:  # item_dict 是字典
                    item_model = LiShiGongJiaSearchResponse.model_validate(item_dict)
                    response_items.append(item_model)
            except Exception as e:
                raise AppException(
                    code=500,
                    message="转换出错，请检查格式",
                    details={"error": str(e)}
                )

            result = cls.paginate_results(response_items, total, page, page_size)

            return result

        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="搜索历史工价失败",
                details={"error": str(e)}
            )
    def create_LiShiGongJia(
            db: Session,
            gjId: int,
            is_gongSi_gongJia: bool,
            user_id: int,
            gongJia: decimal.Decimal,
            bianGengYuanYin: Optional[str] = None,
    ):
        try:
            gsId = get_gsId_by_userid(db, user_id)
            LiShiGongJiaCRUD.create(
                db=db,
                gjId=gjId,
                gsId=gsId,
                is_gongSi_gongJia=is_gongSi_gongJia,
                gongJia=gongJia,
                bianGengYuanYin=bianGengYuanYin,
                user_id=user_id,
            )
            return True
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="创建历史工价服务失败",
                details={"error": str(e)}
            )