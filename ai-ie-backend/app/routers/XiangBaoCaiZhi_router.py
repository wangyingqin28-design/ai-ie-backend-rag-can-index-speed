"""
材质管理路由
"""
import traceback
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Request, Query, Path, Body
from app.config import settings
from app.schemas.system_manage.XiangBaoCaiZhi_schema import (
    XiangBaoCaiZhiCreateRequest,
    XiangBaoCaiZhiUpdateRequest,
    XiangBaoCaiZhiBatchDeleteRequest
)
from app.schemas.system_manage.sys_schema import SearchRequest
from app.services.system_manage.XiangBaoCaiZhi_service import XiangBaoCaiZhiService
from app.utils.exceptions import ValidationException, NotFoundException, AppException,PermissionDeniedException
from app.utils.response import Success

router = APIRouter(prefix="/sys", tags=["箱包材质管理"])


@router.post(
    "/CaiZhi/create",
    summary="创建材质",
    description="创建新的材质种类"
)
async def create_xiangBaoCaiZhi(
        request: Request,
        xiangBaoCaiZhi_data: XiangBaoCaiZhiCreateRequest = Body(..., description="材质数据"),
):
    """
    创建新的材质

    - **材质名称** (caiZhiMingCheng): 必填，最长255字符

    返回创建的材质信息
    """
    try:
        from app.services.system_manage.XiangBaoCaiZhi_service import XiangBaoCaiZhiService
        # 调用服务层创建材质
        response_data = XiangBaoCaiZhiService.create_xiangBaoCaiZhi(
            request=request,
            xiangBaoCaiZhi_data=xiangBaoCaiZhi_data,
        )
        return Success(
            msg="材质创建成功",
            data=response_data
        )
    except ValidationException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except NotFoundException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="创建材质失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )




@router.post(
    "/CaiZhi/search_admin/",
    summary="搜索材质（分页）-后台管理接口",
    description="分页搜索材质，支持材质名称模糊搜索",
)
async def search_xiangBaoCaiZhi_admin(
        request: Request,
        searchRequest: SearchRequest = Body(..., description="请求分页搜索"),
):
    """
    分页搜索标材质
    - **keyword**: 搜索关键词（可选，默认为空）
    - **page**: 页码（可选，默认为1）
    - **page_size**: 每页数量（可选，默认20，最大100）
    返回分页的材质列表
    """
    try:
        # 调用服务层搜索材质
        result = XiangBaoCaiZhiService.search_XiangBaoCaiZhi_admin(
            request=request,
            keyword=searchRequest.search_keyword,
            page=searchRequest.page,
            page_size=searchRequest.page_size,
            userid=searchRequest.userid
        )
        return Success(
            msg="搜索成功",
            data=result
        )
    except ValidationException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except NotFoundException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except PermissionDeniedException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="搜索材质失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )




@router.post(
    "/CaiZhi/search_user/",
    summary="搜索材质（分页）-前台用户接口",
    description="分页搜索材质，支持材质名称模糊搜索",
)
async def search_xiangBaoCaiZhi_user(
        request: Request,
        searchRequest: SearchRequest = Body(..., description="请求分页搜索"),
):
    """
    分页搜索标材质
    - **keyword**: 搜索关键词（可选，默认为空）
    - **page**: 页码（可选，默认为1）
    - **page_size**: 每页数量（可选，默认20，最大100）
    返回分页的材质列表
    """
    try:
        # 调用服务层搜索材质
        result = XiangBaoCaiZhiService.search_XiangBaoCaiZhi_user(
            request=request,
            keyword=searchRequest.search_keyword,
            page=searchRequest.page,
            page_size=searchRequest.page_size,
            userid=searchRequest.userid
        )
        return Success(
            msg="搜索成功",
            data=result
        )
    except ValidationException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except NotFoundException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="搜索材质失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


@router.put(
    "/CaiZhi/{xbczId}",
    summary="更新材质",
    description="更新材质信息，ID必填，其他选填"
)
async def update_xiangBaoCaiZhi(
        request: Request,
        update_data: XiangBaoCaiZhiUpdateRequest = Body(..., description="更新数据")

):
    """
    更新材质信息
    - **xbczId**: 材质ID（路径参数）
    - **更新数据**: 需要更新的字段
    返回更新后的材质信息
    """
    try:
        # 调用服务层更新材质
        item = XiangBaoCaiZhiService.update_xiangBaoCaiZhi(
            request=request,
            xbczId=update_data.xbczId,
            user_id=update_data.up_userid,
            update_data=update_data
        )
        return Success(
            msg="更新材质成功",
            data=item
        )
    except ValidationException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except NotFoundException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="更新材质失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


@router.post(
    "/CaiZhi/restore/{xbczId}",
    summary="恢复删除的材质",
    description="恢复软删除材质（标记为未删除状态，清空删除人员）"
)
async def restore_xiangBaoCaiZhi(
        request: Request,
        user_id: int = Query(..., description="用户唯一标识"),
        xbczId: int = Path(..., description="材质ID"),
):
    try:
        # 参数校验
        if not xbczId or xbczId < 0:
            raise ValidationException(
                message="材质ID无效",
                details={"材质ID": xbczId}
            )
        if not (isinstance(xbczId, int) and len(str(xbczId)) == 16):
            raise ValidationException(
                message="材质ID必须为16位正整数",
                details={"材质ID": xbczId, "error": "ID长度非16位或非正整数"}
            )
        # userid检验
        if not (isinstance(user_id, int) and len(str(user_id)) == 16):
            raise ValidationException(
                message="操作人ID必须为16位正整数",
                details={"操作人ID": user_id, "error": "ID长度非16位或非正整数"}
            )
        # 调用服务层恢复材质
        success = XiangBaoCaiZhiService.restore_xiangBaoCaiZhi(
            request=request,
            xbczId=xbczId,
            user_id=user_id
        )

        return Success(
            msg="恢复材质成功",
            data={"restore": success}
        )
    except ValidationException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except NotFoundException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="恢复材质失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


@router.patch(
    "/CaiZhi/delete/",
    summary="批量删除的材质",
    description="批量软删除材质（标记为删除状态，删除人员）"
)
async def Batch_delete_xiangBaoCaiZhi(
        request: Request,
        deleted_request: XiangBaoCaiZhiBatchDeleteRequest = Body(..., description="批量删除请求体"),
):
    """
    批量删除材质
    """
    try:
        delete_count = XiangBaoCaiZhiService.batch_delete_xiangBaoCaiZhi(
            request=request,
            xbcz_ids=deleted_request.xbcz_ids,
            user_id=deleted_request.del_userid
        )
        return Success(
            msg=f"成功删除{str(delete_count)}条记录",
            data={"delete": delete_count}
        )
    except ValidationException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except NotFoundException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="删除材质失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


@router.get(
    "/CaiZhi/search_all/",
    response_model=List[Dict[str, Any]],
    summary="获取所有材质信息",
    description="返回材质数据，包含ID和名称"
)
async def get_all_xiangBaoCaiZhi(
        request: Request,
        userid: int,
        keywords:Optional[str] = None,

):
    """
    获取所有材质信息
    - **返回格式**: [{"query.xbczId": int, "query.caiZhiMingCheng": str}, ...]
    """
    try:
        result = XiangBaoCaiZhiService.search_all_xiangBaoCaiZhi(request=request,keywords=keywords,userid=userid)
        return Success(
            msg="搜索成功",
            data={"result": result}
        )
    except ValidationException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except NotFoundException as e:
        if hasattr(e, 'code') and hasattr(e, 'message'):
            raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="搜索材质下拉栏失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )




