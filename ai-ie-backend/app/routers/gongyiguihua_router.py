# 工艺规划
from typing import Optional

from fastapi import APIRouter, Request
from app.services.gongyiguihua.gongyiguihua_service import PriceService
from app.utils.exceptions import ValidationException, AppException
from app.schemas.gongyiguihua.price_schemas import PriceCalculationResponse
from app.utils.response import Success
from app.utils.exceptions import ProcessPlanningException



router = APIRouter(
    prefix="/GongYiGuiHua",
    tags=["工艺规划"]
)

@router.get("/{xbkhid}",
               summary="点击按钮获取khid返回款号名称、工序、工种、工价",
               response_model=PriceCalculationResponse )
async def get_kh(
        request: Request,
        xbkhid: int,
        userid: Optional[int] = None
):

    """
    根据箱包款号表ID进行工艺规划,返回款号名称、总工价、工序、工种、工价
    """

    try:
    # 参数格式校验
        if not (isinstance(xbkhid, int) and len(str(xbkhid)) == 16):
            raise ValidationException(message="款号表主键ID必须为16位正整数",
                                    details={"khid": xbkhid, "error": "ID长度非16位或非正整数"})

    # 调用Service层方法，获取处理后的结构化数据
        price_service = PriceService()
        labor_cost = await price_service.get_work_processing(int(xbkhid), request,userid)

        return Success(
            code=200,
            msg="工艺规划完成",
            data=labor_cost
        )

    # 捕获Service层抛出的业务异常
    except AppException as e:
        raise e
    except Exception as e:
        raise ProcessPlanningException(
            message=f"工艺规划失败: {str(e)}",
            details={
                "error_category": "system_error",
                "error_type": type(e).__name__,
                "xbkhid": xbkhid,
            }
        )


