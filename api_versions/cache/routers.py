from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from core.redis_client import redis_client
import os
import httpx
from utils import clean_cache_files
from settings.config import settings
from api_versions.logs.utils import record_operation_log
from api_versions.auth.routers import get_current_user

router = APIRouter()

# 1. 新增缓存（通过请求头转发到 /v2/llm-streaming）
class CacheCreateSchema(BaseModel):
    dify_api_key: str
    reference_id: str
    user_id: str
    text: str

@router.post("/create")
async def create_cache(request: Request, data: CacheCreateSchema):
    url = os.getenv("LLM_STREAMING_URL") or f"http://127.0.0.1:{settings.fastapi_port}/v2/llm-streaming"
    headers = {
        "dify_api_key": data.dify_api_key,
        "reference_id": data.reference_id,
        "user_id": data.user_id,
    }
    params = {"text": data.text}

    # 获取当前用户（如果已登录）
    try:
        current_user = await get_current_user(request)
        username = current_user.username
    except:
        username = "anonymous"

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params, timeout=20)
        if resp.status_code == 200:
            # Redis 可用性检查
            try:
                await redis_client.set("cache_ping", "1", ex=1)
            except Exception as redis_err:
                # 记录失败日志（Redis 不可用）
                await record_operation_log(
                    request=request,
                    username=username,
                    operation_type="CREATE",
                    operation_content="写缓存失败：Redis 不可用",
                    target_type="cache",
                    target_id=data.reference_id,
                    status="failed",
                    details={"error": str(redis_err)},
                )
                raise HTTPException(500, "写缓存失败：Redis 服务不可用")

            # 正常记录成功日志
            try:
                await record_operation_log(
                    request=request,
                    username=username,
                    operation_type="CREATE",
                    operation_content=f"创建缓存: {data.text[:10]}",
                    target_type="cache",
                    target_id=data.reference_id,
                    details={"text": data.text, "reference_id": data.reference_id, "user_id": data.user_id},
                )
            except Exception:
                pass
            return {"message": "缓存已写入"}
        else:
            await record_operation_log(
                    request=request,
                    username=data.user_id or "unknown",
                    operation_type="CREATE",
                    operation_content=f"创建缓存 reference_id:{data.reference_id}",
                    target_type="cache",
                    status="failed",
                    target_id=data.reference_id,
                    details={"dify_api_key": data.dify_api_key},
                )
            raise HTTPException(500, f"写入失败: {resp.text}")

# 2. 清空缓存和文件（转发到 /utils/chear）
class ClearCacheSchema(BaseModel):
    password: str = settings.admin_password
    order: str = settings.order

@router.post("/clear")
async def clear_cache(request: Request, body: ClearCacheSchema):
    # 校验口令和指令
    if body.password.strip() != settings.admin_password.strip() or body.order.strip() != settings.order.strip():
        return "指令或密码不对"

    # 调用内部工具函数执行清理
    result = await clean_cache_files.clear_cache_files(text=body.order, password=body.password)

    # 获取当前用户（如果已登录）
    try:
        current_user = await get_current_user(request)
        username = current_user.username
    except:
        username = "anonymous"

    # 记录操作日志
    try:
        await record_operation_log(
            request=request,
            username=username, 
            operation_type="DELETE",
            operation_content="清空缓存",
            target_type="cache",
            target_id="*",
            details={"order": body.order},
        )
    except Exception:
        await record_operation_log(
            request=request,
            username=username, 
            operation_type="DELETE",
            operation_content="清空缓存",
            target_type="cache",
            target_id="*",
            details={"order": body.order},
        )
    return result

# 3. 显示全部缓存信息
@router.get("/list")
async def list_cache():
    keys = await redis_client.keys("*")
    result = []
    for k in keys:
        try:
            v = await redis_client.get(k)
            ttl = await redis_client.ttl(k)
            val = v.decode('utf-8') if v else ''
            vlen = len(val)
        except Exception:
            ttl = -2
            val = ''
            vlen = 0
        result.append({
            "key": k.decode() if isinstance(k, bytes) else k,
            "value": val,
            "value_len": vlen,
            "ttl": ttl
        })
    return result

@router.get("/detail")
async def cache_detail(key: str):
    """返回指定缓存键的详细信息，包括类型、ttl、长度和值/列表"""
    if not key:
        raise HTTPException(400, "请提供 key 查询参数")

    # 获取类型与 ttl
    r_type = await redis_client.type(key)
    ttl = await redis_client.ttl(key)

    result = {"key": key, "type": r_type, "ttl": ttl}

    # 根据不同类型获取值
    try:
        if r_type == "string":
            val = await redis_client.get(key)
            result["length"] = len(val) if val else 0
            result["value"] = val
        elif r_type == "list":
            items = await redis_client.lrange(key, 0, -1)
            result["length"] = len(items)
            result["items"] = items
        elif r_type == "hash":
            h = await redis_client.hgetall(key)
            result["length"] = len(h)
            result["items"] = h
        elif r_type == "set":
            s = await redis_client.smembers(key)
            s = list(s)
            result["length"] = len(s)
            result["items"] = s
        elif r_type == "zset":
            z = await redis_client.zrange(key, 0, -1, withscores=True)
            result["length"] = len(z)
            result["items"] = z
        else:
            # 可能已经过期或者是其他未知类型
            result["length"] = 0
            result["value"] = None
    except Exception as e:
        raise HTTPException(500, f"读取缓存失败: {e}")

    return result 