from settings.config import settings


TORTOISE_ORM = {
    "connections": {
        # "default": "mysql://root:difyai123456@192.168.2.253:3306/tts_db"  # MySQL数据库URL
        "default": rf"mysql://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"  # MySQL数据库URL
    },
    "apps": {
        # 你的应用模型
        "models": {
            "models": ["api_versions.v2.models", "api_versions.wake.models"],  # 指向你的模型文件（如 models.py）
            "default_connection": "default"
        },
        # 必须添加 aerich 专用配置
        "aerich": {
            "models": ["aerich.models"],  # 固定写法
            "default_connection": "default"
        }
    }
}

