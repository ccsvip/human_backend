import re
import orjson
import aiohttp
from fastapi import Request
import asyncio
from utils.tools import remove_emojis
import random
from settings.config import TEXT_LIST
from core.logger import logger
from core.services.v1.tts_server import text2speech
from core.dependencies import get_headers, urls


# TODO 此文件待整理

def find_natural_break(text:str, min_len=50) -> int:
    """ 智能寻找自然断句点 """

    # 优先查找句末标点（可扩展）
    punctuations = {'。', '！', '？', '…', ';', '，', '.'}

    # 反向查找最近的标点（从min_len位置向前找）
    for i in range(min_len, 0, -1):
        if i < len(text) and text[i] in punctuations:
            return i + 1 # 包括标点

    # 找不到则向前找最近的空格
    for i in range(min_len, 0, -1):
        if i < len(text) and text[i].isspace():
            return i + 1

    # 最后按最小长度影切分
    return min(min_len, len(text))

async def chat_messages_chunk(request:Request, text:str):
    # 基础配置
    min_length = 35 # 触发TTS的最小字符数
    newline_clean = re.compile(r"[ \n\t\\*]+")  # 处理换行符

    # # 初始化变量
    tts_buffer = [] # 存储文本片段的列表
    current_length = 0 # 当前累计字数
    lock = asyncio.Lock()  # 创建异步锁

    headers = get_headers(request).copy()
    data = {
        "inputs": {},
        "query": text,
        "response_mode": "streaming",
        "conversation_id": "",
        "user": "dev-user"  # TODO 这部分后续不能写死
    }

    full_text_buffer = []

    async with aiohttp.ClientSession() as session:
        async with session.post(urls['chat-messages'], headers=headers, json=data) as response:
            logger.debug("response_status", response.status)
            if response.status != 200:
                logger.error(f"LLM接口发生错误,请检查. 状态码: {response.status}")  # TODO 后续发邮件或者其他方案
                # 返回错误事件 兼容现有错误逻辑
                event = {
                    "event": "error",
                    "message": random.choice(TEXT_LIST),
                    "code": response.status,
                    "params": data
                }
                yield f"event: error\ndata: {orjson.dumps(event)}\n\n"
                return
            # 逐行处理流数据
            async for raw_line in response.content:
                yield raw_line  # 原始流 直接返回
                if await request.is_disconnected():
                    logger.info("客户端断开")
                    break
                # 解码与基础校验
                line = raw_line.decode("utf-8").strip()
                # 步骤1：基础校验
                if not line.startswith("data:"):
                    continue
                # 步骤2：解析json
                try:
                    json_data = orjson.loads(line[5:].encode('utf-8'))  # 去掉 "data:"
                except Exception as e:
                    logger.warning(f"JSON解析失败: {str(e)}")
                    continue
                # 步骤3：提前回答内容
                answer = json_data.get("answer")
                if not answer:
                    continue
                # 步骤4：清理文本
                clean_text = remove_emojis(answer)
                clean_text = newline_clean.sub(' ', clean_text).strip()  # 替换换行符
                full_text_buffer.append(clean_text)
                # 步骤5：写入缓冲区
                async with lock:
                    tts_buffer.append(clean_text)  # 文本加入到队列里面
                    current_length += len(clean_text)
                # 步骤6：检查是否达到处理条件 独立处理循环（避免阻塞主线程）
                while True:  # 必须用循环处理可能的多端切割
                    async with lock:
                        if current_length < min_length:
                            break
                        # 步骤7：合并文本
                        # 将缓冲区的内容拼接成字符串
                        full_text = ''.join(tts_buffer)
                    # 步骤8：寻找自然断点
                    split_pos = find_natural_break(full_text, min_length)
                    # 步骤9：分割文本
                    process_part = full_text[:split_pos].strip()
                    remaining_part = full_text[split_pos:].strip()  # 剩余部分
                    # logger.info(f"🎧切分音频: {process_part}")
                    # 步骤10：更新缓冲区
                    async with lock:
                        tts_buffer = [remaining_part] if remaining_part else []
                        current_length = len(remaining_part)
            # 处理剩余文本
            async with lock:
                if tts_buffer:
                    final_text = "".join(tts_buffer).strip()
                    # logger.info(f"🚀 最终生成: {final_text}")
                    content = "".join(full_text_buffer)
                    logger.info(f"💬 大模型回复: {content}")
                    logger.info("💡 准备发送最终TTS任务")
                    audio_result = await asyncio.create_task(
                        text2speech(request=request, text=content, model='')
                    )
                    # logger.info(f"🔗 生成音频URL: {audio_result['url']}")  # 新增调试日志
                    result_data = {
                        "event": "tts_completed",
                        "url": audio_result["url"],
                        "text": content
                    }
                    yield f"event: tts\ndata: {orjson.dumps(result_data)}\n\n".encode()