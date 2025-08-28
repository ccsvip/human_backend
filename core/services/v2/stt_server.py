import random
import colorama
import aiofiles
import hashlib
import aiohttp
import asyncio
import time
from fastapi import UploadFile, File, Request
from core.logger import logger
from core.exceptions import AudioExceptions
from settings.config import settings, AUDIO_DIR
from utils.tools import get_file_name
import aiofiles
from core.dependencies import urls, get_headers
from core.decorators.async_tools import async_timer
from core.redis_client import redis_client


# ------------------------------------------------------------------------------
async def _audio_to_text_request(request, file_content, file_name, content_type):
    start_time = time.time()
    headers = headers = get_headers(request).copy()
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
                elapsed = time.time() - start_time
                return json_data.get("text", "")
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"❌ STT服务器错误 {e}，耗时: {elapsed:.3f}秒")  # TODO 发邮件通知
        return ''

# @async_timer
async def audio_to_text(request: Request, audio_file: UploadFile = File(...)):
    total_start_time = time.time()
    
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
    cache_key = f"stt:{audio_sha256}"
    is_cached = await redis_client.exists(cache_key)
    
    if is_cached:
        cached_text = await redis_client.get(cache_key)
        logger.info(f"🎯 命中STT缓存(哈希: {audio_sha256[:10]})，总耗时: {time.time() - total_start_time:.3f}秒")
        return cached_text

    # 无缓存时调用STT获取文本内容 发起请求获取结果
    text = await _audio_to_text_request(
        request=request,
        file_content=file_content,
        file_name=file_name,
        content_type=audio_file.content_type
    )
    # 处理STT结果
    if text:
        
        # 并行处理：同时保存文件和发送STT请求
        save_file_task = asyncio.create_task(save_audio_file(file_name, file_content))
        
        # 等待保存任务完成
        try:
            await save_file_task
            logger.debug("📁 音频文件保存完成")
        except Exception as e:
            logger.error(f"❌ 音频文件保存失败: {e}")
        text = text.strip("？?。.>")
        logger.info(f"💾 新增STT缓存(哈希: {audio_sha256[:10]})")
        asyncio.create_task(redis_client.set(
            name=cache_key,
            value=text,
            ex=settings.cache_expiry # 秒
        ))
        return text
    else:
        logger.debug("stt服务异常")
        return ''

# ------------------------------------------------------------------------------


# websocket tts接口
async def audio_to_text_ws(file_content: bytes):
    audio_sha256 = hashlib.sha256(file_content).hexdigest()

    if await redis_client.exists(f"stt:{audio_sha256}"):
        return await redis_client.get(f"stt:{audio_sha256}")
    
    # 保存临时文件 （根据实际需求调整）
    file_name = get_file_name()
    async with aiofiles.open(AUDIO_DIR / file_name, "wb") as f:
        await f.write(file_content)
    
    text = await _audio_to_text_request_ws(file_content, file_name)

    await redis_client.setex(
        name=f"stt:{audio_sha256}",
        value=text,
        ex=settings.cache_expiry # 秒

    )
    return text


async def _audio_to_text_request_ws(file_content, file_name):
    # 这里保持原有逻辑 但需要调整为适合websocket的调用方式
    form = aiohttp.FormData()
    form.add_field("file", file_content, filename=file_name)
    async with aiohttp.clientsession() as session:
        async with session.post(
            urls['audio-to-text'],
            data=form,
        ) as response:
            return await response.json().get("text", "")
        
# 辅助函数：保存音频文件
async def save_audio_file(file_name, file_content):
    async with aiofiles.open(AUDIO_DIR / file_name, "wb") as f:
        await f.write(file_content)
    return True
        