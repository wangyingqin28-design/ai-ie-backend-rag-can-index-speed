# app/service/system_manage/XiangBaoCaiZhi_service.py
from typing import Optional, List, Dict, Any
from fastapi import Request, Body
from app.models import orm_models
from app.schemas.system_manage.XiangBaoCaiZhi_schema import XiangBaoCaiZhiCreateRequest, XiangBaoCaiZhiUpdateRequest, \
    XiangBaoCaiZhiResponseBase, XiangBaoCaiZhiSearchResponse, XiangBaoCaiZhiGetSearchResponse
from app.services.system_manage.XiangBaoCaiZhi_crud import XiangBaoCaiZhiCRUD
from app.services.system_manage.base_sys_service import BaseService, GETSOFT_ID
from app.services.user.user_crud import get_gsId_by_userid
from app.utils.exceptions import NotFoundException, ValidationException, AppException,PermissionDeniedException


class XiangBaoCaiZhiService(BaseService):
    """材质相关的业务服务"""
#==================================================================================
#===========================================================
#===========================================================
    @classmethod
    def search_XiangBaoCaiZhi_user(
            cls,
            request: Request,
            userid:int,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 10,
    ) -> Dict[str, Any]:
        """搜索材质"""
        try:
            #标记为只读接口
            cls.mark_read_only(request)
            #获取数据会话
            db = cls.get_db_session(request)
            #清理关键词
            clean_keyword = keyword.strip() if keyword else ""
            gsId = get_gsId_by_userid(db, userid)
            #调用CRUD层进行搜索（返回result和total）
            results,total = XiangBaoCaiZhiCRUD.search_user(
                db=db,
                keyword=clean_keyword,
                page=page,
                page_size=page_size,
                gsId=gsId
            )
            #使用paginate_results
            result = cls.paginate_results(results,total, page, page_size)
            result["search_keyword"] = clean_keyword
            #在业务逻辑层转换
            try:
                response_data = []
                for xiangBaoCaiZhi in result["items"]:
                    item = XiangBaoCaiZhiSearchResponse.model_validate(xiangBaoCaiZhi)
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
            if hasattr(e,'code') and hasattr(e,'message'):
                raise e
            raise AppException(
                code=500,
                message="搜索材质失败",
                details={"error": str(e),
                         "keyword": keyword,
                         page: page,
                         page_size: page_size
                         }
            )
    # ==========================================================================
        # ===========================================================
    @classmethod
    def search_XiangBaoCaiZhi_admin(
            cls,
            request: Request,
            userid: int,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 10,
    ) -> Dict[str, Any]:
        """搜索材质"""
        try:
            # 标记为只读接口
            cls.mark_read_only(request)
            # 获取数据会话
            db = cls.get_db_session(request)
            # 清理关键词
            clean_keyword = keyword.strip() if keyword else ""
            gsId = get_gsId_by_userid(db, userid)
            if gsId != GETSOFT_ID:
                raise PermissionDeniedException(
                    message="非本公司所属用户"
                )
            # 调用CRUD层进行搜索（返回result和total）
            results, total = XiangBaoCaiZhiCRUD.search_admin(
                db=db,
                keyword=clean_keyword,
                page=page,
                page_size=page_size
            )

            # 使用paginate_results
            result = cls.paginate_results(results, total, page, page_size)
            result["search_keyword"] = clean_keyword
            # 在业务逻辑层转换
            try:
                response_data = []
                for xiangBaoCaiZhi in result["items"]:
                    item = XiangBaoCaiZhiGetSearchResponse.model_validate(xiangBaoCaiZhi)
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
            if hasattr(e, 'code') and hasattr(e, 'message'):
                raise e
            raise AppException(
                code=500,
                message="搜索材质失败",
                details={"error": str(e),
                         "keyword": keyword,
                         page: page,
                         page_size: page_size
                         }
            )
        # ==========================================================================
    @classmethod
    def create_xiangBaoCaiZhi(
            cls,
            request: Request,
            xiangBaoCaiZhi_data:XiangBaoCaiZhiCreateRequest = Body(...,description="材质数据"),
    ) -> orm_models.AIXiangBaoCaiZhi:
        """
        创建材质
        """
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)
            data_dict =xiangBaoCaiZhi_data.dict()
            caiZhiMingCheng = data_dict.get("caiZhiMingCheng")
            czlxId = data_dict.get("czlxId")
            caiZhiMiaoShu = data_dict.get("caiZhiMiaoShu")
            user_id = data_dict.get("in_userid")
            gsId = get_gsId_by_userid(db,user_id)



            #  检查材质名称是否重复
            existing = XiangBaoCaiZhiCRUD.get_existing_by_name(db=db, caiZhiMingCheng=caiZhiMingCheng,gsId=gsId)
            if existing:
                raise ValidationException(
                    message=f"材质名称 '{caiZhiMingCheng}' 已存在",
                    details={
                        "conflict_value": caiZhiMingCheng,
                    }
                )

            # 4. 创建新材质
            new_xiangBaoCaiZhi = XiangBaoCaiZhiCRUD.create(
                db=db,
                caiZhiMingCheng=caiZhiMingCheng,
                caiZhiMiaoShu=caiZhiMiaoShu,
                czlxId=czlxId,
                user_id=user_id,
                gsId= gsId
            )

            response_data = XiangBaoCaiZhiResponseBase.model_validate(new_xiangBaoCaiZhi).dict()

            return response_data
        except ValidationException as e:
            raise e
        except NotFoundException as e:
            raise e
        except Exception as e:
            raise AppException(
                code=500,
                message="创建材质失败，服务器内部错误",
                details={"error": str(e)},
            )
    # ==========================================================================
    @classmethod
    def update_xiangBaoCaiZhi(
            cls,
            request: Request,
            xbczId: int,
            user_id: int,
            update_data: XiangBaoCaiZhiUpdateRequest
    ) -> orm_models.AIXiangBaoCaiZhi:
        """
        更新材质信息
        """
        try:

            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, user_id)
            # 2. 检查是否要更新材质名称，并验证是否重复
            xiangBaoCaiZhi = XiangBaoCaiZhiCRUD.get_by_id(db=db, xbczId=xbczId,gsId=gsId)
            update_dict = update_data.dict(exclude_unset=True)  # 先转换为字典
            new_name = update_dict.get('caiZhiMingCheng')
            if new_name and new_name != xiangBaoCaiZhi.caiZhiMingCheng:
                existing = XiangBaoCaiZhiCRUD.get_existing_by_name(
                    db=db, caiZhiMingCheng=new_name,gsId=gsId,exclude_id=xbczId
                )
                if existing:
                    raise ValidationException(
                        message=f"材质名称 '{new_name}' 已存在",
                        details={
                            "conflict_field": "caiZhiMingCheng",
                            "conflict_value": new_name,
                            "existing_id": existing.xbczId
                        }
                    )
            # 4. 调用CRUD层更新
            updated_xiangBaoCaiZhi = XiangBaoCaiZhiCRUD.update(
                db=db,
                xbczId=xbczId,
                update_data=update_dict,
                user_id=user_id
            )

            try:
                item = XiangBaoCaiZhiResponseBase.model_validate(updated_xiangBaoCaiZhi).dict()
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
                message="更新质失败，服务器内部错误",
                details={"error": str(e)},
            )

    # ==========================================================================
    @classmethod
    def restore_xiangBaoCaiZhi(
            cls,
            request: Request,
            xbczId: int,
            user_id: int
    ) -> bool:
        """
        恢复已删除的材质
        """
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)
            # 调用CRUD层进行恢复
            success = XiangBaoCaiZhiCRUD.restore(db, xbczId, user_id)
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
                message="恢复材质失败，服务器内部错误",
                details={"error": str(e)},
            )
    # ==========================================================================
    @classmethod
    def batch_delete_xiangBaoCaiZhi(
            cls,
            request: Request,
            xbcz_ids: List[int],
            user_id: int
    ) -> int:
        """
        批量软删除材质
        """
        try:
            # 参数校验
            if not xbcz_ids:
                raise ValidationException(
                    message="材质ID列表不能为空",
                    details={"xbcz_ids": xbcz_ids}
                )
            # 获取数据库会话
            db = cls.get_db_session(request)
            # 调用CRUD层进行批量删除
            result = XiangBaoCaiZhiCRUD.batch_delete(db, xbcz_ids, user_id)
            return result
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="删除材质失败，服务器内部错误",
                details={"error": str(e)},
            )
    #===========================================================================
    @classmethod
    def search_all_xiangBaoCaiZhi(
            cls,
            request: Request,
            userid:int,
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
            response = XiangBaoCaiZhiCRUD.search_all(db=db, keywords=keywords,gsId=gsId)
            return response
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="搜索材质失败服务，服务器内部错误",
                details={"error": str(e)},
            )


