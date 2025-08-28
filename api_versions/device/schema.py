from pydantic import BaseModel
from tortoise.contrib.pydantic import pydantic_model_creator
from api_versions.v2.models import Device, App
from typing import List
from datetime import datetime


Device_Pydantic = pydantic_model_creator(Device, name="Device")
App_Pydantic = pydantic_model_creator(App, name="App")

class DeviceCreateSchema(BaseModel):
    name: str
    description: str
    is_active: bool = True


class DeviceUpdateSchema(BaseModel):
    name: str
    description: str
    is_active: bool = True



class AppCreateSchema(BaseModel):
    name: str
    description: str
    api_key: str


class AppUpdateSchema(BaseModel):
    name: str
    description: str
    api_key: str

class AppWithKeySchema(BaseModel):
    id: int
    name: str
    description: str
    api_key: str
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.strftime("%Y-%m-%d %H:%M:%S")
        }
class DeviceWithAppsSchema(Device_Pydantic):
    apps: List[AppWithKeySchema]
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.strftime("%Y-%m-%d %H:%M:%S")
        }