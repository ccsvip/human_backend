from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from tortoise.contrib.pydantic import pydantic_model_creator
from ..v2.models import Logo

class LogoCreateSchema(BaseModel):
    """创建Logo的Schema"""
    name: str
    description: Optional[str] = None
    update_log: Optional[str] = None
    is_active: bool = True

class LogoUpdateSchema(BaseModel):
    """更新Logo的Schema"""
    name: Optional[str] = None
    description: Optional[str] = None
    update_log: Optional[str] = None
    is_active: Optional[bool] = None

# 使用Tortoise的pydantic_model_creator生成Schema
LogoOutSchema = pydantic_model_creator(Logo, name="LogoOut")

class LogoOutWithURLSchema(BaseModel):
    """带URL的Logo输出Schema"""
    id: int
    name: str
    file_path: str
    description: Optional[str]
    update_log: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    url: str

    class Config:
        from_attributes = True