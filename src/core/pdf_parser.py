import re
import PyPDF2
import pdfminer.high_level
import pdfminer.layout
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import hashlib
from dataclasses import dataclass
import io
import base64
import sqlite3
import logging
from datetime import datetime

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PDFElement:
    """PDF元素数据类"""
    content: str
    element_type: str  # 'text'/'figure'/'table'/'formula'
    page_num: int
    binary_data: Optional[bytes] = None
    element_index: Optional[int] = None
    bbox: Optional[Tuple[float, float, float, float]] = None  # (x0, y0, x1, y1)

class PDFElementDB:
    """PDF元素数据库处理类"""
    
    def __init__(self, db_path: str = "data/pdf_elements.db"):
        """
        初始化数据库
        :param db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            # 启用外键约束
            conn.execute("PRAGMA foreign_keys = ON")
            
            # PDF文件表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pdf_files (
                    file_id TEXT PRIMARY KEY,
                    file_path TEXT UNIQUE NOT NULL,
                    file_hash TEXT NOT NULL,
                    total_pages INTEGER NOT NULL,
                    last_processed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 元素表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS elements (
                    element_id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    element_type TEXT NOT NULL,
                    content TEXT,
                    binary_data BLOB,
                    page_num INTEGER NOT NULL,
                    element_index INTEGER NOT NULL,
                    bbox TEXT,  -- 存储为"x0,y0,x1,y1"
                    FOREIGN KEY (file_id) REFERENCES pdf_files (file_id) ON DELETE CASCADE
                )
            """)
            
            # 创建索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_elements_file ON elements (file_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_elements_page ON elements (file_id, page_num)
            """)
            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        return sqlite3.connect(str(self.db_path))

    def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件哈希值"""
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    def store_pdf_elements(
        self, 
        file_path: str, 
        elements: List[PDFElement], 
        total_pages: int
    ) -> str:
        """
        存储PDF元素到数据库
        :param file_path: PDF文件路径
        :param elements: PDF元素列表
        :param total_pages: PDF总页数
        :return: 文件ID
        """
        file_path = str(Path(file_path).absolute())
        file_hash = self._calculate_file_hash(file_path)
        file_id = hashlib.md5(file_path.encode()).hexdigest()

        with self._get_connection() as conn:
            try:
                # 开始事务
                conn.execute("BEGIN TRANSACTION")
                
                # 插入或更新PDF文件记录
                conn.execute("""
                    INSERT OR REPLACE INTO pdf_files 
                    (file_id, file_path, file_hash, total_pages)
                    VALUES (?, ?, ?, ?)
                """, (file_id, file_path, file_hash, total_pages))
                
                # 删除旧元素（如果存在）
                conn.execute("DELETE FROM elements WHERE file_id = ?", (file_id,))
                
                # 插入新元素
                for idx, element in enumerate(elements):
                    element_id = f"{file_id}_{element.element_type}_{idx}"
                    bbox_str = (
                        ",".join(map(str, element.bbox)) 
                        if element.bbox else None
                    )
                    
                    conn.execute("""
                        INSERT INTO elements (
                            element_id, file_id, element_type, content,
                            binary_data, page_num, element_index, bbox
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        element_id,
                        file_id,
                        element.element_type,
                        element.content,
                        element.binary_data,
                        element.page_num,
                        idx,
                        bbox_str
                    ))
                
                conn.commit()
                logger.info(f"Stored {len(elements)} elements for {file_path}")
                return file_id
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to store elements: {str(e)}")
                raise

    def get_elements_by_file(self, file_path: str) -> List[PDFElement]:
        """根据文件路径获取所有元素"""
        file_id = hashlib.md5(str(Path(file_path).absolute()).encode()).hexdigest()
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    element_type, content, binary_data, 
                    page_num, element_index, bbox
                FROM elements
                WHERE file_id = ?
                ORDER BY page_num, element_index
            """, (file_id,))
            
            elements = []
            for row in cursor.fetchall():
                bbox = (
                    tuple(map(float, row[5].split(','))) 
                    if row[5] else None
                )
                elements.append(PDFElement(
                    content=row[1],
                    element_type=row[0],
                    page_num=row[3],
                    binary_data=row[2],
                    element_index=row[4],
                    bbox=bbox
                ))
            return elements

    def get_file_metadata(self, file_path: str) -> Optional[Dict]:
        """获取PDF文件元数据"""
        file_id = hashlib.md5(str(Path(file_path).absolute()).encode()).hexdigest()
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT file_path, file_hash, total_pages, last_processed
                FROM pdf_files
                WHERE file_id = ?
            """, (file_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'file_path': row[0],
                    'file_hash': row[1],
                    'total_pages': row[2],
                    'last_processed': row[3]
                }
            return None

class PDFParser:
    """PDF解析器，支持文本、图像、表格和公式提取"""
    
    # 元素匹配规则
    FIGURE_PATTERNS = [
        re.compile(r'(Figure|Fig\.?)\s+\d+[:\.]', re.IGNORECASE),
        re.compile(r'(图|图表)\s*\d+[:：]')
    ]
    TABLE_PATTERNS = [
        re.compile(r'Table\s+\d+[:\.]', re.IGNORECASE),
        re.compile(r'表\s*\d+[:：]')
    ]
    FORMULA_PATTERNS = [
        re.compile(r'\$(.*?)\$'),
        re.compile(r'\\begin{equation}(.*?)\\end{equation}', re.DOTALL),
        re.compile(r'\\[(.*?)\\]')
    ]

    def __init__(self):
        """初始化解析器"""
        self.db = PDFElementDB()
        self._current_file_hash = None

    def parse_and_store(self, file_path: str) -> List[PDFElement]:
        """
        解析PDF并存储元素到数据库
        :param file_path: PDF文件路径
        :return: 解析后的元素列表
        """
        file_path = str(Path(file_path).absolute())
        
        # 检查文件是否需要重新解析
        file_metadata = self.db.get_file_metadata(file_path)
        current_hash = self.db._calculate_file_hash(file_path)
        
        if (file_metadata and file_metadata['file_hash'] == current_hash):
            logger.info(f"Using cached elements for {file_path}")
            return self.db.get_elements_by_file(file_path)
        
        # 提取元素
        with open(file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            total_pages = len(pdf_reader.pages)
        
        text_elements = self._extract_text_elements(file_path)
        image_elements = self._extract_images(file_path)
        
        # 合并并排序元素
        all_elements = text_elements + image_elements
        all_elements.sort(key=lambda x: (x.page_num, x.element_index or 0))
        
        # 存储到数据库
        self.db.store_pdf_elements(file_path, all_elements, total_pages)
        return all_elements

    def _extract_text_elements(self, file_path: str) -> List[PDFElement]:
        """提取文本元素"""
        elements = []
        
        try:
            # 使用pdfminer提取带位置信息的文本
            laparams = pdfminer.layout.LAParams()
            with open(file_path, 'rb') as f:
                for page_num, (page, layout) in enumerate(
                    pdfminer.high_level.extract_pages(f, laparams=laparams), 
                    start=1
                ):
                    for element_idx, element in enumerate(layout):
                        if isinstance(element, pdfminer.layout.LTTextBox):
                            text = element.get_text().strip()
                            if not text:
                                continue
                                
                            elem_type = self._classify_element(text)
                            elements.append(PDFElement(
                                content=text,
                                element_type=elem_type,
                                page_num=page_num,
                                element_index=element_idx,
                                bbox=(
                                    element.x0, element.y0, 
                                    element.x1, element.y1
                                )
                            ))
        except Exception as e:
            logger.error(f"Error extracting text: {str(e)}")
            # 回退到简单文本提取
            raw_text = self._extract_raw_text(file_path)
            if raw_text:
                for para in [p.strip() for p in raw_text.split('\n\n') if p.strip()]:
                    elements.append(PDFElement(
                        content=para,
                        element_type=self._classify_element(para),
                        page_num=1,
                        element_index=len(elements)
                    ))
        
        return elements

    def _extract_raw_text(self, file_path: str) -> Optional[str]:
        """提取原始文本（无格式）"""
        try:
            return pdfminer.high_level.extract_text(file_path)
        except Exception as e:
            logger.warning(f"pdfminer failed: {str(e)}")
            try:
                with open(file_path, 'rb') as f:
                    return "\n".join(
                        page.extract_text() 
                        for page in PyPDF2.PdfReader(f).pages
                        if page.extract_text()
                    )
            except Exception as e:
                logger.error(f"PyPDF2 failed: {str(e)}")
                return None

    def _extract_images(self, file_path: str) -> List[PDFElement]:
        """提取PDF中的图像"""
        images = []
        try:
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                
                for page_num, page in enumerate(pdf_reader.pages, start=1):
                    if '/XObject' not in page.get('/Resources', {}):
                        continue
                        
                    x_objects = page['/Resources']['/XObject'].get_object()
                    
                    for obj_name, obj in x_objects.items():
                        if obj.get('/Subtype') == '/Image':
                            try:
                                image_data = obj._data
                                if isinstance(image_data, bytes):
                                    # 存储为base64编码
                                    base64_data = base64.b64encode(image_data)
                                    images.append(PDFElement(
                                        content=f"Image_{page_num}_{len(images)}",
                                        element_type='figure',
                                        page_num=page_num,
                                        binary_data=base64_data,
                                        element_index=len(images)
                                    ))
                            except Exception as e:
                                logger.warning(f"Image extraction failed: {str(e)}")
        except Exception as e:
            logger.error(f"Image extraction error: {str(e)}")
        
        return images

    def _classify_element(self, text: str) -> str:
        """元素分类逻辑"""
        if any(p.search(text) for p in self.FIGURE_PATTERNS):
            return 'figure'
        if any(p.search(text) for p in self.TABLE_PATTERNS):
            return 'table'
        if any(p.search(text) for p in self.FORMULA_PATTERNS):
            return 'formula'
        return 'text'

    def clear_cache(self, file_path: str = None) -> None:
        """
        清除缓存数据
        :param file_path: 指定文件路径或清除所有缓存
        """
        with self.db._get_connection() as conn:
            if file_path:
                file_id = hashlib.md5(str(Path(file_path).absolute()).encode()).hexdigest()
                conn.execute("DELETE FROM pdf_files WHERE file_id = ?", (file_id,))
            else:
                conn.execute("DELETE FROM pdf_files")
            conn.commit()

