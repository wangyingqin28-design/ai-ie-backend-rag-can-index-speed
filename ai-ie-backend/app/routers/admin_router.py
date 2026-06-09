import traceback

from fastapi import Request, Body, APIRouter
from loguru import logger

from app.config import settings
from app.schemas.admin.admin_schemas import AdminPageRequest, AdminBatchDeleteDXFRequest
from app.services.dxf.dxf_service import FileUploadService
from app.utils.exception_handler import Fail
from app.utils.exceptions import AppException, NotFoundException, DeleteFailedException
from app.utils.response import Success

router = APIRouter(
    prefix="/admin",
    tags=["后台管理"],
    responses={404: {"description": "Not found"}},
)

file_upload_service = FileUploadService()

@router.post("/list", summary="管理员分页获取所有dxf文件信息(包含模糊查询以及按上传时间查询)")
async def admin_get_dxf_list(request: Request, page_request: AdminPageRequest = Body(..., description="管理员分页查询参数")):
    """管理员分页获取所有纸格信息"""

    request.state.read_only = True

    try:
        # 调用Service层方法，获取处理后的结构化数据
        data = file_upload_service.get_all_aiXiangBaoKuanHao(request=request, page_request=page_request,
                                                                 start_time=page_request.start_dt,
                                                                 end_time=page_request.end_dt)

        # 直接返回响应
        return Success(msg="获取DXF文件列表成功", data=data)

    # 捕获Service层抛出的业务异常
    except AppException as e:
        raise e
    # 捕获未知异常，封装为分析异常返回
    except Exception as e:
        raise NotFoundException(
            message=f"获取DXF文件列表失败: {str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None
            }
        )



@router.patch("/delete", summary="批量删除dxf")
async def admin_del_dxf(
        request: Request,
        delete_request: AdminBatchDeleteDXFRequest = Body(..., description="删除参数"),  # 批量参数放请求体
):
    """
    批量删除dxf
    """
    try:

        # 提取批量删除的纸格ID列表
        xbkh_ids = delete_request.aiXiangBaoKuanHao_ids

        # 调用Service层方法
        delete_count = file_upload_service.admin_batch_delete_aiXiangBaoKuanHao(request=request,del_userid=delete_request.del_userid,aiXiangBaoKuanHao_ids=delete_request.aiXiangBaoKuanHao_ids)

        if delete_count > 0:

            for xbkhId in xbkh_ids:
                try:
                    file_upload_service.delete_board_cache(xbkhId)#删除缓存
                except Exception as e:
                    # 单个缓存删除失败不影响整体，仅记录日志
                    logger.warning(f"批量删除时清理缓存失败 | xbkhId={xbkhId} | 错误: {str(e)}")


            # 直接返回响应
            return Success(msg=f"成功删除{delete_count}条记录",data=delete_count)
        else:
            return Fail(msg="无有效记录可删除（可能已被删除）")

    # 捕获Service层抛出的业务异常
    except AppException as e:
        raise e
    except Exception as e:
        # 捕获未知异常，封装为分析异常返回
        raise DeleteFailedException(
            message=f"批量删除DXF文件失败: {str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None
            }
        )






























































