from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


# ==================== 请求模型 ====================
class PriceCalculationRequest(BaseModel):
    """
    工价计算请求模型
    """
    xbkhid: int = Field(..., ge=10**15, le=10**16-1, description="箱包款号表主键ID，必须为16位正整数")


# ==================== 响应模型 ====================
class GongYiItem(BaseModel):
    """
    工序列表模型
    """
    gongXuMingCheng: str = Field(..., description="工序名称")
    gongZhongMingCheng: str = Field(..., description="工种名称")
    gongJia: float = Field(..., ge=0, description="工序工价")



class PriceCalculationResponse(BaseModel):
    """
    工价计算响应模型
    """
    xbkhId: int = Field(..., description="箱包款号ID")
    xiangBaoMingCheng: str = Field(..., description="箱包名称")
    zongGongJia: float = Field(..., ge=0, description="总工价")
    gongXuLieBiao: List[GongYiItem] = Field(..., description="工序列表")

    class Config:
        # 允许从字典创建模型
        from_attributes = True
