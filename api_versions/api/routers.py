from fastapi import APIRouter
from api_versions.device.routers import routers as device_router
from api_versions.env.routers import router as env_router
from api_versions.app.routers import router as app_router
from api_versions.media.routers import router as media_router
from api_versions.cache.routers import router as cache_router
from api_versions.auth.routers import router as auth_router
from api_versions.model.routers import router as model_router
from api_versions.wake.routers import router as wake_router
from api_versions.audio.audio_data import router as audio_data_router

router = APIRouter()
router.include_router(device_router, prefix="/device", tags=['设备管理'])
router.include_router(env_router, prefix="/env", tags=['虚拟环境'])
router.include_router(app_router, prefix="/app", tags=['应用管理'])
router.include_router(media_router, prefix="/media", tags=['媒体管理'])
router.include_router(cache_router, prefix="/cache", tags=['缓存管理'])
router.include_router(auth_router, prefix="/auth", tags=['认证授权'])
router.include_router(model_router, prefix="/model", tags=['模型管理']) 
router.include_router(wake_router, prefix="/wakeword", tags=['唤醒词管理'])
router.include_router(audio_data_router, prefix="/audio-data", tags=['音频数据管理'])