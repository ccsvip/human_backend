import os
from pathlib import Path
from typing import Set
import hashlib
from tortoise import Tortoise
from core.logger import logger
from api_versions.v2.models import MediaFile

# 定义静态目录和允许的扩展名
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
IMG_DIR = STATIC_DIR / "img"
VIDEO_DIR = STATIC_DIR / "video"
ALLOWED_IMAGE_EXTS: Set[str] = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_VIDEO_EXTS: Set[str] = {".mp4", ".mov", ".webm", ".avi"}

async def sync_media_files() -> None:
    """扫描 static/img 和 static/video，将文件信息同步到数据库 media_file 表。"""
    if not Tortoise._inited:  # 确保数据库已初始化
        logger.warning("数据库未初始化，跳过媒体同步")
        return

    # 先补全历史记录缺失的 file_hash，方便后续去重
    await _backfill_missing_hashes()

    await _sync_directory(IMG_DIR, "image", ALLOWED_IMAGE_EXTS)
    await _sync_directory(VIDEO_DIR, "video", ALLOWED_VIDEO_EXTS)

async def _sync_directory(directory: Path, media_type: str, allowed_exts: Set[str]):
    if not directory.exists():
        logger.info(f"目录不存在，跳过: {directory}")
        return

    files = list(directory.iterdir())
    if not files:
        logger.info(f"目录为空，跳过: {directory}")
        return

    for file in files:
        if file.is_file() and file.suffix.lower() in allowed_exts:
            rel_path = f"{directory.name}/{file.name}"

            # 计算文件hash
            try:
                with open(file, "rb") as f:
                    file_bytes = f.read()
                file_hash = hashlib.sha256(file_bytes).hexdigest()
            except Exception as e:
                logger.error(f"读取文件失败 {file}: {e}")
                continue

            # 查重：如果已存在相同 hash，跳过
            # 先检查是否有完全匹配的记录（hash和路径都匹配）
            exact_match = await MediaFile.filter(file_hash=file_hash, file_path=rel_path, is_delete=False).first()
            if exact_match:
                # 完全匹配，直接跳过
                logger.debug(f"媒体文件完全匹配，跳过: {rel_path}")
                continue
            
            # 查找相同hash但路径不同的记录
            existing = await MediaFile.filter(file_hash=file_hash, is_delete=False).first()
            if existing:
                # 发现相同hash但路径不同的记录，这表示有重复数据
                logger.debug(f"发现重复文件hash: 数据库路径='{existing.file_path}', 文件系统路径='{rel_path}'")
                
                # 检查文件系统中哪个路径的文件真实存在
                existing_file_path = STATIC_DIR / existing.file_path
                current_file_path = STATIC_DIR / rel_path
                
                if current_file_path.exists() and not existing_file_path.exists():
                    # 当前文件存在，数据库中的旧路径文件不存在，更新为当前路径
                    try:
                        await existing.update_from_dict({"file_path": rel_path}).save()
                        logger.info(f"更新媒体路径（文件已移动）: {existing.file_path} -> {rel_path}")
                    except Exception as e:
                        logger.warning(f"更新媒体路径失败 {rel_path}: {e}")
                elif existing_file_path.exists() and current_file_path.exists():
                    # 两个文件都存在，说明是重复文件，保留数据库中的记录，跳过当前文件
                    logger.debug(f"跳过重复文件: {rel_path} (已存在: {existing.file_path})")
                else:
                    # 其他情况，保持原有逻辑
                    logger.debug(f"保持原有记录: {existing.file_path}")

                # 若之前被标记删除，恢复展示
                if existing.is_delete:
                    try:
                        await existing.update_from_dict({"is_delete": False}).save()
                        logger.info(f"恢复已删除的媒体文件: {existing.file_path}")
                    except Exception:
                        pass

                # 清理可能的重复记录
                await _cleanup_duplicates(existing.file_path, file_hash, existing.id)
                
                # 跳过创建新记录
                continue

            # 若 hash 未找到，但根据 path 找到旧记录且缺少 hash，则更新
            existing_by_path = await MediaFile.get_or_none(file_path=rel_path)
            if existing_by_path and not existing_by_path.file_hash:
                try:
                    await existing_by_path.update_from_dict({"file_hash": file_hash}).save()
                    logger.info(f"更新媒体hash: {rel_path}")
                    await _cleanup_duplicates(rel_path, file_hash, existing_by_path.id)
                except Exception as e:
                    logger.warning(f"更新媒体hash失败 {rel_path}: {e}")
                continue

            # 不存在任何记录时创建
            try:
                # 再次检查是否存在相同hash的记录（防止并发创建）
                existing_hash_check = await MediaFile.get_or_none(file_hash=file_hash)
                if existing_hash_check:
                    logger.debug(f"发现并发创建的重复hash记录，跳过: {rel_path}")
                    await _cleanup_duplicates(rel_path, file_hash, existing_hash_check.id)
                    continue

                new_rec = await MediaFile.create(
                    name=file.stem,
                    file_path=rel_path,
                    file_hash=file_hash,
                    description=None,
                    media_type=media_type,
                    is_show=True,
                    is_delete=False,
                )
                logger.info(f"已同步媒体文件: {rel_path}")
                await _cleanup_duplicates(rel_path, file_hash, new_rec.id)
            except Exception as e:
                # 如果是重复键错误，尝试查找现有记录并清理
                if "Duplicate entry" in str(e) and "file_hash" in str(e):
                    logger.warning(f"检测到file_hash重复，尝试清理: {rel_path}")
                    try:
                        existing_rec = await MediaFile.get_or_none(file_hash=file_hash)
                        if existing_rec:
                            await _cleanup_duplicates(rel_path, file_hash, existing_rec.id)
                            logger.info(f"已清理重复记录: {rel_path}")
                        else:
                            logger.error(f"未找到重复的hash记录: {file_hash}")
                    except Exception as cleanup_e:
                        logger.error(f"清理重复记录失败 {rel_path}: {cleanup_e}")
                else:
                    logger.error(f"同步媒体文件失败 {rel_path}: {e}")

# --------------------------------- 工具函数 ---------------------------------

async def _cleanup_duplicates(rel_path: str, file_hash: str, keep_id: int):
    """将同路径或同hash的其他记录标记删除，避免前端重复"""
    try:
        await MediaFile.filter(file_path=rel_path).exclude(id=keep_id).update(is_delete=True)
        if file_hash:
            await MediaFile.filter(file_hash=file_hash).exclude(id=keep_id).update(is_delete=True)
    except Exception as e:
        logger.warning(f"清理重复媒体记录失败 {rel_path}: {e}")

async def _backfill_missing_hashes():
    """为旧记录补写 file_hash，并立即清理重复记录"""
    missing_hash_records = await MediaFile.filter(file_hash__isnull=True, is_delete=False).all()
    if not missing_hash_records:
        return

    logger.info(f"发现 {len(missing_hash_records)} 条缺失 hash 的媒体记录，开始补写…")

    for rec in missing_hash_records:
        # 计算文件hash
        file_path_full = STATIC_DIR / rec.file_path
        if not file_path_full.exists():
            logger.warning(f"文件不存在，跳过补写 hash: {rec.file_path}")
            continue
        try:
            with open(file_path_full, "rb") as f:
                file_bytes = f.read()
            file_hash = hashlib.sha256(file_bytes).hexdigest()
        except Exception as e:
            logger.warning(f"读取文件失败，跳过 {rec.file_path}: {e}")
            continue

        # 如果已存在同 hash 的记录，保留较新的（created_at 较大）
        existing_with_hash = await MediaFile.get_or_none(file_hash=file_hash)
        if existing_with_hash:
            # 保留较早创建的那条？按需求保留 existing_with_hash，删除当前
            keep_id = existing_with_hash.id
            await rec.update_from_dict({"is_delete": True}).save()
            await _cleanup_duplicates(rec.file_path, file_hash, keep_id)
            continue

        # 更新自身 hash
        try:
            await rec.update_from_dict({"file_hash": file_hash}).save()
            await _cleanup_duplicates(rec.file_path, file_hash, rec.id)
        except Exception as e:
            if "Duplicate entry" in str(e) and "file_hash" in str(e):
                logger.warning(f"补写hash时发现重复，标记删除当前记录: {rec.file_path}")
                # 如果更新时发现hash重复，查找现有记录并删除当前记录
                existing_with_hash = await MediaFile.get_or_none(file_hash=file_hash)
                if existing_with_hash:
                    await rec.update_from_dict({"is_delete": True}).save()
                    await _cleanup_duplicates(rec.file_path, file_hash, existing_with_hash.id)
                else:
                    logger.error(f"补写hash失败且找不到重复记录: {rec.file_path}")
            else:
                logger.error(f"补写hash失败 {rec.file_path}: {e}")

    logger.info("补写 file_hash 完成")


async def check_and_fix_duplicate_hashes():
    """检查并修复重复的file_hash（启动时调用）"""
    try:
        # 查找重复的hash
        conn = Tortoise.get_connection("default")
        query = """
        SELECT file_hash, COUNT(*) as count
        FROM media_file
        WHERE file_hash IS NOT NULL AND is_delete = 0
        GROUP BY file_hash
        HAVING COUNT(*) > 1
        LIMIT 5
        """

        result = await conn.execute_query(query)
        duplicate_hashes = result[1]

        if not duplicate_hashes:
            return

        logger.warning(f"发现 {len(duplicate_hashes)} 个重复的file_hash，开始自动修复...")

        for hash_info in duplicate_hashes:
            file_hash, count = hash_info
            logger.info(f"修复重复hash: {file_hash} (重复 {count} 次)")

            # 获取重复记录
            records = await MediaFile.filter(file_hash=file_hash, is_delete=False).order_by("created_at")
            if len(records) > 1:
                # 保留第一个，删除其他
                keep_record = records[0]
                for dup_record in records[1:]:
                    await dup_record.update_from_dict({"is_delete": True}).save()
                    logger.info(f"标记删除重复记录: ID={dup_record.id}")

        logger.info("重复hash自动修复完成")

    except Exception as e:
        logger.error(f"检查重复hash失败: {e}")