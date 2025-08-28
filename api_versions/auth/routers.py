from fastapi import APIRouter, HTTPException, status, Request, Depends
from datetime import datetime, timedelta
import time
import jwt
from settings.config import settings
from api_versions.v2.models import User, Role, Permission, PathPermission
from .schema import (
    InitUserSchema, LoginSchema, LoginResultSchema,
    UserProfileSchema, UpdateProfileSchema, ChangePasswordSchema, UpdateAvatarSchema,
    RoleSchema, CreateUserSchema, UpdateUserSchema, UserListResponseSchema, 
    UserListQuerySchema, ResetPasswordSchema, CreatePathPermissionSchema,
    UpdatePathPermissionSchema, PathPermissionResponseSchema
)
from api_versions.logs.utils import record_login_log, record_operation_log

router = APIRouter()

JWT_SECRET = getattr(settings, "api_key", "human_api_secret")
JWT_EXPIRE_SECONDS = 60 * 60 * 24  # 1 天

def success(data=None, message="success"):
    return {"code": 200, "message": message, "data": data}

@router.get("/init", summary="检查是否已经初始化")
async def check_init():
    count = await User.all().count()
    return success({"initialized": count > 0})

@router.post("/init", summary="初始化管理员用户")
async def init_admin(data: InitUserSchema):
    # 已初始化则禁止
    count = await User.all().count()
    if count > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="系统已初始化")

    # 创建管理员角色
    admin_role = await Role.get_or_none(name="admin")
    if not admin_role:
        admin_role = await Role.create(name="admin", description="管理员")

    # 创建用户
    password_hash = User.hash_password(data.password)
    user = await User.create(username=data.username, password_hash=password_hash)
    await user.roles.add(admin_role)
    return success(message="初始化成功")

@router.post("/login", summary="用户登录")
async def login(data: LoginSchema, request: Request):
    user = await User.get_or_none(username=data.username)
    
    # 用户不存在
    if not user:
        # 记录失败的登录日志
        await record_login_log(
            request=request,
            username=data.username,
            status="failed",
            login_message="用户不存在"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名或密码错误")
    
    # 密码错误
    if not user.verify_password(data.password):
        # 记录失败的登录日志
        await record_login_log(
            request=request,
            username=data.username,
            status="failed",
            login_message="密码错误",
            user=user
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名或密码错误")

    # 登录成功，生成token
    payload = {
        "user_id": user.id,
        "username": user.username,
        "exp": int(time.time()) + JWT_EXPIRE_SECONDS,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    
    # 记录成功的登录日志
    await record_login_log(
        request=request,
        username=user.username,
        status="success",
        login_message="登录成功",
        user=user
    )
    
    return success({"token": token})

@router.post("/user", summary="获取当前用户信息")
async def get_user_info(request: Request):
    token = request.headers.get("Token")
    if not token:
        data = await request.json()
        token = data if isinstance(data, str) else data.get("token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供Token")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token无效")
    user_id = payload.get("user_id")
    user = await User.get_or_none(id=user_id).prefetch_related("roles", "roles__permissions")
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    # 组装用户信息
    roles_objs = await user.roles.all()
    roles = [r.name for r in roles_objs]
    permissions = []
    for r in roles_objs:
        perms = await r.permissions.all()
        permissions.extend([p.code for p in perms])
    
    # 根据权限生成可访问的路由
    unique_permissions = list(set(permissions))
    routes = []
    
    # 调试信息：打印用户权限和角色
    # print(f"用户 {user.username} 的角色: {roles}")
    # print(f"用户 {user.username} 的权限: {unique_permissions}")
    
    # 检查是否为管理员 - 扩展角色名称匹配
    admin_roles = ["admin", "super_admin", "管理员", "超级管理员"]
    is_admin = any(role in admin_roles for role in roles)

    # 调试信息：打印用户角色和管理员判断结果
    print(f"用户 {user.username} 的角色: {roles}")
    print(f"用户 {user.username} 是否为管理员: {is_admin}")

    if is_admin:
        # 管理员可以访问所有路由
        routes = [
            "rbac", "rbac-user", "rbac-role", "rbac-permission", "rbac-analysis",
            "media-manage", "media-image", "media-video",
            "system", "system-app", "system-device", "system-env", "system-site", "system-logo", "system-profile",
            "cache-manage", "cache-list", "cache-create", "cache-operate", "cache-clear",
            "model-manage", "model-list", "model-wakeword",
            "test", "test-digital-human", "test-audio-data",
            "logs", "logs-login", "logs-operation"
        ]
        print(f"管理员 {user.username} 的完整路由列表: {routes}")
    else:
        # 根据具体权限分配路由 - 更精确的控制
        system_routes = []
        rbac_routes = []
        
        for perm in unique_permissions:
            # 用户权限管理 - 精确匹配
            if perm in ["user:view", "user:create", "user:edit", "user:delete", "user:reset_password"]:
                if "rbac-user" not in rbac_routes:
                    rbac_routes.append("rbac-user")
            elif perm in ["role:view", "role:create", "role:edit", "role:delete", "role:assign_permission"]:
                if "rbac-role" not in rbac_routes:
                    rbac_routes.append("rbac-role")
            elif perm in ["permission:view", "permission:create", "permission:edit", "permission:delete"]:
                if "rbac-permission" not in rbac_routes:
                    rbac_routes.append("rbac-permission")
            
            # 系统管理权限 - 精确匹配
            elif perm == "system:app":
                if "system-app" not in system_routes:
                    system_routes.append("system-app")
            elif perm == "system:device":
                if "system-device" not in system_routes:
                    system_routes.append("system-device")
            elif perm == "system:env":
                if "system-env" not in system_routes:
                    system_routes.append("system-env")
            elif perm == "system:config":
                if "system-site" not in system_routes:
                    system_routes.append("system-site")
            
            # 媒体管理 - 精确匹配
            elif perm in ["media:view", "media:upload", "media:delete"]:
                routes.extend(["media-manage", "media-image", "media-video"])
            
            # 缓存管理 - 精确匹配
            elif perm in ["cache:view", "cache:create", "cache:clear"]:
                routes.extend(["cache-manage", "cache-list", "cache-create", "cache-operate", "cache-clear"])
            
            # 模型管理 - 精确匹配
            elif perm in ["model:view", "model:create", "model:edit", "model:delete"]:
                routes.extend(["model-manage", "model-list"])
            
            # 唤醒词管理 - 精确匹配
            elif perm in ["wakeword:view", "wakeword:create", "wakeword:edit", "wakeword:delete"]:
                routes.extend(["model-manage", "model-wakeword"])
            
            # 日志管理权限
            elif perm in ["logs:login:view", "logs:login:delete", "logs:operation:view", "logs:operation:delete"]:
                print(f"用户 {user.username} 有日志权限 {perm}，添加日志路由")
                routes.extend(["logs", "logs-login", "logs-operation"])

            # 如果用户有系统管理权限，也给予日志管理权限
            elif perm in ["system:env", "system:device", "system:app", "system:config"]:
                if "logs" not in routes:
                    routes.extend(["logs", "logs-login", "logs-operation"])

            # 个人中心权限
            elif perm in ["profile:view", "profile:edit"]:
                system_routes.extend(["system-profile"])
        
        # 只有当有系统管理相关权限时，才添加system父路由
        if system_routes:
            routes.extend(["system"] + system_routes)
        
        # 只有当有RBAC相关权限时，才添加rbac父路由
        if rbac_routes:
            print(f"用户 {user.username} 的RBAC路由: {rbac_routes}")
            routes.extend(["rbac"] + rbac_routes)
        else:
            print(f"用户 {user.username} 没有RBAC权限，不添加RBAC路由")
        
        # 基础路由，所有用户都可以访问
        routes.extend(["home", "test", "test-digital-human", "test-audio-data"])
        
        # 去重
        routes = list(set(routes))
    
    # 调试信息：打印最终的路由列表
    final_routes = list(set(routes))
    print(f"用户 {user.username} 最终路由权限: {final_routes}")

    return success({
        "id": user.id,
        "username": user.username,
        "avatar": user.avatar,
        "img_url": user.get_img_url(request),  # 使用request构建完整的头像URL
        "roles": roles,
        "permissions": unique_permissions,
        "routes": final_routes,  # 去重
    })

# JWT依赖函数
async def get_current_user(request: Request) -> User:
    """从请求中获取当前用户"""
    token = request.headers.get("Authorization")
    if token and token.startswith("Bearer "):
        token = token[7:]
    else:
        token = request.headers.get("Token")
    
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供Token")
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token无效")
    
    user_id = payload.get("user_id")
    user = await User.get_or_none(id=user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    
    return user

@router.get("/profile", summary="获取个人资料")
async def get_profile(request: Request, current_user: User = Depends(get_current_user)):
    """获取当前用户的个人资料"""
    await current_user.fetch_related("roles")
    
    # 构建角色信息
    roles_data = []
    for role in current_user.roles:
        roles_data.append({
            "id": role.id,
            "name": role.name,
            "display_name": role.description or role.name,
            "description": role.description
        })
    
    profile_data = {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "phone": current_user.phone,
        "gender": current_user.gender,
        "department": current_user.department,
        "avatar": current_user.avatar,
        "img_url": current_user.get_img_url(request),  # 使用request构建完整的头像URL
        "roles": roles_data,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at
    }
    
    return success(profile_data)

@router.put("/profile", summary="更新个人资料")
async def update_profile(
    profile_data: UpdateProfileSchema,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """更新当前用户的个人资料"""
    update_fields = {}
    
    if profile_data.email is not None:
        update_fields["email"] = profile_data.email
    if profile_data.phone is not None:
        update_fields["phone"] = profile_data.phone
    if profile_data.gender is not None:
        update_fields["gender"] = profile_data.gender
    if profile_data.department is not None:
        update_fields["department"] = profile_data.department
    
    if update_fields:
        await User.filter(id=current_user.id).update(**update_fields)
    
    # 记录操作日志
    await record_operation_log(
        request=request,
        username=current_user.username,
        operation_type="UPDATE",
        operation_content="修改个人资料",
        target_type="user",
        target_id=current_user.id,
        status="success",
        user=current_user,
    )
    return success(message="个人资料更新成功")

@router.put("/profile/avatar", summary="更新头像")
async def update_avatar(
    avatar_data: UpdateAvatarSchema,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """更新当前用户的头像"""
    await User.filter(id=current_user.id).update(avatar=avatar_data.avatar)

    await record_operation_log(
        request=request,
        username=current_user.username,
        operation_type="UPDATE",
        operation_content="修改头像",
        target_type="user",
        target_id=current_user.id,
        status="success",
        user=current_user,
    )
    return success(message="头像更新成功")

@router.put("/profile/password", summary="修改密码")
async def change_password(
    password_data: ChangePasswordSchema,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """修改当前用户的密码"""
    # 验证当前密码
    if not current_user.verify_password(password_data.current_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码错误")
    
    # 更新密码
    new_password_hash = User.hash_password(password_data.new_password)
    await User.filter(id=current_user.id).update(password_hash=new_password_hash)
    
    # 记录操作日志
    await record_operation_log(
        request=request,
        username=current_user.username,
        operation_type="UPDATE",
        operation_content="修改密码",
        target_type="user",
        target_id=current_user.id,
        status="success",
        user=current_user,
    )
    return success(message="密码修改成功")

# ====== 用户管理API ======

@router.get("/users", summary="获取用户列表")
async def get_users(
    request: Request,
    page: int = 1,
    size: int = 10,
    search: str = None,
    current_user: User = Depends(get_current_user)
):
    """获取用户列表（分页）"""
    # 检查权限 - 只有管理员可以访问
    await current_user.fetch_related("roles")
    is_admin = any(role.name == "admin" for role in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    
    # 构建查询
    query = User.all().prefetch_related("roles")
    
    # 搜索条件
    if search:
        query = query.filter(
            username__icontains=search
        ) | query.filter(
            email__icontains=search
        )
    
    # 分页
    total = await query.count()
    users = await query.offset((page - 1) * size).limit(size)
    
    # 构建响应数据
    users_data = []
    for user in users:
        roles_data = []
        for role in user.roles:
            roles_data.append({
                "id": role.id,
                "name": role.name,
                "display_name": role.description or role.name,
                "description": role.description
            })
        
        users_data.append({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "gender": user.gender,
            "department": user.department,
            "avatar": user.avatar,
            "img_url": user.get_img_url(request),
            "roles": roles_data,
            "is_active": True,  # 暂时固定为True，因为User模型还没有is_active字段
            "is_superuser": user.id == 1,  # 第一个用户为超级管理员
            "created_at": user.created_at,
            "updated_at": user.updated_at
        })
    
    return success({
        "items": users_data,
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    })

@router.post("/users", summary="创建用户")
async def create_user(
    user_data: CreateUserSchema,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """创建新用户"""
    # 检查权限
    await current_user.fetch_related("roles")
    is_admin = any(role.name == "admin" for role in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    
    # 检查用户名是否已存在
    existing_user = await User.get_or_none(username=user_data.username)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")
    
    # 检查邮箱是否已存在
    if user_data.email:
        existing_email = await User.get_or_none(email=user_data.email)
        if existing_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已存在")
    
    # 创建用户
    password_hash = User.hash_password(user_data.password)
    user = await User.create(
        username=user_data.username,
        password_hash=password_hash,
        email=user_data.email,
        phone=user_data.phone,
        gender=user_data.gender,
        department=user_data.department
    )
    
    # 分配角色
    if user_data.role_ids:
        roles = await Role.filter(id__in=user_data.role_ids)
        for role in roles:
            await user.roles.add(role)
    
    await record_operation_log(
        request=request,
        username=current_user.username,
        operation_type="CREATE",
        operation_content=f"创建用户 {user.username}",
        target_type="user",
        target_id=user.id,
        status="success",
        user=current_user,
    )
    return success({"id": user.id, "username": user.username}, "用户创建成功")

@router.put("/users/{user_id}", summary="更新用户")
async def update_user(
    user_id: int,
    user_data: UpdateUserSchema,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """更新用户信息"""
    # 检查权限
    await current_user.fetch_related("roles")
    is_admin = any(role.name == "admin" for role in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    
    # 获取目标用户
    target_user = await User.get_or_none(id=user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    
    # 更新基本信息
    update_fields = {}
    if user_data.email is not None:
        # 检查邮箱是否已被其他用户使用
        if user_data.email:
            existing_email = await User.get_or_none(email=user_data.email)
            if existing_email and existing_email.id != user_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被其他用户使用")
        update_fields["email"] = user_data.email
    
    if user_data.phone is not None:
        update_fields["phone"] = user_data.phone
    if user_data.gender is not None:
        update_fields["gender"] = user_data.gender
    if user_data.department is not None:
        update_fields["department"] = user_data.department
    
    # 更新基本信息
    if update_fields:
        await User.filter(id=user_id).update(**update_fields)
    
    # 更新角色
    if user_data.role_ids is not None:
        await target_user.fetch_related("roles")
        # 清除现有角色
        await target_user.roles.clear()
        # 添加新角色
        if user_data.role_ids:
            roles = await Role.filter(id__in=user_data.role_ids)
            for role in roles:
                await target_user.roles.add(role)
    
    await record_operation_log(
        request=request,
        username=current_user.username,
        operation_type="UPDATE",
        operation_content=f"更新用户 {target_user.username}",
        target_type="user",
        target_id=target_user.id,
        status="success",
        user=current_user,
    )
    return success(message="用户更新成功")

@router.delete("/users/{user_id}", summary="删除用户")
async def delete_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """删除用户"""
    # 检查权限
    await current_user.fetch_related("roles")
    is_admin = any(role.name == "admin" for role in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    
    # 不能删除自己
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除自己")
    
    # 不能删除第一个用户（超级管理员）
    if user_id == 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除超级管理员")
    
    # 获取目标用户
    target_user = await User.get_or_none(id=user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    
    # 删除用户
    await target_user.delete()
    
    await record_operation_log(
        request=request,
        username=current_user.username,
        operation_type="DELETE",
        operation_content=f"删除用户 {target_user.username}",
        target_type="user",
        target_id=target_user.id,
        status="success",
        user=current_user,
    )
    return success(message="用户删除成功")

@router.post("/users/{user_id}/reset-password", summary="重置用户密码")
async def reset_user_password(
    user_id: int,
    password_data: ResetPasswordSchema,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """重置用户密码"""
    # 检查权限
    await current_user.fetch_related("roles")
    is_admin = any(role.name == "admin" for role in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    
    # 获取目标用户
    target_user = await User.get_or_none(id=user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    
    # 重置密码
    new_password_hash = User.hash_password(password_data.new_password)
    await User.filter(id=user_id).update(password_hash=new_password_hash)
    
    await record_operation_log(
        request=request,
        username=current_user.username,
        operation_type="UPDATE",
        operation_content=f"重置用户密码 {target_user.username}",
        target_type="user",
        target_id=target_user.id,
        status="success",
        user=current_user,
    )
    return success(message="密码已重置")

# ====== 权限管理API ======

@router.get("/permissions", summary="获取权限列表")
async def get_permissions(current_user: User = Depends(get_current_user)):
    """获取所有权限列表"""
    # 检查权限（只有管理员才能查看）
    await current_user.fetch_related("roles")
    is_admin = any(role.name in ["admin", "super_admin"] for role in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问")
    
    permissions = await Permission.all()
    permissions_data = []
    for perm in permissions:
        permissions_data.append({
            "id": perm.id,
            "name": perm.name,
            "code": perm.code,
            "description": perm.description,
            "created_at": perm.created_at
        })
    
    return success(permissions_data)

@router.post("/permissions", summary="创建权限")
async def create_permission(
    permission_data: dict,
    current_user: User = Depends(get_current_user)
):
    """创建新权限"""
    # 检查权限（只有超级管理员才能创建权限）
    await current_user.fetch_related("roles")
    is_super_admin = any(role.name == "super_admin" for role in current_user.roles)
    if not is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作")
    
    # 检查权限编码是否已存在
    if await Permission.filter(code=permission_data["code"]).exists():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="权限编码已存在")
    
    permission = await Permission.create(
        name=permission_data["name"],
        code=permission_data["code"],
        description=permission_data.get("description", "")
    )
    
    return success({
        "id": permission.id,
        "name": permission.name,
        "code": permission.code,
        "description": permission.description
    }, "权限创建成功")

@router.put("/permissions/{permission_id}", summary="更新权限")
async def update_permission(
    permission_id: int,
    permission_data: dict,
    current_user: User = Depends(get_current_user)
):
    """更新权限信息"""
    # 检查权限（只有超级管理员才能更新权限）
    await current_user.fetch_related("roles")
    is_super_admin = any(role.name == "super_admin" for role in current_user.roles)
    if not is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作")
    
    permission = await Permission.get_or_none(id=permission_id)
    if not permission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="权限不存在")
    
    # 更新权限信息
    update_fields = {}
    if "name" in permission_data:
        update_fields["name"] = permission_data["name"]
    if "description" in permission_data:
        update_fields["description"] = permission_data["description"]
    
    if update_fields:
        await Permission.filter(id=permission_id).update(**update_fields)
    
    return success(message="权限更新成功")

@router.delete("/permissions/{permission_id}", summary="删除权限")
async def delete_permission(
    permission_id: int,
    current_user: User = Depends(get_current_user)
):
    """删除权限"""
    # 检查权限（只有超级管理员才能删除权限）
    await current_user.fetch_related("roles")
    is_super_admin = any(role.name == "super_admin" for role in current_user.roles)
    if not is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作")
    
    permission = await Permission.get_or_none(id=permission_id)
    if not permission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="权限不存在")
    
    # 检查是否有角色使用此权限
    roles_count = await permission.roles.all().count()
    if roles_count > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该权限正在被角色使用，无法删除")
    
    await permission.delete()
    return success(message="权限删除成功")

# ====== 角色管理API ======

@router.get("/roles", summary="获取角色列表")
async def get_roles(current_user: User = Depends(get_current_user)):
    """获取所有角色列表"""
    # 检查权限（只有管理员才能查看）
    await current_user.fetch_related("roles")
    is_admin = any(role.name in ["admin", "super_admin"] for role in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问")
    
    roles = await Role.all().prefetch_related("permissions", "users")
    roles_data = []
    for role in roles:
        permissions_data = []
        for perm in role.permissions:
            permissions_data.append({
                "id": perm.id,
                "name": perm.name,
                "code": perm.code
            })
        
        users_count = len(role.users)
        
        roles_data.append({
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "permissions": permissions_data,
            "users_count": users_count,
            "created_at": role.created_at
        })
    
    return success(roles_data)

@router.post("/roles", summary="创建角色")
async def create_role(
    role_data: dict,
    current_user: User = Depends(get_current_user)
):
    """创建新角色"""
    # 检查权限（只有管理员才能创建角色）
    await current_user.fetch_related("roles")
    is_admin = any(role.name in ["admin", "super_admin"] for role in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作")
    
    # 检查角色名称是否已存在
    if await Role.filter(name=role_data["name"]).exists():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="角色名称已存在")
    
    role = await Role.create(
        name=role_data["name"],
        description=role_data.get("description", "")
    )
    
    # 分配权限
    if "permission_ids" in role_data and role_data["permission_ids"]:
        permissions = await Permission.filter(id__in=role_data["permission_ids"])
        await role.permissions.add(*permissions)
    
    return success({
        "id": role.id,
        "name": role.name,
        "description": role.description
    }, "角色创建成功")

@router.put("/roles/{role_id}", summary="更新角色")
async def update_role(
    role_id: int,
    role_data: dict,
    current_user: User = Depends(get_current_user)
):
    """更新角色信息"""
    # 检查权限（只有管理员才能更新角色）
    await current_user.fetch_related("roles")
    is_admin = any(role.name in ["admin", "super_admin"] for role in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作")
    
    role = await Role.get_or_none(id=role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
    
    # 更新基本信息
    update_fields = {}
    if "name" in role_data and role_data["name"] != role.name:
        # 检查新名称是否已存在
        if await Role.filter(name=role_data["name"]).exists():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="角色名称已存在")
        update_fields["name"] = role_data["name"]
    
    if "description" in role_data:
        update_fields["description"] = role_data["description"]
    
    if update_fields:
        await Role.filter(id=role_id).update(**update_fields)
    
    # 更新权限分配
    if "permission_ids" in role_data:
        await role.permissions.clear()
        if role_data["permission_ids"]:
            permissions = await Permission.filter(id__in=role_data["permission_ids"])
            await role.permissions.add(*permissions)
    
    return success(message="角色更新成功")

@router.delete("/roles/{role_id}", summary="删除角色")
async def delete_role(
    role_id: int,
    current_user: User = Depends(get_current_user)
):
    """删除角色"""
    # 检查权限（只有管理员才能删除角色）
    await current_user.fetch_related("roles")
    is_admin = any(role.name in ["admin", "super_admin"] for role in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作")
    
    role = await Role.get_or_none(id=role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
    
    # 检查是否为系统角色
    if role.name in ["admin", "super_admin"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="系统角色不允许删除")
    
    # 检查是否有用户使用此角色
    users_count = await role.users.all().count()
    if users_count > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该角色正在被用户使用，无法删除")
    
    await role.delete()
    return success(message="角色删除成功")

@router.get("/roles/{role_id}/permissions", summary="获取角色权限")
async def get_role_permissions(
    role_id: int,
    current_user: User = Depends(get_current_user)
):
    """获取指定角色的权限列表"""
    # 检查权限
    await current_user.fetch_related("roles")
    is_admin = any(role.name in ["admin", "super_admin"] for role in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问")
    
    role = await Role.get_or_none(id=role_id).prefetch_related("permissions")
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
    
    permissions_data = []
    for perm in role.permissions:
        permissions_data.append({
            "id": perm.id,
            "name": perm.name,
            "code": perm.code,
            "description": perm.description
        })
    
    return success(permissions_data)

@router.put("/roles/{role_id}/permissions", summary="设置角色权限")
async def set_role_permissions(
    role_id: int,
    permission_data: dict,
    current_user: User = Depends(get_current_user)
):
    """设置角色的权限"""
    # 检查权限（只有管理员才能设置角色权限）
    await current_user.fetch_related("roles")
    is_admin = any(role.name in ["admin", "super_admin"] for role in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作")
    
    role = await Role.get_or_none(id=role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
    
    # 清除原有权限
    await role.permissions.clear()
    
    # 添加新权限
    permission_ids = permission_data.get("permission_ids", [])
    if permission_ids:
        permissions = await Permission.filter(id__in=permission_ids)
        await role.permissions.add(*permissions)
    
    return success(message="角色权限设置成功")

# ====== 用户角色权限管理API ======

@router.get("/users/{user_id}/roles", summary="获取用户角色")
async def get_user_roles(
    user_id: int,
    current_user: User = Depends(get_current_user)
):
    """获取指定用户的角色列表"""
    # 检查权限
    await current_user.fetch_related("roles")
    is_admin = any(role.name in ["admin", "super_admin"] for role in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问")
    
    user = await User.get_or_none(id=user_id).prefetch_related("roles")
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    
    roles_data = []
    for role in user.roles:
        roles_data.append({
            "id": role.id,
            "name": role.name,
            "description": role.description
        })
    
    return success(roles_data)

@router.post("/users/{user_id}/roles", summary="设置用户角色")
async def set_user_roles(
    user_id: int,
    role_data: dict,
    current_user: User = Depends(get_current_user)
):
    """设置用户的角色"""
    # 检查权限（只有管理员才能设置用户角色）
    await current_user.fetch_related("roles")
    is_admin = any(role.name in ["admin", "super_admin"] for role in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作")
    
    user = await User.get_or_none(id=user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    
    # 清除原有角色
    await user.roles.clear()
    
    # 添加新角色
    role_ids = role_data.get("role_ids", [])
    if role_ids:
        roles = await Role.filter(id__in=role_ids)
        await user.roles.add(*roles)
    
    return success(message="用户角色设置成功")

@router.get("/users/{user_id}/permissions", summary="获取用户权限")
async def get_user_permissions(
    user_id: int,
    current_user: User = Depends(get_current_user)
):
    """获取指定用户的直接权限列表（通过角色获得的权限）"""
    # 检查权限
    await current_user.fetch_related("roles")
    is_admin = any(role.name in ["admin", "super_admin"] for role in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问")
    
    user = await User.get_or_none(id=user_id).prefetch_related("roles", "roles__permissions")
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    
    # 收集用户通过角色获得的所有权限
    permissions_data = []
    permission_ids = set()
    
    for role in user.roles:
        for permission in role.permissions:
            if permission.id not in permission_ids:
                permission_ids.add(permission.id)
                permissions_data.append({
                    "id": permission.id,
                    "name": permission.name,
                    "code": permission.code,
                    "description": permission.description
                })
    
    return success(permissions_data)

@router.post("/users/{user_id}/permissions", summary="设置用户权限")
async def set_user_permissions(
    user_id: int,
    permission_data: dict,
    current_user: User = Depends(get_current_user)
):
    """设置用户的直接权限（注意：这里暂时返回成功，因为当前架构中用户权限通过角色管理）"""
    # 检查权限（只有管理员才能设置用户权限）
    await current_user.fetch_related("roles")
    is_admin = any(role.name in ["admin", "super_admin"] for role in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作")
    
    user = await User.get_or_none(id=user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    
    # 在当前架构中，用户权限通过角色管理，这里先返回成功
    # 如果需要用户直接权限，需要扩展数据模型
    return success(message="用户权限设置成功（通过角色管理）")

# ====== 权限检查装饰器 ======

def check_permission(permission_code: str):
    """权限检查装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 从kwargs中获取current_user
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未认证")
            
            # 获取用户权限
            await current_user.fetch_related("roles", "roles__permissions")
            user_permissions = []
            for role in current_user.roles:
                for perm in role.permissions:
                    user_permissions.append(perm.code)
            
            # 检查权限
            if permission_code not in user_permissions:
                # 检查是否为超级管理员（超级管理员拥有所有权限）
                is_super_admin = any(role.name == "super_admin" for role in current_user.roles)
                if not is_super_admin:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator 

@router.post("/logout", summary="用户退出登录")
async def logout(request: Request, current_user: User = Depends(get_current_user)):
    """用户退出登录，记录退出日志"""
    try:
        # 记录退出登录日志
        await record_login_log(
            request=request,
            username=current_user.username,
            status="success",
            login_message="退出登录",
            user=current_user
        )
        
        return success(message="退出登录成功")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"退出登录失败: {str(e)}") 