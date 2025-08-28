from core.logger import logger
from core.services.v2 import tts_server
from settings.config import settings
from utils.llm_tools import normalize_time_expressions

async def _normalize_text_for_tts(text: str) -> str:
    """TTS统一预处理：时间表达等中文规范化。"""
    try:
        return normalize_time_expressions(text)
    except Exception as e:
        logger.warning(f"_normalize_text_for_tts 失败: {e}")
        return text


async def tts_servers(*, func_name, request, text, **kwargs):

    logger.debug(f"Using TTS function: {func_name}")

    # 统一规范化文本（如 21:30-21:45 -> 21点30分至21点45分）
    original_text = text
    text = await _normalize_text_for_tts(text)

    # 基础参数
    base_params = {"request": request, "text": text}
    # 添加额外参数（用于数据库保存/追踪规范化前后文本）
    base_params.update({
        "ai_response_text": text,
        "raw_text_before_normalize": original_text
    })
    base_params.update(kwargs)


    func_dict = {
        "edge_tts": {"func": tts_server.text_to_audio_edge, "params": {**base_params, "rate": settings.rate}},
        "aliyun_tts": {"func": tts_server.text_to_audio_aliyun, "params": base_params},
        "local_tts": {"func": tts_server.text_to_audio_ffmpeg_speed, "params": base_params},
        "qwen_tts": {"func": tts_server.text_to_audio_qwen, "params": base_params}
    }

    # 安全地获取TTS函数配置
    tts_config = func_dict.get(func_name)
    if not tts_config:
        raise ValueError(f"Unsupported TTS function: {func_name}")

    func = tts_config.get("func")
    if not func:
        raise ValueError(f"TTS function not found for: {func_name}")

    return await func(**tts_config["params"])