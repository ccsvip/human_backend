from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
AUDIO_DIR = BASE_DIR / 'static'
AUDIO_DIR.mkdir(exist_ok=True, parents=True)
FAIL_DIR = AUDIO_DIR / 'fail'
FAIL_DIR.mkdir(exist_ok=True, parents=True)
SETTINGS_DIR = BASE_DIR / 'settings'
PROMPT_PATH = SETTINGS_DIR / 'prompt.txt'

class Settings(BaseSettings):
    base_url: str
    model_url: str
    model_name: str
    api_key: str
    max_file_size: int
    tts_url: str
    reference_id: str
    zhiyun_app_key: str
    zhiyun_app_secret: str
    voice_name: str
    log_level: str
    mode: str
    fastapi_port: int
    expose_port: int

    # 智云翻译
    zhiyun_translate_apikey: str
    zhiyun_translate_secret: str
    

    # TTS服务
    tts_service: str 
    local_tts_speed: float

    # redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 1
    redis_password: str = "difyai123456"
    cache_expiry: int = 3600

    # 清除文件
    order: str
    admin_password: str

    # 信号量
    semaphore: int = 3

    # 最大上下文长度
    max_conversation_rounds: int

    # dashscope
    dashscope_api_key: str

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / '.env',
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # edge_tts
    voice_name_man: str
    voice_name_woman: str
    rate: str

    # db
    db_host: str
    db_port: str
    db_user: str
    db_password: str
    db_root_password: str
    db_name: str
    enable_database: bool
    db_expose_port: int

    # yueer
    yueer_api_key: str

    # greeting
    greeting_enable: bool

    greeting_en: bool

    # 切分长度
    cut_length:int 

    # 切分符号
    symbols: str

    # 是否缓存开场白3个问题
    opening_statement: bool
    host: str

    # 数字转中文
    numbers_to_chinese: bool

    # 纠错大模型
    correct_api_key: str


settings = Settings()


# from pprint import pprint
# pprint(settings.model_dump())


TEXT_LIST = [
  "好的，很抱歉我刚才可能表达得不够清晰，请您再说一遍，我会认真听的。作为您的智能助手，我很乐意为您提供帮助。",
  "没问题，请您再说一遍，我会仔细聆听。我随时在这里为您服务，请尽管提问。",
  "抱歉，我可能没能准确理解您刚才的问题，请您再重复一遍，我会尽力帮助您。我期待您的提问。",
  "好的，请您再说一次，我保证会认真听取。您有任何需求，我都会尽力满足。",
  "非常抱歉，我可能理解有误，请您再说一遍，我会更加专注。我是您的 AI 助手，能为您效劳是我的荣幸。",
  "好的，请您再重复一遍，我将确保理解您的需求。请放心，我会尽力为您解决问题。",
  "没关系，请您再说一遍，我会更加集中注意力。您有任何疑问，都可以随时向我提出。",
  "抱歉，我可能没有完全接收到您刚才的信息，请您再说一遍，我会仔细聆听。我随时准备为您提供帮助。",
  "好的，请您再重复一遍，我会尽力理解您的意思。我是您的智能伙伴，为您服务是我的职责。",
  "非常抱歉，我可能没有清晰地理解您的表达，请您再重复一次，我会认真听取的。您有任何问题，都可以随时问我哦！"
]

GREETING_LIST = [
    "感谢您的等待，我正在生成答案",
    "我正在生成答案，请稍等",
    "感谢您的等待，这就为您解答",
    "让我思考一下您的问题"
]

LANGUAGE_MAPPING = {
    "en": "英文",
    "zh": "中文",
    "ja": "日文",
    "ko": "韩文",
    "fr": "法文",
    "de": "德文",
    "es": "西班牙文",
    "ar": "阿拉伯文"
}


ZHIYUN_LANGUAGE_MAPPING = {
    "en": "英文", "英文": "en",
    "zh": "中文", "中文": "zh",
    "ja": "日文", "日文": "ja",
    "ko": "韩文", "韩文": "ko",
    "fr": "法文", "法文": "fr",
    "de": "德文", "德文": "de",
    "es": "西班牙文", "西班牙文": "es",
    "ar": "阿拉伯文", "阿拉伯文": "ar"
}