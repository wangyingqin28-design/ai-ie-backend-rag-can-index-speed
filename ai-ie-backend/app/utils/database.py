from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from pathlib import Path

# 获取当前文件的上级目录（即back/目录）
dotenv_path = Path(__file__).resolve().parent.parent.parent / ".env"
print(dotenv_path)
load_dotenv(dotenv_path=dotenv_path)

# 加载环境变量
load_dotenv()

# SQL Server 连接字符串
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")


# 同步 SQL Server 连接 URL（稳定无坑）
SQLALCHEMY_DATABASE_URL = (
    f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}?"
    f"driver={DB_DRIVER}&"
    "encrypt=no&"
    "TrustServerCertificate=yes&"
    "Connection Timeout=30"  # 增加超时配置，提升稳定性
)

# #连接本地数据库(禁删!!)
# DB_HOST = "localhost"
# DB_NAME = "getsoft"
# DB_USER = ""
# DB_PASSWORD = ""
# DB_DRIVER = "ODBC Driver 17 for SQL Server"
# #SQLAlchemy 连接 URL for SQL Server (Windows 身份验证)
#
# #同步 SQL Server 连接 URL（稳定无坑）
# SQLALCHEMY_DATABASE_URL = (
#     f"mssql+pyodbc://{DB_HOST}/{DB_NAME}?"
#     f"driver={DB_DRIVER.replace(' ', '+')}&"
#     "trusted_connection=yes&"
#     "encrypt=no&"
#     "TrustServerCertificate=yes"
# )


# 2. 创建同步引擎
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600
)

# 同步 Session 工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# # 同步 Base 基类
# class Base(DeclarativeBase):
#     __abstract__ = True

# ====================== 同步依赖（适配 FastAPI 异步调用） ======================
def get_db():
    """同步数据库依赖：供中间件/接口调用"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()




