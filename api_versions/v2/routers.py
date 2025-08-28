import asyncio
import colorama
from fastapi import APIRouter, Request, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from core.logger import logger
from utils.redis_tools import generate_cache_key, get_cached_sse_data, store_sse_bulk_data
from core.services.v2 import stt_server, llm_server, tts_server, llm_server_other
from core.redis_client import redis_client
import orjson
import time
from .schema import DeviceCreateSchema, DeviceUpdateSchema, AppWithKeySchema, Device_Pydantic, App_Pydantic, DeviceWithAppsSchema, MediaOutSchema, MediaOutWithURLSchema, MediaUpdateSchema
from .models import Device, App, MediaFile
from .statistics import router as statistics_router
from api_versions.device.routers import routers as device_router
from api_versions.env.routers import router as env_router
import uuid
import os
from pathlib import Path
from typing import Set
from datetime import datetime
import hashlib
from utils.media_sync import _cleanup_duplicates

router = APIRouter()

# 包含统计路由
router.include_router(statistics_router, prefix="/statistics", tags=["统计数据"])

@router.post("/audio-to-text", description="最大支持15MB的音频文件", summary="语音转文本接口")
async def audio_to_text(result:str=Depends(stt_server.audio_to_text)):
    return result

@router.post("/chat-messages-blocking", description="阻塞模式 llm", summary="阻塞模式 llm")
async def chat_messages_blocking(request:Request, text:str):
    from .statistics import record_chat_stats, record_online_user, record_response_time
    
    start_time = time.time()
    
    # 记录在线用户
    user_id = request.state.user_id or "anonymous"
    await record_online_user(user_id)
    
    result_json = await llm_server.chat_messages_block(request=request, text=text)
    
    # 记录对话统计和响应时间
    end_time = time.time()
    response_time = (end_time - start_time) * 1000  # 转换为毫秒
    await record_chat_stats()
    await record_response_time(response_time)
    
    return result_json

@router.post("/chat-messages-streaming", description="流模式 llm", summary="流模式 llm", include_in_schema=False)
async def chat_messages_streaming(request:Request, text:str):
    # async for data in  llm_server.chat_messages_streaming(request=request, text=text):
    async for data in  llm_server.chat_messages_streaming_new(request=request, text=text):
        yield data

@router.get("/chat-messages-streaming", description="流模式 llm (GET)", summary="流模式 llm (GET)", include_in_schema=False)
async def chat_messages_streaming_get(request:Request, text:str):
    """GET方式的流式聊天接口，用于SSE连接"""
    return StreamingResponse(
        llm_server.chat_messages_streaming_new(request=request, text=text),
        media_type='text/event-stream',
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*"
        }
    )

@router.post("/text-to-audio", description="文本转语音接口", summary="文本转语音")
async def text_to_audio(request:Request, text:str):
    return await tts_server.text_to_audio_(request=request, text=text)

@router.post("/clear-context", description="清空用户上下文", summary="清空上下文")
async def clear_context(request: Request):
    """清空当前用户的对话上下文"""
    try:
        api_key = request.state.api_key or ""
        user_id = request.state.user_id or ""

        if not user_id:
            raise HTTPException(status_code=400, detail="用户ID不能为空")

        await llm_server.clear_user_context(api_key, user_id, "用户主动清空")

        return {"success": True, "message": "上下文已清空"}
    except Exception as e:
        logger.error(f"清空上下文失败: {e}")
        raise HTTPException(status_code=500, detail=f"清空上下文失败: {str(e)}")

@router.get("/get-cached-questions", description="必须请求头传入 dify_api_key reference_id user_id", summary="获取缓存问题列表")
async def get_cached_questions(request: Request, text: str = ""):
    """获取当前用户缓存的问题列表

    只有当缓存中存在 __END_OF_STREAM__ 标记时，才认为缓存是完整的，才返回问题列表
    """
    try:
        api_key = request.state.api_key or ""
        user_id = request.state.user_id or ""
        reference_id = request.state.reference_id or ""

        if not user_id:
            raise HTTPException(status_code=400, detail="用户ID不能为空")

        # 读取“用户问题列表”使用的专用键：question:{api_key}:{user_id}:{reference_id}
        # 之前误用了 SSE 流缓存键（sse_cache:...hash），导致即使 Redis 有数据也读不到问题列表
        question_cache_key = f"question:{api_key}:{user_id}:{reference_id}"
        cached_questions = await redis_client.lrange(question_cache_key, 0, -1)

        # 兼容旧逻辑：如果未命中 question: 命名空间，则回退到历史的 sse_cache 哈希键
        used_cache_key = question_cache_key
        if not cached_questions:
            fallback_key = await generate_cache_key(request=request, text=text)
            fallback_data = await redis_client.lrange(fallback_key, 0, -1)
            if fallback_data:
                cached_questions = fallback_data
                used_cache_key = fallback_key

        # 检查缓存是否完整：必须包含 __END_OF_STREAM__ 标记
        if cached_questions:
            # 调试：打印缓存内容类型和结束标记检查
            logger.info(f"🔍 缓存内容类型检查: {[type(item).__name__ for item in cached_questions[-3:]]}")
            logger.info(f"🔍 最后几项内容: {cached_questions[-3:]}")

            # 检查是否包含结束标记（支持字符串和字节两种格式）
            has_end_marker = (b"__END_OF_STREAM__" in cached_questions or
                            "__END_OF_STREAM__" in cached_questions)

            if has_end_marker:
                # 过滤掉结束标记，只返回实际的问题（支持字符串和字节两种格式）
                filtered_questions = [q for q in cached_questions
                                    if q != b"__END_OF_STREAM__" and q != "__END_OF_STREAM__"]
                logger.info(f"✅ 缓存完整，返回问题列表: {len(filtered_questions)} 个问题")
                return {
                    "success": True,
                    "questions": filtered_questions,
                    "count": len(filtered_questions),
                    "cache_key": used_cache_key
                }
            else:
                # 缓存不完整，流式响应可能还在进行中
                logger.info(f"⚠️ 缓存不完整，缺少结束标记")
                return {
                    "success": False,
                    "message": "缓存不完整，流式响应可能还在进行中",
                    "questions": [],
                    "count": 0,
                    "cache_key": used_cache_key
                }
        else:
            return {
                "success": False,
                "message": "未找到缓存的问题",
                "questions": [],
                "count": 0,
                "cache_key": used_cache_key
            }

    except Exception as e:
        logger.error(f"获取缓存问题列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取缓存问题列表失败: {str(e)}")

@router.get("/parameters", description="必须在请求头传入 dify_api_key", summary="获取开场白和建议问题")
async def get_parameters(request:Request):
    return StreamingResponse(
        llm_server_other.parameters_(request=request),
        media_type='text/event-stream',
        headers={"X-Stream-Data": "true"}
    )

@router.post("/tts-blocking", description="阻塞模式主入口", summary="通过传递音频获取全部(阻塞模式)")
async def main_router(request:Request, text:str=Depends(stt_server.audio_to_text)):
    print(text)

    llm_result = await chat_messages_blocking(request=request, text=text)
    print(llm_result)

    tts_url = await text_to_audio(request=request, text=llm_result)
    print(tts_url)

    return {
        "question": text,
        "answer": llm_result,
        "url": tts_url
    }

# async def generate_stream(*, request, text):


#     # 测试不写缓存的速度
#     # async for data in llm_server.chat_messages_streaming(request=request, text=text):
#     #     yield data

#     # async for parameter in llm_server_other.parameters_(request=request):
#         # yield parameter


#     # 写缓存的速度

#     cache_key = await generate_cache_key(request=request, text=text)
#     cached_data = await get_cached_sse_data(request=request, cache_key=cache_key)

#     if cached_data:
#         logger.info(f"🎯 命中SSE缓存(哈希: {cache_key[-10:]})")
#         for data in cached_data:
#             yield data
#     else:
#         logger.info(f"💾 处理新的请求并进行缓存(哈希: {cache_key[-10:]})")
#         async for data in llm_server.chat_messages_streaming(request=request, text=text):
#             yield data
#             await store_see_data_to_cache(request=request, cache_key=cache_key, sse_data=data)

#         async for parameter in llm_server_other.parameters_(request=request):
#             yield parameter
#             await store_see_data_to_cache(request=request, cache_key=cache_key, sse_data=parameter)

@router.get("/llm-streaming", description="流模式 llm", summary="流模式 llm")
async def llm_streaming(*, request:Request, text:str):
    text = text.strip("？?。.>")
    return StreamingResponse(
        generate_stream(request=request, text=text), 
        media_type='text/event-stream',
        headers={"X-Stream-Data": "true"}
    )
async def generate_stream(*, request, text, skip_question=False):
    cache_key = await generate_cache_key(request=request, text=text)
    cached_data = await get_cached_sse_data(request=request, cache_key=cache_key)
    if cached_data:
        logger.info(f"🎯  命中SSE缓存(哈希: {cache_key[-10:]})")
        for data in cached_data:
            if isinstance(data, str):
                data = data.encode('utf-8')
            if skip_question and b'"event": "message"' in data and b'"question":' in data:
                continue
            yield data
    else:
        if text:
            logger.info(f"💾  处理新的请求并进行缓存(哈希: {cache_key[-10:]})")
            buffer = []
            buffer_size = 10

            # async for data in llm_server.chat_messages_streaming(request=request, text=text, skip_question=skip_question):
            async for data in llm_server.chat_messages_streaming_new(request=request, text=text, skip_question=skip_question):
                if isinstance(data, str):
                    data_bytes = data.encode('utf-8')
                else:
                    data_bytes = data
                yield data_bytes
                buffer.append(data_bytes)

                if len(buffer) >= buffer_size:
                    asyncio.create_task(store_sse_bulk_data(cache_key, buffer.copy()))
                    buffer.clear()

            if buffer:
                await store_sse_bulk_data(cache_key, buffer)
                buffer.clear()
            param_buffer = []
            async for parameter in llm_server_other.parameters_(request=request):
                if isinstance(parameter, str):
                    parameter_bytes = parameter.encode('utf-8')
                else:
                    parameter_bytes = parameter
                yield parameter_bytes
                param_buffer.append(parameter_bytes)
            if param_buffer:
                await store_sse_bulk_data(cache_key, param_buffer, append=True)
                await redis_client.rpush(cache_key, b"__END_OF_STREAM__")
        else:
            # 不写缓存
            # async for data in llm_server.chat_messages_streaming(request=request, text=text, skip_question=skip_question):
            async for data in llm_server.chat_messages_streaming_new(request=request, text=text, skip_question=skip_question):
                if isinstance(data, str):
                    data_bytes = data.encode('utf-8')
                else:
                    data_bytes = data
                yield data_bytes
            
            async for parameter in llm_server_other.parameters_(request=request):
                if isinstance(parameter, str):
                    parameter_bytes = parameter.encode('utf-8')
                else:
                    parameter_bytes = parameter
                yield parameter_bytes

@router.post("/tts", description="流模式主入口", summary="通过传递音频获取全部(流模式)")
async def main_router_streaming(request: Request, text: str = Depends(stt_server.audio_to_text)):
    async def stream_generator():
        if text:
            cache_key = await generate_cache_key(request=request, text=text)
            cached_data = await get_cached_sse_data(request=request, cache_key=cache_key)
            if cached_data:
                logger.info(f"🎯  命中完整SSE缓存(哈希: {cache_key[-10:]})")
                for data in cached_data:
                    if isinstance(data, str):
                        data = data.encode('utf-8')
                    if b'"event": "message"' in data and b'"question":' in data:
                        continue
                    yield data
                return
        async for data in generate_stream(request=request, text=text, skip_question=False):
            yield data
    return StreamingResponse(
        stream_generator(),
        media_type='text/event-stream',
        headers={"X-Stream-Data": "true"}
    )