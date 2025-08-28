import aiohttp
import asyncio
import time
import uuid
import hashlib
from core.logger import logger
from settings.config import settings


async def translate_youdao_async(text: str, src_lang="auto", tgt_lang="en", **kwargs) -> str:
    from utils.tools import remove_emojis

    # 中文不翻译
    if tgt_lang in ['zh', 'zh-CHS'] or len(tgt_lang) == 0:
        return text

    url = "https://openapi.youdao.com/api"

    app_key = settings.zhiyun_translate_apikey
    app_secret = settings.zhiyun_translate_secret
    text = await remove_emojis(text=text)


    # 签名 input 处理
    if len(text) <= 20:
        input_text = text
    else:
        input_text = text[:10] + str(len(text)) + text[-10:]
    curtime = str(int(time.time()))
    salt = str(uuid.uuid4())
    sign_str = app_key + input_text + salt + curtime + app_secret
    sign = hashlib.sha256(sign_str.encode('utf-8')).hexdigest()

    params = {
        'q': text,
        'from': src_lang,
        'to': tgt_lang,
        'appKey': app_key,
        'salt': salt,
        'sign': sign,
        'signType': 'v3',
        'curtime': curtime
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP error: {resp.status}")
                jd = await resp.json()
                if jd.get("errorCode") == "0":
                    return jd["translation"][0]
                else:
                    raise RuntimeError(f"API error: {jd.get('errorCode')}")
    except Exception as e:
        print(f"error: {e}")
        return ''
        

# 🧪 测试入口
if __name__ == "__main__":
    q = """
        您好，关于您提到的附近有没有商场，这里有几个推荐的商场哦～

        天河城：位于天河区天河路208号，地铁1号线体育西路站直达，是广州地标级大型购物中心，品牌丰富，适合购物和休闲。

        太古汇：位于天河区天河路383号，地铁3号线石牌桥站直达，高端购物、餐饮、艺术空间，适合追求品质生活的您。

        正佳广场：位于天河区天河路228号，地铁1号线体育中心站直达，集购物、娱乐、餐饮于一体的大型商场，适合家庭和朋友聚会。

        天环广场：位于天河区天河路218号，地铁APM线天河南站直达，时尚品牌、餐饮丰富、环境舒适，适合喜欢时尚和美食的您。

        万达广场（白云店）：位于白云区云城东路501号，地铁2号线飞翔公园站直达，综合性商圈，购物、娱乐、餐饮齐全，适合喜欢热闹的您。

        希望这些建议能让您找到合适的商场，享受愉快的购物时光！
    """

    async def main():
        try:
            result = await translate_youdao_async(q)
            print("翻译结果：", result)
        except Exception as e:
            print("出错：", e)

    asyncio.run(main())
