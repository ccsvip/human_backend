from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime

class InitUserSchema(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")

    @field_validator('username')
    @classmethod
    def username_length(cls, v: str):
        if len(v) < 3:
            raise ValueError('用户名长度必须不少于3位')
        return v

    @field_validator('password')
    @classmethod
    def password_length(cls, v: str):
        if len(v) < 6:
            raise ValueError('密码长度必须不少于6位')
        return v

class LoginSchema(BaseModel):
    username: str
    password: str

    @field_validator('username')
    @classmethod
    def login_username_length(cls, v):
        if len(v) < 3:
            raise ValueError('用户名长度必须不少于3位')
        return v

    @field_validator('password')
    @classmethod
    def login_password_length(cls, v):
        if len(v) < 6:
            raise ValueError('密码长度必须不少于6位')
        return v

class LoginResultSchema(BaseModel):
    token: str 

class RoleSchema(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str] = None

class UserProfileSchema(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: str = "unknown"
    department: Optional[str] = None
    avatar: Optional[str] = None
    img_url: str  # 完整的头像URL
    roles: List[RoleSchema] = []
    created_at: datetime
    updated_at: datetime

class UpdateProfileSchema(BaseModel):
    email: Optional[str] = Field(None, description="邮箱")
    phone: Optional[str] = Field(None, description="手机号")
    gender: Optional[str] = Field("unknown", description="性别")
    department: Optional[str] = Field(None, description="所属部门")

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str):
        if v and '@' not in v:
            raise ValueError('邮箱格式不正确')
        return v

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str):
        if v and (len(v) != 11 or not v.startswith('1')):
            raise ValueError('手机号格式不正确')
        return v

    @field_validator('gender')
    @classmethod
    def validate_gender(cls, v: str):
        if v not in ['male', 'female', 'unknown']:
            raise ValueError('性别只能是 male、female 或 unknown')
        return v

class ChangePasswordSchema(BaseModel):
    current_password: str = Field(..., description="当前密码")
    new_password: str = Field(..., description="新密码")

    @field_validator('new_password')
    @classmethod
    def password_length(cls, v: str):
        if len(v) < 6:
            raise ValueError('新密码长度必须不少于6位')
        return v

class UpdateAvatarSchema(BaseModel):
    avatar: str = Field(..., description="头像路径")

# 用户管理相关Schema
class CreateUserSchema(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
    email: Optional[str] = Field(None, description="邮箱")
    phone: Optional[str] = Field(None, description="手机号")
    gender: str = Field("unknown", description="性别")
    department: Optional[str] = Field(None, description="所属部门")
    role_ids: List[int] = Field([], description="角色ID列表")
    is_active: bool = Field(True, description="是否激活")

    @field_validator('username')
    @classmethod
    def username_length(cls, v: str):
        if len(v) < 3:
            raise ValueError('用户名长度必须不少于3位')
        return v

    @field_validator('password')
    @classmethod
    def password_length(cls, v: str):
        if len(v) < 6:
            raise ValueError('密码长度必须不少于6位')
        return v

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str):
        if v and '@' not in v:
            raise ValueError('邮箱格式不正确')
        return v

class UpdateUserSchema(BaseModel):
    email: Optional[str] = Field(None, description="邮箱")
    phone: Optional[str] = Field(None, description="手机号")
    gender: Optional[str] = Field(None, description="性别")
    department: Optional[str] = Field(None, description="所属部门")
    role_ids: Optional[List[int]] = Field(None, description="角色ID列表")
    is_active: Optional[bool] = Field(None, description="是否激活")

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str):
        if v and '@' not in v:
            raise ValueError('邮箱格式不正确')
        return v

class UserListResponseSchema(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: str = "unknown"
    department: Optional[str] = None
    avatar: Optional[str] = None
    img_url: str  # 完整的头像URL
    roles: List[RoleSchema] = []
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime
    updated_at: datetime

class UserListQuerySchema(BaseModel):
    page: int = Field(1, ge=1, description="页码")
    size: int = Field(10, ge=1, le=100, description="每页数量")
    search: Optional[str] = Field(None, description="搜索关键词")

class ResetPasswordSchema(BaseModel):
    new_password: str = Field(..., description="新密码")

    @field_validator('new_password')
    @classmethod
    def password_length(cls, v: str):
        if len(v) < 6:
            raise ValueError('新密码长度必须不少于6位')
        return v

# 路径权限相关Schema
class CreatePathPermissionSchema(BaseModel):
    path: str = Field(..., description="路径")
    name: str = Field(..., description="权限名称")
    description: Optional[str] = Field(None, description="权限描述")
    type: str = Field(..., description="权限类型: user/role")
    target_id: int = Field(..., description="目标ID (用户ID或角色ID)")
    is_active: bool = Field(True, description="是否启用")

    @field_validator('path')
    @classmethod
    def validate_path(cls, v: str):
        if not v.startswith('/'):
            raise ValueError('路径必须以/开头')
        return v

    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str):
        if v not in ['user', 'role']:
            raise ValueError('权限类型只能是 user 或 role')
        return v

class UpdatePathPermissionSchema(BaseModel):
    path: Optional[str] = Field(None, description="路径")
    name: Optional[str] = Field(None, description="权限名称")
    description: Optional[str] = Field(None, description="权限描述")
    type: Optional[str] = Field(None, description="权限类型: user/role")
    target_id: Optional[int] = Field(None, description="目标ID (用户ID或角色ID)")
    is_active: Optional[bool] = Field(None, description="是否启用")

    @field_validator('path')
    @classmethod
    def validate_path(cls, v: str):
        if v and not v.startswith('/'):
            raise ValueError('路径必须以/开头')
        return v

    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str):
        if v and v not in ['user', 'role']:
            raise ValueError('权限类型只能是 user 或 role')
        return v

class PathPermissionResponseSchema(BaseModel):
    id: int
    path: str
    name: str
    description: Optional[str] = None
    type: str
    target_id: int
    target_name: Optional[str] = None  # 目标名称（用户名或角色名）
    is_active: bool
    created_at: datetime
    updated_at: datetime