import aiohttp
import aiofiles
from io import BytesIO
from pydub import AudioSegment
from utils.auth_v3_zhiyun import add_auth_params
from settings.config import AUDIO_DIR
from settings.config import settings
from core.logger import logger

# 您的应用ID
APP_KEY = settings.zhiyun_app_key
# 您的应用密钥
APP_SECRET = settings.zhiyun_app_secret

async def do_request(url, headers, data):
    """异步发送请求"""
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data, headers=headers) as response:
            if response.status != 200:
                content = await response.read()
                raise Exception(f"API Error: {content.decode('utf-8')}")
            content_type = response.headers.get('Content-Type', '')
            return content_type, await response.read()


async def save_audio(content, file_name):

    """异步保存音频文件"""
    file_path = AUDIO_DIR / file_name
    if not content:
        return False
    try:
        # 从内存里面转为wav
        audio = AudioSegment.from_mp3(BytesIO(content))

        # 设置音频参数
        audio = audio.set_frame_rate(16000) # 16khz
        audio = audio.set_channels(1)

        async with aiofiles.open(file_path, 'wb') as f:
            wav_buffer = BytesIO()
            audio.export(wav_buffer, format='wav')
            await f.write(wav_buffer.getvalue())
        logger.debug(f"16K单声道音频已保存至: {file_path}")
        logger.debug(f"""
                    音频参数验证：
                    采样率: {audio.frame_rate}Hz
                    声道数: {audio.channels}
                    时长: {len(audio) / 1000}s
                    文件大小: {file_path.stat().st_size} bytes
                    """)
        return True
    except Exception as e:
        logger.info(f"保存文件失败: {str(e)}")
        return False


async def tts_main(*, q, voice_name, request, file_name):
    """主异步函数"""
    try:
        data = {
            'q': q,
            'voiceName': voice_name or settings.voice_name,  # 例如："zh-CHS-XiaoxiaoNeural"
            'format': 'mp3'
        }
        # 添加鉴权参数
        add_auth_params(APP_KEY, APP_SECRET, data)

        # 发送异步请求
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        content_type, audio_content = await do_request(
            'https://openapi.youdao.com/ttsapi',
            headers,
            data
        )

        # 处理响应
        if 'audio' in content_type:
            await save_audio(audio_content, file_name)
            if request:
                url = request.url_for("audio_files", path=file_name)
                return {"url": str(url)}
        else:
            logger.error(f"请求异常: {audio_content.decode('utf-8')}")
            url = request.url_for("audio_files", path="fail/zhiyun_fail.wav")
            return {"url": str(url)}
    except Exception as e:
        logger.error(f"操作失败: {str(e)}")


if __name__ == '__main__':
    text = "跟着光 成为光 散发光"
    # asyncio.run(tts_main(q=text, voice_name="youxiaofu", file_name=''))
