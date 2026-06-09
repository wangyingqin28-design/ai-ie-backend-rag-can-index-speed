# app/service/system_manage/XiangBaoGongZhong_service.py
import os
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from fastapi import Request
from loguru import logger
from app.models import orm_models
from app.schemas.system_manage.XiangBaoGongZhong_schema import XiangBaoGongZhongResponseBase, \
    XiangBaoGongZhongUpdateRequest
from app.services.system_manage.XiangBaoGongZhong_crud import XiangBaoGongZhongCRUD
from app.services.system_manage.base_sys_service import BaseService
from app.services.user.user_crud import get_gsId_by_userid
from app.utils.exceptions import NotFoundException, ValidationException, AppException,PermissionDeniedException
load_dotenv()
GETSOFT_ID_STR = os.getenv("GETSOFT_ID")
GETSOFT_ID = int(GETSOFT_ID_STR)

class XiangBaoGongZhongService(BaseService):
    """工种相关的业务服务"""
#==================================================================================
#======================================================================
#======================================================================
    @classmethod
    def search_XiangBaoGongZhong_admin(
            cls,
            userid : int,
            request: Request,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 10,
    ) -> Dict[str, Any]:
        """搜索工种"""
        try:
            # 标记为只读接口
            cls.mark_read_only(request)
            # 获取数据库会话
            db = cls.get_db_session(request)
            logger.info(f"用户ID为{userid}")
            gsId = get_gsId_by_userid(db=db, userid=userid)
            # 清理关键词
            clean_keyword = keyword.strip() if keyword else ""
            logger.info(f'公司ID为{gsId}')
            try:
                if gsId != GETSOFT_ID:
                    raise PermissionDeniedException(
                        message="非本公司所属用户"
                    )
            except PermissionDeniedException as e:
                raise e
            results, total = XiangBaoGongZhongCRUD.search_admin(
                db=db,
                keyword=clean_keyword,
                page=page,
                page_size=page_size,
            )
            # 直接传递Pydantic模型列表给paginate_results
            result = cls.paginate_results(results, total, page, page_size)
            # 添加搜索关键词字段
            result["search_keyword"] = clean_keyword
            return result
        # 先捕获具体的业务异常
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="搜索工种失败，服务错误",
                details={"error": str(e)},
            )
    # ==========================================================================
    # ======================================================================
    @classmethod
    def search_XiangBaoGongZhong_user(
            cls,
            userid: int,
            request: Request,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 10,
    ) -> Dict[str, Any]:
        """搜索工种"""
        try:
            # 标记为只读接口
            cls.mark_read_only(request)
            # 获取数据库会话
            db = cls.get_db_session(request)
            logger.info(f"用户ID为{userid}")
            gsId = get_gsId_by_userid(db=db, userid=userid)
            # 清理关键词
            clean_keyword = keyword.strip() if keyword else ""
            logger.info(f'公司ID为{gsId}')
            results, total = XiangBaoGongZhongCRUD.search_user(
                db=db,
                keyword=clean_keyword,
                page=page,
                page_size=page_size,
                gsId=gsId
            )
            # 直接传递Pydantic模型列表给paginate_results
            result = cls.paginate_results(results, total, page, page_size)
            # 添加搜索关键词字段
            result["search_keyword"] = clean_keyword
            return result
        except ValidationException:
            raise
        except NotFoundException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="搜索工种失败，服务错误",
                details={"error": str(e)},
            )
    # ==========================================================================
    @classmethod
    def create_xiangBaoGongZhong(
            cls,
            request: Request,
            user_id: int,
            gongZhongMingCheng:str,
    ) -> orm_models.AIXiangBaoGongZhong:
        """
        创建工种
        """
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, user_id)
            #  检查工种名称是否重复
            existing = XiangBaoGongZhongCRUD.get_existing_by_name(
                db=db,
                gongZhongMingCheng=gongZhongMingCheng,
                gsId=gsId,
            )
            if existing:
                raise ValidationException(
                    message=f"工种名称 '{gongZhongMingCheng}' 已存在",
                    details={
                        "conflict_field": "工种名称",
                        "conflict_value": gongZhongMingCheng,
                        "existing_id": existing.xbgzId
                    }
                )

            # 4. 创建新工种
            new_xiangBaoGongZhong = XiangBaoGongZhongCRUD.create(
                db=db,
                gongZhongMingCheng=gongZhongMingCheng,
                user_id=user_id,
                gsId=gsId,
            )
            response_data = XiangBaoGongZhongResponseBase.model_validate(new_xiangBaoGongZhong).dict()
            return response_data
        except ValidationException:
            raise
        except NotFoundException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="创建工种失败，服务器错误",
                details={"error": str(e)},
            )
    # ==========================================================================
    @classmethod
    def update_xiangBaoGongZhong(
            cls,
            request: Request,
            xbgzId: int,
            up_userid: int,
            update_data: XiangBaoGongZhongUpdateRequest
    ) -> orm_models.AIXiangBaoGongZhong:
        """
        更新工种信息
        """
        try:

            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, up_userid)
            logger.info(f'gsId:{gsId}')
            # 2. 检查是否要更新工种名称，并验证是否重复
            xiangBaoGongZhong = XiangBaoGongZhongCRUD.get_by_id(
                db=db,xbgzId=xbgzId,gsId=gsId)
            update_dict = update_data.dict(exclude_unset=True)  # 先转换为字典
            new_name = update_dict.get('gongZhongMingCheng')
            if new_name and new_name != xiangBaoGongZhong.gongZhongMingCheng:
                existing = XiangBaoGongZhongCRUD.get_existing_by_name(
                    db=db, gongZhongMingCheng=new_name, exclude_id=xbgzId,gsId=gsId
                )
                if existing:
                    raise ValidationException(
                        message=f"工种名称 '{new_name}' 已存在",
                        details={
                            "conflict_field": "gongZhongMingCheng",
                            "conflict_value": new_name,
                        }
                    )
            # 4. 调用CRUD层更新
            updated_xiangBaoGongZhong = XiangBaoGongZhongCRUD.update(
                db=db,
                xbgzId=xbgzId,
                update_data=update_dict,
                up_userid=up_userid,
                gsId=gsId
            )

            try:
                item = XiangBaoGongZhongResponseBase.model_validate(updated_xiangBaoGongZhong).dict()
            except Exception as e:
                raise AppException(
                    code=500,
                    message="model_validate转换出错"
                )
            return item
        except ValidationException:
            raise
        except NotFoundException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="更新工种失败，服务错误",
                details={"error": str(e)},
            )
    # ==========================================================================
    @classmethod
    def restore_xiangBaoGongZhong(
            cls,
            request: Request,
            xbgzId: int,
            user_id: int
    ) -> bool:
        """
        恢复已删除的工种
        """
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, user_id)
            # 调用CRUD层进行恢复
            success = XiangBaoGongZhongCRUD.restore(db=db, xbgzId=xbgzId, user_id=user_id,gsId=gsId)

            if success:
                return True

            return False

        except ValidationException:
            raise
        except NotFoundException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="恢复工种失败，服务错误",
                details={"error": str(e)},
            )
    # ==========================================================================
    @classmethod
    def batch_delete_xiangBaoGongZhong(
            cls,
            request: Request,
            xbgz_ids: List[int],
            user_id: int
    ) -> int:
        """
        批量软删除工种
        """
        try:
            # 参数校验
            if not xbgz_ids:
                raise ValidationException(
                    message="工种ID列表不能为空",
                    details={"xbgz_ids": xbgz_ids}
                )
            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, user_id)
            # 调用CRUD层进行批量删除
            result = XiangBaoGongZhongCRUD.batch_delete(db=db, xbgzIds=xbgz_ids, user_id=user_id,gsId=gsId)
            return result

        except ValidationException:
            raise
        except NotFoundException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="批量删工种失败，服务错误",
                details={"error": str(e)},
            )
    #===========================================================================
    @classmethod
    def search_all_xiangBaoGongZhong(
            cls,
            userid:int,
            request: Request,
            keywords: str = None  # 保持一致性
    ) -> List[Dict[str, Any]]:  # 修正返回类型
        """
        下拉栏搜索包型
        """
        try:
            # 标记为只读
            cls.mark_read_only(request)
            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, userid)

            response = XiangBaoGongZhongCRUD.search_all(db=db, keywords=keywords,gsId=gsId)
            return response
        except ValidationException:
            raise
        except NotFoundException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="搜索工种下拉栏服务失败，服务错误",
                details={"error": str(e)},
            )


