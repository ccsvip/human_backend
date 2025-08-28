from functools import wraps
from core.logger import logger
import time


def async_timer(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.perf_counter()
        # 关键部分
        result = await func(*args, **kwargs)
        cost_time = time.perf_counter() - start
        logger.info(f"⏳ {func.__name__} 执行时间: {cost_time:.4f} 秒")
        return result
    return wrapper