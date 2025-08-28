from core.logger import logger

async def media_log_tools(*, request, m, operation_type, action, action_description, **kwargs):
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
    
    # 保存文件信息用于日志记录
    file_name = m.name
    file_path = m.file_path
    media_type = m.media_type

    media_id = kwargs.get("media_id")

    # 记录日志
    try:
        await OperationLog.create(
            username=username,
            operation_type=operation_type,
            operation_content=f"{action_description}{media_type}: {file_name}",
            target_type="media",
            target_id=str(media_id),
            ip_address=request.client.host if request.client else "unknown",
            status="success",
            details={
                "action": action,
                "file_name": file_name,
                "file_path": file_path,
                "media_type": media_type
            },
            is_admin=is_admin
        )
    except Exception as e:
        # 操作日志记录失败不影响主要功能
        logger.warning(f"记录{action_description}操作日志失败: {e}")