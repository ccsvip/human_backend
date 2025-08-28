#!/usr/bin/env python3
"""
数据库连接测试脚本
用于诊断局域网部署时的数据库连接问题
"""
import asyncio
import os
from tortoise import Tortoise
from settings.config import settings

async def test_database_connection():
    """测试数据库连接"""
    print("=== 数据库连接测试 ===")
    print(f"数据库主机: {settings.db_host}")
    print(f"数据库端口: {settings.db_port}")
    print(f"数据库用户: {settings.db_user}")
    print(f"数据库名称: {settings.db_name}")
    
    db_url = f"mysql://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"
    print(f"连接字符串: mysql://{settings.db_user}:***@{settings.db_host}:{settings.db_port}/{settings.db_name}")
    
    try:
        # 初始化 Tortoise ORM
        await Tortoise.init(
            db_url=db_url,
            modules={"models": ["api_versions.v2.models"]}
        )
        print("✅ 数据库连接成功!")
        
        # 测试查询
        from api_versions.v2.models import Device, App
        device_count = await Device.all().count()
        app_count = await App.all().count()
        print(f"📊 设备数量: {device_count}")
        print(f"📊 应用数量: {app_count}")
        
        # 测试写入
        test_device = await Device.create(
            name=f"test_device_{os.getpid()}",
            description="测试设备连接"
        )
        print(f"✅ 测试写入成功! 设备ID: {test_device.id}")
        
        # 清理测试数据
        await test_device.delete()
        print("🧹 测试数据已清理")
        
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        print(f"错误类型: {type(e).__name__}")
        
        # 提供解决建议
        if "Access denied" in str(e):
            print("💡 建议: 检查数据库用户名和密码")
        elif "Can't connect" in str(e) or "Connection refused" in str(e):
            print("💡 建议: 检查数据库主机地址和端口")
        elif "Unknown database" in str(e):
            print("💡 建议: 检查数据库名称是否存在")
            
    finally:
        await Tortoise.close_connections()

if __name__ == "__main__":
    asyncio.run(test_database_connection())