"""
标准工序管理路由
"""
import traceback
from fastapi import APIRouter, Request, Query, Path, Body
from app.config import settings
from app.schemas.system_manage.BiaoZhunGongXu_schema import (
    BiaoZhunGongXuCreateRequest,
    BiaoZhunGongXuUpdateRequest,
    BiaoZhunGongXuBatchDeleteRequest
)
from app.schemas.system_manage.sys_schema import SearchRequest
from app.services.system_manage.BiaoZhunGongXu_service import BiaoZhunGongXuService
from app.utils.exception_handler import Fail
from app.utils.exceptions import ValidationException, AppException
from app.utils.response import Success
router = APIRouter(prefix="/BiaoZhunGongXu", tags=["标准工序管理"])


@router.post(
    "/",
    summary="创建标准工序",
    description="创建新的标准工序记录"
)
async def create_BiaoZhunGongXu(
        request: Request,
        biaoZhunGongXu_data: BiaoZhunGongXuCreateRequest = Body(..., description="工序数据"),
):
    """
    创建新的标准工序

    - **工序名称** (gongXuMingCheng): 必填，最长255字符
    - **工序描述** (gongXuMiaoShu): 可选，最长255字符
    - **推荐工种ID** (xbgzId): 可选

    返回创建的标准工序信息
    """
    try:
        # 1. 必填字段校验
        if not biaoZhunGongXu_data.gongXuMingCheng:
            raise ValidationException(
                message="缺少必要字段: gongXuMingCheng",
                details={"missing_field": "gongXuMingCheng"}
            )
        # 2. 工序名称校验
        biaoZhunGongXu_dict = biaoZhunGongXu_data.dict(exclude_none=True)
        if "gongXuMingCheng" in biaoZhunGongXu_dict:
            gongXu_name = biaoZhunGongXu_dict["gongXuMingCheng"]
            if gongXu_name == "" or gongXu_name == "string":
                raise ValidationException(
                    message="工序名称不能为空或'string'",
                    details={"gongXuMingCheng": gongXu_name}
                )
        # 3. userid检验
        if not (isinstance(BiaoZhunGongXuCreateRequest.in_userid, int) and len(str(BiaoZhunGongXuCreateRequest.in_userid)) == 16):
            raise ValidationException(
                message="操作人ID必须为16位正整数",
                details={"BiaoZhunGongXuCreateRequest.in_userid": BiaoZhunGongXuCreateRequest.in_userid, "error": "ID长度非16位或非正整数"}
            )
        from app.services.system_manage.BiaoZhunGongXu_service import BiaoZhunGongXuService
        # 调用服务层创建工序
        response_data = BiaoZhunGongXuService.create_biaoZhunGongXu(
            request=request,
            biaoZhunGongXu_data=biaoZhunGongXu_data.dict(exclude_none=True),
            user_id=BiaoZhunGongXuCreateRequest.in_userid
        )

        # 返回成功响应
        return Success(
            code=201,
            msg="标准工序创建成功",
            data=response_data
        )
    except Exception as e:
        # 未知异常记录日志并返回500错误
        raise AppException(
            code=500,
            message=f"创建标准工序失败: {str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None
            }
        )
@router.post(
    "/search/",
    summary="搜索标准工序（分页）",
    description="分页搜索标准工序，支持关键词模糊搜索",
)
async def search_BiaoZhunGongXues(
        request: Request,
        searchRequest: SearchRequest = Body(..., description="请求分页搜索"),
):
    """
    分页搜索标准工序
    返回分页的工序列表
    """
    try:
        # 参数校验
        if searchRequest.page < 1:
            raise ValidationException(
                message="页码必须大于0",
                details={"page": searchRequest.page}
            )

        if searchRequest.page_size < 1 or searchRequest.page_size > 100:
            raise ValidationException(
                message="每页数量必须在1-100之间",
                details={"page_size": searchRequest.page_size}
            )
        # 调用服务层搜索工序
        from app.services.system_manage.BiaoZhunGongXu_service import BiaoZhunGongXuService
        result = BiaoZhunGongXuService.search_biaoZhunGongXu(
            request=request,
            keyword=searchRequest.keyword,
            page=searchRequest.page,
            page_size=searchRequest.page_size,
        )
        return Success(
            msg="搜索成功",
            data=result
        )
    except ValidationException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message=f"分页搜索标准工序失败: {str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None
            }
        )


@router.put(
    "/{bzgxId}",
    summary="更新标准工序",
    description="更新标准工序信息"
)
async def update_BiaoZhunGongXu(
        request: Request,
        update_data: BiaoZhunGongXuUpdateRequest = Body(..., description="更新数据")

):
    """
    更新标准工序信息
    - **bzgxId**: 标准工序ID（路径参数）
    - **更新数据**: 需要更新的字段
    返回更新后的工序信息
    """
    try:
        # 调用服务层更新工序
        item = BiaoZhunGongXuService.update_biaoZhunGongXu(
            request=request,
            user_id=update_data.up_userid,
            update_data=update_data,
            bzgxId=update_data.bzgxId
        )
        return Success(
            msg="更新工序成功",
            data=item
        )
    except Exception as e:
        # 未知异常记录日志并返回500错误
        raise AppException(
            code=500,
            message=f"更新标准工序失败: {str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None
            }
        )


@router.post(
    "/restore/{bzgxId}",
    summary="恢复删除的标准工序",
    description="恢复软删除标准工序（标记为未删除状态，清空删除人员）"
)
async def restore_biaoZhunGongXu(
        request: Request,
        user_id: int = Query(..., description="用户唯一标识"),
        bzgxId: int = Path(..., description="标准工序ID"),
):
    try:
        # 参数校验
        if not bzgxId or bzgxId < 0:
            raise ValidationException(
                message="工序ID无效",
                details={"bzgxId": bzgxId}
            )
        if not (isinstance(bzgxId, int) and len(str(bzgxId)) == 16):
            raise ValidationException(
                message="标准工序ID必须为16位正整数",
                details={"bzgxId": bzgxId, "error": "ID长度非16位或非正整数"}
            )
        # userid检验
        if not (isinstance(user_id, int) and len(str(user_id)) == 16):
            raise ValidationException(
                message="操作人ID必须为16位正整数",
                details={"userid": user_id, "error": "ID长度非16位或非正整数"}
            )
        # 调用服务层恢复工序
        success = BiaoZhunGongXuService.restore_biaoZhunGongXu(
            request=request,
            bzgxId=bzgxId,
            user_id=user_id
        )

        return Success(
            msg="恢复工序成功",
            data={"restore": success}
        )
    except Exception as e:
        raise AppException(
            code=500,
            message=f"恢复标准工序失败: {str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None
            }
        )


@router.patch(
    "/delete_BiaoZhunGongXu/",
    summary="批量删除的标准工序",
    description="批量软删除标准工序（标记为删除状态，删除人员）"
)
async def Batch_delete_biaoZhunGongXu(
        request: Request,
        deleted_request: BiaoZhunGongXuBatchDeleteRequest = Body(..., description="批量删除请求体"),
):
    """
    批量删除标准工序
    """
    try:
        del_userid = deleted_request.del_userid
        bzgxIds = deleted_request.bzgx_ids
        for bzgxId in bzgxIds:
            if not (isinstance(bzgxId, int) and len(str(bzgxId)) == 16):
                raise ValidationException(
                    message="标准工序ID必须为16位正整数",
                    details={"bzgxId": bzgxId, "error": "ID长度非16位或非正整数"}
                )
        # userid检验
        if not (isinstance(del_userid, int) and len(str(del_userid)) == 16):
            raise ValidationException(
                message="操作人ID必须为16位正整数",
                details={"del_userid": del_userid, "error": "ID长度非16位或非正整数"}
            )
        if not bzgxIds:
            raise ValidationException(
                message="标准工序ID列表不能为空"
            )
        delete_count = BiaoZhunGongXuService.batch_delete_biaoZhunGongXu(
            request=request,
            bzgxIds=bzgxIds,
            user_id=del_userid
        )
        return Success(
            msg=f"成功删除{str(delete_count)}条记录",
            data={"delete": delete_count}
        )
    except Exception as e:
        raise AppException(
            code=500,
            message=f"删除标准工序失败: {str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None
            }
        )