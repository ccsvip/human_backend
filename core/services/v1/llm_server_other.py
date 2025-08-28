from fastapi import Request
import aiohttp
from typing import Dict
from core.logger import logger
from core.tasks import get_suggested_answer
from core.dependencies import get_headers, urls, base_url
from core.redis_client import redis_client


async def parameters(*, request:Request):
    headers = get_headers(request).copy()
    async with aiohttp.ClientSession() as session:
        async with session.get(urls['parameters'], headers=headers) as resp:
            json_data = await resp.json()
            logger.debug(f"{__name__} json_data: {json_data}")
            return json_data

async def handler_parameters(*, request:Request, data:Dict[str, str]):
    logger.debug(f"{__name__} {data}")
    opening_statement = data.get("opening_statement") # 开场白
    suggested_questions = data.get("suggested_questions") # 开场白下面建议的问题
    if not suggested_questions:
        logger.error("⚠️ 开场白问题尚未设置，请通知管理员设置")
    return {
        "opening_statement": opening_statement,
        "suggested_questions": suggested_questions
    }

async def get_next_suggested(*, request, user_id='', suggested_redis_key=''):
    headers = get_headers(request).copy()
    messages_id = await redis_client.getex(suggested_redis_key)
    logger.debug(f"messages_id: {messages_id}")
    url = urls['messages_suggested'].format(base_url, messages_id)
    logger.debug(f"{__name__} url: {url} user_id: {user_id} suggested_redis_key: {suggested_redis_key}") 
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params={"user": user_id}) as response:
                json_data = await response.json()
                logger.debug(f"{__name__} json_data: {json_data}")
                # {'result': 'success', 'data': ['你吃饭了吗？', '哪里不舒服？', '天气怎么样？']}
                return json_data
    except Exception as e:
        logger.error(f"⚠️ 建议问题未打开 请通知管理员打开: {e}")
        return {"data": []}
