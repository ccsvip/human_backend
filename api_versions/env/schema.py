from pydantic import BaseModel
from typing import Optional

class EnvVar(BaseModel):
    key: str
    value: str
    is_secret: Optional[bool] = False  # 是否为敏感字段

class EnvVarCreate(BaseModel):
    key: str
    value: str
    is_secret: Optional[bool] = False

class EnvVarUpdate(BaseModel):
    value: str
    is_secret: Optional[bool] = False 