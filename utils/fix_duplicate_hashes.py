"""
修复媒体文件表中重复的file_hash问题
用于清理现有的重复数据
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tortoise import Tortoise
from settings.tortoise_config import TORTOISE_ORM
from api_versions.v2.models import MediaFile
from core.logger import logger


async def fix_duplicate_hashes():
    """修复重复的file_hash问题"""
    try:
        logger.info("🚀 开始修复重复的file_hash...")
        
        # 初始化Tortoise ORM
        await Tortoise.init(config=TORTOISE_ORM)
        
        # 查找所有重复的file_hash
        duplicate_hashes = await find_duplicate_hashes()
        
        if not duplicate_hashes:
            logger.info("✅ 没有发现重复的file_hash")
            return
        
        logger.info(f"🔍 发现 {len(duplicate_hashes)} 个重复的file_hash")
        
        # 处理每个重复的hash
        for file_hash in duplicate_hashes:
            await fix_single_hash(file_hash)
        
        logger.info("✅ 重复file_hash修复完成")
        
    except Exception as e:
        logger.error(f"❌ 修复重复file_hash失败: {str(e)}")
        raise e
    finally:
        # 关闭数据库连接
        await Tortoise.close_connections()


async def find_duplicate_hashes():
    """查找所有重复的file_hash"""
    # 使用原生SQL查询重复的hash
    conn = Tortoise.get_connection("default")
    
    query = """
    SELECT file_hash 
    FROM media_file 
    WHERE file_hash IS NOT NULL 
    GROUP BY file_hash 
    HAVING COUNT(*) > 1
    """
    
    result = await conn.execute_query(query)
    return [row[0] for row in result[1]]


async def fix_single_hash(file_hash: str):
    """修复单个重复的file_hash"""
    logger.info(f"🔧 处理重复hash: {file_hash}")
    
    # 获取所有具有相同hash的记录
    records = await MediaFile.filter(file_hash=file_hash).order_by("created_at")
    
    if len(records) <= 1:
        return
    
    # 保留最早创建的记录
    keep_record = records[0]
    duplicate_records = records[1:]
    
    logger.info(f"保留记录: ID={keep_record.id}, 路径={keep_record.file_path}")
    
    # 检查文件是否真实存在
    static_dir = Path(__file__).parent.parent / "static"
    keep_file_path = static_dir / keep_record.file_path
    
    for dup_record in duplicate_records:
        dup_file_path = static_dir / dup_record.file_path
        
        # 如果保留的文件不存在，但重复的文件存在，则交换保留对象
        if not keep_file_path.exists() and dup_file_path.exists():
            logger.info(f"交换保留记录: 新保留ID={dup_record.id}, 路径={dup_record.file_path}")
            keep_record, dup_record = dup_record, keep_record
            keep_file_path = dup_file_path
        
        # 标记重复记录为删除
        logger.info(f"标记删除重复记录: ID={dup_record.id}, 路径={dup_record.file_path}")
        await dup_record.update_from_dict({"is_delete": True}).save()
        
        # 如果重复记录的文件存在但与保留记录路径不同，删除重复文件
        if dup_file_path.exists() and dup_file_path != keep_file_path:
            try:
                dup_file_path.unlink()
                logger.info(f"删除重复文件: {dup_file_path}")
            except Exception as e:
                logger.warning(f"删除重复文件失败 {dup_file_path}: {e}")


async def cleanup_orphaned_records():
    """清理孤儿记录（文件不存在的记录）"""
    logger.info("🧹 开始清理孤儿记录...")
    
    static_dir = Path(__file__).parent.parent / "static"
    records = await MediaFile.filter(is_delete=False).all()
    
    orphaned_count = 0
    for record in records:
        file_path = static_dir / record.file_path
        if not file_path.exists():
            logger.info(f"标记孤儿记录为删除: ID={record.id}, 路径={record.file_path}")
            await record.update_from_dict({"is_delete": True}).save()
            orphaned_count += 1
    
    logger.info(f"✅ 清理了 {orphaned_count} 个孤儿记录")


async def main():
    """主函数"""
    print("媒体文件重复hash修复工具")
    print("=" * 50)
    
    choice = input("请选择操作:\n1. 修复重复hash\n2. 清理孤儿记录\n3. 全部执行\n请输入选择 (1/2/3): ")
    
    if choice == "1":
        await fix_duplicate_hashes()
    elif choice == "2":
        await Tortoise.init(config=TORTOISE_ORM)
        try:
            await cleanup_orphaned_records()
        finally:
            await Tortoise.close_connections()
    elif choice == "3":
        await fix_duplicate_hashes()
        await Tortoise.init(config=TORTOISE_ORM)
        try:
            await cleanup_orphaned_records()
        finally:
            await Tortoise.close_connections()
    else:
        print("无效选择")


if __name__ == "__main__":
    asyncio.run(main())
