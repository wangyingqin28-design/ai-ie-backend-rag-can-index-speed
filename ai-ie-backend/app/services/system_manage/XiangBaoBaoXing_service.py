# app/service/system_manage/XiangBaoBaoXing_service.py
from typing import Optional, Dict, Any, List

from fastapi import Request, Body

from app.models import orm_models
from app.schemas.system_manage.XiangBaoBaoXing_schema import XiangBaoBaoXingCreateRequest, XiangBaoBaoXingUpdateRequest, \
    XiangBaoBaoXingResponseBase
from app.services.system_manage.XiangBaoBaoXing_crud import XiangBaoBaoXingCRUD
from app.services.system_manage.base_sys_service import BaseService, GETSOFT_ID
from app.services.user.user_crud import get_gsId_by_userid
from app.utils.exceptions import NotFoundException, ValidationException, AppException, PermissionDeniedException


class XiangBaoBaoXingService(BaseService):
    """包型相关的业务服务"""
#==================================================================================
#==================================================================================
    #======================================================================
    @classmethod
    def search_XiangBaoBaoXing_user(
            cls,
            request: Request,
            userid:int,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 10,
            parent_id:Optional[int] = None,
            fubxId:Optional[int] = None
    ) -> Dict[str, Any]:
        """搜索包型"""
        try:
            #标记为只读接口
            cls.mark_read_only(request)
            #获取数据会话
            db = cls.get_db_session(request)
            #清理关键词
            clean_keyword = keyword.strip() if keyword else ""
            gsId = get_gsId_by_userid(db, userid)

            #调用CRUD层进行搜索（返回result和total）
            items,total = XiangBaoBaoXingCRUD.search_user(
                db=db,
                keyword=clean_keyword,
                page=page,
                page_size=page_size,
                parent_id=parent_id,
                fubxId=fubxId,
                gsId=gsId,
            )
            #使用paginate_results
            result = cls.paginate_results(
                results=items,
                total=total,
                page=page,
                page_size=page_size
            )
            result["search_keyword"] = clean_keyword
            return result
        except ValidationException as e:
            raise e
        except NotFoundException as e:
            raise e
        except Exception as e:
            raise AppException(
                code=500,
                message="搜索包型失败，服务错误",
                details={"error": str(e)},
            )
    #======================================================================
    @classmethod
    def search_XiangBaoBaoXing_admin(
            cls,
            request: Request,
            userid:int,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 10,
            parent_id:Optional[int] = None,
            fubxId:Optional[int] = None
    ) -> Dict[str, Any]:
        """搜索包型"""
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
            items,total = XiangBaoBaoXingCRUD.search_admin(
                db=db,
                keyword=clean_keyword,
                page=page,
                page_size=page_size,
                parent_id=parent_id,
                fubxId=fubxId,
            )
            #使用paginate_results
            result = cls.paginate_results(
                results=items,
                total=total,
                page=page,
                page_size=page_size
            )
            result["search_keyword"] = clean_keyword
            return result
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="搜索包型失败，服务错误",
                details={"error": str(e)},
            )
    # ==========================================================================
    @classmethod
    def create_xiangBaoBaoXing(
            cls,
            request: Request,
            xiangBaoBaoXing_data:XiangBaoBaoXingCreateRequest = Body(...,description="包型数据"),
    ) -> orm_models.AIXiangBaoBaoXing:
        """
        创建包型
        """
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)
            data_dict =xiangBaoBaoXing_data.dict()
            baoXingMingCheng = data_dict.get("baoXingMingCheng")
            parent_id = data_dict.get("parent_id")
            fubxId = data_dict.get("fubxId")
            baoXingMiaoShu = data_dict.get("baoXingMiaoShu")
            user_id= data_dict.get("in_userid")
            gsId = get_gsId_by_userid(db,user_id)



            #  检查包型名称是否重复
            existing = XiangBaoBaoXingCRUD.get_existing_by_name(db=db,baoXingMingCheng=baoXingMingCheng,gsId=gsId)
            if existing:
                raise ValidationException(
                    message=f"包型名称 '{baoXingMingCheng}' 已存在",
                    details={
                        "conflict_field": "baoXingMingCheng",
                        "conflict_value": baoXingMingCheng,
                    }
                )
            # 4. 创建新包型
            new_xiangBaoBaoXing = XiangBaoBaoXingCRUD.create(
                db=db,
                baoXingMingCheng=baoXingMingCheng,
                fubxId=fubxId,
                parent_id=parent_id,
                user_id=user_id,
                baoXingMiaoShu=baoXingMiaoShu,
                gsId=gsId,
            )
            response_data = XiangBaoBaoXingResponseBase.model_validate(new_xiangBaoBaoXing).dict()
            return response_data
        except ValidationException as e:
            raise e
        except NotFoundException as e:
            raise e
        except Exception as e:
            raise AppException(
                code=500,
                message="创建包型失败，服务错误",
                details={"error": str(e)},
            )
    # ==========================================================================
    @classmethod
    def update_xiangBaoBaoXing(
            cls,
            request: Request,
            xbbxId: int,
            update_data: XiangBaoBaoXingUpdateRequest
    ):
        """
        更新包型信息
        """
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)
            userid = update_data.up_userid
            gsId = get_gsId_by_userid(db, userid)

            # 1. 检查是否要更新包型名称，并验证是否重复
            new_name = update_data.baoXingMingCheng
            if new_name:
                existing = XiangBaoBaoXingCRUD.get_existing_by_name(
                    db=db,
                    baoXingMingCheng=new_name,
                    exclude_id=xbbxId,
                    gsId=gsId
                )
                if existing:
                    raise ValidationException(
                        message=f"包型名称 '{new_name}' 已存在",
                        details={
                            "conflict_field": "baoXingMingCheng",
                            "conflict_value": new_name,
                            "existing_id": existing.xbbxId
                        }
                    )

            # 2. 准备更新数据
            update_dict = update_data.model_dump(exclude_none=True)

            # 3. 调用CRUD层更新（CRUD层会验证包型是否存在）
            updated_xiangBaoBaoXing = XiangBaoBaoXingCRUD.update(
                db=db,
                xbbxId=xbbxId,
                gsId=gsId,  # 添加 gsId 参数
                update_data=update_dict
            )
            # 4. 转换为响应模型
            return XiangBaoBaoXingResponseBase.model_validate(updated_xiangBaoBaoXing)

        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="更新包型失败，服务错误",
                details={"error": str(e)},
            )

    # ==========================================================================
    @classmethod
    def restore_xiangBaoBaoXing(
            cls,
            request: Request,
            xbbxId: int,
            user_id: int
    ) -> bool:
        """
        恢复已删除的包型
        """
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)

            # 调用CRUD层进行恢复
            success = XiangBaoBaoXingCRUD.restore(db, xbbxId, user_id)

            if success:
                return True

            return False
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="恢复包型失败，服务器内部错误",
                details={"error": str(e)},
            )
    #==========================================================================
    @classmethod
    def batch_delete_xiangBaoBaoXing(
            cls,
            request: Request,
            xbbx_ids: List[int],
            user_id: int
    ) -> int:
        """
        批量软删除包型
        """
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, user_id)
            # 调用CRUD层进行批量删除
            result = XiangBaoBaoXingCRUD.batch_delete(db=db, xbbxIds=xbbx_ids, user_id=user_id,gsId=gsId)
            return result

        except ValidationException as e:
            raise e
        except NotFoundException as e:
            raise e
        except Exception as e:
            raise AppException(
                code=500,
                message="删除包型失败，服务错误",
                details={"error": str(e)},
            )
    #===========================================================================
    @classmethod
    def search_all_xiangBaoBaoXing(
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

            response = XiangBaoBaoXingCRUD.search_all(db=db, keywords=keywords,gsId=gsId)
            return response
        except ValidationException as e:
            raise e
        except NotFoundException as e:
            raise e
        except Exception as e:
            raise AppException(
                code=500,
                message="搜索包型失败，服务错误",
                details={"error": str(e)},
            )


