from abc import ABC, abstractmethod
from typing import Optional

class TranslationResult:
    def __init__(self, src_text: str, translated_text: str, src_lang: str, target_lang: str):
        self.src_text = src_text
        self.translated_text = translated_text
        self.src_lang = src_lang
        self.target_lang = target_lang

class AbstractTranslator(ABC):
    @abstractmethod
    def translate(self, text: str, src_lang: str = 'en', target_lang: str = 'zh') -> Optional[TranslationResult]:
        """抽象翻译方法"""
        pass
    
    @abstractmethod
    def name(self) -> str:
        """返回翻译服务名称"""
        pass
    
    @abstractmethod
    def configure(self, config: dict):
        """配置翻译服务"""
        pass