import asyncio
from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException, Query
from typing import List, Set, Optional
from pathlib import Path
import uuid, os
from datetime import datetime
from ..v2.models import Logo, OperationLog
from .schema import LogoOutWithURLSchema, LogoUpdateSchema
import hashlib
from core.logger import logger

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = BASE_DIR / "static"
LOGO_DIR = STATIC_DIR / "site"
LOGO_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXTS: Set[str] = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}

def _generate_filename(ext: str) -> str:
    """生成文件名"""
    prefix = datetime.utcnow().strftime("%Y_%m_%d")
    return f"logo_{prefix}_{uuid.uuid4().hex[:8]}{ext}"

async def _save_logo_file(upload_file: UploadFile) -> str:
    """保存logo文件并返回相对路径"""
    ext = os.path.splitext(upload_file.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        raise HTTPException(400, f"不支持的文件类型 {ext}")

    content = await upload_file.read()
    filename = _generate_filename(ext)
    target_path = LOGO_DIR / filename
    
    with open(target_path, 'wb') as f:
        f.write(content)
    
    return f"site/{filename}"

def _create_logo_response(logo: Logo, request: Request) -> LogoOutWithURLSchema:
    """创建Logo响应对象"""
    return LogoOutWithURLSchema(
        id=logo.id,
        name=logo.name,
        file_path=logo.file_path,
        description=logo.description,
        update_log=logo.update_log,
        is_active=logo.is_active,
        created_at=logo.created_at,
        updated_at=logo.updated_at,
        url=logo.get_logo_url(request)
    )

@router.post("/upload", response_model=LogoOutWithURLSchema)
async def upload_logo(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    update_log: Optional[str] = Form(None),
    is_active: bool = Form(True)
):
    """上传Logo"""
    from api_versions.auth.routers import get_current_user
    
    # 获取当前用户
    try:
        current_user = await get_current_user(request)
        username = current_user.username
        is_admin = any(role.name in ["super_admin", "admin"] for role in await current_user.roles.all())
    except:
        username = "anonymous"
        is_admin = False

    # 保存文件
    file_path = await _save_logo_file(file)
    
    # 创建数据库记录
    logo = await Logo.create(
        name=name,
        file_path=file_path,
        description=description,
        update_log=update_log,
        is_active=is_active
    )

    # 记录操作日志
    try:
        await OperationLog.create(
            username=username,
            operation_type="CREATE",
            operation_content=f"上传Logo: {name}",
            target_type="logo",
            target_id=str(logo.id),
            ip_address=request.client.host if request.client else "unknown",
            status="success",
            details={
                "action": "upload_logo",
                "logo_name": name,
                "file_path": file_path
            },
            is_admin=is_admin
        )
    except Exception as e:
        logger.warning(f"记录操作日志失败: {e}")

    return _create_logo_response(logo, request)

@router.get("/list", response_model=List[LogoOutWithURLSchema])
async def list_logos(
    request: Request,
    is_active: Optional[bool] = Query(None, description="是否启用"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页数量")
):
    """获取Logo列表"""
    query = Logo.all()
    
    if is_active is not None:
        query = query.filter(is_active=is_active)
    
    # 分页
    offset = (page - 1) * size
    logos = await query.order_by("-created_at").offset(offset).limit(size)
    
    return [_create_logo_response(logo, request) for logo in logos]

@router.get("/{logo_id}", response_model=LogoOutWithURLSchema)
async def get_logo(request: Request, logo_id: int):
    """获取单个Logo"""
    logo = await Logo.get_or_none(id=logo_id)
    if not logo:
        raise HTTPException(404, "Logo不存在")
    
    return _create_logo_response(logo, request)

@router.put("/{logo_id}", response_model=LogoOutWithURLSchema)
async def update_logo(
    request: Request,
    logo_id: int,
    data: LogoUpdateSchema
):
    """更新Logo信息"""
    from api_versions.auth.routers import get_current_user
    
    # 获取当前用户
    try:
        current_user = await get_current_user(request)
        username = current_user.username
        is_admin = any(role.name in ["super_admin", "admin"] for role in await current_user.roles.all())
    except:
        username = "anonymous"
        is_admin = False

    logo = await Logo.get_or_none(id=logo_id)
    if not logo:
        raise HTTPException(404, "Logo不存在")
    
    # 更新数据
    update_dict = data.model_dump(exclude_unset=True)
    if update_dict:
        await logo.update_from_dict(update_dict).save()

    # 记录操作日志
    try:
        await OperationLog.create(
            username=username,
            operation_type="UPDATE",
            operation_content=f"更新Logo: {logo.name}",
            target_type="logo",
            target_id=str(logo.id),
            ip_address=request.client.host if request.client else "unknown",
            status="success",
            details={
                "action": "update_logo",
                "logo_id": logo_id,
                "updates": update_dict
            },
            is_admin=is_admin
        )
    except Exception as e:
        logger.warning(f"记录操作日志失败: {e}")

    return _create_logo_response(logo, request)

@router.put("/{logo_id}/file")
async def update_logo_file(
    request: Request,
    logo_id: int,
    file: UploadFile = File(...),
    update_log: Optional[str] = Form(None)
):
    """更新Logo文件"""
    from api_versions.auth.routers import get_current_user
    
    # 获取当前用户
    try:
        current_user = await get_current_user(request)
        username = current_user.username
        is_admin = any(role.name in ["super_admin", "admin"] for role in await current_user.roles.all())
    except:
        username = "anonymous"
        is_admin = False

    logo = await Logo.get_or_none(id=logo_id)
    if not logo:
        raise HTTPException(404, "Logo不存在")
    
    # 删除旧文件
    if logo.file_path:
        old_file_path = STATIC_DIR / logo.file_path
        try:
            if old_file_path.exists():
                old_file_path.unlink()
                logger.info(f"已删除旧Logo文件: {old_file_path}")
        except Exception as e:
            logger.warning(f"删除旧Logo文件失败: {e}")
    
    # 保存新文件
    new_file_path = await _save_logo_file(file)
    
    # 更新数据库记录
    update_data = {"file_path": new_file_path}
    if update_log:
        update_data["update_log"] = update_log
    
    await logo.update_from_dict(update_data).save()

    # 记录操作日志
    try:
        await OperationLog.create(
            username=username,
            operation_type="UPDATE",
            operation_content=f"更新Logo文件: {logo.name}",
            target_type="logo",
            target_id=str(logo.id),
            ip_address=request.client.host if request.client else "unknown",
            status="success",
            details={
                "action": "update_logo_file",
                "logo_id": logo_id,
                "new_file_path": new_file_path,
                "old_file_path": logo.file_path
            },
            is_admin=is_admin
        )
    except Exception as e:
        logger.warning(f"记录操作日志失败: {e}")

    return _create_logo_response(logo, request)

@router.delete("/{logo_id}")
async def delete_logo(request: Request, logo_id: int):
    """删除Logo"""
    from api_versions.auth.routers import get_current_user
    
    # 获取当前用户
    try:
        current_user = await get_current_user(request)
        username = current_user.username
        is_admin = any(role.name in ["super_admin", "admin"] for role in await current_user.roles.all())
    except:
        username = "anonymous"
        is_admin = False

    logo = await Logo.get_or_none(id=logo_id)
    if not logo:
        raise HTTPException(404, "Logo不存在")
    
    # 删除文件
    if logo.file_path:
        file_path = STATIC_DIR / logo.file_path
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"已删除Logo文件: {file_path}")
        except Exception as e:
            logger.warning(f"删除Logo文件失败: {e}")
    
    # 删除数据库记录
    logo_name = logo.name
    await logo.delete()

    # 记录操作日志
    try:
        await OperationLog.create(
            username=username,
            operation_type="DELETE",
            operation_content=f"删除Logo: {logo_name}",
            target_type="logo",
            target_id=str(logo_id),
            ip_address=request.client.host if request.client else "unknown",
            status="success",
            details={
                "action": "delete_logo",
                "logo_id": logo_id,
                "logo_name": logo_name
            },
            is_admin=is_admin
        )
    except Exception as e:
        logger.warning(f"记录操作日志失败: {e}")

    return {"message": "Logo删除成功"}

@router.patch("/{logo_id}/toggle")
async def toggle_logo_status(request: Request, logo_id: int):
    """切换Logo启用状态"""
    from api_versions.auth.routers import get_current_user
    
    # 获取当前用户
    try:
        current_user = await get_current_user(request)
        username = current_user.username
        is_admin = any(role.name in ["super_admin", "admin"] for role in await current_user.roles.all())
    except:
        username = "anonymous"
        is_admin = False

    logo = await Logo.get_or_none(id=logo_id)
    if not logo:
        raise HTTPException(404, "Logo不存在")
    
    # 切换状态
    new_status = not logo.is_active
    await logo.update_from_dict({"is_active": new_status}).save()

    # 记录操作日志
    try:
        await OperationLog.create(
            username=username,
            operation_type="UPDATE",
            operation_content=f"{'启用' if new_status else '禁用'}Logo: {logo.name}",
            target_type="logo",
            target_id=str(logo.id),
            ip_address=request.client.host if request.client else "unknown",
            status="success",
            details={
                "action": "toggle_logo_status",
                "logo_id": logo_id,
                "new_status": new_status,
                "old_status": not new_status
            },
            is_admin=is_admin
        )
    except Exception as e:
        logger.warning(f"记录操作日志失败: {e}")

    return _create_logo_response(logo, request)