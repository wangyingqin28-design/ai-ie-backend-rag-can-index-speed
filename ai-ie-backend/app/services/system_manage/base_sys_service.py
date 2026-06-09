from typing import Any, Dict, List, Optional, Type

from fastapi import Request
from sqlalchemy.orm import Session, Query
import os
from dotenv import load_dotenv
load_dotenv()
GETSOFT_ID_STR = os.getenv("GETSOFT_ID")
GETSOFT_ID = int(GETSOFT_ID_STR)

class BaseService:
    """基础服务类，提供通用数据库操作方法"""
    @staticmethod
    def get_db_session(request: Request) -> Session:
        """从请求中获取数据库会话"""
        return request.state.db
    @classmethod
    def mark_read_only(cls, request: Request) -> None:
        """标记为只读接口"""
        request.state.read_only = True
    @classmethod
    def paginate_query(
            cls,
            query: Query,
            page: int = 1,
            page_size: int = 20,
            max_page_size: int = 100
    ) -> Dict[str, Any]:
        """
        通用分页查询

        Args:
            query: SQLAlchemy查询对象
            page: 页码
            page_size: 每页数量
            max_page_size: 最大每页数量限制

        Returns:
            分页结果字典，包含items、分页信息和导航信息
        """
        # 参数校验
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        elif page_size > max_page_size:
            page_size = max_page_size
        # 计算总数
        total = query.count()
        # 分页查询
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        # 计算总页数
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_previous": page > 1,  # 新增：是否有上一页
            "has_next": page < total_pages,  # 新增：是否有下一页
            "start_index": (page - 1) * page_size + 1 if total > 0 else 0,  # 新增：当前页起始索引
            "end_index": min(page * page_size, total)  # 新增：当前页结束索引
        }

    @classmethod
    def paginate_results(
            cls,
            results: List[Any],  # 数据列表，不是Query对象
            total: int,  # 总记录数
            page: int = 1,
            page_size: int = 20
    ) -> Dict[str, Any]:
        """
        对已有结果进行分页包装（与原有paginate_query方法区别开）

        Args:
            results: 当前页数据列表
            total: 总记录数
            page: 当前页码
            page_size: 每页数量

        Returns:
            标准分页响应格式
        """
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return {
            "items": results,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_previous": page > 1,
            "has_next": page < total_pages,
            "start_index": (page - 1) * page_size + 1 if total > 0 else 0,  # 新增：当前页起始索引
            "end_index": min(page * page_size, total)  # 新增：当前页结束索引
        }

    @classmethod
    def get_by_id(
            cls,
            request: Request,
            model_class: Type,
            record_id: int,
    ) -> Optional[Any]:
        """
        通用根据ID获取记录方法

        Args:
            request: FastAPI请求对象
            model_class: SQLAlchemy模型类
            record_id: 记录ID

        Returns:
            记录对象或None

        Raises:
            NotFoundException: 记录不存在
        """
        db = cls.get_db_session(request)

        # 自动获取主键字段名
        primary_key = cls._get_primary_key_field(model_class)

        # 构建查询
        record = db.query(model_class).filter(
            getattr(model_class, primary_key) == record_id
        ).first()
        return record

    @staticmethod
    def _get_primary_key_field(model_class: Type) -> str:
        """
        静态方法：获取模型的主键字段名
        """
        # 实现获取主键的逻辑
        mapper = model_class.__mapper__
        primary_keys = mapper.primary_key

        if not primary_keys:
            raise ValueError(f"模型 {model_class.__name__} 没有定义主键")

        # 返回第一个主键字段名
        return primary_keys[0].name