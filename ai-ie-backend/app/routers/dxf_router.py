import traceback

from fastapi import UploadFile, File, Query, Request, Body, APIRouter, Depends
from loguru import logger

from app.config import settings
from app.schemas.dxf.dxf_schemas import BatchDeleteDXFRequest, AIXiangBaoKuanHaoRequest, AIXiangBaoCaiPianRequest, \
    PageRequest
from app.services.dxf.dxf_analysis import DxfAnalysisService
from app.services.dxf.dxf_service import FileUploadService
from app.services.dxf.dxf_to_png import DrawDxfService
from app.utils.auth.login_dependencies import verify_login
from app.utils.exception_handler import Fail
from app.utils.exceptions import ValidationException, AppException, AnalysisException, NotFoundException, \
    DeleteFailedException, DataUpdateFailedException
from app.utils.response import Success

router = APIRouter(
    prefix="/dxf",
    tags=["dxf文件管理"],
    responses={404: {"description": "Not found"}},
)

file_upload_service = FileUploadService()
draw_dxf_service = DrawDxfService()
dxf_analysis_service = DxfAnalysisService()

@router.post("/upload", summary="dxf上传文件")
async def upload_file(
        request: Request,
        in_userid: str = Query(..., description="用户唯一标识"),
        gsId: int = Query(..., description="企业唯一标识"),
        file: UploadFile = File(...)
):
    """文件上传接口（接口层）:将dxf文件存入MinIo"""

    try:
        # 1. 验证文件格式
        if not file.filename or not file.filename.lower().endswith('.dxf'):
            raise ValidationException(
                message="只允许上传DXF格式文件（.dxf后缀）",
                details={"filename": file.filename},
            )
        # 仅做基础格式校验
        if not (isinstance(in_userid, int) and len(str(in_userid)) == 16):
            raise ValidationException(message="操作人ID必须为16位正整数",
                                      details={"del_userid": in_userid, "error": "ID长度非16位或非正整数"})
        if not (isinstance(gsId, int) and len(str(gsId)) == 16):
            raise ValidationException(message="企业ID必须为16位正整数",
                                      details={"gsId": gsId, "error": "ID长度非16位或非正整数"})

        # 读取文件内容
        file_content = await file.read()
        if not file_content:
            raise ValidationException(
                message="上传的DXF文件内容为空",
                details={"file_size": len(file_content), "filename": file.filename}
            )

        # 调用业务逻辑
        file_upload_service.upload_file(request, in_userid, gsId, file_content, file.filename, file.content_type)

        return Success(msg="DXF文件上传成功")

    # 捕获所有自定义业务异常（已登记的异常）
    except AppException as e:
        raise e
    # 捕获所有未知异常
    except Exception as e:
        # 抛自定义解析异常，或直接让global_exception_handler捕获
        raise AnalysisException(
            message=f"DXF解析失败: {str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None
            }
        )

@router.post("/analysis", summary="解析dxf")
async def analysis_dxf(
    request: Request,
    file: UploadFile = File(..., description="dxf文件"),
    in_userid: int = Query(..., description="用户唯一标识"),
    gsId: int = Query(..., description="企业唯一标识"),
    laiYuanLeiXing: int = Query(..., description="来源类型"),
):
    """dxf解析接口（接口层）：DXF解析并入库"""
    try:
        # 1. 验证文件格式
        if not file.filename or not file.filename.lower().endswith('.dxf'):
            raise ValidationException(
                message="只允许上传DXF格式文件（.dxf后缀）",
                details={"filename": file.filename},
            )

        # 仅做基础格式校验
        if not (isinstance(in_userid, int) and len(str(in_userid)) == 16):
            raise ValidationException(message="操作人ID必须为16位正整数",details={"in_userid": in_userid, "error": "ID长度非16位或非正整数"})
        if not (isinstance(gsId, int) and len(str(gsId)) == 16):
            raise ValidationException(message="企业ID必须为16位正整数",details={"gsId": gsId, "error": "ID长度非16位或非正整数"})
        if laiYuanLeiXing not in [0, 1, 2]:
            raise ValidationException(message="来源类型只能是0（单独上传）和后台管理员上传为2，或1（DXF解析）",details={"laiYuanLeiXing": laiYuanLeiXing})

        # 2. 读取文件内容（异步读取）
        file_content = await file.read()
        if not file_content:
            raise ValidationException(
                message="上传的DXF文件为空",
                details={"file_size": len(file_content)}
            )

        # 先调用dxf转图片返回所有图片的minio路径
        object_name_list = draw_dxf_service.draw(request, file_content, file.filename, 500)
        # 后调用dxf解析程序入库，返回所有的裁片对象
        # 3. 调用同步业务逻辑，记得传递request对象（获取中间件创建的会话）
        aiXiangBaoKuanHao = dxf_analysis_service.parse_dxf_entities(request, file_content, file.filename, in_userid,
                                                                        gsId, object_name_list, laiYuanLeiXing)

        return Success(msg="DXF解析成功并入库成功", data=aiXiangBaoKuanHao)

    # 捕获所有自定义业务异常（已登记的异常）
    except AppException as e:
        raise e
        # 捕获所有未知异常
    except Exception as e:
        # 抛自定义解析异常，或直接让global_exception_handler捕获
        raise AnalysisException(
            message=f"DXF解析失败: {str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None
            }
        )

@router.post("/list", summary="根据公司id分页获取dxf文件信息(包含模糊查询以及按上传时间查询)")
async def get_dxf_list(
    request: Request,
    page_request: PageRequest = Body(..., description="分页查询参数"),
):
    """
    分页查询DXF文件列表
    - 支持企业ID过滤
    - 支持关键词模糊查询
    - 支持上传时间范围查询
    """
    request.state.read_only = True

    try:
        # 调用Service层方法，获取处理后的结构化数据
        data = file_upload_service.get_aiXiangBaoKuanHao_by_gsId(request=request, page_request=page_request,start_time=page_request.start_dt, end_time=page_request.end_dt)

        # 直接返回响应
        return Success(msg="获取DXF文件列表成功",data=data)

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


@router.get("/get_aiXiangBaoKuanHao_by_xbkhId", summary="根据箱包款号获取完整的纸格信息(包含裁片以及工艺列表)")
async def get_aiXiangBaoKuanHao_by_xbkhId(
        request: Request,
        xbkhId: int = Query(..., description="箱包款号唯一标识"),

):
    """
    根据箱包款号ID查询已上传的DXF文件信息
    """
    request.state.read_only = True

    try:
        # 参数格式校验
        if not (isinstance(xbkhId, int) and len(str(xbkhId)) == 16):
            raise ValidationException(message="箱包款号ID必须为16位正整数",details={"xbkhId": xbkhId, "error": "ID长度非16位或非正整数"})

        # 调用Service层方法，获取处理后的结构化数据
        #已换成缓存版本
        aiXiangBaoKuanHaoResponse = file_upload_service.query_aiXiangBaoKuanHao_by_xbkhId_with_cache(request= request,xbkhId=xbkhId)

        # 直接返回响应
        return Success(msg="获取纸格信息成功",data=aiXiangBaoKuanHaoResponse)

    # 捕获Service层抛出的业务异常
    except AppException as e:
        raise e
    # 捕获未知异常，封装为分析异常返回
    except Exception as e:
        raise NotFoundException(
            message=f"获取纸格信息失败: {str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None
            }
        )


@router.patch("/delete", summary="批量删除dxf")
async def del_dxf(
        request: Request,
        delete_request: BatchDeleteDXFRequest = Body(..., description="删除参数"),  # 批量参数放请求体
):
    """
    批量删除dxf
    """
    try:

        # 提取批量删除的纸格ID列表
        xbkh_ids = delete_request.aiXiangBaoKuanHao_ids

        # 调用Service层方法
        delete_count = file_upload_service.batch_delete_aiXiangBaoKuanHao(request=request,del_userid=delete_request.del_userid,gsId=delete_request.gsId,aiXiangBaoKuanHao_ids=delete_request.aiXiangBaoKuanHao_ids)

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
            return Fail(msg="无有效记录可删除（可能已被删除或不属于当前企业）")

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


@router.put("/update_aiXiangBaoKuanHao", summary="更新纸格信息")
async def update_aiXiangBaoKuanHao(
        request: Request,
        aiXiangBaoKuanHaoRequest: AIXiangBaoKuanHaoRequest = Body(..., description="款号信息请求对象")
):
    """
    更新纸格信息
    """
    try:

        # 调用Service层方法
        file_upload_service.update_aiXiangBaoKuanHao(request,aiXiangBaoKuanHaoRequest)

        #  删除对应缓存（避免返回旧数据）
        file_upload_service.delete_board_cache(aiXiangBaoKuanHaoRequest.xbkhId)

        return Success(msg="纸格属性更新成功")

    # 捕获Service层抛出的业务异常
    except AppException as e:
        raise e
    except Exception as e:
        # 捕获未知异常，封装为分析异常返回
        raise DataUpdateFailedException(
            message=f"更新纸格信息失败: {str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None
            }
        )


@router.put("/update_aiXiangBaoCaiPian_and_aiCaiPianGongYi", summary="更新裁片和裁片下的工艺信息")
async def update_aiXiangBaoCaiPian_and_aiCaiPianGongYi(
        request: Request,
        aiXiangBaoCaiPianRequest: AIXiangBaoCaiPianRequest = Body(    ...,description="裁片信息请求对象")
):
    """
    更新裁片和裁片下的工艺信息
    """
    try:

        # 调用Service层方法
        aiXiangBaoCaiPian_update_count, gongyi_update_total = file_upload_service.update_aiXiangBaoCaiPian_and_aiCaiPianGongYi(request,aiXiangBaoCaiPianRequest)

        # 删除对应缓存（避免返回旧数据）
        file_upload_service.delete_board_cache(aiXiangBaoCaiPianRequest.xbkhId)

        return Success(msg=f"成功更新裁片属性，成功更新{gongyi_update_total}条工艺数据",data=gongyi_update_total)

    # 捕获Service层抛出的业务异常
    except AppException as e:
        raise e
    except Exception as e:
        # 捕获未知异常，封装为分析异常返回
        raise DataUpdateFailedException(
            message=f"更新裁片及裁片工艺信息失败: {str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None
            }
        )

