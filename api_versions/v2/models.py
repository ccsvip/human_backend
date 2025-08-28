from tortoise import fields, models

class App(models.Model):
    """
    独立的应用实体
    - name: 应用名称（唯一）
    - description: 应用描述
    """
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255, unique=True)
    description = fields.CharField(max_length=255)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    api_key = fields.CharField(max_length=255, unique=True)

    class Meta:
        table = "app"
        table_description = "应用主表"

class Device(models.Model):
    """
    设备实体
    - name: 设备名称（唯一）
    - apps: 多对多关联到应用（通过DeviceApp中间表）
    """
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255, unique=True)
    description = fields.CharField(max_length=255)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    is_active = fields.BooleanField(default=True)

    # 多对多关系定义
    apps = fields.ManyToManyField(
        "models.App",
        through="device_app",
        related_name="devices",
        forward_key="app_id",
        backward_key="device_id",
        through_relation_name="device",  # 新增关键配置
        through_reverse_relation_name="app"  # 新增关键配置
    )

    class Meta:
        table = "device"
        table_description = "设备表"

class DeviceApp(models.Model):
    """
    设备与应用关联表（中间表）
    - 包含关系专属字段：api_key
    """
    id = fields.IntField(pk=True)
    device = fields.ForeignKeyField(
        "models.Device", 
        related_name="device_apps",
        on_delete=fields.CASCADE
    )
    app = fields.ForeignKeyField(
        "models.App",
        related_name="app_devices",
        on_delete=fields.CASCADE
    )

    class Meta:
        table = "device_app"
        table_description = "设备应用关联表"
        unique_together = (("device", "app"),)  # 确保唯一关联

class MediaFile(models.Model):
    """
    媒体文件表（图片 / 视频）
    - name: 原始文件名或用户定义名称
    - file_path: 保存的相对路径，例如 static/img/xxxx.jpg
    - description: 描述信息，可为空
    - media_type: image | video
    - orientation: 媒体方向，horizontal/vertical，可为空
    - is_show: 是否展示
    - is_delete: 是否删除（软删除）
    """
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    file_path = fields.CharField(max_length=512)
    # 通过文件哈希值保证唯一性，避免重复记录
    file_hash = fields.CharField(max_length=64, unique=True, null=True)
    description = fields.CharField(max_length=255, null=True)
    media_type = fields.CharField(max_length=10)
    orientation = fields.CharField(max_length=20, null=True, description="媒体方向：horizontal/vertical")
    is_show = fields.BooleanField(default=True)
    is_delete = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "media_file"
        table_description = "媒体文件表 (图片 / 视频)"

class Permission(models.Model):
    """
    权限表
    - name: 权限名称 (展示用)
    - code: 权限编码 (唯一, 用于代码中判断)
    """
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=64)
    code = fields.CharField(max_length=64, unique=True)
    description = fields.CharField(max_length=255, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "permission"
        table_description = "权限表"

class Role(models.Model):
    """
    角色表
    - name: 角色名称 (唯一)
    - permissions: 多对多权限
    """
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=64, unique=True)
    description = fields.CharField(max_length=255, null=True)
    permissions: fields.ManyToManyRelation[Permission] = fields.ManyToManyField(
        "models.Permission",
        related_name="roles",
        through="role_permission",
    )
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "role"
        table_description = "角色表"

class User(models.Model):
    """
    用户表
    - username: 用户名 (唯一)
    - password_hash: 密码哈希 (加密存储)
    - avatar: 头像路径
    - email: 邮箱
    - phone: 手机号
    - gender: 性别 (male/female/unknown)
    - department: 所属部门
    - roles: 多对多角色
    """
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=64, unique=True)
    password_hash = fields.CharField(max_length=128)
    avatar = fields.CharField(max_length=255, null=True, default="static/avatar/default.jpg", description="头像路径")
    email = fields.CharField(max_length=100, null=True, description="邮箱")
    phone = fields.CharField(max_length=20, null=True, description="手机号")
    gender = fields.CharField(max_length=10, default="unknown", description="性别: male/female/unknown")
    department = fields.CharField(max_length=100, null=True, description="所属部门")
    roles: fields.ManyToManyRelation[Role] = fields.ManyToManyField(
        "models.Role",
        related_name="users",
        through="user_role",
    )
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "user"
        table_description = "用户表"

    @staticmethod
    def hash_password(raw_password: str) -> str:
        import hashlib, os
        # 使用盐值进行简单加密(sha256)
        salt = os.getenv("PASSWORD_SALT", "human_api_salt")
        return hashlib.sha256(f"{salt}{raw_password}".encode()).hexdigest()

    def verify_password(self, raw_password: str) -> bool:
        return self.password_hash == self.hash_password(raw_password)
    
    def get_img_url(self, request) -> str:
        """
        返回完整的头像URL，使用FastAPI的url_for
        """
        if not self.avatar:
            # 默认头像
            return str(request.url_for("audio_files", path="avatar/default.jpg"))
        else:
            # 如果已经是完整URL，直接返回
            if self.avatar.startswith(('http://', 'https://')):
                return self.avatar
            
            # 去掉可能的static/前缀，因为url_for会自动加上
            avatar_path = self.avatar
            if avatar_path.startswith('static/'):
                avatar_path = avatar_path[7:]  # 去掉 'static/' 前缀
            elif avatar_path.startswith('/static/'):
                avatar_path = avatar_path[8:]  # 去掉 '/static/' 前缀
            
            return str(request.url_for("audio_files", path=avatar_path))

class PathPermission(models.Model):
    """
    路径权限表
    - path: 路径 (如 /system/env)
    - name: 权限名称
    - description: 权限描述
    - type: 权限类型 (user: 用户权限, role: 角色权限)
    - target_id: 目标ID (用户ID或角色ID)
    - is_active: 是否启用
    """
    id = fields.IntField(pk=True)
    path = fields.CharField(max_length=255, description="路径")
    name = fields.CharField(max_length=64, description="权限名称")
    description = fields.CharField(max_length=255, null=True, description="权限描述")
    type = fields.CharField(max_length=10, description="权限类型: user/role")
    target_id = fields.IntField(description="目标ID (用户ID或角色ID)")
    is_active = fields.BooleanField(default=True, description="是否启用")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "path_permission"
        table_description = "路径权限表"
        unique_together = (("path", "type", "target_id"),)  # 确保同一目标对同一路径的权限唯一

    @property
    def target_name(self):
        """获取目标名称（用户名或角色名）"""
        # 这个属性需要在API中通过JOIN查询来填充
        return getattr(self, '_target_name', None)

class ModelItem(models.Model):
    """
    模型信息表
    - name: 模型名称（唯一）
    - description: 模型描述
    - category: 模型类别 (male/female/other)
    - orientation: 模型方向 (horizontal/vertical)，可为空
    - local_path: 本地模型路径，自动生成（backend/static/models/下）
    - url: 云端模型URL，可为空
    - thumbnail: 模型缩略图路径
    - file_size: 模型文件大小（字节），上传时自动计算或手动填写
    - is_show: 是否显示
    """
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255, unique=True)
    description = fields.CharField(max_length=255, null=True)
    category = fields.CharField(max_length=10, description="模型类别: male/female/other")
    orientation = fields.CharField(max_length=20, null=True, description="模型方向: horizontal/vertical")
    local_path = fields.CharField(max_length=512, null=True, description="本地模型路径（自动生成）")
    url = fields.CharField(max_length=512, null=True, description="云端模型URL")
    thumbnail = fields.CharField(max_length=512, null=True, description="模型缩略图路径")
    file_size = fields.BigIntField(null=True, description="模型文件大小（字节）")
    is_show = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "model_item"
        table_description = "模型信息表"
        
    def get_file_size_formatted(self) -> str:
        """
        返回格式化的文件大小字符串
        """
        if not self.file_size:
            return "未知"
        
        size = self.file_size
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f}KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f}MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f}GB"

    def get_thumbnail_url(self, request) -> str:
        """
        返回完整的缩略图URL
        """
        if not self.thumbnail:
            # 默认缩略图（根据类别）
            default_thumbnails = {
                'male': 'models/thumbnails/default_male.jpg',
                'female': 'models/thumbnails/default_female.jpg',
                'other': 'models/thumbnails/default_other.jpg'
            }
            thumbnail_path = default_thumbnails.get(self.category, 'models/thumbnails/default.jpg')
            return str(request.url_for("audio_files", path=thumbnail_path))
        else:
            # 如果已经是完整URL，直接返回
            if self.thumbnail.startswith(('http://', 'https://')):
                return self.thumbnail
            
            # 处理相对路径
            thumbnail_path = self.thumbnail
            if thumbnail_path.startswith('static/'):
                thumbnail_path = thumbnail_path[7:]  # 去掉 'static/' 前缀
            elif thumbnail_path.startswith('/static/'):
                thumbnail_path = thumbnail_path[8:]  # 去掉 '/static/' 前缀
            
            return str(request.url_for("audio_files", path=thumbnail_path))


class LoginLog(models.Model):
    """
    登录日志表
    - username: 登录用户名
    - ip_address: IP地址
    - login_location: 登录地址
    - status: 操作状态 (success/failed)
    - device_name: 设备名称
    - browser: 浏览器
    - os: 操作系统
    - login_message: 登录信息
    - login_time: 登录时间
    - is_admin: 是否管理员
    """
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=64, description="登录用户名")
    ip_address = fields.CharField(max_length=45, description="IP地址")
    login_location = fields.CharField(max_length=255, null=True, description="登录地址")
    status = fields.CharField(max_length=20, description="操作状态")  # success/failed
    device_name = fields.CharField(max_length=255, null=True, description="设备名称")
    browser = fields.CharField(max_length=255, null=True, description="浏览器")
    os = fields.CharField(max_length=255, null=True, description="操作系统")
    login_message = fields.CharField(max_length=500, null=True, description="登录信息")
    login_time = fields.DatetimeField(auto_now_add=True, description="登录时间")
    is_admin = fields.BooleanField(default=False, description="是否管理员")

    class Meta:
        table = "login_log"
        table_description = "登录日志表"


class OperationLog(models.Model):
    """
    操作日志表
    - username: 操作用户名
    - operation_type: 操作类型 (CREATE/UPDATE/DELETE)
    - operation_content: 操作内容
    - target_type: 目标类型 (user/device/app/model等)
    - target_id: 目标ID
    - ip_address: IP地址
    - status: 操作状态 (success/failed)
    - details: 详细信息 (JSON格式)
    - operation_time: 操作时间
    - is_admin: 是否管理员
    """
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=64, description="操作用户名")
    operation_type = fields.CharField(max_length=20, description="操作类型")  # CREATE/UPDATE/DELETE/READ/LOGIN/LOGOUT
    operation_content = fields.CharField(max_length=500, description="操作内容")
    target_type = fields.CharField(max_length=50, null=True, description="目标类型")
    target_id = fields.CharField(max_length=50, null=True, description="目标ID")
    ip_address = fields.CharField(max_length=45, description="IP地址")
    status = fields.CharField(max_length=20, description="操作状态")  # success/failed
    details = fields.JSONField(null=True, description="详细信息")
    operation_time = fields.DatetimeField(auto_now_add=True, description="操作时间")
    is_admin = fields.BooleanField(default=False, description="是否管理员")

    class Meta:
        table = "operation_log"
        table_description = "操作日志表"

class SiteConfig(models.Model):
    """
    站点配置表（全局仅保存一条记录）
    - title: 网站标题
    - logo_path: Logo 静态文件相对路径 (相对于 static 目录)
    - favicon_path: Favicon 图标静态文件相对路径
    """
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=255, null=True)
    logo_path = fields.CharField(max_length=512, null=True)
    favicon_path = fields.CharField(max_length=512, null=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "site_config"
        table_description = "站点配置表"

class AudioData(models.Model):
    """
    音频数据管理表
    - user_question: 用户问题
    - ai_response_text: 大模型回复文本
    - audio_file_path: 大模型回复音频路径地址
    - tts_started_at: TTS开始时间
    - tts_completed_at: TTS完成时间
    - created_at: 新增日期
    - updated_at: 更新日期
    """
    id = fields.IntField(pk=True)
    user_question = fields.TextField(description="用户问题")
    ai_response_text = fields.TextField(description="大模型回复文本")
    audio_file_path = fields.CharField(max_length=512, description="音频文件路径")
    tts_started_at = fields.DatetimeField(null=True, description="TTS开始时间")
    tts_completed_at = fields.DatetimeField(description="TTS完成时间")
    created_at = fields.DatetimeField(auto_now_add=True, description="新增日期")
    updated_at = fields.DatetimeField(auto_now=True, description="更新日期")

    class Meta:
        table = "audio_data"
        table_description = "音频数据管理表"

class Logo(models.Model):
    """
    Logo管理表
    - name: 图标名称
    - file_path: 图标文件路径
    - description: 描述信息
    - update_log: 更新日志
    - is_active: 是否启用
    """
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255, description="图标名称")
    file_path = fields.CharField(max_length=512, description="图标文件路径")
    description = fields.CharField(max_length=500, null=True, description="描述信息")
    update_log = fields.TextField(null=True, description="更新日志")
    is_active = fields.BooleanField(default=True, description="是否启用")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建日期")
    updated_at = fields.DatetimeField(auto_now=True, description="更新日期")

    class Meta:
        table = "logo"
        table_description = "Logo管理表"

    def get_logo_url(self, request) -> str:
        """返回完整的Logo URL"""
        if not self.file_path:
            return ""
        
        # 处理相对路径
        logo_path = self.file_path
        if logo_path.startswith('static/'):
            logo_path = logo_path[7:]
        elif logo_path.startswith('/static/'):
            logo_path = logo_path[8:]
        
        return str(request.url_for("audio_files", path=logo_path))