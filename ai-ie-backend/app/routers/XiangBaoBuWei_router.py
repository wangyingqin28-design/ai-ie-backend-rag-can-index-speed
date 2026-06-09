"""
部位管理路由
"""
import traceback
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Request, Query, Path, Body

from app.config import settings
from app.schemas.system_manage.XiangBaoBuWei_schema import (
    XiangBaoBuWeiCreateRequest,
    XiangBaoBuWeiUpdateRequest,
    XiangBaoBuWeiBatchDeleteRequest
)
from app.schemas.system_manage.sys_schema import SearchRequest
from app.services.system_manage.XiangBaoBuWei_service import XiangBaoBuWeiService
from app.utils.exceptions import ValidationException, AppException
from app.utils.response import Success

router = APIRouter(prefix="/sys", tags=["箱包部位管理"])


@router.post(
    "/BuWei/create",
    summary="创建部位",
    description="创建新的部位种类"
)
async def create_xiangBaoBuWei(
        request: Request,
        xiangBaoBuWei_data: XiangBaoBuWeiCreateRequest = Body(..., description="部位数据"),
):
    """
    创建新的部位

    - **部位名称** (buWeiMingCheng): 必填，最长255字符

    返回创建的部位信息
    """
    try:
        # 调用服务层创建部位
        response_data = XiangBaoBuWeiService.create_xiangBaoBuWei(
            request=request,
            xiangBaoBuWei_data=xiangBaoBuWei_data,
        )
        return Success(
            msg="部位创建成功",
            data=response_data
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="创建部位失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )

@router.post(
    "/BuWei/search_admin/",
    summary="搜索部位（分页）-后台管理",
    description="分页搜索部位，支持部位名称模糊搜索",
)
async def search_xiangBaoBuWei_admin(
        request: Request,
        searchRequest: SearchRequest = Body(..., description="请求分页搜索"),
):
    """
    分页搜索标部位
    - **keyword**: 搜索关键词（可选，默认为空）
    - **page**: 页码（可选，默认为1）
    - **page_size**: 每页数量（可选，默认20，最大100）
    返回分页的部位列表
    """
    try:
        # 调用服务层搜索部位
        result = XiangBaoBuWeiService.search_XiangBaoBuWei_admin(
            request=request,
            keyword=searchRequest.search_keyword,
            page=searchRequest.page,
            page_size=searchRequest.page_size,
            userid=searchRequest.userid,
        )
        return Success(
            msg="搜索成功",
            data=result
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="搜索部位失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )

@router.post(
    "/BuWei/search_user/",
    summary="搜索部位（分页）-用户",
    description="分页搜索部位，支持部位名称模糊搜索",
)
async def search_xiangBaoBuWei_user(
        request: Request,
        searchRequest: SearchRequest = Body(..., description="请求分页搜索"),
):
    """
    分页搜索标部位
    - **keyword**: 搜索关键词（可选，默认为空）
    - **page**: 页码（可选，默认为1）
    - **page_size**: 每页数量（可选，默认20，最大100）
    返回分页的部位列表
    """
    try:
        # 调用服务层搜索部位
        result = XiangBaoBuWeiService.search_XiangBaoBuWei_user(
            request=request,
            keyword=searchRequest.search_keyword,
            page=searchRequest.page,
            page_size=searchRequest.page_size,
            userid=searchRequest.userid,
        )
        return Success(
            msg="搜索成功",
            data=result
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="搜索部位失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


@router.put(
    "/BuWei/{xbbwId}",
    summary="更新部位",
    description="更新部位信息"
)
async def update_xiangBaoBuWei(
        request: Request,
        update_data: XiangBaoBuWeiUpdateRequest = Body(..., description="更新数据")

):
    """
    更新部位信息
    - **xbbwId**: 部位ID（路径参数）
    - **更新数据**: 需要更新的字段
    返回更新后的部位信息
    """
    update_dict = update_data.dict(exclude_none=True)
    try:
        # 调用服务层更新部位
        item = XiangBaoBuWeiService.update_xiangBaoBuWei(
            request=request,
            xbbwId=update_data.xbbwId,
            user_id=update_data.up_userid,
            update_data=update_data
        )
        return Success(
            msg="更新部位成功",
            data=item
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="更新部位失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


@router.post(
    "/BuWei/restore/{xbbwId}",
    summary="恢复删除的部位",
    description="恢复软删除部位（标记为未删除状态，清空删除人员）"
)
async def restore_xiangBaoBuWei(
        request: Request,
        user_id: int = Query(..., description="用户唯一标识"),
        xbbwId: int = Path(..., description="部位ID"),
):
    try:
        # 参数校验
        if not xbbwId or xbbwId < 0:
            raise ValidationException(
                message="部位ID无效",
                details={"xbbwId": xbbwId}
            )
        if not (isinstance(xbbwId, int) and len(str(xbbwId)) == 16):
            raise ValidationException(
                message="部位ID必须为16位正整数",
                details={"xbbwId": xbbwId, "error": "ID长度非16位或非正整数"}
            )
        # userid检验
        if not (isinstance(user_id, int) and len(str(user_id)) == 16):
            raise ValidationException(
                message="操作人ID必须为16位正整数",
                details={"userid": user_id, "error": "ID长度非16位或非正整数"}
            )
        # 调用服务层恢复部位
        success = XiangBaoBuWeiService.restore_xiangBaoBuWei(
            request=request,
            xbbwId=xbbwId,
            user_id=user_id
        )

        return Success(
            msg="恢复部位成功",
            data={"restore": success}
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="恢复部位失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


@router.patch(
    "/BuWei/delete/",
    summary="批量删除的部位",
    description="批量软删除部位（标记为删除状态，删除人员）"
)
async def Batch_delete_xiangBaoBuWei(
        request: Request,
        deleted_request: XiangBaoBuWeiBatchDeleteRequest = Body(..., description="批量删除请求体"),
):
    """
    批量删除部位
    """
    try:
        delete_count = XiangBaoBuWeiService.batch_delete_xiangBaoBuWei(
            request=request,
            xbbw_ids=deleted_request.xbbw_ids,
            user_id=deleted_request.del_userid
        )
        return Success(
            msg=f"成功删除{str(delete_count)}条记录",
            data={"delete": delete_count}
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="删除部位失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


@router.get(
    "/BuWei/search_all/",
    response_model=List[Dict[str, Any]],
    summary="获取所有部位信息",
    description="返回部位数据，包含ID和名称"
)
async def get_all_xiangBaoBuWei(
        request: Request,
        userid:int,
        keywords:Optional[str] = None

):
    """
    获取所有部位信息

    - **返回格式**: [{"query.xbbwId": int, "query.buWeiMingCheng": str}, ...]
    """
    if userid<0 or len(str(userid))<16:
        raise ValidationException(
            message="userid非16位正整数"
        )
    try:

        result = XiangBaoBuWeiService.search_all_xiangBaoBuWei(request=request,keywords=keywords,userid=userid)
        return Success(
            msg="搜索成功",
            data={"result": result}
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="搜索部位失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )



