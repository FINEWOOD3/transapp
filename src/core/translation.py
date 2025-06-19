from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
import hashlib
import json
import os
from pathlib import Path
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

@dataclass
class PDFElement:
    content: str
    element_type: str  # 'text'/'figure'/'table'/'formula'
    page_num: int
    bbox: Optional[Tuple[float, float, float, float]] = None

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

class PDFParser:
    def extract_elements(self, file_path: str) -> List[PDFElement]:
        """提取PDF元素（简化版实现）"""
        # 实际实现应包含PDF解析逻辑
        return []

    def extract_elements_by_page(self, file_path: str) -> Dict[int, List[PDFElement]]:
        """分页提取PDF元素（简化版实现）"""
        # 实际实现应包含分页解析逻辑
        return {}

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
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return {int(k): [TranslationResult(**r) for r in v] 
                          for k, v in json.load(f).items()}
            except Exception as e:
                logger.warning(f"缓存加载失败: {e}")
        return {}

    def _save_cache(self, cache_file: Path, cache_data: Dict[int, List[TranslationResult]]):
        """保存缓存"""
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    k: [vars(r) for r in v] 
                    for k, v in cache_data.items()
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"缓存保存失败: {e}")

    def add_translator(self, name: str, translator: AbstractTranslator):
        """添加翻译器"""
        self.translators[name] = translator
        if not self.current_translator:
            self.current_translator = translator

    def set_current_translator(self, name: str) -> bool:
        """设置当前翻译器"""
        if name in self.translators:
            self.current_translator = self.translators[name]
            return True
        return False

    def get_available_translators(self) -> List[str]:
        """获取可用翻译器列表"""
        return list(self.translators.keys())

    def translate_pdf(self, file_path: str, src_lang: str = 'en', 
                     target_lang: str = 'zh', progress_callback=None) -> str:
        """
        翻译PDF文档（带缓存和进度反馈）
        
        参数:
            file_path: PDF文件路径
            src_lang: 源语言代码
            target_lang: 目标语言代码
            progress_callback: 进度回调函数 (current, total)
            
        返回:
            翻译后的文本
        """
        cache_file = self._get_cache_file(file_path, src_lang, target_lang)
        cache = self._load_cache(cache_file)
        new_cache = {}
        
        if not self.current_translator:
            raise ValueError("未设置翻译器")

        # 获取PDF分页内容
        page_elements = self.pdf_parser.extract_elements_by_page(file_path)
        if not page_elements:
            return "PDF解析失败"
        
        total_pages = len(page_elements)
        final_output = []
        processed_pages = 0

        for page_num, elements in page_elements.items():
            page_results = []
            
            # 使用缓存内容
            if page_num in cache:
                final_output.extend(r.translated_text for r in cache[page_num])
                processed_pages += 1
                if progress_callback:
                    progress_callback(processed_pages, total_pages)
                continue

            # 处理当前页元素
            for elem in elements:
                if elem.element_type == 'text':
                    result = self.current_translator.translate(
                        elem.content, src_lang, target_lang)
                    if result:
                        page_results.append(result)
                        final_output.append(result.translated_text)
                else:
                    final_output.append(f"\n【保留{elem.element_type}】\n{elem.content}\n")
            
            # 缓存当前页结果
            if page_results:
                new_cache[page_num] = page_results
            
            processed_pages += 1
            if progress_callback:
                progress_callback(processed_pages, total_pages)

        # 保存新缓存
        if new_cache:
            self._save_cache(cache_file, {**cache, **new_cache})

        return self._format_final_output(final_output, total_pages)

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