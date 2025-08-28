import asyncio
import hashlib
import time
import orjson
import re
import random
import aiohttp
from core.logger import logger
from core.redis_client import redis_client
from core.dependencies import urls, get_headers
from utils.tools import remove_emojis
from settings.config import TEXT_LIST, settings
from fastapi.responses import StreamingResponse
from fastapi import Request
from core.services.v1.tts_server import text2speech
from core.services.v1.llm_server_other import get_next_suggested

logger.debug(f"{__name__} mode: {settings.mode}")

async def chat_messages_(request:Request, text:str, **kwargs):
    logger.debug(f"kwargs: {kwargs}")
    start_time = time.time()
    newline_clean = re.compile(r"[ \n\t\\*]+") # 处理换行符
    headers = get_headers(request).copy()
    api_key = request.state.api_key or settings.api_key
    user_id = kwargs.get('user_id') or request.state.user_id
    redis_key = f"conn:{api_key}:{user_id}"
    next_suggested_key = f"suggested:{api_key}:{user_id}"
    # 获取上一次会话ID 不存在时候返回空字符串
    old_conv_id = await redis_client.get(redis_key) or ""
    data = {
        "query": text,
        "inputs": {},
        "response_mode": "streaming",
        "conversation_id": old_conv_id,
        "user": user_id
    }
    data.update({"query": text})
    full_text_buffer = []
    async with aiohttp.ClientSession() as session:
        async with session.post(urls['chat-messages'], headers=headers, json=data) as response:
            if response.status != 200:
                logger.error(f"LLM接口发生错误,请检查. 状态码: {response.status} {data} {await response.text()}") # TODO 后续发邮件或者其他方案
                random_text = random.choice(TEXT_LIST)
                audio_result = await asyncio.create_task(
                    text2speech(request=request, text=random_text, model=settings.mode, kwargs=kwargs)
                )
                result_data = {
                    "event": "llm_error",
                    "url": audio_result["url"],
                    "text": random_text
                }
                yield f"event: tts\ndata: {orjson.dumps(result_data)}\n\n".encode()
                return

            async for raw_line in response.content:
                if await request.is_disconnected():
                    logger.info("客户端断开")
                    break
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                try:
                    json_data = orjson.loads(line[5:])  # 去掉 "data:"
                    # logger.debug(f"{__name__} json_data: {json_data}")
                except Exception as e:
                    logger.warning(f"JSON解析失败: {str(e)}")
                    continue
                if json_data['event'] == 'message':
                    answer = json_data.get("answer")
                    if not answer:
                        continue
                    clean_text = await remove_emojis(answer)
                    print(clean_text)
                    clean_text = newline_clean.sub(' ', clean_text).strip()  # 替换换行符
                    full_text_buffer.append(clean_text)
            # {'event': 'message_end',
            # 'conversation_id': 'd0a6b05a-fac8-4755-ac79-c712d76dda6f', 'message_id': '9d335ad2-6748-467b-94a2-7cf821a0d752', 'created_at': 1741224569, 'task_id': '8f2698d0-7e8a-4c5b-a30d-ef09dd595185', 'id': '9d335ad2-6748-467b-94a2-7cf821a0d752', 'metadata': {'retriever_resources': [{'dataset_id': '3f24317b-9caa-4eb5-a5b8-886efb465f63', 'dataset_name': '科技馆', 'document_id': '866fb8a9-6833-4b55-b389-7bdd89229597', 'document_name': '预约购票.docx', 'data_source_type': 'upload_file', 'segment_id': '60c6339a-19c3-4d88-a49b-acf48b4c7ecd', 'retriever_from': 'api', 'score': 0.32974573969841003, 'content': '\n个人预约：\n特效影院\n普通票： 30元/人/场\n优惠票： 20元/人/场\n优惠票： 未满18周岁的未成年人和全日制大学本科及以下学历学生（不含成人教育及研究生）。\n温馨提示：\n1.特效电影（巨幕影院除外）不适宜心脏病、高血压等患者及婴幼儿观看，请慎重购票。\n2.动感影院谢绝1.2米以下儿童、70周岁以上老年人及孕妇入场。\n3.4D影院谢绝孕妇入场。\n4.优惠人群在检票时须出示购票登记的有效证件和学生证。\n5.无证或不符合优惠票和免费票范围的须购普通票。', 'position': 1}, {'dataset_id': '3f24317b-9caa-4eb5-a5b8-886efb465f63', 'dataset_name': '科技馆', 'document_id': '2af21d11-9c06-4ec7-aba8-0b0dd4b3beaa', 'document_name': '场馆概况.docx', 'data_source_type': 'upload_file', 'segment_id': '64095b7d-cb80-4a94-9db8-d7960a7d09ac', 'retriever_from': 'api', 'score': 0.313749223947525, 'content': '1楼设有：儿童科学乐园、华夏之光、短期展厅、球幕影院、报告厅场所\n1F分布图URL：http://192.168.2.251:9001/api/v1/buckets/mypic/objects/download?preview=true&prefix=1F.png&version_id=null\n', 'position': 2}, {'dataset_id': '3f24317b-9caa-4eb5-a5b8-886efb465f63', 'dataset_name': '科技馆', 'document_id': '2af21d11-9c06-4ec7-aba8-0b0dd4b3beaa', 'document_name': '场馆概况.docx', 'data_source_type': 'upload_file', 'segment_id': 'ecc25a4e-c6b9-4c17-b842-6549a2906c90', 'retriever_from': 'api', 'score': 0.3135141432285309, 'content': '3楼设有：科技与生活A厅、科技与生活B厅、科技与生活C厅、科技与生活D厅场所\n3F分布图URL：http://192.168.2.251:9001/api/v1/buckets/mypic/objects/download?preview=true&prefix=3F.png&version_id=null\n', 'position': 3}, {'dataset_id': '3f24317b-9caa-4eb5-a5b8-886efb465f63', 'dataset_name': '科技馆', 'document_id': '2af21d11-9c06-4ec7-aba8-0b0dd4b3beaa', 'document_name': '场馆概况.docx', 'data_source_type': 'upload_file', 'segment_id': '3f9411be-8e78-4369-8138-077d565a66bc', 'retriever_from': 'api', 'score': 0.3129405975341797, 'content': '4楼设有：挑战与未来A厅、挑战与未来B厅、挑战与未来C厅、挑战与未来D厅场所\n4F分布图URL：http://192.168.2.251:9001/api/v1/buckets/mypic/objects/download?preview=true&prefix=4F.png&version_id=null\n', 'position': 4}], 'usage': {'prompt_tokens': 1546, 'prompt_unit_price': '0.0', 'prompt_price_unit': '0.0', 'prompt_price': '0.0', 'completion_tokens': 20, 'completion_unit_price': '0.0', 'completion_price_unit': '0.0', 'completion_price': '0.0', 'total_tokens': 1566, 'total_price': '0.0', 'currency': 'USD', 'latency': 1.1669281070062425}}, 'files': None}
            try:
                logger.debug(json_data)
                content = "".join(full_text_buffer)
                logger.debug(full_text_buffer)
                logger.info(f"⏳ 大模型耗时: {time.time() - start_time:.2f}")
                logger.info(f"💬 大模型回复: {content}")
                # logger.info("💡 准备发送最终TTS任务")
                mode = request.state.mode or settings.mode
                logger.debug(f"{__name__} mode: {mode}")
                audio_result = await asyncio.create_task(
                    text2speech(request=request, text=content, model=mode, kwargs=kwargs)
                )
                if message_id := json_data.get("message_id"):
                    logger.debug(f"用户: {user_id} 更新message_id: {message_id}")
                    await asyncio.create_task(redis_client.setex(
                        name=next_suggested_key,
                        time=settings.cache_expiry,
                        value=message_id
                    ))
                next_suggested = await get_next_suggested(
                    request=request,
                    user_id=user_id,
                    suggested_redis_key=next_suggested_key
                )
                # {'result': 'success', 'data': ['你吃饭了吗？', '哪里不舒服？', '天气怎么样？']}
                result_data = {
                    "event": "tts_completed",
                    "url": audio_result["url"],
                    "text": content,
                    "suggested": next_suggested['data']
                }
                logger.debug(f"{__name__} orjson.dumps(result_data): {orjson.dumps(result_data)}, {type(orjson.dumps(result_data))}")
                # yield f"event: tts\ndata: {orjson.dumps(result_data)}\n\n".encode()
                yield f"event: tts\ndata: {orjson.dumps(result_data).decode('utf-8')}\n\n".encode()
                if new_conv_id := json_data.get('conversation_id'):
                    await asyncio.create_task(redis_client.setex(
                        name=redis_key,
                        time=settings.cache_expiry,
                        value=new_conv_id
                    ))
                    logger.debug(f"用户: {user_id} 更新会话id: {new_conv_id}")
            except Exception as e:
                logger.error(f"出错了: {e}")
                random_text = random.choice(TEXT_LIST)
                audio_result = await asyncio.create_task(
                    text2speech(request=request, text=random_text, model=settings.mode, kwargs=kwargs)
                )
                result_data = {
                    "event": "llm_error",
                    "url": audio_result["url"],
                    "text": random_text
                }
                yield f"event: tts\ndata: {orjson.dumps(result_data)}\n\n".encode()
# ----------------------------------------------------------------------------------------------------------------------
async def chat_message_stream_function(request, text):
    headers = get_headers(request).copy()
    user_id = request.state.user_id
    redis_key = f"conn:{user_id}"
    old_conv_id = await redis_client.get(redis_key) or ""
    data = {
        "inputs": {},
        "query": text,
        "response_mode": "streaming",
        "conversation_id": old_conv_id,
        "user": user_id   # TODO 这部分后续不能写死
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(urls['chat-messages'], headers=headers, json=data) as response:
            if response.status != 200:
                logger.error(f"LLM接口发生错误,请检查. 状态码: {response.status}")  # TODO 后续发邮件或者其他方案
                event = {
                    "event": "error",
                    "message": random.choice(TEXT_LIST)
                }
                event.update({"code": response.status,"params": data})
                yield f"event: error\ndata: {orjson.dumps(event)}\n\n"
                return
            async for raw_line in response.content:
                yield raw_line
                if await request.is_disconnected():
                    logger.info("客户端断开")
                    break
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                try:
                    json_data = orjson.loads(line[5:])  # 去掉 "data:"
                    if new_conv_id := json_data.get('conversation_id'):
                        asyncio.create_task(redis_client.setex(
                            name=redis_key,
                            time=settings.cache_expiry,
                            value=new_conv_id
                        ))
                        logger.debug(f"用户: {user_id} 更新会话id: {new_conv_id}")
                except Exception as e:
                    logger.warning(f"JSON解析失败: {str(e)}")
                    event = {
                        "event": "error",
                        "message": random.choice(TEXT_LIST)
                    }
                    event.update({"code": response.status, "params": data})
                    yield f"event: error\ndata: {orjson.dumps(event)}\n\n"
# 流式SSR
async def chat_message_stream_(request, text:str):
    ssr_headers = {
        "Cache-Control": "no-cache",
        "Connection": "Keep-alive",
        "X-Accel-Buffering": "no"
    }
    return StreamingResponse(
        chat_message_stream_function(request, text),
        media_type="text/event-stream",
        headers=ssr_headers
    )
# ----------------------------------------------------------------------------------------------------------------------

# 处理结果内容
async def collect_tts_results(request, text, **kwargs):
    start_time = time.time()
    # 新增缓存检查 TODO 这里有bug 不过先不修
    reference_id = kwargs.get('reference_id') or request.state.reference_id
    user_id = kwargs.get("user_id") or request.state.user_id
    text_sha256 = hashlib.sha256(f"{text}_{reference_id}".encode("utf-8")).hexdigest()
    llm_redis_key = f"llm:{user_id}:{reference_id}:{text_sha256}"
    is_cached = await redis_client.get(llm_redis_key)
    if is_cached:
        logger.info(f"🎯 命中LLM缓存(key: {text_sha256[:10]})")
        total_time = time.time() - start_time
        data = await redis_client.getex(llm_redis_key)
        json_data = orjson.loads(data)
        json_data.update({"total_time": total_time})
        return json_data


    data_dict = dict()
    start_time = time.time()

    async for chunk in chat_messages_(request, text, **kwargs):
        # logger.info(f"🚦 原始数据块类型: {type(chunk)} | 内容片段: {chunk[:100]}...")
        try:
            # 尝试解析SSE格式
            decoded:str = chunk.decode().strip()
            if decoded.startswith("event:"):
                event_type = decoded.split('\n')[0].split(': ')[1]
                json_str = decoded.split('\ndata: ')[1]
                logger.debug(f"{__name__} json_str: {json_str} {type(json_str)} ")
                data = orjson.loads(json_str.encode("utf-8"))
                logger.debug(f"{__name__} data: {data} {type(data)} ")
                if event_type == "tts":
                    # logger.info(f"🔊 捕获到LLM文本: {data['text']}")
                    # logger.info(f"🔊 捕获到TTS事件: {data['url']}")
                    logger.debug(f"{__name__} data: {data}")
                    # url_list.append(data.pop('url'))
                    data_dict.update(data)
                    data_dict.update({"question": text})
                    logger.debug(f"{__name__} data: {data}")
                    # 放入缓存
                    asyncio.create_task(redis_client.setex(
                        llm_redis_key,
                        settings.cache_expiry,
                        # orjson.dumps({"url_list": url_list, "answer": answer})
                        orjson.dumps(data).decode("utf-8")
                    ))
                    logger.info(f"💾 新增LLM缓存(哈希: {text_sha256[:10]})")
        except Exception as e:
            logger.error(f"⚠️ 数据解析异常: {str(e)}")
            continue

    total_time = time.time() - start_time
    # return {"total_time": , "url_list": , "answer": }
    data_dict.update({"total_time": total_time})
    logger.debug(f"{__name__} data_dict: {data_dict}")
    return data_dict
