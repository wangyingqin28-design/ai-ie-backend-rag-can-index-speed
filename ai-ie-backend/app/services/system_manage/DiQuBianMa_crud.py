from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models import orm_models
from app.utils.exceptions import (
    DataUpdateFailedException,
)


class DiQuBianMaCRUD:
    @staticmethod
    def search_all(db: Session) -> List[Dict[str, Any]]:
        try:
            # 构建查询
            results = db.query(orm_models.AIDiQuBianMa).all()

            response_data = []

            # 遍历查询结果，构建指定格式的字典
            for item in results:
                response_data.append({
                    "dqbmId": item.dqbmId,  # 修正：去掉多余的 "Id"
                    "diQuMingCheng": item.diQuMingCheng,
                    "fuJiDiquBianMa": item.fuJiDiquBianMaId,  # 修正：使用正确的属性名
                    "diQuCengJi": item.diQuCengJi  # 修正：保持大小写一致
                })

            return response_data
        except Exception as e:
            # 可以根据需要添加异常处理逻辑
            raise DataUpdateFailedException(
                message="查询地区编码失败,DiQuBianMaCRUD_crud.search_all",
                details={
                    "error": str(e)
                }
            )