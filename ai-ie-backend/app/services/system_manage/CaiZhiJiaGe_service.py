import os
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from fastapi import Request
from loguru import logger

from app.schemas.system_manage.CaiZhiJiaGe_schema import (
    CaiZhiJiaGeSearchResponse,
    CaiZhiJiaGeGetSearchResponse,
    CaiZhiJiaGeUpdateRequest
)
from app.services.system_manage.CaiZhiJiaGe_crud import CaiZhiJiaGeCRUD
from app.services.system_manage.base_sys_service import BaseService
from app.services.user.user_crud import get_gsId_by_userid
from app.utils.exceptions import (
    NotFoundException,
    ValidationException,
    AppException,
    PermissionDeniedException
)

load_dotenv()
GETSOFT_ID_STR = os.getenv("GETSOFT_ID")
GETSOFT_ID = int(GETSOFT_ID_STR)


class CaiZhiJiaGeService(BaseService):
    """材质价格相关业务"""

    # ==========================================================================
    @classmethod
    def search_caiZhiJiaGe_admin(
            cls,
            request: Request,
            userid: int,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 10,
    ) -> Dict[str, Any]:
        """管理员搜索材质价格"""
        try:
            cls.mark_read_only(request)
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, userid)
            logger.info(f'gsId:{gsId}')

            clean_keyword = keyword.strip() if keyword else ""
            results, total = CaiZhiJiaGeCRUD.search_admin(
                db=db,
                gsId=gsId,
                keyword=clean_keyword,
                page=page,
                page_size=page_size
            )

            try:
                if gsId != GETSOFT_ID:
                    raise PermissionDeniedException(
                        message="非本公司所属用户"
                    )
                response_data = []
                for item_dict in results:
                    item = CaiZhiJiaGeGetSearchResponse.parse_obj(item_dict)
                    response_data.append(item)

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
                message="搜索材质价格失败，服务错误",
                details={"error": str(e)},
            )

    # ==========================================================================
    @classmethod
    def search_caiZhiJiaGe_user(
            cls,
            request: Request,
            userid: int,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 10,
    ) -> Dict[str, Any]:
        """普通用户搜索材质价格"""
        try:
            cls.mark_read_only(request)
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, userid)

            clean_keyword = keyword.strip() if keyword else ""
            results, total = CaiZhiJiaGeCRUD.search_user(
                db=db,
                gsId=gsId,
                keyword=clean_keyword,
                page=page,
                page_size=page_size
            )

            try:
                response_data = []
                for item_dict in results:
                    item = CaiZhiJiaGeSearchResponse.parse_obj(item_dict)
                    response_data.append(item)

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
                message="搜索材质价格失败，服务错误",
                details={"error": str(e)},
            )

    # ==========================================================================
    @classmethod
    def create_caiZhiJiaGe(
            cls,
            request: Request,
            caiZhiJiaGe_data: Dict[str, Any],
            user_id: int
    ) -> Optional[bool]:
        """创建材质价格"""
        try:
            db = cls.get_db_session(request)
            czjg = caiZhiJiaGe_data.get('czjg')
            xbczId = caiZhiJiaGe_data.get('xbczId')
            gsId = get_gsId_by_userid(db, user_id)

            # 检查同一公司下相同材质是否已存在
            existing = CaiZhiJiaGeCRUD.get_existing_by_record(db, gsId, xbczId)
            if existing:
                raise ValidationException(
                    message=f"公司所属的材质已存在",
                )

            new_caizhi = CaiZhiJiaGeCRUD.create(
                db=db,
                gsId=gsId,
                user_id=user_id,
                czjg=czjg,
                xbczId=xbczId
            )
            return new_caizhi
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="创建材质价格失败，服务错误",
                details={"error": str(e)}
            )

    # ==========================================================================
    @classmethod
    def update_caiZhiJiaGe(
            cls,
            request: Request,
            czjgId: int,
            user_id: int,
            update_data: CaiZhiJiaGeUpdateRequest
    ) -> Optional[bool]:
        """更新材质价格"""
        try:
            db = cls.get_db_session(request)
            update_dict = update_data.model_dump(exclude_unset=True)
            xbczId = update_dict.get('xbczId')
            czjg = update_dict.get('czjg')
            gsId = get_gsId_by_userid(db, user_id)

            # 获取原记录
            original = CaiZhiJiaGeCRUD.get_by_id(db=db, czjgId=czjgId, gsId=gsId)
            if not original:
                raise NotFoundException(message="材质价格不存在")

            # 如果更改了材质，检查新材质是否已存在
            if xbczId and xbczId != original.xbczId:
                existing = CaiZhiJiaGeCRUD.get_existing_by_record(
                    db=db, gsId=gsId, xbczId=xbczId, exclude_id=czjgId
                )
                if existing:
                    raise ValidationException(
                        message=f"公司下该材质已存在，无法更新"
                    )

            result = CaiZhiJiaGeCRUD.update(
                db=db,
                gsId=gsId,
                czjgId=czjgId,
                xbczId=xbczId if xbczId is not None else original.xbczId,
                czjg=czjg if czjg is not None else original.czjg,
                user_id=user_id,
            )
            return result
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="材质价格更新失败，服务错误",
                details={"error": str(e)}
            )

    # ==========================================================================
    @classmethod
    def restore_caiZhiJiaGe(
            cls,
            request: Request,
            czjgId: int,
            user_id: int
    ) -> Optional[bool]:
        """恢复已删除的材质价格"""
        try:
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, user_id)
            success = CaiZhiJiaGeCRUD.restore(
                db=db, czjgId=czjgId, user_id=user_id, gsId=gsId
            )
            return success
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="恢复材质价格失败，服务错误",
                details={"error": str(e)}
            )

    # ==========================================================================
    @classmethod
    def batch_delete_caiZhiJiaGe(
            cls,
            request: Request,
            czjg_ids: List[int],
            user_id: int
    ) -> Optional[int]:
        """批量软删除材质价格"""
        try:
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, user_id)
            result = CaiZhiJiaGeCRUD.batch_delete(
                db=db, czjgIds=czjg_ids, user_id=user_id, gsId=gsId
            )
            return result
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="批量删除材质价格失败，服务器内部错误",
                details={"error": str(e), "czjgIds": czjg_ids}
            )