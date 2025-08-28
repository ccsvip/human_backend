from settings.config import settings
from fastapi import Request
from core.logger import logger

base_url = settings.base_url
urls = {
    "audio-to-text": f"{base_url}/audio-to-text",
    "chat-messages": f"{base_url}/chat-messages",
    "text-to-audio": f"{settings.tts_url}/v1/tts",
    "parameters": f"{base_url}/parameters",
    "messages_suggested": "{}/messages/{}/suggested"
}

def get_headers(request:Request):
    api_key = request.state.api_key or settings.api_key
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    logger.debug(f"{__name__} headers: {headers}")
    return headers