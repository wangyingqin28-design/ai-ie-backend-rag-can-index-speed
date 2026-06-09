
import traceback
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, UploadFile, File, Query, Request, Body
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

from app.config import settings
from app.schemas.dxf.dxf_schemas import BatchDeleteDXFRequest, AIXiangBaoKuanHaoRequest, AIXiangBaoCaiPianRequest, \
    AICaiPianGongYiRequest
from app.services.dxf.dxf_analysis import DxfAnalysisService
from app.services.dxf.dxf_service import FileUploadService
from app.services.dxf.dxf_to_png import DrawDxfService
from app.utils.exception_handler import app_exception_handler, global_exception_handler, Fail
from app.utils.exceptions import ValidationException, AppException, AnalysisException, NotFoundException, \
    DeleteFailedException, DataUpdateFailedException
from app.utils.middleware.dbTransaction_middleware import DBTransactionMiddleware

from app.utils.response import Success

# 创建FastAPI应用
app = FastAPI(
    title="企业dxf文件管理API",
    description="dxf的上传下载接口API",
    version="1.0.0",
    docs_url=None,  # 禁用默认的docs
    redoc_url=None,  # 禁用默认的redoc
    openapi_tags=[
        {
            "name": "dxf文件上传",
            "description": "根据用户id上传的dxf文件",
        },

    ]
)

#注册事务中间件（必须在路由/异常处理器之前注册）
app.add_middleware(DBTransactionMiddleware)



#注册异常处理器
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)


# 自定义Swagger UI路由
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html(request:Request):
    request.state.read_only = True
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        swagger_js_url="http://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.min.js",
        swagger_css_url="http://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
    )

# 自定义ReDoc路由
@app.get("/redoc", include_in_schema=False)
async def redoc_html(request:Request):
    request.state.read_only = True
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="http://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.min.js",
        redoc_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
        with_google_fonts=False,
    )

file_upload_service = FileUploadService()
draw_dxf_service = DrawDxfService()
dxf_analysis_service = DxfAnalysisService()


@app.post("/upload",tags=["dxf文件上传"])
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
        file_upload_service.upload_file(request,in_userid,gsId,file_content,file.filename,file.content_type)

        return Success(msg="DXF文件上传成功")

    # 捕获所有自定义业务异常（已登记的异常）
    except AppException as e:
        return e
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


@app.post("/analysis", tags=["解析dxf"])
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
        if laiYuanLeiXing not in [0, 1]:
            raise ValidationException(message="来源类型只能是0（单独上传）或1（DXF解析）",details={"laiYuanLeiXing": laiYuanLeiXing})

        # 2. 读取文件内容（异步读取）
        file_content = await file.read()
        if not file_content:
            raise ValidationException(
                message="上传的DXF文件为空",
                details={"file_size": len(file_content)}
            )

        #先调用dxf转图片返回所有图片的minio路径
        object_name_list = draw_dxf_service.draw(request, file_content,file.filename,500)
        #后调用dxf解析程序入库，返回所有的裁片对象
        # 3. 调用同步业务逻辑，记得传递request对象（获取中间件创建的会话）
        aiXiangBaoKuanHao = dxf_analysis_service.parse_dxf_entities(request,file_content,file.filename,in_userid,gsId,object_name_list,laiYuanLeiXing)

        return Success(msg= "DXF解析成功并入库成功",data=aiXiangBaoKuanHao)

    # 捕获所有自定义业务异常（已登记的异常）
    except AppException as e:
        return e
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


@app.get("/dxf/list", tags=["根据公司id分页获取dxf文件信息(包含模糊查询以及按上传时间查询)"])
async def get_dxf_list(
        request: Request,
        gsId: int = Query(..., description="企业唯一标识"),
        page: int = Query(1, ge=1, description="页码，默认1"),
        page_size: int = Query(10, ge=1, le=100, description="每页条数，默认10，最大100"),
        keyword: Optional[str] = Query(None, description="模糊查询关键词"),
        start_time: Optional[str] = Query(None, description="上传开始时间（格式：YYYY-MM-DD HH:MM:SS）"),
        end_time: Optional[str] = Query(None, description="上传结束时间（格式：YYYY-MM-DD HH:MM:SS）")
):
    """
    批量分页获取DXF文件数据接口
    根据企业ID分页查询已上传的DXF文件信息
    """
    request.state.read_only = True

    try:
        # 参数格式校验
        if not (isinstance(gsId, int) and len(str(gsId)) == 16):
            raise ValidationException(message="企业ID必须为16位正整数",details={"gsId": gsId, "error": "ID长度非16位或非正整数"})
        if page < 1:
            raise ValidationException(message="页码必须大于等于1", details={"page": page})
        if page_size < 1 or page_size > 100:
            raise ValidationException(message="每页条数必须在1-100之间", details={"page_size": page_size})

        #时间段参数解析与校验
        start_dt = None
        end_dt = None
        if start_time:
            try:
                # 兼容前端常见的时间格式（YYYY-MM-DD HH:MM:SS）
                start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                raise ValidationException(
                    message="开始时间格式错误，需为YYYY-MM-DD HH:MM:SS",
                    details={"start_time": start_time}
                )
        if end_time:
            try:
                end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                raise ValidationException(
                    message="结束时间格式错误，需为YYYY-MM-DD HH:MM:SS",
                    details={"end_time": end_time}
                )
        # 校验：结束时间不能早于开始时间
        if start_dt and end_dt and end_dt < start_dt:
            raise ValidationException(
                message="结束时间不能早于开始时间",
                details={"start_time": start_time, "end_time": end_time}
            )

        # 调用Service层方法，获取处理后的结构化数据
        data = file_upload_service.get_aiXiangBaoKuanHao_by_gsId(request= request,gsId=gsId,page=page,page_size=page_size,keyword=keyword,start_time=start_dt,end_time=end_dt)

        # 直接返回响应
        return Success(msg="获取DXF文件列表成功",data=data)

    # 捕获Service层抛出的业务异常
    except AppException as e:
        return e
    # 捕获未知异常，封装为分析异常返回
    except Exception as e:
        raise NotFoundException(
            message=f"获取DXF文件列表失败: {str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None
            }
        )

@app.get("/dxf/get_aiXiangBaoKuanHao_by_xbkhId", tags=["根据箱包款号获取完整的纸格信息(包含裁片以及工艺列表)"])
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


        # 直接返回响应
        #return Success(msg="获取DXF文件列表成功",data=data)

    # 捕获Service层抛出的业务异常
    except AppException as e:
        return e
    # 捕获未知异常，封装为分析异常返回
    except Exception as e:
        raise NotFoundException(
            message=f"获取款号信息失败: {str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None
            }
        )



@app.patch("/dxf/delete", tags=["批量删除dxf"])
async def del_dxf(
        request: Request,
        delete_request: BatchDeleteDXFRequest = Body(..., description="删除参数"),  # 批量参数放请求体
):
    """
    批量删除dxf
    """
    try:

        # 从Pydantic模型解析参数
        del_userid = delete_request.del_userid
        aiXiangBaoKuanHao_ids = delete_request.aiXiangBaoKuanHao_ids
        gsId = delete_request.gsId

        # 参数校验
        # 仅做基础格式校验
        if not (isinstance(del_userid, int) and len(str(del_userid)) == 16):
            raise ValidationException(message="操作人ID必须为16位正整数",details={"del_userid": del_userid, "error": "ID长度非16位或非正整数"})
        if not (isinstance(gsId, int) and len(str(gsId)) == 16):
            raise ValidationException(message="企业ID必须16位为正整数",details={"gsId": gsId, "error": "ID长度非16位或非正整数"})
        if not aiXiangBaoKuanHao_ids:
            raise ValidationException(message="待删除的纸格ID列表不能为空")

        # 调用Service层方法
        delete_count = file_upload_service.batch_delete_aiXiangBaoKuanHao(request,del_userid,gsId,aiXiangBaoKuanHao_ids)

        if delete_count > 0:
            # 直接返回响应
            return Success(msg=f"成功删除{delete_count}条记录",data=delete_count)
        else:
            return Fail(msg="无有效记录可删除（可能已被删除或不属于当前企业）")

    # 捕获Service层抛出的业务异常
    except AppException as e:
        return e
    except Exception as e:
        # 捕获未知异常，封装为分析异常返回
        raise DeleteFailedException(
            message=f"批量删除DXF文件失败: {str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None
            }
        )


@app.put("/dxf/update_aiXiangBaoKuanHao", tags=["更新纸格信息"])
async def update_aiXiangBaoKuanHao(
        request: Request,
        aiXiangBaoKuanHaoRequest: AIXiangBaoKuanHaoRequest = Body(..., description="款号信息请求对象")
):
    """
    更新纸格信息
    """
    try:
        # 参数校验
        # 仅做基础格式校验
        if not (isinstance(aiXiangBaoKuanHaoRequest.up_userid, int) and len(str(aiXiangBaoKuanHaoRequest.up_userid)) == 16):
            raise ValidationException(message="操作人ID必须为16位正整数",
                                      details={"up_userid": aiXiangBaoKuanHaoRequest.up_userid, "error": "用户ID长度非16位或非正整数"})
        if not (isinstance(aiXiangBaoKuanHaoRequest.gsId, int) and len(str(aiXiangBaoKuanHaoRequest.gsId)) == 16):
            raise ValidationException(message="企业ID必须为16位正整数",
                                      details={"gsId": aiXiangBaoKuanHaoRequest.gsId, "error": "企业ID长度非16位或非正整数"})
        if aiXiangBaoKuanHaoRequest.laiYuanLeiXing not in [0, 1]:
            raise ValidationException(message="来源类型只能是0（单独上传）或1（DXF解析）",
                                      details={"laiYuanLeiXing": aiXiangBaoKuanHaoRequest.laiYuanLeiXing})

        # 调用Service层方法
        file_upload_service.update_aiXiangBaoKuanHao(request,aiXiangBaoKuanHaoRequest)

        return Success(msg="纸格属性更新成功")

    # 捕获Service层抛出的业务异常
    except AppException as e:
        return e
    except Exception as e:
        # 捕获未知异常，封装为分析异常返回
        raise DataUpdateFailedException(
            message=f"更新纸格信息失败: {str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None
            }
        )


@app.put("/dxf/update_aiXiangBaoCaiPian_and_aiCaiPianGongYi", tags=["更新裁片和裁片下的工艺信息"])
async def update_aiXiangBaoCaiPian_and_aiCaiPianGongYi(
        request: Request,
        aiXiangBaoCaiPianRequest: AIXiangBaoCaiPianRequest = Body(    ...,description="裁片信息请求对象")
):
    """
    更新裁片和裁片下的工艺信息
    """
    try:
        # 参数校验
        # 仅做基础格式校验
        if not (isinstance(aiXiangBaoCaiPianRequest.up_userid, int) and len(str(aiXiangBaoCaiPianRequest.up_userid)) == 16):
            raise ValidationException(message="操作人ID必须为16位正整数",
                                      details={"up_userid": aiXiangBaoCaiPianRequest.up_userid, "error": "用户ID长度非16位或非正整数"})
        if not (isinstance(aiXiangBaoCaiPianRequest.gsId, int) and len(str(aiXiangBaoCaiPianRequest.gsId)) == 16):
            raise ValidationException(message="企业ID必须为16位正整数",
                                      details={"gsId": aiXiangBaoCaiPianRequest.gsId, "error": "企业ID长度非16位或非正整数"})
        if not isinstance(aiXiangBaoCaiPianRequest.caiPianLeiXing, int):
            raise ValidationException(message="裁片类型不能为空")
        if not (isinstance(aiXiangBaoCaiPianRequest.xbbwId, int) and len(str(aiXiangBaoCaiPianRequest.xbbwId)) == 16):
            raise ValidationException(message="裁片所在部位不能为空",
                                      details={"xbbwId": aiXiangBaoCaiPianRequest.xbbwId,"error": "箱包部位ID长度非16位或非正整数"})


        # ========== 裁片厚度区间校验 ==========
        # 定义裁片厚度的合理区间（根据业务调整，示例：0.01mm ~ 100.0mm）
        caiPianHouDuMIN = 0.01  # 最小厚度（避免0或负数）
        caiPianHouDuMAX = 100.0  # 最大厚度

        caiPianHouDu = aiXiangBaoCaiPianRequest.caiPianHouDu
        # 仅当传了厚度值时才校验
        if caiPianHouDu is not None:
            # 校验1：必须是数字（int/float）
            if not isinstance(caiPianHouDu, (int, float)):
                raise ValidationException(
                    message="裁片厚度必须为数字（整数/小数）",
                    details={
                        "caiPianHouDu": caiPianHouDu,
                        "error": "类型错误，非数字"
                    }
                )
            # 校验2：在合理区间内
            if not (caiPianHouDuMIN <= caiPianHouDu <= caiPianHouDuMAX):
                raise ValidationException(
                    message=f"裁片厚度必须在{caiPianHouDuMIN}~{caiPianHouDuMAX}mm范围内",
                    details={
                        "caiPianHouDu": caiPianHouDu,
                        "min": caiPianHouDuMIN,
                        "max": caiPianHouDuMAX,
                        "error": "厚度超出可选范围"
                    }
                )

        # ========== 裁片工艺列表校验 ==========
        # 遍历gongYiLieBiao列表，逐行校验
        for idx, aiCaiPianGongYi in enumerate(aiXiangBaoCaiPianRequest.gongYiLieBiao):
             # 校验1：工艺对象存在
            if aiCaiPianGongYi is None:
                raise ValidationException(
                    message=f"工艺列表第{idx + 1}条数据为空",
                    details={"index": idx, "aiCaiPianGongYi": None}
                )

            # 校验2：gongYiLeiXing必填 + 类型合法 + 取值合法（核心修改）
            gongYiLeiXing = getattr(aiCaiPianGongYi, "gongYiLeiXing", None)

            # 第一步：校验必填（不允许None）
            if gongYiLeiXing is None:
                raise ValidationException(
                    message=f"工艺列表第{idx + 1}条，文本标注：{aiCaiPianGongYi.gongYiMiaoShu}的类型为必填项，不能为空",
                    details={
                        "index": idx,
                        "xbcpId": getattr(aiCaiPianGongYi, "xbcpId", "未知"),
                        "gongYiLeiXing": gongYiLeiXing,
                        "error": "工艺类型为空（None）"
                    }
                )

            # 第二步：校验类型为整数
            if not isinstance(gongYiLeiXing, int):
                raise ValidationException(
                    message=f"工艺列表第{idx + 1}条，文本标注：{aiCaiPianGongYi.gongYiMiaoShu}的类型不合法",
                    details={
                        "index": idx,
                        "xbcpId": getattr(aiCaiPianGongYi, "xbcpId", "未知"),
                        "gongYiLeiXing": gongYiLeiXing,
                        "error": f"工艺类型类型错误，当前为{type(gongYiLeiXing).__name__}，需为int"
                    }
                )

            # 第三步：校验取值为0或1
            if gongYiLeiXing not in (0, 1):
                raise ValidationException(
                    message=f"工艺列表第{idx + 1}条，文本标注：{aiCaiPianGongYi.gongYiMiaoShu}的类型值非法（仅允许工艺/备注）",
                    details={
                        "index": idx,
                        "xbcpId": getattr(aiCaiPianGongYi, "xbcpId", "未知"),
                        "gongYiLeiXing": gongYiLeiXing,
                        "allowed_values": [0, 1],
                        "error": "工艺类型超出合法取值范围"
                    }
                )

        # 调用Service层方法
        aiXiangBaoCaiPian_update_count, gongyi_update_total = file_upload_service.update_aiXiangBaoCaiPian_and_aiCaiPianGongYi(request,aiXiangBaoCaiPianRequest)


        return Success(msg=f"成功更新裁片属性，成功更新{gongyi_update_total}条工艺数据",data=gongyi_update_total)

    # 捕获Service层抛出的业务异常
    except AppException as e:
        return e
    except Exception as e:
        # 捕获未知异常，封装为分析异常返回
        raise DataUpdateFailedException(
            message=f"更新裁片及裁片工艺信息失败: {str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None
            }
        )



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app="app.api.dxf.main:app",  # 要运行的 FastAPI 实例
        host="0.0.0.0",  # 监听所有网卡
        port=8000,  # 端口
        reload=True,  # 开启热重载（仅开发环境用）
    )