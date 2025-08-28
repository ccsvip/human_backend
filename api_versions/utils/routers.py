from fastapi import APIRouter
from core.services.utils import schema
from settings.config import settings
from utils import clean_cache_files

router = APIRouter()


@router.post("/chear", summary='清空全部缓存以及全部文件', description="必须要口令和密码均匹配才能成功执行")
async def clear_cache_files(data:schema.ClearCacheFilesSchema):
    password = data.password
    if password.lower().strip() == settings.admin_password.lower().strip():
        result = await clean_cache_files.clear_cache_files(text=data.order, password=data.password)
        return result if result != data.order.strip() else "未知异常"
    return "指令或密码不对"