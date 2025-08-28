from app.factory import create_app
from settings.config import settings

app = create_app()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.fastapi_port)