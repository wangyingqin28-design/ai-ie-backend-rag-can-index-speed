"""
工种管理路由
"""
import traceback
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Request, Query, Path, Body

from app.config import settings
from app.schemas.system_manage.XiangBaoGongZhong_schema import (
    XiangBaoGongZhongResponse,
    XiangBaoGongZhongCreateRequest,
    XiangBaoGongZhongUpdateRequest,
    XiangBaoGongZhongBatchDeleteRequest
)
from app.schemas.system_manage.sys_schema import SearchRequest
from app.services.system_manage.XiangBaoGongZhong_service import XiangBaoGongZhongService
from app.utils.exceptions import ValidationException, AppException
from app.utils.response import Success

router = APIRouter(prefix="/XiangBaoGongZhong",tags=["箱包工种管理"])


@router.post(
    "/",
    summary="创建工种",
    description="创建新的工种种类" 
)
async def create_XiangBaoGongZhong(
        request:Request,
        xiangBaoGongZhong_data: XiangBaoGongZhongCreateRequest=Body(...,description="工种数据"),
        user_id: int = Query(...,description="用户唯一标识")
):
    """
    创建新的工种
    
    - **工种名称** (gongZhongMingCheng): 必填，最长255字符
    
    返回创建的工种信息
    """
    try:
        # 1. 必填字段校验
        if not xiangBaoGongZhong_data.gongZhongMingCheng:
           raise ValidationException(
                message="缺少必要字段: gongZhongMingCheng",
                details={"missing_field": "gongZhongMingCheng"}
            )
        # 2. 工种名称校验
        xiangBaoGongZhong_dict = xiangBaoGongZhong_data.dict(exclude_none=True)
        if "gongZhongMingCheng" in xiangBaoGongZhong_dict:
            gongZhong_name = xiangBaoGongZhong_dict["gongZhongMingCheng"]
            if gongZhong_name == "" or gongZhong_name == "string":
                raise ValidationException(
                    message="工种名称不能为空或'string'",
                    details={"gongZhongMingCheng": gongZhong_name}
                )
        # 3. userid检验
        if not (isinstance(user_id, int) and len(str(user_id)) == 16):
            raise ValidationException(
                message="操作人ID必须为16位正整数",
               details={"userid": user_id, "error": "ID长度非16位或非正整数"}
            )
        #调用服务层创建工种
        response_data = XiangBaoGongZhongService.create_xiangBaoGongZhong(
            request=request,
            user_id=user_id,
            gongZhongMingCheng=xiangBaoGongZhong_data.gongZhongMingCheng,
        )
        return Success(
            code=200,
            msg="工种创建成功",
            data=response_data
        )
    except Exception as e:
        raise AppException(
            code=500,
            message="创建工种失败 ",
            details={"error": str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )
@router.get(
    "/search/",
    summary="搜索工种（分页）",
    description="分页搜索工种，支持关键词模糊搜索",
    response_model=XiangBaoGongZhongResponse
)
async def search_XiangBaoGongZhong(
        request: Request,
        searchRequest: SearchRequest = Body(...,description=""),
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
        from app.services.system_manage.XiangBaoGongZhong_service import XiangBaoGongZhongService
        result = XiangBaoGongZhongService.search_XiangBaoGongZhong(
            userid=searchRequest.userid,
            request=request,
            keyword=searchRequest.search_keyword,
            page=searchRequest.page,
            page_size=searchRequest.page_size
        )
        return Success(
            msg="搜索成功",
            data=result
        )
    except Exception as e:
        raise AppException(
            code=500,
            message="分页搜索工序失败 ",
            details={"error": str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )
@router.put(
    "/{xbgzId}",
    summary="更新工种",
    description="更新工种信息"
)
async def update_XiangBaoGongZhong(
        request: Request,
        xbgzId: int = Path(..., description="工种ID"),
        user_id: int = Query(..., description="用户唯一标识"),
        update_data: XiangBaoGongZhongUpdateRequest = Body(..., description="更新数据")

):
    """
    更新工种信息
    - **xbgzId**: 工种ID（路径参数）
    - **更新数据**: 需要更新的字段
    返回更新后的工种信息
    """
    try:
        # 参数校验
        if not xbgzId or xbgzId <= 0:
            raise ValidationException(
                message="工种ID无效",
                details={"xbgzId": xbgzId}
            )
        if not (isinstance(xbgzId, int) and len(str(xbgzId)) == 16):
            raise ValidationException(
                message="工种ID必须为16位正整数",
                details={"xbgzId": xbgzId, "error": "ID长度非16位或非正整数"}
            )
        # 过滤掉为None的字段（只更新有值的字段）
        update_dict = update_data.dict(exclude_none=True)
        if "gongZhongMingCheng" in update_dict:
            gongZhong_name = update_dict["gongZhongMingCheng"]
            if gongZhong_name == "" or gongZhong_name == "string":
                raise ValidationException(
                    message="工种名称不能为空或'string'",
                    details={"gongZhongMingCheng": gongZhong_name}
                )
        if not update_dict:
            raise ValidationException(
                message="更新数据不能为空",
                details={"update_data": "至少提供一个需要更新的字段"}
            )
        # userid检验
        if not (isinstance(user_id, int) and len(str(user_id)) == 16):
            raise ValidationException(
                message="操作人ID必须为16位正整数",
                details={"userid": user_id, "error": "ID长度非16位或非正整数"}
            )
        # 调用服务层更新工种
        item = XiangBaoGongZhongService.update_xiangBaoGongZhong(
            request=request,
            xbgzId=xbgzId,
            up_userid=user_id,
            update_data=update_data,
        )

        return Success(
            msg="更新工种成功",
            data=item
        )
    except Exception as e:
        # 未知异常记录日志并返回500错误
        raise AppException(
            code=500,
            message="更新工种失败 ",
            details={"error": str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )
@router.post(
    "/restore/{xbgzId}",
    summary="恢复删除的工种",
    description="恢复软删除工种（标记为未删除状态，清空删除人员）"
)
async def restore_xiangBaoGongZhong(
        request: Request,
        user_id: int = Query(..., description="用户唯一标识"),
        xbgzId: int = Path(..., description="工种ID"),
):
    try:
        # 参数校验
        if not xbgzId or xbgzId < 0:
            raise ValidationException(
                message="工种ID无效",
                details={"xbgzId": xbgzId}
            )
        if not (isinstance(xbgzId, int) and len(str(xbgzId)) == 16):
            raise ValidationException(
                message="工种ID必须为16位正整数",
                details={"xbgzId": xbgzId, "error": "ID长度非16位或非正整数"}
            )
        # userid检验
        if not (isinstance(user_id, int) and len(str(user_id)) == 16):
            raise ValidationException(
                message="操作人ID必须为16位正整数",
                details={"userid": user_id, "error": "ID长度非16位或非正整数"}
            )
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
    except Exception as e:
        raise AppException(
            code=500,
            message="恢复工序失败 ",
            details={"error": str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )

@router.patch(
    "/delete/",
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
        del_userid = deleted_request.del_userid
        xbgzIds = deleted_request.xbgz_ids
        for xbgzId in xbgzIds:
            if not (isinstance(xbgzId, int) and len(str(xbgzId)) == 16):
                raise ValidationException(
                    message="工种ID必须为16位正整数",
                    details={"xbgzId": xbgzId, "error": "ID长度非16位或非正整数"}
                )
        # userid检验
        if not (isinstance(del_userid, int) and len(str(del_userid)) == 16):
            raise ValidationException(
                message="操作人ID必须为16位正整数",
                details={"del_userid": del_userid, "error": "ID长度非16位或非正整数"}
            )
        if not xbgzIds:
            raise ValidationException(
                message="工种ID列表不能为空"
            )
        from app.services.system_manage.XiangBaoGongZhong_service import XiangBaoGongZhongService
        delete_count = XiangBaoGongZhongService.batch_delete_xiangBaoGongZhong(
            request=request,
            xbgz_ids=xbgzIds,
            user_id=del_userid
        )
        return Success(
            msg=f"成功删除{str(delete_count)}条记录",
            data={"delete": delete_count}
        )
    except Exception as e:
        raise AppException(
            code=500,
            message="删除工种失败 ",
            details={"error": str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )
@router.get(
    "/search_all/",
    response_model=List[Dict[str,Any]],
    summary="获取所有工种信息",
    description="返回工种数据，包含ID和名称"
)
async def get_all_xiangBaoGongZhong(
        request: Request,
        userid: int,
        keywords: Optional[str],
):
    """
    获取所有工种信息

    - **返回格式**: [{"query.xbgzId": int, "query.gongZhongMingCheng": str}, ...]
    """
    try:

        result = XiangBaoGongZhongService.search_all_xiangBaoGongZhong(userid=userid,request=request,keywords=keywords)
        return Success(
            msg="搜索成功",
            data={"result": result}
        )
    except Exception as e:
        traceback.print_exc()
        raise AppException(
            code=500,
            message="获取下拉栏工种失败 ",
            details={"error": str(e),
                     "traceback": traceback.format_exc().split("\n") if settings.debug else None
                     }
        )



