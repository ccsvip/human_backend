import re
import aiofiles
import asyncio
import aiohttp
import random
import orjson
import colorama
import asyncio
from urllib.parse import urlparse
from settings.config import AUDIO_DIR
from core.logger import logger
from core.dependencies import urls, get_headers
from settings.config import TEXT_LIST
from core.decorators.async_tools import async_timer
from utils.tools import remove_emojis
from core.services.v2 import llm_server_other
from core.services.v2.llm_server_other import mixin_llm_server
from core.redis_client import redis_client
from settings.config import TEXT_LIST, settings
from utils.llm_tools import get_tag_url, ollama_llm, is_real_image
from utils.tools import normalize_text_numbers, greeting
from utils.tts_tools import tts_servers
from utils.translate_tools import translate
from utils.zhiyun_translate import translate_youdao_async

# 连接超时配置
CONNECTION_TIMEOUT = aiohttp.ClientTimeout(
    total=60,      # 总超时时间
    connect=10,     # 连接超时时间
    sock_read=30,  # 读取超时时间
    sock_connect=10 # socket连接超时
)



symbol_tuple = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.mp3', '.wav', '.aac', '.ogg', '.mp4', '.avi', '.mov', '.mkv',\
                '.PNG', '.JPG', '.JPEG', '.GIF', '.BMP', '.WEBP', '.MP3', '.WAV', '.AAC', '.OGG', '.MP4', '.AVI', '.MOV', '.MKV')

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.PNG', '.JPG', '.JPEG', '.GIF', '.BMP', '.WEBP'}   
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.aac', '.ogg', '.MP3', '.WAV', '.AAC', '.OGG'}
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.MP4', '.AVI', '.MOV', '.MKV'}

@async_timer
async def chat_messages_block(*, request, text, **kwargs):
    headers = get_headers(request).copy()
    user_id = kwargs.get('user_id') or request.state.user_id
    data = {
        "inputs": {},
        "query": text,
        "response_mode": "blocking",
        "conversation_id": "",
        "user": user_id,
    }
    async with aiohttp.ClientSession(timeout=CONNECTION_TIMEOUT) as session:
        async with session.post(url=urls['chat-messages'], headers=headers, json=data) as resp:
            result_json = await resp.json()
            random_text = random.choice(TEXT_LIST)
            return result_json.get("answer", random_text)
        
# 预编译正则表达式和字符串转换表
LINK_PATTERN = re.compile(r'(!\[[*]?\[)')
# 修复序号格式问题：保留 - 符号，避免破坏 -2. -3. 等序号格式
CLEANUP_TABLE = str.maketrans('*#_[].!`/', '         ')  # 9个字符对应9个空格，不包含 -
# CLEANUP_TABLE = str.maketrans('*#-_[]!`/', '         ')  # 11个字符对应11个空格


async def clear_user_context(api_key: str, user_id: str, reason: str = "未知原因"):
    """清空用户上下文的辅助函数"""
    redis_key = f"conn:{api_key}:{user_id}"
    conversation_count_key = f"count:{api_key}:{user_id}"
    next_suggested_key = f"suggested:{api_key}:{user_id}"

    # 删除相关Redis键
    await redis_client.delete(redis_key)  # 删除会话ID
    await redis_client.delete(conversation_count_key)  # 删除计数器
    await redis_client.delete(next_suggested_key)  # 删除建议问题

    logger.info(f"已清空用户 {user_id} 的上下文，原因: {reason}")

async def chat_messages_streaming_new(*, request, text, **kwargs):
    if text:
        logger.info(f"greeting: {request.state.greeting}")
        if request.state.greeting:
            async for greeting_data in greeting(request):
                yield greeting_data 

        logger.info(f"{colorama.Fore.RED}{text}{colorama.Style.RESET_ALL}")

        # 纠错模型调用（带超时）
        try:
            correct_text = await asyncio.wait_for(ollama_llm(question=text), timeout=2.0)
            question = correct_text if len(text) == len(correct_text) else text
            logger.info(f"纠错大模型纠错后: {colorama.Fore.RED}{question}{colorama.Style.RESET_ALL}")
        except asyncio.TimeoutError:
            question = text
            logger.warning("纠错模型超时，使用原文本")
        
        headers = get_headers(request).copy()
        api_key = request.state.api_key or settings.api_key
        user_id = kwargs.get('user_id') or request.state.user_id
        reference_id = request.state.reference_id or ""
        redis_key = f"conn:{api_key}:{user_id}"
        next_suggested_key = f"suggested:{api_key}:{user_id}"
        
        # 获取上一次会话ID（带轮次限制）
        conversation_count_key = f"count:{api_key}:{user_id}"
        
        # 使用Redis原子操作获取并递增计数
        current_count = await redis_client.incr(conversation_count_key)
        await redis_client.expire(conversation_count_key, settings.cache_expiry)
        
        if current_count > settings.max_conversation_rounds:
            # 超过限制，重置会话
            old_conv_id = ""
            await redis_client.delete(redis_key)
            await redis_client.set(conversation_count_key, "1", ex=settings.cache_expiry)  # 重置为1
            current_count = 1
            logger.info(f"用户 {user_id} 会话轮次超过{settings.max_conversation_rounds}，重置上下文")
        else:
            old_conv_id = await redis_client.get(redis_key) or ""
        
        logger.info(f"用户 {user_id} 当前轮次: {current_count}/{settings.max_conversation_rounds} 读取会话ID: {old_conv_id or '空'}")
        logger.debug(f"{__name__} {redis_key} {next_suggested_key} {old_conv_id}")

        data = {
            "inputs": {},
            "query": question,
            "response_mode": "streaming",
            "conversation_id": old_conv_id,
            "user": user_id,
        }

        # 立即发送 question 事件，不等待 HTTP 连接建立
        skip_question = kwargs.get('skip_question', False)
        if not skip_question:
            question_data = {"event": "message", "question": question, "status": "ready"}
            bytes_data = orjson.dumps(question_data)
            sse_message = f"data: {bytes_data.decode()}\n\n".encode()
            yield sse_message

        async with aiohttp.ClientSession(timeout=CONNECTION_TIMEOUT) as session:
            # 记录HTTP连接建立时间
            import time
            http_start_time = time.time()
            logger.info(f"🔗 开始建立HTTP连接到LLM服务...")
            
            # 使用优化的超时配置
            async with session.post(url=urls['chat-messages'], headers=headers, json=data) as resp:
                http_connect_time = time.time() - http_start_time
                logger.info(f"🔗 HTTP连接建立完成，耗时: {http_connect_time:.2f}秒")
                
                try:
                    text_chunk = ""
                    foobar_text = ""
                    link_buffer = []
                    is_collecting_link = False
                    collected_links = []
                    next_suggested_question = {}
                    to_language = request.state.translate
                    zhiyun_to_language = ''
                    first_response_time = None
                    first_tts_start_time = None
                    
                    async for chunk in resp.content:
                        # 检测客户端是否断开连接
                        if await request.is_disconnected():
                            await clear_user_context(api_key, user_id, "客户端断开连接")
                            break

                        if chunk.startswith(b"data:"):
                            # 记录第一个响应时间
                            if first_response_time is None:
                                first_response_time = time.time()
                                first_response_elapsed = first_response_time - http_start_time
                                logger.info(f"🎯 收到LLM第一个响应，总耗时: {first_response_elapsed:.2f}秒")
                            
                            orjson_data = orjson.loads(chunk[6:])
                            logger.debug(f"{__name__} orjson_data:{orjson_data}")

                            if orjson_data.get('event') == "message":
                                base_answer = orjson_data.get('answer')
                                base_answer = base_answer.replace(r"<think>", "").replace(r"</think>", "")
                                stripped = base_answer.strip()

                                # 链接检测逻辑（使用预编译正则）
                                if not is_collecting_link and (
                                    any(kw in stripped.lower() for kw in ["http", "https", "![", "["])
                                    or LINK_PATTERN.search(stripped)
                                ):
                                    logger.debug("开始收集链接", stripped)
                                    is_collecting_link = True
                                    link_buffer = [stripped]
                                    continue

                                elif is_collecting_link:
                                    link_buffer.append(stripped)
                                    if ")" in stripped:
                                        full_link = "".join(link_buffer)
                                        # 就地解析并发送链接事件，保持顺序
                                        try:
                                            title, link_url = get_tag_url(full_link).values()
                                            ext = "." + link_url.rsplit('.')[-1] if '.' in link_url else ""
                                            if ext in IMAGE_EXTENSIONS:
                                                event_type = "image_link"
                                            elif ext in AUDIO_EXTENSIONS:
                                                event_type = "audio_link"
                                            elif ext in VIDEO_EXTENSIONS:
                                                event_type = "video_link"
                                            else:
                                                event_type = "generic_link"

                                            # 图片链接进行有效性校验
                                            if event_type == "image_link":
                                                is_vaild_image = await is_real_image(url=link_url)
                                                if not is_vaild_image:
                                                    logger.info(f"图片链接验证失败，跳过发送SSE：{link_url}")
                                                    # 重置缓冲并继续解析后续内容
                                                    link_buffer = []
                                                    is_collecting_link = False
                                                    continue

                                            event_data = {
                                                "event": event_type,
                                                "link_data": {"title": title, "url": link_url},
                                                "status": "ok"
                                            }
                                            bytes_data = orjson.dumps(event_data)
                                            sse_data = f"data: {bytes_data.decode()}\n\n".encode()
                                            yield sse_data
                                        except Exception as e:
                                            logger.error(f"处理链接失败: {e}")

                                        # 重置缓冲区状态
                                        link_buffer = []
                                        is_collecting_link = False
                                    continue

                                # # 使用预编译的转换表清理文本（更高效）
                                # answer = base_answer.translate(CLEANUP_TABLE)
                                # text_chunk += answer.strip()
                                # foobar_text += base_answer

                                # 修改：分别处理显示文本和TTS文本
                                # 检查是否需要在图片前添加换行符（修复序号格式）
                                if base_answer.startswith('![') and foobar_text and not foobar_text.endswith('\n'):
                                    foobar_text += '\n'
                                
                                # 检查是否需要在序号前添加换行符（修复 -2. -3. 等序号格式）
                                import re
                                if re.match(r'^-?\d+\.', base_answer.strip()) and foobar_text and not foobar_text.endswith('\n'):
                                    foobar_text += '\n'
                                
                                # foobar_text: 保持原始markdown格式，用于前端显示
                                foobar_text += base_answer
                                
                                # text_chunk: 清理后用于TTS，移除 - 符号避免序号读出
                                # answer = base_answer.translate(CLEANUP_TABLE).replace("-", " ")
                                answer = base_answer.translate(CLEANUP_TABLE)
                                text_chunk += answer.strip()

                                
                                # 调试日志：检查换行符保持情况 - 添加长度检查
                                if len(foobar_text) > 100:  # 只在内容足够长时才记录
                                    logger.debug(f"📝 base_answer: {repr(base_answer)}")
                                    logger.debug(f"📝 当前foobar_text长度: {len(foobar_text)}, 内容: {repr(foobar_text[-100:])}")  # 只显示最后100字符
                                    logger.debug(f"🎵 当前text_chunk: {repr(text_chunk[-50:])}")  # 只显示最后50字符

                                # 检查是否需要生成TTS
                                if text_chunk.endswith(tuple(settings.symbols)) and len(text_chunk) >= settings.cut_length:
                                    # 记录第一次TTS开始时间
                                    if first_tts_start_time is None:
                                        first_tts_start_time = time.time()
                                        tts_trigger_elapsed = first_tts_start_time - http_start_time
                                        logger.info(f"🎵 第一次TTS触发，距离开始: {tts_trigger_elapsed:.2f}秒，文本长度: {len(text_chunk)}")
                                    
                                    # 翻译文本
                                    translate_start_time = time.time()
                                    try:
                                        logger.debug(f"{__name__} {foobar_text}")
                                        translate_text = await translate_youdao_async(text=foobar_text, tgt_lang=to_language)
                                        translate_elapsed = time.time() - translate_start_time
                                        logger.info(f"🌏 翻译完成，耗时: {translate_elapsed:.2f}秒")
                                    except Exception as e:
                                        translate_elapsed = time.time() - translate_start_time
                                        logger.error(f"翻译失败，耗时: {translate_elapsed:.2f}秒，错误: {e}")
                                        translate_text = foobar_text

                                    # 文本清理和处理
                                    text_clean = translate_text.translate(CLEANUP_TABLE).replace("-", " ")
                                    if settings.numbers_to_chinese:
                                        text_clean = normalize_text_numbers(text_clean)

                                    # TTS调用（符号+长度门槛）
                                    tts_url = None
                                    text_for_tts = text_clean.strip()
                                    if not text_for_tts:
                                        logger.info("🔕 清理后文本为空，跳过本次TTS触发")
                                    else:
                                        tts_start_time = time.time()
                                        try:
                                            logger.info(f"🔊 开始TTS生成，文本: {text_for_tts[:50]}...")
                                            tts_url = await asyncio.wait_for(
                                                tts_servers(
                                                    func_name=settings.tts_service, 
                                                    request=request, 
                                                    text=text_for_tts,
                                                    user_question=question,
                                                    ai_response_text=translate_text
                                                ),
                                                timeout=60.0
                                            )
                                            tts_elapsed = time.time() - tts_start_time
                                            total_elapsed = time.time() - http_start_time
                                            logger.info(f"🔊 TTS生成完成，耗时: {tts_elapsed:.2f}秒，总耗时: {total_elapsed:.2f}秒")
                                        except asyncio.TimeoutError:
                                            tts_elapsed = time.time() - tts_start_time
                                            logger.warning(f"TTS服务超时，耗时: {tts_elapsed:.2f}秒，文本: {text_for_tts[:50]}...")
                                        except Exception as e:
                                            tts_elapsed = time.time() - tts_start_time
                                            logger.error(f"TTS生成失败，耗时: {tts_elapsed:.2f}秒，错误: {e}")
                                    
                                    event_data = {"event": "message", "answer": translate_text, "status": "ok", "url": tts_url}
                                    bytes_data = orjson.dumps(event_data)
                                    sse_message = f"data: {bytes_data.decode()}\n\n".encode()
                                    yield sse_message
                                    text_chunk = ""
                                    foobar_text = ""

                            elif orjson_data.get("event") == "message_end":
                                message_id = orjson_data.get("message_id")
                                logger.debug(f"用户: {user_id} 更新message_id: {message_id}")
                                
                                # 批量Redis操作
                                new_conversation_id = orjson_data.get("conversation_id")
                                
                                # 正常保存会话信息
                                redis_tasks = [
                                    redis_client.setex(next_suggested_key, settings.cache_expiry, message_id),
                                    redis_client.setex(redis_key, settings.cache_expiry, new_conversation_id)
                                ]
                                
                                await asyncio.gather(*redis_tasks, return_exceptions=True)
                                logger.info(f"用户 {user_id} 会话轮次: {current_count}/{settings.max_conversation_rounds} 会话ID: {new_conversation_id}")
                                logger.info(f"保存会话ID到Redis: {redis_key} = {new_conversation_id}")
                                
                                # 获取建议问题
                                next_suggested = await llm_server_other.get_next_suggested(
                                    request=request, user_id=user_id, suggested_redis_key=next_suggested_key
                                )
                                next_suggested_question['data'] = next_suggested['data']
                    
                    # 处理剩余文本
                    if text_chunk:
                        try:
                            # 翻译剩余文本 - 修复：使用foobar_text保持原始格式（包括空格）
                            logger.debug(f"🔧 剩余文本处理 - foobar_text: {repr(foobar_text)}")
                            logger.debug(f"🔧 剩余文本处理 - text_chunk: {repr(text_chunk)}")
                            translate_text = await translate_youdao_async(text=foobar_text, tgt_lang=to_language)
                        except Exception as e:
                            logger.error(f"翻译剩余文本失败: {e}")
                            translate_text = foobar_text

                        # 文本清理和处理
                        text_clean = translate_text.translate(CLEANUP_TABLE).replace("-", " ")
                        if settings.numbers_to_chinese:
                            text_clean = normalize_text_numbers(text_clean)

                        # TTS调用（与流式一致：必须以指定符号结尾且长度达到阈值）
                        tts_url = None
                        text_for_tts = text_clean.strip()

                        if not text_for_tts:
                            logger.info("🔕 清理后剩余文本为空，跳过TTS")
                        elif text_for_tts.endswith(tuple(settings.symbols)) and len(text_for_tts) >= settings.cut_length:
                            try:
                                tts_url = await asyncio.wait_for(
                                    tts_servers(
                                        func_name=settings.tts_service,
                                        request=request,
                                        text=text_for_tts,
                                        user_question=question,
                                        ai_response_text=translate_text
                                    ),
                                    timeout=20.0
                                )
                            except asyncio.TimeoutError:
                                logger.warning(f"剩余文本TTS服务超时: {text_for_tts[:50]}...")
                            except Exception as e:
                                logger.error(f"剩余文本TTS生成失败: {e}")
                        else:
                            logger.info(f"🔕 剩余文本不满足触发条件（结尾符/长度未达标），symbols={settings.symbols}, cut_length={settings.cut_length}，文本尾部: {repr(text_for_tts[-10:])}")

                        event_data = {"event": "message", "answer": translate_text, "status": "ok", "url": tts_url}
                        sse_msg = f"data: {orjson.dumps(event_data).decode()}\n\n".encode()
                        yield sse_msg

                    # 处理收集的链接（兼容旧逻辑）：现在链接已在流式过程中就地发送，这里通常不会有剩余
                    for link in collected_links:
                        try:
                            title, link_url = get_tag_url(link).values()
                            event_data = {
                                "event": "generic_link",
                                "link_data": {"title": title, "url": link_url},
                                "status": "ok"
                            }
                            bytes_data = orjson.dumps(event_data)
                            sse_data = f"data: {bytes_data.decode()}\n\n".encode()
                            yield sse_data
                        except Exception as e:
                            logger.error(f"处理链接失败: {e}")
                    
                    # 发送建议问题
                    if next_suggested_question and next_suggested_question.get('data'):
                        event_data = {
                            "event": "suggested_questions",
                            "data": next_suggested_question['data'],
                            "status": "ok"
                        }
                        bytes_data = orjson.dumps(event_data)
                        sse_message = f"data: {bytes_data.decode()}\n\n".encode()
                        yield sse_message
                    
                    # 流式响应完成后缓存用户问题列表
                    question_cache_key = f"question:{api_key}:{user_id}:{reference_id}"
                    logger.debug(f"即将缓存用户问题到列表: {question_cache_key} = {question}")
                    try:
                        # 先删除可能存在的非列表类型的键
                        key_type = await redis_client.type(question_cache_key)
                        if key_type != "list" and key_type != "none":
                            await redis_client.delete(question_cache_key)

                        await redis_client.lpush(question_cache_key, question)
                        # 添加结束标记，表示流式响应完成
                        await redis_client.lpush(question_cache_key, "__END_OF_STREAM__")
                        await redis_client.expire(question_cache_key, settings.cache_expiry)
                        logger.debug(f"缓存成功（含结束标记）: {question_cache_key}")
                    except Exception as cache_error:
                        logger.error(f"缓存失败: {cache_error}")

                except Exception as e:
                    logger.error(f"流处理异常: {e}")
                    err_data = {"event": "error", "detail": str(e), "answer": random.choice(TEXT_LIST)}
                    bytes_data = orjson.dumps(err_data)
                    sse_message = f"data: {bytes_data.decode()}\n\n".encode()
                    yield sse_message
    else:
        # 空文本处理
        yield b'data: {"event": "message","question": ""}\n\n'
        text = random.choice(TEXT_LIST)
        event_data = {"event": "message", "status": "error", "answer": text}
        bytes_data = orjson.dumps(event_data)
        sse_message = f"data: {bytes_data.decode()}\n\n".encode()
        yield sse_message

async def write_text(*, content, question):
    filename = f"{question}.txt"
    async with aiofiles.open(AUDIO_DIR / filename, "a", encoding="utf-8") as f:
        await f.write(content.strip() + "\n")
        await f.flush()
