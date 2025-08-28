import aiohttp
import asyncio
import edge_tts
import aiofiles
import functools
import tempfile
import subprocess
import hashlib
from pathlib import Path
import concurrent.futures
from pydub import AudioSegment
from io import BytesIO
from settings.config import AUDIO_DIR

from core.dependencies import urls
from settings.config import settings
from core.logger import logger
from core.decorators.async_tools import async_timer
from core.redis_client import redis_client
import functools

# 连接超时配置
TTS_CONNECTION_TIMEOUT = aiohttp.ClientTimeout(
    total=15,      # 总超时时间
    connect=3,     # 连接超时时间
    sock_read=5,   # 读取超时时间
    sock_connect=3 # socket连接超时
)

# 全局TTS连接器和会话，用于连接池复用
_tts_connector = None
_tts_session = None

def get_tts_connector():
    """获取TTS专用连接器，用于连接池优化"""
    global _tts_connector
    if _tts_connector is None or _tts_connector.closed:
        _tts_connector = aiohttp.TCPConnector(
            limit=50,  # TTS专用连接池
            limit_per_host=20,  # 每个TTS主机的连接数
            ttl_dns_cache=300,
            use_dns_cache=True,
            enable_cleanup_closed=True,
            keepalive_timeout=60,  # 保持连接60秒
        )
    return _tts_connector

async def get_tts_session():
    """获取TTS专用会话，避免重复创建ClientSession的开销"""
    global _tts_session
    if _tts_session is None or _tts_session.closed:
        _tts_session = aiohttp.ClientSession(
            connector=get_tts_connector(),
            timeout=TTS_CONNECTION_TIMEOUT
        )
    return _tts_session

async def cleanup_tts_session():
    """清理TTS会话资源"""
    global _tts_session, _tts_connector
    if _tts_session and not _tts_session.closed:
        await _tts_session.close()
        _tts_session = None
    if _tts_connector and not _tts_connector.closed:
        await _tts_connector.close()
        _tts_connector = None



# 建立局部线程池（最多并发 8 个音频处理任务）
TTS_THREAD_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=8)

async def save_audio_to_db(kwargs, text, file_name, tts_start_time):
    """异步保存音频数据到数据库，不阻塞主流程"""
    try:
        from api_versions.v2.models import AudioData
        from datetime import datetime
        
        user_question = kwargs.get('user_question', text[:100] + '...' if len(text) > 100 else text)
        ai_response_text = kwargs.get('ai_response_text', text)
        tts_started_at = kwargs.get('tts_started_at', tts_start_time)
        
        await AudioData.create(
            user_question=user_question,
            ai_response_text=ai_response_text,
            audio_file_path=f"static/{file_name}",
            tts_started_at=tts_started_at,
            tts_completed_at=datetime.now()
        )
    except Exception as e:
        logger.warning(f"保存音频数据到数据库失败: {e}")

@async_timer
async def text_to_audio_old(*, request, text, **kwargs):
    from utils.tools import get_file_name
    from datetime import datetime
    
    # 记录TTS开始时间
    tts_start_time = datetime.now()
    kwargs['tts_started_at'] = tts_start_time

    reference_id = kwargs.get('reference_id') or request.state.reference_id

    # 可选：构造缓存 key（建议用于后续 Redis 缓存）
    # cache_key = f"tts_cache:{reference_id}:{hashlib.md5(text.encode()).hexdigest()}"
    # cached_url = await redis_client.get(cache_key)
    # if cached_url:
    #     return cached_url.decode()

    data = {
        "text": text,
        "reference_id": reference_id or settings.reference_id,
        "seed": 42,
        "normalize": True,
        "chunk_length": 100,
        "temperature": 0.6,
        "top_p": 0.8,
        "prosody": {"speed": 2.0}
    }

    logger.debug(f"{__name__} data: {data}")

    session = await get_tts_session()
    async with session.post(url=urls['text-to-audio'], json=data) as resp:
        audio_bytes = await resp.read()

    loop = asyncio.get_event_loop()

    try:
        audio_segment = await loop.run_in_executor(
            TTS_THREAD_POOL,
            functools.partial(AudioSegment.from_wav, BytesIO(audio_bytes))
        )
    except Exception as e:
        raise ValueError(f"音频解析失败，请检查API返回数据格式 : [{text}]") from e

    buffer = BytesIO()
    await loop.run_in_executor(
        TTS_THREAD_POOL,
        functools.partial(
            audio_segment.export,
            buffer,
            format="wav",
            codec="pcm_s16le",
            parameters=["-ar", "16000", "-ac", "1"]
        )
    )
    buffer.seek(0)

    file_name = f"{get_file_name()}.wav"
    async with aiofiles.open(AUDIO_DIR / file_name, "wb") as f:
        await f.write(buffer.read())

    url = request.url_for("audio_files", path=file_name)

    # 可选：设置缓存
    # await redis_client.setex(cache_key, settings.cache_expiry, str(url))

    # 自动保存音频数据到数据库
    try:
        from api_versions.v2.models import AudioData
        from datetime import datetime
        
        # 从请求状态或kwargs中获取用户问题和AI回复
        user_question = kwargs.get('user_question', text[:100] + '...' if len(text) > 100 else text)
        ai_response_text = kwargs.get('ai_response_text', text)
        tts_started_at = kwargs.get('tts_started_at', datetime.now())
        
        await AudioData.create(
            user_question=user_question,
            ai_response_text=ai_response_text,
            audio_file_path=f"static/{file_name}",
            tts_started_at=tts_started_at,
            tts_completed_at=datetime.now()
        )
        # logger.info(f"音频数据已保存到数据库: {file_name}")
    except Exception as e:
        logger.warning(f"保存音频数据到数据库失败: {e}")

    return str(url)

async def text_to_audio_(*, request, text, **kwargs):
    # 生成缓存key
    reference_id = kwargs.get('reference_id') or request.state.reference_id
    tts_speed = request.state.tts_speed or settings.local_tts_speed
    cache_key = f"tts_cache:{hashlib.md5(f'{text}_{reference_id}_{tts_speed}'.encode()).hexdigest()}"
    
    # 检查缓存
    try:
        cached_result = await redis_client.get(cache_key)
        if cached_result:
            logger.debug(f"TTS缓存命中: {cache_key}")
            return {"url": cached_result}
    except Exception as e:
        logger.warning(f"读取TTS缓存失败: {e}")
    
    # 缓存未命中，执行TTS生成
    url = await text_to_audio_ffmpeg_speed(request=request, text=text, **kwargs)
    if not url:
        data = {"url": ""}
    else:
        data = {"url": str(url)}
        # 存储到缓存
        try:
            await redis_client.setex(cache_key, settings.cache_expiry, str(url))
            logger.debug(f"TTS结果已缓存: {cache_key}")
        except Exception as e:
            logger.warning(f"存储TTS缓存失败: {e}")
    
    return data

async def text_to_audio_aliyun(*, request, text, voice="longxiaochun", **kwargs):
    from utils.tools import get_file_name

    """
    阿里云语音合成
    """
    import dashscope
    from dashscope.audio.tts_v2 import SpeechSynthesizer
    import tempfile
    
    reference_id = kwargs.get('reference_id') or request.state.reference_id
    if reference_id.lower() == "man":
        voice = "longxiang"
    else:
        voice = "longxiaochun"

    # 若没有将API Key配置到环境变量中，需将下面这行代码注释放开，并将apiKey替换为自己的API Key
    dashscope.api_key = settings.dashscope_api_key
    model = "cosyvoice-v1"
    synthesizer = SpeechSynthesizer(model=model, voice=voice)
    audio = synthesizer.call(text)
    print('requestId: ', synthesizer.get_last_request_id())

    # 首先将获取的音频数据保存为临时文件
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
        temp_file.write(audio)
        temp_file_path = temp_file.name
    
    # 然后使用pydub从文件加载音频（让pydub自动检测格式）
    audio_segment = AudioSegment.from_file(temp_file_path)
    # 转换为16kHz单声道
    audio_segment = audio_segment.set_frame_rate(16000).set_channels(1)
    
    buffer = BytesIO()
    audio_segment.export(
        buffer,
        format="wav",
        codec="pcm_s16le",
        parameters=["-ar", "16000", "-ac", "1"]
    )
    buffer.seek(0)
    
    file_name = f"{get_file_name()}.wav"
    async with aiofiles.open(AUDIO_DIR / file_name, 'wb') as f:
        await f.write(buffer.read())
        url = request.url_for("audio_files", path=file_name)
        # 删除临时文件
        import os
        os.unlink(temp_file_path)
        return str(url)

async def text_to_audio_qwen(*, request, text, **kwargs):
    """
    通过dashscope调用qwen-tts
    """
    import os
    import requests
    import dashscope
    from utils.tools import get_file_name

    reference_id = kwargs.get('reference_id') or request.state.reference_id
    if reference_id.lower() == "woman":
        voice = "Cherry"
    else:
        voice = "Ethan"

    response = dashscope.audio.qwen_tts.SpeechSynthesizer.call(
        model="qwen-tts",
        api_key=settings.dashscope_api_key,
        text=text,
        voice=voice
    )

    return response.output.audio["url"]

    # logger.info(type(response))
    # logger.info(response)
    # logger.info("\n")

    # audio_url = response.output.audio["url"]
    # file_name = f"{get_file_name()}.wav"
    # save_path = AUDIO_DIR / file_name

    # try:
    #     response = requests.get(audio_url)
    #     response.raise_for_status()  # 检查请求是否成功
    #     with open(save_path, 'wb') as f:
    #         f.write(response.content)
    #         url = request.url_for("audio_files", path=file_name)
    #         return str(url)
    #     print(f"音频文件已保存至：{save_path}")
    # except Exception as e:
    #     print(f"下载失败：{str(e)}")

async def text_to_audio_ffmpeg_speed(*, request, text, **kwargs):
    from utils.tools import get_file_name, remove_emojis
    from datetime import datetime
    import time

    # 总计时开始
    total_start_time = time.time()
    
    text = await remove_emojis(text)
    if len(text) < 1:
        return None
    
    text = " ".join(text.split())
    text = text.replace("成人", "晨人")
    # 二次判空：去除空白后为空则直接跳过，避免空音频进入后续流程
    if not text:
        logger.warning("TTS文本清理后为空，已跳过本次生成")
        return None
    logger.debug(f"to tts -> {text}")
    
    # 记录TTS开始时间
    tts_start_time = datetime.now()
    kwargs['tts_started_at'] = tts_start_time

    reference_id = kwargs.get('reference_id') or request.state.reference_id
    prosody_speed = request.state.tts_speed or settings.local_tts_speed  # 默认语速倍速

    data = {
        "text": text,
        "reference_id": reference_id or settings.reference_id,
        "seed": 42,
        "normalize": True,
        "chunk_length": 100,
        "temperature": 0.6,
        "top_p": 0.8
    }

    logger.debug(f"{__name__} data: {data}")
    
    # TTS API调用计时
    api_start_time = time.time()
    logger.info(f"🎙️ 开始调用TTS API，文本长度: {len(text)}，语速: {prosody_speed}x")

    # 请求 TTS 接口 - 使用专用会话优化
    session = await get_tts_session()
    async with session.post(url=urls['text-to-audio'], json=data) as resp:
        audio_bytes = await resp.read()
    # 校验TTS API返回音频有效性，避免空输入导致FFmpeg无输出文件
    if not audio_bytes or len(audio_bytes) == 0:
        logger.warning("TTS API 返回空音频数据，已跳过本次生成")
        return None
    
    api_elapsed = time.time() - api_start_time
    logger.info(f"🎙️ TTS API调用完成，耗时: {api_elapsed:.2f}秒")

    loop = asyncio.get_event_loop()

    # 为了确保数字人嘴型同步，所有文本都必须经过相同的FFmpeg处理流程
    # 保持一致的语速和音频特性

    input_path = None
    output_path = None
    try:
        # FFmpeg处理计时
        ffmpeg_start_time = time.time()
        logger.info(f"🔧 开始FFmpeg音频处理...")
        
        # 写入原始音频到临时文件
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_input:
            temp_input.write(audio_bytes)
            input_path = Path(temp_input.name)

        output_path = input_path.with_name(input_path.stem + "_fast.wav")

        # FFmpeg 命令：变速、转采样、单声道，优化参数
        cmd = [
            "ffmpeg", "-y",
            "-loglevel", "quiet",
            "-i", str(input_path),
            "-filter:a", f"atempo={prosody_speed}",
            "-ar", "16000",
            "-ac", "1",
            "-f", "wav",  # 明确指定格式
            "-acodec", "pcm_s16le",  # 明确指定编解码器
            str(output_path)
        ]

        # 在线程池中执行 FFmpeg（避免阻塞事件循环），并检查返回码与输出文件
        def _run_ffmpeg():
            return subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True
            )
        result = await loop.run_in_executor(TTS_THREAD_POOL, _run_ffmpeg)
        ffmpeg_elapsed = time.time() - ffmpeg_start_time
        if result.returncode != 0 or not output_path.exists():
            err = (result.stderr or "").strip()
            raise RuntimeError(f"FFmpeg 处理失败，code={result.returncode}，输出不存在：{output_path}. {err}")
        logger.info(f"🔧 FFmpeg处理完成，耗时: {ffmpeg_elapsed:.2f}秒")

        # 文件I/O计时
        io_start_time = time.time()
        
        # 读取变速处理后的音频
        buffer = BytesIO(output_path.read_bytes())

        # 保存最终音频到本地
        file_name = f"{get_file_name()}.wav"
        async with aiofiles.open(AUDIO_DIR / file_name, "wb") as f:
            await f.write(buffer.read())

        # 清理临时文件
        if input_path:
            input_path.unlink(missing_ok=True)
        if output_path:
            output_path.unlink(missing_ok=True)
        
        io_elapsed = time.time() - io_start_time
        logger.info(f"💾 文件I/O完成，耗时: {io_elapsed:.2f}秒")

        url = request.url_for("audio_files", path=file_name)
        
        # 数据库保存（异步，不阻塞返回）
        asyncio.create_task(save_audio_to_db(kwargs, text, file_name, tts_start_time))
        
        total_elapsed = time.time() - total_start_time
        logger.info(f"🎵 TTS总耗时: {total_elapsed:.2f}秒 (API: {api_elapsed:.2f}s, FFmpeg: {ffmpeg_elapsed:.2f}s, I/O: {io_elapsed:.2f}s)")
        
        return str(url)

    except Exception as e:
        logger.error(f"音频处理失败（FFmpeg）：[{text}]")
        logger.error(f"错误信息: {e}")
        return None
    finally:
        # 兜底清理（防止异常提前返回导致临时文件残留）
        try:
            if input_path and input_path.exists():
                input_path.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            if output_path and output_path.exists():
                output_path.unlink(missing_ok=True)
        except Exception:
            pass

async def text_to_audio_edge(*, request, text: str, **kwargs):
    from utils.tools import get_file_name
    from datetime import datetime
    import os
    
    # 记录TTS开始时间
    tts_start_time = datetime.now()
    kwargs['tts_started_at'] = tts_start_time

    """微软edge_tts"""
    # 清理文本，移除可能导致问题的字符
    clean_text = text.strip()
    if not clean_text:
        logger.warning("TTS文本为空，跳过")
        return None
        
    # 移除一些可能导致Edge TTS问题的字符
    import re
    clean_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', clean_text)
    clean_text = clean_text.replace('\n', ' ').replace('\r', ' ')
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    if not clean_text:
        logger.warning("TTS文本清理后为空，跳过")
        return None
    
    # 配置参数处理
    reference_id = kwargs.get('reference_id') or request.state.reference_id
    voice = settings.voice_name_man if reference_id.lower() == "man" else settings.voice_name_woman
    rate = kwargs.get("rate") or settings.rate

    try:
        # 生成临时文件
        communicate = edge_tts.Communicate(text=clean_text, voice=voice, rate=rate)
        file_stem = get_file_name()
        
        # 使用上下文管理器处理文件
        async with aiofiles.tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_mp3:
            await communicate.save(tmp_mp3.name)
            
            # 音频格式转换
            audio = AudioSegment.from_file(tmp_mp3.name)
            audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
            
            # 保存最终文件
            wav_path = AUDIO_DIR / f"{file_stem}.wav"
            audio.export(wav_path, format="wav")
            
            # 清理临时文件
            try:
                os.unlink(tmp_mp3.name)
            except:
                pass
                
    except Exception as e:
        logger.error(f"Edge TTS失败: {e}, 文本: {clean_text[:50]}...")
        return None

    # 自动保存音频数据到数据库
    try:
        from api_versions.v2.models import AudioData
        from datetime import datetime
        
        user_question = kwargs.get('user_question', text[:100] + '...' if len(text) > 100 else text)
        ai_response_text = kwargs.get('ai_response_text', text)
        tts_started_at = kwargs.get('tts_started_at', datetime.now())
        
        await AudioData.create(
            user_question=user_question,
            ai_response_text=ai_response_text,
            audio_file_path=f"static/{wav_path.name}",
            tts_started_at=tts_started_at,
            tts_completed_at=datetime.now()
        )
        # logger.info(f"音频数据已保存到数据库: {wav_path.name}")
    except Exception as e:
        logger.warning(f"保存音频数据到数据库失败: {e}")

    # 返回URL
    return str(request.url_for("audio_files", path=wav_path.name))

