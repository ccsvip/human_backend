from fastapi import APIRouter, Request
from core.services.v3 import llm_server


router = APIRouter()


@router.get("/llm-streaming")
async def chat_messages_streaming(*, request:Request, text:str):
    result = llm_server.chat_messages_streaming(request=request, text=text)
    return result
