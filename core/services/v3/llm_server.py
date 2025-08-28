from dify_client import ChatClient
from settings.config import settings
from fastapi import Request


client = ChatClient(
    api_key=None
)
client.base_url = settings.base_url

def chat_messages_streaming(*, request:Request, text:str):
    client.api_key = request.state.api_key or settings.api_key
    response = client.create_chat_message(
        inputs={}, 
        query=text, 
        user=request.state.user_id, 
        response_mode="streaming", 
        conversation_id="", 
        files=None
    )
    print(response.text)
    return response.text


def chat_messages_workflow(*, request:Request, text:str):
    pass
