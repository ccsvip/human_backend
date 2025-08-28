import aiohttp
import asyncio
from settings.config import settings
from core.dependencies import urls
from utils.redis_tools import generate_cache_key, store_sse_bulk_data, update_suggested_questions, get_cached_sse_data
from core.services.v2 import llm_server
from core.logger import logger


class MockRequest:
    """模拟请求对象，用于生成缓存key和url_for"""
    def __init__(self, api_key, reference_id, tts_speed):
        # 创建一个完整的state对象
        class State:
            def __init__(self, api_key, reference_id):
                self.api_key = api_key
                self.reference_id = reference_id
                self.user_id = 'mock_user'  # 添加一个模拟的user_id，虽然缓存时不会用到它
                self.tts_speed = tts_speed
        
        self.state = State(api_key, reference_id)
        # 使用实际运行的URL
        host = getattr(settings, 'host', '0.0.0.0')
        self._base_url = f"http://{host}:{settings.expose_port}"
        self.base_url = self._base_url
        self.url = self._base_url
        logger.info(f"MockRequest using base_url: {self._base_url}")

    def url_for(self, name: str, **path_params) -> str:
        """完整模拟FastAPI的url_for方法"""
        if name == "audio_files":
            # 构造音频文件URL
            file_path = path_params.get('path', '')
            return f"{self._base_url}/static/{file_path}"
        elif name == "tts":
            # TTS接口URL
            return f"{self._base_url}/v2/tts"
        elif name == "llm-streaming":
            # LLM流式接口URL
            return f"{self._base_url}/v2/llm-streaming"
        elif name == "parameters":
            # 参数接口URL
            return urls['parameters']
        else:
            # 其他接口，返回基础URL
            return self._base_url

    @property
    def headers(self):
        """模拟请求头"""
        return {
            "Authorization": f"Bearer {self.state.api_key}"
        }


async def check_cache_exists(api_key: str, reference_id: str, tts_speed: float, question: str) -> bool:
    """检查问题的缓存是否存在"""
    mock_request = MockRequest(api_key, reference_id, tts_speed)
    cache_key = await generate_cache_key(request=mock_request, text=question)
    cached_data = await get_cached_sse_data(request=mock_request, cache_key=cache_key)
    return cached_data is not None


async def cache_suggested_question(api_key: str, reference_id: str, question: str, tts_speed: float=1.3):
    """缓存单个建议问题的回答"""
    # 首先检查缓存是否存在
    if await check_cache_exists(api_key, reference_id, tts_speed, question):
        logger.info(f"✓ 缓存已存在 - 音色: {reference_id}, 问题: {question}")
        return

    mock_request = MockRequest(api_key, reference_id, tts_speed)
    cache_key = await generate_cache_key(request=mock_request, text=question)
    
    buffer = []
    buffer_size = 10
    
    try:
        # 获取LLM回答
        async for data in llm_server.chat_messages_streaming(request=mock_request, text=question, skip_question=True):
            if isinstance(data, str):
                data_bytes = data.encode('utf-8')
            else:
                data_bytes = data
            buffer.append(data_bytes)
            
            if len(buffer) >= buffer_size:
                await store_sse_bulk_data(cache_key, buffer.copy())
                buffer.clear()
        
        if buffer:
            await store_sse_bulk_data(cache_key, buffer)
            buffer.clear()
            
        # 添加结束标记
        await store_sse_bulk_data(cache_key, [b"__END_OF_STREAM__"])
        logger.info(f"✅ 新建缓存成功 - 音色: {reference_id}, 问题: {question}")
    except Exception as e:
        logger.error(f"❌ 缓存问题失败 - 音色: {reference_id}, 问题: {question}, 错误: {e}")


async def get_opening_statement():
    """获取开场白和建议问题并预缓存回答"""
    url = urls['parameters']
    headers = {
        "Authorization": f"Bearer {settings.api_key}"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            try:
                json_data = await resp.json()
                opening_statement = json_data.get("opening_statement")
                suggested_questions = json_data.get("suggested_questions", [])
                logger.info(f"获取到开场白: {opening_statement}")
                logger.info(f"获取到建议问题: {suggested_questions}")

                # 更新建议问题集合
                update_suggested_questions(suggested_questions)

                # 为每个建议问题的男声和女声版本创建缓存
                tasks = []
                for question_ in suggested_questions:

                    question = question_.strip("？?。.>")

                    # 男声版本
                    tasks.append(cache_suggested_question(settings.api_key, "man", question))
                    # 女声版本
                    tasks.append(cache_suggested_question(settings.api_key, "woman", question))
                
                # 并发执行所有缓存任务
                await asyncio.gather(*tasks)
                logger.info("✨ 所有建议问题的缓存检查/更新已完成")

            except Exception as e:
                logger.error(f"获取开场白和建议问题时发生错误: {e}")


if __name__ == "__main__":
    # 运行预缓存脚本
    asyncio.run(get_opening_statement())