import emoji
import hashlib
import uuid
import time
import orjson
import re
import cn2an
import random
import jwt
import colorama
from jwt import exceptions
from fastapi import Request
from core.logger import logger
from utils.zhiyun_translate import translate_youdao_async



# 这是比较老的移除表情的方案
async def remove_emojis_old(text):
    logger.debug(f"{__name__} {text}")
    return "".join(chat for chat in emoji.replace_emoji(text))

async def remove_emojis(text):
    """移除文本中的emoji表情，保持其他内容不变"""
    logger.debug(f"{__name__} 原文本: {text}")
    
    if not text:
        return text
    
    # 使用emoji库移除emoji，保持其他内容不变
    clean_text = emoji.replace_emoji(text, replace='')
    
    logger.debug(f"{__name__} 清理后: {clean_text}")
    return clean_text

def create_hash(key:str):
    hash_key = hashlib.md5(key.encode("utf-8")).hexdigest()
    return hash_key

def get_file_name() -> str:
    """ 获得标准的文件名称 方便统一管理 """
    filename = create_hash(f"{uuid.uuid4().hex}_{int(time.time()*1000)}")
    logger.debug(f"filename: {filename}")
    return filename

# 失败时候的音频
def random_voice(*, voice_id):
    import os
    from settings.config import FAIL_DIR

    audio_list = os.listdir(FAIL_DIR)
    man_audio_list = [audio for audio in audio_list if audio.startswith("man")]
    woman_audio_list = [audio for audio in audio_list if audio.startswith("woman")]
    if voice_id == "man":
        return f"fail/{random.choice(man_audio_list)}"
    elif voice_id == "woman":
        return f"fail/{random.choice(woman_audio_list)}"



def get_user_id(access_token:str) -> str:
    try:
        decode = jwt.decode(access_token, options={"verify_signature": False})
        return {
            "status": "success",
            "user_id": decode.get("user_id"),
        }
    except exceptions.ExpiredSignatureError:
        return {
            "status": "error",
            "message": "token已过期"
        }
    except exceptions.InvalidTokenError:
        return {
            "status": "error",
            "message": "token无效"
        }

# 数字转中文读音（整数 + 小数）
def number_to_chinese_readable(number_str: str) -> str:

    if '.' in number_str:
        integer, decimal = number_str.split('.', 1)
        int_part = cn2an.an2cn(int(integer)) if integer else '零'
        decimal_part = ''.join([cn2an.an2cn(int(d)) for d in decimal])
        return f"{int_part}点{decimal_part}"
    else:
        return cn2an.an2cn(int(number_str))

def normalize_text_numbers(text: str) -> str:
    def replacer(match):
        num = match.group(0)
        try:
            return number_to_chinese_readable(num)
        except Exception:
            return num  # fallback
    # 匹配整数或小数（包括金额、序号等）
    return re.sub(r'\d+(\.\d+)?', replacer, text)



# --------------------------- 开场白 ----------------------
async def greeting(request: Request):
    from settings.config import GREETING_LIST, ZHIYUN_LANGUAGE_MAPPING
    from utils.translate_tools import translate
    from settings.config import settings
    from utils.tts_tools import tts_servers

    if settings.greeting_enable:

        # 先播一句问候语，立即响应
        greeting = random.choice(GREETING_LIST)
        to_language = request.state.translate 

        language = ZHIYUN_LANGUAGE_MAPPING.get(to_language, to_language)
        logger.info(f"目标语言：{colorama.Fore.YELLOW}{language}{colorama.Style.RESET_ALL}")
        
        try:
            if to_language and to_language not in  ["zh-CHS", "zh"]:
                translate_text = await translate_youdao_async(text=greeting, tgt_lang=to_language)
                # 检查翻译结果是否有效
                if not translate_text or not translate_text.strip():
                    translate_text = greeting  # 翻译失败时使用原文
            else:
                translate_text = greeting
                
            # 确保文本不为空
            if translate_text and translate_text.strip():
                tts_url = await tts_servers(func_name=settings.tts_service, request=request, text=translate_text)
                greeting_event = {
                    "event": "message",
                    "answer": translate_text,
                    'greeting': True,
                    "status": "ok",
                    "url": tts_url
                }
                yield f"data: {orjson.dumps(greeting_event).decode()}\n\n".encode()
        except Exception as e:
            logger.error(f"问候语处理失败: {e}")
            # 失败时使用原文
            tts_url = await tts_servers(func_name=settings.tts_service, request=request, text=greeting)
            greeting_event = {
                "event": "message",
                "answer": greeting,
                'greeting': True,
                "status": "ok",
                "url": tts_url
            }
            yield f"data: {orjson.dumps(greeting_event).decode()}\n\n".encode()
