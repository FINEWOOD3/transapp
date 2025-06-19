import re
import PyPDF2
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional
import pdfminer.high_level
import hashlib
import json
import os

@dataclass
class PDFElement:
    content: str
    element_type: str  # 'text'/'figure'/'table'/'formula'
    page_num: int 

class PDFParser:
    # 匹配规则
    FIGURE_PATTERNS = [
        re.compile(r'(Figure|Fig\.?)\s+\d+[:\.]', re.IGNORECASE),  # 英文
        re.compile(r'(图|图表)\s*\d+[:：]')  # 中文
    ]
    TABLE_PATTERNS = [
        re.compile(r'Table\s+\d+[:\.]', re.IGNORECASE),
        re.compile(r'表\s*\d+[:：]')
    ]
    FORMULA_PATTERNS = [
        re.compile(r'\$(.*?)\$'),  # 行内公式
        re.compile(r'\\begin{equation}(.*?)\\end{equation}', re.DOTALL),  # LaTeX
        re.compile(r'\\[(.*?)\\]')  # 简单公式
    ]

    def __init__(self):
        self._backends = [self._extract_with_pypdf2, self._extract_with_pdfminer]

    def extract_elements(self, file_path: str) -> List[PDFElement]:
        """提取PDF元素并分类"""
        if not Path(file_path).exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        raw_text = self.extract_text(file_path)
        if not raw_text:
            return []

        elements  = []
        paragraphs = [p.strip() for p in raw_text.split('\n\n') if p.strip()]
    
        # 获取PDF总页数用于设置page_num（因为这是全文提取，默认设为第1页）
        with open(file_path, 'rb') as f:
            total_pages = len(PyPDF2.PdfReader(f).pages)
    
        for para in paragraphs:
            elem_type = self._classify_element(para)
            elements.append(PDFElement(
                content=para,
                element_type=elem_type,
                page_num=1  # 全文提取无法分页，统一设为第1页
            ))
    
        return elements

    def extract_text(self, file_path: str) -> Optional[str]:
        """提取原始文本（自动选择解析引擎）"""
        for backend in self._backends:
            text = backend(file_path)
            if text and text.strip():
                return text
        return None

    def _extract_with_pypdf2(self, file_path: str) -> Optional[str]:
        """使用PyPDF2提取"""
        try:
            with open(file_path, 'rb') as f:
                return "\n\n".join(
                    page.extract_text() 
                    for page in PyPDF2.PdfReader(f).pages
                    if page.extract_text()
                )
        except Exception:
            return None

    def _extract_with_pdfminer(self, file_path: str) -> Optional[str]:
        """使用pdfminer作为后备"""
        try:
            return pdfminer.high_level.extract_text(file_path)
        except Exception:
            return None

    def _classify_element(self, text: str) -> str:
        """元素分类逻辑"""
        if any(p.search(text) for p in self.FIGURE_PATTERNS):
            return 'figure'
        if any(p.search(text) for p in self.TABLE_PATTERNS):
            return 'table'
        if any(p.search(text) for p in self.FORMULA_PATTERNS):
            return 'formula'
        return 'text'
    
    def extract_elements_by_page(self, file_path: str) -> Dict[int, List[PDFElement]]:
        """按页提取PDF元素"""
        if not Path(file_path).exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 使用PyPDF2获取总页数
        with open(file_path, 'rb') as f:
            total_pages = len(PyPDF2.PdfReader(f).pages)

        page_elements = {}
        for page_num in range(1, total_pages + 1):
            try:
                # 使用pdfminer逐页提取文本（更准确）
                text = pdfminer.high_level.extract_text(
                    file_path, 
                    page_numbers=[page_num-1],  # pdfminer从0开始计数
                    caching=True
                )
                
                elements = []
                for para in [p.strip() for p in text.split('\n\n') if p.strip()]:
                    elem_type = self._classify_element(para)
                    elements.append(PDFElement(para, elem_type, page_num))
                
                page_elements[page_num] = elements
            except Exception as e:
                print(f"第{page_num}页解析失败: {str(e)}")
                continue

        return page_elements

    @staticmethod
    def is_pdf(file_path: str) -> bool:
        """检查文件是否为PDF"""
        return Path(file_path).suffix.lower() == '.pdf'