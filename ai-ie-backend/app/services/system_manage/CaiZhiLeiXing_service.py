# app/service/system_manage/CaiZhiLeiXing_service.py
from typing import Optional, List, Dict, Any
from fastapi import Request, Body
from app.models import orm_models
from app.schemas.system_manage.CaiZhiLeiXing_schema import CaiZhiLeiXingCreateRequest, CaiZhiLeiXingResponseBase, \
    CaiZhiLeiXingUpdateRequest
from app.services.system_manage.CaiZhiLeiXing_crud import CaiZhiLeiXingCRUD
from app.services.system_manage.base_sys_service import BaseService
from app.utils.exceptions import NotFoundException, ValidationException, AppException


class CaiZhiLeiXingService(BaseService):
    """材质相关的业务服务"""
#==================================================================================
    @classmethod
    def search_CaiZhiLeiXing(
            cls,
            request: Request,
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

            #调用CRUD层进行搜索（返回result和total）
            results,total = CaiZhiLeiXingCRUD.search(
                db=db,
                keyword=clean_keyword,
                page=page,
                page_size=page_size
            )

            #使用paginate_results
            result = cls.paginate_results(results,total, page, page_size)

            result["search_keyword"] = clean_keyword
            #在业务逻辑层转换
            try:
                from app.schemas.system_manage.CaiZhiLeiXing_schema import CaiZhiLeiXingResponseBase
                response_data = []
                for caiZhiLeiXing in result["items"]:
                    item = CaiZhiLeiXingResponseBase.model_validate(caiZhiLeiXing)
                    response_data.append(item)
                    result["items"] = response_data
            except Exception as e:
                raise AppException(
                    code=500,
                    message="model_validate转换出错，请检查格式",
                    details={"error": str(e)}
                )
            return result
        except Exception as e:
            if hasattr(e,'code') and hasattr(e,'message'):
                raise e
            raise ValidationException(
                message="搜索材质材质失败",
                details={"error": str(e),
                         "keyword": keyword,
                         page: page,
                         page_size: page_size
                         }
            )
    # ==========================================================================
    @classmethod
    def create_caiZhiLeiXing(
            cls,
            request: Request,
            caiZhiLeiXing_data:CaiZhiLeiXingCreateRequest = Body(...,description="材质数据"),
    ) -> orm_models.AICaiZhiLeiXing:
        """
        创建材质
        """
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)
            data_dict =caiZhiLeiXing_data.dict()
            leiXingMingCheng = data_dict.get("leiXingMingCheng")
            user_id = data_dict.get("in_userid")



            #  检查材质名称是否重复
            existing = CaiZhiLeiXingCRUD.get_existing_by_name(db, leiXingMingCheng)
            if existing:
                raise ValidationException(
                    message=f"材质名称 '{leiXingMingCheng}' 已存在",
                    details={
                        "conflict_field": "leiXingMingCheng",
                        "conflict_value": leiXingMingCheng,
                        "existing_id": existing.czlxId
                    }
                )

            # 4. 创建新材质
            new_caiZhiLeiXing = CaiZhiLeiXingCRUD.create(
                db=db,
                leiXingMingCheng=leiXingMingCheng,
                user_id=user_id,
            )
            from app.schemas.system_manage.CaiZhiLeiXing_schema import CaiZhiLeiXingResponseBase

            response_data = CaiZhiLeiXingResponseBase.model_validate(new_caiZhiLeiXing).dict()

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
    def update_caiZhiLeiXing(
            cls,
            request: Request,
            czlxId: int,
            user_id: int,
            update_data: CaiZhiLeiXingUpdateRequest
    ) -> orm_models.AICaiZhiLeiXing:
        """
        更新材质信息
        """
        try:

            # 获取数据库会话
            db = cls.get_db_session(request)

            # 2. 检查是否要更新材质名称，并验证是否重复
            caiZhiLeiXing = CaiZhiLeiXingCRUD.get_by_id(db, czlxId, include_deleted=False)
            update_dict = update_data.dict(exclude_unset=True)  # 先转换为字典
            new_name = update_dict.get('leiXingMingCheng')
            if new_name and new_name != caiZhiLeiXing.leiXingMingCheng:
                existing = CaiZhiLeiXingCRUD.get_existing_by_name(
                    db, new_name, exclude_id=czlxId
                )
                if existing:
                    raise ValidationException(
                        message=f"材质名称 '{new_name}' 已存在",
                        details={
                            "conflict_field": "leiXingMingCheng",
                            "conflict_value": new_name,
                            "existing_id": existing.czlxId
                        }
                    )
            # 4. 调用CRUD层更新
            updated_caiZhiLeiXing = CaiZhiLeiXingCRUD.update(
                db=db,
                czlxId=czlxId,
                update_data=update_dict,
                user_id=user_id
            )

            try:
                item = CaiZhiLeiXingResponseBase.model_validate(updated_caiZhiLeiXing).dict()
            except Exception as e:
                raise AppException(
                    code=500,
                    message="model_validate转换出错"
                )
            return item
        except ValidationException as e:
            raise e
        except NotFoundException as e:
            raise e
        except Exception as e:
            raise AppException(
                code=500,
                message="更新质失败，服务器内部错误",
                details={"error": str(e)},
            )
    # ==========================================================================
    @classmethod
    def restore_caiZhiLeiXing(
            cls,
            request: Request,
            czlxId: int,
            user_id: int
    ) -> bool:
        """
        恢复已删除的材质
        """
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)

            # 调用CRUD层进行恢复
            success = CaiZhiLeiXingCRUD.restore(db, czlxId, user_id)

            if success:
                return True

            return False

        except ValidationException as e:
            raise e
        except NotFoundException as e:
            raise e
        except Exception as e:
            raise AppException(
                code=500,
                message="恢复材质失败，服务器内部错误",
                details={"error": str(e)},
            )
    # ==========================================================================
    @classmethod
    def batch_delete_caiZhiLeiXing(
            cls,
            request: Request,
            czlx_ids: List[int],
            user_id: int
    ) -> int:
        """
        批量软删除材质
        """
        try:
            # 参数校验
            if not czlx_ids:
                raise ValidationException(
                    message="材质ID列表不能为空",
                    details={"czlx_ids": czlx_ids}
                )
            # 获取数据库会话
            db = cls.get_db_session(request)
            # 调用CRUD层进行批量删除
            result = CaiZhiLeiXingCRUD.batch_delete(db, czlx_ids, user_id)
            return result

        except ValidationException as e:
            raise e
        except NotFoundException as e:
            raise e
        except Exception as e:
            raise AppException(
                code=500,
                message="删除材质失败，服务器内部错误",
                details={"error": str(e)},
            )
    #===========================================================================
    @classmethod
    def search_all_caiZhiLeiXing(
            cls,
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

            response = CaiZhiLeiXingCRUD.search_all(db, keywords=keywords)
            return response
        except ValidationException as e:
            raise e
        except NotFoundException as e:
            raise e
        except Exception as e:
            raise AppException(
                code=500,
                message="搜索材质失败服务，服务器内部错误",
                details={"error": str(e)},
            )


