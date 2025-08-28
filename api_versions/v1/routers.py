from core.logger import logger
from fastapi.routing import APIRouter, Request
from fastapi import  Depends, BackgroundTasks
from core.tasks import get_suggested_answer
from core.redis_client import redis_client
from settings.config import settings
from core.services.v1 import tts_server, stt_server, llm_server_other, llm_server_block, llm_server
from api_versions.v1.schema import ChatMessageSchema, Text2SpeechSchema, ProcessTextTSchema


router = APIRouter(deprecated=True, include_in_schema=False)


@router.post("/audio-to-text",
             description="最大支持15MB的音频文件",
             summary="语音转文本接口")
async def speech2txt(result:str=Depends(stt_server.audio_to_text)):
    return result

@router.post("/chat-messages",
             summary="通过大模型获取答案")
async def chat_messages(request:Request, data:ChatMessageSchema):
    return await llm_server_block.chat_messages_block(request=request, text=data.text)

@router.post("/chat-messages-stream", summary="流式回复")
async def chat_messages_stream(request:Request, data:ChatMessageSchema):
    return await llm_server.chat_message_stream_(request, data.text)

@router.post("/text-to-audio", summary="语音转文本")
async def text2speech(request:Request, data:Text2SpeechSchema):
    return await tts_server.text2speech(request=request, text=data.text, model=data.model)

@router.get("/parameters", summary="获取开场白和建议问题")
async def get_parameters(request:Request):
    result = await llm_server_other.parameters(request=request)
    return await llm_server_other.handler_parameters(request=request, data=result)

@router.get("/messages/{message_id}/suggested", summary="通过message_id获得建议问题")
async def messages_suggested(request:Request, message_id):
    json_data = await llm_server_other.get_next_suggested(request=request)
    return json_data

@router.post("/text2speechparams", summary="通过文本获取全部信息", description="应用密钥请通过请求头传递")
async def process_text_with_params(request:Request, data:ProcessTextTSchema):
    llm_data = await llm_server.collect_tts_results(
        request, data.text,
        reference_id=data.reference_id,
        user_id=data.user_id
    )
    total_time = llm_data.get('total_time')
    url = llm_data.get('url')
    answer = llm_data.get('text')
    suggested = llm_data.get("suggested")
    # logger.info(f"⏱️ 总耗时: {total_time:.2f}秒 | 捕获到{len(url_list)}个音频URL")
    logger.info(f"⏱️ 总耗时: {total_time:.2f}秒")

    try:
        parameters_dict = await get_parameters(request)
        logger.debug(f"parameters_dict: {parameters_dict}")

        # 开场白和建议问题
        opening_statement = parameters_dict["opening_statement"]  # 此处一定可以获取到 所以直接取值
        suggested_questions = parameters_dict["suggested_questions"]

        return {
            'text': answer,
            'question': data.text,
            "url": url,
            "total_time": total_time,
            "suggested_questions": suggested_questions,
            "opening_statement": opening_statement,
            "suggested": suggested
        }
    except Exception as e:
        from utils.tools import random_voice
        logger.error(f"错误信息: {e}")
        reference_id = request.state.reference_id
        url = request.url_for("audio_files", path=random_voice(voice_id=reference_id))
        return {"url": str(url)}


@router.post("/tts", summary="通过音频文件获取全部信息")
async def master_router(request: Request, background_task:BackgroundTasks, text: str = Depends(
    stt_server.audio_to_text)):
    logger.info("✨ 主路由开始执行")
    # STT
    logger.info(f"🎧 audio-to-text识别结果: {text}")
    # LLM
    llm_data = await llm_server.collect_tts_results(request, text)
    total_time = llm_data.get('total_time')
    url = llm_data.get('url')
    answer = llm_data.get('text')
    suggested = llm_data.get("suggested")
    # logger.info(f"⏱️ 总耗时: {total_time:.2f}秒 | 捕获到{len(url_list)}个音频URL")
    logger.info(f"⏱️ 总耗时: {total_time:.2f}秒")

    try:
        parameters_dict = await get_parameters(request)
        logger.debug(f"parameters_dict: {parameters_dict}")

        # 开场白和建议问题
        opening_statement = parameters_dict["opening_statement"] # 此处一定可以获取到 所以直接取值
        suggested_questions = parameters_dict["suggested_questions"]

        # 缓存逻辑
        api_key = request.state.api_key
        user_id = request.state.user_id
        redis_initial_key = f"initial_processed:{api_key}:{user_id}"
        # initial_processed = await redis_client.exists(redis_initial_key)

        # task_list:list = suggested.copy() # TODO: [1]
        # if not initial_processed:
        #     task_list = suggested_questions + suggested
        #     await redis_client.setex(redis_initial_key, settings.cache_expiry, "1")

        # 添加后台任务
        # background_task.add_task(get_suggested_answer.get_answer,
        #                          request=request,
        #                          text_list=task_list)
        return {
            'text': answer,
            'question': text,
            "url": url,
            "total_time": total_time,
            "suggested_questions":suggested_questions,
            "opening_statement": opening_statement,
            "suggested": suggested
        }
    except Exception as e:
        from utils.tools import random_voice
        logger.error(f"错误信息: {e}")
        reference_id = request.state.reference_id
        url = request.url_for("audio_files", path=random_voice(voice_id=reference_id))
        return {"url": str(url)}