from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status, Request
from pathlib import Path
from typing import Optional

from api_versions.auth.routers import get_current_user  # 复用现有的认证逻辑
from api_versions.v2.models import User, SiteConfig
from settings.config import AUDIO_DIR
from api_versions.logs.utils import record_operation_log

router = APIRouter()

# 静态文件子目录，用于存放站点相关文件（logo、favicon等）
SITE_STATIC_SUBDIR = "site"
SITE_STATIC_DIR: Path = AUDIO_DIR / SITE_STATIC_SUBDIR
SITE_STATIC_DIR.mkdir(parents=True, exist_ok=True)


# 公共成功返回
def success(data: Optional[dict] = None, message: str = "success"):
    """统一成功返回格式"""
    return {"code": 200, "message": message, "data": data}


# 工具函数：仅获取，不自动创建
async def _get_site_config() -> Optional[SiteConfig]:
    return await SiteConfig.first()


# 工具函数：若不存在则创建默认记录
async def _get_or_create_site_config() -> SiteConfig:
    cfg = await _get_site_config()
    if not cfg:
        cfg = await SiteConfig.create(title="数字人后台系统")
    return cfg


@router.get("/site", summary="获取站点配置")
async def get_site_config(request: Request):
    cfg = await _get_or_create_site_config()

    def _build_url(path_val: Optional[str]):
        if not path_val:
            return ""
        import time
        base_url = str(request.url_for("audio_files", path=path_val))
        return f"{base_url}?t={int(time.time())}"

    return success({
        "title": cfg.title,
        "logo": _build_url(cfg.logo_path),
        "favicon": _build_url(cfg.favicon_path),
    })


@router.put("/site", summary="更新站点配置", description="仅管理员可调用")
async def update_site_config(
    request: Request,
    title: Optional[str] = Form(None),
    logo: UploadFile | None = File(None),
    favicon: UploadFile | None = File(None),
    current_user: User = Depends(get_current_user),
):
    # 权限校验：仅管理员/超级管理员可修改
    await current_user.fetch_related("roles")
    is_admin = any(r.name in ["admin", "super_admin", "管理员", "超级管理员"] for r in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作")

    cfg = await _get_or_create_site_config()

    if title is not None:
        cfg.title = title

    async def _save_file(upload: UploadFile, filename: str) -> str:
        target_path: Path = SITE_STATIC_DIR / filename
        with open(target_path, "wb") as f:
            f.write(await upload.read())
        # 返回相对于 static 目录的路径（不要带 static/ 前缀）
        return f"{SITE_STATIC_SUBDIR}/{filename}"

    if logo is not None:
        suffix = Path(logo.filename).suffix or ".png"
        cfg.logo_path = await _save_file(logo, f"logo{suffix}")

    if favicon is not None:
        suffix = Path(favicon.filename).suffix or ".ico"
        cfg.favicon_path = await _save_file(favicon, f"favicon{suffix}")

    await cfg.save()

    # 记录操作日志
    await record_operation_log(
        request=request,
        username=current_user.username,
        operation_type="UPDATE",
        operation_content="修改站点配置",
        target_type="site",
        target_id=cfg.id,
        status="success",
        user=current_user,
    )

    # 返回更新后的配置
    return await get_site_config(request)


# 新增 POST: 创建站点配置（仅当不存在记录时）
@router.post("/site", summary="创建站点配置", description="仅管理员可调用")
async def create_site_config(
    request: Request,
    title: str = Form(...),
    logo: UploadFile | None = File(None),
    favicon: UploadFile | None = File(None),
    current_user: User = Depends(get_current_user),
):
    # 权限校验
    await current_user.fetch_related("roles")
    is_admin = any(r.name in ["admin", "super_admin", "管理员", "超级管理员"] for r in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作")

    # 检查是否已存在
    if await _get_site_config():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="配置已存在，请使用 PUT 进行修改")

    cfg = SiteConfig(title=title)

    async def _save_file(upload: UploadFile, filename: str) -> str:
        target_path: Path = SITE_STATIC_DIR / filename
        with open(target_path, "wb") as f:
            f.write(await upload.read())
        return f"{SITE_STATIC_SUBDIR}/{filename}"

    if logo is not None:
        suffix = Path(logo.filename).suffix or ".png"
        cfg.logo_path = await _save_file(logo, f"logo{suffix}")

    if favicon is not None:
        suffix = Path(favicon.filename).suffix or ".ico"
        cfg.favicon_path = await _save_file(favicon, f"favicon{suffix}")

    await cfg.save()

    # 记录操作日志
    await record_operation_log(
        request=request,
        username=current_user.username,
        operation_type="CREATE",
        operation_content="创建站点配置",
        target_type="site",
        target_id=cfg.id,
        status="success",
        user=current_user,
    )

    return await get_site_config(request) 