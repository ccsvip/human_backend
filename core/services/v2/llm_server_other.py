import aiohttp
import orjson
from core.dependencies import urls, get_headers
from settings.config import settings
from core.logger import logger
from core.redis_client import redis_client


async def parameters_(*, request, **kwargs):
    """
        开场白和开场白下面建议问题
    """
    headers = get_headers(request=request).copy()
    async with aiohttp.ClientSession() as session:
        async with session.get(urls['parameters'], headers=headers) as response:
            
            try:
                json_data = await response.json()

                # 开场白
                opening_statement = json_data.get("opening_statement", "")
                # 开场白下面建议问题
                suggested_questions = json_data.get("suggested_questions", [])

                data = {"event": "parameters", "opening_statement": opening_statement, "suggested_questions": suggested_questions}
                bytes_data = orjson.dumps(data)
                sse_message = f"data: {bytes_data.decode()}\n\n".encode()
                yield sse_message
            
            except Exception as e:
                err_data = {"event": "error", "detail": str(e)}
                bytes_data = orjson.dumps(err_data)
                sse_message = f"data: {bytes_data.decode()}\n\n".encode()
                yield sse_message
            

async def get_next_suggested(*, request, user_id='', suggested_redis_key=''):
    headers = get_headers(request).copy()
    messages_id = await redis_client.getex(suggested_redis_key)
    logger.debug(f"messages_id: {messages_id}")
    url = urls['messages_suggested'].format(settings.base_url, messages_id)

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
    

# 纠错大模型
async def mixin_llm_server(*, request, text):
    headers = {
        "Authorization": f"Bearer {settings.correct_api_key}"
    }
    data = {
            "inputs": {},
            "query": text,
            "conversation_id": "",
            "user": "fix-agent",
        }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url=urls['chat-messages'], headers=headers, json=data) as resp:
                json_data = await resp.json()
                clean_text = json_data.get("answer", "")
                clean_text = clean_text.strip("？?。.>")
                return clean_text
    except Exception as e:
        logger.error(f"{__name__} 纠错大模型异常: {e}")
        return text