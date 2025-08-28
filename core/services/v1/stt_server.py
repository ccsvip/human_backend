import random
import hashlib
import aiohttp
import asyncio
from fastapi import UploadFile, File, Request
from core.logger import logger
from core.exceptions import AudioExceptions
from settings.config import settings, AUDIO_DIR, TEXT_LIST
import aiofiles
from core.dependencies import urls, get_headers
from core.decorators.async_tools import async_timer
from core.redis_client import redis_client


# ------------------------------------------------------------------------------
async def _audio_to_text_request(request, file_content, file_name, content_type):
    headers = get_headers(request).copy()
    logger.debug(f"headers: {headers}")
    form = aiohttp.FormData()
    form.add_field("file", value=file_content, filename=file_name, content_type=content_type)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                urls['audio-to-text'],
                headers=headers,
                data=form,
            ) as response:
                json_data = await response.json()
                return json_data.get("text", "")
    except Exception as e:
        logger.error(f"❌ STT服务器错误 {e}")  # TODO 发邮件通知
        return random.choice(TEXT_LIST)

@async_timer
async def audio_to_text(request: Request, audio_file: UploadFile = File(...)):
    file_name = audio_file.filename
    if not file_name.endswith(('mp3', 'mp4', 'mpeg', 'mpga', 'm4a', 'wav', 'webm')):
        logger.error("❌ 上传的音频格式不正确")
        raise AudioExceptions(400, "格式不正确 仅支持mp3, mp4, mpeg, mpga, m4a, wav, webm")

    file_content = await audio_file.read()
    if len(file_content) > settings.max_file_size:
        raise AudioExceptions(415, "最大支持15MB上传")

    # 计算音频哈希值（唯一标识）用于缓存
    audio_sha256 = hashlib.sha256(file_content).hexdigest()

    # 检查缓存是否存在
    is_cached = await redis_client.exists(f"stt:{audio_sha256}")
    if is_cached:
        cached_text = await redis_client.get(f"stt:{audio_sha256}")
        logger.info(f"🎯 命中STT缓存(哈希: {audio_sha256[:10]})")
        return cached_text

    # TODO 这里是否需要考虑路径问题？
    async with aiofiles.open(AUDIO_DIR / file_name, "wb") as f:
        await f.write(file_content)

    # 无缓存时调用STT获取文本内容 发起请求获取结果
    text = await _audio_to_text_request(
        request=request,
        file_content=file_content,
        file_name=file_name,
        content_type=audio_file.content_type
    )
    if not text or text.strip() == "":
        # 写入缓存
        asyncio.create_task(redis_client.set(
            name=f"stt:{audio_sha256}",
            value=text,
            ex=settings.cache_expiry  # 秒
        ))
        logger.info(f"💾 新增文本读取失败STT缓存(哈希: {audio_sha256[:10]})")
        return random.choice(TEXT_LIST)
    logger.debug(f"文本内容: {text}")

    # 写入缓存
    asyncio.create_task(redis_client.set(
        name=f"stt:{audio_sha256}",
        value=text,
        ex=settings.cache_expiry # 秒
    ))
    logger.info(f"💾 新增STT缓存(哈希: {audio_sha256[:10]})")
    return text.strip("？?。.>")

# ------------------------------------------------------------------------------




