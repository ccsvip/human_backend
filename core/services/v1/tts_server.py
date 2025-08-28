import re
import os
import asyncio
import time
import orjson
import aiohttp
import hashlib
from core.logger import logger
from core.redis_client import redis_client
from io import BytesIO
from pydub import AudioSegment
from settings.config import AUDIO_DIR, settings
from core.dependencies import urls
from core.services.v1.tts_server_zhiyun import tts_main
from utils.tools import get_file_name, random_voice


class AioTTSProcessor:
    __slots__ = ['tts_url', 'reference_id', 'session']

    def __init__(self):
        self.tts_url = settings.tts_url
        self.reference_id = settings.reference_id
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit_per_host=10),
            timeout=aiohttp.ClientTimeout(total=300)
        )
        return self

    async def __aexit__(self, *exc):
        await self.session.close()

    async def _fetch_audio(self, request, text_chunk, voice_id, **kwargs):
        """高效音频获取方法"""
        async with self.session.post(
                urls['text-to-audio'],
                json={"text": text_chunk, "reference_id": voice_id or request.state.reference_id}
        ) as resp:
            logger.debug(f"{__name__} voice_id: {voice_id}")
            audio_data = await resp.read()
            return AudioSegment.from_wav(BytesIO(audio_data))

    async def process_text(self,request, full_text, voice_id, **kwargs):
        """全流程处理"""
        chunks = list(self._split_text(full_text))  # 转换为列表避免生成器问题
        tasks = [self._fetch_audio(request, chunk, voice_id, **kwargs) for chunk in chunks]
        return await asyncio.gather(*tasks)

    @staticmethod
    def _split_text(text, max_length=150):
        if len(text) > 20:
            sentences = re.split(r'(?<=[。！？；\n])|(?<=\.\s)', text)  # 拆分断言
            current_chunk = []
            current_len = 0

            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue

                sent_len = len(sent)
                if current_len + sent_len <= max_length:
                    current_chunk.append(sent)
                    current_len += sent_len
                else:
                    if current_chunk:
                        yield ''.join(current_chunk)
                    current_chunk = [sent]
                    current_len = sent_len
            if current_chunk:
                yield ''.join(current_chunk)
        else:
            yield text

def combine_audio(segments, output_path):
    """高性能音频合并"""
    if not segments:
        raise ValueError("No audio segments to combine")

    # 统一音频参数
    combined = segments[0].set_frame_rate(16000).set_channels(1)
    for seg in segments[1:]:
        combined += seg.set_frame_rate(16000).set_channels(1)

    # 内存优化导出
    with BytesIO() as buffer:
        combined.export(buffer, format='wav', parameters=['-ar', '16000'])
        with open(output_path, 'wb') as f:
            f.write(buffer.getvalue())

async def text2speech(*, request, text:str, model, voice_id='', **kwargs):
    # kwargs: {'kwargs': {'reference_id': 'woman', 'user_id': '133', 'dify_api_key': ''}}
    file_name = f"{get_file_name()}.wav"
    logger.debug(f"{__name__} kwargs: {kwargs}")
    if kwargs:
        reference_id = kwargs.get('kwargs').get('reference_id') or request.state.reference_id or settings.reference_id
    else:
        reference_id = request.state.reference_id or settings.reference_id
    # reference_id = kwargs.get("kwargs").get("reference_id") or request.state.reference_id or settings.reference_id
    logger.debug(f"{__name__} mode: {model}")
    if not model:
        try:
            logger.debug(f"reference_id: {reference_id}")
            tts_url_key = hashlib.sha256(f"{text}_{reference_id}".encode("utf-8")).hexdigest()
            logger.debug(f"tts_url_key: {tts_url_key}")
            set_key = f"tts_{reference_id}:{tts_url_key}"
            if await redis_client.exists(set_key):
                logger.info(f"🎯 命中TTS缓存（哈希：{tts_url_key[:10]}）")
                tts_url = await redis_client.get(set_key)
                return {"url": tts_url}
            async with AioTTSProcessor() as processor:
                # logger.info(f"🔊开始处理文本转语音任务 {text}")
                logger.debug(f"{__name__} text: {text}")
                t1 = time.perf_counter()
                segments = await processor.process_text(request, text, voice_id=reference_id, kwargs=kwargs)

                path = AUDIO_DIR / file_name
                await asyncio.get_event_loop().run_in_executor(
                    None, combine_audio, segments, path
                )
                logger.info(f"🔊音频处理总耗时: {time.perf_counter() - t1:.2f}秒")
                url = request.url_for("audio_files", path=file_name)
                file_path = os.path.join(AUDIO_DIR,  file_name)
                url_dict = {"url": str(url), "file_path": file_path}
                asyncio.create_task(redis_client.setex(
                    name=set_key,
                    time=settings.cache_expiry,
                    value=orjson.dumps(url_dict).decode("utf-8")
                ))
                logger.info(f"💾 新增TTS缓存(哈希: {tts_url_key[:10]})")
                return url_dict
        except Exception as e:
            logger.error(f"error: TTS服务出错: {e}")
            logger.debug(f"{__name__}  random_voice(voice_id=reference_id) {random_voice(voice_id=reference_id)}")
            url = request.url_for("audio_files", path=random_voice(voice_id=reference_id))
            logger.debug(f"{__name__} url: {url}")
            return {"url": str(url)}
    else:
        if model not in ['zhiyun', '']:
            return {"message": "模型不存在"}
        else:
            try:
                logger.info("🔊开始处理文本转语音任务")
                t1 = time.perf_counter()
                logger.debug(f"text: {text}")
                zhiyun_tts_key = hashlib.sha256(text.encode("utf-8")).hexdigest()
                is_cached = await redis_client.exists(f"zhiyun_tts:{zhiyun_tts_key}")
                if is_cached:
                    logger.info(f"🎯 命中智云TTS缓存（哈希：{zhiyun_tts_key[:10]}）")
                    data = await redis_client.getex(f"zhiyun_tts:{zhiyun_tts_key}")
                    return orjson.loads(data.encode("utf-8"))
                data_dict = await tts_main(q=text, voice_name=settings.voice_name, request=request, file_name=file_name)
                logger.info(f"🚄音频处理总耗时: {time.perf_counter() - t1:.2f}秒")
                # 写入缓存
                asyncio.create_task(redis_client.setex(
                    name=f"zhiyun_tts:{zhiyun_tts_key}",
                    time=settings.cache_expiry,
                    value=orjson.dumps(data_dict).decode("utf-8")
                ))
                logger.info(f"💾 新增智云_tts缓存(哈希: {zhiyun_tts_key[:10]})")
                return data_dict  # {"url": str(url)}
            except Exception as e:
                logger.error(f"❌ 智云TTS服务出错: {e}")
                url = request.url_for("audio_files", path="fail/zhiyun_fail.wav")
                logger.debug(f"{__name__} url: {url}")
                return {"url": str(url)}



if __name__ == "__main__":
    # asyncio.run(text2speech("科技馆附近有一些商场和公园，比如天天中影汇、新奥购物中心和奥林匹克森林公园。这些地方都是不错的选择呢。"))
    ...