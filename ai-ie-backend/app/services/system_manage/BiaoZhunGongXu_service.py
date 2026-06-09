# app/services/BiaoZhunGongXu_service.py
import os
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from fastapi import Request
from loguru import logger
from app.schemas.system_manage.BiaoZhunGongXu_schema import BiaoZhunGongXuResponseBase, BiaoZhunGongXuSearchResponse, \
    BiaoZhunGongXuGetSearchResponse
from app.schemas.system_manage.BiaoZhunGongXu_schema import BiaoZhunGongXuUpdateRequest
from app.services.system_manage.BiaoZhunGongXu_crud import BiaoZhunGongXuCRUD
from app.services.system_manage.base_sys_service import BaseService
from app.services.user.user_crud import get_gsId_by_userid
from app.utils.exceptions import NotFoundException, ValidationException, AppException, PermissionDeniedException
load_dotenv()
GETSOFT_ID_STR = os.getenv("GETSOFT_ID")
GETSOFT_ID = int(GETSOFT_ID_STR)
class BiaoZhunGongXuService(BaseService):
    """工序相关业务服务"""
    # ==========================================================================
    # ==========================================================================
    # ==========================================================================
    @classmethod
    def search_biaoZhunGongXu_admin(
            cls,
            userid: int,
            request: Request,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 20,
    ) -> Dict[str, Any]:
        """搜索工序"""
        try:
            # 标记为只读接口
            cls.mark_read_only(request)
            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, userid)
            logger.info(f'公司ID为{gsId}')
            # 清理关键词
            clean_keyword = keyword.strip() if keyword else ""
            # 调用CRUD层进行搜索（返回results和total）
            results, total = BiaoZhunGongXuCRUD.search_admin(
                db=db,
                keyword=clean_keyword,
                page=page,
                page_size=page_size,
                gsId=gsId
            )
            try:
                # 将字典列表转换为Pydantic模型列表
                response_items = []
                if gsId == GETSOFT_ID:
                    for item_dict in results:
                        # 使用parse_obj从字典创建Pydantic模型
                        item_model = BiaoZhunGongXuGetSearchResponse.parse_obj(item_dict)
                        response_items.append(item_model)
                else:
                    raise PermissionDeniedException(
                        message="用户为非本公司用户"
                    )
            except AppException:
                raise
            except Exception as e:
                raise AppException(
                    code=500,
                    message='转换格式出错'
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
                message="搜索工序失败",
                details={"error": str(e)}
            )
    # ==========================================================================
    # ==========================================================================
    @classmethod
    def search_biaoZhunGongXu_user(
            cls,
            userid: int,
            request: Request,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 20,
    ) -> Dict[str, Any]:
        """搜索工序"""
        try:
            # 标记为只读接口
            cls.mark_read_only(request)
            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, userid)
            logger.info(f'公司ID为{gsId}')
            # 清理关键词
            clean_keyword = keyword.strip() if keyword else ""
            # 调用CRUD层进行搜索（返回results和total）
            results, total = BiaoZhunGongXuCRUD.search_user(
                db=db,
                keyword=clean_keyword,
                page=page,
                page_size=page_size,
                gsId=gsId
            )
            try:
                # 将字典列表转换为Pydantic模型列表
                response_items = []
                for item_dict in results:
                    # 使用parse_obj从字典创建Pydantic模型
                    item_model = BiaoZhunGongXuSearchResponse.parse_obj(item_dict)
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
                message="搜索工序失败",
                details={"error": str(e)}
            )
    # ==========================================================================
    @classmethod
    def create_biaoZhunGongXu(
            cls,
            request: Request,
            biaoZhunGongXu_data: Dict[str, Any],
            user_id: int
    ):
        """
        创建标准工序
        """
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)
            biaoZhunGongXu_name = biaoZhunGongXu_data.get('gongXuMingCheng')
            gsId = get_gsId_by_userid(db, user_id)
            logger.info(f'gsId:{gsId}')
            #  检查工序名称是否重复
            existing = BiaoZhunGongXuCRUD.get_existing_by_name(db=db,gongXuMingCheng=biaoZhunGongXu_name,gsId=gsId)
            if existing:
                raise ValidationException(
                    message=f"工序名称 '{biaoZhunGongXu_name}' 已存在",
                    details={
                        "conflict_value": biaoZhunGongXu_name,
                    }
                )

            # 4. 创建新工序
            new_biaoZhunGongXu = BiaoZhunGongXuCRUD.create(
                db=db,
                gongXuMingCheng=biaoZhunGongXu_name,
                user_id=user_id,
                gongXuMiaoShu=biaoZhunGongXu_data.get('gongXuMiaoShu'),
                xbgzId=biaoZhunGongXu_data.get('xbgzId'),
                gsId=gsId
            )

            response_data = BiaoZhunGongXuResponseBase.model_validate(new_biaoZhunGongXu).dict()

            return response_data
        except AppException:
            raise
        except Exception as e:
            # 未知异常记录日志并返回500错误
            raise AppException(
                code=500,
                message="创建标准工序失败，服务器内部错误",
                details={"error": str(e)}
            )
    # ==========================================================================
    @classmethod
    def update_biaoZhunGongXu(
            cls,
            request: Request,
            bzgxId: int,
            user_id: int,
            update_data: BiaoZhunGongXuUpdateRequest
    ) -> dict:
        """
        更新标准工序信息
        """
        try:

            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db=db, userid=user_id)
            logger.info(f'gsId:{gsId}')
            # 2. 检查是否要更新工序名称，并验证是否重复
            # biaoZhunGongXu = BiaoZhunGongXuCRUD.get_by_id(
            #     db=db, bzgxId=bzgxId,gsId=gsId)
            # if biaoZhunGongXu is None:
            #     raise NotFoundException(
            #         message="找不到对应的标准工序"
            #     )
            new_name = update_data.gongXuMingCheng
            update_dict = update_data.dict()
            existing = BiaoZhunGongXuCRUD.get_existing_by_name(
                    db=db, gongXuMingCheng=new_name, exclude_id=bzgxId,gsId=gsId
            )
            if existing:
                raise ValidationException(
                    message=f"工序名称 '{new_name}' 已存在",
                    details={
                        "conflict_field": "gongXuMingCheng",
                        "conflict_value": new_name,
                    }
                )
            # 4. 调用CRUD层更新
            updated_biaoZhunGongXu = BiaoZhunGongXuCRUD.update(
                db=db,
                update_dict=update_dict,
                gsId=gsId,
            )
            try:
                item = BiaoZhunGongXuResponseBase.model_validate(updated_biaoZhunGongXu).model_dump()
            except Exception as e:
                raise AppException(
                    code=500,
                    message="转换出错"
                )
            return item
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=500,
                message="更新标准工序失败，服务器内部错误",
                details={"error": str(e)}
            )

    # ==========================================================================
    # ==========================================================================
    @classmethod
    def restore_biaoZhunGongXu(
            cls,
            request: Request,
            bzgxId: int,
            user_id: int
    ) -> Optional[bool]:
        """
        恢复已删除的标准工序
        """
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db=db, userid=user_id)
            logger.info(f"公司ID为{gsId}")

            # 调用CRUD层进行恢复
            success = BiaoZhunGongXuCRUD.restore(db=db, bzgxId=bzgxId, user_id=user_id,gsId=gsId)

            if success:
                return True

            return False
        except AppException:
            raise
        except Exception as e:
            # 未知异常记录日志并返回500错误
            raise AppException(
                code=500,
                message="恢复标准工序失败，服务器内部错误",
                details={"error": str(e)}
            )

    # ==========================================================================
    @classmethod
    def batch_delete_biaoZhunGongXu(
            cls,
            request: Request,
            bzgxIds: List[int],
            user_id: int
    ) -> Optional[int]:
        """
        批量软删除标准工序
        """
        try:
            # 参数校验
            if not bzgxIds:
                raise ValidationException(
                    message="工序ID列表不能为空",
                    details={"bzgx_ids": bzgxIds}
                )
            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db=db,userid=user_id)
            logger.info(f"公司ID为{gsId}")
            # 调用CRUD层进行批量删除
            result = BiaoZhunGongXuCRUD.batch_delete(db=db, bzgxIds=bzgxIds,user_id=user_id,gsId=gsId)
            return result
        except AppException:
            raise
        except Exception as e:
            # 未知异常记录日志并返回500错误
            raise AppException(
                code=500,
                message="批量删除标准工序失败，服务器内部错误",
                details={"error": str(e)}
            )