from typing import Optional, Any

class AppException(Exception):
    """
    自定义业务异常类 —— 用于抛出可预期的业务错误（如参数错误、数据不存在、权限不足）
    可被专门的异常处理器捕获，返回标准化错误响应
    """
    def __init__(
        self,
        code: int,                # 业务错误码（如404/403/10001等）
        message: str,             # 错误提示信息（给前端展示）
        details: Optional[Any] = None,  # 错误详情（如校验失败的字段、额外说明）
        status_code: int = 400    # HTTP状态码（默认400客户端错误）
    ):
        self.code = code          # 业务错误码
        self.message = message    # 错误提示
        self.details = details    # 错误详情
        self.status_code = status_code  # HTTP响应状态码
        super().__init__(message)  # 调用父类Exception的构造方法（保留原生异常特性）

# 业务异常子类，统一继承AppException
class NotFoundException(AppException):
    """资源不存在异常（如用户/数据找不到）"""
    def __init__(self, message: str = "资源不存在", details: Optional[Any] = None):
        super().__init__(code=404, message=message, details=details, status_code=404)

class PermissionDeniedException(AppException):
    """权限不足异常"""
    def __init__(self, message: str = "权限不足", details: Optional[Any] = None):
        super().__init__(code=403, message=message, details=details, status_code=403)

class ValidationException(AppException):
    """参数校验异常"""
    def __init__(self, message: str = "参数校验失败", details: Optional[Any] = None):
        super().__init__(code=400, message=message, details=details, status_code=400)

class AnalysisException(AppException):
    """dxf解析异常"""
    def __init__(self, message: str = "DXF文件解析失败", details: Optional[Any] = None):
        super().__init__(code=500, message=message, details=details, status_code=400)

class SystemException(AppException):
    """系统级异常（数据库/中间件故障）"""
    def __init__(self, message: str = "系统异常", details: Optional[Any] = None):
        super().__init__(code=500, message=message, details=details, status_code=500)

class DataUpdateFailedException(AppException):
    """数据更新失败异常（无匹配记录/更新行数为0）"""
    def __init__(self, message: str = "数据更新失败", details: Optional[Any] = None):
        # （自定义业务码，区别于HTTP码），HTTP状态码保持400
        super().__init__(code=10002, message=message, details=details, status_code=400)

class DeleteFailedException(AppException):
    """数据删除失败异常"""
    def __init__(self, message: str = "数据删除失败", details: Optional[Any] = None):
        # （自定义业务码，区别于HTTP码），HTTP状态码保持400
        super().__init__(code=10003, message=message, details=details, status_code=400)

class UserCreateException(AppException):
    """用户创建失败异常"""
    def __init__(self, message: str = "用户创建失败", details: Optional[Any] = None):
        # （自定义业务码，区别于HTTP码），HTTP状态码保持400
        super().__init__(code=10004, message=message, details=details, status_code=400)

class LoginException(AppException):
    """用户登录异常（Token验证失败/账号密码错误）"""
    def __init__(self, message: str = "登录失败", details: Optional[Any] = None):
        super().__init__(code=10005, message=message, details=details, status_code=401)

class TokenException(AppException):
    """Token无效/过期/注销异常（专门用于Token验证）"""
    def __init__(self, message: str = "Token无效、过期或已注销", details: Optional[Any] = None):
        super().__init__(code=10006, message=message, details=details, status_code=401)# 登录失败返回401

class ProcessPlanningException(AppException):
    """工艺规划失败异常"""
    def __init__(self, message: str = "工艺规划失败", details: Optional[Any] = None):
        super().__init__(code=11001, message=message, details=details, status_code=400)

class ServiceCallException(AppException):
    """服务调用异常（RAG调用失败、网络超时、服务不可用等）"""
    def __init__(self, message: str = "服务调用失败", details: Optional[Any] = None):
        super().__init__(code=11002, message=message, details=details, status_code=400)

class LaborCostCalculationException(AppException):
    """计算工价失败异常"""
    def __init__(self, message: str = "计算工价失败", details: Optional[Any] = None):
        super().__init__(code=11003, message=message, details=details, status_code=400)

class RagResponsePreprocessingException(AppException):
    """大模型返回数据预处理失败异常"""
    def __init__(self, message: str = "大模型返回数据预处理失败", details: Optional[Any] = None):
        super().__init__(code=11004, message=message, details=details, status_code=400)