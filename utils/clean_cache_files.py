import os
from core.logger import logger
from core.redis_client import redis_client
from settings.config import AUDIO_DIR, settings
from api_versions.v2.models import AudioData


def check_admin_password(*, password, **kwargs) -> bool:
    return True

async def clean_redis_cache(**kwargs):
    try:
        await redis_client.flushall()
    except Exception as e:
        logger.error(f"清除缓存失败: {e}")


def clean_files():
    file_list = os.listdir(AUDIO_DIR)
    logger.debug(f"{__name__} file_list: {file_list}")

    try:
        for file_name in file_list:
            abs_path = os.path.join(AUDIO_DIR, file_name)
            # logger.debug(f"{file_name} 已成功移除")
            if os.path.isfile(abs_path):
                os.remove(abs_path)
    except Exception as e:
        logger.error(f"发生了一些错误: {e}")
    else:
        logger.debug("操作成功")

async def clean_audio_data():
    """清理数据库中的音频数据记录"""
    try:
        await AudioData.all().delete()
        logger.debug("数据库音频记录已清理")
    except Exception as e:
        logger.error(f"清理数据库音频记录失败: {e}")


#清空缓存和文件(不通过语音)
async def clear_cache_files(*, text:str, password=None, **kwargs):

    logger.debug(f"text: {text}")
    logger.debug(f"settings.order: {settings.order}")

    # 校验文本是否命中
    if text.strip() == settings.order.strip():
        # 校验密码
        if is_admin := check_admin_password(password=password):
            # 清空redis
            await clean_redis_cache()

            # 清空文件
            clean_files()
            
            # 清空数据库音频记录
            await clean_audio_data()

            # 记录日志
            logger.warning("全部缓存、文件和数据库记录已清理")

            # 发送清理成功的文本音频URL
            return "全部文件和缓存已全部清空"
    # 未命中 直接返回咨询的文本
    return text