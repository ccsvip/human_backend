from fastapi import APIRouter, HTTPException, Request, Depends, Query
from typing import Optional
from datetime import datetime, timezone, timedelta
from tortoise.queryset import Q
from api_versions.v2.models import AudioData, User
from api_versions.auth.routers import get_current_user
from api_versions.logs.utils import record_operation_log
from pydantic import BaseModel
from settings.config import GREETING_LIST
from core.logger import logger

router = APIRouter()

# 中国时区 UTC+8
CHINA_TZ = timezone(timedelta(hours=8))

def convert_to_china_timezone(dt: datetime) -> datetime:
    """转换时区到中国时间"""
    if dt is None:
        return None
    
    # 如果已经有时区信息，直接转换
    if dt.tzinfo is not None:
        china_dt = dt.astimezone(CHINA_TZ)
        # 返回不带时区信息的本地时间（因为前端期望的是本地时间）
        return china_dt.replace(tzinfo=None)
    
    # 如果没有时区信息，假设是UTC时间，先加上UTC时区信息再转换
    utc_dt = dt.replace(tzinfo=timezone.utc)
    china_dt = utc_dt.astimezone(CHINA_TZ)
    
    # 返回不带时区信息的本地时间（因为前端期望的是本地时间）
    return china_dt.replace(tzinfo=None)

class AudioDataSchema(BaseModel):
    id: int
    user_question: str
    ai_response_text: str
    audio_file_path: str
    tts_completed_at: datetime
    created_at: datetime
    updated_at: datetime
    audio_url: Optional[str] = None
    tts_duration: Optional[float] = None

    class Config:
        from_attributes = True

class AudioDataCreateSchema(BaseModel):
    user_question: str
    ai_response_text: str
    audio_file_path: str
    tts_started_at: Optional[datetime] = None
    tts_completed_at: datetime

def success(data=None, message="success"):
    return {"code": 200, "message": message, "data": data}


@router.get("/list", summary="获取音频数据列表")
async def get_audio_data_list(
    request: Request,
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页数量"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    current_user: User = Depends(get_current_user)
):
    """获取音频数据列表（按问题分组）"""
    query = AudioData.all()
    
    if search:
        query = query.filter(
            Q(user_question__icontains=search) | Q(ai_response_text__icontains=search)
        )
        logger.info(f"🔍 应用搜索过滤: {search}")
    
    # 过滤掉GREETING_LIST中的问候语
    query = query.exclude(user_question__in=GREETING_LIST)
    
    # 获取所有符合条件的音频数据（按创建时间升序排序）
    all_audio_data = await query.order_by("created_at")
    
    # 先按问题分组
    grouped_data = {}
    for audio_data in all_audio_data:
        question = audio_data.user_question
        if question not in grouped_data:
            grouped_data[question] = []
        
        audio_url = None
        if audio_data.audio_file_path:
            file_path = audio_data.audio_file_path
            if file_path.startswith('static/'):
                file_path = file_path[7:]
            audio_url = str(request.url_for("audio_files", path=file_path))
        
        # 计算TTS耗时（秒）
        tts_duration = None
        if audio_data.tts_started_at and audio_data.tts_completed_at:
            tts_duration = (audio_data.tts_completed_at - audio_data.tts_started_at).total_seconds()
        
        grouped_data[question].append(AudioDataSchema(
            id=audio_data.id,
            user_question=audio_data.user_question,
            ai_response_text=audio_data.ai_response_text,
            audio_file_path=audio_data.audio_file_path,
            tts_completed_at=convert_to_china_timezone(audio_data.tts_completed_at),
            created_at=convert_to_china_timezone(audio_data.created_at),
            updated_at=convert_to_china_timezone(audio_data.updated_at),
            audio_url=audio_url,
            tts_duration=tts_duration
        ))
    
    # 按最早的音频记录创建时间对分组进行排序
    grouped_list = []
    for question, audio_list in grouped_data.items():
        # 按创建时间升序排序每个分组内的音频
        audio_list.sort(key=lambda x: x.created_at, reverse=False)
        grouped_list.append((question, audio_list))
    
    # 按每个分组中最早音频的创建时间升序排序
    grouped_list.sort(key=lambda x: x[1][0].created_at, reverse=False)
    
    # 计算分组总数和分页
    total_groups = len(grouped_list)
    total_pages = (total_groups + size - 1) // size
    
    # 对分组进行分页
    offset = (page - 1) * size
    paginated_groups = grouped_list[offset:offset + size]
    
    result_data = {
        "groups": paginated_groups,
        "total": total_groups,  # 返回分组总数用于分页
        "page": page,
        "size": size,
        "pages": total_pages
    }
    
    return success(result_data)

@router.post("/create", summary="创建音频数据记录")
async def create_audio_data(
    request: Request,
    data: AudioDataCreateSchema,
    current_user: User = Depends(get_current_user)
):
    """创建音频数据记录"""
    try:
        audio_data = await AudioData.create(
            user_question=data.user_question,
            ai_response_text=data.ai_response_text,
            audio_file_path=data.audio_file_path,
            tts_started_at=data.tts_started_at,
            tts_completed_at=data.tts_completed_at
        )
        
        await record_operation_log(
            request=request,
            username=current_user.username,
            operation_type="CREATE",
            operation_content=f"创建音频数据记录: {data.user_question[:50]}...",
            target_type="audio_data",
            target_id=audio_data.id,
            user=current_user,
            details={
                "user_question": data.user_question,
                "audio_file_path": data.audio_file_path
            }
        )
        
        audio_url = None
        if audio_data.audio_file_path:
            file_path = audio_data.audio_file_path
            if file_path.startswith('static/'):
                file_path = file_path[7:]
            audio_url = str(request.url_for("audio_files", path=file_path))
        
        # 计算TTS耗时（秒）
        tts_duration = None
        if audio_data.tts_started_at and audio_data.tts_completed_at:
            tts_duration = (audio_data.tts_completed_at - audio_data.tts_started_at).total_seconds()
        
        return success(AudioDataSchema(
            id=audio_data.id,
            user_question=audio_data.user_question,
            ai_response_text=audio_data.ai_response_text,
            audio_file_path=audio_data.audio_file_path,
            tts_completed_at=convert_to_china_timezone(audio_data.tts_completed_at),
            created_at=convert_to_china_timezone(audio_data.created_at),
            updated_at=convert_to_china_timezone(audio_data.updated_at),
            audio_url=audio_url,
            tts_duration=tts_duration
        ), "音频数据记录创建成功")
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建音频数据记录失败: {str(e)}")

@router.delete("/{audio_id}", summary="删除音频数据")
async def delete_audio_data(
    request: Request,
    audio_id: int,
    current_user: User = Depends(get_current_user)
):
    """删除音频数据"""
    audio_data = await AudioData.get_or_none(id=audio_id)
    if not audio_data:
        raise HTTPException(status_code=404, detail="音频数据不存在")
    
    user_question = audio_data.user_question
    audio_file_path = audio_data.audio_file_path
    
    await audio_data.delete()
    
    await record_operation_log(
        request=request,
        username=current_user.username,
        operation_type="DELETE",
        operation_content=f"删除音频数据记录: {user_question[:50]}...",
        target_type="audio_data",
        target_id=audio_id,
        user=current_user,
        details={
            "user_question": user_question,
            "audio_file_path": audio_file_path
        }
    )
    
    return success(message="音频数据删除成功")