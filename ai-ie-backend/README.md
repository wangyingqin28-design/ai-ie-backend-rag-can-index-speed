# ai-ie-backend

python后端

# 1. 安装 pip-tools
pip install pip-tools

# 2. 导出依赖（覆盖原有 requirements.txt）
pip list --format=freeze > requirements.txt

# 4. 数据库逆向生成所有表model命令
--table 指定要生成模型的表名（可多个，逗号分隔）  
--schema 如需指定非默认 schema（如 dbo） 
--schema=your_schema_name  
--outfile 指定生成目录与文件名

python -m sqlacodegen "mssql+pyodbc://用户名:密码@主机地址:端口/数据库名?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes" --outfile models/orm_models.py

# 5. 在定义函数时使用Success统一响应类指定类型：Success[UserResponse]，详情见utils中的response.py
@app.get("/user/{user_id}")
async def get_user(user_id: int) -> Success[UserResponse]:
    user_data = {"id": user_id, "username": "test", "email": "test@xxx.com", "token": "123"}
    return Success(data=UserResponse(**user_data))
#将响应类对象插入Success中的data, ** 表示将user_data字典解包，
{code: 状态码, msg: 提示信息, data: 业务数据}，code与msg已有默认值

# 6. 基于orm_model生成基础响应模型参考app/schemas/dxf/dxf_schemas.py，使用sqlalchemy_to_pydantic()+继承

# 7. 统一异常处理：在app/utils/exceptions.py文件中自定义异常类，在app/utils/exception_handler.py文件中参考异常处理三道防线

# 8. 全局事务处理示例：
# （1）. 创建FastAPI应用实例
app = FastAPI(title="你的项目名称"...)

# （2）. 注册事务中间件（核心：必须在路由/异常处理器之前注册）
app.add_middleware(DBTransactionMiddleware)

# （3）. 注册异常处理器（与事务中间件配合）
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# 9. 接口示例
@app.get("/get/xiangbao/{xiangbao_id}")
async def get_xiangbao(request: Request, xiangbao_id: int):
    """
    查询箱包款号（只读操作示例）
    只读操作需标记 request.state.read_only = True，无需提交事务
    """
    # 标记为只读操作，事务中间件会跳过提交步骤
    request.state.read_only = True
    # 业务逻辑...
    return Success(...)
    
# 10.项目启动命令
# （1）. 启动 mssql数据库
......

# （2）. 启动/关闭容器
docker compose up -d
docker compose down

# （3）. uvicorn启动后端
uvicorn app.main:app --host 0.0.0.0 --log-config scripts/uvicorn-log-config.yaml

# （4）. 启动 celeryworker
celery -A config.celery worker -l INFO --pool=threads --concurrency=4

# （5）. 启动 celerybeat
celery -A config.celery beat -l INFO



