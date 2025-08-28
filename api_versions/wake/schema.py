from pydantic import BaseModel, computed_field
from datetime import datetime
from pypinyin import pinyin, Style
import re


class WakeWordSchema(BaseModel):
    id: int
    word: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def pinyin_format(self) -> str:
        """生成拼音格式: 拼音 @唤醒词，格式与keywords.txt一致"""
        # 声母列表，按长度排序以确保优先匹配较长的声母
        initials = ['zh', 'ch', 'sh', 'b', 'p', 'm', 'f', 'd', 't', 'n', 'l', 'g', 'k', 'h', 
                   'j', 'q', 'x', 'r', 'z', 'c', 's', 'y', 'w']
        
        result = []
        
        # 处理每个汉字
        for char in self.word:
            char_pinyin = pinyin(char, style=Style.TONE, heteronym=False)
            if char_pinyin and char_pinyin[0]:
                # 获取拼音字符串
                pinyin_str = char_pinyin[0][0]
                
                # 查找声母
                found_initial = False
                for initial in initials:
                    if pinyin_str.startswith(initial):
                        # 找到声母，分离声母和韵母
                        result.append(initial)
                        result.append(pinyin_str[len(initial):])
                        found_initial = True
                        break
                
                # 如果没有找到声母，可能是只有韵母的情况（如"啊"的拼音是"a"）
                if not found_initial:
                    result.append(pinyin_str)
        
        # 用空格连接所有拼音部分
        pinyin_result = ' '.join(result)
        return f"{pinyin_result} @{self.word}"

    class Config:
        from_attributes = True





class WakeWordCreateSchema(BaseModel):
    word: str 
    description: str | None = None



