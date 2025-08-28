from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from core.services.v2 import stt_server, llm_server
from core.logger import logger
import orjson
from typing import Dict


router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections = {}

    async def connect(self, websocket:WebSocket, user_id:str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
    
    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_message(self, message:Dict, user_id:str):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json(message)



manager = ConnectionManager()


async def handle_llm_streaming(request:Request, text:str, user_id:str):
    async for chunk in llm_server.chat_messages_streaming(request=request, text=text):
        try:
            data = orjson.loads(chunk.split(b"data: ")[1])
            await manager.send_message({
                "type": data.get("event", "message"),
                "data": data
            }, user_id=user_id)
        except Exception as e:
            logger.error(f"websocket消息解析失败{e}")
        
    

@router.websocket("/ws/chat")
async def websocket_chat(*, request:Request, websocket: WebSocket):
    user_id = request.state.user_id
    await manager.connect(websocket, user_id)

    try:
        while True:
            # 接受客户端数据
            data = await websocket.receive_bytes()

            # STT处理
            text = await stt_server
            await manager.send_message({
                "type": "stt_result",
                "data": {"text": text}
            }, user_id=user_id)

            # 触发LLM处理
            await handle_llm_streaming(websocket, text, user_id)
    except WebSocketDisconnect:
        logger.error(f"客户端断开链接: {user_id}")
    except Exception as e:
        logger.error(f"websocket处理失败: {e}")
        await manager.send_message({
            "type": "error",
            "data": {"message": str(e)}
        }, user_id=user_id)