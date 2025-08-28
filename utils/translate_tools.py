from settings.config import LANGUAGE_MAPPING

translate_prompt = """
你是一个专业的、严格的翻译器。请严格遵循以下格式和规则，将[待翻译文本]翻译为{target_language}。

[规则]
1. 逐字逐句进行翻译，不做任何意译或引申。
2. 绝对禁止在翻译结果之外添加任何解释、注释、更正或补充说明。
3. 专有名词（如人名“张伟”）应使用拼音直译（如“Zhang Wei”）。
4. 输出必须纯净，只包含最终译文。

[示例]
待翻译文本：这是我的项目，项目编号是 X-123。
翻译结果：
This is my project, project number is X-123.

[正式任务]
待翻译文本：
{text}
翻译结果：
"""




async def translate(*, request, text: str, target_language: str) -> str:
    """使用本地模型翻译文本"""
    from utils.llm_tools import ollama_llm

    print(f"待翻译的问题：  {text}")
    target_language = LANGUAGE_MAPPING.get(target_language, target_language)
    prompt = translate_prompt.format(target_language=target_language, text=text)

    r = await ollama_llm(question=text, prompt=prompt)
    print(f"翻译后: {r}")


    return r
