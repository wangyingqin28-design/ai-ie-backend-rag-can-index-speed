# app/services/caoZuoRiZhi_service.py
from typing import Optional, Dict, Any
import json
from fastapi import Request

from app.schemas.system_manage.CaoZuoRiZhi_schema import (
    CaoZuoRiZhiCreateRequest,
    CaoZuoRiZhiSearchRequest,
    CaoZuoRiZhiResponse,
    CaoZuoRiZhiRecoverResponse,
    CaoZuoRiZhiSearchResponse
)
from app.services.system_manage.BiaoZhunGongXu_crud import BiaoZhunGongXuCRUD
from app.services.system_manage.CaoZuoRiZhi_crud import CaoZuoRiZhiCRUD
from app.services.system_manage.base_sys_service import BaseService
from app.utils.exceptions import (
    NotFoundException, ValidationException, AppException
)


class CaoZuoRiZhiService(BaseService):
    """操作日志业务服务"""

    # ==========================================================================
    # 查询操作日志
    # ==========================================================================
    @classmethod
    def get_caoZuoRiZhi_by_id(
            cls,
            request: Request,
            czrzId: int
    ) -> CaoZuoRiZhiResponse:
        """
        根据ID获取操作日志
        """
        try:
            # 标记为只读接口
            cls.mark_read_only(request)

            # 获取数据库会话
            db = cls.get_db_session(request)

            # 调用CRUD层获取日志
            log = CaoZuoRiZhiCRUD.get_by_id(db, czrzId)

            # 转换为响应模型
            return CaoZuoRiZhiResponse.model_validate(log)

        except NotFoundException as e:
            raise e
        except Exception as e:
            raise AppException(
                code=500,
                message="获取操作日志失败",
                details={"error": str(e), "czrzId": czrzId}
            )

    @classmethod
    def search_caoZuoRiZhi(
            cls,
            request: Request,
            search_request: CaoZuoRiZhiSearchRequest
    ) -> CaoZuoRiZhiSearchResponse:
        """
        搜索操作日志
        """
        try:
            # 标记为只读接口
            cls.mark_read_only(request)

            # 获取数据库会话
            db = cls.get_db_session(request)

            # 调用CRUD层搜索
            logs, total = CaoZuoRiZhiCRUD.search(
                db=db,
                biaoMing=search_request.search_keyword,
                page=search_request.page,
                page_size=search_request.page_size
            )

            # 转换为响应模型列表
            response_items = []
            for log in logs:

                item = CaoZuoRiZhiResponse.model_validate(log)
                response_items.append(item)

            result = cls.paginate_results(
                results=response_items,
                total=total,
                page=search_request.page,
                page_size=search_request.page_size
            )
            return CaoZuoRiZhiSearchResponse(
                items=result['items'],
                total=result['total'],
                page=result['page'],
                page_size=result['page_size'],
                total_pages=result['total_pages'],
                has_previous=result['has_previous'],
                has_next=result['has_next'],
                search_keyword=search_request.search_keyword,
            )
        except Exception as e:
            raise AppException(
                code=500,
                message="搜索操作日志失败",
                details={"error": str(e)}
            )

    # ==========================================================================
    # 恢复相关功能
    # ==========================================================================

    @classmethod
    def recover_data(
            cls,
            request: Request,
            czrzId: int
    ) -> bool:
        """
        执行数据恢复

        逻辑：
        1. 获取操作日志
        2. 根据操作类型和表名调用相应的CRUD方法
        3. 直接调用CRUD层，不经过Service层，避免重复记录操作日志
        """
        try:
            # 获取数据库会话
            db = cls.get_db_session(request)

            # 获取当前用户ID（执行恢复的用户）
            current_user_id = getattr(request.state, 'user_id', None)
            if not current_user_id:
                raise ValidationException(
                    message="未获取到当前用户信息",
                    details={"czrzId": czrzId}
                )

            # 获取日志数据
            log_info = CaoZuoRiZhiCRUD.get_by_id(db, czrzId)

            recover_czrzId= log_info.czrzId
            recover_biaoMing = log_info.biaoMing
            recover_caoZuoLeiXing = log_info.caoZuoLeiXing
            recover_caoZuoZhuJian = log_info.caoZuoZhuJian
            recover_liShiShuJu = log_info.liShiShuJu
            liShiShuJu_json = json.loads(recover_liShiShuJu)

            # 检查记录ID
            if recover_caoZuoZhuJian is None:
                message = f"无法从操作主键'{recover_caoZuoZhuJian}'解析出有效的记录ID"
                raise NotFoundException(
                    message=message,
                )

            # 根据表名和操作类型执行恢复
            if recover_biaoMing == "AI_BiaoZhunGongXu":

                if recover_caoZuoLeiXing == 2:  # 删除操作
                    # 直接调用CRUD的restore方法
                    success = BiaoZhunGongXuCRUD.restore(
                        db=db,
                        bzgxId=recover_caoZuoZhuJian,
                        user_id=current_user_id
                    )

                    if success:
                        return True
                    else:
                        return False

                elif recover_caoZuoLeiXing == 1:  # 更新操作
                    # 检查是否有旧数据
                    if not recover_caoZuoZhuJian:
                        message= "历史数据中缺少更新前的数据"
                        raise NotFoundException(
                            message=message,
                        )

                    # 直接调用CRUD的update方法
                    allowed_fields = ['gongXuMingCheng', 'gongXuMiaoShu', 'xbgzId']
                    update_data = {k: v for k, v in liShiShuJu_json.items() if k in allowed_fields}

                    if not update_data:
                        message = "没有可恢复的有效字段"
                        raise NotFoundException(
                            message=message,
                        )

                    BiaoZhunGongXuCRUD.update(
                        db=db,
                        update_data=update_data,
                    )


                    return True

                else:
                    message= f"不支持恢复的操作类型: {recover_caoZuoLeiXing}"
                    raise AppException(
                        code=500,
                        message=message,
                    )


            else:
                # 其他表的恢复逻辑可以在这里添加
                message= f"暂不支持表 {recover_biaoMing} 的数据恢复"
                raise AppException(
                    code=500,
                    message=message,
                )

        except ValidationException as e:
            raise e
        except NotFoundException as e:
            raise e
        except Exception as e:
            raise AppException(
                code=500,
                message="执行数据恢复失败",
                details={"error": str(e), "czrzId": czrzId}
            )
