from fastapi import APIRouter, status, HTTPException, Request
from .schema import DeviceCreateSchema, DeviceUpdateSchema, AppWithKeySchema, Device_Pydantic, App_Pydantic, DeviceWithAppsSchema
from api_versions.v2.models import Device, App

# 日志记录依赖
from api_versions.auth.routers import get_current_user
from api_versions.v2.models import OperationLog
from core.logger import logger


routers = APIRouter()


# 创建设备
@routers.post("/devices", status_code=status.HTTP_201_CREATED)
async def create_device(request: Request, device_data: DeviceCreateSchema):
    try:
        device = await Device.create(**device_data.model_dump())
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
                operation_content=f"创建设备: {device.name}",
                target_type="device",
                target_id=str(device.id),
                ip_address=request.client.host if request.client else "unknown",
                status="success",
                details={"action": "create_device", "device_id": device.id},
                is_admin=is_admin
            )
        except Exception as e:
            logger.warning(f"记录操作日志失败: {e}")

        return await Device_Pydantic.from_tortoise_orm(device)
    except  Exception as e:
        # 记录失败日志
        try:
            await OperationLog.create(
                username="anonymous",
                operation_type="CREATE",
                operation_content=f"创建设备失败: {device_data.name}",
                target_type="device",
                target_id=None,
                ip_address=request.client.host if request.client else "unknown",
                status="failed",
                details={"error": str(e)},
                is_admin=False
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"创建设备失败: {str(e)}"
        )

# 获取全部设备
@routers.get("/devices", description="获取全部设备")
async def get_all_devices():
    return await Device_Pydantic.from_queryset(Device.all())


# 获取设备详情接口
@routers.get("/devices/{device_id}", response_model=DeviceWithAppsSchema, description="获取设备关联的全部应用")
async def get_one_device(device_id: str):
    # 使用正确的查询方式（根据name查询）
    device = await (
        Device.filter(name=device_id)
        .prefetch_related("apps")  # 预加载关联应用
        .first()
    )
    
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 获取设备基础信息（使用Pydantic v2语法）
    device_data = Device_Pydantic.from_orm(device)
    
    # 获取完整关联应用（包含中间表字段）
    related_apps = await device.apps.all().prefetch_related("app_devices")
    
    # 构建响应数据
    apps = [
        AppWithKeySchema(
            id=app.id,
            name=app.name,
            description=app.description,
            api_key=app.api_key,  # 应用自身的api_key
            created_at=app.created_at,
            updated_at=app.updated_at
        ) for app in related_apps
    ]
    
    return DeviceWithAppsSchema(
        **device_data.model_dump(),
        apps=apps
    )

@routers.put("/devices/{device_id}")
async def update_device(request: Request, device_id:int, device_data: DeviceUpdateSchema):
    device = await Device.get_or_none(pk=device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="设备不存在"
        )

    update_data = device_data.model_dump(exclude_unset=True)
    await device.update_from_dict(update_data).save()

    # 记录日志
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
            operation_content=f"更新设备: {device.name}",
            target_type="device",
            target_id=str(device.id),
            ip_address=request.client.host if request.client else "unknown",
            status="success",
            details={"action": "update_device", "device_id": device.id},
            is_admin=is_admin
        )
    except Exception as e:
        logger.warning(f"记录操作日志失败: {e}")
    return await Device_Pydantic.from_tortoise_orm(device)

@routers.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT, description="删除设备")
async def delete_device(request: Request, device_id: int):
    device = await Device.get_or_none(pk=device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    await device.delete()

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
            operation_content=f"删除设备: {device.name}",
            target_type="device",
            target_id=str(device_id),
            ip_address=request.client.host if request.client else "unknown",
            status="success",
            details={"action": "delete_device", "device_id": device_id},
            is_admin=is_admin
        )
    except Exception as e:
        logger.warning(f"记录操作日志失败: {e}")
    return {"detail": "设备已删除"}

@routers.get("/apps")
async def get_all_apps():
    return await App_Pydantic.from_queryset(App.all())

@routers.post("/devices/{device_id}/apps/{app_id}", status_code=status.HTTP_204_NO_CONTENT, summary="绑定应用")
async def bind_app(request: Request, device_id:int, app_id:int):
    try:
        logger.info(f"开始绑定操作: device_id={device_id}, app_id={app_id}")
        
        device = await Device.get_or_none(id=device_id)
        app = await App.get_or_none(id=app_id)
        
        logger.info(f"查询结果: device={'found' if device else 'not found'}, app={'found' if app else 'not found'}")
        
        if not device or not app:
            logger.warning(f"设备或应用不存在: device_id={device_id}, app_id={app_id}")
            raise HTTPException(status_code=404, detail="设备或应用不存在")
        
        logger.info(f"开始执行绑定: {device.name} -> {app.name}")
        await device.apps.add(app)
        logger.info(f"绑定操作执行完成")
        
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
                operation_type="BIND",
                operation_content=f"绑定应用: {device.name} -> {app.name}",
                target_type="device_app",
                target_id=f"{device_id}_{app_id}",
                ip_address=request.client.host if request.client else "unknown",
                status="success",
                details={"action": "bind_app", "device_id": device_id, "app_id": app_id},
                is_admin=is_admin
            )
        except Exception as e:
            logger.warning(f"记录操作日志失败: {e}")
        
        logger.info(f"绑定操作成功: device_id={device_id}, app_id={app_id}")
        return {"detail": "绑定成功"}
    except HTTPException:
        raise
    except Exception as e:
        # 记录失败日志
        try:
            await OperationLog.create(
                username="anonymous",
                operation_type="BIND",
                operation_content=f"绑定应用失败: device_id={device_id}, app_id={app_id}",
                target_type="device_app",
                target_id=f"{device_id}_{app_id}",
                ip_address=request.client.host if request.client else "unknown",
                status="failed",
                details={"error": str(e)},
                is_admin=False
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"绑定应用失败: {str(e)}"
        )

@routers.delete("/devices/{device_id}/apps/{app_id}", status_code=status.HTTP_204_NO_CONTENT, summary="解绑应用")
async def unbind_app(request: Request, device_id:int, app_id:int):
    try:
        device = await Device.get_or_none(id=device_id)
        app = await App.get_or_none(id=app_id)
        if not device or not app:
            raise HTTPException(status_code=404, detail="设备或应用不存在")
        
        await device.apps.remove(app)
        
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
                operation_type="UNBIND",
                operation_content=f"解绑应用: {device.name} -> {app.name}",
                target_type="device_app",
                target_id=f"{device_id}_{app_id}",
                ip_address=request.client.host if request.client else "unknown",
                status="success",
                details={"action": "unbind_app", "device_id": device_id, "app_id": app_id},
                is_admin=is_admin
            )
        except Exception as e:
            logger.warning(f"记录操作日志失败: {e}")
        
        return {"detail": "解绑成功"}
    except HTTPException:
        raise
    except Exception as e:
        # 记录失败日志
        try:
            await OperationLog.create(
                username="anonymous",
                operation_type="UNBIND",
                operation_content=f"解绑应用失败: device_id={device_id}, app_id={app_id}",
                target_type="device_app",
                target_id=f"{device_id}_{app_id}",
                ip_address=request.client.host if request.client else "unknown",
                status="failed",
                details={"error": str(e)},
                is_admin=False
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"解绑应用失败: {str(e)}"
        )

