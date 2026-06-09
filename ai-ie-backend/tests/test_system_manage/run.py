#!/usr/bin/env python3
"""
FastAPI SQL Server 应用启动脚本
"""

import uvicorn
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 将项目根目录（back）添加到Python路径，是关键一步
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 从新路径导入应用实例
from app.api.system_manage.main import app

# 加载环境变量
# 自动加载.env文件（不需要指定路径）
load_dotenv()

# 读取配置
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# 数据库配置检查
required_env_vars = ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]

if missing_vars:
    print(f"❌ 缺少必要的环境变量: {missing_vars}")
    print("请在 .env 文件中配置以下变量:")
    print("DB_HOST=YULITH")
    print("DB_NAME=getai")
    print("DB_USER=your_username")
    print("DB_PASSWORD=your_password")
    print("DB_DRIVER=ODBC Driver 17 for SQL Server")
    sys.exit(1)

print("=" * 50)
print("AI标准流程管理系统")
print("=" * 50)
print(f"• 数据库主机: {os.getenv('DB_HOST')}")
print(f"• 数据库名称: {os.getenv('DB_NAME')}")
print(f"• 服务地址: {API_HOST}:{API_PORT}")
print(f"• 调试模式: {DEBUG}")
print("=" * 50)

if __name__ == "__main__":
    import uvicorn
    try:
        # 启动应用
        uvicorn.run(
            "app.api.system_manage.main:app",
            host=API_HOST,
            port=API_PORT,
            reload=DEBUG,
            log_level="info" if DEBUG else "warning",
            access_log=True,
            workers=1 if DEBUG else 4
        )
    except KeyboardInterrupt:
        print("\n🛑 应用已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)