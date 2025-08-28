import aiohttp
import random
import time
import asyncio
from core.logger import logger
from core.services.v1.tts_server import text2speech
from core.dependencies import get_headers, urls
from settings.config import settings, TEXT_LIST
from core.redis_client import redis_client
from core.services.v1.llm_server_other import get_next_suggested


async def chat_messages_block(*, request, text, **kwargs):
    start_time = time.time()
    headers = get_headers(request=request).copy()
    user_id = kwargs.get('user_id') or request.state.user_id
    api_key = request.state.api_key or settings.api_key
    redis_key = f"conn:{api_key}:{user_id}"
    next_suggested_key = f"suggested:{api_key}:{user_id}"
    # 获取上一次会话ID 不存在时候返回空字符串
    old_conv_id = await redis_client.get(redis_key) or ""
    data = {
        "query": text,
        "inputs": {},
        "response_mode": "blocking",
        "conversation_id": old_conv_id,
        "user": user_id
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(urls['chat-messages'], headers=headers, json=data) as response:
                json_data = await response.json()
                logger.info(f"⏳ 大模型耗时: {time.time() - start_time:.2f}")
                logger.debug(f"{__name__} json_data:{json_data}")
                answer = json_data.get("answer") or random.choice(TEXT_LIST)
                conversation_id = json_data.get("conversation_id")
                logger.debug(f"{__name__} conversation_id: {conversation_id}")
                mode = request.state.mode or settings.mode
                audio_result =await asyncio.create_task(
                    text2speech(request=request, text=answer, model=mode, kwargs=kwargs)
                )
                if message_id := json_data.get("message_id"):
                    logger.debug(f"用户: {user_id} 更新message_id: {message_id}")
                    asyncio.create_task(redis_client.setex(
                        name=next_suggested_key,
                        time=settings.cache_expiry,
                        value=message_id
                    ))
                # next_suggested: {'result': 'success', 'data': ['AI安全吗？', '会取代人类吗？', '隐私有保障？']}
                next_suggested = await get_next_suggested(
                    request=request,
                    user_id=user_id,
                    suggested_redis_key=next_suggested_key
                )
                logger.debug(f"{__name__} next_suggested: {next_suggested}")
                result_data = {
                    "text": answer,
                    "url": audio_result.get("url"),
                    "suggested": next_suggested['data']
                }
                asyncio.create_task(redis_client.setex(
                    name=redis_key,
                    time=settings.cache_expiry,
                    value=conversation_id
                ))
                return result_data
        except Exception as e:
            logger.error(f" ❌ LLM发生了错误: {e}")
            return {
                "text": random.choice(TEXT_LIST),
                "url": '',
                "suggested": []
            }