"""
RBAC权限系统数据初始化脚本
用于创建基础的权限、角色和用户数据
"""

from api_versions.v2.models import User, Role, Permission
from core.logger import logger
from tortoise import Tortoise

# 基础权限定义
PERMISSIONS = [
    # 用户管理权限
    {"name": "查看用户", "code": "user:view", "description": "查看用户列表和详情"},
    {"name": "创建用户", "code": "user:create", "description": "创建新用户"},
    {"name": "编辑用户", "code": "user:edit", "description": "编辑用户信息"},
    {"name": "删除用户", "code": "user:delete", "description": "删除用户"},
    {"name": "重置密码", "code": "user:reset_password", "description": "重置用户密码"},
    
    # 角色管理权限
    {"name": "查看角色", "code": "role:view", "description": "查看角色列表和详情"},
    {"name": "创建角色", "code": "role:create", "description": "创建新角色"},
    {"name": "编辑角色", "code": "role:edit", "description": "编辑角色信息"},
    {"name": "删除角色", "code": "role:delete", "description": "删除角色"},
    {"name": "分配权限", "code": "role:assign_permission", "description": "为角色分配权限"},
    
    # 权限管理权限
    {"name": "查看权限", "code": "permission:view", "description": "查看权限列表"},
    {"name": "创建权限", "code": "permission:create", "description": "创建新权限"},
    {"name": "编辑权限", "code": "permission:edit", "description": "编辑权限信息"},
    {"name": "删除权限", "code": "permission:delete", "description": "删除权限"},
    
    # 系统管理权限
    {"name": "环境变量管理", "code": "system:env", "description": "管理系统环境变量"},
    {"name": "设备管理", "code": "system:device", "description": "管理设备信息"},
    {"name": "应用管理", "code": "system:app", "description": "管理应用信息"},
    
    # 媒体管理权限
    {"name": "查看媒体", "code": "media:view", "description": "查看媒体文件"},
    {"name": "上传媒体", "code": "media:upload", "description": "上传媒体文件"},
    {"name": "删除媒体", "code": "media:delete", "description": "删除媒体文件"},
    
    # 缓存管理权限
    {"name": "查看缓存", "code": "cache:view", "description": "查看缓存信息"},
    {"name": "创建缓存", "code": "cache:create", "description": "创建缓存"},
    {"name": "清理缓存", "code": "cache:clear", "description": "清理缓存"},
    
    # 模型管理权限
    {"name": "查看模型", "code": "model:view", "description": "查看模型列表和详情"},
    {"name": "创建模型", "code": "model:create", "description": "创建新模型"},
    {"name": "编辑模型", "code": "model:edit", "description": "编辑模型信息"},
    {"name": "删除模型", "code": "model:delete", "description": "删除模型"},
    
    # 唤醒词管理权限
    {"name": "查看唤醒词", "code": "wakeword:view", "description": "查看唤醒词列表和详情"},
    {"name": "创建唤醒词", "code": "wakeword:create", "description": "创建新唤醒词"},
    {"name": "编辑唤醒词", "code": "wakeword:edit", "description": "编辑唤醒词信息"},
    {"name": "删除唤醒词", "code": "wakeword:delete", "description": "删除唤醒词"},
    
    # 日志管理权限
    {"name": "查看登录日志", "code": "logs:login:view", "description": "查看登录日志"},
    {"name": "删除登录日志", "code": "logs:login:delete", "description": "删除登录日志"},
    {"name": "查看操作日志", "code": "logs:operation:view", "description": "查看操作日志"},
    {"name": "删除操作日志", "code": "logs:operation:delete", "description": "删除操作日志"},

    # 个人中心权限
    {"name": "查看个人资料", "code": "profile:view", "description": "查看个人资料"},
    {"name": "编辑个人资料", "code": "profile:edit", "description": "编辑个人资料"},
]

# 角色定义
ROLES = [
    {
        "name": "super_admin",
        "description": "超级管理员",
        "permissions": "all"  # 拥有所有权限
    },
    {
        "name": "admin", 
        "description": "管理员",
        "permissions": [
            "user:view", "user:create", "user:edit", "user:delete", "user:reset_password",
            "role:view", "role:create", "role:edit", "role:delete", "role:assign_permission",
            "permission:view",
            "system:env", "system:device", "system:app",
            "media:view", "media:upload", "media:delete",
            "cache:view", "cache:create", "cache:clear",
            "model:view", "model:create", "model:edit", "model:delete",
            "wakeword:view", "wakeword:create", "wakeword:edit", "wakeword:delete",
            "logs:login:view", "logs:login:delete", "logs:operation:view", "logs:operation:delete",
            "profile:view", "profile:edit"
        ]
    },
    {
        "name": "operator",
        "description": "操作员", 
        "permissions": [
            "system:device", "system:app",
            "media:view", "media:upload",
            "cache:view", "cache:create",
            "model:view",
            "wakeword:view", "wakeword:create", "wakeword:edit",
            "profile:view", "profile:edit"
        ]
    },

]

# --- 新增: MySQL 全局锁工具函数，防止多进程并发初始化 ---
async def _acquire_db_lock(lock_name: str, timeout: int = 30) -> bool:
    """尝试获取 MySQL GET_LOCK，全局互斥，成功返回 True。

    在非 MySQL 数据库或不支持 GET_LOCK 的环境下，返回 True 直接继续。
    """
    try:
        conn = Tortoise.get_connection("default")
        result = await conn.execute_query("SELECT GET_LOCK(%s, %s) AS got_lock", [lock_name, timeout])
        return result[1][0].get("got_lock") == 1
    except Exception:
        # 其它数据库（如 SQLite）或指令不被支持时，直接返回 True
        return True
# --- 新增结束 ---

async def init_permissions():
    """初始化权限数据"""
    logger.info("开始初始化权限数据...")
    
    created_count = 0
    for perm_data in PERMISSIONS:
        permission, created = await Permission.get_or_create(
            code=perm_data["code"],
            defaults={
                "name": perm_data["name"],
                "description": perm_data["description"]
            }
        )
        if created:
            created_count += 1
            logger.info(f"创建权限: {permission.name} ({permission.code})")
    
    logger.info(f"权限初始化完成，新创建 {created_count} 个权限")
    return created_count

async def init_roles():
    """初始化角色数据"""
    logger.info("开始初始化角色数据...")
    
    created_count = 0
    for role_data in ROLES:
        role, created = await Role.get_or_create(
            name=role_data["name"],
            defaults={"description": role_data["description"]}
        )
        
        if created:
            created_count += 1
            logger.info(f"创建角色: {role.name}")
        
        # 分配权限
        if role_data["permissions"] == "all":
            # 超级管理员拥有所有权限
            all_permissions = await Permission.all()
            await role.permissions.clear()
            await role.permissions.add(*all_permissions)
            logger.info(f"为角色 {role.name} 分配所有权限")
        else:
            # 分配指定权限
            permissions = await Permission.filter(code__in=role_data["permissions"])
            await role.permissions.clear()
            await role.permissions.add(*permissions)
            logger.info(f"为角色 {role.name} 分配 {len(permissions)} 个权限")
    
    logger.info(f"角色初始化完成，新创建 {created_count} 个角色")
    return created_count

async def upgrade_existing_admin():
    """升级现有的admin用户为super_admin"""
    logger.info("开始升级现有管理员...")
    
    # 查找所有admin角色的用户
    admin_role = await Role.get_or_none(name="admin")
    super_admin_role = await Role.get_or_none(name="super_admin")
    
    if not admin_role or not super_admin_role:
        logger.warning("未找到admin或super_admin角色，跳过用户升级")
        return 0
    
    admin_users = await admin_role.users.all()
    upgraded_count = 0
    
    for user in admin_users:
        # 检查是否已经是super_admin
        user_roles = await user.roles.all()
        is_super_admin = any(role.name == "super_admin" for role in user_roles)
        
        if not is_super_admin:
            await user.roles.add(super_admin_role)
            upgraded_count += 1
            logger.info(f"用户 {user.username} 已升级为超级管理员")
    
    logger.info(f"管理员升级完成，升级 {upgraded_count} 个用户")
    return upgraded_count

async def init_rbac_data():
    """初始化RBAC数据"""
    logger.info("🚀 开始初始化RBAC权限系统数据...")
    
    try:
        # --- 新增: 进程互斥，避免并发初始化 ---
        lock_acquired = await _acquire_db_lock("init_rbac_data", 0)
        if not lock_acquired:
            logger.info("检测到其他进程正在执行 RBAC 初始化，当前进程跳过")
            return True  # 视为成功，避免阻塞启动
        # --- 新增结束 ---

        # 1. 初始化权限
        perm_count = await init_permissions()
        
        # 2. 初始化角色
        role_count = await init_roles()
        
        # 3. 升级现有管理员
        upgraded_count = await upgrade_existing_admin()
        
        logger.info(f"✅ RBAC数据初始化完成!")
        logger.info(f"   - 新建权限: {perm_count}")
        logger.info(f"   - 新建角色: {role_count}")
        logger.info(f"   - 升级用户: {upgraded_count}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ RBAC数据初始化失败: {str(e)}")
        return False

if __name__ == "__main__":
    import asyncio
    from settings.tortoise_config import TORTOISE_ORM
    
    async def main():
        await Tortoise.init(config=TORTOISE_ORM)
        await init_rbac_data()
        await Tortoise.close_connections()
    
    asyncio.run(main()) 