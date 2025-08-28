import asyncio
from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException
from typing import List, Set
from pathlib import Path
import uuid, os
from datetime import datetime
from ..v2.models import MediaFile
from ..v2.schema import MediaOutSchema, MediaOutWithURLSchema, MediaUpdateSchema
import hashlib
from utils.media_sync import _cleanup_duplicates
from core.logger import logger
from utils.media_tools import media_log_tools


router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = BASE_DIR / "static"
IMG_DIR = STATIC_DIR / "img"
VIDEO_DIR = STATIC_DIR / "video"
AVATAR_DIR = STATIC_DIR / "avatar"
IMG_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)
AVATAR_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXTS: Set[str] = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_VIDEO_EXTS: Set[str] = {".mp4", ".mov", ".webm"}

def _generate_filename(ext: str) -> str:
    prefix = datetime.utcnow().strftime("%Y_%m_%d")
    return f"{prefix}_{uuid.uuid4().hex[:8]}{ext}"

async def _save_file_with_hash(upload_file: UploadFile, target_dir: Path, allowed: Set[str]):
    """保存文件并返回 (relative_path, file_hash, content)"""
    ext = os.path.splitext(upload_file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"不支持的文件类型 {ext}")

    content = await upload_file.read()
    file_hash = hashlib.sha256(content).hexdigest()

    # 若已存在同样hash，直接返回现有记录路径
    existing = await MediaFile.get_or_none(file_hash=file_hash)
    if existing:
        return existing.file_path, file_hash, None  # 不再写入磁盘

    filename = _generate_filename(ext)
    target_path = target_dir / filename
    with open(target_path, 'wb') as f:
        f.write(content)
    return f"{target_dir.name}/{filename}", file_hash, content

@router.post("/upload/image", response_model=MediaOutWithURLSchema)
async def upload_image(request: Request, file: UploadFile = File(...), name: str = Form(...), description: str | None = Form(None), orientation: str | None = Form(None), is_show: bool = Form(True)):
    from api_versions.auth.routers import get_current_user
    from api_versions.v2.models import OperationLog

    # 获取当前用户（如果已登录）
    try:
        current_user = await get_current_user(request)
        username = current_user.username
        is_admin = any(role.name in ["super_admin", "admin"] for role in await current_user.roles.all())
    except:
        username = "anonymous"
        is_admin = False

    rel, file_hash, _ = await _save_file_with_hash(file, IMG_DIR, ALLOWED_IMAGE_EXTS)
    m = await MediaFile.get_or_none(file_hash=file_hash)
    if m is None:
        # 可能已有同路径但缺hash
        m = await MediaFile.get_or_none(file_path=rel)
        if m and not m.file_hash:
            try:
                await m.update_from_dict({"file_hash": file_hash}).save()
            except Exception as e:
                if "Duplicate entry" in str(e) and "file_hash" in str(e):
                    # 如果更新时发现hash重复，查找现有记录
                    existing_m = await MediaFile.get_or_none(file_hash=file_hash)
                    if existing_m:
                        m = existing_m
                    else:
                        raise e
                else:
                    raise e
        else:
            try:
                m = await MediaFile.create(name=name, file_path=rel, file_hash=file_hash, description=description, orientation=orientation, media_type="image", is_show=is_show, is_delete=False)
            except Exception as e:
                if "Duplicate entry" in str(e) and "file_hash" in str(e):
                    # 如果创建时发现hash重复，查找现有记录
                    m = await MediaFile.get_or_none(file_hash=file_hash)
                    if not m:
                        raise HTTPException(status_code=500, detail=f"文件hash冲突但找不到现有记录: {file_hash}")
                else:
                    raise HTTPException(status_code=500, detail=f"创建媒体记录失败: {str(e)}")
    await _cleanup_duplicates(rel, file_hash, m.id)

    # 如果记录曾被标记删除，恢复显示
    if m.is_delete:
        await m.update_from_dict({"is_delete": False}).save()

    # 记录操作日志
    try:
        await OperationLog.create(
            username=username,
            operation_type="CREATE",
            operation_content=f"上传图片: {name}",
            target_type="media",
            target_id=str(m.id),
            ip_address=request.client.host if request.client else "unknown",
            status="success",
            details={
                "action": "upload_image",
                "file_name": name,
                "file_path": rel,
                "file_type": "image"
            },
            is_admin=is_admin
        )
    except Exception as e:
        # 操作日志记录失败不影响主要功能
        logger.warning(f"记录操作日志失败: {e}")

    base = await MediaOutSchema.from_tortoise_orm(m)
    return MediaOutWithURLSchema(**base.model_dump(), url=str(request.url_for("audio_files", path=rel)))

@router.post("/upload/avatar")
async def upload_avatar(request: Request, file: UploadFile = File(...), name: str = Form(...), description: str | None = Form(None)):
    """专门的头像上传接口，不保存到媒体管理数据库"""
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        raise HTTPException(400, f"不支持的文件类型 {ext}")

    content = await file.read()
    filename = _generate_filename(ext)
    target_path = AVATAR_DIR / filename
    
    # 直接保存文件，不保存到MediaFile表
    with open(target_path, 'wb') as f:
        f.write(content)
    
    rel_path = f"avatar/{filename}"
    url = str(request.url_for("audio_files", path=rel_path))
    
    return {
        "message": "头像上传成功",
        "file_path": rel_path,
        "url": url,
        "name": name
    }

@router.post("/upload/video", response_model=MediaOutWithURLSchema)
async def upload_video(request: Request, file: UploadFile = File(...), name: str = Form(...), description: str | None = Form(None), orientation: str | None = Form(None), is_show: bool = Form(True)):
    rel, file_hash, _ = await _save_file_with_hash(file, VIDEO_DIR, ALLOWED_VIDEO_EXTS)
    m = await MediaFile.get_or_none(file_hash=file_hash)
    if m is None:
        m = await MediaFile.get_or_none(file_path=rel)
        if m and not m.file_hash:
            try:
                await m.update_from_dict({"file_hash": file_hash}).save()
            except Exception as e:
                if "Duplicate entry" in str(e) and "file_hash" in str(e):
                    # 如果更新时发现hash重复，查找现有记录
                    existing_m = await MediaFile.get_or_none(file_hash=file_hash)
                    if existing_m:
                        m = existing_m
                    else:
                        raise e
                else:
                    raise e
        else:
            try:
                m = await MediaFile.create(name=name, file_path=rel, file_hash=file_hash, description=description, orientation=orientation, media_type="video", is_show=is_show, is_delete=False)
            except Exception as e:
                if "Duplicate entry" in str(e) and "file_hash" in str(e):
                    # 如果创建时发现hash重复，查找现有记录
                    m = await MediaFile.get_or_none(file_hash=file_hash)
                    if not m:
                        raise HTTPException(status_code=500, detail=f"文件hash冲突但找不到现有记录: {file_hash}")
                else:
                    raise HTTPException(status_code=500, detail=f"创建媒体记录失败: {str(e)}")
    await _cleanup_duplicates(rel, file_hash, m.id)

    if m.is_delete:
        await m.update_from_dict({"is_delete": False}).save()

    base = await MediaOutSchema.from_tortoise_orm(m)
    # 记录日志
    asyncio.create_task(media_log_tools(request=request, m=m, operation_type="CREATE", action="upload_video", action_description="上传", media_id=m.id))
    return MediaOutWithURLSchema(**base.model_dump(), url=str(request.url_for("audio_files", path=rel)))

@router.get("/media", response_model=List[MediaOutWithURLSchema])
async def list_media(request: Request, media_type: str | None = None, orientation: str | None = None):
    q = MediaFile.filter(is_delete=False)
    if media_type:
        q = q.filter(media_type=media_type)
    if orientation:
        q = q.filter(orientation=orientation)
    items = await q.order_by("-created_at").all()
    res = []
    for m in items:
        base = await MediaOutSchema.from_tortoise_orm(m)
        res.append(MediaOutWithURLSchema(**base.model_dump(), url=str(request.url_for("audio_files", path=m.file_path))) )
    return res

@router.patch("/media/{media_id}", response_model=MediaOutWithURLSchema)
async def update_media(media_id: int, data: MediaUpdateSchema, request: Request):

    m = await MediaFile.get_or_none(pk=media_id, is_delete=False)
    if not m:
        raise HTTPException(404, "媒体不存在")
    update_dict = data.model_dump(exclude_unset=True)
    if update_dict:
        await m.update_from_dict(update_dict).save()
    base = await MediaOutSchema.from_tortoise_orm(m)

    # 记录日志
    asyncio.create_task(media_log_tools(request=request, m=m, operation_type="UPDATE", action="update_media", action_description="更新", media_id=media_id))
    return MediaOutWithURLSchema(**base.model_dump(), url=str(request.url_for("audio_files", path=m.file_path)))

@router.delete("/media/{media_id}")
async def delete_media(request: Request, media_id: int):
    m = await MediaFile.get_or_none(pk=media_id)
    if not m:
        raise HTTPException(404, "媒体不存在")

    # 级联删除：先删除本地文件
    if m.file_path:
        file_full_path = STATIC_DIR / m.file_path
        try:
            if file_full_path.exists():
                file_full_path.unlink()  # 删除文件
                print(f"已删除本地文件: {file_full_path}")
        except Exception as e:
            print(f"删除本地文件失败: {file_full_path}, 错误: {e}")
            # 即使文件删除失败，也继续删除数据库记录

    # 删除数据库记录
    await m.delete()

    asyncio.create_task(media_log_tools(request=request, m=m, operation_type="DELETE", action="delete_media", action_description="删除", media_id=media_id))

    return {"message": "删除成功"}