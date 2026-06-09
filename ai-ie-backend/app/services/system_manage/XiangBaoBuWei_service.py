# app/service/system_manage/XiangBaoBuWei_service.py
from typing import Optional, List, Dict, Any
from fastapi import Request, Body
from app.models import orm_models
from app.schemas.system_manage.XiangBaoBuWei_schema import XiangBaoBuWeiCreateRequest, XiangBaoBuWeiSearchResponse, \
    XiangBaoBuWeiResponseBase, XiangBaoBuWeiGetSearchResponse
from app.services.system_manage.BiaoZhunGongXu_service import GETSOFT_ID
from app.services.system_manage.XiangBaoBuWei_crud import XiangBaoBuWeiCRUD
from app.services.system_manage.base_sys_service import BaseService
from app.services.user.user_crud import get_gsId_by_userid
from app.utils.exceptions import NotFoundException, ValidationException, AppException, PermissionDeniedException


class XiangBaoBuWeiService(BaseService):
    """部位相关的业务服务"""
#==================================================================================
    #======================================================================
    @classmethod
    def search_XiangBaoBuWei_admin(
            cls,
            userid:int,
            request: Request,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 10,
    ) -> Dict[str, Any]:
        """搜索部位"""
        try:
            #标记为只读接口
            cls.mark_read_only(request)
            #获取数据会话
            db = cls.get_db_session(request)
            #清理关键词
            clean_keyword = keyword.strip() if keyword else ""
            gsId = get_gsId_by_userid(db, userid)
            if gsId != GETSOFT_ID:
                raise PermissionDeniedException(
                    message="非本公司所属用户"
                )

            #调用CRUD层进行搜索（返回result和total）
            results,total = XiangBaoBuWeiCRUD.search_admin(
                db=db,
                keyword=clean_keyword,
                page=page,
                page_size=page_size
            )

            #使用paginate_results
            result = cls.paginate_results(results,total,page, page_size)

            result["search_keyword"] = clean_keyword
            #在业务逻辑层转换
            try:
                response_data = []
                for xiangBaoBuWei in result["items"]:
                    item = XiangBaoBuWeiGetSearchResponse.model_validate(xiangBaoBuWei)
                    response_data.append(item)
                    result["items"] = response_data
            except Exception as e:
                raise AppException(
                    code=500,
                    message="model_validate转换出错，请检查格式",
                    details={"error": str(e)}
                )
            return result
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="搜索部位失败，服务错误",
                details={"error": str(e)},
            )
    @classmethod
    def search_XiangBaoBuWei_user(
            cls,
            userid:int,
            request: Request,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 10,
    ) -> Dict[str, Any]:
        """搜索部位"""
        try:
            #标记为只读接口
            cls.mark_read_only(request)
            #获取数据会话
            db = cls.get_db_session(request)
            #清理关键词
            clean_keyword = keyword.strip() if keyword else ""
            gsId = get_gsId_by_userid(db, userid)

            #调用CRUD层进行搜索（返回result和total）
            results,total = XiangBaoBuWeiCRUD.search_user(
                db=db,
                keyword=clean_keyword,
                page=page,
                page_size=page_size,
                gsId=gsId
            )

            #使用paginate_results
            result = cls.paginate_results(results,total,page, page_size)

            result["search_keyword"] = clean_keyword
            #在业务逻辑层转换
            try:
                response_data = []
                for xiangBaoBuWei in result["items"]:
                    item = XiangBaoBuWeiSearchResponse.model_validate(xiangBaoBuWei)
                    response_data.append(item)
                    result["items"] = response_data
            except Exception as e:
                raise AppException(
                    code=500,
                    message="model_validate转换出错，请检查格式",
                    details={"error": str(e)}
                )
            return result
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="搜索部位失败，服务器内部错误",
                details={"error": str(e)},
            )
    # ==========================================================================
    @classmethod
    def create_xiangBaoBuWei(
            cls,
            request: Request,
            xiangBaoBuWei_data:XiangBaoBuWeiCreateRequest = Body(...,description="部位数据"),
    ) -> orm_models.AIXiangBaoBuWei:
        """
        创建部位
        """
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)
            data_dict =xiangBaoBuWei_data.dict()
            buWeiMingCheng = data_dict.get("buWeiMingCheng")
            userid = xiangBaoBuWei_data.in_userid
            gsId = get_gsId_by_userid(db, userid)




            #  检查部位名称是否重复
            existing = XiangBaoBuWeiCRUD.get_existing_by_name(db=db, buWeiMingCheng=buWeiMingCheng,gsId=gsId)
            if existing:
                raise ValidationException(
                    message=f"部位名称 '{buWeiMingCheng}' 已存在",
                    details={
                        "conflict_value": buWeiMingCheng,
                    }
                )

            # 4. 创建新部位
            new_xiangBaoBuWei = XiangBaoBuWeiCRUD.create(
                db=db,
                buWeiMingCheng=buWeiMingCheng,
                user_id=xiangBaoBuWei_data.in_userid,
                gsId=gsId
            )

            response_data = XiangBaoBuWeiResponseBase.model_validate(new_xiangBaoBuWei).dict()

            return response_data
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="创建部位失败，服务器内部错误",
                details={"error": str(e)},
            )
    # ==========================================================================
    from app.schemas.system_manage.XiangBaoBuWei_schema import XiangBaoBuWeiUpdateRequest
    @classmethod
    def update_xiangBaoBuWei(
            cls,
            request: Request,
            xbbwId: int,
            user_id: int,
            update_data: XiangBaoBuWeiUpdateRequest
    ) -> orm_models.AIXiangBaoBuWei:
        """
        更新部位信息
        """
        try:

            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, user_id)
            # 2. 检查是否要更新部位名称，并验证是否重复
            xiangBaoBuWei = XiangBaoBuWeiCRUD.get_by_id(db=db, xbbwId=xbbwId, include_deleted=False,gsId=gsId)
            update_dict = update_data.dict(exclude_unset=True)  # 先转换为字典
            new_name = update_dict.get('buWeiMingCheng')
            if new_name and new_name != xiangBaoBuWei.buWeiMingCheng:
                existing = XiangBaoBuWeiCRUD.get_existing_by_name(
                    db=db,buWeiMingCheng=new_name, exclude_id=xbbwId,gsId=gsId
                )
                if existing:
                    raise ValidationException(
                        message=f"部位名称 '{new_name}' 已存在",
                        details={
                            "conflict_value": new_name,
                        }
                    )
            # 4. 调用CRUD层更新
            updated_xiangBaoBuWei = XiangBaoBuWeiCRUD.update(
                db=db,
                xbbwId=xbbwId,
                update_data=update_dict,
                user_id=user_id,
                gsId=gsId
            )

            try:
                item = XiangBaoBuWeiResponseBase.model_validate(updated_xiangBaoBuWei).dict()
            except Exception as e:
                raise AppException(
                    code=500,
                    message="model_validate转换出错"
                )

            return item
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="更新质失败，服务错误",
                details={"error": str(e)},
            )

    # ==========================================================================
    @classmethod
    def restore_xiangBaoBuWei(
            cls,
            request: Request,
            xbbwId: int,
            user_id: int
    ) -> bool:
        """
        恢复已删除的部位
        """
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, user_id)

            # 调用CRUD层进行恢复
            success = XiangBaoBuWeiCRUD.restore(db=db, xbbwId=xbbwId, user_id=user_id,gsId=gsId)

            if success:
                return True

            return False
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="恢复部位失败，服务错误",
                details={"error": str(e)},
            )
    # ==========================================================================
    @classmethod
    def batch_delete_xiangBaoBuWei(
            cls,
            request: Request,
            xbbw_ids: List[int],
            user_id: int
    ) -> int:
        """
        批量软删除部位
        """
        try:
            # 参数校验
            if not xbbw_ids:
                raise ValidationException(
                    message="部位ID列表不能为空",
                    details={"xbbw_ids": xbbw_ids}
                )
            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, user_id)
            # 调用CRUD层进行批量删除
            result = XiangBaoBuWeiCRUD.batch_delete(db=db, xbbwIds=xbbw_ids, user_id=user_id,gsId=gsId)
            return result
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="删除部位失败，服务器内部错误",
                details={"error": str(e)},
            )
    #===========================================================================
    @classmethod
    def search_all_xiangBaoBuWei(
            cls,
            userid:int,
            request: Request,
            keywords:Optional[str],
    ) -> List[Dict[str, Any]]:
        """
        下拉栏搜索部位
        """
        try:
            #标记为只读
            cls.mark_read_only(request)
            #获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db,userid)
            response = XiangBaoBuWeiCRUD.search_all(db=db,keywords=keywords,gsId=gsId)
            return response
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="搜索部位失败，服务错误",
                details={"error": str(e)},
            )


