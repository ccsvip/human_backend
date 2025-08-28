import hashlib
import orjson
from settings.config import settings
from fastapi import Request
from core.redis_client import redis_client
from core.logger import logger
from typing import Union, Any


# 存储开场白建议问题的集合
suggested_questions = set()

def update_suggested_questions(questions: list):
    """更新建议问题集合，存储时去除标点符号"""
    global suggested_questions
    # 存储时就去除标点符号，这样比较时就不用重复处理了
    suggested_questions = {q.strip("？?。.>") for q in questions}

def normalize_question(text: str) -> str:
    """标准化问题文本，去除标点符号"""
    return text.strip("？?。.>")

async def generate_cache_key(*, request:Request, text:str):
    """ 生成缓存key 
    如果是开场白建议问题之一：只使用密钥和音色
    其他问题：使用设备ID、密钥和音色
    """
    secret_key = request.state.api_key or settings.api_key
    reference_id = request.state.reference_id or settings.reference_id
    
    # 标准化问题文本后再检查是否是建议问题之一
    normalized_text = normalize_question(text)
    if normalized_text in suggested_questions:
        # 建议问题：只用密钥和音色
        hashed_key = hashlib.sha256(f"{secret_key}_{reference_id}_{normalized_text}".encode("utf-8")).hexdigest()
        logger.debug(f"命中建议问题缓存 - 原文本: {text}, 标准化后: {normalized_text}")
        return f"sse_cache:suggested:{secret_key}:{reference_id}:{hashed_key}"
    else:
        # 其他问题：需要设备ID
        user_id = request.state.user_id
        hashed_key = hashlib.sha256(f"{secret_key}_{user_id}_{reference_id}_{normalized_text}".encode("utf-8")).hexdigest()
        return f"sse_cache:{secret_key}:{user_id}:{reference_id}:{hashed_key}"

# async def get_cached_sse_data(*, request:Request, cache_key:str):
#     """ 获取缓存数据 """
#     if await redis_client.exists(cache_key):
#         cached_data_str = await redis_client.lrange(cache_key, 0, -1)
#         result = []
#         for item in cached_data_str:
#             try:
#                 # 尝试解析JSON
#                 result.append(orjson.loads(item))
#             except Exception:
#                 # 如果解析失败，说明可能是bytes类型，直接添加
#                 result.append(item)
#         return result
#     return None

async def get_cached_sse_data(*, request: Request, cache_key: str):
    """优化后的缓存读取"""
    if not await redis_client.exists(cache_key):
        return None

    try:
        # 单次获取全部数据
        raw_data = await redis_client.lrange(cache_key, 0, -1)
        
        # 过滤结束标记
        filtered_data = [item for item in raw_data if item != b"__END_OF_STREAM__"]
        
        result = []
        for item in filtered_data:
            try:
                result.append(orjson.loads(item))
            except orjson.JSONDecodeError:
                result.append(item)
            except Exception as e:
                logger.warning(f"数据解析异常: {e}")
                result.append(item)
        
        return result
    except Exception as e:
        logger.error(f"缓存读取失败: {e}")
        return None


async def store_see_data_to_cache(*, request:Request, cache_key:str, sse_data: Union[dict, bytes, str, Any]):
    """ 存储SSE数据到缓存 """
    try:
        if not await redis_client.exists(cache_key):
            # 首次存储
            if isinstance(sse_data, bytes):
                # 如果是bytes类型，直接存储
                await redis_client.lpush(cache_key, sse_data)
            else:
                # 其他类型尝试序列化
                await redis_client.lpush(cache_key, orjson.dumps(sse_data))
        else:
            # 追加数据
            if isinstance(sse_data, bytes):
                # 如果是bytes类型，直接存储
                await redis_client.rpush(cache_key, sse_data)
            else:
                # 其他类型尝试序列化
                await redis_client.rpush(cache_key, orjson.dumps(sse_data))
        await redis_client.expire(cache_key, settings.cache_expiry)
    except Exception as e:
        logger.error(f"存储SSE数据到缓存失败: {e} {type(sse_data)}")
        return None


async def store_sse_bulk_data(cache_key: str, data_list: list, append: bool = False):
    """批量存储SSE数据"""
    if not data_list:
        return
    
    try:
        async with redis_client.pipeline(transaction=True) as pipe:
            for data in data_list:
                if isinstance(data, bytes):
                    pipe.rpush(cache_key, data)
                else:
                    pipe.rpush(cache_key, orjson.dumps(data))
            pipe.expire(cache_key, settings.cache_expiry)
            await pipe.execute()
    except Exception as e:
        logger.error(f"批量存储失败: {e}")