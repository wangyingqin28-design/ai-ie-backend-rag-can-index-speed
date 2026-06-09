import os
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from fastapi import Request
from loguru import logger

from app.schemas.system_manage.GongSiGongJia_schema import GongSiGongJiaSearchResponse, \
    GongSiGongJiaGetSearchResponse
from app.schemas.system_manage.GongSiGongJia_schema import GongSiGongJiaUpdateRequest
from app.services.system_manage.GongSiGongJia_crud import GongSiGongJiaCRUD
from app.services.system_manage.LiShiGongJia_crud import LiShiGongJiaCRUD
from app.services.system_manage.base_sys_service import BaseService
from app.services.user.user_crud import get_gsId_by_userid
from app.utils.exceptions import NotFoundException, ValidationException, AppException, PermissionDeniedException
load_dotenv()
GETSOFT_ID_STR = os.getenv("GETSOFT_ID")
GETSOFT_ID = int(GETSOFT_ID_STR)

class GongSiGongJiaService(BaseService):
    """公司工价相关业务"""
    # ==========================================================================
    @classmethod
    def search_gongSiGongjia_admin(
            cls,
            request: Request,
            userid:int,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 10,
    ) -> Dict[str, Any]:
        """搜索公司工价"""
        try:
            # 标记为只读接口
            cls.mark_read_only(request)
            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, userid)
            logger.info(f'gsId:{gsId}')
            # 清理关键词
            clean_keyword = keyword.strip() if keyword else ""
            # 调用CRUD层进行搜索（返回results和total）
            results, total = GongSiGongJiaCRUD.search_admin(
                db=db,
                gsId=gsId,
                keyword=clean_keyword,
                page=page,
                page_size=page_size
            )
            # 在业务逻辑层转换
            try:

                if gsId != GETSOFT_ID:
                    raise PermissionDeniedException(
                        message="非本公司所属用户"
                    )
                response_data = []
                for gongSiGongJia_dict in results:
                    # 确保字典包含所有必要字段
                    item = GongSiGongJiaGetSearchResponse.parse_obj(gongSiGongJia_dict)
                    response_data.append(item)

                # 使用paginate_results
                result = cls.paginate_results(response_data, total, page, page_size)
            except PermissionDeniedException:
                raise
            except Exception as e:
                raise AppException(
                    code=500,
                    message="model_validate转换出错，请检查格式",
                    details={"error": str(e)}
                )
            result["search_keyword"] = clean_keyword
            return result
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="搜索公司工价失败，服务错误",
                details={"error": str(e)},
            )
    # ==========================================================================
    # ==========================================================================
    @classmethod
    def search_gongSiGongjia_user(
            cls,
            request: Request,
            userid: int,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 10,
    ) -> Dict[str, Any]:
        """搜索公司工价"""
        try:
            # 标记为只读接口
            cls.mark_read_only(request)
            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, userid)
            # 清理关键词
            clean_keyword = keyword.strip() if keyword else ""

            # 调用CRUD层进行搜索（返回results和total）
            results, total = GongSiGongJiaCRUD.search_user(
                db=db,
                gsId=gsId,
                keyword=clean_keyword,
                page=page,
                page_size=page_size
            )

            # 在业务逻辑层转换
            try:
                response_data = []
                for gongSiGongJia_dict in results:
                    # 确保字典包含所有必要字段
                    item = GongSiGongJiaSearchResponse.parse_obj(gongSiGongJia_dict)
                    response_data.append(item)

                # 使用paginate_results
                result = cls.paginate_results(response_data, total, page, page_size)
            except Exception as e:
                raise AppException(
                    code=500,
                    message="model_validate转换出错，请检查格式",
                    details={"error": str(e)}
                )
            result["search_keyword"] = clean_keyword
            return result
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="搜索公司工价失败，服务错误",
                details={"error": str(e)},
            )
    # ==========================================================================
    # ==========================================================================
    # ==========================================================================
    @classmethod
    def create_gongSiGongjia(
            cls,
            request: Request,
            gongSiGongjia_data: Dict[str, Any],
            user_id: int
    ) -> Optional[bool]:
        """
        创建标准公司工价
        """
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)
            gongJia = gongSiGongjia_data.get('gongJia')
            gsgjId = gongSiGongjia_data.get('gsgjId')
            xbgzId = gongSiGongjia_data.get('xbgzId')
            gsId = get_gsId_by_userid(db, user_id)
            #  检查gsId是否重复
            existing =GongSiGongJiaCRUD.get_existing_by_record(db, gsId, xbgzId)
            if existing:
                raise ValidationException(
                    message=f"公司所属的工种已存在",
                )
            # 4. 创建新公司工价
            new_gongSiGongjia =GongSiGongJiaCRUD.create(
                db=db,
                gsId=gsId,
                user_id=user_id,
                gongJia=gongJia,
                xbgzId=xbgzId
            )

            LiShiGongJiaCRUD.create(db=db,gjId=gsgjId,is_gongSi_gongJia=True,gongJia=gongJia,user_id=user_id,bianGengYuanYin="初始值",gsId=gsId)
            return new_gongSiGongjia
        except AppException:
            raise
        except Exception as e:
            # 未知异常记录日志并返回500错误
            raise AppException(
                code=500,
                message="创建公司工价失败，服务错误",
                details={"error": str(e)}
            )
    # ==========================================================================
    @classmethod
    def update_gongSiGongjia(
            cls,
            request: Request,
            gsgjId: int,
            user_id: int,
            update_data:GongSiGongJiaUpdateRequest
    ) -> Optional[bool]:
        """
        更新公司工价信息
        """
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)
            # 2. 检查是否要更新gsId，并验证是否重复
            update_dict = update_data.model_dump(exclude_unset=True)  # 先转换为字典
            xbgzId = update_dict.get('xbgzId')
            gongJia = update_dict.get('gongJia')
            bianGengYuanYin = update_dict.get('bianGengYuanYin')
            gsId = get_gsId_by_userid(db, user_id)
            gongSiGongjia =GongSiGongJiaCRUD.get_by_id(db=db, gsgjId=gsgjId, gsId=gsId)
            if gsId and gsId != gongSiGongjia.gsId:
                existing =GongSiGongJiaCRUD.get_existing_by_record(
                    db=db, gsId=gsId, gsgjId=gsgjId
                )
            # 4. 调用CRUD层更新
            result =GongSiGongJiaCRUD.update(
                db=db,
                gsgjId=gsgjId,
                xbgzId=xbgzId,
                user_id=user_id,
                gongJia=gongJia,
                gsId=gsId,
            )
            LiShiGongJiaCRUD.create(
                db=db,
                gjId=gsgjId,
                is_gongSi_gongJia=True,
                user_id=user_id,
                gongJia=gongJia,
                bianGengYuanYin=bianGengYuanYin,
                gsId=gsId)
            return result
        except AppException:
            raise
        except Exception as e:
            # 未知异常记录日志并返回500错误
            raise AppException(
                code=500,
                message="公司工价更新失败，服务错误",
                details={"error": str(e)}
            )
    # ==========================================================================
    # ==========================================================================
    @classmethod
    def restore_GongSiGongJia(
            cls,
            request: Request,
            gsgjId: int,
            user_id: int
    ) -> Optional[bool]:
        """
        恢复已删除的公司工价
        """
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, user_id)
            # 调用CRUD层进行恢复
            success =GongSiGongJiaCRUD.restore(
                db=db, gsgjId=gsgjId, user_id=user_id, gsId=gsId)
            if success:
                return True
            return False
        except AppException:
            raise
        except Exception as e:
            # 未知异常记录日志并返回500错误
            raise AppException(
                code=500,
                message="恢复公司工价失败，服务错误",
                details={"error": str(e)}
            )
    # ==========================================================================
    @classmethod
    def batch_delete_gongSiGongjia(
            cls,
            request: Request,
            gsgj_ids: List[int],
            user_id: int
    ) -> Optional[int]:
        """
        批量软删除标准公司工价
        """
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db,user_id)
            # 调用CRUD层进行批量删除
            result =GongSiGongJiaCRUD.batch_delete(
                db=db,gsgjIds=gsgj_ids,user_id=user_id,gsId=gsId)
            return result
        except AppException:
            raise
        except Exception as e:
            # 未知异常记录日志并返回500错误
            raise AppException(
                code=500,
                message="批量删除公司工价失败，服务器内部错误",
                details={"error": str(e), "gsgjIds": gsgj_ids}
            )
    # ===========================================================================
