import asyncio
from tortoise import Tortoise
from core.redis_client import check_redis_connection
from core.logger import logger
from settings.config import settings
from settings.tortoise_config import TORTOISE_ORM
from utils.spider.init_opening_statement import get_opening_statement
from utils.db_migration_helper import migration_helper

async def init_start_lifespan():
    await check_redis_connection()
    await db_connect()

    # 在数据库连接成功后执行迁移检查
    if settings.enable_database:
        logger.info("🔄 开始检查数据库迁移状态...")
        migration_success = await migration_helper.check_and_migrate()
        if not migration_success:
            logger.error("❌ 数据库迁移失败，请检查数据库连接和迁移文件")
        else:
            logger.info("✅ 数据库迁移检查完成")
            # 同步静态资源到数据库
            from utils.media_sync import sync_media_files, check_and_fix_duplicate_hashes
            await sync_media_files()
            # 检查并修复重复的file_hash
            await check_and_fix_duplicate_hashes()

    await check_greeting_status()

    # 初始化RBAC权限数据
    if settings.enable_database:
        logger.info("🔄 开始初始化RBAC权限数据...")
        from utils.init_rbac_data import init_rbac_data
        rbac_success = await init_rbac_data()
        if rbac_success:
            logger.info("✅ RBAC权限数据初始化完成")
        else:
            logger.warning("⚠️ RBAC权限数据初始化失败")

    if settings.opening_statement:
        print("✅ 正在启用开场白缓存...")
        await get_opening_statement()
    else:
        print("❌ 开场白缓存未开启")





async def db_connect():
    if settings.enable_database:
        max_retries = 3
        for attempt in range(1, max_retries+1):
            try:
                # print(f"ℹ️ 数据库连接尝试（第{attempt}次）")
                try:
                    # 安全解析多层配置
                    connections = TORTOISE_ORM.get('connections', {})
                    default_conn = connections.get('default', {})
                    
                    # 处理不同配置格式
                    if isinstance(default_conn, str):
                        db_url = default_conn
                    elif isinstance(default_conn, dict):
                        credentials = default_conn.get('credentials', {})
                        db_url = credentials.get('uri') if isinstance(credentials, dict) else str(credentials)
                    else:
                        db_url = str(default_conn)
                    
                    # 获取模块配置
                    apps = TORTOISE_ORM.get('apps', {})
                    models_app = apps.get('models', {})
                    models_list = models_app.get('models', []) if isinstance(models_app, dict) else []
                    
                    # print("ℹ️ 数据库配置验证:")
                    # print(f" - 连接地址: {db_url or '未配置'}")
                    # print(f" - 数据模型: {', '.join(models_list) or '无'}")
                except Exception as config_error:
                    print(f"⚠️ 配置解析错误: {str(config_error)[:100]}")
                await Tortoise.init(config=TORTOISE_ORM)
                # 严格验证连接有效性
                conn = Tortoise.get_connection("default")
                await conn.execute_query("SELECT 1")
                await conn.execute_query("SELECT version()")
                # print("✅ 数据库连接成功（配置验证和双重查询测试通过）")
                break
            except Exception as e:
                if attempt == max_retries:
                    print(f"❌ 数据库连接最终失败: {str(e)[:200]}")
                    print("⚠️ 数据库功能将禁用，程序继续以无数据库模式运行")
                    settings.enable_database = False  # 自动禁用错误配置
                    break
                # print(f"⚠️ 连接尝试失败（{attempt}/{max_retries}）: {str(e)[:100]}")
                await asyncio.sleep(2 ** attempt)  # 指数退避
    print("✅ 数据库连接成功（配置验证和双重查询测试通过）" if settings.enable_database else "❌ 数据库未连接（配置解析错误或未开启数据库功能）")


async def check_greeting_status():
    status = '✅ 随机回复已打开' if settings.greeting_enable else '❌ 随机回复已关闭'
    print(status)