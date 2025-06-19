from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
import hashlib
import json
import os
from pathlib import Path
from .pdf_parser import PDFElement, PDFParser
from abc import ABC, abstractmethod

@dataclass
class TranslationResult:
    src_text: str
    translated_text: str
    src_lang: str
    target_lang: str
    page_num: int 
    
class AbstractTranslator(ABC):
    @abstractmethod
    def translate(self, text: str, src_lang: str, target_lang: str) -> Optional[TranslationResult]:
        pass
    
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    def configure(self, config: dict):
        pass

class TranslationEngine:
    def __init__(self, cache_dir: str = "translation_cache"):
        self.translators: Dict[str, AbstractTranslator] = {}
        self.current_translator: Optional[AbstractTranslator] = None
        self.pdf_parser = PDFParser()
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def _get_cache_file(self, file_path: str, src_lang: str, target_lang: str) -> Path:
        """生成缓存文件名"""
        file_hash = hashlib.md5(Path(file_path).read_bytes()).hexdigest()
        return self.cache_dir / f"{file_hash}_{src_lang}_{target_lang}.json"

    def _load_cache(self, cache_file: Path) -> Dict[int, List[TranslationResult]]:
        """加载缓存"""
        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                return {int(k): v for k, v in json.load(f).items()}
        return {}

    def _save_cache(self, cache_file: Path, cache_data: Dict[int, List[TranslationResult]]):
        """保存缓存"""
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)

    def translate_pdf(self, file_path: str, src_lang: str = 'en', target_lang: str = 'zh') -> str:
        """分页翻译PDF并整合结果"""
        cache_file = self._get_cache_file(file_path, src_lang, target_lang)
        cache = self._load_cache(cache_file)
        
        # 获取PDF分页内容
        page_elements = self.pdf_parser.extract_elements_by_page(file_path)
        if not page_elements:
            return "PDF解析失败"
        
        total_pages = len(page_elements)
        final_output = []
        cached_pages = 0

        final_output = []
        for page_num, elements in page_elements.items():
            if page_num in cache:
                final_output.extend([r.translated_text for r in cache[page_num]])
                continue

            for elem in elements:
                if elem.element_type == 'text' and self.current_translator:
                    result = self.current_translator.translate(elem.content, src_lang, target_lang)
                    if result:
                        final_output.append(result.translated_text)
                else:
                    final_output.append(f"\n【保留{elem.element_type}】\n{elem.content}\n")

        return '\n\n'.join(final_output)

    def _format_final_output(self, content_parts: List[str], total_pages: int) -> str:
        """格式化最终输出（添加分页标记）"""
        output = []
        current_page = 1
        
        for part in content_parts:
            output.append(part)
            # 每页内容后添加分页标记（除最后一页）
            if current_page < total_pages:
                output.append(f"\n\n=== 第 {current_page} 页结束 ===\n\n")
                current_page += 1
        
        return "".join(output)
    
    def __init__(self):
        self.translators: Dict[str, AbstractTranslator] = {}
        self.current_translator: Optional[AbstractTranslator] = None
        self.pdf_parser = PDFParser()

    def add_translator(self, name: str, translator: AbstractTranslator):
        self.translators[name] = translator
        if not self.current_translator:
            self.current_translator = translator

    def translate_pdf(self, file_path: str, src_lang: str = 'en', target_lang: str = 'zh') -> str:
        """翻译PDF并保留图表公式"""
        elements = self.pdf_parser.extract_elements(file_path)
        output = []
        
        for elem in elements:
            if elem.element_type == 'text':
                if self.current_translator:
                    result = self.current_translator.translate(elem.content, src_lang, target_lang)
                    output.append(result.translated_text if result else elem.content)
            else:
                output.append(f"\n【保留{elem.element_type}】\n{elem.content}\n")
        
        return '\n\n'.join(output)

    def set_current_translator(self, name: str) -> bool:
        if name in self.translators:
            self.current_translator = self.translators[name]
            return True
        return False

    def get_available_translators(self) -> List[str]:
        return list(self.translators.keys())