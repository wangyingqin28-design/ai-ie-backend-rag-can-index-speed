from typing import Optional, Dict, Any

from fastapi import Request

from app.schemas.system_manage.DocumentIndex_schema import DocumentIndexSearchResponseBase, \
    DocumentIndexGetSearchResponseBase
from app.services.system_manage.DocumentIndex_crud import DocumentIndexCRUD
from app.services.system_manage.base_sys_service import BaseService, GETSOFT_ID
from app.services.user.user_crud import get_gsId_by_userid
from app.utils.exceptions import NotFoundException, ValidationException, AppException


class DocumentIndexService(BaseService):
    @classmethod
    def get_documentIndex_by_id(
            cls,
            userid: int,
            request: Request,
            id: str = None,

) -> Optional[dict]:
        """搜索单条规则"""
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, userid)
            if gsId == GETSOFT_ID:

                # 调用CRUD层
                DocumentIndex = DocumentIndexCRUD.get_by_id_admin(db, id)
            else:
                DocumentIndex = DocumentIndexCRUD.get_by_id_user(db=db,id=id,gsId=gsId)

            return DocumentIndex
        except AppException:
            raise
        except Exception as e:
            # 未知异常记录日志并返回500错误
            raise AppException(
                code=500,
                message="获取规则详情失败",
                details={"error": str(e), "id": id}
            )
    @classmethod
    def search_documentIndex_user(
            cls,
            userid:int,
            request: Request,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 10,
    ) -> Dict[str,Any]:
        """搜索公司规则"""
        try:
            # 标记为只读接口
            cls.mark_read_only(request)
            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, userid)
            # 清理关键词
            clean_keyword = keyword.strip() if keyword else None

            # 调用CRUD层进行搜索（返回results和total）
            results, total = DocumentIndexCRUD.search_user(
                db=db,
                enterprise_id=gsId,
                keyword=clean_keyword,
                page=page,
                page_size=page_size
            )

            # 在业务逻辑层转换
            try:
                response_data = []
                for documentIndex_dict in results:
                    # 确保字典包含所有必要字段
                    item = DocumentIndexSearchResponseBase.model_validate(documentIndex_dict)
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
                message="搜索公司规则失败，服务器内部错误",
                details={"error": str(e)},
            )
    @classmethod
    def search_documentIndex_admin(
            cls,
            userid:int,
            request: Request,
            keyword: Optional[str] = None,
            page: int = 1,
            page_size: int = 10,
    ) -> Dict[str,Any]:
        """搜索公司规则"""
        try:
            # 标记为只读接口
            cls.mark_read_only(request)
            # 获取数据库会话
            db = cls.get_db_session(request)
            gsId = get_gsId_by_userid(db, userid)
            # 清理关键词
            clean_keyword = keyword.strip() if keyword else None

            # 调用CRUD层进行搜索（返回results和total）
            results, total = DocumentIndexCRUD.search_user(
                db=db,
                enterprise_id=gsId,
                keyword=clean_keyword,
                page=page,
                page_size=page_size
            )

            # 在业务逻辑层转换
            try:
                response_data = []
                for documentIndex_dict in results:
                    # 确保字典包含所有必要字段
                    item = DocumentIndexGetSearchResponseBase.model_validate(documentIndex_dict)
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
                message="搜索公司规则失败，服务器内部错误",
                details={"error": str(e)},
            )

