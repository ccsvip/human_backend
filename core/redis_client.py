from redis.asyncio import Redis
from settings.config import settings

redis_client = Redis.from_url(
    f"redis://{settings.redis_host}:{settings.redis_port}",
    db=settings.redis_db,
    password=settings.redis_password,
    decode_responses=True,
    socket_timeout=5,
    socket_connect_timeout=5,
    health_check_interval=30
)

# 可选：添加连接测试和容错逻辑（需在异步上下文中调用）
async def check_redis_connection():
    try:
        await redis_client.ping()
        print("✅ Redis 连接成功")
        # await listen_for_expired_events()
        # return True
    except Exception as e:
        print(f"❌ Redis 连接失败: {e}")
        return False
    
# TODO 待定
async def listen_for_expired_events():
    pubsub = redis_client.pubsub()
    await pubsub.psubscribe('__keyevent@0__:expired')

    async for message in pubsub.listen():
        print(f"message: {message}")
        return 'ok'