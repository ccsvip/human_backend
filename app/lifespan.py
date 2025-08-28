from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.lifespan_tools import init_start_lifespan
from tortoise import Tortoise, run_async
from settings.tortoise_config import TORTOISE_ORM
from settings.config import settings


async def start_app():
    print("✅ fastapi已启动")
    await init_start_lifespan()
    
async def shutdown():
    print("❌ fastapi已关闭")
    
    # 清理TTS会话资源
    try:
        from core.services.v2.tts_server import cleanup_tts_session
        await cleanup_tts_session()
        print("❌ TTS会话资源已清理")
    except Exception as e:
        print(f"⚠️ TTS会话清理失败: {e}")
    
    if settings.enable_database:
        await Tortoise.close_connections()
        print("❌ 数据库连接已关闭")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_app()
    yield
    await shutdown()


