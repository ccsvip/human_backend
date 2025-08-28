import re
import aiohttp
import json
import aiofiles
from settings.config import settings, PROMPT_PATH
from urllib.parse import urlparse, parse_qs, unquote

def get_tag_url(text: str) -> dict:
    # 匹配Markdown图片格式: ![描述](URL)
    markdown_image_pattern = r'!\[(.*?)\]\((.*?)\)'
    # 匹配普通Markdown链接格式: [描述](URL)
    markdown_link_pattern = r'\[(.*?)\]\((.*?)\)'

    # 1. 优先尝试匹配Markdown图片格式
    image_match = re.search(markdown_image_pattern, text)
    if image_match:
        title = image_match.group(1)
        link = image_match.group(2)
        is_markdown = True
    else:
        # 2. 尝试匹配普通Markdown链接格式
        link_match = re.search(markdown_link_pattern, text)
        if link_match:
            title = link_match.group(1)
            link = link_match.group(2)
            is_markdown = False
        else:
            # 3. 最后尝试匹配纯URL格式
            url_pattern = r'(https?://[^\s<]+[^)\s\.,!<])'  # 改进：排除结尾标点
            url_match = re.search(url_pattern, text)
            if url_match:
                link = url_match.group(1)
                title = ""
                is_markdown = False
            else:
                return {"title": "", "link": ""}

    # 处理特殊参数
    if '&version_id=null' in link:
        link = link.split('&version_id=null')[0]

    # 修复URL结尾问题
    link = link.rstrip('?&')  # 移除结尾的?和&

    # 尝试从URL参数/路径中提取标题（仅当无描述时）
    if not title:
        if '&prefix=' in link:
            try:
                parsed = urlparse(link)
                query = parse_qs(parsed.query)
                if 'prefix' in query:
                    title = unquote(query['prefix'][0])
                    if '.' in title:
                        title = title.split('.', 1)[0]
            except Exception:
                pass
        elif '.' in link.split('/')[-1]:
            filename = link.split('/')[-1].split('?')[0]
            title = filename.rsplit('.', 1)[0] if '.' in filename else filename

    return {"title": title, "link": link}




# ---- 纠错模型
prompt_content = ''

async def load_prompt():
    async with aiofiles.open(PROMPT_PATH, 'r', encoding="utf-8") as f:
        global prompt_content
        prompt_content = await f.read()

async def ollama_llm(*, question:str, prompt='', **kwargs):
    """ 纠错的时候不要传递prompt """
    if not prompt:
        await load_prompt()
        real_prompt = prompt_content.format(question)
    else:
        real_prompt = prompt


    model_url = settings.model_url
    data = {
        "model": settings.model_name,
        "prompt": real_prompt,
        "options": {
            "response_format": {"type": "text"},
            "streaming": True,
            "temperature":0.1,    # 降低随机性
            "top_p":0.8,         # 限制词汇选择范围
            "repeat_penalty":1.1  # 避免重复
        },
        "stream": True
    }

    # print(f"提示词: \n\n {prompt_content}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(model_url, json=data) as response:
                response.raise_for_status()

                answer = ''
                # print("\n--- 模型流式回复 ---")
                # 迭代响应的每一行
                async for line in response.content:
                    if line:
                        # 解码 bytes 为 string，然后解析 JSON
                        chunk = json.loads(line.decode('utf-8'))
                        # 打印出每个数据块中的 response 部分
                        answer += chunk.get('response', '').replace(r"<think>", "").replace(r"</think>", "")

                        # print(answer)

                        # 如果是最后一块数据，Ollama会返回 done: True
                        if chunk.get('done'):
                            # print("\n--- 流式传输结束 ---")
                            break
                clean_text = answer.strip().strip("？?。.>")

                # print("清理后", clean_text)

                return clean_text

    except aiohttp.ClientConnectorError:
        print(f"错误: 无法连接到 Ollama 服务于 {model_url}。请检查服务是否正在运行以及IP地址是否正确。")
        return question
    except aiohttp.ClientResponseError as e:
        # import traceback
        # traceback.print_exc()
        print(f"错误: Ollama 服务器返回错误状态 {e.status}: {e.message}")
        return question
    except Exception as e:
        print(f"发生未知错误: {e}")
        return question



# 判断是否正常的图片
async def is_real_image(url: str, timeout=3) -> bool:
    try:
        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/127.0.0.1 Safari/537.36",
            "Range": "bytes=0-1023"
        }
        async with aiohttp.ClientSession(timeout=timeout_obj) as client:
            async with client.get(url, allow_redirects=True, headers=headers) as resp:
                if not resp.ok:
                    return False
                return resp.headers.get("Content-Type", "").lower().startswith("image/")
    except aiohttp.ClientError:
        return False

# ---- 文本时间规范化（用于TTS前处理）
from core.logger import logger

def normalize_time_range(text: str) -> str:
    """
    将类似 "21:30-21:45" / "21：30～21：45" 以及被上游清理为
    "21:30 21:45" 的时间范围转换为
    "21点30分到21点45分"（或“至”），以便中文TTS正确朗读。

    仅处理范围时间，不处理单个时间点。
    """
    def replacer(match: re.Match) -> str:
        h1, m1, h2, m2 = match.groups()
        try:
            return f"{int(h1)}点{int(m1)}分到{int(h2)}点{int(m2)}分"
        except Exception:
            # 容错：若转换失败，返回原始片段
            return match.group(0)

    # 1) 含连接符（-, —, –, －, ~, ～, 〜, ﹘, ﹣）与全角冒号
    pattern_dash = re.compile(r"(?<!\d)(\d{1,2})\s*[:：]\s*(\d{1,2})\s*[\-—–－~～〜﹘﹣]\s*(\d{1,2})\s*[:：]\s*(\d{1,2})(?!\d)")
    text = re.sub(pattern_dash, replacer, text)

    # 2) 连接符被上游替换为空格的情况：两个时间之间只有空白
    #    可兼容已有“到/至”残留，统一替换为“到”
    pattern_space = re.compile(r"(?<!\d)(\d{1,2})\s*[:：]\s*(\d{1,2})\s+(?:到|至)?\s*(\d{1,2})\s*[:：]\s*(\d{1,2})(?!\d)")
    text = re.sub(pattern_space, replacer, text)

    return text

# ---- 年龄范围规范化（用于TTS前处理）

def normalize_age_range(text: str) -> str:
    """
    处理年龄范围：
    - 3-8岁 / 3～8岁 / 3 — 8 岁 → 3到8岁
    - 3 8岁（上游把连接符替换为空格） → 3到8岁
    - 也兼容“到/至”已存在的情况，统一为“到”
    优先级：在时间范围处理之后执行，避免冲突。
    """
    def replacer(m: re.Match) -> str:
        a1, a2 = m.groups()
        try:
            return f"{int(a1)}到{int(a2)}岁"
        except Exception:
            return m.group(0)

    # 1) 带连接符的年龄范围
    pattern_age_dash = re.compile(r"(?<!\d)(\d{1,3})\s*[\-—–－~～〜﹘﹣]\s*(\d{1,3})\s*岁")
    text = re.sub(pattern_age_dash, replacer, text)

    # 2) 连接符被替换为空格或已写成到/至：两个数字之间只有空白或‘到|至’，随后紧跟‘岁’
    pattern_age_space = re.compile(r"(?<!\d)(\d{1,3})\s+(?:到|至)?\s*(\d{1,3})\s*岁")
    text = re.sub(pattern_age_space, replacer, text)

    # 3) “年”也作为年龄单位的别名
    pattern_year_dash = re.compile(r"(?<!\d)(\d{1,3})\s*[\-—–－~～〜﹘﹣]\s*(\d{1,3})\s*年")
    text = re.sub(pattern_year_dash, lambda m: f"{int(m.group(1))}到{int(m.group(2))}年", text)

    pattern_year_space = re.compile(r"(?<!\d)(\d{1,3})\s+(?:到|至)?\s*(\d{1,3})\s*年")
    text = re.sub(pattern_year_space, lambda m: f"{int(m.group(1))}到{int(m.group(2))}年", text)

    return text



def normalize_time_expressions(text: str) -> str:
    """
    综合时间与年龄规范化：
    - 优先将时间范围如 "21:30-21:45" 转为 "21点30分到21点45分"；
    - 将年龄范围如 "3-8岁" 转为 "3到8岁"；
    - 再将单个时间点如 "21:30" 转为 "21点30分"；
    - 尽量避免误伤，按“时间范围 -> 年龄范围 -> 单点时间”顺序处理。
    """
    if not text:
        return text

    original = text

    # 1) 时间范围
    text = normalize_time_range(text)

    # 2) 年龄范围（单位：岁/年），放在时间范围之后，避免冲突
    text = normalize_age_range(text)

    # 3) 单个时间点（避免再次处理已转好的“点/分”）
    def single_replacer(m: re.Match) -> str:
        h, m1 = m.groups()
        try:
            return f"{int(h)}点{int(m1)}分"
        except Exception:
            return m.group(0)

    single_pattern = re.compile(r"(?<!\d)(\d{1,2})\s*[:：]\s*(\d{1,2})(?!\d)")
    text = re.sub(single_pattern, single_replacer, text)

    if text != original:
        try:
            logger.debug(f"normalize_time_expressions: {original} -> {text}")
        except Exception:
            pass
    return text
