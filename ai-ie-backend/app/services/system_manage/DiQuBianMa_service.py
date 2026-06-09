from typing import List, Dict, Any
from fastapi import Request
from app.services.system_manage.DiQuBianMa_crud import DiQuBianMaCRUD
from app.services.system_manage.base_sys_service import BaseService
from app.utils.exceptions import NotFoundException, ValidationException, AppException


class DiQuBianMaService(BaseService):
    #===========================================================================
    @classmethod
    def search_all_DiQuBianMa(
            cls,
            request: Request,
    ) -> List[Dict[str, Any]]:
        """
        下拉栏搜索工种
        """
        try:
            #标记为只读
            cls.mark_read_only(request)
            #获取数据库会话
            db = cls.get_db_session(request)

            response = DiQuBianMaCRUD.search_all(db)
            return response
        except ValidationException as e:
            raise e
        except NotFoundException as e:
            raise e
        except Exception as e:
            raise AppException(
                code=500,
                message="搜索工种失败，服务器内部错误",
                details={"error": str(e)},
            )