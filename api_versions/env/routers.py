from fastapi import APIRouter, HTTPException, status
from .schema import EnvVar, EnvVarCreate, EnvVarUpdate
from pathlib import Path
from typing import List
import os
from settings import config as settings_config

router = APIRouter()

ENV_PATH = Path(__file__).parent.parent.parent / ".env"

SECRET_KEYS = []  # 可根据实际情况调整

def read_env() -> List[EnvVar]:
    if not ENV_PATH.exists():
        return []
    env_vars = []
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            is_secret = any(s in key.upper() for s in SECRET_KEYS)
            env_vars.append(EnvVar(key=key, value=value, is_secret=is_secret))
    return env_vars

def write_env(env_vars: List[EnvVar]):
    # 将列表转换为 dict 方便查找
    env_map = {v.key: v.value for v in env_vars}

    new_lines = []
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("#") or "=" not in line:
                    new_lines.append(line)  # 保留原注释/空行
                    continue
                key, _ = line.split("=", 1)
                key = key.strip()
                if key in env_map:
                    new_lines.append(f"{key}={env_map.pop(key)}\n")  # 替换为新值
                # 若 key 已被删除，则跳过写入

    # 追加新增键
    for k, v in env_map.items():
        new_lines.append(f"{k}={v}\n")

    # 写回文件，保持原注释顺序
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    # 热加载设置：更新原对象属性，确保全局引用一致
    new_settings = settings_config.Settings()
    for k, v in new_settings.model_dump().items():
        setattr(settings_config.settings, k, v)

@router.get("/env", response_model=List[EnvVar], tags=["env"], summary="获取所有环境变量")
async def list_env():
    return read_env()

@router.post("/env", response_model=EnvVar, tags=["env"], summary="新增环境变量")
async def create_env(var: EnvVarCreate):
    env_vars = read_env()
    if any(v.key == var.key for v in env_vars):
        raise HTTPException(status_code=400, detail="变量已存在")
    env_vars.append(EnvVar(**var.dict()))
    write_env(env_vars)
    return EnvVar(**var.dict())

@router.put("/env/{key}", response_model=EnvVar, tags=["env"], summary="更新环境变量")
async def update_env(key: str, var: EnvVarUpdate):
    env_vars = read_env()
    found = False
    for v in env_vars:
        if v.key == key:
            v.value = var.value
            v.is_secret = var.is_secret
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="变量不存在")
    write_env(env_vars)
    return EnvVar(key=key, value=var.value, is_secret=var.is_secret)

@router.delete("/env/{key}", tags=["env"], summary="删除环境变量")
async def delete_env(key: str):
    env_vars = read_env()
    new_vars = [v for v in env_vars if v.key != key]
    if len(new_vars) == len(env_vars):
        raise HTTPException(status_code=404, detail="变量不存在")
    write_env(new_vars)
    return {"detail": "变量已删除"} 