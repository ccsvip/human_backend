import asyncio
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .lifespan import lifespan
from core.logger import logger
from tortoise.contrib.fastapi import register_tortoise
from settings.tortoise_config import TORTOISE_ORM
from settings.config import AUDIO_DIR




def create_app() -> FastAPI:
    app:FastAPI = FastAPI(
        title="数字人项目后端接口",
        docs_url="/",
        version="0.0.1",
        lifespan=lifespan,
        swagger_ui_parameters={"defaultModelsExpandDepth": -1}
    )

    @app.get("/health", status_code=200, include_in_schema=False)
    def health():
        return {"status": "200", "message": "health"}

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=3600
    )

    register_tortoise(
        app,
        config=TORTOISE_ORM,
        generate_schemas=False, # 开发环境建议True 生产环境建议False
        add_exception_handlers=True

    )

    @app.middleware("http")
    async def suppress_disconnect_errors(request: Request, call_next):
        try:
            return await call_next(request)
        except ConnectionResetError as e:
            logger.debug(f"客户端提前断开连接: {request.client} - {e}")

    @app.middleware("http")
    async def user_context_middleware(request:Request, call_next):
        user_id = request.headers.get("user_id", "anonymous")
        reference_id = request.headers.get("reference_id")
        api_key = request.headers.get("dify_api_key", "")
        mode = request.headers.get("mode", '')
        tts_speed = request.headers.get("tts_speed", 1.2)
        translate = request.headers.get("translate", "zh")
        greeting = request.headers.get("greeting", "")

        logger.info(f"请求头: {request.headers}")

        request.state.user_id = user_id # 注入到请求状态
        request.state.reference_id = reference_id
        request.state.api_key = api_key
        request.state.mode = mode
        request.state.tts_speed = tts_speed
        request.state.translate = translate
        request.state.greeting = greeting

        request.state.streaming_lock = asyncio.Lock()

        response = await call_next(request)
        return response

    # 使用配置中的静态文件目录
    app.mount("/static", StaticFiles(directory=str(AUDIO_DIR)), name="audio_files")
    
    # 按功能模块独立注册路由，避免统一的"管理API"分组
    from api_versions.v1.routers import router as v1_router
    from api_versions.v2.routers import router as v2_router
    from api_versions.v3.routers import router as v3_router
    from api_versions.utils.routers import router as utils_router
    from api_versions.api.routers import router as api_router
    from api_versions.device.routers import routers as device_router
    from api_versions.model.routers import router as model_router
    from api_versions.media.routers import router as media_router
    from api_versions.env.routers import router as env_router
    from api_versions.app.routers import router as app_router
    from api_versions.auth.routers import router as auth_router
    from api_versions.cache.routers import router as cache_router
    from api_versions.logs.routers import router as logs_router
    from api_versions.config.routers import router as config_router
    from api_versions.wake.routers import router as wakeword_router
    from api_versions.audio.audio_data import router as audio_data_router
    from api_versions.logo.routers import router as logo_router

    # 数字人核心接口和工具接口
    app.include_router(router=v2_router, prefix="/v2", tags=['数字人核心接口'])
    app.include_router(router=utils_router, prefix="/utils", tags=['工具接口'], include_in_schema=False)
    app.include_router(router=v1_router, prefix="/v1", tags=['V1版本（已弃用）'], include_in_schema=False)
    app.include_router(router=v3_router, prefix="/v3", tags=['数字人核心接口'])
    
    # 各模块独立注册
    app.include_router(router=device_router, prefix="/api/device", tags=['设备管理'])
    app.include_router(router=model_router, prefix="/api/model", tags=['模型管理'])
    app.include_router(router=media_router, prefix="/api/media", tags=['媒体管理'])
    app.include_router(router=env_router, prefix="/api/env", tags=['虚拟环境'], include_in_schema=False)
    app.include_router(router=app_router, prefix="/api/app", tags=['应用管理'])
    app.include_router(router=auth_router, prefix="/api/auth", tags=['认证授权'], include_in_schema=False)
    app.include_router(router=cache_router, prefix="/api/cache", tags=['缓存管理'], include_in_schema=False)
    app.include_router(router=config_router, prefix="/api/config", tags=['系统配置'])
    app.include_router(router=logs_router, prefix="/api/logs", tags=['日志管理'])
    app.include_router(router=wakeword_router, prefix="/api/wakeword", tags=['唤醒词管理'])
    app.include_router(router=audio_data_router, prefix="/api/audio-data", tags=['音频数据管理'])
    app.include_router(router=logo_router, prefix="/api/logo", tags=['Logo管理'])

    # v3接口

    
    
    

    # 在事件循环级别忽略客户端强制断开产生的 ConnectionResetError 低级日志（WinError 10054）
    loop = asyncio.get_event_loop()
    def _ignore_conn_reset(loop, context):
        exc = context.get("exception")
        if isinstance(exc, ConnectionResetError):
            logger.debug(f"忽略 ConnectionResetError: {exc}")
            return  # 吞掉
        loop.default_exception_handler(context)
    loop.set_exception_handler(_ignore_conn_reset)

    return app