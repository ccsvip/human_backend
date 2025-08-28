"""
数据库表初始化脚本
用于创建日志相关的数据库表
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tortoise import Tortoise
from settings.config import TORTOISE_ORM
from core.logger import logger

async def init_db_tables():
    """初始化数据库表"""
    try:
        logger.info("🚀 开始初始化数据库表...")
        
        # 初始化Tortoise ORM
        await Tortoise.init(config=TORTOISE_ORM)
        
        # 生成数据库表结构
        await Tortoise.generate_schemas()
        
        logger.info("✅ 数据库表初始化完成")
        
    except Exception as e:
        logger.error(f"❌ 数据库表初始化失败: {str(e)}")
        raise e
    finally:
        # 关闭数据库连接
        await Tortoise.close_connections()

if __name__ == "__main__":
    asyncio.run(init_db_tables())
