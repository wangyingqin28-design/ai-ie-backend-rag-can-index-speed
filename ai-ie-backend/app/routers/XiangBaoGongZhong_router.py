"""
工种管理路由
"""
import traceback
from typing import List, Dict, Any
from fastapi import APIRouter, Request, Query, Path, Body
from app.config import settings
from app.schemas.system_manage.XiangBaoGongZhong_schema import (
    XiangBaoGongZhongUpdateRequest,
    XiangBaoGongZhongBatchDeleteRequest
)
from app.schemas.system_manage.sys_schema import SearchRequest
from app.services.system_manage.XiangBaoGongZhong_service import XiangBaoGongZhongService
from app.utils.exceptions import ValidationException, NotFoundException, AppException, PermissionDeniedException
from app.utils.response import Success

router = APIRouter(prefix="/sys",tags=["箱包工种管理"])


@router.post(
    "/GongZhong/create",
    summary="创建工种",
    description="创建新的工种种类" 
)
async def create_xiangBaoGongZhong(
        request:Request,
        gongZhongMingCheng: str = Query(...,description="工种名称"),
        user_id: int = Query(...,description="用户唯一标识")
):
    """
    创建新的工种
    
    - **工种名称** (gongZhongMingCheng): 必填，最长255字符
    
    返回创建的工种信息
    """
    try:
        #调用服务层创建工种
        response_data = XiangBaoGongZhongService.create_xiangBaoGongZhong(
            request=request,
            gongZhongMingCheng=gongZhongMingCheng,
            user_id=user_id
        )
        return Success(
            msg="工种创建成功",
            data=response_data
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="创建工种失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )
@router.post(
    "/GongZhong/search_admin/",
    summary="搜索工种（分页）-后台管理界面",
    description="分页搜索工种，支持工种名称模糊搜索，页码必须大于0，每页数量必须在1-100之间",
)
async def search_xiangBaoGongZhong_admin(
        request: Request,
        searchRequest: SearchRequest = Body(...,description="请求分页搜索"),
):
    """
    分页搜索标工种
    - **keyword**: 搜索关键词（可选，默认为空）
    - **page**: 页码（可选，默认为1）
    - **page_size**: 每页数量（可选，默认20，最大100）
    返回分页的工种列表
    """
    try:
        # 调用服务层搜索工种
        result = XiangBaoGongZhongService.search_XiangBaoGongZhong_admin(
            request=request,
            userid=searchRequest.userid,
            keyword=searchRequest.search_keyword,
            page=searchRequest.page,
            page_size=searchRequest.page_size
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
            message="搜索包型失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )

@router.post(
    "/GongZhong/search_user/",
    summary="搜索工种（分页）-用户界面",
    description="分页搜索工种，支持工种名称模糊搜索，页码必须大于0，每页数量必须在1-100之间",
)
async def search_xiangBaoGongZhong_user(
        request: Request,
        searchRequest: SearchRequest = Body(...,description="请求分页搜索"),
):
    """
    分页搜索标工种
    - **keyword**: 搜索关键词（可选，默认为空）
    - **page**: 页码（可选，默认为1）
    - **page_size**: 每页数量（可选，默认20，最大100）
    返回分页的工种列表
    """
    try:
        # 调用服务层搜索工种
        result = XiangBaoGongZhongService.search_XiangBaoGongZhong_user(
            request=request,
            userid=searchRequest.userid,
            keyword=searchRequest.search_keyword,
            page=searchRequest.page,
            page_size=searchRequest.page_size
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
            message="搜索工种失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )

@router.put(
    "/GongZhong/{xbgzId}",
    summary="更新工种",
    description="更新工种信息"
)
async def update_xiangBaoGongZhong(
        request: Request,
        update_data: XiangBaoGongZhongUpdateRequest = Body(..., description="更新数据")

):
    """
    更新工种信息
    - **xbgzId**: 工种ID（路径参数）
    - **更新数据**: 需要更新的字段
    返回更新后的工种信息
    """
    try:
        from app.services.system_manage.XiangBaoGongZhong_service import XiangBaoGongZhongService
        # 调用服务层更新工种
        item = XiangBaoGongZhongService.update_xiangBaoGongZhong(
            request=request,
            xbgzId=update_data.xbgzId,
            up_userid=update_data.up_userid,
            update_data=update_data
        )
        return Success(
            msg="更新工种成功",
            data=item
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="更新工种失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )

@router.post(
    "/GongZhong/restore/{xbgzId}",
    summary="恢复删除的工种",
    description="恢复软删除工种（标记为未删除状态，清空删除人员）"
)
async def restore_xiangBaoGongZhong(
        request: Request,
        user_id: int = Query(..., description="用户唯一标识"),
        xbgzId: int = Path(..., description="工种ID"),
):
    try:
        from app.services.system_manage.XiangBaoGongZhong_service import XiangBaoGongZhongService
        # 调用服务层恢复工种
        success = XiangBaoGongZhongService.restore_xiangBaoGongZhong(
            request=request,
            xbgzId=xbgzId,
            user_id=user_id
        )

        return Success(
            msg="恢复工种成功",
            data={"restore": success}
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="恢复工种失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )

@router.patch(
    "/GongZhong/delete/",
    summary="批量删除的工种",
    description="批量软删除工种（标记为删除状态，删除人员）"
)
async def Batch_delete_xiangBaoGongZhong(
        request: Request,
        deleted_request: XiangBaoGongZhongBatchDeleteRequest = Body(..., description="批量删除请求体"),
):
    """
    批量删除工种
    """
    try:
        delete_count = XiangBaoGongZhongService.batch_delete_xiangBaoGongZhong(
            request=request,
            xbgz_ids=deleted_request.xbgz_ids,
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
            message="删除工种失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )
@router.post(
    "/GongZhong/search_all/",
    response_model=List[Dict[str, Any]],  # 修正类型
    summary="获取所有工种",
    description="返回工种，供下拉栏选择"
)
async def get_xiangBaoGongZhong_search_all(
    request: Request,
    userid: int,
    keywords: str = None  # 添加默认值
):
    try:
        results = XiangBaoGongZhongService.search_all_xiangBaoGongZhong(
            request=request,
            keywords=keywords,
            userid=userid,
        )
        return Success(
            msg="搜索成功",
            data={"results": results}
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(
            code=500,
            message="搜索工种下拉栏失败",
            details={'error':str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )


