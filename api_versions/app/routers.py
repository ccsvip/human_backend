from fastapi import APIRouter, HTTPException, status, Request
from api_versions.device.schema import AppCreateSchema, AppUpdateSchema, App_Pydantic
from api_versions.v2.models import App

# 日志记录依赖
from api_versions.auth.routers import get_current_user
from api_versions.v2.models import OperationLog
from core.logger import logger

router = APIRouter()

@router.get('/apps', summary='获取全部应用')
async def list_apps():
    return await App_Pydantic.from_queryset(App.all())

@router.post('/apps', status_code=status.HTTP_201_CREATED, summary='创建应用')
async def create_app(request: Request, app_data: AppCreateSchema):
    if await App.filter(name=app_data.name).exists():
        raise HTTPException(status_code=400, detail='应用已存在')
    app = await App.create(**app_data.model_dump())

    # 记录操作日志
    try:
        try:
            current_user = await get_current_user(request)
            username = current_user.username
            is_admin = any(role.name in ["super_admin", "admin"] for role in await current_user.roles.all())
        except Exception:
            username = "anonymous"
            is_admin = False

        await OperationLog.create(
            username=username,
            operation_type="CREATE",
            operation_content=f"创建应用: {app.name}",
            target_type="app",
            target_id=str(app.id),
            ip_address=request.client.host if request.client else "unknown",
            status="success",
            details={"action": "create_app", "app_id": app.id},
            is_admin=is_admin
        )
    except Exception as e:
        logger.warning(f"记录操作日志失败: {e}")
    return await App_Pydantic.from_tortoise_orm(app)

@router.put('/apps/{app_id}', summary='更新应用')
async def update_app(request: Request, app_id: int, app_data: AppUpdateSchema):
    app = await App.get_or_none(id=app_id)
    if not app:
        raise HTTPException(status_code=404, detail='应用不存在')
    await app.update_from_dict(app_data.model_dump(exclude_unset=True)).save()

    try:
        try:
            current_user = await get_current_user(request)
            username = current_user.username
            is_admin = any(role.name in ["super_admin", "admin"] for role in await current_user.roles.all())
        except Exception:
            username = "anonymous"
            is_admin = False

        await OperationLog.create(
            username=username,
            operation_type="UPDATE",
            operation_content=f"更新应用: {app.name}",
            target_type="app",
            target_id=str(app.id),
            ip_address=request.client.host if request.client else "unknown",
            status="success",
            details={"action": "update_app", "app_id": app.id},
            is_admin=is_admin
        )
    except Exception as e:
        logger.warning(f"记录操作日志失败: {e}")
    return await App_Pydantic.from_tortoise_orm(app)

@router.delete('/apps/{app_id}', status_code=status.HTTP_204_NO_CONTENT, summary='删除应用')
async def delete_app(request: Request, app_id: int):
    app = await App.get_or_none(id=app_id)
    if not app:
        raise HTTPException(status_code=404, detail='应用不存在')
    await app.delete()

    try:
        try:
            current_user = await get_current_user(request)
            username = current_user.username
            is_admin = any(role.name in ["super_admin", "admin"] for role in await current_user.roles.all())
        except Exception:
            username = "anonymous"
            is_admin = False

        await OperationLog.create(
            username=username,
            operation_type="DELETE",
            operation_content=f"删除应用: {app.name if app else app_id}",
            target_type="app",
            target_id=str(app_id),
            ip_address=request.client.host if request.client else "unknown",
            status="success",
            details={"action": "delete_app", "app_id": app_id},
            is_admin=is_admin
        )
    except Exception as e:
        logger.warning(f"记录操作日志失败: {e}")
    return {'detail': '应用已删除'} 