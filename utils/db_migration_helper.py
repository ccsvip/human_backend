import asyncio
import os
from pathlib import Path
from tortoise import Tortoise
from tortoise.backends.base.client import BaseDBAsyncClient
from core.logger import logger
from settings.config import settings
from settings.tortoise_config import TORTOISE_ORM
import importlib.util
import json


class DatabaseMigrationHelper:
    """数据库迁移助手类"""
    
    def __init__(self):
        self.migrations_dir = Path(__file__).parent.parent / "migrations" / "models"
        self.aerich_table = "aerich"
    
    async def check_and_migrate(self):
        """检查并执行数据库迁移"""
        if not settings.enable_database:
            logger.info("数据库未启用，跳过迁移检查")
            return True
            
        try:
            # 确保数据库连接已建立
            try:
                conn = Tortoise.get_connection("default")
            except Exception:
                # 如果连接不存在，初始化连接
                await Tortoise.init(config=TORTOISE_ORM)
                conn = Tortoise.get_connection("default")
            
            # 检查是否需要初始化 aerich 表
            await self._ensure_aerich_table_exists(conn)
            
            # 获取已执行的迁移
            executed_migrations = await self._get_executed_migrations(conn)
            
            # 获取所有迁移文件
            available_migrations = self._get_available_migrations()
            
            # 执行未执行的迁移
            pending_migrations = [
                migration for migration in available_migrations 
                if migration["version"] not in executed_migrations
            ]
            
            if pending_migrations:
                logger.info(f"发现 {len(pending_migrations)} 个待执行的数据库迁移")
                for migration in pending_migrations:
                    await self._execute_migration(conn, migration)
                logger.info("所有待执行的迁移已完成")
            else:
                logger.info("数据库迁移已是最新状态")
                
            return True
            
        except Exception as e:
            logger.error(f"数据库迁移检查失败: {str(e)}")
            return False
    
    async def _ensure_aerich_table_exists(self, conn: BaseDBAsyncClient):
        """确保 aerich 表存在"""
        try:
            # 检查 aerich 表是否存在
            result = await conn.execute_query(
                "SELECT COUNT(*) as count FROM information_schema.tables "
                "WHERE table_schema = %s AND table_name = %s",
                [settings.db_name, self.aerich_table]
            )
            
            table_exists = result[1][0]['count'] > 0
            
            if not table_exists:
                logger.info("创建 aerich 迁移记录表")
                await conn.execute_script("""
                    CREATE TABLE IF NOT EXISTS `aerich` (
                        `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
                        `version` VARCHAR(255) NOT NULL,
                        `app` VARCHAR(100) NOT NULL,
                        `content` JSON NOT NULL
                    ) CHARACTER SET utf8mb4;
                """)
                
        except Exception as e:
            logger.warning(f"检查/创建 aerich 表时出现问题: {str(e)}")
    
    async def _get_executed_migrations(self, conn: BaseDBAsyncClient) -> set:
        """获取已执行的迁移版本列表"""
        try:
            result = await conn.execute_query(
                f"SELECT version FROM {self.aerich_table} WHERE app = %s",
                ["models"]
            )
            return {row['version'] for row in result[1]}
        except Exception as e:
            logger.warning(f"获取已执行迁移列表失败: {str(e)}")
            return set()
    
    def _get_available_migrations(self) -> list:
        """获取所有可用的迁移文件"""
        migrations = []
        
        if not self.migrations_dir.exists():
            logger.warning(f"迁移目录不存在: {self.migrations_dir}")
            return migrations
        
        for file_path in self.migrations_dir.glob("*.py"):
            if file_path.name.startswith("__"):
                continue
                
            # 解析迁移文件名获取版本号
            version = file_path.stem
            migrations.append({
                "version": version,
                "file_path": file_path,
                "module_name": f"migrations.models.{version}"
            })
        
        # 按版本号排序
        migrations.sort(key=lambda x: x["version"])
        return migrations
    
    async def _execute_migration(self, conn: BaseDBAsyncClient, migration: dict):
        """执行单个迁移"""
        try:
            logger.info(f"执行迁移: {migration['version']}")
            
            # 动态导入迁移模块
            spec = importlib.util.spec_from_file_location(
                migration["module_name"], 
                migration["file_path"]
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"无法加载迁移模块: {migration['module_name']}")
            
            migration_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration_module)
            
            # 执行 upgrade 函数
            if hasattr(migration_module, 'upgrade'):
                sql = await migration_module.upgrade(conn)
                if sql and sql.strip():
                    await conn.execute_script(sql)
                    logger.info(f"迁移 {migration['version']} 执行成功")
                
                # 记录迁移执行
                await self._record_migration(conn, migration)
            else:
                logger.warning(f"迁移文件 {migration['version']} 没有 upgrade 函数")
                
        except Exception as e:
            logger.error(f"执行迁移 {migration['version']} 失败: {str(e)}")
            raise
    
    async def _record_migration(self, conn: BaseDBAsyncClient, migration: dict):
        """记录迁移执行"""
        try:
            content = {
                "executed_at": asyncio.get_event_loop().time(),
                "file_path": str(migration["file_path"])
            }
            
            await conn.execute_query(
                f"INSERT INTO {self.aerich_table} (version, app, content) VALUES (%s, %s, %s)",
                [migration["version"], "models", json.dumps(content)]
            )
            
        except Exception as e:
            logger.error(f"记录迁移执行失败: {str(e)}")


# 创建全局实例
migration_helper = DatabaseMigrationHelper() 