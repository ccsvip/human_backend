import hashlib
import orjson
import asyncio
from core.redis_client import redis_client
from core.logger import logger
from fastapi import Request
from settings.config import settings
from core.services.v1 import llm_server_block

semaphore = asyncio.Semaphore(settings.semaphore)

async def get_answer(*, request:Request, text_list, **kwargs):
    logger.debug(f"{__name__} is running..")
    reference_id = kwargs.get('reference_id') or request.state.reference_id
    user_id = kwargs.get("user_id") or request.state.user_id

    async def _process_request(question):
        async with semaphore:
            return await process_question(question)

    async def process_question(question):
        question = question.strip("？?。.>")
        text_sha256 = hashlib.sha256(f"{question}_{reference_id}".encode("utf-8")).hexdigest()
        llm_redis_key = f"llm:{user_id}:{reference_id}:{text_sha256}"
        is_cached = await redis_client.get(llm_redis_key)
        if not is_cached:
            logger.info(f"⏳ 正在对问题: {question} 执行后台任务..")
            logger.debug(f"{__name__} text: {question}")
            result = await llm_server_block.chat_messages_block(request=request, text=question)
            json_data = result.copy()
            json_data.update({"question": question})
            logger.debug(f"{__name__} json_data: {json_data}")
            asyncio.create_task(redis_client.setex(
                name=llm_redis_key,
                time=settings.cache_expiry,
                value=orjson.dumps(json_data).decode("utf-8")
                ))
    logger.debug(f"任务列表: {text_list}")
    for q in text_list:
        asyncio.create_task(_process_request(q))

    return "后台任务已添加"